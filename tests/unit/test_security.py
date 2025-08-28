"""
Unit tests for security utilities.

Tests PII masking, rate limiting, input validation, and session management.
"""

import asyncio
import hashlib
import pytest
from unittest.mock import Mock, patch

from src.telegram_toolkit_mcp.utils.security import (
    PIIMasker,
    RateLimiter,
    InputValidator,
    SessionManager,
    SecurityAuditor,
    get_rate_limiter,
    get_session_manager,
    get_security_auditor,
    generate_secure_token,
    hash_sensitive_data
)


class TestPIIMasker:
    """Test PII masking functionality."""

    def test_mask_text_basic(self):
        """Test basic text masking."""
        text = "My phone is +1234567890 and email is test@example.com"
        masked = PIIMasker.mask_text(text)

        assert "[REDACTED]" in masked
        assert "+1234567890" not in masked
        assert "test@example.com" not in masked

    def test_mask_text_api_credentials(self):
        """Test API credentials masking."""
        text = 'api_id=12345 api_hash=abcdef1234567890 session_string=long_session_data'
        masked = PIIMasker.mask_text(text)

        # Current implementation masks only the values, not the keys
        assert "api_id=12345" in masked  # Key remains
        assert "[REDACTED]" in masked  # Values are masked
        assert "abcdef1234567890" not in masked  # Hash is masked
        assert "long_session_data" not in masked  # Session is masked

    def test_mask_text_ip_addresses(self):
        """Test IP address masking."""
        text = "Request from 192.168.1.100 with token abc123"
        masked = PIIMasker.mask_text(text)

        assert "192.168.1.100" not in masked
        assert "[REDACTED]" in masked
        # Note: abc123 is not masked as it doesn't match any PII pattern

    def test_mask_dict(self):
        """Test dictionary masking."""
        data = {
            "username": "testuser",
            "api_id": "12345",
            "nested": {
                "session_string": "long_session_data",
                "safe_field": "safe_value"
            },
            "safe_list": ["item1", "item2"]
        }

        masked = PIIMasker.mask_dict(data)

        assert masked["username"] == "testuser"  # Not sensitive
        assert masked["api_id"] == "[REDACTED]"  # Sensitive
        assert masked["nested"]["session_string"] == "[REDACTED]"  # Sensitive
        assert masked["nested"]["safe_field"] == "safe_value"  # Not sensitive
        assert masked["safe_list"] == ["item1", "item2"]  # Not sensitive

    def test_mask_empty_values(self):
        """Test masking with None and empty values."""
        assert PIIMasker.mask_text(None) == "None"
        assert PIIMasker.mask_text("") == ""
        assert PIIMasker.mask_dict({}) == {}
        assert PIIMasker.mask_dict(None) == {}

    def test_hash_identifier(self):
        """Test identifier hashing."""
        identifier = "test_session_123"
        hashed = PIIMasker.hash_identifier(identifier, "")  # No prefix

        assert hashed != identifier
        assert len(hashed) == 64  # SHA256 hex length
        assert hashed.isalnum()

    def test_hash_identifier_with_prefix(self):
        """Test identifier hashing with custom prefix."""
        identifier = "test_session_123"
        hashed = PIIMasker.hash_identifier(identifier, "custom")

        assert hashed.startswith("custom_")
        assert len(hashed) > len("custom_")


class TestRateLimiter:
    """Test rate limiting functionality."""

    @pytest.fixture
    def rate_limiter(self):
        """Create a test rate limiter."""
        return RateLimiter(requests_per_minute=10, burst_limit=3)

    def test_rate_limiter_init(self, rate_limiter):
        """Test rate limiter initialization."""
        assert rate_limiter.requests_per_minute == 10
        assert rate_limiter.burst_limit == 3
        assert rate_limiter.requests == {}

    @pytest.mark.asyncio
    async def test_rate_limiter_allow(self, rate_limiter):
        """Test allowing requests within limits."""
        allowed, wait_time = await rate_limiter.check_rate_limit("test_user")
        assert allowed is True
        assert wait_time == 0.0

        # Should still be allowed
        allowed, wait_time = await rate_limiter.check_rate_limit("test_user")
        assert allowed is True
        assert wait_time == 0.0

    @pytest.mark.asyncio
    async def test_rate_limiter_burst_limit(self, rate_limiter):
        """Test burst limit enforcement."""
        # Use up burst limit
        for i in range(3):
            allowed, wait_time = await rate_limiter.check_rate_limit("test_user")
            assert allowed is True

        # Next request should be blocked
        allowed, wait_time = await rate_limiter.check_rate_limit("test_user")
        assert allowed is False
        assert wait_time > 0

    @pytest.mark.asyncio
    async def test_rate_limiter_basic_functionality(self, rate_limiter):
        """Test basic rate limiter functionality."""
        # Test that initial requests are allowed
        allowed, wait_time = await rate_limiter.check_rate_limit("test_user")
        assert allowed is True
        assert wait_time == 0.0

        # Test that requests are being tracked
        assert "test_user" in rate_limiter.requests
        assert len(rate_limiter.requests["test_user"]) == 1

    @pytest.mark.asyncio
    async def test_rate_limiter_cleanup(self, rate_limiter):
        """Test old request cleanup."""
        with patch('src.telegram_toolkit_mcp.utils.security.datetime') as mock_datetime:
            from datetime import datetime, timedelta

            # Set initial time
            start_time = datetime.now()
            mock_datetime.now.return_value = start_time

            # Make some requests
            await rate_limiter.check_rate_limit("test_user")
            await rate_limiter.check_rate_limit("test_user")

            # Move time forward by more than 1 minute
            future_time = start_time + timedelta(minutes=2)
            mock_datetime.now.return_value = future_time

            # New request should be allowed (old requests cleaned up)
            allowed, wait_time = await rate_limiter.check_rate_limit("test_user")
            assert allowed is True
            assert wait_time == 0.0


