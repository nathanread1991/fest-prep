"""Tests for AWS X-Ray tracing: recorder, middleware, instrumentation, sampling.

Requirements: US-5.5
"""

from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from festival_playlist_generator.core.config import settings

# ---------------------------------------------------------------------------
# xray.py – configure_xray, is_xray_enabled, xray_subsegment, decorators
# ---------------------------------------------------------------------------


class TestConfigureXray:
    """Tests for X-Ray recorder configuration."""

    def test_disabled_when_setting_false(self) -> None:
        """When XRAY_ENABLED is False, configure_xray is a no-op."""
        import festival_playlist_generator.core.xray as xray_mod

        xray_mod._xray_enabled = False
        xray_mod._recorder = None

        with patch.object(settings, "XRAY_ENABLED", False):
            xray_mod.configure_xray()

        assert xray_mod.is_xray_enabled() is False
        assert xray_mod._get_recorder() is None

    def test_enabled_with_sdk_installed(self) -> None:
        """When XRAY_ENABLED is True and SDK available, recorder is set."""
        import builtins

        import festival_playlist_generator.core.xray as xray_mod

        xray_mod._xray_enabled = False
        xray_mod._recorder = None

        mock_recorder = MagicMock()
        original_import = builtins.__import__

        def custom_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if name == "aws_xray_sdk.core":
                mod = MagicMock()
                mod.xray_recorder = mock_recorder
                return mod
            return original_import(name, *args, **kwargs)

        with (
            patch.object(settings, "XRAY_ENABLED", True),
            patch("builtins.__import__", side_effect=custom_import),
        ):
            xray_mod.configure_xray()

        # Restore for other tests
        xray_mod._xray_enabled = False
        xray_mod._recorder = None

    def test_disabled_when_sdk_not_installed(self) -> None:
        """When aws-xray-sdk is not installed, tracing stays disabled."""
        import builtins

        import festival_playlist_generator.core.xray as xray_mod

        xray_mod._xray_enabled = False
        xray_mod._recorder = None

        original_import = builtins.__import__

        def fail_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if "aws_xray_sdk" in name:
                raise ImportError("no sdk")
            return original_import(name, *args, **kwargs)

        with (
            patch.object(settings, "XRAY_ENABLED", True),
            patch("builtins.__import__", side_effect=fail_import),
        ):
            xray_mod.configure_xray()

        assert xray_mod.is_xray_enabled() is False
        assert xray_mod._get_recorder() is None


class TestIsXrayEnabled:
    """Tests for the is_xray_enabled helper."""

    def test_returns_module_flag(self) -> None:
        import festival_playlist_generator.core.xray as xray_mod

        original = xray_mod._xray_enabled
        try:
            xray_mod._xray_enabled = True
            assert xray_mod.is_xray_enabled() is True
            xray_mod._xray_enabled = False
            assert xray_mod.is_xray_enabled() is False
        finally:
            xray_mod._xray_enabled = original


class TestXraySubsegment:
    """Tests for the xray_subsegment context manager."""

    def test_noop_when_disabled(self) -> None:
        """When tracing is off, the block runs and yields None."""
        import festival_playlist_generator.core.xray as xray_mod

        original = xray_mod._xray_enabled
        xray_mod._xray_enabled = False
        try:
            with xray_mod.xray_subsegment("test") as seg:
                assert seg is None
        finally:
            xray_mod._xray_enabled = original

    def test_creates_subsegment_when_enabled(self) -> None:
        """When tracing is on, begin/end subsegment are called."""
        import festival_playlist_generator.core.xray as xray_mod

        mock_recorder = MagicMock()
        mock_sub = MagicMock()
        mock_recorder.begin_subsegment.return_value = mock_sub

        original_enabled = xray_mod._xray_enabled
        original_recorder = xray_mod._recorder
        xray_mod._xray_enabled = True
        xray_mod._recorder = mock_recorder
        try:
            with xray_mod.xray_subsegment("test.op", "remote", {"key": "val"}) as seg:
                assert seg is mock_sub
            mock_recorder.begin_subsegment.assert_called_once_with("test.op", "remote")
            mock_sub.put_metadata.assert_called_once_with("key", "val")
            mock_recorder.end_subsegment.assert_called_once()
        finally:
            xray_mod._xray_enabled = original_enabled
            xray_mod._recorder = original_recorder

    def test_records_exception(self) -> None:
        """Exceptions inside the block are recorded on the subsegment."""
        import festival_playlist_generator.core.xray as xray_mod

        mock_recorder = MagicMock()
        mock_sub = MagicMock()
        mock_recorder.begin_subsegment.return_value = mock_sub

        original_enabled = xray_mod._xray_enabled
        original_recorder = xray_mod._recorder
        xray_mod._xray_enabled = True
        xray_mod._recorder = mock_recorder
        try:
            with pytest.raises(ValueError, match="boom"):
                with xray_mod.xray_subsegment("fail") as seg:  # noqa: F841
                    raise ValueError("boom")
            mock_sub.add_exception.assert_called_once()
            mock_recorder.end_subsegment.assert_called_once()
        finally:
            xray_mod._xray_enabled = original_enabled
            xray_mod._recorder = original_recorder


