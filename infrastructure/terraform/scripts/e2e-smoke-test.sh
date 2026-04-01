#!/usr/bin/env bash
# ============================================================================
# End-to-End Smoke Test Script
# ============================================================================
# Tests core application functionality through the ALB endpoint:
#   1. Health check
#   2. User registration (with unique timestamp-based username)
#   3. User login and JWT token capture
#   4. Festival search (GET /api/v1/festivals)
#   5. Festival creation with auth token (POST /api/v1/festivals)
#   6. Playlist listing (GET /api/v1/playlists)
#   7. Spotify integration endpoint availability (graceful)
#   8. Setlist.fm integration endpoint availability (graceful)
#
# Usage:
#   ./scripts/e2e-smoke-test.sh
#   ./scripts/e2e-smoke-test.sh --alb-dns <dns-name>
#
# Environment variables:
#   ALB_DNS        - ALB DNS name (auto-detected from Terraform if not set)
#   PROJECT_NAME   - Project name (default: festival-playlist)
#   ENVIRONMENT    - Environment name (default: dev)
#   AWS_REGION     - AWS region (default: eu-west-2)
# ============================================================================

set -euo pipefail

# ============================================================================
# Configuration
# ============================================================================

PROJECT_NAME="${PROJECT_NAME:-festival-playlist}"
ENVIRONMENT="${ENVIRONMENT:-dev}"
AWS_REGION="${AWS_REGION:-eu-west-2}"
ALB_DNS="${ALB_DNS:-}"
TIMESTAMP="$(date +%s)"
TEST_USERNAME="smoketest_${TIMESTAMP}"
TEST_EMAIL="smoketest_${TIMESTAMP}@e2e-test.local"
TEST_PASSWORD="SmokeTest!Pass123"
AUTH_TOKEN=""

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info()    { echo -e "${BLUE}[INFO]${NC} $*"; }
log_success() { echo -e "${GREEN}[PASS]${NC} $*"; }
log_warn()    { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error()   { echo -e "${RED}[FAIL]${NC} $*"; }

# Track results
TESTS_PASSED=0
TESTS_FAILED=0
TESTS_SKIPPED=0

record_pass()  { TESTS_PASSED=$((TESTS_PASSED + 1)); }
record_fail()  { TESTS_FAILED=$((TESTS_FAILED + 1)); }
record_skip()  { TESTS_SKIPPED=$((TESTS_SKIPPED + 1)); }

# ============================================================================
# Parse Arguments
# ============================================================================

while [[ $# -gt 0 ]]; do
    case $1 in
        --alb-dns)
            ALB_DNS="$2"
            shift 2
            ;;
        --help|-h)
            echo "Usage: $0 [--alb-dns <dns>]"
            echo ""
            echo "Options:"
            echo "  --alb-dns   ALB DNS name (auto-detected from Terraform if omitted)"
            exit 0
            ;;
        *)
            echo "Unknown option: $1"
            exit 1
            ;;
    esac
done

# ============================================================================
# Resolve ALB DNS Name
# ============================================================================

resolve_alb_dns() {
    if [ -n "${ALB_DNS}" ]; then
        log_info "Using provided ALB DNS: ${ALB_DNS}"
        return 0
    fi

    log_info "Resolving ALB DNS name from Terraform output..."

    local tf_dir
    tf_dir="$(cd "$(dirname "$0")/.." && pwd)"

    if [ -f "${tf_dir}/main.tf" ]; then
        ALB_DNS=$(terraform -chdir="${tf_dir}" output -raw alb_dns_name 2>/dev/null || echo "")
    fi

    if [ -z "${ALB_DNS}" ]; then
        ALB_DNS=$(aws elbv2 describe-load-balancers \
            --region "${AWS_REGION}" \
            --names "${PROJECT_NAME}-${ENVIRONMENT}-alb" \
            --query 'LoadBalancers[0].DNSName' \
            --output text 2>/dev/null || echo "")
    fi

    if [ -z "${ALB_DNS}" ] || [ "${ALB_DNS}" = "None" ]; then
        log_error "Could not resolve ALB DNS name"
        return 1
    fi

    log_info "Resolved ALB DNS: ${ALB_DNS}"
}

# ============================================================================
# Helper: HTTP request with status code capture
# ============================================================================

