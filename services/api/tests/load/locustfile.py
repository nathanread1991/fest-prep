"""Locust load test for Festival Playlist Generator API.

Simulates realistic user traffic patterns against the API to validate
performance requirements:
  - API response time < 200ms (p95) with caching
  - Search operations < 300ms (p95)
  - Support 100 concurrent users (initial target)

Note on rate limiting:
  The API enforces 60 req/min per IP (app-level) and the AWS WAF
  enforces 1000 req/5min per IP. When running from a single machine
  all Locust users share one IP, so 429 and 403 responses are expected.
  The test treats both as successful rate-limiter behaviour and tracks
  them separately from real errors.

Usage:
  # Local testing:
  locust -f locustfile.py --host=http://localhost:8000 \
      --users 100 --spawn-rate 10 --run-time 2m --headless

  # AWS testing (recommended: 5min+ with slow ramp):
  locust -f locustfile.py --host=https://api.gig-prep.co.uk \
      --users 50 --spawn-rate 5 --run-time 5m --headless

  # AWS with warm-up (best results):
  #   Step 1: Warm caches and Aurora with light traffic
  locust -f locustfile.py --host=https://api.gig-prep.co.uk \
      --users 10 --spawn-rate 2 --run-time 2m --headless
  #   Step 2: Run the real test
  locust -f locustfile.py --host=https://api.gig-prep.co.uk \
      --users 100 --spawn-rate 10 --run-time 5m --headless

Requirements: US-7.4
"""

import random

from locust import HttpUser, between, events, task

# Counters for tracking rate-limited vs real requests
_rate_limited_count = 0
_waf_blocked_count = 0
_successful_count = 0


def _get(client, url, name):  # type: ignore[no-untyped-def]
    """GET helper that treats 429/403 as rate-limiting, not errors."""
    global _rate_limited_count, _waf_blocked_count, _successful_count
    with client.get(url, catch_response=True, name=name) as resp:
        if resp.status_code == 429:
            _rate_limited_count += 1
            resp.success()
        elif resp.status_code == 403:
            _waf_blocked_count += 1
            resp.success()  # WAF rate-limit, not a real error
        elif resp.status_code >= 400:
            resp.failure(f"HTTP {resp.status_code}")
        else:
            _successful_count += 1


def _post(client, url, payload, name):  # type: ignore[no-untyped-def]
    """POST helper that treats 429/403 as rate-limiting."""
    global _rate_limited_count, _waf_blocked_count, _successful_count
    with client.post(url, json=payload, catch_response=True, name=name) as resp:
        if resp.status_code == 429:
            _rate_limited_count += 1
            resp.success()
        elif resp.status_code == 403:
            _waf_blocked_count += 1
            resp.success()
        elif resp.status_code in (200, 201, 422):
            _successful_count += 1
        else:
            resp.failure(f"HTTP {resp.status_code}")


class HealthCheckUser(HttpUser):
    """Lightweight user that only hits the health endpoint.

    Health endpoint bypasses app-level rate limiting, so this provides
    a clean baseline for raw server performance. WAF may still block.
    """

    weight = 1
    wait_time = between(2, 5)

    @task
    def health(self) -> None:
        _get(self.client, "/health", "/health")


class BrowsingUser(HttpUser):
    """Simulates a user browsing festivals and artists (read-heavy).

    Most common traffic pattern — searching and viewing details.
    """

    weight = 6
    wait_time = between(1, 3)

    @task(5)
    def list_festivals(self) -> None:
        _get(self.client, "/api/v1/festivals/?skip=0&limit=20", "/api/v1/festivals")

    @task(4)
    def search_festivals(self) -> None:
        q = random.choice(["rock", "jazz", "summer", "music", "fest"])  # noqa: S311
        _get(
            self.client,
            f"/api/v1/festivals/search/?q={q}&limit=10",
            "/api/v1/festivals/search",
        )

    @task(4)
    def list_artists(self) -> None:
        _get(self.client, "/api/v1/artists/?skip=0&limit=20", "/api/v1/artists")

    @task(3)
    def search_artists(self) -> None:
        q = random.choice(["radiohead", "arctic", "foo", "the", "daft"])  # noqa: S311
        _get(
            self.client,
            f"/api/v1/artists/search/?q={q}&limit=10",
            "/api/v1/artists/search",
        )

    @task(2)
    def get_festival_detail(self) -> None:
        _get(self.client, "/api/v1/festivals/1", "/api/v1/festivals/{id}")

    @task(2)
    def get_artist_detail(self) -> None:
        _get(self.client, "/api/v1/artists/1", "/api/v1/artists/{id}")

    @task(1)
    def list_playlists(self) -> None:
        _get(self.client, "/api/v1/playlists/?skip=0&limit=20", "/api/v1/playlists")


