"""
MCP Tool: tg.resolve_chat

Resolves chat identifiers to standardized format for Telegram Toolkit MCP.

This tool accepts various chat identifier formats (@username, t.me URLs, numeric IDs)
and returns standardized chat information for use by other MCP tools.
"""

import re
from typing import Dict, Union

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
    FloodWaitException,
    error_handler,
    create_success_response,
    get_error_tracker
)
from ..models.types import ResolveChatResponse
from ..core.monitoring import record_tool_success, record_tool_error, MetricsTimer
from ..core.tracing import trace_mcp_tool_call, trace_telegram_api_call, add_span_attribute, add_span_event
from ..utils.security import get_rate_limiter, InputValidator, get_security_auditor
from ..utils.logging import get_logger

logger = get_logger(__name__)


class ChatResolver:
    """
    Chat identifier resolver for MCP tools.

    Handles various chat identifier formats and provides
    standardized chat information.
    """

    # Regex patterns for different identifier formats
    USERNAME_PATTERN = re.compile(r'^@([a-zA-Z0-9_]{5,32})$')
    TELEGRAM_URL_PATTERN = re.compile(r'^https?://t\.me/([a-zA-Z0-9_]{5,32})(?:/.*)?$')
    NUMERIC_ID_PATTERN = re.compile(r'^-?\d+$')

    @staticmethod
    def validate_chat_identifier(identifier: str) -> bool:
        """
        Validate chat identifier format.

        Args:
            identifier: Chat identifier to validate

        Returns:
            bool: True if identifier format is valid
        """
        if not identifier or not isinstance(identifier, str):
            return False

        identifier = identifier.strip()

        # Check against all patterns
        return (
            ChatResolver.USERNAME_PATTERN.match(identifier) is not None or
            ChatResolver.TELEGRAM_URL_PATTERN.match(identifier) is not None or
            ChatResolver.NUMERIC_ID_PATTERN.match(identifier) is not None
        )

    @staticmethod
    def parse_chat_identifier(identifier: str) -> Dict[str, str]:
        """
        Parse chat identifier into components.

        Args:
            identifier: Chat identifier to parse

        Returns:
            Dict containing parsed components:
            - 'type': 'username', 'url', or 'numeric'
            - 'value': The actual identifier value
            - 'canonical': Canonical form for API calls
        """
        identifier = identifier.strip()

        # Check username format
        username_match = ChatResolver.USERNAME_PATTERN.match(identifier)
        if username_match:
            username = username_match.group(1)
            return {
                'type': 'username',
                'value': username,
                'canonical': f"@{username}"
            }

        # Check URL format
        url_match = ChatResolver.TELEGRAM_URL_PATTERN.match(identifier)
        if url_match:
            username = url_match.group(1)
            return {
                'type': 'url',
                'value': username,
                'canonical': f"@{username}"
            }

        # Check numeric format
        if ChatResolver.NUMERIC_ID_PATTERN.match(identifier):
            return {
                'type': 'numeric',
                'value': identifier,
                'canonical': identifier
            }

        # Fallback (should not happen if validated)
        return {
            'type': 'unknown',
            'value': identifier,
            'canonical': identifier
        }


