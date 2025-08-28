# Telegram Toolkit MCP API Documentation

## Overview

The Telegram Toolkit MCP server provides read-only access to public Telegram chats through the Model Context Protocol (MCP). This API documentation covers all available tools, their parameters, responses, and error handling.

## Authentication

The server requires Telegram API credentials:

```bash
export TELEGRAM_API_ID="your_api_id"
export TELEGRAM_API_HASH="your_api_hash"
```

> **Security Note**: These credentials are used to authenticate with Telegram's API. Never share them and rotate them if compromised.

## Tools

### 1. `tg.resolve_chat`

Resolves chat identifiers to standardized format and retrieves basic chat information.

#### Purpose
- Normalize various chat identifier formats
- Validate chat accessibility
- Retrieve chat metadata

#### Input Parameters

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `input` | string | Yes | Chat identifier in any of these formats:<br>• `@username`<br>• `t.me/username`<br>• `https://t.me/username`<br>• Numeric ID |

#### Output Schema

```json
{
  "type": "object",
  "properties": {
    "chat_id": {
      "type": "string",
      "description": "Normalized chat ID"
    },
    "kind": {
      "type": "string",
      "enum": ["user", "group", "channel"],
      "description": "Type of chat entity"
    },
    "title": {
      "type": "string",
      "description": "Display name of the chat"
    },
    "username": {
      "type": "string",
      "description": "Username if available"
    },
    "description": {
      "type": "string",
      "description": "Chat description"
    },
    "member_count": {
      "type": "integer",
      "description": "Number of members (for groups/channels)"
    },
    "verified": {
      "type": "boolean",
      "description": "Whether the channel is verified by Telegram"
    }
  }
}
```

#### Examples

**Basic Usage:**
```json
{
  "input": "@telegram"
}
```

**Response:**
```json
{
  "chat_id": "136817688",
  "kind": "channel",
  "title": "Telegram",
  "username": "telegram",
  "member_count": 1000000,
  "verified": true
}
```

**Numeric ID:**
```json
{
  "input": "136817688"
}
```

**URL Format:**
```json
{
  "input": "https://t.me/telegram"
}
```

#### Error Handling

- **CHAT_NOT_FOUND**: Chat doesn't exist or is private
- **VALIDATION_ERROR**: Invalid identifier format
- **FLOOD_WAIT**: Rate limit exceeded
- **CHANNEL_PRIVATE**: Channel is private and inaccessible

### 2. `tg.fetch_history`

Fetches message history from a chat with advanced filtering and pagination.

#### Purpose
- Retrieve historical messages from public chats
- Support complex filtering and search
- Handle large datasets with pagination
- Provide structured message data

#### Input Parameters

| Parameter | Type | Required | Default | Description |
|-----------|------|----------|---------|-------------|
| `chat` | string | Yes | - | Chat identifier (resolved via tg.resolve_chat) |
| `from_date` | string | No | - | Start date (ISO 8601 format: YYYY-MM-DDTHH:MM:SSZ) |
| `to_date` | string | No | - | End date (ISO 8601 format) |
| `page_size` | integer | No | 50 | Messages per page (1-100) |
| `cursor` | string | No | - | Pagination cursor for next page |
| `direction` | string | No | "desc" | Sort order: "asc" or "desc" |
| `search` | string | No | - | Text search query |
| `filter` | object | No | - | Advanced filtering options |

#### Advanced Filtering (`filter` object)

```json
{
  "media_types": {
    "type": "array",
    "items": {
      "type": "string",
      "enum": ["text", "photo", "video", "document", "audio", "voice", "sticker", "link", "poll"]
    },
    "description": "Filter by media content types"
  },
  "has_media": {
    "type": "boolean",
    "description": "Filter messages with/without media attachments"
  },
  "from_users": {
    "type": "array",
    "items": {"type": "integer"},
    "description": "Filter by sender user IDs"
  },
  "min_views": {
    "type": "integer",
    "minimum": 0,
    "description": "Minimum view count"
  },
  "max_views": {
    "type": "integer",
    "minimum": 0,
    "description": "Maximum view count"
  }
}
```

#### Output Schema