class PlaylistCreatorUser(HttpUser):
    """Simulates a user who creates playlists (write-heavy)."""

    weight = 2
    wait_time = between(2, 5)

    @task(3)
    def browse_then_create(self) -> None:
        _get(self.client, "/api/v1/festivals/?skip=0&limit=10", "/api/v1/festivals")

    @task(1)
    def create_festival(self) -> None:
        payload = {
            "name": f"Load Test Festival {random.randint(1, 100000)}",  # noqa: S311
            "location": "Test Venue, London",
            "year": 2026,
        }
        _post(self.client, "/api/v1/festivals/", payload, "/api/v1/festivals [POST]")

    @task(1)
    def list_setlists(self) -> None:
        _get(self.client, "/api/v1/setlists/?skip=0&limit=10", "/api/v1/setlists")


class APIStressUser(HttpUser):
    """Rapid-fire requests to stress-test caching and connection pooling."""

    weight = 1
    wait_time = between(0.1, 0.5)

    @task(3)
    def cached_festival_list(self) -> None:
        _get(
            self.client,
            "/api/v1/festivals/?skip=0&limit=10",
            "/api/v1/festivals (stress)",
        )

    @task(3)
    def cached_artist_list(self) -> None:
        _get(
            self.client,
            "/api/v1/artists/?skip=0&limit=10",
            "/api/v1/artists (stress)",
        )

    @task(1)
    def health_rapid(self) -> None:
        _get(self.client, "/health", "/health (stress)")


# ---------------------------------------------------------------------------
# Event hooks for reporting
# ---------------------------------------------------------------------------


@events.quitting.add_listener
def _print_summary(environment, **kwargs):  # type: ignore[no-untyped-def]
    """Print a performance summary when the test finishes."""
    stats = environment.runner.stats
    total = stats.total

    if total.num_requests == 0:
        print("\n⚠️  No requests were made.")
        return

    p50 = total.get_response_time_percentile(0.50) or 0
    p95 = total.get_response_time_percentile(0.95) or 0
    p99 = total.get_response_time_percentile(0.99) or 0
    fail_ratio = (total.num_failures / total.num_requests) * 100

    print("\n" + "=" * 70)
    print("  PERFORMANCE SUMMARY")
    print("=" * 70)
    print(f"  Total requests:   {total.num_requests:,}")
    print(f"  Failures:         {total.num_failures:,} ({fail_ratio:.1f}%)")
    print(f"  Rate-limited:     {_rate_limited_count:,} (429s, app-level)")
    print(f"  WAF-blocked:      {_waf_blocked_count:,} (403s, AWS WAF)")
    print(f"  Successful:       {_successful_count:,}")
    print(f"  Median (p50):     {p50:.0f} ms")
    print(f"  p95:              {p95:.0f} ms")
    print(f"  p99:              {p99:.0f} ms")
    print(f"  Avg:              {total.avg_response_time:.0f} ms")
    print(f"  RPS:              {total.total_rps:.1f}")
    print("=" * 70)

    # Check against performance requirements
    if p95 <= 200:
        print("  ✅ p95 < 200ms — PASS")
    else:
        print(f"  ❌ p95 = {p95:.0f}ms (target < 200ms) — FAIL")

    if fail_ratio < 1:
        print("  ✅ Error rate < 1% (excluding rate-limits) — PASS")
    else:
        print(f"  ❌ Error rate = {fail_ratio:.1f}% — FAIL")

    print("=" * 70 + "\n")
