"""
Filtering and deduplication utilities for Telegram Toolkit MCP.

This module provides server-side filtering, deduplication, and data
quality assurance for message processing and retrieval.
"""

import hashlib
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple

from ..utils.logging import get_logger

logger = get_logger(__name__)


class DateRangeFilter:
    """
    Date range filtering for message collections.

    Handles various date formats, timezone conversions, and range validation.
    """

    @staticmethod
    def parse_datetime(date_str: str) -> datetime:
        """
        Parse datetime string with multiple format support.

        Args:
            date_str: Date string in various formats

        Returns:
            datetime: Parsed datetime object (UTC)

        Raises:
            ValueError: If date format is invalid
        """
        if not date_str:
            raise ValueError("Empty date string")

        # Handle different date formats
        formats = [
            "%Y-%m-%dT%H:%M:%S.%fZ",  # ISO with microseconds
            "%Y-%m-%dT%H:%M:%SZ",     # ISO without microseconds
            "%Y-%m-%dT%H:%M:%S",      # ISO without Z
            "%Y-%m-%d %H:%M:%S",      # SQL format
            "%Y-%m-%d",               # Date only
        ]

        for fmt in formats:
            try:
                dt = datetime.strptime(date_str.replace('Z', ''), fmt)
                # Assume UTC if no timezone info
                if 'Z' not in date_str and '+' not in date_str and '-' not in date_str[10:]:
                    dt = dt.replace(tzinfo=None)  # Naive datetime, assume UTC
                return dt
            except ValueError:
                continue

        raise ValueError(f"Unable to parse date: {date_str}")

    @staticmethod
    def validate_date_range(
        from_date: Optional[str],
        to_date: Optional[str]
    ) -> Tuple[Optional[datetime], Optional[datetime]]:
        """
        Validate and parse date range.

        Args:
            from_date: Start date string
            to_date: End date string

        Returns:
            Tuple of (from_datetime, to_datetime)

        Raises:
            ValueError: If date range is invalid
        """
        from_dt = None
        to_dt = None

        if from_date:
            from_dt = DateRangeFilter.parse_datetime(from_date)

        if to_date:
            to_dt = DateRangeFilter.parse_datetime(to_date)

        # Validate range
        if from_dt and to_dt and from_dt >= to_dt:
            raise ValueError("from_date must be before to_date")

        # Check for reasonable date ranges (not too far in future/past)
        now = datetime.utcnow()
        max_past = now - timedelta(days=365 * 10)  # 10 years ago
        max_future = now + timedelta(days=365)     # 1 year in future

        for dt, name in [(from_dt, "from_date"), (to_dt, "to_date")]:
            if dt:
                if dt < max_past:
                    logger.warning(f"{name} is too far in the past", date=dt.isoformat())
                elif dt > max_future:
                    logger.warning(f"{name} is too far in the future", date=dt.isoformat())

        return from_dt, to_dt

    @staticmethod
    def filter_messages_by_date(
        messages: List[Dict],
        from_date: Optional[datetime] = None,
        to_date: Optional[datetime] = None
    ) -> List[Dict]:
        """
        Filter messages by date range.

        Args:
            messages: List of message dictionaries
            from_date: Start date filter
            to_date: End date filter

        Returns:
            Filtered list of messages
        """
        if not from_date and not to_date:
            return messages

        filtered = []

        for msg in messages:
            msg_date = None

            # Extract date from message
            if 'date' in msg:
                if isinstance(msg['date'], (int, float)):
                    msg_date = datetime.fromtimestamp(msg['date'])
                elif isinstance(msg['date'], str):
                    try:
                        msg_date = DateRangeFilter.parse_datetime(msg['date'])
                    except ValueError:
                        logger.warning("Invalid date format in message", message_id=msg.get('id'))
                        continue
                elif isinstance(msg['date'], datetime):
                    msg_date = msg['date']

            if msg_date is None:
                logger.warning("Message without date", message_id=msg.get('id'))
                continue

            # Apply filters
            if from_date and msg_date < from_date:
                continue
            if to_date and msg_date > to_date:
                continue

            filtered.append(msg)

        logger.debug(
            "Date filtering applied",
            original_count=len(messages),
            filtered_count=len(filtered),
            from_date=from_date.isoformat() if from_date else None,
            to_date=to_date.isoformat() if to_date else None
        )

        return filtered


