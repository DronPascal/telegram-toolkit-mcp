"""
MCP Tool: tg.fetch_history

Fetch message history from Telegram chats with basic pagination and filtering.

This tool provides read-only access to message history from public Telegram
chats with support for date ranges, pagination, and basic content filtering.
"""

from datetime import datetime
from typing import Any

try:
    from mcp.server import Tool
    from mcp.server.fastmcp import Context
except ImportError:
    # Fallback for development
    class Tool:
        def __init__(self, **kwargs):
            pass

        def __call__(self, func):
            return func

    Context = None

from ..core.error_handler import (
    ChannelPrivateException,
    ChatNotFoundException,
    FloodWaitException,
    ValidationException,
    create_success_response,
    get_error_tracker,
)
from ..core.filtering import DateRangeFilter, get_message_processor
from ..core.monitoring import (
    MetricsTimer,
    record_messages_fetched,
    record_ndjson_export,
    record_page_served,
)
from ..core.ndjson_resources import get_resource_manager
from ..core.pagination import Paginator
from ..core.telegram_client import TelegramClientWrapper
from ..core.tracing import (
    add_span_attribute,
    add_span_event,
    trace_mcp_tool_call,
    trace_resource_operation,
    trace_telegram_api_call,
)
from ..models.types import ExportInfo, MessageInfo, PageInfo
from ..utils.logging import get_logger
from ..utils.security import InputValidator, get_rate_limiter, get_security_auditor

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
    def validate_date_range(
        from_date: str | None, to_date: str | None
    ) -> tuple[datetime | None, datetime | None]:
        """
        Validate and parse date range parameters.

        Args:
            from_date: Start date in ISO format (optional)
            to_date: End date in ISO format (optional)

        Returns:
            Tuple of (from_datetime, to_datetime)

        Raises:
            ValidationException: If date range is invalid
        """
        try:
            return DateRangeFilter.validate_date_range(from_date, to_date)
        except ValueError as e:
            raise ValidationException(
                field="date_range", value=f"{from_date} to {to_date}", reason=str(e)
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
                field="page_size", value=page_size, reason="page_size must be positive"
            )

        if page_size > MessageHistoryFetcher.MAX_PAGE_SIZE:
            logger.warning(
                "Page size too large, limiting to maximum",
                requested=page_size,
                max_allowed=MessageHistoryFetcher.MAX_PAGE_SIZE,
            )
            return MessageHistoryFetcher.MAX_PAGE_SIZE

        return page_size

    @staticmethod
    def format_messages_for_response(
        messages: list[dict], page_size: int, has_more: bool = False
    ) -> dict:
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
                if "date" in msg and isinstance(msg["date"], (int, float)):
                    msg["date"] = datetime.fromtimestamp(msg["date"])

                # Create MessageInfo object
                message_obj = MessageInfo(**msg)
                message_objects.append(message_obj.model_dump())
            except Exception as e:
                logger.warning(
                    "Failed to convert message to MessageInfo",
                    message_id=msg.get("id"),
                    error=str(e),
                )
                # Keep original format if conversion fails
                message_objects.append(msg)

        # Create page info
        page_info = PageInfo(
            cursor=f"after:{messages[-1]['id']}" if messages else "end",
            has_more=has_more,
            count=len(messages),
            fetched=len(messages),
        )

        return {
            "messages": message_objects,
            "page_info": page_info.model_dump(),
            "export": None,  # Will be implemented with NDJSON resources
        }


