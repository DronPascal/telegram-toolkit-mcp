"""
Telegram client wrapper for MCP server.

This module provides a high-level interface for interacting with Telegram
API through Telethon, with proper error handling and resource management.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from ..utils.logging import get_logger

logger = get_logger(__name__)


class TelegramClientWrapper:
    """
    Wrapper around Telethon client with MCP-specific functionality.

    This class provides a clean interface for Telegram operations
    with proper error handling and logging.
    """

    def __init__(self, client: Any = None):
        """
        Initialize the wrapper.

        Args:
            client: Telethon client instance (injected for testing)
        """
        self._client = client
        self._is_connected = False

    @property
    def client(self) -> Any:
        """Get the underlying Telethon client."""
        if self._client is None:
            raise RuntimeError("Telegram client not initialized")
        return self._client

    @property
    def is_connected(self) -> bool:
        """Check if client is connected and authorized."""
        return self._is_connected and self._client is not None

    async def connect(self, client: Any) -> None:
        """
        Connect to Telegram with the provided client.

        Args:
            client: Configured Telethon client instance
        """
        try:
            self._client = client

            # Check if already connected
            if hasattr(client, "is_connected") and client.is_connected():
                self._is_connected = True
                logger.info("Telegram client already connected")
                return

            # Connect to Telegram
            logger.info("Connecting to Telegram")
            await client.connect()
            self._is_connected = True

            logger.info("Successfully connected to Telegram")

        except Exception as e:
            logger.error("Failed to connect to Telegram", error=str(e))
            self._is_connected = False
            raise

    async def disconnect(self) -> None:
        """Disconnect from Telegram."""
        if self._client and self._is_connected:
            try:
                logger.info("Disconnecting from Telegram")
                await self._client.disconnect()
                self._is_connected = False
                logger.info("Successfully disconnected from Telegram")
            except Exception as e:
                logger.error("Error during disconnect", error=str(e))

    async def get_chat_info(self, chat_identifier: str) -> dict[str, Any]:
        """
        Get information about a chat/channel.

        Args:
            chat_identifier: Chat username, ID, or URL

        Returns:
            Dict containing chat information
        """
        try:
            logger.info("Getting chat info", chat=chat_identifier)

            # Resolve chat entity
            if chat_identifier.startswith("@"):
                chat_entity = await self.client.get_entity(chat_identifier)
            elif chat_identifier.startswith("https://t.me/"):
                username = chat_identifier.split("/")[-1]
                chat_entity = await self.client.get_entity(f"@{username}")
            else:
                # Try as numeric ID first, then as username
                try:
                    chat_id = int(chat_identifier)
                    chat_entity = await self.client.get_entity(chat_id)
                except ValueError:
                    chat_entity = await self.client.get_entity(chat_identifier)

            # Extract chat information
            chat_info = {
                "id": chat_entity.id,
                "title": getattr(chat_entity, "title", None)
                or getattr(chat_entity, "first_name", "Unknown"),
                "username": getattr(chat_entity, "username", None),
                "type": self._get_chat_type(chat_entity),
                "participants_count": getattr(chat_entity, "participants_count", None),
                "verified": getattr(chat_entity, "verified", False),
                "restricted": getattr(chat_entity, "restricted", False),
                "megagroup": getattr(chat_entity, "megagroup", False),
                "gigagroup": getattr(chat_entity, "gigagroup", False),
            }

            logger.info(
                "Chat info retrieved",
                chat=chat_identifier,
                chat_id=chat_info["id"],
                type=chat_info["type"],
            )

            return chat_info

        except Exception as e:
            logger.error("Failed to get chat info", chat=chat_identifier, error=str(e))
            raise

    def _get_chat_type(self, entity: Any) -> str:
        """
        Determine the type of chat entity.

        Args:
            entity: Telethon chat entity

        Returns:
            str: Chat type ('user', 'channel', 'supergroup', 'group')
        """
        entity_type = str(type(entity).__name__).lower()

        if "user" in entity_type:
            return "user"
        elif "channel" in entity_type:
            # Check if it's a broadcast channel or supergroup
            if hasattr(entity, "broadcast") and entity.broadcast:
                return "channel"
            elif hasattr(entity, "megagroup") and entity.megagroup:
                return "supergroup"
            else:
                return "channel"
        elif "chat" in entity_type:
            return "group"
        else:
            return "unknown"

    async def fetch_messages(
        self,
        chat_id: str | int,
        limit: int = 100,
        offset_id: int | None = None,
        offset_date: int | None = None,
        min_id: int | None = None,
        max_id: int | None = None,
        search: str | None = None,
        from_user: str | None = None,
        **kwargs,
    ) -> list[dict[str, Any]]:
        """
        Fetch messages from a chat with various filtering options.

        Args:
            chat_id: Chat identifier
            limit: Maximum number of messages to fetch
            offset_id: Offset message ID
            offset_date: Offset date (Unix timestamp)
            min_id: Minimum message ID
            max_id: Maximum message ID
            search: Search query
            from_user: Filter by specific user
            **kwargs: Additional Telethon parameters

        Returns:
            List of message dictionaries
        """
        try:
            logger.info(
                "Fetching messages", chat=chat_id, limit=limit, search=search, offset_id=offset_id
            )

            # Prepare fetch parameters
            fetch_kwargs = {
                "limit": limit,
                "offset_id": offset_id,
                "offset_date": offset_date,
                "min_id": min_id,
                "max_id": max_id,
                "search": search,
            }

            # Remove None values
            fetch_kwargs = {k: v for k, v in fetch_kwargs.items() if v is not None}

            # Add any additional kwargs
            fetch_kwargs.update(kwargs)

            # Fetch messages
            messages = []
            async for message in self.client.iter_messages(chat_id, **fetch_kwargs):
                message_dict = self._convert_message_to_dict(message)
                messages.append(message_dict)

                # Log progress for large fetches
                if len(messages) % 100 == 0:
                    logger.debug(f"Fetched {len(messages)} messages so far")

            logger.info(
                "Messages fetched successfully",
                chat=chat_id,
                count=len(messages),
                requested_limit=limit,
            )

            return messages

        except Exception as e:
            logger.error("Failed to fetch messages", chat=chat_id, error=str(e), limit=limit)
            raise

    def _convert_message_to_dict(self, message: Any) -> dict[str, Any]:
        """
        Convert a Telethon message object to a dictionary.

        Args:
            message: Telethon message object

        Returns:
            Dict containing message data
        """
        try:
            # Basic message info
            message_dict = {
                "id": message.id,
                "date": message.date.timestamp() if message.date else None,
                "text": message.text or "",
                "out": message.out,
                "mentioned": message.mentioned,
                "media_unread": message.media_unread,
                "silent": message.silent,
                "post": message.post,
                "from_scheduled": message.from_scheduled,
                "legacy": message.legacy,
                "edit_hide": message.edit_hide,
                "pinned": message.pinned,
                "noforwards": message.noforwards,
            }

            # Sender information
            if message.sender:
                message_dict["sender"] = {
                    "id": message.sender.id,
                    "first_name": getattr(message.sender, "first_name", None),
                    "last_name": getattr(message.sender, "last_name", None),
                    "username": getattr(message.sender, "username", None),
                    "bot": getattr(message.sender, "bot", False),
                    "verified": getattr(message.sender, "verified", False),
                }

            # Message statistics
            if hasattr(message, "views") and message.views is not None:
                message_dict["views"] = message.views
            if hasattr(message, "forwards") and message.forwards is not None:
                message_dict["forwards"] = message.forwards
            if hasattr(message, "replies") and message.replies:
                message_dict["replies"] = (
                    message.replies.replies if hasattr(message.replies, "replies") else 0
                )

            # Edit information
            if hasattr(message, "edit_date") and message.edit_date:
                message_dict["edit_date"] = message.edit_date.timestamp()

            # Reply information
            if message.reply_to and hasattr(message.reply_to, "reply_to_msg_id"):
                message_dict["reply_to_msg_id"] = message.reply_to.reply_to_msg_id

            # Media information (basic)
            if message.media:
                message_dict["has_media"] = True
                message_dict["media_type"] = str(type(message.media).__name__)
            else:
                message_dict["has_media"] = False

            # Additional attributes
            if hasattr(message, "grouped_id") and message.grouped_id:
                message_dict["grouped_id"] = message.grouped_id

            return message_dict

        except Exception as e:
            logger.warning(
                "Error converting message to dict",
                message_id=getattr(message, "id", "unknown"),
                error=str(e),
            )
            # Return minimal information on error
            return {
                "id": getattr(message, "id", None),
                "error": "Failed to parse message",
                "text": getattr(message, "text", ""),
            }

    @asynccontextmanager
    async def session_context(self) -> AsyncGenerator["TelegramClientWrapper", None]:
        """
        Context manager for client sessions.

        Ensures proper cleanup even if errors occur.
        """
        try:
            yield self
        finally:
            if self.is_connected:
                await self.disconnect()
