# System Patterns: Telegram Toolkit MCP

## Core Architectural Patterns

### 1. HTTP Transport MCP Server Pattern
```python
# FastMCP-based server with HTTP transport and health endpoints
class TelegramMCPServer:
    def __init__(self):
        self.mcp = FastMCP("Telegram History Exporter")
        self.telegram_client = None

    async def lifespan(self):
        # Initialize Telethon client
        self.telegram_client = TelegramClient(
            StringSession(os.getenv("TELEGRAM_STRING_SESSION")),
            int(os.getenv("TELEGRAM_API_ID")),
            os.getenv("TELEGRAM_API_HASH")
        )
        await self.telegram_client.start()

        # Add health endpoint
        @self.mcp.app.get("/health")
        async def health_endpoint():
            return PlainTextResponse("OK", status_code=200)

        yield
        await self.telegram_client.disconnect()

    def run_server_sync(self):
        """Run with HTTP transport (synchronous for production)"""
        self.mcp.run(transport="http", host="0.0.0.0", port=8000)
```

### 2. Tool Implementation Pattern
```python
@mcp.tool()
async def tg_fetch_history(
    chat: str,
    from_date: str,
    to_date: str,
    page_size: int = 100,
    cursor: Optional[str] = None
) -> FetchHistoryResult:
    """Fetch message history with pagination and filtering."""

    # 1. Input validation and parsing
    entity = await resolve_chat_entity(chat)

    # 2. Cursor decoding
    last_id = decode_cursor(cursor) if cursor else 0

    # 3. Telethon iteration with post-filtering
    messages = []
    async for message in client.iter_messages(
        entity,
        reverse=True,
        min_id=last_id,
        limit=page_size * 2  # Buffer for filtering
    ):
        if message.date > datetime.fromisoformat(to_date):
            break
        if message.date >= datetime.fromisoformat(from_date):
            messages.append(process_message(message))

        if len(messages) >= page_size:
            break

    # 4. Deduplication and cursor generation
    messages = deduplicate_messages(messages)
    new_cursor = encode_cursor(messages[-1].id) if messages else None

    # 5. Resource generation for large datasets
    export_uri = None
    if len(messages) > 500:
        export_uri = await generate_ndjson_resource(messages)

    return FetchHistoryResult(
        messages=messages,
        page_info=PageInfo(
            cursor=new_cursor,
            has_more=len(messages) == page_size,
            count=len(messages),
            fetched=len(messages)
        ),
        export=export_uri
    )
```

### 3. Error Handling Pattern
```python
class TelegramErrorHandler:
    ERROR_MAPPINGS = {
        FloodWaitError: ("FLOOD_WAIT", lambda e: {"retry_after": e.seconds}),
        ChannelPrivateError: ("CHANNEL_PRIVATE", None),
        UsernameInvalidError: ("USERNAME_INVALID", None),
        AuthKeyUnregisteredError: ("AUTH_REQUIRED", None)
    }

    @classmethod
    def handle_error(cls, error: Exception) -> dict:
        for error_type, (code, payload_func) in cls.ERROR_MAPPINGS.items():
            if isinstance(error, error_type):
                payload = payload_func(error) if payload_func else {}
                return {
                    "isError": True,
                    "content": [{"type": "text", "text": f"{code}: {str(error)}"}],
                    "structuredContent": {
                        "error": {"code": code, **payload}
                    }
                }
        return cls._unknown_error(error)

    @classmethod
    def _unknown_error(cls, error: Exception) -> dict:
        return {
            "isError": True,
            "content": [{"type": "text", "text": f"UNKNOWN: {str(error)}"}],
            "structuredContent": {
                "error": {"code": "UNKNOWN", "message": str(error)}
            }
        }
```

### 4. Pagination Pattern
```python
class TelegramPaginator:
    @staticmethod
    def encode_cursor(message_id: int, direction: str = "asc") -> str:
        """Encode cursor as base64 JSON."""
        cursor_data = {"last_id": message_id, "direction": direction}
        return base64.b64encode(json.dumps(cursor_data).encode()).decode()

    @staticmethod
    def decode_cursor(cursor: str) -> Optional[int]:
        """Decode cursor from base64 JSON."""
        try:
            cursor_data = json.loads(base64.b64decode(cursor).decode())
            return cursor_data.get("last_id")
        except:
            return None

    @staticmethod
    async def fetch_page(
        client: TelegramClient,
        entity,
        from_date: datetime,
        to_date: datetime,
        min_id: int = 0,
        page_size: int = 100
    ) -> tuple[list, bool]:
        """Fetch one page with date filtering and deduplication."""
        messages = []
        seen_ids = set()

        async for message in client.iter_messages(
            entity,
            reverse=True,
            min_id=min_id,
            limit=page_size * 2  # Buffer for filtering
        ):
            # Stop if beyond date range
            if message.date > to_date:
                break

            # Skip if before date range
            if message.date < from_date:
                continue

            # Deduplication
            if message.id in seen_ids:
                continue
            seen_ids.add(message.id)

            messages.append(message)

            # Stop if page full
            if len(messages) >= page_size:
                break

        has_more = len(messages) == page_size
        return messages, has_more
```