class TestInputValidator:
    """Test input validation functionality."""

    def test_sanitize_chat_identifier_valid(self):
        """Test valid chat identifier sanitization."""
        valid_identifiers = [
            "@testchannel",
            "t.me/testchannel",
            "test_channel_123",
            "-1001234567890"
        ]

        for identifier in valid_identifiers:
            sanitized = InputValidator.sanitize_chat_identifier(identifier)
            assert sanitized == identifier.strip()

    def test_sanitize_chat_identifier_invalid(self):
        """Test invalid chat identifier rejection."""
        invalid_identifiers = [
            "",  # Empty
            "   ",  # Whitespace only
            "a" * 101,  # Too long
            "@channel<script>",  # Dangerous characters
            "channel; DROP TABLE users;",  # SQL injection attempt
        ]

        for identifier in invalid_identifiers:
            with pytest.raises(ValueError):
                InputValidator.sanitize_chat_identifier(identifier)

    def test_validate_page_size(self):
        """Test page size validation."""
        # Valid sizes
        assert InputValidator.validate_page_size(10) == 10
        assert InputValidator.validate_page_size(1) == 1
        assert InputValidator.validate_page_size(100) == 100

        # Invalid sizes
        with pytest.raises(ValueError):
            InputValidator.validate_page_size(0)

        with pytest.raises(ValueError):
            InputValidator.validate_page_size(-1)

        with pytest.raises(ValueError):
            InputValidator.validate_page_size(101)  # Over limit

    def test_validate_date_range_valid(self):
        """Test valid date range validation."""
        # Valid ranges
        InputValidator.validate_date_range("2025-01-01T00:00:00Z", "2025-01-02T00:00:00Z")
        InputValidator.validate_date_range("2025-01-01T00:00:00Z", None)
        InputValidator.validate_date_range(None, "2025-01-02T00:00:00Z")
        InputValidator.validate_date_range(None, None)

    def test_validate_date_range_invalid(self):
        """Test invalid date range validation."""
        # Invalid ranges
        with pytest.raises(ValueError, match="from_date must be before to_date"):
            InputValidator.validate_date_range("2025-01-02T00:00:00Z", "2025-01-01T00:00:00Z")  # From > To

        with pytest.raises(ValueError, match="Date range cannot exceed 1 year"):
            InputValidator.validate_date_range("2025-01-01T00:00:00Z", "2026-01-01T00:00:00Z")  # Too wide

        with pytest.raises(ValueError, match="Invalid date format"):
            InputValidator.validate_date_range("invalid-date", "2025-01-01T00:00:00Z")  # Invalid format

    def test_sanitize_search_query_valid(self):
        """Test valid search query sanitization."""
        queries = [
            "bitcoin price",
            "test query 123",
            "special_chars_@#$%",
        ]

        for query in queries:
            sanitized = InputValidator.sanitize_search_query(query)
            assert sanitized == query.strip()

    def test_sanitize_search_query_invalid(self):
        """Test invalid search query rejection."""
        invalid_queries = [
            "",  # Empty
            "a" * 257,  # Too long
            "query with <script> tags",  # Dangerous tags
        ]

        for query in invalid_queries:
            with pytest.raises(ValueError):
                InputValidator.sanitize_search_query(query)


