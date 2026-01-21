"""Tests for structured logging and error handling."""

import json
import logging
from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from festival_playlist_generator.api.exception_handlers import (
    CircuitBreakerOpenError,
    ErrorResponse,
    circuit_breaker_handler,
    general_exception_handler,
    http_exception_handler,
    integrity_error_handler,
    sqlalchemy_error_handler,
    validation_exception_handler,
)
from festival_playlist_generator.api.middleware import RequestIDMiddleware
from festival_playlist_generator.core.database import transaction_context
from festival_playlist_generator.core.logging_config import (
    JSONFormatter,
    clear_request_id,
    get_request_id,
    set_request_id,
    setup_logging,
)


class TestJSONFormatter:
    """Tests for JSONFormatter."""

    def test_json_formatter_basic_log(self):
        """Test JSON formatter with basic log message."""
        formatter = JSONFormatter(service_name="test-service")
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.funcName = "test_function"
        record.module = "test_module"

        result = formatter.format(record)
        log_entry = json.loads(result)

        assert log_entry["level"] == "INFO"
        assert log_entry["message"] == "Test message"
        assert log_entry["service_name"] == "test-service"
        assert log_entry["logger"] == "test.logger"
        assert log_entry["module"] == "test_module"
        assert log_entry["function"] == "test_function"
        assert log_entry["line"] == 42
        assert "timestamp" in log_entry

    def test_json_formatter_with_request_id(self):
        """Test JSON formatter includes request ID from context."""
        formatter = JSONFormatter()
        set_request_id("test-request-123")

        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        record.funcName = "test_func"
        record.module = "test"

        result = formatter.format(record)
        log_entry = json.loads(result)

        assert log_entry["request_id"] == "test-request-123"

        clear_request_id()

    def test_json_formatter_with_exception(self):
        """Test JSON formatter includes exception details."""
        formatter = JSONFormatter()

        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

            record = logging.LogRecord(
                name="test.logger",
                level=logging.ERROR,
                pathname="test.py",
                lineno=1,
                msg="Error occurred",
                args=(),
                exc_info=exc_info,
            )
            record.funcName = "test_func"
            record.module = "test"

            result = formatter.format(record)
            log_entry = json.loads(result)

            assert "exception" in log_entry
            assert log_entry["exception"]["type"] == "ValueError"
            assert log_entry["exception"]["message"] == "Test error"
            assert "stacktrace" in log_entry["exception"]


class TestRequestIDContext:
    """Tests for request ID context management."""

    def test_set_and_get_request_id(self):
        """Test setting and getting request ID."""
        test_id = "test-123"
        set_request_id(test_id)

        assert get_request_id() == test_id

        clear_request_id()

    def test_clear_request_id(self):
        """Test clearing request ID."""
        set_request_id("test-123")
        clear_request_id()

        assert get_request_id() is None

    def test_request_id_isolation(self):
        """Test request ID is isolated per context."""
        # This would need async context testing in real scenario
        set_request_id("test-1")
        assert get_request_id() == "test-1"

        set_request_id("test-2")
        assert get_request_id() == "test-2"

        clear_request_id()


class TestErrorResponse:
    """Tests for ErrorResponse formatting."""

    def test_format_error_basic(self):
        """Test basic error response formatting."""
        response = ErrorResponse.format_error(
            error="test_error", message="Test error message", status_code=400
        )

        assert response["error"] == "test_error"
        assert response["message"] == "Test error message"
        assert response["status_code"] == 400
        assert "timestamp" in response

    def test_format_error_with_request_id(self):
        """Test error response includes request ID from context."""
        set_request_id("test-request-456")

        response = ErrorResponse.format_error(
            error="test_error", message="Test error message", status_code=400
        )

        assert response["request_id"] == "test-request-456"

        clear_request_id()

    def test_format_error_with_details(self):
        """Test error response with additional details."""
        details = {"field": "email", "constraint": "unique"}

        response = ErrorResponse.format_error(
            error="validation_error",
            message="Validation failed",
            status_code=422,
            details=details,
        )

        assert response["details"] == details


class TestCircuitBreakerOpenError:
    """Tests for CircuitBreakerOpenError."""

    def test_circuit_breaker_error_creation(self):
        """Test creating circuit breaker error."""
        error = CircuitBreakerOpenError("spotify")

        assert error.service_name == "spotify"
        assert "spotify" in error.message
        assert "OPEN" in error.message

    def test_circuit_breaker_error_custom_message(self):
        """Test circuit breaker error with custom message."""
        custom_msg = "Custom error message"
        error = CircuitBreakerOpenError("spotify", custom_msg)

        assert error.service_name == "spotify"
        assert error.message == custom_msg


