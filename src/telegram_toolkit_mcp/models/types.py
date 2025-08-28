"""
Core type definitions for Telegram Toolkit MCP.

This module defines Pydantic models for MCP structured content,
Telegram API responses, and internal data structures.
"""

from datetime import datetime

try:
    from pydantic import BaseModel, ConfigDict, Field
except ImportError:
    # Fallback for development
    BaseModel = object

    def Field(**kwargs):
        return lambda cls: cls

    ConfigDict = dict


class PeerInfo(BaseModel):
    """Information about message sender/peer."""

    peer_id: str = Field(..., description="Telegram peer identifier")
    kind: str = Field(..., description="Peer type: user/bot/channel")
    display: str | None = Field(None, description="Display name if available")

    model_config = ConfigDict(frozen=True)


class AttachmentInfo(BaseModel):
    """Information about message attachment."""

    type: str = Field(
        ...,
        description="Attachment type",
        examples=["photo", "video", "document", "audio", "voice", "sticker", "link", "poll"],
    )
    mime: str | None = Field(None, description="MIME type for media files")
    size: int | None = Field(None, ge=0, description="File size in bytes")
    uri: str | None = Field(None, description="Resource URI or download link")

    model_config = ConfigDict(frozen=True)


class MessageInfo(BaseModel):
    """Telegram message information."""

    id: int = Field(..., ge=1, description="Message ID")
    date: datetime = Field(..., description="Message timestamp (UTC)")
    from_: PeerInfo = Field(..., alias="from", description="Message sender info")
    text: str = Field("", description="Message text content")

    # Optional metadata
    reply_to_id: int | None = Field(None, ge=1, description="Reply-to message ID")
    topic_id: int | None = Field(None, ge=1, description="Forum topic ID")
    grouped_id: int | None = Field(None, ge=1, description="Media group ID")

    # Engagement metrics
    edit_date: datetime | None = Field(None, description="Last edit timestamp")
    views: int | None = Field(None, ge=0, description="View count")
    forwards: int | None = Field(None, ge=0, description="Forward count")
    replies: int | None = Field(None, ge=0, description="Reply count")
    reactions: int | None = Field(None, ge=0, description="Reaction count")

    # Attachments
    attachments: list[AttachmentInfo] = Field(
        default_factory=list, description="Message attachments"
    )

    model_config = ConfigDict(
        frozen=True, populate_by_name=True, json_encoders={datetime: lambda v: v.isoformat() + "Z"}
    )


class PageInfo(BaseModel):
    """Pagination information."""

    cursor: str = Field(..., description="Base64-encoded cursor for next page")
    has_more: bool = Field(..., description="Whether more pages are available")
    count: int = Field(..., ge=0, description="Total messages in this page")
    fetched: int = Field(..., ge=0, description="Messages actually fetched")

    model_config = ConfigDict(frozen=True)


class ExportInfo(BaseModel):
    """Information about exported data."""

    uri: str = Field(..., description="Resource URI for exported data")
    format: str = Field(..., description="Export format", examples=["ndjson", "csv"])

    model_config = ConfigDict(frozen=True)


class ChatInfo(BaseModel):
    """Basic chat information."""

    chat_id: str = Field(..., description="Telegram chat identifier")
    kind: str = Field(..., description="Chat type", examples=["channel", "supergroup", "group"])
    title: str = Field(..., description="Chat title/name")
    member_count: int | None = Field(None, ge=0, description="Member count")

    model_config = ConfigDict(frozen=True)


class ErrorInfo(BaseModel):
    """Error information for MCP responses."""

    code: str = Field(
        ...,
        description="Error code",
        examples=[
            "FLOOD_WAIT",
            "CHANNEL_PRIVATE",
            "USERNAME_INVALID",
            "AUTH_REQUIRED",
            "INPUT_VALIDATION",
            "RATE_LIMITED",
        ],
    )
    message: str = Field(..., description="Human-readable error message")
    retry_after: int | None = Field(None, ge=0, description="Seconds to wait before retry")
    details: dict | None = Field(None, description="Additional error details")

    model_config = ConfigDict(frozen=True)