class TestTraceDecorators:
    """Tests for trace_function and trace_async_function decorators."""

    def test_trace_function_noop_when_disabled(self) -> None:
        import festival_playlist_generator.core.xray as xray_mod

        original = xray_mod._xray_enabled
        xray_mod._xray_enabled = False
        try:

            @xray_mod.trace_function("my_func")
            def my_func(x: int) -> int:
                return x + 1

            assert my_func(5) == 6
        finally:
            xray_mod._xray_enabled = original

    @pytest.mark.asyncio
    async def test_trace_async_function_noop_when_disabled(self) -> None:
        import festival_playlist_generator.core.xray as xray_mod

        original = xray_mod._xray_enabled
        xray_mod._xray_enabled = False
        try:

            @xray_mod.trace_async_function("my_async")
            async def my_async(x: int) -> int:
                return x * 2

            assert await my_async(3) == 6
        finally:
            xray_mod._xray_enabled = original


# ---------------------------------------------------------------------------
# xray_middleware.py – XRayMiddleware
# ---------------------------------------------------------------------------


class TestXRayMiddleware:
    """Tests for the FastAPI X-Ray middleware."""

    def test_skip_paths_defined(self) -> None:
        from festival_playlist_generator.api.xray_middleware import _SKIP_PATHS

        assert "/health" in _SKIP_PATHS
        assert "/docs" in _SKIP_PATHS
        assert "/redoc" in _SKIP_PATHS
        assert "/openapi.json" in _SKIP_PATHS

    def test_get_client_ip_from_forwarded(self) -> None:
        from festival_playlist_generator.api.xray_middleware import (
            _get_client_ip,
        )

        request = MagicMock()
        request.headers = {"x-forwarded-for": "1.2.3.4, 5.6.7.8"}
        assert _get_client_ip(request) == "1.2.3.4"

    def test_get_client_ip_from_client(self) -> None:
        from festival_playlist_generator.api.xray_middleware import (
            _get_client_ip,
        )

        request = MagicMock()
        request.headers = {}
        request.client.host = "10.0.0.1"
        assert _get_client_ip(request) == "10.0.0.1"

    def test_get_client_ip_none(self) -> None:
        from festival_playlist_generator.api.xray_middleware import (
            _get_client_ip,
        )

        request = MagicMock()
        request.headers = {}
        request.client = None
        assert _get_client_ip(request) is None

    def test_safe_env_returns_setting(self) -> None:
        from festival_playlist_generator.api.xray_middleware import _safe_env

        result = _safe_env()
        assert isinstance(result, str)
        assert result == settings.ENVIRONMENT


# ---------------------------------------------------------------------------
# xray_instrumentation.py – DB, Redis, external API, business logic
# ---------------------------------------------------------------------------


class TestInstrumentDbQuery:
    """Tests for database query X-Ray instrumentation."""

    def test_noop_when_disabled(self) -> None:
        from festival_playlist_generator.core.xray_instrumentation import (
            instrument_db_query,
        )

        with patch(
            "festival_playlist_generator.core.xray_instrumentation" ".is_xray_enabled",
            return_value=False,
        ):
            result = instrument_db_query("SELECT", "SELECT * FROM t")
            assert result is None

    def test_creates_subsegment_when_enabled(self) -> None:
        from festival_playlist_generator.core.xray_instrumentation import (
            instrument_db_query,
        )

        mock_recorder = MagicMock()
        mock_sub = MagicMock()
        mock_recorder.begin_subsegment.return_value = mock_sub

        with (
            patch(
                "festival_playlist_generator.core.xray_instrumentation"
                ".is_xray_enabled",
                return_value=True,
            ),
            patch(
                "festival_playlist_generator.core.xray_instrumentation"
                "._get_recorder",
                return_value=mock_recorder,
            ),
        ):
            result = instrument_db_query("SELECT", "SELECT * FROM artists")

        assert result is mock_sub
        mock_recorder.begin_subsegment.assert_called_once_with("db.select", "remote")
        mock_sub.put_metadata.assert_called_once()
        mock_sub.put_annotation.assert_called_once_with("db_operation", "SELECT")