### 5. Resource Generation Pattern
```python
class NDJSONResourceManager:
    def __init__(self, temp_dir: str = "/tmp/mcp-resources"):
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(exist_ok=True)

    async def generate_resource(
        self,
        messages: list,
        chat_identifier: str,
        date_range: tuple[datetime, datetime]
    ) -> str:
        """Generate NDJSON file and return resource URI."""
        from_date, to_date = date_range

        # Generate unique filename
        timestamp = int(time.time())
        filename = f"export_{chat_identifier}_{from_date.date()}_{to_date.date()}_{timestamp}.ndjson"
        filepath = self.temp_dir / filename

        # Write NDJSON
        with open(filepath, 'w', encoding='utf-8') as f:
            for message in messages:
                json_line = json.dumps(
                    self._message_to_dict(message),
                    ensure_ascii=False,
                    default=str
                )
                f.write(json_line + '\n')

        # Return MCP resource URI
        return f"mcp://resources/telegram/{filename}"

    def _message_to_dict(self, message) -> dict:
        """Convert Telethon message to dict format."""
        return {
            "id": message.id,
            "date": message.date.isoformat(),
            "chat_id": str(message.chat_id or message.peer_id),
            "from": {
                "peer_id": str(message.from_id or message.peer_id),
                "kind": self._get_peer_kind(message),
                "display": getattr(message.sender, 'first_name', '') if message.sender else ''
            },
            "text": message.text or "",
            "reply_to_id": message.reply_to_msg_id,
            "topic_id": getattr(message, 'topic_id', None),
            "edit_date": message.edit_date.isoformat() if message.edit_date else None,
            "views": message.views,
            "forwards": message.forwards,
            "replies": message.replies_count if message.replies else None,
            "reactions": len(message.reactions.results) if message.reactions else None,
            "attachments": self._extract_attachments(message)
        }

    def _get_peer_kind(self, message) -> str:
        """Determine peer type (user/bot/channel)."""
        if message.sender:
            if message.sender.bot:
                return "bot"
            else:
                return "user"
        return "channel"

    def _extract_attachments(self, message) -> list:
        """Extract attachment information."""
        attachments = []
        if message.media:
            # Process different media types
            if hasattr(message.media, 'photo'):
                attachments.append({"type": "photo", "size": getattr(message.media.photo, 'size', 0)})
            elif hasattr(message.media, 'document'):
                attachments.append({
                    "type": "document",
                    "mime": getattr(message.media.document, 'mime_type', ''),
                    "size": getattr(message.media.document, 'size', 0)
                })
        return attachments
```

## Data Flow Patterns

### Message Processing Pipeline
```
1. Input Validation → 2. Entity Resolution → 3. Cursor Decoding →
4. Telethon Query → 5. Date Filtering → 6. Deduplication →
7. Message Processing → 8. Pagination → 9. Resource Generation → 10. Response
```

### Error Handling Flow
```
Exception Caught → Error Classification → Payload Generation →
Response Construction → Logging → Client Notification
```

## Security Patterns

### Session Management
```python
class SecureSessionManager:
    @staticmethod
    def load_session() -> str:
        """Load session string from secure storage."""
        session = os.getenv("TELEGRAM_STRING_SESSION")
        if not session:
            raise ValueError("TELEGRAM_STRING_SESSION not configured")
        return session

    @staticmethod
    def validate_session_string(session: str) -> bool:
        """Validate session string format."""
        try:
            # Basic validation - should be base64-like
            return len(session) > 100 and not any(char in session for char in ['<', '>', '&'])
        except:
            return False
```

