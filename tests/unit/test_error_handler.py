"""
Unit tests for error handling functionality.

Tests error mapping, retry logic, error tracking, and MCP-compliant responses.
"""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import pytest

from src.telegram_toolkit_mcp.core.error_handler import (
    ChannelPrivateException,
    ChatNotFoundException,
    ErrorTracker,
    FloodWaitException,
    TelegramMCPException,
    ValidationException,
    create_error_response,
    create_success_response,
    get_error_tracker,
    map_telethon_exception,
    retry_on_failure,
    retry_with_backoff,
)


class TestCustomExceptions:
    """Test custom exception classes."""

    def test_flood_wait_exception(self):
        """Test FloodWaitException creation and properties."""
        exc = FloodWaitException(retry_after=30)

        assert "Rate limit exceeded" in exc.message
        assert exc.retry_after == 30
        assert exc.code == "FLOOD_WAIT"

    def test_flood_wait_exception_to_dict(self):
        """Test FloodWaitException to_dict method."""
        exc = FloodWaitException(retry_after=30)

        error_dict = exc.to_dict()
        assert error_dict["code"] == "FLOOD_WAIT"
        assert "Rate limit exceeded" in error_dict["message"]
        assert error_dict["retry_after"] == 30

    def test_chat_not_found_exception(self):
        """Test ChatNotFoundException."""
        exc = ChatNotFoundException(chat_id="123")

        assert "Chat 123 not found" in exc.message
        assert exc.code == "CHAT_NOT_FOUND"

    def test_channel_private_exception(self):
        """Test ChannelPrivateException."""
        exc = ChannelPrivateException(chat_id="test_channel")

        assert "Channel test_channel is private or inaccessible" in exc.message
        assert exc.code == "CHANNEL_PRIVATE"

    def test_validation_exception(self):
        """Test ValidationException."""
        exc = ValidationException("field1", "invalid_value", "Invalid format")

        assert "Invalid format" in exc.message
        assert exc.code == "INPUT_VALIDATION"


class TestExceptionMapping:
    """Test exception mapping from Telethon to MCP errors."""

    def test_map_flood_wait_error(self):
        """Test mapping Telethon FloodWaitError."""
        # Mock Telethon FloodWaitError
        mock_error = Mock()
        mock_error.__class__.__name__ = "FloodWaitError"
        mock_error.seconds = 60

        mapped = map_telethon_exception(mock_error)
        assert isinstance(mapped, FloodWaitException)
        assert mapped.retry_after == 60

    def test_map_channel_private_error(self):
        """Test mapping channel private errors."""
        mock_error = Mock()
        mock_error.__class__.__name__ = "ChannelPrivateError"

        mapped = map_telethon_exception(mock_error)
        assert isinstance(mapped, ChannelPrivateException)

    def test_map_chat_not_found_error(self):
        """Test mapping chat not found errors."""
        mock_error = Mock()
        mock_error.__class__.__name__ = "ChatNotFoundError"

        mapped = map_telethon_exception(mock_error)
        assert isinstance(mapped, ChatNotFoundException)

    def test_map_generic_error(self):
        """Test mapping generic errors."""
        mock_error = Mock()
        mock_error.__class__.__name__ = "SomeOtherError"
        mock_error.__str__ = Mock(return_value="Generic error")

        mapped = map_telethon_exception(mock_error)
        assert isinstance(mapped, TelegramMCPException)
        assert "Generic error" in mapped.message

    def test_map_none_error(self):
        """Test mapping None error."""
        mapped = map_telethon_exception(None)
        assert isinstance(mapped, TelegramMCPException)


class TestRetryLogic:
    """Test retry logic functionality."""

    @pytest.fixture
    def mock_func(self):
        """Create a mock async function."""
        return AsyncMock()

    def test_retry_with_backoff_success(self, mock_func):
        """Test successful retry operation."""
        mock_func.return_value = "success"

        result = asyncio.run(retry_with_backoff(mock_func))

        assert result == "success"
        assert mock_func.call_count == 1

    def test_retry_with_backoff_failure(self, mock_func):
        """Test failed retry operation."""
        mock_func.side_effect = ValueError("Test error")

        with pytest.raises(TelegramMCPException):
            asyncio.run(retry_with_backoff(mock_func))

        assert mock_func.call_count == 3  # Default max_attempts

    def test_retry_with_backoff_flood_wait(self, mock_func):
        """Test retry with FLOOD_WAIT exception."""
        mock_func.side_effect = [FloodWaitException(retry_after=1), "success"]

        with patch("asyncio.sleep") as mock_sleep:
            result = asyncio.run(retry_with_backoff(mock_func))

        assert result == "success"
        assert mock_func.call_count == 2
        mock_sleep.assert_called_once_with(1)

    def test_retry_with_backoff_max_attempts(self, mock_func):
        """Test retry with maximum attempts reached."""
        mock_func.side_effect = FloodWaitException(retry_after=1)

        with patch("asyncio.sleep"):
            with pytest.raises(FloodWaitException):
                asyncio.run(retry_with_backoff(mock_func, retry_config=Mock(max_attempts=2)))

        assert mock_func.call_count == 2

    def test_retry_on_failure_decorator(self, mock_func):
        """Test retry_on_failure decorator."""
        decorated_func = retry_on_failure(max_attempts=2, initial_delay=0.1)(mock_func)
        mock_func.side_effect = [Exception("Error"), "success"]

        with patch("asyncio.sleep") as mock_sleep:
            result = asyncio.run(decorated_func())

        assert result == "success"
        assert mock_func.call_count == 2
        mock_sleep.assert_called_once()

    def test_retry_config_creation(self):
        """Test retry configuration creation."""
        from src.telegram_toolkit_mcp.core.error_handler import RetryConfig

        config = RetryConfig(max_attempts=5, initial_delay=2.0, backoff_factor=3.0)

        assert config.max_attempts == 5
        assert config.initial_delay == 2.0
        assert config.backoff_factor == 3.0