@Tool(
    name="tg.resolve_chat",
    description="Resolve chat identifiers to standardized format",
    inputSchema={
        "type": "object",
        "required": ["input"],
        "properties": {
            "input": {
                "type": "string",
                "description": "Chat identifier (@username, t.me URL, or numeric ID)",
                "examples": ["@telegram", "https://t.me/telegram", "136817688"]
            }
        },
        "additionalProperties": False
    }
)
async def resolve_chat_tool(
    input: str,
    ctx: Context = None
) -> Dict:
    """
    MCP Tool: Resolve chat identifier to standardized format.

    This tool takes various chat identifier formats and resolves them
    to a standardized format with chat information.

    Args:
        input: Chat identifier (@username, t.me URL, or numeric ID)
        ctx: MCP context (optional)

    Returns:
        Dict containing resolved chat information
    """
    # Start tracing for the MCP tool call
    async with trace_mcp_tool_call("tg.resolve_chat", {"input": input}):
        # Add span attributes
        add_span_attribute("chat.input", input)
        add_span_event("tool_started", {"tool": "tg.resolve_chat"})

        # Start metrics timer for the tool execution
        with MetricsTimer('tool', 'tg.resolve_chat') as timer:
            try:
            # Rate limiting check
            rate_limiter = get_rate_limiter()
            allowed, wait_time = await rate_limiter.check_rate_limit(f"resolve_chat:{input}")

            if not allowed:
                get_security_auditor().log_security_event(
                    "rate_limit_exceeded",
                    {
                        "tool": "tg.resolve_chat",
                        "input": input,
                        "wait_time": wait_time
                    }
                )
                return {
                    "isError": True,
                    "error": {
                        "type": "RATE_LIMIT_EXCEEDED",
                        "title": "Rate limit exceeded",
                        "status": 429,
                        "detail": f"Too many requests. Please wait {wait_time:.1f} seconds."
                    },
                    "content": [
                        {
                            "type": "text",
                            "text": f"Rate limit exceeded. Please wait {wait_time:.1f} seconds before retrying."
                        }
                    ]
                }

            # Input validation and sanitization
            try:
                input = InputValidator.sanitize_chat_identifier(input)
            except ValueError as e:
                get_security_auditor().log_security_event(
                    "input_validation_failed",
                    {
                        "tool": "tg.resolve_chat",
                        "input": input,
                        "error": str(e)
                    }
                )
                return {
                    "isError": True,
                    "error": {
                        "type": "INPUT_VALIDATION_ERROR",
                        "title": "Input validation failed",
                        "status": 400,
                        "detail": str(e)
                    },
                    "content": [
                        {
                            "type": "text",
                            "text": f"Invalid input: {e}"
                        }
                    ]
                }

            logger.info("Resolving chat identifier", input=input)

        # Validate input
        if not input or not isinstance(input, str):
            raise ValidationException(
                field="input",
                value=input,
                reason="Input must be a non-empty string"
            )

        # Validate identifier format
        if not ChatResolver.validate_chat_identifier(input):
            raise ValidationException(
                field="input",
                value=input,
                reason="Invalid chat identifier format. Use @username, t.me URL, or numeric ID"
            )

        # Parse identifier
        parsed = ChatResolver.parse_chat_identifier(input)
        logger.info("Parsed identifier", parsed=parsed)

        # Get MCP server from context to access Telegram client
        if ctx is None:
            raise RuntimeError("MCP context not available")

        # Access Telegram client through server state
        # This will be injected by the server during tool registration
        server_state = getattr(ctx, '_server_state', None)
        if server_state is None:
            raise RuntimeError("Server state not available in context")

        telegram_client = getattr(server_state, 'telegram_client', None)
        if telegram_client is None:
            raise RuntimeError("Telegram client not available")

        # Wrap client for high-level operations
        client_wrapper = TelegramClientWrapper(telegram_client)

        # Get chat information with FLOOD_WAIT handling
        try:
            with client_wrapper.session_context() as client:
                # Trace Telegram API call
                async with trace_telegram_api_call("get_chat_info", {"chat": parsed['canonical']}):
                    add_span_attribute("telegram.chat.canonical", parsed['canonical'])
                    add_span_event("telegram_api_call_started", {"method": "get_chat_info"})
                    chat_info = await client.get_chat_info(parsed['canonical'])
                    add_span_event("telegram_api_call_completed", {"success": True})
        except FloodWaitException as e:
            add_span_event("telegram_api_call_failed", {"error": "FLOOD_WAIT", "retry_after": e.retry_after})
            logger.warning(
                "FLOOD_WAIT encountered during chat resolution",
                input=input,
                retry_after=e.retry_after,
                error=str(e)
            )
            get_error_tracker().track_error(e, {
                "tool": "tg.resolve_chat",
                "input": input,
                "operation": "get_chat_info"
            })
            return {
                "isError": True,
                "error": e.to_dict(),
                "content": [
                    {
                        "type": "text",
                        "text": f"Rate limit exceeded. Please wait {e.retry_after} seconds before retrying."
                    }
                ]
            }

        # Prepare response
        response_data = {
            "chat_id": str(chat_info['id']),
            "kind": chat_info['type'],
            "title": chat_info['title'],
            "username": chat_info.get('username'),
            "member_count": chat_info.get('participants_count'),
            "verified": chat_info.get('verified', False),
            "resolved_from": {
                "input": input,
                "type": parsed['type'],
                "canonical": parsed['canonical']
            }
        }

        # Record successful tool execution
        record_tool_success("tg.resolve_chat", chat_type=response_data['kind'])

        logger.info(
            "Chat resolved successfully",
            chat_id=response_data['chat_id'],
            kind=response_data['kind'],
            title=response_data['title']
        )

        # Create MCP-compliant response
        return create_success_response(
            content=[
                {
                    "type": "text",
                    "text": f"Resolved chat: {response_data['title']} ({response_data['kind']})"
                }
            ],
            structured_content=response_data
        )

    except ValidationException as e:
        logger.warning("Input validation failed", error=e.message, input=input)
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
        logger.warning("Chat not found", chat=input, error=e.message)
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
        logger.warning("Channel is private", chat=input, error=e.message)
        get_error_tracker().track_error(e, {"tool": "tg.resolve_chat", "input": input})
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

    except FloodWaitException as e:
        logger.warning("FLOOD_WAIT in resolve_chat", input=input, retry_after=e.retry_after)
        get_error_tracker().track_error(e, {"tool": "tg.resolve_chat", "input": input})
        return {
            "isError": True,
            "error": e.to_dict(),
            "content": [
                {
                    "type": "text",
                    "text": f"Rate limit exceeded: {e.message}"
                }
            ]
        }

    except Exception as e:
        logger.error("Unexpected error in resolve_chat", error=str(e), input=input)
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
__all__ = ["resolve_chat_tool", "ChatResolver"]