class TestEndDbQuery:
    """Tests for ending database query subsegments."""

    def test_noop_when_none(self) -> None:
        from festival_playlist_generator.core.xray_instrumentation import (
            end_db_query,
        )

        # Should not raise
        end_db_query(None)

    def test_records_error(self) -> None:
        from festival_playlist_generator.core.xray_instrumentation import (
            end_db_query,
        )

        mock_sub = MagicMock()
        mock_recorder = MagicMock()
        err = RuntimeError("db error")

        with (
            patch(
                "festival_playlist_generator.core.xray_instrumentation"
                ".is_xray_enabled",
                return_value=True,
            ),
            patch(
                "festival_playlist_generator.core.xray_instrumentation"
                "._get_recorder",
                return_value=mock_recorder,
            ),
        ):
            end_db_query(mock_sub, error=err)

        mock_sub.add_exception.assert_called_once()
        mock_recorder.end_subsegment.assert_called_once()


class TestTraceRedisOperation:
    """Tests for Redis X-Ray instrumentation."""

    def test_noop_when_disabled(self) -> None:
        from festival_playlist_generator.core.xray_instrumentation import (
            trace_redis_operation,
        )

        with patch(
            "festival_playlist_generator.core.xray_instrumentation" ".is_xray_enabled",
            return_value=False,
        ):
            result = trace_redis_operation("GET", "cache:key")
            assert result is None

    def test_creates_subsegment_when_enabled(self) -> None:
        from festival_playlist_generator.core.xray_instrumentation import (
            trace_redis_operation,
        )

        mock_recorder = MagicMock()
        mock_sub = MagicMock()
        mock_recorder.begin_subsegment.return_value = mock_sub

        with (
            patch(
                "festival_playlist_generator.core.xray_instrumentation"
                ".is_xray_enabled",
                return_value=True,
            ),
            patch(
                "festival_playlist_generator.core.xray_instrumentation"
                "._get_recorder",
                return_value=mock_recorder,
            ),
        ):
            result = trace_redis_operation("GET", "cache:key")

        assert result is mock_sub
        mock_recorder.begin_subsegment.assert_called_once_with("redis.get", "remote")
        mock_sub.put_annotation.assert_called_once_with("redis_operation", "GET")


class TestEndRedisOperation:
    """Tests for ending Redis subsegments."""

    def test_noop_when_none(self) -> None:
        from festival_playlist_generator.core.xray_instrumentation import (
            end_redis_operation,
        )

        end_redis_operation(None)

    def test_records_cache_hit(self) -> None:
        from festival_playlist_generator.core.xray_instrumentation import (
            end_redis_operation,
        )

        mock_sub = MagicMock()
        mock_recorder = MagicMock()

        with (
            patch(
                "festival_playlist_generator.core.xray_instrumentation"
                ".is_xray_enabled",
                return_value=True,
            ),
            patch(
                "festival_playlist_generator.core.xray_instrumentation"
                "._get_recorder",
                return_value=mock_recorder,
            ),
        ):
            end_redis_operation(mock_sub, hit=True)

        mock_sub.put_annotation.assert_called_once_with("cache_hit", True)
        mock_recorder.end_subsegment.assert_called_once()


class TestTraceExternalApiCall:
    """Tests for external API call X-Ray instrumentation."""

    def test_noop_when_disabled(self) -> None:
        from festival_playlist_generator.core.xray_instrumentation import (
            trace_external_api_call,
        )

        with patch(
            "festival_playlist_generator.core.xray_instrumentation" ".is_xray_enabled",
            return_value=False,
        ):
            result = trace_external_api_call(
                "spotify", "search", "https://api.spotify.com"
            )
            assert result is None

    def test_creates_subsegment_when_enabled(self) -> None:
        from festival_playlist_generator.core.xray_instrumentation import (
            trace_external_api_call,
        )

        mock_recorder = MagicMock()
        mock_sub = MagicMock()
        mock_recorder.begin_subsegment.return_value = mock_sub

        with (
            patch(
                "festival_playlist_generator.core.xray_instrumentation"
                ".is_xray_enabled",
                return_value=True,
            ),
            patch(
                "festival_playlist_generator.core.xray_instrumentation"
                "._get_recorder",
                return_value=mock_recorder,
            ),
        ):
            result = trace_external_api_call(
                "spotify", "search", "https://api.spotify.com/v1/search"
            )

        assert result is mock_sub
        mock_recorder.begin_subsegment.assert_called_once_with(
            "spotify.search", "remote"
        )


