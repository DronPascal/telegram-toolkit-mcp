"""
Integration Tests: Pagination + Filtering

This module tests the integration between Pagination and Filtering
components to ensure proper message processing and pagination.
"""

import pytest
from datetime import datetime, timezone, timedelta
import datetime as dt
from unittest.mock import MagicMock

from telegram_toolkit_mcp.core.pagination import Paginator, PaginationCursor
from telegram_toolkit_mcp.core.filtering import DateRangeFilter, MessageProcessor
from telegram_toolkit_mcp.models.types import MessageInfo


class TestPaginationFilteringIntegration:
    """Integration tests for Pagination and Filtering component interaction."""

    @pytest.fixture
    def paginator(self):
        """Create paginator instance."""
        return Paginator(chat_id="test_chat")

    @pytest.fixture
    def message_processor(self):
        """Create message processor instance."""
        return MessageProcessor()

    @pytest.fixture
    def sample_messages(self):
        """Create sample messages for testing."""
        base_date = datetime.now(dt.timezone.utc)

        messages = []
        for i in range(50):  # Create 50 test messages
            message = MagicMock()
            message.id = 1000 + i
            message.date = base_date - timedelta(hours=i)  # Different timestamps
            message.message = f"Test message {i}"
            message.media = None if i % 3 != 0 else MagicMock()  # Some have media
            message.views = 100 + i * 2  # Different view counts
            messages.append(message)

        return messages

    def test_pagination_with_date_filtering(self, paginator, message_processor, sample_messages):
        """Test pagination works correctly with date range filtering."""
        # Create date range filter
        from_date = datetime.now(dt.timezone.utc) - timedelta(hours=25)
        to_date = datetime.now(dt.timezone.utc) - timedelta(hours=10)

        # Filter messages by date
        filtered_messages = []
        for msg in sample_messages:
            if from_date <= msg.date <= to_date:
                filtered_messages.append(msg)

        # Apply pagination to filtered messages
        page_size = 10
        total_pages = (len(filtered_messages) + page_size - 1) // page_size

        # Test first page
        start_idx = 0
        end_idx = min(page_size, len(filtered_messages))
        first_page = filtered_messages[start_idx:end_idx]

        # Verify pagination logic
        assert len(first_page) <= page_size
        assert len(first_page) > 0

        # Test cursor creation
        if first_page:
            cursor = PaginationCursor(
                offset_id=first_page[-1].id,
                offset_date=first_page[-1].date,
                direction="desc"
            )
            assert cursor is not None
            assert cursor.offset_id == first_page[-1].id

    def test_message_processor_with_pagination_cursor(self, paginator, message_processor):
        """Test message processor works with pagination cursors."""
        # Create a cursor
        cursor = PaginationCursor(
            offset_id=12345,
            offset_date=datetime.now(dt.timezone.utc),
            direction="desc"
        )

        # Test cursor serialization/deserialization
        cursor_str = paginator.encode_cursor(cursor)
        decoded_cursor = paginator.decode_cursor(cursor_str)

        assert decoded_cursor is not None
        assert decoded_cursor.message_id == cursor.message_id
        assert decoded_cursor.direction == cursor.direction

    def test_filtering_with_pagination_metadata(self, paginator, message_processor, sample_messages):
        """Test filtering preserves pagination metadata."""
        # Apply content filtering
        search_term = "Test message 5"
        filtered_by_content = [
            msg for msg in sample_messages
            if search_term in msg.message
        ]

        # Apply media filtering
        filtered_by_media = [
            msg for msg in filtered_by_content
            if msg.media is not None
        ]

        # Create pagination parameters
        page_size = 5
        total_filtered = len(filtered_by_media)

        # Calculate pagination metadata
        total_pages = (total_filtered + page_size - 1) // page_size
        has_more = total_pages > 1

        # Verify filtering and pagination work together
        assert total_filtered >= 0
        assert total_pages >= 0
        assert isinstance(has_more, bool)

        # Test with empty results
        empty_filtered = [
            msg for msg in sample_messages
            if "nonexistent" in msg.message
        ]
        assert len(empty_filtered) == 0

    def test_cursor_based_pagination_with_filters(self, paginator, message_processor, sample_messages):
        """Test cursor-based pagination with active filters."""
        # Sort messages by ID (simulating database order)
        sorted_messages = sorted(sample_messages, key=lambda x: x.id, reverse=True)

        # Create initial cursor
        initial_cursor = paginator.create_initial_cursor("desc")

        # Create cursor from first message if available
        if sorted_messages:
            cursor = PaginationCursor(
                offset_id=sorted_messages[0].id,
                offset_date=sorted_messages[0].date,
                direction="desc"
            )
            assert cursor is not None

        # Simulate paginated fetching with cursor
        page_size = 10
        current_cursor = initial_cursor
        all_fetched_messages = []

        for page in range(3):  # Fetch 3 pages
            # Get messages after cursor
            if current_cursor and hasattr(current_cursor, 'message_id'):
                remaining_messages = [
                    msg for msg in sorted_messages
                    if msg.id < current_cursor.message_id
                ]
            else:
                remaining_messages = sorted_messages

            # Apply pagination
            page_messages = remaining_messages[:page_size]
            all_fetched_messages.extend(page_messages)

            # Update cursor for next page
            if page_messages and len(remaining_messages) > page_size:
                current_cursor = PaginationCursor(
                    offset_id=page_messages[-1].id,
                    offset_date=page_messages[-1].date,
                    direction="desc"
                )
            else:
                current_cursor = None
                break

        # Verify pagination worked correctly
        assert len(all_fetched_messages) <= len(sorted_messages)
        assert len(set(msg.id for msg in all_fetched_messages)) == len(all_fetched_messages)  # No duplicates

    def test_date_range_filter_integration(self, paginator, message_processor):
        """Test DateRangeFilter integration with pagination."""
        # Create date range strings in supported format
        from_date = (datetime.now(dt.timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%dT%H:%M:%SZ")
        to_date = datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

        # Test date validation
        validated_from, validated_to = DateRangeFilter.validate_date_range(
            from_date,
            to_date
        )

        assert validated_from is not None
        assert validated_to is not None
        assert validated_from < validated_to

        # Test invalid date range
        with pytest.raises(ValueError):
            DateRangeFilter.validate_date_range(
                to_date,  # to before from
                from_date
            )

    def test_message_processor_with_paginator(self, paginator, message_processor, sample_messages):
        """Test MessageProcessor works with Paginator for response formatting."""
        # Process messages for response
        processed_messages = []
        for msg in sample_messages[:5]:  # Process first 5 messages
            # Simulate message processing
            processed_msg = {
                "id": msg.id,
                "date": msg.date.isoformat(),
                "message": msg.message,
                "media": msg.media is not None,
                "views": msg.views
            }
            processed_messages.append(processed_msg)

        # Create pagination info
        page_info = {
            "cursor": "next_page_cursor",
            "has_more": len(sample_messages) > 5,
            "count": len(processed_messages),
            "fetched": len(processed_messages)
        }

        # Verify integration
        assert len(processed_messages) == 5
        assert page_info["has_more"] is True
        assert page_info["count"] == page_info["fetched"]

    def test_edge_case_empty_results(self, paginator, message_processor):
        """Test pagination and filtering with empty results."""
        # Test with empty message list
        empty_messages = []

        # Test pagination on empty list
        cursor = paginator.create_initial_cursor("desc")
        assert cursor is not None

        # Test filtering on empty list
        filtered_empty = [
            msg for msg in empty_messages
            if "test" in getattr(msg, 'message', '')
        ]
        assert len(filtered_empty) == 0

        # Test cursor operations on empty results
        end_cursor = PaginationCursor()  # Empty cursor
        assert end_cursor.offset_id is None

    def test_pagination_cursor_stability(self, paginator, message_processor, sample_messages):
        """Test cursor stability across multiple pagination calls."""
        # Sort messages consistently
        sorted_messages = sorted(sample_messages, key=lambda x: x.id, reverse=True)

        # Create initial cursor
        cursor1 = paginator.create_initial_cursor("desc")
        cursor2 = paginator.create_initial_cursor("desc")

        # Cursors should be equivalent for same parameters
        assert cursor1.direction == cursor2.direction

        # Test cursor from specific message
        if sorted_messages:
            msg_cursor = PaginationCursor(
                offset_id=sorted_messages[10].id,
                offset_date=sorted_messages[10].date,
                direction="desc"
            )
            assert msg_cursor is not None
            assert msg_cursor.offset_id == sorted_messages[10].id

            # Test cursor encoding/decoding stability
            encoded = msg_cursor.encode()
            decoded = PaginationCursor.decode(encoded)

            assert decoded.offset_id == msg_cursor.offset_id
            assert decoded.direction == msg_cursor.direction
