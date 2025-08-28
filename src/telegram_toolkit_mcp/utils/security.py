"""
Security utilities for Telegram Toolkit MCP.

This module provides security-related functionality including
input validation, rate limiting, and secure session handling.
"""

import asyncio
import hashlib
import hmac
import os
import secrets
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, Optional, Tuple

from .logging import PIIMasker, get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Rate limiter for API calls and tool usage."""

    def __init__(self, requests_per_minute: int = 30, burst_limit: int = 10):
        self.requests_per_minute = requests_per_minute
        self.burst_limit = burst_limit
        self.requests: Dict[str, list] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def check_rate_limit(self, identifier: str) -> Tuple[bool, float]:
        """
        Check if request is within rate limits.

        Args:
            identifier: Unique identifier for rate limiting (e.g., IP, user_id)

        Returns:
            Tuple of (allowed: bool, wait_time: float)
        """
        async with self._lock:
            now = datetime.now()
            cutoff = now - timedelta(minutes=1)

            # Clean old requests
            self.requests[identifier] = [
                req_time for req_time in self.requests[identifier]
                if req_time > cutoff
            ]

            current_requests = len(self.requests[identifier])

            if current_requests >= self.requests_per_minute:
                # Calculate wait time until oldest request expires
                oldest_request = min(self.requests[identifier])
                wait_time = (oldest_request - cutoff).total_seconds()
                return False, max(0, wait_time)

            # Check burst limit
            recent_requests = [
                req_time for req_time in self.requests[identifier]
                if req_time > now - timedelta(seconds=10)
            ]

            if len(recent_requests) >= self.burst_limit:
                wait_time = 10 - (now - min(recent_requests)).total_seconds()
                return False, max(0, wait_time)

            # Add current request
            self.requests[identifier].append(now)
            return True, 0.0


class InputValidator:
    """Input validation and sanitization utilities."""

    @staticmethod
    def sanitize_chat_identifier(identifier: str) -> str:
        """
        Sanitize chat identifier to prevent injection attacks.

        Args:
            identifier: Raw chat identifier

        Returns:
            str: Sanitized identifier

        Raises:
            ValueError: If identifier is invalid
        """
        if not isinstance(identifier, str):
            raise ValueError("Chat identifier must be a string")

        # Remove whitespace
        identifier = identifier.strip()

        if not identifier:
            raise ValueError("Chat identifier cannot be empty")

        if len(identifier) > 100:
            raise ValueError("Chat identifier too long")

        # Allow only specific characters
        import re
        if not re.match(r'^[@a-zA-Z0-9_/\-\.]+$', identifier):
            raise ValueError("Chat identifier contains invalid characters")

        return identifier

    @staticmethod
    def validate_page_size(page_size: int) -> int:
        """
        Validate and clamp page size.

        Args:
            page_size: Requested page size

        Returns:
            int: Validated page size
        """
        if not isinstance(page_size, int) or page_size < 1:
            raise ValueError("Page size must be a positive integer")

        # Clamp to reasonable limits
        return max(1, min(page_size, 100))

    @staticmethod
    def validate_date_range(from_date: Optional[str], to_date: Optional[str]) -> None:
        """
        Validate date range parameters.

        Args:
            from_date: Start date string
            to_date: End date string

        Raises:
            ValueError: If date range is invalid
        """
        from datetime import datetime

        if from_date and to_date:
            try:
                from_dt = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
                to_dt = datetime.fromisoformat(to_date.replace('Z', '+00:00'))

                if from_dt >= to_dt:
                    raise ValueError("from_date must be before to_date")

                # Prevent excessive date ranges
                if (to_dt - from_dt).days > 365:
                    raise ValueError("Date range cannot exceed 1 year")

            except ValueError as e:
                raise ValueError(f"Invalid date format: {e}")

    @staticmethod
    def sanitize_search_query(query: str) -> str:
        """
        Sanitize search query to prevent injection.

        Args:
            query: Raw search query

        Returns:
            str: Sanitized query

        Raises:
            ValueError: If query is invalid
        """
        if not isinstance(query, str):
            raise ValueError("Search query must be a string")

        query = query.strip()

        if len(query) > 256:
            raise ValueError("Search query too long")

        # Remove potentially dangerous characters
        import re
        query = re.sub(r'[<>]', '', query)

        return query


class SessionManager:
    """Secure session management for Telegram clients."""

    def __init__(self):
        self._session_cache: Dict[str, bytes] = {}
        self._session_hashes: Dict[str, str] = {}

    def store_session(self, session_id: str, session_data: bytes) -> None:
        """
        Securely store session data.

        Args:
            session_id: Unique session identifier
            session_data: Session data bytes
        """
        # Create hash for integrity checking
        session_hash = hashlib.sha256(session_data).hexdigest()

        # Store in memory only (never write to disk)
        self._session_cache[session_id] = session_data
        self._session_hashes[session_id] = session_hash

        logger.info(
            "Session stored securely",
            session_id=PIIMasker.hash_identifier(session_id, "session"),
            session_hash=session_hash[:8] + "..."
        )

    def get_session(self, session_id: str) -> Optional[bytes]:
        """
        Retrieve session data with integrity check.

        Args:
            session_id: Session identifier

        Returns:
            Session data or None if not found/invalid
        """
        if session_id not in self._session_cache:
            return None

        session_data = self._session_cache[session_id]
        expected_hash = self._session_hashes[session_id]

        # Verify integrity
        actual_hash = hashlib.sha256(session_data).hexdigest()
        if actual_hash != expected_hash:
            logger.error(
                "Session integrity check failed",
                session_id=PIIMasker.hash_identifier(session_id, "session")
            )
            # Remove corrupted session
            del self._session_cache[session_id]
            del self._session_hashes[session_id]
            return None

        return session_data

    def remove_session(self, session_id: str) -> bool:
        """
        Remove session data.

        Args:
            session_id: Session identifier

        Returns:
            bool: True if session was removed
        """
        if session_id in self._session_cache:
            del self._session_cache[session_id]
            del self._session_hashes[session_id]
            logger.info(
                "Session removed",
                session_id=PIIMasker.hash_identifier(session_id, "session")
            )
            return True
        return False

    def list_sessions(self) -> list[str]:
        """
        List available session IDs (for monitoring).

        Returns:
            List of hashed session IDs
        """
        return [PIIMasker.hash_identifier(sid, "session") for sid in self._session_cache.keys()]

    def clear_all_sessions(self) -> int:
        """
        Clear all stored sessions.

        Returns:
            int: Number of sessions cleared
        """
        count = len(self._session_cache)
        self._session_cache.clear()
        self._session_hashes.clear()
        logger.info("All sessions cleared", session_count=count)
        return count


class SecurityAuditor:
    """Security auditing and monitoring."""

    def __init__(self):
        self.security_events: list[Dict[str, Any]] = []
        self.max_events = 1000

    def log_security_event(self, event_type: str, details: Dict[str, Any]) -> None:
        """
        Log a security-related event.

        Args:
            event_type: Type of security event
            details: Event details
        """
        event = {
            'timestamp': datetime.now().isoformat(),
            'event_type': event_type,
            'details': PIIMasker.mask_dict(details)
        }

        self.security_events.append(event)

        # Keep only recent events
        if len(self.security_events) > self.max_events:
            self.security_events = self.security_events[-self.max_events:]

        logger.warning(
            "Security event logged",
            event_type=event_type,
            masked_details=PIIMasker.mask_dict(details)
        )

    def get_security_events(self, limit: int = 100) -> list[Dict[str, Any]]:
        """
        Get recent security events.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of security events
        """
        return self.security_events[-limit:]


# Global instances
_rate_limiter = RateLimiter()
_session_manager = SessionManager()
_security_auditor = SecurityAuditor()


def get_rate_limiter() -> RateLimiter:
    """Get global rate limiter instance."""
    return _rate_limiter


def get_session_manager() -> SessionManager:
    """Get global session manager instance."""
    return _session_manager


def get_security_auditor() -> SecurityAuditor:
    """Get global security auditor instance."""
    return _security_auditor


def generate_secure_token(length: int = 32) -> str:
    """
    Generate a secure random token.

    Args:
        length: Token length in bytes

    Returns:
        str: Hex-encoded token
    """
    return secrets.token_hex(length)


def hash_sensitive_data(data: str, salt: Optional[str] = None) -> str:
    """
    Hash sensitive data for storage/logging.

    Args:
        data: Data to hash
        salt: Optional salt

    Returns:
        str: Hashed data
    """
    if salt is None:
        salt = os.environ.get('HASH_SALT', 'telegram-toolkit-mcp')

    return hmac.new(
        salt.encode(),
        data.encode(),
        hashlib.sha256
    ).hexdigest()