class TestEndExternalApiCall:
    """Tests for ending external API call subsegments."""

    def test_noop_when_none(self) -> None:
        from festival_playlist_generator.core.xray_instrumentation import (
            end_external_api_call,
        )

        end_external_api_call(None)

    def test_records_status_500_as_fault(self) -> None:
        from festival_playlist_generator.core.xray_instrumentation import (
            end_external_api_call,
        )

        mock_sub = MagicMock()
        mock_recorder = MagicMock()

        with (
            patch(
                "festival_playlist_generator.core.xray_instrumentation"
                ".is_xray_enabled",
                return_value=True,
            ),
            patch(
                "festival_playlist_generator.core.xray_instrumentation"
                "._get_recorder",
                return_value=mock_recorder,
            ),
        ):
            end_external_api_call(mock_sub, status_code=500)

        mock_sub.put_http_meta.assert_called_once_with("status", 500)
        mock_sub.add_fault_flag.assert_called_once()

    def test_records_status_429_as_throttle(self) -> None:
        from festival_playlist_generator.core.xray_instrumentation import (
            end_external_api_call,
        )

        mock_sub = MagicMock()
        mock_recorder = MagicMock()

        with (
            patch(
                "festival_playlist_generator.core.xray_instrumentation"
                ".is_xray_enabled",
                return_value=True,
            ),
            patch(
                "festival_playlist_generator.core.xray_instrumentation"
                "._get_recorder",
                return_value=mock_recorder,
            ),
        ):
            end_external_api_call(mock_sub, status_code=429)

        mock_sub.add_throttle_flag.assert_called_once()

    def test_records_status_400_as_error(self) -> None:
        from festival_playlist_generator.core.xray_instrumentation import (
            end_external_api_call,
        )

        mock_sub = MagicMock()
        mock_recorder = MagicMock()

        with (
            patch(
                "festival_playlist_generator.core.xray_instrumentation"
                ".is_xray_enabled",
                return_value=True,
            ),
            patch(
                "festival_playlist_generator.core.xray_instrumentation"
                "._get_recorder",
                return_value=mock_recorder,
            ),
        ):
            end_external_api_call(mock_sub, status_code=404)

        mock_sub.add_error_flag.assert_called_once()

    def test_records_exception_as_fault(self) -> None:
        from festival_playlist_generator.core.xray_instrumentation import (
            end_external_api_call,
        )

        mock_sub = MagicMock()
        mock_recorder = MagicMock()
        err = ConnectionError("timeout")

        with (
            patch(
                "festival_playlist_generator.core.xray_instrumentation"
                ".is_xray_enabled",
                return_value=True,
            ),
            patch(
                "festival_playlist_generator.core.xray_instrumentation"
                "._get_recorder",
                return_value=mock_recorder,
            ),
        ):
            end_external_api_call(mock_sub, error=err)

        mock_sub.add_exception.assert_called_once()
        mock_sub.add_fault_flag.assert_called_once()


class TestTraceBusinessOperation:
    """Tests for business logic X-Ray instrumentation."""

    def test_noop_when_disabled(self) -> None:
        from festival_playlist_generator.core.xray_instrumentation import (
            trace_business_operation,
        )

        with patch(
            "festival_playlist_generator.core.xray_instrumentation" ".is_xray_enabled",
            return_value=False,
        ):
            result = trace_business_operation("create_playlist")
            assert result is None

    def test_creates_local_subsegment(self) -> None:
        from festival_playlist_generator.core.xray_instrumentation import (
            trace_business_operation,
        )

        mock_recorder = MagicMock()
        mock_sub = MagicMock()
        mock_recorder.begin_subsegment.return_value = mock_sub

        with (
            patch(
                "festival_playlist_generator.core.xray_instrumentation"
                ".is_xray_enabled",
                return_value=True,
            ),
            patch(
                "festival_playlist_generator.core.xray_instrumentation"
                "._get_recorder",
                return_value=mock_recorder,
            ),
        ):
            result = trace_business_operation("create_playlist", {"festival_id": 42})

        assert result is mock_sub
        mock_recorder.begin_subsegment.assert_called_once_with(
            "create_playlist", "local"
        )
        mock_sub.put_metadata.assert_called_once_with("festival_id", 42)


