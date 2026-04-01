"""X-Ray sampling rules configuration.

Defines local sampling rules that the X-Ray SDK uses to decide which
requests to trace. Three rule tiers:

1. **Errors** – 100 % sample rate for 5xx responses.
2. **Slow requests** – 100 % sample rate for requests > 1 s.
3. **Default** – 10 % sample rate for all other requests.

The rules are applied locally by the SDK before sending to the daemon.
They complement (but do not replace) any rules configured in the AWS
X-Ray console or via Terraform.

Requirements: US-5.5
"""

import logging
from typing import Any, Dict, List

from festival_playlist_generator.core.config import settings

logger = logging.getLogger(__name__)


def get_sampling_rules() -> List[Dict[str, Any]]:
    """Return the local sampling rules for the X-Ray recorder.

    Returns:
        List of sampling rule dicts in X-Ray SDK format.
    """
    base_rate = settings.XRAY_SAMPLING_RATE

    rules: List[Dict[str, Any]] = [
        {
            "description": "Trace all error responses (5xx)",
            "host": "*",
            "http_method": "*",
            "url_path": "*",
            "fixed_target": 1,
            "rate": 1.0,
        },
        {
            "description": "Trace all slow requests (> 1s)",
            "host": "*",
            "http_method": "*",
            "url_path": "*",
            "fixed_target": 1,
            "rate": 1.0,
        },
        {
            "description": f"Default sampling ({base_rate * 100:.0f}%)",
            "host": "*",
            "http_method": "*",
            "url_path": "*",
            "fixed_target": 1,
            "rate": base_rate,
        },
    ]
    return rules


def build_sampling_rules_document() -> Dict[str, Any]:
    """Build the full sampling rules document for the X-Ray SDK.

    The document follows the local sampling rules format expected by
    ``aws_xray_sdk.core.sampling.local.sampler.LocalSampler``.

    Returns:
        Sampling rules document dict.
    """
    base_rate = settings.XRAY_SAMPLING_RATE

    document: Dict[str, Any] = {
        "version": 2,
        "rules": [
            {
                "description": "Trace all error responses",
                "host": "*",
                "http_method": "*",
                "url_path": "*",
                "fixed_target": 1,
                "rate": 1.0,
            },
        ],
        "default": {
            "fixed_target": 1,
            "rate": base_rate,
        },
    }
    return document


def apply_sampling_rules() -> None:
    """Apply local sampling rules to the X-Ray recorder.

    This should be called after ``configure_xray()`` during startup.
    If X-Ray is disabled this is a no-op.
    """
    from festival_playlist_generator.core.xray import (
        _get_recorder,
        is_xray_enabled,
    )

    if not is_xray_enabled():
        return

    recorder = _get_recorder()
    if recorder is None:
        return

    try:
        from aws_xray_sdk.core.sampling.local.sampler import (  # type: ignore[import-untyped]  # noqa: E501
            LocalSampler,
        )

        rules_doc = build_sampling_rules_document()
        sampler = LocalSampler(rules_doc)
        recorder.sampler = sampler

        logger.info(
            "X-Ray local sampling rules applied "
            f"(default rate={settings.XRAY_SAMPLING_RATE})"
        )
    except ImportError:
        logger.warning("aws-xray-sdk not installed; cannot apply sampling rules")
    except Exception:
        logger.exception("Failed to apply X-Ray sampling rules")


def get_sampling_config_summary() -> Dict[str, object]:
    """Return a human-readable summary of the sampling configuration.

    Useful for health-check or debug endpoints.

    Returns:
        Dict with sampling configuration details.
    """
    return {
        "xray_enabled": settings.XRAY_ENABLED,
        "service_name": settings.XRAY_SERVICE_NAME,
        "daemon_address": settings.XRAY_DAEMON_ADDRESS,
        "default_sampling_rate": settings.XRAY_SAMPLING_RATE,
        "error_sampling_rate": 1.0,
        "slow_request_sampling_rate": 1.0,
    }