@Tool(
    name="tg.fetch_history",
    description="Fetch message history from Telegram chats with cursor-based pagination",
    inputSchema={
        "type": "object",
        "required": ["chat"],
        "properties": {
            "chat": {
                "type": "string",
                "description": "Chat identifier (@username, t.me URL, or numeric ID)",
            },
            "from": {
                "type": "string",
                "format": "date-time",
                "description": "Start date for message range (ISO 8601)",
            },
            "to": {
                "type": "string",
                "format": "date-time",
                "description": "End date for message range (ISO 8601)",
            },
            "page_size": {
                "type": "integer",
                "minimum": 1,
                "maximum": 100,
                "default": 50,
                "description": "Number of messages per page",
            },
            "cursor": {"type": "string", "description": "Base64-encoded cursor for pagination"},
            "direction": {
                "type": "string",
                "enum": ["asc", "desc"],
                "default": "desc",
                "description": "Sort direction: 'asc' for oldest first, 'desc' for newest first",
            },
            "search": {
                "type": "string",
                "description": "Search query to filter messages by text content",
            },
            "filter": {
                "type": "object",
                "description": "Advanced filtering options",
                "properties": {
                    "media_types": {
                        "type": "array",
                        "items": {
                            "type": "string",
                            "enum": [
                                "text",
                                "photo",
                                "video",
                                "document",
                                "audio",
                                "voice",
                                "sticker",
                                "link",
                                "poll",
                            ],
                        },
                        "description": "Filter by media types",
                    },
                    "has_media": {
                        "type": "boolean",
                        "description": "Filter messages with/without media attachments",
                    },
                    "from_users": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Filter by sender user IDs",
                    },
                    "min_views": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Minimum view count for messages",
                    },
                    "max_views": {
                        "type": "integer",
                        "minimum": 0,
                        "description": "Maximum view count for messages",
                    },
                },
                "additionalProperties": False,
            },
        },
        "additionalProperties": False,
    },
)
async def fetch_history_tool(
    chat: str,
    from_date: str | None = None,
    to_date: str | None = None,
    page_size: int = 50,
    cursor: str | None = None,
    direction: str = "desc",
    search: str | None = None,
    filter: dict[str, Any] | None = None,
    ctx: Context = None,
) -> dict:
    """
    MCP Tool: Fetch message history from Telegram chats with advanced filtering.

    This tool retrieves message history from public Telegram chats
    with support for date filtering, cursor-based pagination, text search,
    and advanced content filtering.

    Args:
        chat: Chat identifier (@username, t.me URL, or numeric ID)
        from_date: Start date for message range (ISO 8601)
        to_date: End date for message range (ISO 8601)
        page_size: Number of messages per page (max 100)
        cursor: Base64-encoded cursor for pagination
        direction: Sort direction ("asc" or "desc")
        search: Search query to filter messages by text content
        filter: Advanced filtering options (media types, users, views, etc.)
        ctx: MCP context (optional)

    Returns:
        Dict containing messages and pagination info
    """
    # Prepare arguments for tracing
    trace_args = {
        "chat": chat,
        "from_date": from_date,
        "to_date": to_date,
        "page_size": page_size,
        "cursor": cursor,
        "direction": direction,
        "search": search,
        "filter": filter,
    }

    # Start tracing for the MCP tool call
    async with trace_mcp_tool_call("tg.fetch_history", trace_args):
        # Add span attributes
        add_span_attribute("chat.identifier", chat)
        add_span_attribute("page_size", page_size)
        add_span_attribute("has_cursor", cursor is not None)
        add_span_attribute("has_search", search is not None)
        add_span_attribute("has_filter", filter is not None)
        add_span_attribute("direction", direction)
        add_span_event("tool_started", {"tool": "tg.fetch_history"})

        # Start metrics timer for the tool execution
        with MetricsTimer("tool", "tg.fetch_history") as timer:
            try:
                # Rate limiting check
                rate_limiter = get_rate_limiter()
                allowed, wait_time = await rate_limiter.check_rate_limit(f"fetch_history:{chat}")

                if not allowed:
                    get_security_auditor().log_security_event(
                        "rate_limit_exceeded",
                        {"tool": "tg.fetch_history", "chat": chat, "wait_time": wait_time},
                    )
                    return {
                        "isError": True,
                        "error": {
                            "type": "RATE_LIMIT_EXCEEDED",
                            "title": "Rate limit exceeded",
                            "status": 429,
                            "detail": f"Too many requests. Please wait {wait_time:.1f} seconds.",
                        },
                        "content": [
                            {
                                "type": "text",
                                "text": f"Rate limit exceeded. Please wait {wait_time:.1f} seconds before retrying.",
                            }
                        ],
                    }

                # Input validation and sanitization
                try:
                    chat = InputValidator.sanitize_chat_identifier(chat)
                    page_size = InputValidator.validate_page_size(page_size)
                    InputValidator.validate_date_range(from_date, to_date)

                    if search:
                        search = InputValidator.sanitize_search_query(search)

                    if cursor:
                        # Basic cursor format validation
                        import base64

                        try:
                            base64.b64decode(cursor)
                        except Exception:
                            raise ValueError("Invalid cursor format")

                except ValueError as e:
                    get_security_auditor().log_security_event(
                        "input_validation_failed",
                        {
                            "tool": "tg.fetch_history",
                            "input": {"chat": chat, "page_size": page_size, "search": search},
                            "error": str(e),
                        },
                    )
                    return {
                        "isError": True,
                        "error": {
                            "type": "INPUT_VALIDATION_ERROR",
                            "title": "Input validation failed",
                            "status": 400,
                            "detail": str(e),
                        },
                        "content": [{"type": "text", "text": f"Invalid input: {e}"}],
                    }

                logger.info(
                    "Fetching message history",
                    chat=chat,
                    from_date=from_date,
                    to_date=to_date,
                    page_size=page_size,
                    cursor=cursor,
                    direction=direction,
                    search=search,
                    filter=filter,
                )

                # Validate inputs and parse dates
                from_dt, to_dt = MessageHistoryFetcher.validate_date_range(from_date, to_date)

                # Initialize paginator
                paginator = Paginator(chat)

                # Validate page size
                validated_page_size = paginator.validate_page_size(page_size)

                # Decode cursor if provided
                current_cursor = paginator.decode_cursor(cursor)
                if current_cursor and current_cursor.direction != direction:
                    logger.warning(
                        "Cursor direction mismatch, using cursor direction",
                        cursor_direction=current_cursor.direction,
                        requested_direction=direction,
                    )
                    direction = current_cursor.direction

                # Get MCP server from context to access Telegram client
                if ctx is None:
                    raise RuntimeError("MCP context not available")

                server_state = getattr(ctx, "_server_state", None)
                if server_state is None:
                    raise RuntimeError("Server state not available in context")

                telegram_client = getattr(server_state, "telegram_client", None)
                if telegram_client is None:
                    raise RuntimeError("Telegram client not available")

                # Wrap client for high-level operations
                client_wrapper = TelegramClientWrapper(telegram_client)

                # Get pagination parameters
                if current_cursor is None:
                    current_cursor = paginator.create_initial_cursor(direction)

                pagination_params = paginator.get_pagination_params(
                    current_cursor, validated_page_size, direction
                )

                # Add search if provided
                if search:
                    pagination_params["search"] = search

                # Add initial date filtering if no cursor and dates provided
                if not cursor:  # Only for first page
                    if from_date:
                        from_dt = datetime.fromisoformat(from_date.replace("Z", "+00:00"))
                        if "offset_date" not in pagination_params:
                            pagination_params["offset_date"] = from_dt

                # Fetch messages with automatic FLOOD_WAIT handling
                try:
                    with client_wrapper.session_context() as client:
                        # Trace Telegram API call
                        async with trace_telegram_api_call("fetch_messages", pagination_params):
                            add_span_attribute("telegram.chat", chat)
                            add_span_attribute("telegram.limit", pagination_params.get("limit", 0))
                            add_span_attribute(
                                "telegram.offset_id", pagination_params.get("offset_id", 0)
                            )
                            add_span_event(
                                "telegram_api_call_started", {"method": "fetch_messages"}
                            )
                            messages = await client.fetch_messages(chat, **pagination_params)
                            add_span_event(
                                "telegram_api_call_completed",
                                {
                                    "success": True,
                                    "messages_count": len(messages) if messages else 0,
                                },
                            )
                except FloodWaitException as e:
                    add_span_event(
                        "telegram_api_call_failed",
                        {"error": "FLOOD_WAIT", "retry_after": e.retry_after},
                    )
                    logger.warning(
                        "FLOOD_WAIT encountered during message fetch",
                        chat=chat,
                        retry_after=e.retry_after,
                        error=str(e),
                    )
                    get_error_tracker().track_error(
                        e, {"tool": "tg.fetch_history", "chat": chat, "operation": "fetch_messages"}
                    )
                    return {
                        "isError": True,
                        "error": e.to_dict(),
                        "content": [
                            {
                                "type": "text",
                                "text": f"Rate limit exceeded. Please wait {e.retry_after} seconds before retrying.",
                            }
                        ],
                    }

                # Apply server-side filtering and processing
                processor = get_message_processor()

                # Extract filter parameters
                media_types = filter.get("media_types") if filter else None
                has_media = filter.get("has_media") if filter else None
                from_users = filter.get("from_users") if filter else None
                min_views = filter.get("min_views") if filter else None
                max_views = filter.get("max_views") if filter else None

                messages = processor.process_messages(
                    messages,
                    from_date=from_date,
                    to_date=to_date,
                    search_query=search,
                    media_types=media_types,
                    sender_ids=from_users,
                    deduplicate=True,
                )

                # Apply additional filters that aren't handled by the processor
                if has_media is not None:
                    if has_media:
                        messages = [msg for msg in messages if msg.get("has_media", False)]
                    else:
                        messages = [msg for msg in messages if not msg.get("has_media", False)]

                if min_views is not None:
                    messages = [msg for msg in messages if (msg.get("views") or 0) >= min_views]

                if max_views is not None:
                    messages = [msg for msg in messages if (msg.get("views") or 0) <= max_views]

                logger.debug(
                    "Applied advanced filters",
                    total_filters={
                        "date_range": bool(from_date or to_date),
                        "search": bool(search),
                        "media_types": bool(media_types),
                        "has_media": has_media is not None,
                        "from_users": bool(from_users),
                        "views_range": bool(min_views is not None or max_views is not None),
                    },
                )

                # Determine if there are more messages
                has_more = paginator.should_continue_pagination(
                    messages, validated_page_size, current_cursor.fetched_count + len(messages)
                )

                # Create next cursor if there are more messages
                next_cursor = None
                if has_more and messages:
                    next_cursor = current_cursor.get_next_cursor(messages[-1])
                    next_cursor.fetched_count = current_cursor.fetched_count + len(messages)

                # Create NDJSON resource for large datasets if needed
                export_info = None
                if len(messages) > 100:  # Threshold for creating resource
                    try:
                        # Trace resource creation
                        async with trace_resource_operation("create", "ndjson_export"):
                            add_span_attribute("resource.messages_count", len(messages))
                            add_span_attribute("resource.chat", chat)
                            add_span_event(
                                "resource_creation_started",
                                {"operation": "create_ndjson", "messages_count": len(messages)},
                            )

                            resource_manager = get_resource_manager()
                            resource_info = await resource_manager.create_ndjson_resource(
                                messages,
                                metadata={
                                    "chat": chat,
                                    "from_date": from_date,
                                    "to_date": to_date,
                                    "direction": direction,
                                    "search": search,
                                },
                            )

                            add_span_event(
                                "resource_creation_completed",
                                {
                                    "success": True,
                                    "resource_id": resource_info.get("resource_id", "unknown"),
                                },
                            )
                        export_info = ExportInfo(
                            uri=resource_info["uri"], format="ndjson"
                        ).model_dump()

                        # Record NDJSON export metrics
                        record_ndjson_export("success")

                        logger.info(
                            "NDJSON resource created for large dataset",
                            resource_id=resource_info["resource_id"],
                            item_count=len(messages),
                        )

                    except Exception as e:
                        add_span_event(
                            "resource_creation_failed",
                            {"error": str(e), "messages_count": len(messages)},
                        )
                        logger.warning(
                            "Failed to create NDJSON resource, using inline data", error=str(e)
                        )
                        record_ndjson_export("error")

                # Format response
                response_data = MessageHistoryFetcher.format_messages_for_response(
                    messages, validated_page_size, has_more
                )

                # Update page info with cursor
                if next_cursor:
                    response_data["page_info"]["cursor"] = next_cursor.encode()
                else:
                    response_data["page_info"]["cursor"] = None

                # Add export info if available
                if export_info:
                    response_data["export"] = export_info

                # Record metrics for successful operation
                has_filters = bool(
                    search
                    or media_types
                    or from_users
                    or min_views is not None
                    or max_views is not None
                    or from_date
                    or to_date
                )
                record_messages_fetched("tg.fetch_history", len(messages), has_filters)
                record_page_served("tg.fetch_history", direction)

                logger.info(
                    "Message history fetched successfully",
                    chat=chat,
                    message_count=len(messages),
                    has_more=has_more,
                    total_fetched=current_cursor.fetched_count + len(messages),
                    cursor_provided=bool(cursor),
                    direction=direction,
                    filters_applied={
                        "search": bool(search),
                        "media_types": bool(media_types),
                        "from_users": bool(from_users),
                        "views_filter": bool(min_views is not None or max_views is not None),
                        "date_range": bool(from_date or to_date),
                    },
                )

                # Create MCP-compliant response
                status_text = f"Fetched {len(messages)} messages from {chat}"
                if has_more:
                    status_text += f" (cursor: {next_cursor.encode() if next_cursor else 'end'})"
                else:
                    status_text += " (end of results)"

                return create_success_response(
                    content=[{"type": "text", "text": status_text}],
                    structured_content=response_data,
                )

            except ValidationException as e:
                logger.warning("Input validation failed", error=e.message, chat=chat)
                get_error_tracker().track_error(e, {"tool": "tg.fetch_history", "chat": chat})
                return {
                    "isError": True,
                    "error": e.to_dict(),
                    "content": [{"type": "text", "text": f"Invalid input: {e.message}"}],
                }

            except ChatNotFoundException as e:
                logger.warning("Chat not found", chat=chat, error=e.message)
                get_error_tracker().track_error(e, {"tool": "tg.fetch_history", "chat": chat})
                return {
                    "isError": True,
                    "error": e.to_dict(),
                    "content": [{"type": "text", "text": f"Chat not found: {e.message}"}],
                }

            except ChannelPrivateException as e:
                logger.warning("Channel is private", chat=chat, error=e.message)
                get_error_tracker().track_error(e, {"tool": "tg.fetch_history", "chat": chat})
                return {
                    "isError": True,
                    "error": e.to_dict(),
                    "content": [{"type": "text", "text": f"Channel is private: {e.message}"}],
                }

            except FloodWaitException as e:
                logger.warning("FLOOD_WAIT in fetch_history", chat=chat, retry_after=e.retry_after)
                get_error_tracker().track_error(e, {"tool": "tg.fetch_history", "chat": chat})
                return {
                    "isError": True,
                    "error": e.to_dict(),
                    "content": [{"type": "text", "text": f"Rate limit exceeded: {e.message}"}],
                }

            except Exception as e:
                logger.error(
                    "Unexpected error in fetch_history",
                    error=str(e),
                    chat=chat,
                    from_date=from_date,
                    to_date=to_date,
                )
                get_error_tracker().track_error(
                    e,
                    {
                        "tool": "tg.fetch_history",
                        "chat": chat,
                        "from_date": from_date,
                        "to_date": to_date,
                    },
                )
                return {
                    "isError": True,
                    "error": {"code": "INTERNAL_ERROR", "message": f"Internal error: {str(e)}"},
                    "content": [{"type": "text", "text": f"Internal error occurred: {str(e)}"}],
                }


# Export the tool function for registration
__all__ = ["fetch_history_tool", "MessageHistoryFetcher"]