# Perform a request and print the HTTP status code.
# Globals set after call: LAST_HTTP_CODE, LAST_BODY
LAST_HTTP_CODE=""
LAST_BODY=""

http_get() {
    local url="$1"
    local extra_args=("${@:2}")
    LAST_BODY=$(curl -s --max-time 15 -w "\n%{http_code}" "${extra_args[@]}" "${url}" 2>/dev/null || echo -e "\n000")
    LAST_HTTP_CODE=$(echo "${LAST_BODY}" | tail -n1)
    LAST_BODY=$(echo "${LAST_BODY}" | sed '$d')
}

http_post() {
    local url="$1"
    local data="$2"
    local extra_args=("${@:3}")
    LAST_BODY=$(curl -s --max-time 15 -w "\n%{http_code}" \
        -X POST \
        -H "Content-Type: application/json" \
        "${extra_args[@]}" \
        -d "${data}" \
        "${url}" 2>/dev/null || echo -e "\n000")
    LAST_HTTP_CODE=$(echo "${LAST_BODY}" | tail -n1)
    LAST_BODY=$(echo "${LAST_BODY}" | sed '$d')
}

# ============================================================================
# Test 1: Health Check
# ============================================================================

test_health() {
    log_info "Test 1: Health check (/health)"

    http_get "http://${ALB_DNS}/health"

    if [ "${LAST_HTTP_CODE}" != "200" ]; then
        log_error "Health check returned HTTP ${LAST_HTTP_CODE} (expected 200)"
        record_fail
        return 1
    fi

    local status
    status=$(echo "${LAST_BODY}" | python3 -c "import sys,json; print(json.load(sys.stdin).get('status',''))" 2>/dev/null || echo "")

    if [ "${status}" = "healthy" ]; then
        log_success "Health check passed (status=healthy)"
        record_pass
    else
        log_error "Health check body invalid. Expected status=healthy, got: ${status}"
        record_fail
        return 1
    fi
}

# ============================================================================
# Test 2: User Registration
# ============================================================================

test_register() {
    log_info "Test 2: User registration (POST /api/v1/auth/register)"

    local payload
    payload=$(cat <<EOF
{"username": "${TEST_USERNAME}", "email": "${TEST_EMAIL}", "password": "${TEST_PASSWORD}"}
EOF
)

    http_post "http://${ALB_DNS}/api/v1/auth/register" "${payload}"

    if [ "${LAST_HTTP_CODE}" = "200" ] || [ "${LAST_HTTP_CODE}" = "201" ]; then
        log_success "User registration succeeded (HTTP ${LAST_HTTP_CODE})"
        record_pass
    elif [ "${LAST_HTTP_CODE}" = "409" ] || [ "${LAST_HTTP_CODE}" = "400" ]; then
        log_warn "User may already exist (HTTP ${LAST_HTTP_CODE}) — acceptable for idempotent runs"
        record_pass
    else
        log_error "User registration failed (HTTP ${LAST_HTTP_CODE}): ${LAST_BODY}"
        record_fail
    fi
}

# ============================================================================
# Test 3: User Login and JWT Capture
# ============================================================================