class TestSessionManager:
    """Test session management functionality."""

    @pytest.fixture
    def session_manager(self):
        """Create a test session manager."""
        return SessionManager()

    def test_session_store_and_retrieve(self, session_manager):
        """Test session storage and retrieval."""
        session_id = "test_session_123"
        session_data = b"test_session_data_12345"

        # Store session
        session_manager.store_session(session_id, session_data)

        # Retrieve session
        retrieved = session_manager.get_session(session_id)
        assert retrieved == session_data

    def test_session_integrity_check(self, session_manager):
        """Test session integrity verification."""
        session_id = "test_session_123"
        session_data = b"test_session_data_12345"

        # Store session
        session_manager.store_session(session_id, session_data)

        # Tamper with stored data (simulate corruption)
        session_manager._session_cache[session_id] = b"corrupted_data"

        # Should return None due to integrity failure
        retrieved = session_manager.get_session(session_id)
        assert retrieved is None

    def test_session_remove(self, session_manager):
        """Test session removal."""
        session_id = "test_session_123"
        session_data = b"test_session_data_12345"

        # Store and verify
        session_manager.store_session(session_id, session_data)
        assert session_manager.get_session(session_id) == session_data

        # Remove and verify
        assert session_manager.remove_session(session_id) is True
        assert session_manager.get_session(session_id) is None

        # Remove non-existent
        assert session_manager.remove_session("non_existent") is False

    def test_session_list_and_clear(self, session_manager):
        """Test session listing and clearing."""
        # Store multiple sessions
        sessions = [
            ("session1", b"data1"),
            ("session2", b"data2"),
            ("session3", b"data3"),
        ]

        for session_id, data in sessions:
            session_manager.store_session(session_id, data)

        # List sessions (should be hashed)
        session_list = session_manager.list_sessions()
        assert len(session_list) == 3

        for hashed_id in session_list:
            assert hashed_id.startswith("session_")
            assert len(hashed_id) > len("session_")

        # Clear all sessions
        cleared_count = session_manager.clear_all_sessions()
        assert cleared_count == 3

        # Verify all cleared
        assert len(session_manager.list_sessions()) == 0


class TestSecurityAuditor:
    """Test security auditing functionality."""

    @pytest.fixture
    def security_auditor(self):
        """Create a test security auditor."""
        return SecurityAuditor()

    def test_log_security_event(self, security_auditor):
        """Test security event logging."""
        event_type = "test_event"
        details = {
            "user": "testuser",
            "ip": "192.168.1.100",
            "api_key": "secret_key_123"
        }

        security_auditor.log_security_event(event_type, details)

        # Check event was logged
        events = security_auditor.get_security_events()
        assert len(events) == 1

        event = events[0]
        assert event["event_type"] == event_type
        assert "timestamp" in event
        assert event["details"]["user"] == "testuser"  # Not sensitive
        assert event["details"]["ip"] == "[REDACTED]"  # Sensitive (IP)
        assert event["details"]["api_key"] == "[REDACTED]"  # Sensitive

    def test_security_event_limit(self, security_auditor):
        """Test security event limit enforcement."""
        security_auditor.max_events = 3

        # Log more events than limit
        for i in range(5):
            security_auditor.log_security_event(f"event_{i}", {"data": f"value_{i}"})

        # Should only keep the last max_events
        events = security_auditor.get_security_events()
        assert len(events) == 3

        # Should be the most recent events
        assert events[0]["event_type"] == "event_4"
        assert events[-1]["event_type"] == "event_2"

    def test_get_security_events_limit(self, security_auditor):
        """Test security events retrieval with limit."""
        # Log multiple events
        for i in range(5):
            security_auditor.log_security_event(f"event_{i}", {"data": f"value_{i}"})

        # Get with limit
        events = security_auditor.get_security_events(limit=2)
        assert len(events) == 2
        assert events[0]["event_type"] == "event_4"
        assert events[1]["event_type"] == "event_3"


class TestUtilityFunctions:
    """Test utility functions."""

    def test_generate_secure_token(self):
        """Test secure token generation."""
        token1 = generate_secure_token()
        token2 = generate_secure_token()

        assert len(token1) == 64  # 32 bytes * 2 hex chars per byte
        assert token1 != token2  # Should be unique
        assert all(c in "0123456789abcdef" for c in token1)  # Hex only

    def test_generate_secure_token_custom_length(self):
        """Test secure token generation with custom length."""
        token = generate_secure_token(16)  # 16 bytes
        assert len(token) == 32  # 16 bytes * 2 hex chars per byte

    def test_hash_sensitive_data(self):
        """Test sensitive data hashing."""
        data = "sensitive_password_123"
        salt = "test_salt"

        hashed1 = hash_sensitive_data(data, salt)
        hashed2 = hash_sensitive_data(data, salt)

        assert hashed1 == hashed2  # Same input should give same hash
        assert len(hashed1) == 64  # SHA256 hex length
        assert hashed1 != data  # Should not be the same as input

    def test_hash_sensitive_data_default_salt(self):
        """Test sensitive data hashing with default salt."""
        data = "test_data"

        hashed = hash_sensitive_data(data)  # No salt provided
        assert len(hashed) == 64
        assert hashed != data


class TestGlobalInstances:
    """Test global instance management."""

    def test_get_rate_limiter(self):
        """Test global rate limiter instance."""
        limiter1 = get_rate_limiter()
        limiter2 = get_rate_limiter()

        assert limiter1 is limiter2  # Should be same instance

    def test_get_session_manager(self):
        """Test global session manager instance."""
        manager1 = get_session_manager()
        manager2 = get_session_manager()

        assert manager1 is manager2  # Should be same instance

    def test_get_security_auditor(self):
        """Test global security auditor instance."""
        auditor1 = get_security_auditor()
        auditor2 = get_security_auditor()

        assert auditor1 is auditor2  # Should be same instance
