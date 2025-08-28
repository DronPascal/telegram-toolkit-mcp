# Technical Context: Telegram Toolkit MCP

## Technology Stack

### Core Technologies

#### Python 3.11+
- **Rationale**: Async/await support, type hints, performance optimizations
- **Key Features Used**: `asyncio` for concurrent requests, `dataclasses` for models
- **Version Requirements**: Minimum Python 3.11 for enhanced async features

#### Telethon 1.36+
- **Purpose**: MTProto client for Telegram API access
- **Key Capabilities**:
  - User session management via StringSession
  - Message iteration with filtering and pagination
  - Automatic FLOOD_WAIT handling
  - Media and attachment processing
- **Why Telethon**: Mature, well-maintained, comprehensive MTProto coverage

#### MCP Python SDK (FastMCP)
- **Purpose**: MCP server implementation framework
- **Key Features**:
  - Automatic JSON Schema generation from Pydantic models
  - Streamable HTTP transport support
  - Tool registration and error handling
  - Resource management
- **Version**: Latest compatible with MCP 2025-06-18

### Supporting Technologies

#### JSON Schema Draft 2020-12
- **Purpose**: Response validation and documentation
- **Implementation**: `jsonschema` library for validation
- **Key Features**: `$ref` support, comprehensive type system

#### NDJSON (Newline Delimited JSON)
- **Purpose**: Streaming large datasets efficiently
- **Format**: One JSON object per line, UTF-8 encoding
- **Benefits**: Memory-efficient, streaming-friendly, standard format

#### OpenTelemetry Python
- **Purpose**: Distributed tracing and metrics
- **Components**:
  - `opentelemetry-distro` for auto-instrumentation
  - `opentelemetry-exporter-otlp` for trace export
  - Custom metrics for MCP operations

#### Prometheus Client
- **Purpose**: Application metrics collection
- **Metrics Types**:
  - Counter: Request counts, message counts
  - Histogram: Response times, FLOOD_WAIT durations
  - Gauge: Active connections, queue sizes

## Development Environment

### Local Development
```bash
# Python environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Dependencies
pip install -r requirements.txt

# Environment variables
cp .env.example .env
# Edit .env with actual values
```

### Required Environment Variables
```bash
# Telegram API credentials
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_STRING_SESSION=your_session_string

# Server configuration
MCP_SERVER_HOST=localhost
MCP_SERVER_PORT=8000

# Performance tuning
FLOOD_SLEEP_THRESHOLD=60
REQUEST_TIMEOUT=30
MAX_PAGE_SIZE=100

# Resource management
TEMP_DIR=/tmp/mcp-resources
RESOURCE_MAX_AGE_HOURS=24
```

## Telegram API Integration

### MTProto vs Bot API Decision
**Why MTProto (Telethon):**
- ✅ Access to full message history (not limited to bot join date)
- ✅ User session provides higher rate limits
- ✅ Access to all message metadata (views, reactions, forwards)
- ✅ Support for all channel types and forum topics
- ✅ No bot-specific limitations

**Bot API Limitations (why not used):**
- ❌ Only messages after bot was added to channel
- ❌ Lower rate limits
- ❌ Limited metadata access
- ❌ Cannot access private channels
- ❌ No forum topic support

### Session Management
```python
# StringSession provides secure, portable session storage
from telethon import TelegramClient
from telethon.sessions import StringSession

# Initialize with string session
client = TelegramClient(
    StringSession(session_string),
    api_id,
    api_hash
)
```

### Message Iteration Strategy
```python
# Core iteration pattern with post-filtering
async for message in client.iter_messages(
    entity,
    reverse=True,  # Ascending order
    min_id=cursor_last_id,
    limit=page_size * 2  # Buffer for filtering
):
    # Date range filtering (server-side)
    if message.date > to_datetime:
        break
    if message.date < from_datetime:
        continue

    # Process message
    processed_msg = await process_message(message)
    messages.append(processed_msg)

    if len(messages) >= page_size:
        break
```

## MCP Implementation Details

### Tool Registration Pattern
```python
from mcp import FastMCP

app = FastMCP("Telegram History Exporter")

@app.tool()
async def tg_resolve_chat(input: str) -> ResolveChatResult:
    """Resolve chat identifier to internal format."""
    # Implementation
    pass

@app.tool()
async def tg_fetch_history(
    chat: str,
    from_date: str,
    to_date: str,
    page_size: int = 100,
    cursor: Optional[str] = None
) -> FetchHistoryResult:
    """Fetch message history with pagination."""
    # Implementation
    pass
```

### Response Structure Compliance
```python
# MCP-compliant response format
{
    "content": [
        {
            "type": "text",
            "text": "Found 150 messages in @telegram channel"
        }
    ],
    "structuredContent": {
        "messages": [...],
        "page_info": {...},
        "export": {...}
    }
}
```

### Error Handling Strategy
```python
# MCP error response format
{
    "isError": True,
    "content": [
        {
            "type": "text",
            "text": "FLOOD_WAIT: Retry after 87 seconds"
        }
    ],
    "structuredContent": {
        "error": {
            "code": "FLOOD_WAIT",
            "retry_after": 87,
            "cursor": "base64_encoded_cursor"
        }
    }
}
```

## Data Processing Pipeline

