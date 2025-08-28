"""
Pagination utilities for Telegram Toolkit MCP.

This module provides cursor-based pagination with proper encoding/decoding,
support for different sorting orders, and pagination state management.
"""

import base64
import json
from datetime import datetime
from typing import Any, Dict, Optional, Tuple

from ..utils.logging import get_logger

logger = get_logger(__name__)


class PaginationCursor:
    """
    Cursor for pagination state management.

    Encodes pagination state into an opaque string that can be safely
    passed between client and server.
    """

    def __init__(
        self,
        offset_id: Optional[int] = None,
        offset_date: Optional[datetime] = None,
        direction: str = "desc",  # "asc" or "desc"
        chat_id: Optional[str] = None,
        fetched_count: int = 0
    ):
        """
        Initialize pagination cursor.

        Args:
            offset_id: Message ID to offset from
            offset_date: Date to offset from
            direction: Sort direction ("asc" or "desc")
            chat_id: Chat identifier for validation
            fetched_count: Number of messages fetched so far
        """
        self.offset_id = offset_id
        self.offset_date = offset_date
        self.direction = direction
        self.chat_id = chat_id
        self.fetched_count = fetched_count

    def to_dict(self) -> Dict[str, Any]:
        """
        Convert cursor to dictionary for serialization.

        Returns:
            Dict containing cursor state
        """
        data = {
            "direction": self.direction,
            "fetched_count": self.fetched_count,
        }

        if self.offset_id is not None:
            data["offset_id"] = self.offset_id

        if self.offset_date is not None:
            data["offset_date"] = self.offset_date.timestamp()

        if self.chat_id is not None:
            data["chat_id"] = self.chat_id

        return data

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'PaginationCursor':
        """
        Create cursor from dictionary.

        Args:
            data: Dictionary containing cursor state

        Returns:
            PaginationCursor instance
        """
        offset_date = None
        if "offset_date" in data:
            offset_date = datetime.fromtimestamp(data["offset_date"])

        return cls(
            offset_id=data.get("offset_id"),
            offset_date=offset_date,
            direction=data.get("direction", "desc"),
            chat_id=data.get("chat_id"),
            fetched_count=data.get("fetched_count", 0)
        )

    def encode(self) -> str:
        """
        Encode cursor to base64 string.

        Returns:
            str: Base64-encoded cursor
        """
        try:
            data = self.to_dict()
            json_str = json.dumps(data, ensure_ascii=False)
            encoded = base64.urlsafe_b64encode(json_str.encode('utf-8'))
            return encoded.decode('utf-8')
        except Exception as e:
            logger.error("Failed to encode cursor", error=str(e))
            raise ValueError(f"Failed to encode cursor: {e}")

    @classmethod
    def decode(cls, cursor_str: str) -> 'PaginationCursor':
        """
        Decode cursor from base64 string.

        Args:
            cursor_str: Base64-encoded cursor

        Returns:
            PaginationCursor instance

        Raises:
            ValueError: If cursor is invalid
        """
        try:
            # Add padding if needed
            missing_padding = len(cursor_str) % 4
            if missing_padding:
                cursor_str += '=' * (4 - missing_padding)

            decoded = base64.urlsafe_b64decode(cursor_str.encode('utf-8'))
            data = json.loads(decoded.decode('utf-8'))

            return cls.from_dict(data)

        except Exception as e:
            logger.error("Failed to decode cursor", cursor=cursor_str, error=str(e))
            raise ValueError(f"Invalid cursor: {e}")

    def is_valid_for_chat(self, chat_id: str) -> bool:
        """
        Check if cursor is valid for a specific chat.

        Args:
            chat_id: Chat identifier to validate against

        Returns:
            bool: True if cursor is valid for the chat
        """
        if self.chat_id is None:
            return True  # No chat validation required

        return str(self.chat_id) == str(chat_id)

    def get_next_cursor(self, last_message: Dict[str, Any]) -> 'PaginationCursor':
        """
        Create next cursor based on last message.

        Args:
            last_message: Last message in current page

        Returns:
            PaginationCursor for next page
        """
        next_cursor = PaginationCursor(
            direction=self.direction,
            chat_id=self.chat_id,
            fetched_count=self.fetched_count
        )

        # Set offset based on last message
        if 'id' in last_message:
            if self.direction == "desc":
                # For descending: use message ID as offset
                next_cursor.offset_id = last_message['id']
            else:
                # For ascending: use message ID + 1
                next_cursor.offset_id = last_message['id'] + 1

        if 'date' in last_message and isinstance(last_message['date'], (int, float)):
            next_cursor.offset_date = datetime.fromtimestamp(last_message['date'])

        return next_cursor


