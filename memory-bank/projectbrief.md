# Telegram Toolkit MCP - Project Brief

## Project Overview
**Telegram Toolkit MCP** is a read-only Model Context Protocol (MCP) server designed to safely extract message history from public Telegram chats and channels by date periods with paginated delivery (ASC order), strict `structuredContent` according to schema, and large exports via NDJSON resources (MCP rev. 2025-06-18).

## Core Objectives
- Provide secure read-only access to public Telegram channel/group message history
- Support date-range filtering with ascending pagination and cursor-based navigation
- Implement strict JSON Schema validation for all responses
- Handle large datasets via NDJSON resource streaming
- Ensure compatibility with MCP specification rev. 2025-06-18
- Support remote deployment via Streamable HTTP transport

## Key Features
- **Date-based filtering**: Extract messages within specific UTC time ranges
- **Pagination**: Cursor-based navigation with configurable page sizes (≤100)
- **Content filtering**: Server-side filtering by message types (media, links, etc.)
- **Search**: Text-based message search within date ranges
- **Thread support**: Handle forum topics and thread-based conversations
- **Resource streaming**: NDJSON exports for large datasets
- **Error handling**: Comprehensive error codes with retry mechanisms
- **Observability**: Prometheus metrics, OpenTelemetry tracing, structured logging

## Technical Foundation
- **Language**: Python 3.11+
- **Telegram Client**: Telethon (MTProto user-session based)
- **MCP Framework**: Official Python SDK with FastMCP
- **Transport**: Streamable HTTP (Cloudflare compatible)
- **Data Format**: JSON Schema Draft 2020-12, NDJSON for resources
- **Authentication**: StringSession-based user authentication
- **Storage**: In-memory processing with NDJSON file exports

## Success Criteria
- **Performance**: p95 ≤ 2.5s per page (≤100 messages)
- **Accuracy**: 0% gaps in date ranges, ≤0.5% duplicates
- **Reliability**: Proper FLOOD_WAIT handling with cursor preservation
- **Compliance**: Strict adherence to MCP 2025-06-18 specification
- **Security**: No PII logging, secure session management
- **Scalability**: Efficient handling of large public channels (1000+ messages/day)

## Project Scope (v1.0 MVP)
**Included:**
- Core tools: `tg.resolve_chat`, `tg.fetch_history`
- Date-range filtering and pagination
- Content type filtering and text search
- NDJSON resource exports
- Comprehensive error handling
- Basic observability (metrics, tracing, logging)

**Excluded:**
- Message sending or modification
- Binary media downloads
- Private/invite-only chats
- Administrative actions
- Real-time message streaming

## Risk Mitigation
- **API Limits**: Exponential backoff, cursor preservation, rate limiting
- **Data Accuracy**: Server-side date filtering, message deduplication
- **Security**: Secure session storage, PII masking, audit logging
- **Performance**: Resource-based large exports, configurable page sizes
- **Compliance**: MCP specification adherence, public-only access

## Quality Assurance
- **Testing**: Unit tests for schemas, cursors, errors; E2E tests on public channels
- **Validation**: JSON Schema compliance for all responses
- **Monitoring**: SLO tracking, error rate monitoring, performance metrics
- **Documentation**: Comprehensive README, API examples, error code reference

## Future Roadmap
- **v1.1**: Advanced statistics tool (`tg.stats`)
- **v1.2**: Multi-backend support (Pyrogram alternative)
- **v2.0**: Media download capabilities
- **v2.1**: Real-time monitoring features

## Project Status
**Current Phase**: TЗ v1.0 finalized, ready for implementation
**Next Steps**: Repository setup, core implementation, testing
**Timeline**: 6-8 weeks for MVP completion
**Team**: Solo developer with MCP/Telegram expertise