### Message Processing Flow
1. **Raw Message** → Telethon message object
2. **Validation** → Check message integrity
3. **Transformation** → Convert to internal format
4. **Filtering** → Apply date/content filters
5. **Deduplication** → Remove duplicates by ID
6. **Serialization** → Convert to JSON schema format
7. **Pagination** → Apply page limits and generate cursor

### Resource Generation Flow
1. **Threshold Check** → If messages > 500, generate resource
2. **NDJSON Creation** → Write messages to temporary file
3. **URI Generation** → Create MCP resource URI
4. **Notification** → Send `resources/updated` notification
5. **Cleanup** → Schedule resource deletion after TTL

## Security Considerations

### Session Security
- **StringSession Storage**: Environment variables only
- **No File Persistence**: Sessions never written to disk
- **Runtime Only**: Sessions exist only in memory during execution
- **Validation**: Session string format validation on startup

### Data Protection
- **PII Masking**: Hash-based chat identifiers in logs
- **Content Sanitization**: Remove sensitive patterns from messages
- **Access Control**: Public channels only
- **Audit Logging**: Complete request/response logging

### Network Security
- **TLS**: All external communications over HTTPS
- **Rate Limiting**: Respect Telegram API limits
- **Timeout Handling**: Prevent hanging connections
- **Error Sanitization**: No sensitive data in error messages

## Performance Characteristics

### Expected Performance Metrics
- **Response Time**: p95 ≤ 2.5s for 100 messages
- **Throughput**: 100-200 messages/second during iteration
- **Memory Usage**: < 100MB for typical operations
- **Storage**: Temporary NDJSON files, auto-cleanup after 24h

### Bottlenecks and Optimizations
- **Network I/O**: Telegram API calls are the main bottleneck
- **Date Filtering**: Server-side filtering vs API-level filtering
- **Message Processing**: Async processing for media-rich messages
- **Resource Generation**: Streaming NDJSON for large datasets

## Deployment Architecture

### Local Development
```bash
# Start MCP server
python -m telegram_toolkit_mcp.server

# Connect MCP client
mcp-client connect http://localhost:8000
```

### Cloud Deployment (Cloudflare)
```yaml
# wrangler.toml for Cloudflare Workers
name = "telegram-toolkit-mcp"
main = "src/worker.ts"
compatibility_date = "2024-01-01"

[env.production.vars]
TELEGRAM_API_ID = "your_api_id"
```

### Docker Deployment
```dockerfile
FROM python:3.11-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
EXPOSE 8000

CMD ["python", "-m", "telegram_toolkit_mcp.server"]
```

## Testing Strategy

### Unit Testing
- **Schema Validation**: All response formats
- **Cursor Encoding/Decoding**: Pagination logic
- **Error Handling**: All error code paths
- **Message Processing**: Transformation pipeline

### Integration Testing
- **E2E Scenarios**: Real Telegram channels (@telegram, @bloomberg)
- **Load Testing**: Performance under various message volumes
- **Error Scenarios**: Network failures, API limits

### Test Data
- **Public Channels**: @telegram, @bloomberg, @apod_telegram
- **Date Ranges**: 1 day, 1 week, 1 month
- **Filters**: all, media, links, photos
- **Search Terms**: Common keywords in test channels

## Monitoring and Observability

### Application Metrics
```python
# Prometheus metrics
REQUEST_COUNT = Counter('mcp_requests_total', 'Total requests', ['tool', 'status'])
RESPONSE_TIME = Histogram('mcp_response_duration', 'Response time', ['tool'])
MESSAGE_COUNT = Counter('telegram_messages_processed', 'Messages processed')
FLOOD_WAIT_TIME = Histogram('telegram_flood_wait_seconds', 'Flood wait duration')
```

### Distributed Tracing
```python
# OpenTelemetry spans
with tracer.start_as_current_span("tg_fetch_history") as span:
    span.set_attribute("chat.id", chat_id)
    span.set_attribute("date.range", f"{from_date} to {to_date}")
    # ... implementation
```

### Logging Strategy
```python
# Structured JSON logging
{
    "timestamp": "2025-01-01T12:00:00Z",
    "level": "INFO",
    "tool": "tg_fetch_history",
    "chat_hash": "a1b2c3d4...",
    "duration": 1.23,
    "message_count": 150,
    "cursor": "base64_cursor",
    "status": "success"
}
```

## Future Technical Roadmap

### Version 1.1 Features
- **tg.stats Tool**: Aggregated statistics and engagement metrics
- **Enhanced Filtering**: More content type filters
- **Search Improvements**: Better text search capabilities

### Version 2.0 Features
- **Multi-Backend Support**: Pyrogram as alternative to Telethon
- **Media Downloads**: Binary file retrieval capabilities
- **Real-time Streaming**: WebSocket-based live monitoring
- **Advanced Analytics**: Built-in sentiment analysis

### Technical Debt and Improvements
- **Code Coverage**: Aim for >90% test coverage
- **Performance Profiling**: Identify and optimize bottlenecks
- **Memory Optimization**: Reduce memory footprint for large datasets
- **Documentation**: Auto-generated API docs from schemas

This technical context provides the foundation for implementing a robust, scalable, and maintainable MCP server for Telegram data extraction.