class Paginator:
    """
    High-level pagination manager for message history.

    Handles cursor encoding/decoding, page size validation,
    and pagination state management.
    """

    MAX_PAGE_SIZE = 100
    DEFAULT_PAGE_SIZE = 50
    MAX_TOTAL_MESSAGES = 10000  # Safety limit

    def __init__(self, chat_id: str):
        """
        Initialize paginator for a specific chat.

        Args:
            chat_id: Chat identifier
        """
        self.chat_id = str(chat_id)

    def validate_page_size(self, page_size: int) -> int:
        """
        Validate and normalize page size.

        Args:
            page_size: Requested page size

        Returns:
            int: Validated page size
        """
        if page_size < 1:
            raise ValueError("page_size must be positive")

        if page_size > self.MAX_PAGE_SIZE:
            logger.warning(
                "Page size too large, limiting to maximum",
                requested=page_size,
                max_allowed=self.MAX_PAGE_SIZE
            )
            return self.MAX_PAGE_SIZE

        return page_size

    def decode_cursor(self, cursor_str: Optional[str]) -> Optional[PaginationCursor]:
        """
        Decode cursor string to PaginationCursor.

        Args:
            cursor_str: Base64-encoded cursor string

        Returns:
            PaginationCursor or None if no cursor
        """
        if not cursor_str:
            return None

        try:
            cursor = PaginationCursor.decode(cursor_str)

            # Validate cursor for this chat
            if not cursor.is_valid_for_chat(self.chat_id):
                logger.warning(
                    "Cursor not valid for chat",
                    cursor_chat=cursor.chat_id,
                    current_chat=self.chat_id
                )
                return None

            return cursor

        except ValueError as e:
            logger.warning("Invalid cursor provided", cursor=cursor_str, error=str(e))
            return None

    def create_initial_cursor(self, direction: str = "desc") -> PaginationCursor:
        """
        Create initial cursor for first page.

        Args:
            direction: Sort direction

        Returns:
            PaginationCursor for first page
        """
        return PaginationCursor(
            direction=direction,
            chat_id=self.chat_id,
            fetched_count=0
        )

    def get_pagination_params(
        self,
        cursor: Optional[PaginationCursor],
        page_size: int,
        direction: str = "desc"
    ) -> Dict[str, Any]:
        """
        Get pagination parameters for Telegram API call.

        Args:
            cursor: Current pagination cursor
            page_size: Number of messages per page
            direction: Sort direction

        Returns:
            Dict containing parameters for iter_messages
        """
        params = {
            'limit': page_size,
            'reverse': direction == "asc",  # Telethon reverse parameter
        }

        if cursor:
            if cursor.offset_id is not None:
                params['offset_id'] = cursor.offset_id

            if cursor.offset_date is not None:
                params['offset_date'] = cursor.offset_date

        return params

    def should_continue_pagination(
        self,
        messages: list,
        requested_page_size: int,
        total_fetched: int
    ) -> bool:
        """
        Determine if pagination should continue.

        Args:
            messages: Messages in current page
            requested_page_size: Requested page size
            total_fetched: Total messages fetched so far

        Returns:
            bool: True if more pages are available
        """
        # If we got fewer messages than requested, we've reached the end
        if len(messages) < requested_page_size:
            return False

        # Safety check: don't fetch too many messages total
        if total_fetched >= self.MAX_TOTAL_MESSAGES:
            logger.warning(
                "Reached maximum total messages limit",
                total_fetched=total_fetched,
                max_allowed=self.MAX_TOTAL_MESSAGES
            )
            return False

        return True


def encode_cursor(cursor: PaginationCursor) -> str:
    """
    Convenience function to encode cursor.

    Args:
        cursor: PaginationCursor to encode

    Returns:
        str: Encoded cursor
    """
    return cursor.encode()


def decode_cursor(cursor_str: str) -> Optional[PaginationCursor]:
    """
    Convenience function to decode cursor.

    Args:
        cursor_str: Cursor string to decode

    Returns:
        PaginationCursor or None if invalid
    """
    try:
        return PaginationCursor.decode(cursor_str)
    except ValueError:
        return None


# Export main classes and functions
__all__ = [
    "PaginationCursor",
    "Paginator",
    "encode_cursor",
    "decode_cursor"
]