@pytest.mark.asyncio
class TestExceptionHandlers:
    """Tests for exception handlers."""

    async def test_http_exception_handler(self):
        """Test HTTP exception handler."""
        request = Mock(spec=Request)
        request.url.path = "/api/test"
        request.method = "GET"

        exc = HTTPException(status_code=404, detail="Not found")

        with patch(
            "festival_playlist_generator.api.exception_handlers.get_request_version"
        ) as mock_version:
            with patch(
                "festival_playlist_generator.api.exception_handlers.APIVersionManager"
            ) as mock_manager:
                mock_version.return_value = "1.0"
                mock_formatter = Mock()
                mock_formatter.error_response.return_value = Mock(status_code=404)
                mock_manager.get_formatter.return_value = mock_formatter

                response = await http_exception_handler(request, exc)

                mock_formatter.error_response.assert_called_once()

    async def test_circuit_breaker_handler(self):
        """Test circuit breaker exception handler."""
        request = Mock(spec=Request)
        request.url.path = "/api/test"
        request.method = "GET"

        exc = CircuitBreakerOpenError("spotify")

        with patch(
            "festival_playlist_generator.api.exception_handlers.get_request_version"
        ) as mock_version:
            with patch(
                "festival_playlist_generator.api.exception_handlers.APIVersionManager"
            ) as mock_manager:
                mock_version.return_value = "1.0"
                mock_formatter = Mock()
                mock_formatter.error_response.return_value = Mock(status_code=503)
                mock_manager.get_formatter.return_value = mock_formatter

                response = await circuit_breaker_handler(request, exc)

                mock_formatter.error_response.assert_called_once()
                call_args = mock_formatter.error_response.call_args
                assert call_args[1]["status_code"] == 503


@pytest.mark.asyncio
class TestTransactionContext:
    """Tests for transaction context manager."""

    async def test_transaction_context_commit(self):
        """Test transaction context commits on success."""
        mock_session = AsyncMock()
        # in_transaction() is not async, so mock it as a regular method
        mock_session.in_transaction = Mock(return_value=False)
        mock_session.is_active = True

        async with transaction_context(mock_session) as session:
            assert session == mock_session

        # Verify transaction lifecycle
        mock_session.begin.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.close.assert_called_once()

    async def test_transaction_context_rollback(self):
        """Test transaction context rolls back on exception."""
        mock_session = AsyncMock()
        # in_transaction() is not async, so mock it as a regular method
        mock_session.in_transaction = Mock(return_value=False)
        mock_session.is_active = True

        with pytest.raises(ValueError):
            async with transaction_context(mock_session) as session:
                raise ValueError("Test error")

        # Verify rollback was called
        mock_session.begin.assert_called_once()
        mock_session.rollback.assert_called_once()
        mock_session.commit.assert_not_called()
        mock_session.close.assert_called_once()


class TestRequestIDMiddleware:
    """Tests for RequestIDMiddleware."""

    @pytest.mark.asyncio
    async def test_middleware_generates_request_id(self):
        """Test middleware generates request ID if not provided."""
        middleware = RequestIDMiddleware(app=Mock())

        request = Mock(spec=Request)
        request.headers.get.return_value = None

        async def call_next(req):
            # Verify request ID was set in context
            request_id = get_request_id()
            assert request_id is not None

            response = Mock()
            response.headers = {}
            return response

        response = await middleware.dispatch(request, call_next)

        # Verify request ID was added to response
        assert "X-Request-ID" in response.headers

        # Verify request ID was cleared after request
        assert get_request_id() is None

    @pytest.mark.asyncio
    async def test_middleware_uses_existing_request_id(self):
        """Test middleware uses existing request ID from header."""
        middleware = RequestIDMiddleware(app=Mock())

        existing_id = "existing-request-123"
        request = Mock(spec=Request)
        request.headers.get.return_value = existing_id

        async def call_next(req):
            # Verify existing request ID was used
            request_id = get_request_id()
            assert request_id == existing_id

            response = Mock()
            response.headers = {}
            return response

        response = await middleware.dispatch(request, call_next)

        # Verify same request ID was added to response
        assert response.headers["X-Request-ID"] == existing_id