class MessageDeduplicator:
    """
    Message deduplication utilities.

    Handles duplicate detection and removal based on various criteria.
    """

    @staticmethod
    def generate_message_hash(message: Dict) -> str:
        """
        Generate hash for message deduplication.

        Args:
            message: Message dictionary

        Returns:
            str: Hash string for deduplication
        """
        # Use combination of ID, date, and content for uniqueness
        components = [
            str(message.get('id', '')),
            str(message.get('date', '')),
            message.get('text', ''),
            str(message.get('from', {}).get('id', '')),
        ]

        # Add media info if present
        if message.get('has_media'):
            components.append('media')

        content = '|'.join(components)
        return hashlib.md5(content.encode()).hexdigest()

    @staticmethod
    def deduplicate_messages(messages: List[Dict]) -> List[Dict]:
        """
        Remove duplicate messages based on content hash.

        Args:
            messages: List of message dictionaries

        Returns:
            Deduplicated list of messages
        """
        seen_hashes = set()
        deduplicated = []

        duplicates_found = 0

        for msg in messages:
            msg_hash = MessageDeduplicator.generate_message_hash(msg)

            if msg_hash in seen_hashes:
                duplicates_found += 1
                logger.debug("Duplicate message found", message_id=msg.get('id'), hash=msg_hash)
                continue

            seen_hashes.add(msg_hash)
            deduplicated.append(msg)

        if duplicates_found > 0:
            logger.info(
                "Deduplication completed",
                original_count=len(messages),
                deduplicated_count=len(deduplicated),
                duplicates_removed=duplicates_found
            )

        return deduplicated

    @staticmethod
    def deduplicate_by_id(messages: List[Dict]) -> List[Dict]:
        """
        Remove duplicates based on message ID only (faster).

        Args:
            messages: List of message dictionaries

        Returns:
            Deduplicated list of messages
        """
        seen_ids = set()
        deduplicated = []

        for msg in messages:
            msg_id = msg.get('id')
            if msg_id is None:
                deduplicated.append(msg)
                continue

            if msg_id in seen_ids:
                continue

            seen_ids.add(msg_id)
            deduplicated.append(msg)

        return deduplicated


class ContentFilter:
    """
    Content-based filtering for messages.

    Supports text search, media type filtering, and other content criteria.
    """

    @staticmethod
    def filter_by_text(messages: List[Dict], search_query: str) -> List[Dict]:
        """
        Filter messages containing specific text.

        Args:
            messages: List of message dictionaries
            search_query: Text to search for

        Returns:
            Filtered list of messages
        """
        if not search_query:
            return messages

        query_lower = search_query.lower()
        filtered = []

        for msg in messages:
            text = msg.get('text', '').lower()
            if query_lower in text:
                filtered.append(msg)

        logger.debug(
            "Text filtering applied",
            search_query=search_query,
            original_count=len(messages),
            filtered_count=len(filtered)
        )

        return filtered

    @staticmethod
    def filter_by_media_type(
        messages: List[Dict],
        media_types: Optional[List[str]] = None
    ) -> List[Dict]:
        """
        Filter messages by media type.

        Args:
            messages: List of message dictionaries
            media_types: List of media types to include (None for all)

        Returns:
            Filtered list of messages
        """
        if not media_types:
            return messages

        filtered = []
        media_types_set = set(media_types)

        for msg in messages:
            if msg.get('has_media'):
                media_type = msg.get('media_type', '')
                # Check if any of the message's media types match
                if any(mt in media_type.lower() for mt in media_types):
                    filtered.append(msg)
            elif 'text' in media_types:  # Include text-only messages
                filtered.append(msg)

        logger.debug(
            "Media type filtering applied",
            media_types=media_types,
            original_count=len(messages),
            filtered_count=len(filtered)
        )

        return filtered

    @staticmethod
    def filter_by_sender(messages: List[Dict], sender_ids: List[int]) -> List[Dict]:
        """
        Filter messages by sender ID.

        Args:
            messages: List of message dictionaries
            sender_ids: List of sender IDs to include

        Returns:
            Filtered list of messages
        """
        if not sender_ids:
            return messages

        sender_ids_set = set(sender_ids)
        filtered = []

        for msg in messages:
            sender_info = msg.get('sender', {})
            sender_id = sender_info.get('id')

            if sender_id and sender_id in sender_ids_set:
                filtered.append(msg)

        logger.debug(
            "Sender filtering applied",
            sender_ids=sender_ids,
            original_count=len(messages),
            filtered_count=len(filtered)
        )

        return filtered