### PII Protection
```python
class PIIMasker:
    @staticmethod
    def mask_chat_identifier(chat_id: str) -> str:
        """Create hash-based identifier for logging."""
        return hashlib.sha256(str(chat_id).encode()).hexdigest()[:16]

    @staticmethod
    def sanitize_message_text(text: str) -> str:
        """Remove or mask sensitive information."""
        # Remove phone numbers, emails, etc.
        patterns = [
            r'\+\d{10,}',  # Phone numbers
            r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',  # Emails
        ]
        sanitized = text
        for pattern in patterns:
            sanitized = re.sub(pattern, '[REDACTED]', sanitized)
        return sanitized
```

## Performance Patterns

### Connection Pooling
```python
class ConnectionManager:
    def __init__(self):
        self._clients: dict[str, TelegramClient] = {}
        self._lock = asyncio.Lock()

    async def get_client(self, session_string: str) -> TelegramClient:
        """Get or create client for session."""
        async with self._lock:
            if session_string not in self._clients:
                client = TelegramClient(
                    StringSession(session_string),
                    api_id, api_hash
                )
                await client.start()
                self._clients[session_string] = client
            return self._clients[session_string]
```

### Resource Cleanup
```python
class ResourceCleaner:
    def __init__(self, temp_dir: str, max_age_hours: int = 24):
        self.temp_dir = Path(temp_dir)
        self.max_age = max_age_hours

    async def cleanup_old_resources(self):
        """Remove old NDJSON files."""
        cutoff = datetime.now() - timedelta(hours=self.max_age)
        for file_path in self.temp_dir.glob("*.ndjson"):
            if file_path.stat().st_mtime < cutoff.timestamp():
                file_path.unlink()

    async def cleanup_session(self):
        """Cleanup on shutdown."""
        await self.cleanup_old_resources()
```

## Observability Patterns

### Metrics Collection
```python
class MetricsCollector:
    def __init__(self):
        self.request_counter = Counter(
            'mcp_tool_calls_total',
            'Total tool calls',
            ['tool', 'status']
        )
        self.response_histogram = Histogram(
            'tg_fetch_history_duration_seconds',
            'Response time for fetch_history',
            ['chat_type']
        )

    def record_tool_call(self, tool: str, success: bool):
        """Record tool call metrics."""
        status = 'success' if success else 'error'
        self.request_counter.labels(tool=tool, status=status).inc()

    def record_response_time(self, tool: str, duration: float, chat_type: str):
        """Record response time."""
        if tool == 'tg_fetch_history':
            self.response_histogram.labels(chat_type=chat_type).observe(duration)
```

### Structured Logging
```python
class StructuredLogger:
    @staticmethod
    def log_tool_call(
        tool: str,
        chat_hash: str,
        params: dict,
        success: bool,
        duration: Optional[float] = None,
        error: Optional[str] = None
    ):
        """Log tool call with structured data."""
        log_entry = {
            'timestamp': datetime.utcnow().isoformat(),
            'tool': tool,
            'chat_hash': chat_hash,
            'params': {k: v for k, v in params.items() if k != 'session_string'},
            'success': success,
            'duration': duration,
            'error': error
        }
        logger.info(json.dumps(log_entry, ensure_ascii=False))
```

## Configuration Patterns

### Environment Configuration
```python
@dataclass
class TelegramConfig:
    api_id: int
    api_hash: str
    session_string: str
    flood_sleep_threshold: int = 60
    request_timeout: int = 30
    max_page_size: int = 100
    temp_dir: str = "/tmp/mcp-resources"

    @classmethod
    def from_env(cls) -> 'TelegramConfig':
        """Load configuration from environment variables."""
        return cls(
            api_id=int(os.getenv("TELEGRAM_API_ID")),
            api_hash=os.getenv("TELEGRAM_API_HASH"),
            session_string=os.getenv("TELEGRAM_STRING_SESSION"),
            flood_sleep_threshold=int(os.getenv("FLOOD_SLEEP_THRESHOLD", 60)),
            request_timeout=int(os.getenv("REQUEST_TIMEOUT", 30)),
            max_page_size=int(os.getenv("MAX_PAGE_SIZE", 100)),
            temp_dir=os.getenv("TEMP_DIR", "/tmp/mcp-resources")
        )
```

## Production Deployment Patterns

### 1. Docker Compose v2 Production Pattern
```yaml
services:
  telegram-mcp:
    build: .
    ports:
      - "127.0.0.1:8000:8000"  # Secure binding
    environment:
      - TELEGRAM_API_ID=${TELEGRAM_API_ID}
      - TELEGRAM_API_HASH=${TELEGRAM_API_HASH}
      - TELEGRAM_STRING_SESSION=${TELEGRAM_STRING_SESSION}
    healthcheck:
      test: ["CMD-SHELL", "curl -fsS http://localhost:8000/health || exit 1"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 40s
    restart: unless-stopped

# Commands
docker compose up -d
docker compose logs -f
curl http://localhost:8000/health
```

