"""
Error handling and exception management for Telegram Toolkit MCP.

This module provides centralized error handling, retry logic, and
MCP-compliant error responses for the Telegram integration.
"""

import asyncio
from collections.abc import AsyncGenerator, Callable
from contextlib import asynccontextmanager
from typing import Any, TypeVar

from ..utils.logging import get_logger

logger = get_logger(__name__)

T = TypeVar("T")


class TelegramMCPErrors:
    """Standard error codes for MCP responses."""

    # Authentication and authorization
    AUTH_REQUIRED = "AUTH_REQUIRED"
    SESSION_INVALID = "SESSION_INVALID"

    # Chat and channel access
    CHAT_NOT_FOUND = "CHAT_NOT_FOUND"
    CHANNEL_PRIVATE = "CHANNEL_PRIVATE"
    ACCESS_DENIED = "ACCESS_DENIED"

    # Rate limiting
    FLOOD_WAIT = "FLOOD_WAIT"
    RATE_LIMITED = "RATE_LIMITED"

    # Data and parsing
    INVALID_CHAT_ID = "INVALID_CHAT_ID"
    MESSAGE_NOT_FOUND = "MESSAGE_NOT_FOUND"
    PARSING_ERROR = "PARSING_ERROR"

    # Network and connectivity
    NETWORK_ERROR = "NETWORK_ERROR"
    TIMEOUT_ERROR = "TIMEOUT_ERROR"
    CONNECTION_ERROR = "CONNECTION_ERROR"

    # Input validation
    INPUT_VALIDATION = "INPUT_VALIDATION"
    INVALID_DATE_RANGE = "INVALID_DATE_RANGE"
    INVALID_PAGE_SIZE = "INVALID_PAGE_SIZE"

    # Resource management
    RESOURCE_EXHAUSTED = "RESOURCE_EXHAUSTED"
    STORAGE_ERROR = "STORAGE_ERROR"

    # Generic errors
    INTERNAL_ERROR = "INTERNAL_ERROR"
    UNKNOWN_ERROR = "UNKNOWN_ERROR"


class TelegramMCPException(Exception):
    """
    Base exception class for Telegram Toolkit MCP errors.

    This exception includes MCP-compliant error information.
    """

    def __init__(
        self,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
        retry_after: int | None = None,
        cause: Exception | None = None,
    ):
        """
        Initialize MCP exception.

        Args:
            code: Error code from TelegramMCPErrors
            message: Human-readable error message
            details: Additional error details
            retry_after: Seconds to wait before retry (for rate limits)
            cause: Original exception that caused this error
        """
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.retry_after = retry_after
        self.cause = cause

    def to_dict(self) -> dict[str, Any]:
        """
        Convert exception to dictionary for MCP response.

        Returns:
            Dict containing error information
        """
        error_dict = {
            "code": self.code,
            "message": self.message,
        }

        if self.details:
            error_dict["details"] = self.details

        if self.retry_after is not None:
            error_dict["retry_after"] = self.retry_after

        if self.cause:
            error_dict["cause"] = str(self.cause)

        return error_dict


class FloodWaitException(TelegramMCPException):
    """Exception for Telegram FLOOD_WAIT errors."""

    def __init__(self, retry_after: int, cause: Exception | None = None):
        super().__init__(
            code=TelegramMCPErrors.FLOOD_WAIT,
            message=f"Rate limit exceeded. Wait {retry_after} seconds before retry.",
            retry_after=retry_after,
            cause=cause,
        )


class ChannelPrivateException(TelegramMCPException):
    """Exception for private/unaccessible channels."""

    def __init__(self, chat_id: str | int, cause: Exception | None = None):
        super().__init__(
            code=TelegramMCPErrors.CHANNEL_PRIVATE,
            message=f"Channel {chat_id} is private or inaccessible",
            details={"chat_id": str(chat_id)},
            cause=cause,
        )


class ChatNotFoundException(TelegramMCPException):
    """Exception for non-existent chats."""

    def __init__(self, chat_id: str | int, cause: Exception | None = None):
        super().__init__(
            code=TelegramMCPErrors.CHAT_NOT_FOUND,
            message=f"Chat {chat_id} not found",
            details={"chat_id": str(chat_id)},
            cause=cause,
        )


class ValidationException(TelegramMCPException):
    """Exception for input validation errors."""

    def __init__(self, field: str, value: Any, reason: str, cause: Exception | None = None):
        super().__init__(
            code=TelegramMCPErrors.INPUT_VALIDATION,
            message=f"Invalid {field}: {reason}",
            details={"field": field, "value": str(value), "reason": reason},
            cause=cause,
        )