class TestErrorTracker:
    """Test error tracking functionality."""

    @pytest.fixture
    def error_tracker(self):
        """Create a test error tracker."""
        return ErrorTracker()

    def test_track_error(self, error_tracker):
        """Test error tracking."""
        error = ValueError("Test error")
        context = {"tool": "test_tool", "user": "test_user"}

        error_tracker.track_error(error, context)

        assert len(error_tracker.errors) == 1
        tracked_error = error_tracker.errors[0]

        assert tracked_error["type"] == "ValueError"
        assert tracked_error["message"] == "Test error"
        assert tracked_error["context"] == context
        assert "timestamp" in tracked_error

    def test_get_error_summary(self, error_tracker):
        """Test error summary generation."""
        # Track multiple errors
        errors = [
            ValueError("Error 1"),
            FloodWaitException(retry_after=30),
            ValueError("Error 2"),
            ChatNotFoundException("Chat not found"),
        ]

        for i, error in enumerate(errors):
            error_tracker.track_error(error, {"request_id": f"req_{i}"})

        summary = error_tracker.get_error_summary()

        assert summary["total_errors"] == 4
        assert summary["error_types"]["ValueError"] == 2
        assert summary["error_types"]["FloodWaitException"] == 1
        assert summary["error_types"]["ChatNotFoundException"] == 1

    def test_error_limit(self, error_tracker):
        """Test error tracking limit."""
        error_tracker.max_recent_errors = 3

        # Track more errors than limit
        for i in range(5):
            error_tracker.track_error(ValueError(f"Error {i}"), {"id": i})

        assert len(error_tracker.recent_errors) == 3
        # Should keep the most recent errors
        assert error_tracker.recent_errors[0]["context"]["id"] == 2  # First (oldest)
        assert error_tracker.recent_errors[-1]["context"]["id"] == 4  # Last (newest)

    def test_get_recent_errors(self, error_tracker):
        """Test getting recent errors."""
        # Track errors
        for i in range(5):
            error_tracker.track_error(ValueError(f"Error {i}"), {"id": i})

        recent = error_tracker.get_recent_errors(limit=3)
        assert len(recent) == 3
        assert recent[0]["context"]["id"] == 2  # Oldest in recent
        assert recent[-1]["context"]["id"] == 4  # Most recent


class TestResponseCreation:
    """Test MCP response creation functions."""

    def test_create_success_response(self):
        """Test creating success response."""
        content = [{"type": "text", "text": "Success message"}]
        structured_content = {"data": "test"}

        response = create_success_response(content=content, structured_content=structured_content)

        assert response["content"] == content
        assert response["structuredContent"] == structured_content
        assert response.get("isError") is None or response.get("isError") is False

    def test_create_error_response(self):
        """Test creating error response."""
        exc = ValidationException("field1", "value", "Invalid")

        response = create_error_response(exc)

        assert response["isError"] is True
        assert response["error"]["code"] == "INPUT_VALIDATION"
        assert "Invalid field1: Invalid" in response["content"][0]["text"]

    def test_create_error_response_with_exception(self):
        """Test creating error response from exception."""
        exc = ValidationException("field1", "value", "Invalid")

        response = create_error_response(exc)

        assert response["isError"] is True
        assert response["error"]["code"] == "INPUT_VALIDATION"
        assert "Invalid field1: Invalid" in response["content"][0]["text"]


