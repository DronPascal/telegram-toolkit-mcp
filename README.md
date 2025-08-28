# Telegram Toolkit MCP

[![Python 3.11+](https://img.shields.io/badge/python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache-yellow.svg)](https://opensource.org/licenses/apache-2-0)
[![MCP 2025-06-18](https://img.shields.io/badge/MCP-2025--06--18-green.svg)](https://modelcontextprotocol.io/)

**Read-only MCP server for safe extraction of Telegram message history from public chats with proper pagination, error handling, and NDJSON resource streaming.**

## 🚀 Features

- **MCP 2025-06-18 Compliant**: Full compliance with latest Model Context Protocol specification
- **Read-Only Access**: Safe extraction from public Telegram channels only
- **Advanced Pagination**: Cursor-based navigation with date filtering
- **NDJSON Streaming**: Efficient large dataset exports
- **Error Resilience**: Comprehensive FLOOD_WAIT handling with retry logic
- **Observability**: Built-in Prometheus metrics and OpenTelemetry tracing
- **Security First**: PII protection, secure session management
- **Production Ready**: Async architecture with proper resource cleanup

## 📋 Table of Contents

- [Quick Start](#quick-start)
- [Installation](#installation)
- [Configuration](#configuration)
- [Usage](#usage)
- [MCP Tools](#mcp-tools)
- [API Reference](#api-reference)
- [Development](#development)
- [Contributing](#contributing)
- [License](#license)

## 🚀 Quick Start

```bash
# 1. Install
pip install telegram-toolkit-mcp

# 2. Configure (copy and edit)
cp env.example .env
# Edit .env with your Telegram API credentials

# 3. Run
telegram-mcp-server

# 4. Connect your MCP client
# Server will be available at http://localhost:8000
```

## 📦 Installation

### From PyPI (recommended)
```bash
pip install telegram-toolkit-mcp
```

### From Source
```bash
git clone https://github.com/your-org/telegram-toolkit-mcp.git
cd telegram-toolkit-mcp
pip install -e .
```

### Development Setup
```bash
git clone https://github.com/your-org/telegram-toolkit-mcp.git
cd telegram-toolkit-mcp
pip install -e ".[dev,observability]"
```

## ⚙️ Configuration

### Environment Variables

Copy `env.example` to `.env` and configure:

```bash
# Required: Telegram API credentials
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_STRING_SESSION=  # Will be auto-generated

# Optional: Server settings
MCP_SERVER_HOST=localhost
MCP_SERVER_PORT=8000
MAX_PAGE_SIZE=100

# Optional: Performance tuning
FLOOD_SLEEP_THRESHOLD=60
REQUEST_TIMEOUT=30

# Optional: Observability
ENABLE_PROMETHEUS_METRICS=true
ENABLE_OPENTELEMETRY_TRACING=true
```

### Getting Telegram API Credentials

1. Go to https://my.telegram.org/auth
2. Log in with your phone number
3. Go to "API development tools"
4. Create an application to get `api_id` and `api_hash`

## 🎯 Usage

### Basic Usage

```python
import asyncio
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def main():
    # Connect to MCP server
    async with stdio_client([
        "telegram-mcp-server"
    ]) as (read, write):
        async with ClientSession(read, write) as session:
            # Resolve chat
            result = await session.call_tool(
                "tg.resolve_chat",
                {"input": "@telegram"}
            )
            print(result)  # {"chat_id": "136817688", "kind": "channel"}

            # Fetch messages
            result = await session.call_tool(
                "tg.fetch_history",
                {
                    "chat": "@telegram",
                    "from": "2025-01-01T00:00:00Z",
                    "to": "2025-01-02T00:00:00Z",
                    "page_size": 50
                }
            )
            print(result)  # Structured message data with pagination

asyncio.run(main())
```

### With Claude Desktop

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "telegram-toolkit": {
      "command": "telegram-mcp-server",
      "env": {
        "TELEGRAM_API_ID": "your_api_id",
        "TELEGRAM_API_HASH": "your_api_hash",
        "TELEGRAM_STRING_SESSION": "your_session_string"
      }
    }
  }
}
```

## 🔧 MCP Tools

### `tg.resolve_chat`

Resolves chat identifiers to internal format.

**Input:**
```json
{
  "input": "@telegram"
}
```

**Output:**
```json
{
  "chat_id": "136817688",
  "kind": "channel",
  "title": "Telegram News"
}
```

### `tg.fetch_history`

Fetches message history with pagination and filtering.

**Input:**
```json
{
  "chat": "@telegram",
  "from": "2025-01-01T00:00:00Z",
  "to": "2025-01-02T00:00:00Z",
  "page_size": 100,
  "cursor": "base64_encoded_cursor",
  "search": "bitcoin",
  "filter": "links"
}
```

**Output:**
```json
{
  "messages": [
    {
      "id": 12345,
      "date": "2025-01-01T10:30:00Z",
      "from": {
        "peer_id": "channel:136817688",
        "kind": "channel",
        "display": "Telegram"
      },
      "text": "Breaking news...",
      "views": 10000,
      "forwards": 500
    }
  ],
  "page_info": {
    "cursor": "next_cursor_base64",
    "has_more": true,
    "count": 100,
    "fetched": 100
  },
  "export": {
    "uri": "mcp://resources/export/telegram.ndjson",
    "format": "ndjson"
  }
}
```

## 📚 API Reference

### Response Format

All tools return MCP-compliant responses with:

1. **content[]**: Human-readable summary (for compatibility)
2. **structuredContent**: Machine-readable data with JSON Schema validation
3. **Resources**: NDJSON exports for large datasets (when applicable)

### Error Handling

Standardized error codes:
- `FLOOD_WAIT`: Rate limit exceeded, includes retry_after
- `CHANNEL_PRIVATE`: Access denied to private channel
- `USERNAME_INVALID`: Invalid chat identifier
- `INPUT_VALIDATION`: Invalid request parameters

### Pagination

- **Cursor-based**: Opaque base64-encoded cursors
- **Date filtering**: Server-side UTC filtering
- **Deduplication**: Automatic message deduplication
- **Resource limits**: Max 100 messages per page

## 🛠️ Development

### Setting up Development Environment

```bash
# Clone repository
git clone https://github.com/your-org/telegram-toolkit-mcp.git
cd telegram-toolkit-mcp

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# .venv\Scripts\activate   # Windows

# Install development dependencies
pip install -e ".[dev,observability]"

# Set up pre-commit hooks
pre-commit install

# Run tests
pytest
```

### Project Structure

```
telegram-toolkit-mcp/
├── src/telegram_toolkit_mcp/
│   ├── __init__.py
│   ├── server.py              # FastMCP server
│   ├── tools/                 # MCP tool implementations
│   │   ├── resolve_chat.py
│   │   └── fetch_history.py
│   ├── models/                # Pydantic models
│   │   ├── types.py
│   │   └── schemas.py
│   ├── core/                  # Business logic
│   │   ├── telegram_client.py
│   │   ├── pagination.py
│   │   └── error_handler.py
│   └── utils/                 # Utilities
│       ├── logging.py
│       └── security.py
├── tests/
│   ├── unit/
│   ├── integration/
│   └── e2e/
├── docs/
├── pyproject.toml
├── .gitignore
├── .cursorignore
└── README.md
```

### Running Tests

```bash
# Unit tests
pytest tests/unit/

# Integration tests
pytest tests/integration/

# End-to-end tests (requires Telegram API)
pytest tests/e2e/

# All tests with coverage
pytest --cov=telegram_toolkit_mcp
```

## 🤝 Contributing

We welcome contributions! Please see our [Contributing Guide](CONTRIBUTING.md) for details.

### Development Guidelines

1. **Code Quality**: Follow PEP 8, use type hints, maintain test coverage >90%
2. **Security**: Never log PII, validate all inputs, handle secrets securely
3. **Performance**: Optimize for memory usage and API call efficiency
4. **Compatibility**: Maintain MCP specification compliance
5. **Documentation**: Update docs for any API changes

### Testing Channels

For E2E testing, we use these public channels:
- `@telegram` - Official Telegram news
- `@bloomberg` - Financial news
- `@apod_telegram` - NASA Astronomy Picture of the Day

## 📊 Observability

### Metrics (Prometheus)

The server exposes metrics at `/metrics`:
- `mcp_tool_calls_total{tool,status}` - Tool call counts
- `tg_fetch_history_messages_total` - Messages processed
- `tg_fetch_history_duration_seconds` - Response times
- `telegram_floodwait_seconds` - FLOOD_WAIT durations

### Tracing (OpenTelemetry)

Distributed tracing for request flows with:
- Tool execution spans
- Telegram API call spans
- Resource generation spans

## ⚖️ License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## ⚠️ Disclaimer

This is an unofficial project and is not affiliated with Telegram. Use responsibly and in accordance with Telegram's Terms of Service. Only access public channels and respect rate limits.

## 🙏 Acknowledgments

- [Telethon](https://github.com/LonamiWebs/Telethon) for Telegram API client
- [MCP](https://modelcontextprotocol.io/) for the protocol specification
- [FastMCP](https://github.com/modelcontextprotocol/python-sdk) for Python SDK