def map_telethon_exception(exc: Exception) -> TelegramMCPException:
    """
    Map Telethon exceptions to MCP exceptions.

    Args:
        exc: Original Telethon exception

    Returns:
        TelegramMCPException: Mapped MCP exception
    """
    exc_type = type(exc).__name__
    exc_str = str(exc)

    # Handle specific Telethon exceptions
    if "flood" in exc_str.lower():
        # Extract retry time from flood wait message
        import re

        match = re.search(r"wait (\d+)", exc_str, re.IGNORECASE)
        retry_after = int(match.group(1)) if match else 60

        return FloodWaitException(retry_after, exc)

    elif "chat not found" in exc_str.lower() or "peer not found" in exc_str.lower():
        return ChatNotFoundException("unknown", exc)

    elif "channel private" in exc_str.lower() or "you have not joined" in exc_str.lower():
        return ChannelPrivateException("unknown", exc)

    elif "timeout" in exc_str.lower():
        return TelegramMCPException(TelegramMCPErrors.TIMEOUT_ERROR, "Request timed out", cause=exc)

    elif "connection" in exc_str.lower():
        return TelegramMCPException(
            TelegramMCPErrors.CONNECTION_ERROR, "Connection error", cause=exc
        )

    # Generic mapping
    else:
        return TelegramMCPException(
            TelegramMCPErrors.INTERNAL_ERROR, f"Internal error: {exc_str}", cause=exc
        )


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_attempts: int = 3,
        initial_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_factor: float = 2.0,
        jitter: bool = True,
    ):
        """
        Initialize retry configuration.

        Args:
            max_attempts: Maximum number of retry attempts
            initial_delay: Initial delay between retries (seconds)
            max_delay: Maximum delay between retries (seconds)
            backoff_factor: Exponential backoff factor
            jitter: Whether to add random jitter to delays
        """
        self.max_attempts = max_attempts
        self.initial_delay = initial_delay
        self.max_delay = max_delay
        self.backoff_factor = backoff_factor
        self.jitter = jitter


async def retry_with_backoff(
    func: Callable[..., T], retry_config: RetryConfig = None, *args, **kwargs
) -> T:
    """
    Execute a function with exponential backoff retry logic.

    Args:
        func: Function to execute
        retry_config: Retry configuration
        *args: Positional arguments for func
        **kwargs: Keyword arguments for func

    Returns:
        Result of the function call

    Raises:
        TelegramMCPException: If all retry attempts fail
    """
    if retry_config is None:
        retry_config = RetryConfig()

    last_exception = None

    for attempt in range(retry_config.max_attempts):
        try:
            return await func(*args, **kwargs)

        except FloodWaitException as e:
            last_exception = e

            if attempt == retry_config.max_attempts - 1:
                # Last attempt failed with flood wait
                logger.error(
                    "All retry attempts failed with flood wait",
                    attempts=retry_config.max_attempts,
                    last_retry_after=e.retry_after,
                )
                raise

            # Wait for the flood wait duration
            wait_time = e.retry_after
            logger.warning(
                f"Flood wait encountered, waiting {wait_time}s",
                attempt=attempt + 1,
                max_attempts=retry_config.max_attempts,
                wait_time=wait_time,
            )
            await asyncio.sleep(wait_time)

        except Exception as e:
            last_exception = e

            if attempt == retry_config.max_attempts - 1:
                # Last attempt failed
                logger.error(
                    "All retry attempts failed",
                    attempts=retry_config.max_attempts,
                    last_error=str(e),
                )
                raise map_telethon_exception(e) from e

            # Calculate delay with exponential backoff
            delay = min(
                retry_config.initial_delay * (retry_config.backoff_factor**attempt),
                retry_config.max_delay,
            )

            if retry_config.jitter:
                # Add random jitter (±25%)
                import random

                jitter_range = delay * 0.25
                delay += random.uniform(-jitter_range, jitter_range)

            logger.warning(
                f"Attempt {attempt + 1} failed, retrying in {delay:.2f}s",
                attempt=attempt + 1,
                max_attempts=retry_config.max_attempts,
                delay=delay,
                error=str(e),
            )

            await asyncio.sleep(delay)

    # This should never be reached, but just in case
    if last_exception:
        raise map_telethon_exception(last_exception) from last_exception

    raise RuntimeError("Retry logic error")


@asynccontextmanager
async def error_handler() -> AsyncGenerator[None, None]:
    """
    Context manager for centralized error handling.

    Catches and maps exceptions to MCP-compliant errors.
    """
    try:
        yield
    except TelegramMCPException:
        # Already an MCP exception, re-raise as-is
        raise
    except Exception as e:
        # Map other exceptions to MCP format
        logger.error("Unhandled exception in error handler", error=str(e))
        raise map_telethon_exception(e) from e


def create_error_response(error: TelegramMCPException) -> dict[str, Any]:
    """
    Create MCP-compliant error response.

    Args:
        error: MCP exception

    Returns:
        Dict containing error response
    """
    return {
        "isError": True,
        "error": error.to_dict(),
        "content": [{"type": "text", "text": f"Error: {error.message}"}],
    }


def create_success_response(
    content: Any = None, structured_content: Any = None, resources: list | None = None
) -> dict[str, Any]:
    """
    Create MCP-compliant success response.

    Args:
        content: Human-readable content
        structured_content: Machine-readable structured data
        resources: List of MCP resources

    Returns:
        Dict containing success response
    """
    response = {
        "isError": False,
    }

    if content:
        response["content"] = content

    if structured_content:
        response["structuredContent"] = structured_content

    if resources:
        response["resources"] = resources

    return response
