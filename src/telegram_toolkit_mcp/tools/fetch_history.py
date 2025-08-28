"""
MCP Tool: tg.fetch_history

Fetch message history from Telegram chats with basic pagination and filtering.

This tool provides read-only access to message history from public Telegram
chats with support for date ranges, pagination, and basic content filtering.
"""

from datetime import datetime
from typing import Dict, List, Optional

try:
    from mcp import Tool
    from mcp.server.fastmcp import Context
except ImportError:
    # Fallback for development
    Tool = lambda **kwargs: lambda func: func
    Context = None

from ..core.telegram_client import TelegramClientWrapper
from ..core.error_handler import (
    ChatNotFoundException,
    ChannelPrivateException,
    ValidationException,
    error_handler,
    create_success_response
)
from ..models.types import MessageInfo, PageInfo, ExportInfo
from ..utils.logging import get_logger

logger = get_logger(__name__)


class MessageHistoryFetcher:
    """
    Message history fetcher for MCP tools.

    Handles message retrieval with pagination, filtering, and
    MCP-compliant response formatting.
    """

    MAX_PAGE_SIZE = 100  # Maximum messages per page
    DEFAULT_PAGE_SIZE = 50  # Default messages per page

    @staticmethod
    def validate_date_range(from_date: Optional[str], to_date: Optional[str]) -> None:
        """
        Validate date range parameters.

        Args:
            from_date: Start date in ISO format (optional)
            to_date: End date in ISO format (optional)

        Raises:
            ValidationException: If date range is invalid
        """
        if from_date and to_date:
            try:
                from_dt = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
                to_dt = datetime.fromisoformat(to_date.replace('Z', '+00:00'))

                if from_dt >= to_dt:
                    raise ValidationException(
                        field="date_range",
                        value=f"{from_date} to {to_date}",
                        reason="from_date must be before to_date"
                    )
            except ValueError as e:
                raise ValidationException(
                    field="date_range",
                    value=f"{from_date} to {to_date}",
                    reason=f"Invalid date format: {e}"
                )

    @staticmethod
    def validate_page_size(page_size: int) -> int:
        """
        Validate and normalize page size.

        Args:
            page_size: Requested page size

        Returns:
            int: Validated page size

        Raises:
            ValidationException: If page size is invalid
        """
        if page_size < 1:
            raise ValidationException(
                field="page_size",
                value=page_size,
                reason="page_size must be positive"
            )

        if page_size > MessageHistoryFetcher.MAX_PAGE_SIZE:
            logger.warning(
                "Page size too large, limiting to maximum",
                requested=page_size,
                max_allowed=MessageHistoryFetcher.MAX_PAGE_SIZE
            )
            return MessageHistoryFetcher.MAX_PAGE_SIZE

        return page_size

    @staticmethod
    def format_messages_for_response(
        messages: List[Dict],
        page_size: int,
        has_more: bool = False
    ) -> Dict:
        """
        Format messages for MCP response.

        Args:
            messages: Raw message data
            page_size: Page size used
            has_more: Whether more messages are available

        Returns:
            Dict containing formatted response data
        """
        # Convert to MessageInfo objects for validation
        message_objects = []
        for msg in messages:
            try:
                # Convert timestamps
                if 'date' in msg and isinstance(msg['date'], (int, float)):
                    msg['date'] = datetime.fromtimestamp(msg['date'])

                # Create MessageInfo object
                message_obj = MessageInfo(**msg)
                message_objects.append(message_obj.model_dump())
            except Exception as e:
                logger.warning(
                    "Failed to convert message to MessageInfo",
                    message_id=msg.get('id'),
                    error=str(e)
                )
                # Keep original format if conversion fails
                message_objects.append(msg)

        # Create page info
        page_info = PageInfo(
            cursor=f"after:{messages[-1]['id']}" if messages else "end",
            has_more=has_more,
            count=len(messages),
            fetched=len(messages)
        )

        return {
            "messages": message_objects,
            "page_info": page_info.model_dump(),
            "export": None  # Will be implemented with NDJSON resources
        }


