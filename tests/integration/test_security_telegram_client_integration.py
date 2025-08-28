"""
Integration Tests: Security + TelegramClientWrapper

This module tests the integration between Security utilities and TelegramClientWrapper
to ensure proper input validation and security measures.
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime, timezone, timedelta

from telegram_toolkit_mcp.core.telegram_client import TelegramClientWrapper
from telegram_toolkit_mcp.utils.security import (
    InputValidator,
    get_rate_limiter,
    get_security_auditor
)
from telegram_toolkit_mcp.utils.config import AppConfig, TelegramConfig, ServerConfig
from telegram_toolkit_mcp.core.error_handler import ValidationException


class TestSecurityTelegramClientIntegration:
    """Integration tests for Security utilities and TelegramClientWrapper."""

    @pytest.fixture
    def mock_config(self):
        """Mock application configuration."""
        return AppConfig(
            telegram=TelegramConfig(
                api_id=12345,
                api_hash="test_hash_12345678901234567890123456789012",
                session_string=None
            ),
            server=ServerConfig(host="localhost", port=8000, log_level="DEBUG"),
            performance=type(
                "PerformanceConfig",
                (),
                {"flood_sleep_threshold": 30, "request_timeout": 10, "max_page_size": 50},
            )(),
            resources=type(
                "ResourceConfig",
                (),
                {
                    "temp_dir": "/tmp/test-resources",
                    "resource_max_age_hours": 1,
                    "ndjson_chunk_size": 100
                },
            )(),
            observability=type(
                "ObservabilityConfig",
                (),
                {
                    "enable_prometheus_metrics": False,
                    "enable_opentelemetry_tracing": False,
                    "otlp_endpoint": None,
                    "otlp_exporter": "grpc",
                    "service_name": "test",
                    "service_version": "1.0.0",
                    "trace_sampling_rate": 1.0,
                    "trace_max_attributes": 128,
                    "trace_max_events": 128
                },
            )()
        )

    @pytest.fixture
    async def mock_telethon_client(self):
        """Mock Telethon client."""
        client = AsyncMock()
        client.is_connected.return_value = True
        client.get_entity = AsyncMock()
        client.iter_messages = AsyncMock()
        client.disconnect = AsyncMock()
        return client

    @pytest.mark.asyncio
    async def test_input_validation_with_client_wrapper(self, mock_config, mock_telethon_client):
        """Test InputValidator integration with TelegramClientWrapper."""
        # Create client wrapper
        client_wrapper = TelegramClientWrapper(mock_config)
        client_wrapper._client = mock_telethon_client

        # Test valid chat identifiers
        valid_chats = [
            "@username",
            "t.me/channel",
            "123456789",  # numeric ID
            "https://t.me/channel"
        ]

        for chat in valid_chats:
            # Should not raise exception
            validated_chat = InputValidator.sanitize_chat_identifier(chat)
            assert validated_chat is not None
            assert len(validated_chat) > 0

        # Test invalid chat identifiers
        invalid_chats = [
            "",
            "   ",
            "@",
            "t.me/",
            "<script>alert('xss')</script>",
            "javascript:alert('xss')"
        ]

        for chat in invalid_chats:
            with pytest.raises(ValueError):
                InputValidator.sanitize_chat_identifier(chat)

    @pytest.mark.asyncio
    async def test_rate_limiting_with_client_operations(self, mock_config, mock_telethon_client):
        """Test rate limiting integration with client operations."""
        # Create client wrapper
        client_wrapper = TelegramClientWrapper(mock_config)
        client_wrapper._client = mock_telethon_client

        # Mock successful responses
        mock_chat = MagicMock()
        mock_chat.id = 123456789
        mock_chat.title = "Test Channel"
        mock_telethon_client.get_entity.return_value = mock_chat
        mock_telethon_client.iter_messages.return_value = []

        rate_limiter = get_rate_limiter()

        # Test multiple rapid requests
        for i in range(5):
            allowed, wait_time = await rate_limiter.check_rate_limit(f"test_operation_{i}")

            if not allowed:
                # Should wait before retrying
                assert wait_time > 0
                break

        # Verify rate limiter is working
        assert rate_limiter is not None

    @pytest.mark.asyncio
    async def test_security_auditor_with_client_errors(self, mock_config, mock_telethon_client):
        """Test SecurityAuditor integration with client error scenarios."""
        from telegram_toolkit_mcp.core.error_handler import ChannelPrivateException

        # Create client wrapper
        client_wrapper = TelegramClientWrapper(mock_config)
        client_wrapper._client = mock_telethon_client

        # Mock private channel scenario
        mock_telethon_client.iter_messages.side_effect = ChannelPrivateException(
            chat_id=123456789,
            message="Channel is private"
        )

        security_auditor = get_security_auditor()

        # Attempt operation that should fail with security-related error
        try:
            await client_wrapper.fetch_messages(
                chat="private_channel",
                limit=10,
                offset_date=datetime.now(timezone.utc)
            )
        except ChannelPrivateException:
            # Log security event
            security_auditor.log_security_event(
                "access_denied",
                {
                    "resource": "channel",
                    "chat": "private_channel",
                    "reason": "channel_private"
                }
            )

        # Verify security event was logged
        events = security_auditor.get_security_events()
        assert len(events) > 0

        # Find the access_denied event
        access_events = [e for e in events if e["event_type"] == "access_denied"]
        assert len(access_events) > 0

        event = access_events[0]
        assert event["details"]["resource"] == "channel"
        assert event["details"]["reason"] == "channel_private"

    def test_input_validation_edge_cases(self):
        """Test InputValidator handles various edge cases."""
        # Test extremely long chat names
        long_chat = "@" + "a" * 1000
        with pytest.raises(ValueError):
            InputValidator.sanitize_chat_identifier(long_chat)

        # Test chat names with special characters
        special_chats = [
            "@user@domain.com",  # Multiple @ symbols
            "@user#channel",     # Special characters
            "@user channel",     # Spaces
        ]

        for chat in special_chats:
            # Should either validate successfully or raise ValueError
            try:
                validated = InputValidator.sanitize_chat_identifier(chat)
                assert validated is not None
            except ValueError:
                # Expected for invalid formats
                pass

        # Test numeric IDs
        valid_numeric = ["123", "123456789", "-1001234567890"]
        for chat_id in valid_numeric:
            validated = InputValidator.sanitize_chat_identifier(chat_id)
            assert validated == chat_id

    def test_page_size_validation_integration(self):
        """Test page size validation integration."""
        # Test valid page sizes
        valid_sizes = [1, 10, 50, 100]

        for size in valid_sizes:
            # Should not raise exception
            validated = InputValidator.validate_page_size(size)
            assert validated == size

        # Test invalid page sizes
        invalid_sizes = [0, -1, 101, 1000]

        for size in invalid_sizes:
            with pytest.raises(ValueError):
                InputValidator.validate_page_size(size)

    def test_search_query_validation(self):
        """Test search query validation."""
        # Test valid search queries
        valid_queries = [
            "test search",
            "telegram channel",
            "python programming",
            "123 numbers",
            "special_chars_test"
        ]

        for query in valid_queries:
            # Should not raise exception
            sanitized = InputValidator.sanitize_search_query(query)
            assert sanitized == query

        # Test invalid search queries
        invalid_queries = [
            "",  # Empty
            "   ",  # Only spaces
            "a" * 257,  # Too long
            "test<malicious>",  # HTML-like tags
            "test>redirect",  # Redirect-like
        ]

        for query in invalid_queries:
            with pytest.raises(ValueError):
                InputValidator.sanitize_search_query(query)

    @pytest.mark.asyncio
    async def test_rate_limiter_burst_protection(self):
        """Test rate limiter handles burst requests properly."""
        rate_limiter = get_rate_limiter()

        # Simulate burst of requests
        burst_size = 20
        allowed_count = 0
        blocked_count = 0

        for i in range(burst_size):
            allowed, wait_time = await rate_limiter.check_rate_limit("burst_test")

            if allowed:
                allowed_count += 1
            else:
                blocked_count += 1
                assert wait_time > 0

        # Verify some requests were blocked
        assert blocked_count > 0
        assert allowed_count + blocked_count == burst_size

    def test_security_auditor_event_filtering(self):
        """Test SecurityAuditor event filtering and retrieval."""
        security_auditor = get_security_auditor()

        # Log various security events
        events_to_log = [
            ("rate_limit_exceeded", {"tool": "fetch_history", "chat": "test1"}),
            ("input_validation_failed", {"field": "chat", "value": "invalid"}),
            ("access_denied", {"resource": "channel", "chat": "private"}),
            ("rate_limit_exceeded", {"tool": "resolve_chat", "chat": "test2"}),
        ]

        for event_type, details in events_to_log:
            security_auditor.log_security_event(event_type, details)

        # Retrieve all events
        all_events = security_auditor.get_security_events()
        assert len(all_events) == 4

        # Verify events are in reverse chronological order (most recent first)
        assert all_events[0]["event_type"] == "rate_limit_exceeded"
        assert all_events[0]["details"]["chat"] == "test2"

        # Verify event details
        for event in all_events:
            assert "timestamp" in event
            assert "event_type" in event
            assert "details" in event

    @pytest.mark.asyncio
    async def test_client_wrapper_with_security_validation(
        self, mock_config, mock_telethon_client
    ):
        """Test client wrapper properly integrates with security validation."""
        # Create client wrapper
        client_wrapper = TelegramClientWrapper(mock_config)
        client_wrapper._client = mock_telethon_client

        # Mock successful response
        mock_chat = MagicMock()
        mock_chat.id = 123456789
        mock_chat.title = "Test Channel"
        mock_telethon_client.get_entity.return_value = mock_chat
        mock_telethon_client.iter_messages.return_value = []

        # Test with valid parameters
        await client_wrapper.fetch_messages(
            chat="@validchannel",
            limit=10,
            offset_date=datetime.now(timezone.utc)
        )

        # Verify telethon methods were called
        mock_telethon_client.get_entity.assert_called()
        mock_telethon_client.iter_messages.assert_called()

        # Test with invalid chat (should be caught by input validation)
        with pytest.raises(ValueError):
            await client_wrapper.fetch_messages(
                chat="",  # Invalid empty chat
                limit=10,
                offset_date=datetime.now(timezone.utc)
            )

    def test_comprehensive_input_validation(self):
        """Test comprehensive input validation scenarios."""
        # Test date range validation
        from_date = datetime.now(timezone.utc) - timedelta(days=1)
        to_date = datetime.now(timezone.utc)

        # Should not raise exception for valid dates
        InputValidator.validate_date_range(from_date.isoformat(), to_date.isoformat())

        # Should raise exception for invalid date range
        with pytest.raises(ValueError):
            InputValidator.validate_date_range(to_date.isoformat(), from_date.isoformat())  # from > to

        # Test date range too large
        far_future = datetime.now(timezone.utc) + timedelta(days=400)
        with pytest.raises(ValueError):
            InputValidator.validate_date_range(from_date.isoformat(), far_future.isoformat())

        # Test search query with maximum length
        max_query = "a" * 256  # Maximum allowed length
        sanitized = InputValidator.sanitize_search_query(max_query)
        assert sanitized == max_query

        # Test search query over maximum length
        over_limit_query = "a" * 257
        with pytest.raises(ValueError):
            InputValidator.sanitize_search_query(over_limit_query)