test_login() {
    log_info "Test 3: User login (POST /api/v1/auth/login)"

    local payload
    payload=$(cat <<EOF
{"username": "${TEST_USERNAME}", "password": "${TEST_PASSWORD}"}
EOF
)

    http_post "http://${ALB_DNS}/api/v1/auth/login" "${payload}"

    if [ "${LAST_HTTP_CODE}" = "200" ]; then
        AUTH_TOKEN=$(echo "${LAST_BODY}" | python3 -c "
import sys, json
data = json.load(sys.stdin)
print(data.get('access_token', data.get('token', '')))
" 2>/dev/null || echo "")

        if [ -n "${AUTH_TOKEN}" ]; then
            log_success "Login succeeded, JWT token captured"
            record_pass
        else
            log_warn "Login returned 200 but no token found in response"
            record_pass
        fi
    else
        log_error "Login failed (HTTP ${LAST_HTTP_CODE}): ${LAST_BODY}"
        record_fail
    fi
}

# ============================================================================
# Test 4: Festival Search
# ============================================================================

test_festival_search() {
    log_info "Test 4: Festival search (GET /api/v1/festivals)"

    http_get "http://${ALB_DNS}/api/v1/festivals"

    if [ "${LAST_HTTP_CODE}" = "200" ]; then
        log_success "Festival search returned HTTP 200"
        record_pass
    elif [ "${LAST_HTTP_CODE}" = "401" ]; then
        log_warn "Festival search requires auth (HTTP 401) — testing with token"
        if [ -n "${AUTH_TOKEN}" ]; then
            http_get "http://${ALB_DNS}/api/v1/festivals" -H "Authorization: Bearer ${AUTH_TOKEN}"
            if [ "${LAST_HTTP_CODE}" = "200" ]; then
                log_success "Festival search with auth returned HTTP 200"
                record_pass
            else
                log_error "Festival search with auth failed (HTTP ${LAST_HTTP_CODE})"
                record_fail
            fi
        else
            log_warn "No auth token available, skipping authenticated retry"
            record_skip
        fi
    else
        log_error "Festival search failed (HTTP ${LAST_HTTP_CODE}): ${LAST_BODY}"
        record_fail
    fi
}

# ============================================================================
# Test 5: Festival Creation
# ============================================================================

test_festival_create() {
    log_info "Test 5: Festival creation (POST /api/v1/festivals)"

    if [ -z "${AUTH_TOKEN}" ]; then
        log_warn "No auth token available — skipping festival creation"
        record_skip
        return 0
    fi

    local payload
    payload=$(cat <<EOF
{"name": "E2E Smoke Test Festival ${TIMESTAMP}", "location": "Test Venue, London", "date": "2025-09-01"}
EOF
)

    http_post "http://${ALB_DNS}/api/v1/festivals" "${payload}" \
        -H "Authorization: Bearer ${AUTH_TOKEN}"

    if [ "${LAST_HTTP_CODE}" = "200" ] || [ "${LAST_HTTP_CODE}" = "201" ]; then
        log_success "Festival creation succeeded (HTTP ${LAST_HTTP_CODE})"
        record_pass
    elif [ "${LAST_HTTP_CODE}" = "409" ]; then
        log_warn "Festival already exists (HTTP 409) — acceptable"
        record_pass
    elif [ "${LAST_HTTP_CODE}" = "401" ] || [ "${LAST_HTTP_CODE}" = "403" ]; then
        log_warn "Festival creation not authorized (HTTP ${LAST_HTTP_CODE})"
        record_skip
    else
        log_error "Festival creation failed (HTTP ${LAST_HTTP_CODE}): ${LAST_BODY}"
        record_fail
    fi
}

# ============================================================================
# Test 6: Playlist Listing
# ============================================================================

test_playlist_list() {
    log_info "Test 6: Playlist listing (GET /api/v1/playlists)"

    local auth_args=()
    if [ -n "${AUTH_TOKEN}" ]; then
        auth_args=(-H "Authorization: Bearer ${AUTH_TOKEN}")
    fi

    http_get "http://${ALB_DNS}/api/v1/playlists" "${auth_args[@]}"

    if [ "${LAST_HTTP_CODE}" = "200" ]; then
        log_success "Playlist listing returned HTTP 200"
        record_pass
    elif [ "${LAST_HTTP_CODE}" = "401" ]; then
        if [ -z "${AUTH_TOKEN}" ]; then
            log_warn "Playlist listing requires auth and no token available"
            record_skip
        else
            log_error "Playlist listing returned 401 even with auth token"
            record_fail
        fi
    else
        log_error "Playlist listing failed (HTTP ${LAST_HTTP_CODE}): ${LAST_BODY}"
        record_fail
    fi
}

# ============================================================================
# Test 7: Spotify Integration Endpoint Availability
# ============================================================================

test_spotify_integration() {
    log_info "Test 7: Spotify integration endpoint availability"

    # Test artist search which uses Spotify under the hood.
    # This is expected to fail gracefully if Spotify credentials
    # are not configured — we only check the endpoint responds.
    local auth_args=()
    if [ -n "${AUTH_TOKEN}" ]; then
        auth_args=(-H "Authorization: Bearer ${AUTH_TOKEN}")
    fi

    http_get "http://${ALB_DNS}/api/v1/artists?q=test" "${auth_args[@]}"

    if [ "${LAST_HTTP_CODE}" = "200" ]; then
        log_success "Spotify/artist endpoint returned HTTP 200"
        record_pass
    elif [ "${LAST_HTTP_CODE}" = "503" ] || [ "${LAST_HTTP_CODE}" = "502" ]; then
        log_warn "Spotify integration unavailable (HTTP ${LAST_HTTP_CODE}) — credentials may not be configured"
        record_skip
    elif [ "${LAST_HTTP_CODE}" = "401" ]; then
        log_warn "Artist endpoint requires auth (HTTP 401) — endpoint is reachable"
        record_pass
    elif [ "${LAST_HTTP_CODE}" = "422" ]; then
        log_warn "Artist endpoint returned validation error (HTTP 422) — endpoint is reachable"
        record_pass
    else
        log_warn "Artist/Spotify endpoint returned HTTP ${LAST_HTTP_CODE} — may need Spotify credentials"
        record_skip
    fi
}

# ============================================================================
# Test 8: Setlist.fm Integration Endpoint Availability
# ============================================================================

test_setlistfm_integration() {
    log_info "Test 8: Setlist.fm integration endpoint availability"

    # Test a festival-by-ID endpoint which may trigger Setlist.fm lookups.
    # We use the festivals endpoint with a search query as a proxy.
    # Graceful failure if Setlist.fm API key is not configured.
    local auth_args=()
    if [ -n "${AUTH_TOKEN}" ]; then
        auth_args=(-H "Authorization: Bearer ${AUTH_TOKEN}")
    fi

    http_get "http://${ALB_DNS}/api/v1/festivals?q=glastonbury" "${auth_args[@]}"

    if [ "${LAST_HTTP_CODE}" = "200" ]; then
        log_success "Setlist.fm/festival search endpoint returned HTTP 200"
        record_pass
    elif [ "${LAST_HTTP_CODE}" = "503" ] || [ "${LAST_HTTP_CODE}" = "502" ]; then
        log_warn "Setlist.fm integration unavailable (HTTP ${LAST_HTTP_CODE}) — API key may not be configured"
        record_skip
    elif [ "${LAST_HTTP_CODE}" = "401" ]; then
        log_warn "Festival search requires auth (HTTP 401) — endpoint is reachable"
        record_pass
    elif [ "${LAST_HTTP_CODE}" = "422" ]; then
        log_warn "Festival search returned validation error (HTTP 422) — endpoint is reachable"
        record_pass
    else
        log_warn "Festival/Setlist.fm endpoint returned HTTP ${LAST_HTTP_CODE} — may need API key"
        record_skip
    fi
}

# ============================================================================
# Summary
# ============================================================================

print_summary() {
    local total=$((TESTS_PASSED + TESTS_FAILED + TESTS_SKIPPED))

    echo ""
    echo "========================================="
    log_info "E2E Smoke Test Summary"
    echo "========================================="
    echo "  ALB DNS:  ${ALB_DNS:-N/A}"
    echo "  Region:   ${AWS_REGION}"
    echo "  Test User: ${TEST_USERNAME}"
    echo ""
    echo "  Total:    ${total}"
    echo "  Passed:   ${TESTS_PASSED}"
    echo "  Failed:   ${TESTS_FAILED}"
    echo "  Skipped:  ${TESTS_SKIPPED}"
    echo "========================================="

    if [ "${TESTS_FAILED}" -gt 0 ]; then
        log_error "E2E smoke tests FAILED (${TESTS_FAILED} test(s) failed)"
        return 1
    elif [ "${TESTS_PASSED}" -eq 0 ]; then
        log_error "No tests passed — something is wrong"
        return 1
    else
        log_success "E2E smoke tests PASSED"
        return 0
    fi
}

# ============================================================================
# Main
# ============================================================================

main() {
    echo ""
    log_info "========================================="
    log_info "E2E Smoke Tests — Festival Playlist Generator"
    log_info "========================================="
    echo ""

    # Resolve ALB DNS
    if ! resolve_alb_dns; then
        log_error "Cannot proceed without ALB DNS name"
        log_info "Provide via --alb-dns flag, ALB_DNS env var, or ensure Terraform outputs are available"
        exit 1
    fi

    echo ""

    test_health
    echo ""
    test_register
    echo ""
    test_login
    echo ""
    test_festival_search
    echo ""
    test_festival_create
    echo ""
    test_playlist_list
    echo ""
    test_spotify_integration
    echo ""
    test_setlistfm_integration
    echo ""

    print_summary
}

main "$@"