class MessageProcessor:
    """
    High-level message processing pipeline.

    Combines filtering, deduplication, and quality assurance.
    """

    def __init__(self):
        self.date_filter = DateRangeFilter()
        self.deduplicator = MessageDeduplicator()
        self.content_filter = ContentFilter()

    def process_messages(
        self,
        messages: List[Dict],
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        search_query: Optional[str] = None,
        media_types: Optional[List[str]] = None,
        sender_ids: Optional[List[int]] = None,
        deduplicate: bool = True
    ) -> List[Dict]:
        """
        Process messages through filtering pipeline.

        Args:
            messages: Raw message list
            from_date: Start date filter
            to_date: End date filter
            search_query: Text search query
            media_types: Media type filters
            sender_ids: Sender ID filters
            deduplicate: Whether to remove duplicates

        Returns:
            Processed message list
        """
        logger.info("Starting message processing pipeline", message_count=len(messages))

        processed = messages

        # Step 1: Parse and validate date range
        from_dt, to_dt = None, None
        if from_date or to_date:
            try:
                from_dt, to_dt = self.date_filter.validate_date_range(from_date, to_date)
            except ValueError as e:
                logger.warning("Invalid date range, skipping date filtering", error=str(e))

        # Step 2: Apply date filtering
        if from_dt or to_dt:
            processed = self.date_filter.filter_messages_by_date(processed, from_dt, to_dt)

        # Step 3: Apply content filters
        if search_query:
            processed = self.content_filter.filter_by_text(processed, search_query)

        if media_types:
            processed = self.content_filter.filter_by_media_type(processed, media_types)

        if sender_ids:
            processed = self.content_filter.filter_by_sender(processed, sender_ids)

        # Step 4: Deduplication
        if deduplicate:
            processed = self.deduplicator.deduplicate_messages(processed)

        logger.info(
            "Message processing completed",
            original_count=len(messages),
            processed_count=len(processed),
            filters_applied={
                "date_range": bool(from_dt or to_dt),
                "search": bool(search_query),
                "media_types": bool(media_types),
                "sender_ids": bool(sender_ids),
                "deduplication": deduplicate
            }
        )

        return processed

    def validate_processing_params(
        self,
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        media_types: Optional[List[str]] = None,
        sender_ids: Optional[List[int]] = None
    ) -> None:
        """
        Validate processing parameters.

        Args:
            from_date: Start date
            to_date: End date
            media_types: Media type filters
            sender_ids: Sender ID filters

        Raises:
            ValueError: If parameters are invalid
        """
        # Validate date range
        if from_date or to_date:
            self.date_filter.validate_date_range(from_date, to_date)

        # Validate media types
        if media_types:
            valid_media_types = {'text', 'photo', 'video', 'document', 'audio', 'voice', 'sticker'}
            invalid_types = set(media_types) - valid_media_types
            if invalid_types:
                raise ValueError(f"Invalid media types: {invalid_types}")

        # Validate sender IDs
        if sender_ids:
            if not all(isinstance(sid, int) and sid > 0 for sid in sender_ids):
                raise ValueError("Sender IDs must be positive integers")


# Global processor instance
_message_processor = MessageProcessor()


def get_message_processor() -> MessageProcessor:
    """Get global message processor instance."""
    return _message_processor