```json
{
  "type": "object",
  "properties": {
    "messages": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "integer",
            "description": "Unique message ID"
          },
          "date": {
            "type": "number",
            "description": "Unix timestamp"
          },
          "text": {
            "type": "string",
            "description": "Message text content"
          },
          "out": {
            "type": "boolean",
            "description": "Whether message was sent by current user"
          },
          "mentioned": {
            "type": "boolean",
            "description": "Whether current user is mentioned"
          },
          "silent": {
            "type": "boolean",
            "description": "Whether message is silent"
          },
          "post": {
            "type": "boolean",
            "description": "Whether this is a channel post"
          },
          "from_scheduled": {
            "type": "boolean",
            "description": "Whether message was scheduled"
          },
          "legacy": {
            "type": "boolean",
            "description": "Legacy message format"
          },
          "edit_hide": {
            "type": "boolean",
            "description": "Whether edit history is hidden"
          },
          "pinned": {
            "type": "boolean",
            "description": "Whether message is pinned"
          },
          "noforwards": {
            "type": "boolean",
            "description": "Whether forwarding is disabled"
          },
          "sender": {
            "type": "object",
            "properties": {
              "id": {"type": "integer"},
              "first_name": {"type": "string"},
              "last_name": {"type": "string"},
              "username": {"type": "string"},
              "bot": {"type": "boolean"},
              "verified": {"type": "boolean"}
            }
          },
          "views": {
            "type": "integer",
            "description": "Number of views"
          },
          "forwards": {
            "type": "integer",
            "description": "Number of forwards"
          },
          "replies": {
            "type": "integer",
            "description": "Number of replies"
          },
          "reactions": {
            "type": "integer",
            "description": "Number of reactions"
          },
          "has_media": {
            "type": "boolean",
            "description": "Whether message has media attachments"
          },
          "media_type": {
            "type": "string",
            "enum": ["photo", "video", "document", "audio", "voice", "sticker", "link", "poll"],
            "description": "Type of media attachment"
          }
        }
      }
    },
    "page_info": {
      "type": "object",
      "properties": {
        "has_more": {
          "type": "boolean",
          "description": "Whether there are more messages"
        },
        "cursor": {
          "type": "string",
          "description": "Cursor for next page (null if no more)"
        },
        "total_fetched": {
          "type": "integer",
          "description": "Total messages fetched so far"
        }
      }
    },
    "export": {
      "type": "object",
      "description": "Large dataset export information",
      "properties": {
        "uri": {
          "type": "string",
          "description": "MCP resource URI for large datasets"
        },
        "format": {
          "type": "string",
          "enum": ["ndjson"],
          "description": "Export format"
        }
      }
    }
  }
}
```

#### Examples

**Basic Message Fetch:**
```json
{
  "chat": "136817688",
  "page_size": 10
}
```

**Date Range Query:**
```json
{
  "chat": "@telegram",
  "from_date": "2025-01-01T00:00:00Z",
  "to_date": "2025-01-02T00:00:00Z",
  "page_size": 50
}
```

**Search Query:**
```json
{
  "chat": "@telegram",
  "search": "bitcoin",
  "page_size": 25
}
```

**Advanced Filtering:**
```json
{
  "chat": "@telegram",
  "filter": {
    "media_types": ["photo", "video"],
    "has_media": true,
    "min_views": 1000
  },
  "page_size": 20
}
```

**Pagination:**
```json
{
  "chat": "@telegram",
  "cursor": "eyJvZmZzZXRfaWQiOiAxMjM0NSwgImRpcmVjdGlvbiI6ICJkZXNjIn0=",
  "page_size": 50
}
```

#### Response Examples

**Normal Response:**
```json
{
  "messages": [
    {
      "id": 12345,
      "date": 1640995200.0,
      "text": "Welcome to Telegram!",
      "sender": {
        "id": 67890,
        "username": "telegram",
        "first_name": "Telegram",
        "verified": true
      },
      "views": 1500,
      "has_media": false
    }
  ],
  "page_info": {
    "has_more": true,
    "cursor": "next_cursor_value",
    "total_fetched": 50
  }
}
```

**Large Dataset Response:**
```json
{
  "messages": [...],
  "page_info": {
    "has_more": true,
    "cursor": "next_cursor_value",
    "total_fetched": 150
  },
  "export": {
    "uri": "mcp://resources/export/abc123.ndjson",
    "format": "ndjson"
  }
}
```