class TestEndBusinessOperation:
    """Tests for ending business logic subsegments."""

    def test_noop_when_none(self) -> None:
        from festival_playlist_generator.core.xray_instrumentation import (
            end_business_operation,
        )

        end_business_operation(None)

    def test_records_error(self) -> None:
        from festival_playlist_generator.core.xray_instrumentation import (
            end_business_operation,
        )

        mock_sub = MagicMock()
        mock_recorder = MagicMock()
        err = ValueError("bad input")

        with (
            patch(
                "festival_playlist_generator.core.xray_instrumentation"
                ".is_xray_enabled",
                return_value=True,
            ),
            patch(
                "festival_playlist_generator.core.xray_instrumentation"
                "._get_recorder",
                return_value=mock_recorder,
            ),
        ):
            end_business_operation(mock_sub, error=err)

        mock_sub.add_exception.assert_called_once()
        mock_recorder.end_subsegment.assert_called_once()


# ---------------------------------------------------------------------------
# xray_sampling.py – sampling rules, document, apply
# ---------------------------------------------------------------------------


class TestGetSamplingRules:
    """Tests for get_sampling_rules."""

    def test_returns_three_rules(self) -> None:
        from festival_playlist_generator.core.xray_sampling import (
            get_sampling_rules,
        )

        rules = get_sampling_rules()
        assert len(rules) == 3

    def test_error_rule_has_full_rate(self) -> None:
        from festival_playlist_generator.core.xray_sampling import (
            get_sampling_rules,
        )

        rules = get_sampling_rules()
        error_rule = rules[0]
        assert error_rule["rate"] == 1.0
        assert "error" in error_rule["description"].lower()

    def test_slow_rule_has_full_rate(self) -> None:
        from festival_playlist_generator.core.xray_sampling import (
            get_sampling_rules,
        )

        rules = get_sampling_rules()
        slow_rule = rules[1]
        assert slow_rule["rate"] == 1.0
        assert "slow" in slow_rule["description"].lower()

    def test_default_rule_uses_setting(self) -> None:
        from festival_playlist_generator.core.xray_sampling import (
            get_sampling_rules,
        )

        rules = get_sampling_rules()
        default_rule = rules[2]
        assert default_rule["rate"] == settings.XRAY_SAMPLING_RATE

    def test_all_rules_have_required_keys(self) -> None:
        from festival_playlist_generator.core.xray_sampling import (
            get_sampling_rules,
        )

        required_keys = {
            "description",
            "host",
            "http_method",
            "url_path",
            "fixed_target",
            "rate",
        }
        for rule in get_sampling_rules():
            assert required_keys.issubset(rule.keys())


class TestBuildSamplingRulesDocument:
    """Tests for build_sampling_rules_document."""

    def test_document_version(self) -> None:
        from festival_playlist_generator.core.xray_sampling import (
            build_sampling_rules_document,
        )

        doc = build_sampling_rules_document()
        assert doc["version"] == 2

    def test_document_has_rules_and_default(self) -> None:
        from festival_playlist_generator.core.xray_sampling import (
            build_sampling_rules_document,
        )

        doc = build_sampling_rules_document()
        assert "rules" in doc
        assert "default" in doc
        assert isinstance(doc["rules"], list)
        assert len(doc["rules"]) >= 1

    def test_default_rate_matches_setting(self) -> None:
        from festival_playlist_generator.core.xray_sampling import (
            build_sampling_rules_document,
        )

        doc = build_sampling_rules_document()
        assert doc["default"]["rate"] == settings.XRAY_SAMPLING_RATE

    def test_error_rule_100_percent(self) -> None:
        from festival_playlist_generator.core.xray_sampling import (
            build_sampling_rules_document,
        )

        doc = build_sampling_rules_document()
        error_rule = doc["rules"][0]
        assert error_rule["rate"] == 1.0