class TestErrorHandlerIntegration:
    """Test error handler integration with other components."""

    def test_get_error_tracker_singleton(self):
        """Test error tracker singleton pattern."""
        tracker1 = get_error_tracker()
        tracker2 = get_error_tracker()

        assert tracker1 is tracker2

    def test_error_tracker_with_metrics(self, error_tracker):
        """Test error tracker integration with metrics."""
        with patch(
            "src.telegram_toolkit_mcp.core.monitoring.get_metrics_collector"
        ) as mock_get_metrics:
            mock_metrics = Mock()
            mock_get_metrics.return_value = mock_metrics

            error = FloodWaitException(retry_after=30)
            error_tracker.track_error(error, {"tool": "test_tool"})

            # Should record flood wait event in metrics
            mock_metrics.record_flood_wait.assert_called_once_with("test_tool", 1, 30)

    def test_flood_wait_retry_with_metrics(self):
        """Test FLOOD_WAIT retry integration with metrics."""
        with patch(
            "src.telegram_toolkit_mcp.core.error_handler.record_flood_wait_event"
        ) as mock_record:
            mock_func = AsyncMock(side_effect=[FloodWaitException(retry_after=1), "success"])

            with patch("asyncio.sleep"):
                result = asyncio.run(retry_with_backoff(mock_func))

            assert result == "success"
            mock_record.assert_called_once()


class TestErrorHandlerEdgeCases:
    """Test error handler edge cases."""

    def test_exception_with_no_message(self):
        """Test exception without message."""

        class NoMessageException(Exception):
            pass

        exc = NoMessageException()
        mapped = map_telethon_exception(exc)

        assert isinstance(mapped, TelegramMCPException)
        assert "Internal error" in mapped.message

    def test_exception_with_unicode_message(self):
        """Test exception with unicode message."""
        error = ValueError("Ошибка в кодировке UTF-8 🔥")
        mapped = map_telethon_exception(error)

        assert isinstance(mapped, TelegramMCPException)
        assert "UTF-8" in mapped.message

    def test_flood_wait_exception_with_zero_retry(self):
        """Test FloodWaitException with zero retry time."""
        exc = FloodWaitException(retry_after=0)

        assert exc.retry_after == 0
        error_dict = exc.to_dict()
        assert "0 seconds" in error_dict["message"]

    def test_validation_exception_with_none_values(self):
        """Test ValidationException with None values."""
        exc = ValidationException(None, None, None)

        assert exc.details["field"] is None
        assert exc.details["value"] == "None"  # str(None) = "None"
        assert exc.details["reason"] is None

        error_dict = exc.to_dict()
        assert error_dict["code"] == "INPUT_VALIDATION"

    def test_error_tracker_concurrent_access(self, error_tracker):
        """Test error tracker under concurrent access."""
        import threading

        errors = []

        def track_errors(worker_id: int):
            for i in range(10):
                error = ValueError(f"Worker {worker_id} error {i}")
                error_tracker.track_error(error, {"worker": worker_id, "error_id": i})
                errors.append(f"worker_{worker_id}_{i}")

        threads = []
        for i in range(3):
            thread = threading.Thread(target=track_errors, args=(i,))
            threads.append(thread)
            thread.start()

        for thread in threads:
            thread.join()

        # Should have tracked all errors
        assert len(error_tracker.errors) == 30
        assert len(errors) == 30

    def test_retry_with_backoff_timeout(self):
        """Test retry with backoff handling FloodWaitException."""
        mock_func = AsyncMock(side_effect=FloodWaitException(retry_after=100))

        with patch("asyncio.sleep") as mock_sleep:
            # Should eventually raise FloodWaitException after all retries exhausted
            with pytest.raises(FloodWaitException):
                asyncio.run(retry_with_backoff(mock_func, retry_config=Mock(max_attempts=1)))

    def test_error_response_with_large_content(self):
        """Test error response with large content."""
        large_content = "x" * 10000
        exc = ValidationException("field1", large_content, "Invalid")

        response = create_error_response(exc)

        assert response["isError"] is True
        # Message contains the validation error text, not the large content value
        assert "Invalid field1: Invalid" in response["content"][0]["text"]


class TestErrorHandlerConfiguration:
    """Test error handler configuration scenarios."""

    def test_retry_config_validation(self):
        """Test retry configuration validation."""
        from src.telegram_toolkit_mcp.core.error_handler import RetryConfig

        # Valid config
        config = RetryConfig(max_attempts=5, initial_delay=1.0, backoff_factor=2.0)
        assert config.max_attempts == 5

        # Edge cases
        config = RetryConfig(max_attempts=1, initial_delay=0.1, backoff_factor=1.1)
        assert config.max_attempts == 1

    def test_error_tracker_configuration(self):
        """Test error tracker configuration."""
        tracker = ErrorTracker()
        original_max = tracker.max_recent_errors

        # Test with different limits
        tracker.max_recent_errors = 10
        assert tracker.max_recent_errors == 10

        # Reset
        tracker.max_recent_errors = original_max

    def test_exception_to_dict_completeness(self):
        """Test that all exceptions have complete to_dict methods."""
        exceptions = [
            FloodWaitException(retry_after=30),
            ChatNotFoundException(chat_id="123"),
            ChannelPrivateException(chat_id="test_channel"),
            ValidationException("field", "value", "reason"),
            TelegramMCPException(code="GENERIC_ERROR", message="Generic error"),
        ]

        for exc in exceptions:
            error_dict = exc.to_dict()

            required_fields = ["code", "message"]
            for field in required_fields:
                assert field in error_dict
                assert error_dict[field] is not None