## Error Handling

### MCP Error Response Format

All errors follow the MCP Problem Details specification:

```json
{
  "isError": true,
  "error": {
    "type": "ERROR_TYPE",
    "title": "Human readable title",
    "status": 400,
    "detail": "Detailed error description with context"
  },
  "content": [
    {
      "type": "text",
      "text": "User-friendly error message with guidance"
    }
  ]
}
```

### Error Types

| Error Type | HTTP Status | Description |
|------------|-------------|-------------|
| `VALIDATION_ERROR` | 400 | Invalid input parameters or format |
| `CHAT_NOT_FOUND` | 404 | Chat doesn't exist or is inaccessible |
| `CHANNEL_PRIVATE` | 403 | Channel is private and requires invitation |
| `FLOOD_WAIT` | 429 | Rate limit exceeded, includes retry_after |
| `INTERNAL_ERROR` | 500 | Server-side error, should be reported |

### Common Error Scenarios

#### Rate Limiting
```json
{
  "isError": true,
  "error": {
    "type": "FLOOD_WAIT",
    "title": "Rate limit exceeded",
    "status": 429,
    "detail": "Rate limit exceeded. Retry after 30 seconds."
  },
  "content": [
    {
      "type": "text",
      "text": "Rate limit exceeded. Please wait 30 seconds before retrying."
    }
  ]
}
```

#### Invalid Chat
```json
{
  "isError": true,
  "error": {
    "type": "CHAT_NOT_FOUND",
    "title": "Chat not found",
    "status": 404,
    "detail": "Chat 'invalid_chat' not found or is private."
  },
  "content": [
    {
      "type": "text",
      "text": "Chat not found. Please check the chat identifier and ensure it's public."
    }
  ]
}
```

#### Input Validation
```json
{
  "isError": true,
  "error": {
    "type": "VALIDATION_ERROR",
    "title": "Input validation failed",
    "status": 400,
    "detail": "page_size must be between 1 and 100, got 150"
  },
  "content": [
    {
      "type": "text",
      "text": "Invalid page size. Please use a value between 1 and 100."
    }
  ]
}
```

## Rate Limiting

### Built-in Protection

The server includes automatic rate limiting to prevent abuse:

- **Per-minute limits**: 30 requests per minute per chat
- **Burst protection**: 10 requests in 10-second windows
- **Automatic backoff**: Exponential backoff for FLOOD_WAIT errors
- **Client-specific limits**: Separate limits per chat identifier

### Rate Limit Headers

When rate limited, the server returns appropriate error responses with retry guidance.

## Pagination

### Cursor-Based Pagination

The API uses opaque cursors for efficient pagination:

1. **Initial Request**: No cursor provided
2. **Subsequent Requests**: Use cursor from previous response
3. **End Detection**: `has_more: false` and `cursor: null`

### Cursor Encoding

Cursors are base64-encoded JSON containing:
```json
{
  "offset_id": 12345,
  "offset_date": 1640995200,
  "min_id": null,
  "max_id": null,
  "fetched_count": 50,
  "direction": "desc"
}
```

### Best Practices

1. **Process sequentially**: Don't skip pages
2. **Respect cursors**: Use provided cursors exactly
3. **Handle end condition**: Stop when `has_more` is false
4. **Store progress**: Save cursors for resumable operations

## Large Dataset Handling

### NDJSON Resources

For datasets >100 messages, the server automatically creates NDJSON resources:

- **Automatic creation**: Triggered when message count exceeds threshold
- **Streaming access**: Efficient streaming via MCP resource API
- **Temporary storage**: Automatic cleanup after configurable time
- **Metadata preservation**: All query parameters included

### Resource URIs

```
mcp://resources/export/{resource_id}.ndjson
```

### Resource Lifecycle

1. **Creation**: Automatic when dataset is large
2. **Access**: Via MCP resource reading API
3. **Cleanup**: Automatic expiration after 24 hours (configurable)
4. **Monitoring**: Resource usage tracked in metrics

## Monitoring

### Prometheus Metrics

The server exposes comprehensive metrics at `/metrics`:

#### Tool Metrics
- `mcp_tool_calls_total{tool, status, chat_type}` - Tool call counts
- `mcp_tool_duration_seconds{tool, status}` - Tool execution times

#### API Metrics
- `telegram_api_calls_total{method, status}` - Telegram API calls
- `telegram_api_duration_seconds{method}` - API response times

#### Error Metrics
- `telegram_toolkit_errors_total{error_type, component}` - Error counts

#### Resource Metrics
- `telegram_ndjson_exports_total{status}` - Export creation
- `telegram_ndjson_export_size_bytes` - Export sizes

### Key Monitoring Queries

```promql
# Success rate
rate(mcp_tool_calls_total{status="success"}[5m]) /
rate(mcp_tool_calls_total[5m])

# Error rate
rate(telegram_toolkit_errors_total[5m])

# FLOOD_WAIT frequency
rate(telegram_flood_wait_events_total[5m])

# Large export usage
rate(telegram_ndjson_exports_total{status="success"}[1h])
```

## Performance Guidelines

### Optimal Usage Patterns

1. **Page Size Selection**:
   - Small pages (10-25): Low latency, more requests
   - Medium pages (50-75): Balanced performance
   - Large pages (100): High throughput, higher latency

2. **Filtering Strategy**:
   - Use server-side filtering to reduce data transfer
   - Combine multiple filters for precise results
   - Prefer date ranges over full scans

3. **Caching Recommendations**:
   - Cache chat resolution results
   - Implement client-side result caching
   - Store pagination progress for resumable operations

### Performance Benchmarks

| Operation | p50 | p95 | p99 | Notes |
|-----------|-----|-----|-----|-------|
| Chat Resolution | 50ms | 200ms | 500ms | Single API call |
| Message Fetch (10) | 75ms | 300ms | 800ms | Small dataset |
| Message Fetch (50) | 150ms | 600ms | 1.5s | Medium dataset |
| Message Fetch (100) | 300ms | 1.2s | 3s | Large dataset |
| NDJSON Export | 500ms | 2s | 5s | Resource creation |

### Scaling Considerations

1. **Concurrent Requests**: Server handles multiple simultaneous requests
2. **Memory Usage**: Efficient streaming for large datasets
3. **Rate Limiting**: Automatic protection against overload
4. **Resource Cleanup**: Automatic cleanup prevents disk space issues

## Security Considerations

### Data Protection

- **PII Masking**: All sensitive data automatically masked in logs
- **No Persistence**: Messages never stored on disk
- **Secure Sessions**: In-memory session management
- **Input Validation**: Comprehensive sanitization

### Access Control

- **Public Only**: Only public channels accessible
- **No Authentication**: No user authentication required
- **Rate Limiting**: Built-in abuse protection
- **Audit Logging**: All operations logged with context

### Compliance

- **GDPR**: PII masking for personal data protection
- **Telegram ToS**: Respects official API usage policies
- **Open Source**: Transparent security implementation

## Troubleshooting

### Common Issues

#### Connection Problems
```
Error: Failed to connect to Telegram
```
**Solution**: Check API credentials and network connectivity

#### Rate Limiting
```
Error: Rate limit exceeded
```
**Solution**: Reduce request frequency, implement exponential backoff

#### Large Responses
```
Warning: Dataset too large, using NDJSON resource
```
**Solution**: This is normal, use the provided resource URI

#### Invalid Cursors
```
Error: Invalid cursor format
```
**Solution**: Use cursors exactly as provided by the API

### Debug Information

Enable detailed logging:
```bash
export DEBUG=true
export LOG_LEVEL=DEBUG
```

### Health Checks

```bash
# Check server health
curl http://localhost:8000/health

# View metrics
curl http://localhost:8000/metrics
```

## Version History

### v0.1.0 (Current)
- Initial release with core functionality
- MCP 2025-06-18 compliance
- Comprehensive security features
- Prometheus metrics integration
- Advanced filtering and pagination

## Support

For issues and questions:
1. Check the troubleshooting section above
2. Review error messages and metrics
3. Verify API credentials and network connectivity
4. Ensure proper input parameter formats

## Contributing

See the main README.md for contribution guidelines and development setup.
