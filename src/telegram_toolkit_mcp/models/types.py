"""
Core type definitions for Telegram Toolkit MCP.

This module defines Pydantic models for MCP structured content,
Telegram API responses, and internal data structures.
"""

from datetime import datetime
from typing import Dict, List

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
    username: str | None = Field(None, description="Chat username (if available)")
    member_count: int | None = Field(None, ge=0, description="Member count")
    verified: bool = Field(False, description="Whether chat is verified")
    restricted: bool = Field(False, description="Whether chat is restricted")
    megagroup: bool = Field(False, description="Whether it's a supergroup")
    gigagroup: bool = Field(False, description="Whether it's a gigagroup")

    model_config = ConfigDict(frozen=True)


class ResolveChatRequest(BaseModel):
    """Request model for chat resolution."""

    input: str = Field(..., description="Chat identifier to resolve")

    model_config = ConfigDict(frozen=True)


class ResolveChatResponse(BaseModel):
    """Response model for chat resolution."""

    chat_id: str = Field(..., description="Resolved chat ID")
    kind: str = Field(..., description="Chat type")
    title: str = Field(..., description="Chat title")
    username: str | None = Field(None, description="Chat username")
    member_count: int | None = Field(None, description="Member count")
    verified: bool = Field(False, description="Verification status")
    resolved_from: Dict[str, str] = Field(..., description="Original input information")

    model_config = ConfigDict(frozen=True)


class FetchHistoryRequest(BaseModel):
    """Request model for fetching message history."""

    chat: str = Field(..., description="Chat identifier to fetch from")
    limit: int = Field(100, ge=1, le=1000, description="Maximum messages to fetch")
    from_date: datetime | None = Field(None, description="Start date for filtering (UTC)")
    to_date: datetime | None = Field(None, description="End date for filtering (UTC)")
    cursor: str | None = Field(None, description="Pagination cursor")
    include_attachments: bool = Field(False, description="Include attachment information")
    search: str | None = Field(None, description="Text search query")

    model_config = ConfigDict(frozen=True)


class FetchHistoryResponse(BaseModel):
    """Response model for message history fetch."""

    messages: list[MessageInfo] = Field(..., description="Fetched messages")
    page_info: PageInfo = Field(..., description="Pagination information")
    export_info: ExportInfo | None = Field(None, description="Export information for large datasets")
    total_fetched: int = Field(..., ge=0, description="Total messages fetched in this request")

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
