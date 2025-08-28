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
from typing import Any, Dict, Optional

from .config import get_config


class PIIMasker:
    """PII masking utilities."""

    # Patterns for sensitive information
    SENSITIVE_PATTERNS = [
        # Phone numbers
        re.compile(r'\+\d{10,}'),
        # Email addresses
        re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
        # API keys/hashes (long hex strings)
        re.compile(r'\b[a-fA-F0-9]{32,}\b'),
        # Telegram session strings (base64-like)
        re.compile(r'[A-Za-z0-9+/=]{100,}'),
    ]

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
            masked = pattern.sub('[REDACTED]', masked)

        return masked

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
            return f"{prefix}:empty"

        # Use first 16 chars of SHA256 hash
        hash_obj = hashlib.sha256(identifier.encode())
        hash_short = hash_obj.hexdigest()[:16]

        return f"{prefix}:{hash_short}"


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

    def _create_log_entry(
        self,
        level: str,
        message: str,
        **kwargs
    ) -> Dict[str, Any]:
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
            "message": self.masker.mask_text(message)
        }

        # Add structured data
        for key, value in kwargs.items():
            if key == "chat_id" and value:
                entry["chat_hash"] = self.masker.hash_identifier(str(value), "chat")
            elif key == "chat" and value:
                entry["chat_hash"] = self.masker.hash_identifier(str(value), "chat")
            elif key == "trace_id" and value:
                entry["trace_id"] = value
            elif key == "span_id" and value:
                entry["span_id"] = value
            elif key == "tool" and value:
                entry["tool"] = value
            elif key == "duration" and isinstance(value, (int, float)):
                entry["duration"] = value
            elif key == "status" and value:
                entry["status"] = value
            elif key == "fetched" and isinstance(value, int):
                entry["fetched"] = value
            elif key == "flood_wait_seconds" and isinstance(value, (int, float)):
                entry["flood_wait_seconds"] = value
            else:
                # For unknown fields, mask and include if safe
                if isinstance(value, str):
                    entry[key] = self.masker.mask_text(value)
                elif isinstance(value, (int, float, bool)):
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
        chat: Optional[str] = None,
        status: str = "unknown",
        duration: Optional[float] = None,
        fetched: Optional[int] = None,
        error: Optional[str] = None,
        trace_id: Optional[str] = None,
        **kwargs
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
            **kwargs
        )

    def log_telegram_api_call(
        self,
        method: str,
        chat: Optional[str] = None,
        success: bool = True,
        duration: Optional[float] = None,
        flood_wait: Optional[float] = None,
        **kwargs
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
            **kwargs
        )


# Global logger instance
_default_logger: Optional[StructuredLogger] = None


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
    logger.info("Logging system initialized", level="INFO")


# Initialize logging when module is imported
setup_logging()
