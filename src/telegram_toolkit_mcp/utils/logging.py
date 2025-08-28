"""
Logging utilities with PII protection for Telegram Toolkit MCP.

This module provides structured logging with automatic PII masking
and security-conscious log formatting.
"""

import hashlib
import json
import logging
import re
import sys
from typing import Any

from .config import get_config


class PIIMasker:
    """PII masking utilities."""

    # Patterns for sensitive information
    SENSITIVE_PATTERNS = [
        # Phone numbers (international format)
        re.compile(
            r"\+\d{1,4}[\s\-\.]?\(?\d{1,4}\)?[\s\-\.]?\d{1,4}[\s\-\.]?\d{1,4}[\s\-\.]?\d{0,4}"
        ),
        # Email addresses
        re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b"),
        # API keys/hashes (32+ hex chars)
        re.compile(r"\b[a-fA-F0-9]{32,}\b"),
        # Telegram session strings (base64-like, 100+ chars)
        re.compile(r"[A-Za-z0-9+/=]{100,}"),
        # Telegram API credentials
        re.compile(
            r"(?i)(api_id|api_hash|session_string|telegram_token)\s*[=:]\s*['\"]?([^'\"\s]{10,})['\"]?"
        ),
        # IP addresses
        re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
        # URLs with sensitive parameters
        re.compile(r"https?://[^\s]*?(?:token|key|secret|password|session)[^\s]*"),
        # Chat IDs (large numeric strings)
        re.compile(r"(?<!\d)-?\d{8,}(?!\d)"),
        # User mentions with sensitive info
        re.compile(r"@[a-zA-Z0-9_]{3,}@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
    ]

    # Fields that should always be masked
    SENSITIVE_FIELDS = {
        "password",
        "token",
        "secret",
        "key",
        "api_key",
        "session",
        "auth",
        "credential",
        "api_id",
        "api_hash",
        "session_string",
        "phone",
        "email",
        "user_id",
        "chat_id",
        "message_id",
        "file_id",
        "access_token",
        "refresh_token",
    }

    @staticmethod
    def mask_text(text: str) -> str:
        """
        Mask sensitive information in text.

        Args:
            text: Input text to mask

        Returns:
            str: Masked text
        """
        if not isinstance(text, str):
            return str(text)

        masked = text
        for pattern in PIIMasker.SENSITIVE_PATTERNS:
            masked = pattern.sub("[REDACTED]", masked)

        return masked

    @staticmethod
    def mask_dict(data: dict) -> dict:
        """
        Recursively mask sensitive information in dictionary.

        Args:
            data: Dictionary to mask

        Returns:
            dict: Masked dictionary
        """
        if data is None:
            return {}
        if not isinstance(data, dict):
            return data

        masked = {}
        for key, value in data.items():
            # Mask sensitive field names
            if key.lower() in PIIMasker.SENSITIVE_FIELDS:
                masked[key] = "[REDACTED]"
            elif isinstance(value, dict):
                masked[key] = PIIMasker.mask_dict(value)
            elif isinstance(value, list):
                masked[key] = [PIIMasker.mask_value(item) for item in data[key]]
            else:
                masked[key] = PIIMasker.mask_value(value)

        return masked

    @staticmethod
    def mask_value(value: Any) -> Any:
        """
        Mask a single value if it contains sensitive information.

        Args:
            value: Value to mask

        Returns:
            Masked value
        """
        if isinstance(value, str):
            return PIIMasker.mask_text(value)
        elif isinstance(value, dict):
            return PIIMasker.mask_dict(value)
        elif isinstance(value, list):
            return [PIIMasker.mask_value(item) for item in value]
        else:
            return value

    @staticmethod
    def hash_identifier(identifier: str, prefix: str = "hash") -> str:
        """
        Create a hash-based identifier for logging.

        Args:
            identifier: Original identifier
            prefix: Prefix for the hashed identifier

        Returns:
            str: Hashed identifier
        """
        if not identifier:
            if prefix:
                return f"{prefix}_empty"
            else:
                return "empty"

        # Use full SHA256 hash for test compatibility
        hash_obj = hashlib.sha256(identifier.encode())
        full_hash = hash_obj.hexdigest()

        if prefix:
            return f"{prefix}_{full_hash}"
        else:
            return full_hash


class SecureFormatter(logging.Formatter):
    """Logging formatter with automatic PII masking."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.masker = PIIMasker()

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with PII masking."""
        # Format the message first
        formatted = super().format(record)

        # Mask sensitive information
        return self.masker.mask_text(formatted)


class StructuredLogger:
    """Structured JSON logger for MCP operations."""

    def __init__(self, name: str):
        self.name = name
        self.masker = PIIMasker()
        self._logger = None

    @property
    def logger(self) -> logging.Logger:
        """Get configured logger instance."""
        if self._logger is None:
            self._setup_logger()
        return self._logger

    def _setup_logger(self) -> None:
        """Set up logger with secure formatting."""
        config = get_config()

        self._logger = logging.getLogger(self.name)
        self._logger.setLevel(getattr(logging, config.server.log_level))

        # Remove existing handlers
        for handler in self._logger.handlers[:]:
            self._logger.removeHandler(handler)

        # Create console handler with secure formatter
        handler = logging.StreamHandler(sys.stdout)
        formatter = SecureFormatter(
            '{"timestamp": "%(asctime)s", "level": "%(levelname)s", '
            '"logger": "%(name)s", "message": "%(message)s"}'
        )
        handler.setFormatter(formatter)
        self._logger.addHandler(handler)

        # Prevent duplicate messages
        self._logger.propagate = False

    def _create_log_entry(self, level: str, message: str, **kwargs) -> dict[str, Any]:
        """
        Create structured log entry.

        Args:
            level: Log level
            message: Log message
            **kwargs: Additional structured data

        Returns:
            Dict containing log entry data
        """
        import datetime

        entry = {
            "timestamp": datetime.datetime.utcnow().isoformat() + "Z",
            "level": level,
            "logger": self.name,
            "message": self.masker.mask_text(message),
        }

        # Add structured data
        for key, value in kwargs.items():
            if key == "chat_id" and value or key == "chat" and value:
                entry["chat_hash"] = self.masker.hash_identifier(str(value), "chat")
            elif key == "trace_id" and value:
                entry["trace_id"] = value
            elif key == "span_id" and value:
                entry["span_id"] = value
            elif key == "tool" and value:
                entry["tool"] = value
            elif key == "log_level" and value:  # Handle log_level field
                entry["log_level"] = value
            elif key == "duration" and isinstance(value, int | float):
                entry["duration"] = value
            elif key == "status" and value:
                entry["status"] = value
            elif key == "fetched" and isinstance(value, int):
                entry["fetched"] = value
            elif key == "flood_wait_seconds" and isinstance(value, int | float):
                entry["flood_wait_seconds"] = value
            # For unknown fields, mask and include if safe
            elif isinstance(value, str):
                entry[key] = self.masker.mask_text(value)
            elif isinstance(value, int | float | bool):
                entry[key] = value

        return entry

    def debug(self, message: str, **kwargs) -> None:
        """Log debug message."""
        entry = self._create_log_entry("DEBUG", message, **kwargs)
        self.logger.debug(json.dumps(entry, ensure_ascii=False))

    def info(self, message: str, **kwargs) -> None:
        """Log info message."""
        entry = self._create_log_entry("INFO", message, **kwargs)
        self.logger.info(json.dumps(entry, ensure_ascii=False))

    def warning(self, message: str, **kwargs) -> None:
        """Log warning message."""
        entry = self._create_log_entry("WARNING", message, **kwargs)
        self.logger.warning(json.dumps(entry, ensure_ascii=False))

    def error(self, message: str, **kwargs) -> None:
        """Log error message."""
        entry = self._create_log_entry("ERROR", message, **kwargs)
        self.logger.error(json.dumps(entry, ensure_ascii=False))

    def critical(self, message: str, **kwargs) -> None:
        """Log critical message."""
        entry = self._create_log_entry("CRITICAL", message, **kwargs)
        self.logger.critical(json.dumps(entry, ensure_ascii=False))

    def log_tool_call(
        self,
        tool: str,
        chat: str | None = None,
        status: str = "unknown",
        duration: float | None = None,
        fetched: int | None = None,
        error: str | None = None,
        trace_id: str | None = None,
        **kwargs,
    ) -> None:
        """
        Log MCP tool call with structured data.

        Args:
            tool: Tool name
            chat: Chat identifier (will be hashed)
            status: Call status (success/error)
            duration: Call duration in seconds
            fetched: Number of items fetched
            error: Error message if applicable
            trace_id: Trace identifier
            **kwargs: Additional structured data
        """
        message = f"Tool call: {tool}"
        if error:
            message += f" - Error: {error}"

        self.info(
            message,
            tool=tool,
            chat=chat,
            status=status,
            duration=duration,
            fetched=fetched,
            trace_id=trace_id,
            **kwargs,
        )

    def log_telegram_api_call(
        self,
        method: str,
        chat: str | None = None,
        success: bool = True,
        duration: float | None = None,
        flood_wait: float | None = None,
        **kwargs,
    ) -> None:
        """
        Log Telegram API call.

        Args:
            method: API method name
            chat: Chat identifier (will be hashed)
            success: Whether call was successful
            duration: Call duration
            flood_wait: FLOOD_WAIT seconds if applicable
        """
        status = "success" if success else "error"
        message = f"Telegram API call: {method}"

        if flood_wait:
            message += f" - FLOOD_WAIT: {flood_wait}s"

        self.info(
            message,
            method=method,
            chat=chat,
            status=status,
            duration=duration,
            flood_wait_seconds=flood_wait,
            **kwargs,
        )


# Global logger instance
_default_logger: StructuredLogger | None = None


def get_logger(name: str = "telegram_toolkit_mcp") -> StructuredLogger:
    """
    Get structured logger instance.

    Args:
        name: Logger name

    Returns:
        StructuredLogger: Configured logger instance
    """
    global _default_logger
    if _default_logger is None or _default_logger.name != name:
        _default_logger = StructuredLogger(name)
    return _default_logger


def setup_logging() -> None:
    """Setup global logging configuration."""
    # Configure root logger to prevent duplicate messages
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.WARNING)  # Only show warnings and above from other libraries

    # Our logger will handle its own output
    logger = get_logger()
    logger.info("Logging system initialized", log_level="INFO")


# Initialize logging when module is imported
setup_logging()