@Tool(
    name="tg.fetch_history",
    description="Fetch message history from Telegram chats",
    inputSchema={
        "type": "object",
        "required": ["chat"],
        "properties": {
            "chat": {
                "type": "string",
                "description": "Chat identifier (@username, t.me URL, or numeric ID)"
            },
            "from": {
                "type": "string",
                "format": "date-time",
                "description": "Start date for message range (ISO 8601)"
            },
            "to": {
                "type": "string",
                "format": "date-time",
                "description": "End date for message range (ISO 8601)"
            },
            "page_size": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "default": 50,
                "description": "Number of messages per page"
            },
            "search": {
                "type": "string",
                "description": "Search query to filter messages"
            }
        },
        "additionalProperties": False
    }
)
async def fetch_history_tool(
    chat: str,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    page_size: int = 50,
    search: Optional[str] = None,
    ctx: Context = None
) -> Dict:
    """
    MCP Tool: Fetch message history from Telegram chats.

    This tool retrieves message history from public Telegram chats
    with support for date filtering, pagination, and search.

    Args:
        chat: Chat identifier (@username, t.me URL, or numeric ID)
        from_date: Start date for message range (ISO 8601)
        to_date: End date for message range (ISO 8601)
        page_size: Number of messages per page (max 100)
        search: Search query to filter messages
        ctx: MCP context (optional)

    Returns:
        Dict containing messages and pagination info
    """
    try:
        logger.info(
            "Fetching message history",
            chat=chat,
            from_date=from_date,
            to_date=to_date,
            page_size=page_size,
            search=search
        )

        # Validate inputs
        MessageHistoryFetcher.validate_date_range(from_date, to_date)
        validated_page_size = MessageHistoryFetcher.validate_page_size(page_size)

        # Get MCP server from context to access Telegram client
        if ctx is None:
            raise RuntimeError("MCP context not available")

        server_state = getattr(ctx, '_server_state', None)
        if server_state is None:
            raise RuntimeError("Server state not available in context")

        telegram_client = getattr(server_state, 'telegram_client', None)
        if telegram_client is None:
            raise RuntimeError("Telegram client not available")

        # Wrap client for high-level operations
        client_wrapper = TelegramClientWrapper(telegram_client)

        # Prepare fetch parameters
        fetch_kwargs = {
            'limit': validated_page_size,
        }

        # Add date filtering
        if from_date:
            from_dt = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
            fetch_kwargs['offset_date'] = from_dt

        if to_date:
            # Note: Telethon doesn't directly support end date filtering
            # This will be handled in post-processing
            pass

        # Add search if provided
        if search:
            fetch_kwargs['search'] = search

        # Fetch messages
        with client_wrapper.session_context() as client:
            messages = await client.fetch_messages(chat, **fetch_kwargs)

        # Post-process messages (date filtering, etc.)
        if to_date:
            to_dt = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
            messages = [
                msg for msg in messages
                if msg.get('date') and datetime.fromtimestamp(msg['date']) <= to_dt
            ]

        # Check if there might be more messages
        has_more = len(messages) == validated_page_size

        # Format response
        response_data = MessageHistoryFetcher.format_messages_for_response(
            messages, validated_page_size, has_more
        )

        logger.info(
            "Message history fetched successfully",
            chat=chat,
            message_count=len(messages),
            has_more=has_more
        )

        # Create MCP-compliant response
        return create_success_response(
            content=[
                {
                    "type": "text",
                    "text": f"Fetched {len(messages)} messages from {chat}"
                }
            ],
            structured_content=response_data
        )

    except ValidationException as e:
        logger.warning("Input validation failed", error=e.message, chat=chat)
        return {
            "isError": True,
            "error": e.to_dict(),
            "content": [
                {
                    "type": "text",
                    "text": f"Invalid input: {e.message}"
                }
            ]
        }

    except ChatNotFoundException as e:
        logger.warning("Chat not found", chat=chat, error=e.message)
        return {
            "isError": True,
            "error": e.to_dict(),
            "content": [
                {
                    "type": "text",
                    "text": f"Chat not found: {e.message}"
                }
            ]
        }

    except ChannelPrivateException as e:
        logger.warning("Channel is private", chat=chat, error=e.message)
        return {
            "isError": True,
            "error": e.to_dict(),
            "content": [
                {
                    "type": "text",
                    "text": f"Channel is private: {e.message}"
                }
            ]
        }

    except Exception as e:
        logger.error(
            "Unexpected error in fetch_history",
            error=str(e),
            chat=chat,
            from_date=from_date,
            to_date=to_date
        )
        return {
            "isError": True,
            "error": {
                "code": "INTERNAL_ERROR",
                "message": f"Internal error: {str(e)}"
            },
            "content": [
                {
                    "type": "text",
                    "text": f"Internal error occurred: {str(e)}"
                }
            ]
        }


# Export the tool function for registration
__all__ = ["fetch_history_tool", "MessageHistoryFetcher"]