class TestApplySamplingRules:
    """Tests for apply_sampling_rules."""

    def test_noop_when_disabled(self) -> None:
        from festival_playlist_generator.core.xray_sampling import (
            apply_sampling_rules,
        )

        with patch(
            "festival_playlist_generator.core.xray.is_xray_enabled",
            return_value=False,
        ):
            # Should not raise
            apply_sampling_rules()

    def test_noop_when_recorder_none(self) -> None:
        from festival_playlist_generator.core.xray_sampling import (
            apply_sampling_rules,
        )

        with (
            patch(
                "festival_playlist_generator.core.xray.is_xray_enabled",
                return_value=True,
            ),
            patch(
                "festival_playlist_generator.core.xray._get_recorder",
                return_value=None,
            ),
        ):
            apply_sampling_rules()

    def test_applies_local_sampler(self) -> None:
        from festival_playlist_generator.core.xray_sampling import (
            apply_sampling_rules,
        )

        mock_recorder = MagicMock()
        mock_sampler_cls = MagicMock()
        mock_sampler_instance = MagicMock()
        mock_sampler_cls.return_value = mock_sampler_instance

        with (
            patch(
                "festival_playlist_generator.core.xray.is_xray_enabled",
                return_value=True,
            ),
            patch(
                "festival_playlist_generator.core.xray._get_recorder",
                return_value=mock_recorder,
            ),
            patch.dict(
                "sys.modules",
                {
                    "aws_xray_sdk": MagicMock(),
                    "aws_xray_sdk.core": MagicMock(),
                    "aws_xray_sdk.core.sampling": MagicMock(),
                    "aws_xray_sdk.core.sampling.local": MagicMock(),
                    "aws_xray_sdk.core.sampling.local.sampler": MagicMock(
                        LocalSampler=mock_sampler_cls
                    ),
                },
            ),
        ):
            apply_sampling_rules()

        assert mock_recorder.sampler is not None

    def test_handles_import_error(self) -> None:
        """apply_sampling_rules should not raise if SDK is missing."""
        import builtins

        from festival_playlist_generator.core.xray_sampling import (
            apply_sampling_rules,
        )

        mock_recorder = MagicMock()
        original_import = builtins.__import__

        def fail_import(name: str, *args: Any, **kwargs: Any) -> Any:
            if "aws_xray_sdk" in name:
                raise ImportError("no sdk")
            return original_import(name, *args, **kwargs)

        with (
            patch(
                "festival_playlist_generator.core.xray.is_xray_enabled",
                return_value=True,
            ),
            patch(
                "festival_playlist_generator.core.xray._get_recorder",
                return_value=mock_recorder,
            ),
            patch("builtins.__import__", side_effect=fail_import),
        ):
            # Should not raise
            apply_sampling_rules()


class TestGetSamplingConfigSummary:
    """Tests for get_sampling_config_summary."""

    def test_returns_expected_keys(self) -> None:
        from festival_playlist_generator.core.xray_sampling import (
            get_sampling_config_summary,
        )

        summary = get_sampling_config_summary()
        assert "xray_enabled" in summary
        assert "service_name" in summary
        assert "daemon_address" in summary
        assert "default_sampling_rate" in summary
        assert "error_sampling_rate" in summary
        assert "slow_request_sampling_rate" in summary

    def test_error_rate_always_100(self) -> None:
        from festival_playlist_generator.core.xray_sampling import (
            get_sampling_config_summary,
        )

        summary = get_sampling_config_summary()
        assert summary["error_sampling_rate"] == 1.0
        assert summary["slow_request_sampling_rate"] == 1.0

    def test_default_rate_matches_setting(self) -> None:
        from festival_playlist_generator.core.xray_sampling import (
            get_sampling_config_summary,
        )

        summary = get_sampling_config_summary()
        assert summary["default_sampling_rate"] == settings.XRAY_SAMPLING_RATE


# ---------------------------------------------------------------------------
# Integration: main.py wiring
# ---------------------------------------------------------------------------


class TestMainAppXrayWiring:
    """Verify that main.py wires up X-Ray correctly."""

    def test_xray_middleware_registered(self) -> None:
        """XRayMiddleware should be in the app middleware stack."""
        from festival_playlist_generator.main import app

        middleware_classes = [
            m.cls.__name__ for m in app.user_middleware if hasattr(m, "cls")
        ]
        assert "XRayMiddleware" in middleware_classes

    def test_configure_xray_called_in_lifespan(self) -> None:
        """configure_xray and apply_sampling_rules are in the lifespan."""
        import inspect

        from festival_playlist_generator.main import lifespan

        source = inspect.getsource(lifespan)
        assert "configure_xray()" in source
        assert "apply_sampling_rules()" in source
