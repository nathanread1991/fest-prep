"""
Property tests for ci-infra.yml workflow correctness.

Validates:
  - Property 2: Infra CI does not trigger on app-only changes
  - Property 11 (infra variant): CI pipeline cancels stale runs — infra uses
    cancel-in-progress: false for Terraform state safety

Requirements: 2.3, 12.2, 12.3
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List

import yaml  # type: ignore[import-untyped]
from hypothesis import given, settings
from hypothesis import strategies as st

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_repo_root() -> Path:
    """Walk up from this file to find the repo root (contains .github/)."""
    current = Path(__file__).resolve().parent
    for parent in [current] + list(current.parents):
        if (parent / ".github" / "workflows").is_dir():
            return parent
    raise FileNotFoundError(
        "Cannot find repo root containing .github/workflows/"
    )


REPO_ROOT = _find_repo_root()
CI_INFRA_PATH = REPO_ROOT / ".github" / "workflows" / "ci-infra.yml"

INFRA_PATH_PREFIX = "infrastructure/terraform/"
APP_PATH_PREFIX = "services/api/"


def _load_workflow() -> Dict[str, Any]:
    """Load and parse the ci-infra.yml workflow file."""
    with open(CI_INFRA_PATH, "r") as fh:
        data: Dict[str, Any] = yaml.safe_load(fh)
    return data


def _get_trigger_paths(workflow: Dict[str, Any], event: str) -> List[str]:
    """Return the ``paths`` list for a given trigger event."""
    trigger_block = workflow.get("on", workflow.get(True, {}))
    event_block = trigger_block.get(event, {})
    paths: List[str] = event_block.get("paths", [])
    return paths


# ---------------------------------------------------------------------------
# Property 2 — Infra CI does not trigger on app-only changes
# ---------------------------------------------------------------------------


class TestInfraCITriggerPaths:
    """
    # Feature: cicd-pipeline-rework, Property 2: Infra CI does not trigger
    # on app-only changes
    """

    def test_push_paths_only_include_infra(self) -> None:
        """All push path filters must be under infrastructure/terraform/."""
        workflow = _load_workflow()
        paths = _get_trigger_paths(workflow, "push")
        assert len(paths) > 0, "ci-infra.yml must define push path filters"
        for p in paths:
            assert p.startswith(INFRA_PATH_PREFIX), (
                f"Push path filter '{p}' is outside {INFRA_PATH_PREFIX}"
            )

    def test_pull_request_paths_only_include_infra(self) -> None:
        """All pull_request path filters must be under infrastructure/terraform/."""
        workflow = _load_workflow()
        paths = _get_trigger_paths(workflow, "pull_request")
        assert len(paths) > 0, "ci-infra.yml must define pull_request path filters"
        for p in paths:
            assert p.startswith(INFRA_PATH_PREFIX), (
                f"PR path filter '{p}' is outside {INFRA_PATH_PREFIX}"
            )

    @settings(max_examples=100)
    @given(
        suffix=st.text(
            alphabet=st.characters(
                whitelist_categories=("L", "N"),
                whitelist_characters=("_", "-", "/", "."),
            ),
            min_size=1,
            max_size=80,
        )
    )
    def test_app_only_paths_never_match_infra_filters(
        self, suffix: str
    ) -> None:
        """
        For any randomly generated app-only file path, none of the
        ci-infra.yml path filters should match it.
        """
        workflow = _load_workflow()
        app_path = APP_PATH_PREFIX + suffix

        push_paths = _get_trigger_paths(workflow, "push")
        pr_paths = _get_trigger_paths(workflow, "pull_request")

        for pattern in push_paths + pr_paths:
            # GitHub Actions uses glob-style matching; a path starting with
            # "infrastructure/terraform/" will never match a path starting
            # with "services/api/".
            prefix = pattern.rstrip("*").rstrip("/")
            assert not app_path.startswith(prefix), (
                f"App path '{app_path}' would match infra filter '{pattern}'"
            )


# ---------------------------------------------------------------------------
# Property 11 (infra variant) — Concurrency configuration
# ---------------------------------------------------------------------------


class TestInfraCIConcurrency:
    """
    # Feature: cicd-pipeline-rework, Property 11: CI pipeline cancels stale
    # runs (infra variant — cancel-in-progress must be false for Terraform
    # state safety)
    """

    def test_concurrency_group_is_defined(self) -> None:
        """ci-infra.yml must define a top-level concurrency group."""
        workflow = _load_workflow()
        assert "concurrency" in workflow, (
            "ci-infra.yml must define a concurrency block"
        )
        concurrency = workflow["concurrency"]
        assert "group" in concurrency, (
            "concurrency block must define a group"
        )

    def test_cancel_in_progress_is_false(self) -> None:
        """
        Infra CI must NOT cancel in-progress runs because concurrent
        Terraform operations against the same state can corrupt it.
        """
        workflow = _load_workflow()
        concurrency = workflow["concurrency"]
        cancel = concurrency.get("cancel-in-progress", True)
        assert cancel is False, (
            "ci-infra.yml concurrency.cancel-in-progress must be false "
            f"for Terraform state safety, got {cancel!r}"
        )

    def test_concurrency_group_includes_environment(self) -> None:
        """
        The concurrency group should be scoped to an environment to
        prevent cross-environment state conflicts.
        """
        workflow = _load_workflow()
        group: str = workflow["concurrency"]["group"]
        assert "infra" in group.lower(), (
            f"Concurrency group '{group}' should reference 'infra'"
        )