### 2. Nginx Streaming Proxy Pattern
```nginx
# nginx.conf for Streamable HTTP
server {
    listen 443 ssl http2;
    server_name your-domain.com;

    location /mcp {
        proxy_pass http://127.0.0.1:8000/mcp;

        # CRITICAL: Disable buffering for streaming
        proxy_buffering off;
        proxy_request_buffering off;

        # Long timeouts for streaming responses
        proxy_send_timeout 600s;
        proxy_read_timeout 600s;

        # Connection upgrade support
        proxy_http_version 1.1;
        proxy_set_header Connection "";
    }

    location /health {
        proxy_pass http://127.0.0.1:8000/health;
        proxy_buffering on;
        proxy_read_timeout 10s;
    }
}
```

### 3. Automated Deployment Pattern
```bash
#!/bin/bash
# deploy.sh - One-command production deployment

DOMAIN_NAME=${1:-"your-domain.com"}
EMAIL=${2:-"admin@your-domain.com"}

# Pre-deployment checks
if ! command -v docker &> /dev/null || ! docker compose version &> /dev/null; then
    echo "❌ Docker Compose v2 required"
    exit 1
fi

# Create directories and copy files
sudo mkdir -p /opt/telegram-toolkit-mcp
sudo chown -R $USER:$USER /opt/telegram-toolkit-mcp
cp -r . /opt/telegram-toolkit-mcp/

# Configure environment
cd /opt/telegram-toolkit-mcp
cp env.example .env
# User edits .env with credentials

# Deploy and configure
docker compose up -d
./configure-nginx.sh $DOMAIN_NAME
sudo certbot --nginx -d $DOMAIN_NAME --email $EMAIL

echo "✅ Deployment complete!"
echo "🌐 https://$DOMAIN_NAME"
```

### 4. Health Check Pattern
```python
# Health endpoint in FastMCP
@mcp.app.get("/health")
async def health_endpoint():
    """Health check for load balancers and monitoring."""
    return PlainTextResponse("OK", status_code=200)

# Docker health check
healthcheck:
  test: ["CMD-SHELL", "curl -fsS http://localhost:8000/health || exit 1"]
  interval: 30s
  timeout: 10s
  retries: 3
  start_period: 40s
```

### 5. MCP Client Integration Pattern
```json
{
  "mcpServers": {
    "telegram-toolkit": {
      "command": "npx",
      "args": ["@modelcontextprotocol/inspector", "--remote", "https://your-domain.com/mcp"]
    }
  }
}
```

```bash
# Test MCP connection
curl -X POST https://your-domain.com/mcp \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc": "2.0", "id": 1, "method": "tools/list"}'
```

## Migration Patterns

### From STDIO to HTTP Transport
```python
# OLD: STDIO transport (local only)
await mcp.run()  # Could cause event loop conflicts

# NEW: HTTP transport (production-ready)
mcp.run(transport="http", host="0.0.0.0", port=8000)

# Benefits:
# ✅ No event loop conflicts
# ✅ Remote MCP client support
# ✅ Production deployment ready
# ✅ Health checks and monitoring
# ✅ Streamable HTTP for large responses
```

### From Monolithic Scripts to Modular Architecture
```bash
# OLD: Single script approach
python scripts/run_all_tests.py  # Everything in one file

# NEW: Modular architecture
python scripts/testing/run_all_tests.py      # Master runner
python scripts/testing/run_unit_tests.py     # Unit tests only
python scripts/testing/run_integration_tests.py  # Integration only
python scripts/testing/run_e2e_tests.py      # E2E only
python scripts/testing/run_performance_tests.py  # Performance only

# Benefits:
# ✅ Separation of concerns
# ✅ Easier maintenance
# ✅ Selective test execution
# ✅ Better error isolation
# ✅ CI/CD flexibility
```

### From Docker Compose v1 to v2
```bash
# OLD: docker-compose (deprecated)
docker-compose up -d
docker-compose logs -f

# NEW: docker compose (recommended)
docker compose up -d
docker compose logs -f

# Benefits:
# ✅ Modern syntax
# ✅ Better performance
# ✅ Enhanced networking
# ✅ Improved security
```

These patterns ensure consistent, reliable, and maintainable implementation across the entire codebase, from development to enterprise production deployment.
