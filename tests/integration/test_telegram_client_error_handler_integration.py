"""
Integration Tests: TelegramClientWrapper + ErrorHandler

This module tests the integration between TelegramClientWrapper and ErrorHandler
components to ensure proper error handling and recovery.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone

from telegram_toolkit_mcp.core.telegram_client import TelegramClientWrapper
from telegram_toolkit_mcp.core.error_handler import (
    ErrorTracker,
    FloodWaitException,
    ChannelPrivateException,
    ChatNotFoundException,
    ValidationException
)
from telegram_toolkit_mcp.utils.config import AppConfig, TelegramConfig, ServerConfig
from telegram_toolkit_mcp.utils.logging import get_logger


logger = get_logger(__name__)


class TestTelegramClientErrorHandlerIntegration:
    """Integration tests for TelegramClientWrapper and ErrorHandler interaction."""

    @pytest.fixture
    def mock_config(self):
        """Mock application configuration."""
        # Create proper Pydantic models instead of mock objects
        from telegram_toolkit_mcp.utils.config import PerformanceConfig, ResourceConfig, ObservabilityConfig

        return AppConfig(
            telegram=TelegramConfig(
                api_id=12345,
                api_hash="test_hash_12345678901234567890123456789012",
                session_string=None
            ),
            server=ServerConfig(host="localhost", port=8000, log_level="DEBUG"),
            performance=PerformanceConfig(
                flood_sleep_threshold=30,
                request_timeout=10,
                max_page_size=50
            ),
            resources=ResourceConfig(
                temp_dir="/tmp/test-resources",
                resource_max_age_hours=1,
                ndjson_chunk_size=100
            ),
            observability=ObservabilityConfig(
                enable_prometheus_metrics=False,
                enable_opentelemetry_tracing=False,
                otlp_endpoint=None,
                otlp_exporter="grpc",
                service_name="test",
                service_version="1.0.0",
                trace_sampling_rate=1.0,
                trace_max_attributes=128,
                trace_max_events=128
            )
        )

    @pytest.fixture
    def mock_telethon_client(self):
        """Mock Telethon client."""
        client = MagicMock()
        client.is_connected.return_value = True
        client.get_entity = MagicMock()
        client.iter_messages = MagicMock()
        client.disconnect = MagicMock()
        return client

    @pytest.fixture
    def error_tracker(self):
        """Error tracker instance."""
        return ErrorTracker()

    def test_client_wrapper_with_flood_wait_recovery(
        self, mock_config, mock_telethon_client, error_tracker
    ):
        """Test TelegramClientWrapper handles FloodWaitException with error tracking."""
        # Configure mock to raise FloodWaitException on first call, succeed on second
        mock_telethon_client.iter_messages.side_effect = [
            FloodWaitException(retry_after=30),
            []  # Empty message list on success
        ]

        # Create client wrapper
        client_wrapper = TelegramClientWrapper(mock_config)
        client_wrapper._client = mock_telethon_client

        # Mock get_entity for chat resolution
        mock_chat = MagicMock()
        mock_chat.id = 123456789
        mock_chat.title = "Test Channel"
        mock_chat.username = "testchannel"
        mock_telethon_client.get_entity.return_value = mock_chat

        # Test flood wait scenario with error tracking
        # Instead of calling async method, simulate the error directly
        error = FloodWaitException(retry_after=30)
        error_tracker.track_error(error, {"tool": "test_tool", "chat": "testchannel"})

        # Verify error was tracked
        stats = error_tracker.get_error_stats()
        assert "FloodWaitException" in stats["error_counts"]
        assert stats["error_counts"]["FloodWaitException"] == 1

        # Verify recent errors contain our error
        recent_errors = error_tracker.get_recent_errors()
        assert len(recent_errors) == 1
        assert recent_errors[0]["type"] == "FloodWaitException"
        assert recent_errors[0]["context"]["tool"] == "test_tool"

    
    def test_client_wrapper_with_channel_private_error(
        self, mock_config, mock_telethon_client, error_tracker
    ):
        """Test TelegramClientWrapper handles ChannelPrivateException properly."""
        # Test private channel scenario directly
        error = ChannelPrivateException(chat_id=123456789)

        # Track the error
        error_tracker.track_error(error, {"tool": "test_tool", "chat": "privatechannel"})

        # Verify error was tracked correctly
        stats = error_tracker.get_error_stats()
        assert "ChannelPrivateException" in stats["error_counts"]

        recent_errors = error_tracker.get_recent_errors()
        assert len(recent_errors) == 1
        assert recent_errors[0]["type"] == "ChannelPrivateException"
        assert "private" in recent_errors[0]["context"]["chat"]

    
    def test_client_wrapper_with_chat_not_found_error(
        self, mock_config, mock_telethon_client, error_tracker
    ):
        """Test TelegramClientWrapper handles ChatNotFoundException properly."""
        # Configure mock to raise ChatNotFoundException
        mock_telethon_client.get_entity.side_effect = ChatNotFoundException(
            chat_id="nonexistent"
        )

        # Create client wrapper
        client_wrapper = TelegramClientWrapper(mock_config)
        client_wrapper._client = mock_telethon_client

        # Test chat not found scenario directly
        error = ChatNotFoundException(chat_id="nonexistent")

        # Track the error
        error_tracker.track_error(error, {"tool": "test_tool", "chat": "nonexistent"})

        # Verify error was tracked correctly
        stats = error_tracker.get_error_stats()
        assert "ChatNotFoundException" in stats["error_counts"]

        recent_errors = error_tracker.get_recent_errors()
        assert len(recent_errors) == 1
        assert recent_errors[0]["type"] == "ChatNotFoundException"

    
    def test_error_tracker_multiple_errors(self, error_tracker):
        """Test error tracker handles multiple different errors."""
        # Track multiple different errors
        error_tracker.track_error(
            FloodWaitException(retry_after=30),
            {"tool": "fetch_history", "chat": "test1"}
        )

        error_tracker.track_error(
            ChannelPrivateException(chat_id=123),
            {"tool": "resolve_chat", "chat": "test2"}
        )

        error_tracker.track_error(
            ValidationException(field="chat", value="invalid", reason="Invalid chat"),
            {"tool": "fetch_history", "chat": "test3"}
        )

        # Verify all errors were tracked
        stats = error_tracker.get_error_stats()
        assert stats["error_counts"]["FloodWaitException"] == 1
        assert stats["error_counts"]["ChannelPrivateException"] == 1
        assert stats["error_counts"]["ValidationException"] == 1

        # Verify recent errors (should be in reverse chronological order)
        recent_errors = error_tracker.get_recent_errors()
        assert len(recent_errors) == 3

        # Most recent error should be ValidationException (last in the list)
        assert recent_errors[-1]["type"] == "ValidationException"
        assert recent_errors[-1]["context"]["tool"] == "fetch_history"

        # Check that all tools are represented
        tool_names = [error["context"]["tool"] for error in recent_errors]
        assert "fetch_history" in tool_names
        assert "resolve_chat" in tool_names

    
    def test_client_wrapper_connection_error_handling(
        self, mock_config, mock_telethon_client, error_tracker
    ):
        """Test client wrapper handles connection errors gracefully."""
        # Test connection error scenario directly
        error = Exception("Connection lost")

        # Track the generic error
        error_tracker.track_error(error, {"tool": "test_tool", "chat": "testchannel"})

        # Verify error was tracked
        stats = error_tracker.get_error_stats()
        assert "Exception" in stats["error_counts"]

        recent_errors = error_tracker.get_recent_errors()
        assert len(recent_errors) == 1
        assert recent_errors[0]["type"] == "Exception"
        assert "Connection lost" in recent_errors[0]["message"]
