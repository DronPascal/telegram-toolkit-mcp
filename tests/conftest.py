"""
Pytest configuration and fixtures for Telegram Toolkit MCP.
"""

import asyncio
import os
import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import pytest_asyncio
from dotenv import load_dotenv

# Load test environment
load_dotenv(".env.test")


@pytest.fixture(scope="session")
def event_loop():
    """Create an instance of the default event loop for the test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
def temp_dir() -> Generator[Path, None, None]:
    """Create a temporary directory for tests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        yield Path(temp_dir)


@pytest.fixture
def error_tracker():
    """Error tracker fixture for tests."""
    from src.telegram_toolkit_mcp.core.error_handler import ErrorTracker

    return ErrorTracker()


@pytest.fixture(scope="session")
def test_config():
    """Test configuration fixture."""
    from telegram_toolkit_mcp.utils.config import AppConfig, ServerConfig, TelegramConfig

    # Mock configuration for tests
    return AppConfig(
        telegram=TelegramConfig(
            api_id=12345, api_hash="test_hash_12345678901234567890123456789012", session_string=None
        ),
        server=ServerConfig(host="localhost", port=8000, log_level="DEBUG"),
        performance=type(
            "PerformanceConfig",
            (),
            {"flood_sleep_threshold": 30, "request_timeout": 10, "max_page_size": 50},
        )(),
        resources=type(
            "ResourceConfig",
            (),
            {
                "temp_dir": "/tmp/test-resources",
                "resource_max_age_hours": 1,
                "ndjson_chunk_size": 100,
            },
        )(),
        observability=type(
            "ObservabilityConfig",
            (),
            {
                "enable_prometheus_metrics": False,
                "enable_opentelemetry_tracing": False,
                "otlp_endpoint": None,
            },
        )(),
        debug=True,
    )


@pytest.fixture(autouse=True)
def setup_test_environment(monkeypatch, temp_dir):
    """Set up test environment variables and directories."""
    # Set test environment variables
    monkeypatch.setenv("TELEGRAM_API_ID", "12345")
    monkeypatch.setenv("TELEGRAM_API_HASH", "test_hash_12345678901234567890123456789012")
    monkeypatch.setenv("TEMP_DIR", str(temp_dir))
    monkeypatch.setenv("DEBUG", "true")

    # Ensure test directories exist
    (temp_dir / "resources").mkdir(exist_ok=True)


@pytest.fixture
async def mock_telegram_client():
    """Mock Telegram client for testing."""

    # This would be replaced with actual mocking in real tests
    class MockClient:
        async def start(self):
            pass

        async def disconnect(self):
            pass

        def iter_messages(self, *args, **kwargs):
            # Return empty async iterator for tests
            return self._empty_iterator()

        async def _empty_iterator(self):
            return
            yield  # Make it an async generator

    return MockClient()


# Additional test fixtures
@pytest.fixture
def mock_prometheus_registry():
    """Fixture for Prometheus registry in tests."""
    from prometheus_client import CollectorRegistry

    return CollectorRegistry()


@pytest.fixture
def mock_metrics_collector(mock_prometheus_registry):
    """Fixture for metrics collector with test registry."""
    from src.telegram_toolkit_mcp.core.monitoring import MetricsCollector

    return MetricsCollector(registry=mock_prometheus_registry)


@pytest.fixture
def mock_security_context():
    """Fixture for security testing context."""
    return {
        "client_ip": "192.168.1.100",
        "user_agent": "TestClient/1.0",
        "request_id": "test-request-123",
        "session_id": "test-session-456",
    }


@pytest.fixture
def mock_cursor():
    """Fixture for mock pagination cursor."""
    return {
        "offset_id": 12345,
        "offset_date": 1640995200,
        "min_id": None,
        "max_id": None,
        "fetched_count": 50,
        "direction": "desc",
    }


@pytest.fixture
def mock_filter_params():
    """Fixture for mock filter parameters."""
    return {
        "media_types": ["photo", "video"],
        "has_media": True,
        "from_users": [67890, 67891],
        "min_views": 10,
        "max_views": 1000,
    }


@pytest.fixture
def sample_messages():
    """Fixture providing a list of sample message dictionaries."""
    base_time = 1640995200.0  # 2022-01-01 00:00:00 UTC

    return [
        {
            "id": 12340 + i,
            "date": base_time + (i * 3600),  # One hour apart
            "text": f"Test message {i}",
            "out": False,
            "mentioned": False,
            "media_unread": False,
            "silent": False,
            "post": False,
            "from_scheduled": False,
            "legacy": False,
            "edit_hide": False,
            "pinned": False,
            "noforwards": False,
            "sender": {
                "id": 67890 + i,
                "first_name": f"User{i}",
                "last_name": "Test",
                "username": f"user{i}",
                "bot": False,
                "verified": False,
            },
            "views": 10 + i * 5,
            "forwards": i,
            "has_media": i % 3 == 0,  # Every third message has media
            "media_type": "photo" if i % 3 == 0 else None,
        }
        for i in range(10)
    ]


@pytest.fixture
def mock_telethon_message():
    """Fixture for mocked Telethon message object."""
    message = MagicMock()

    # Basic message attributes
    message.id = 12345
    message.date.timestamp.return_value = 1640995200.0  # 2022-01-01 00:00:00 UTC
    message.text = "Test message content"
    message.out = False
    message.mentioned = False
    message.media_unread = False
    message.silent = False
    message.post = False
    message.from_scheduled = False
    message.legacy = False
    message.edit_hide = False
    message.pinned = False
    message.noforwards = False

    # Mock sender
    sender = MagicMock()
    sender.id = 67890
    sender.first_name = "Test"
    sender.last_name = "User"
    sender.username = "testuser"
    sender.bot = False
    sender.verified = False
    message.sender = sender

    # Mock views and forwards
    message.views = 42
    message.forwards = 5

    # Mock media
    message.media = None

    return message


@pytest.fixture
def mock_telethon_channel():
    """Fixture for mocked Telethon channel entity."""
    channel = MagicMock()

    # Basic channel attributes
    channel.id = 123456789
    channel.title = "Test Channel"
    channel.username = "testchannel"
    channel.participants_count = 1000
    channel.verified = True
    channel.restricted = False
    channel.megagroup = False
    channel.gigagroup = False
    channel.broadcast = True  # This is a broadcast channel

    return channel


# Test markers
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line("markers", "unit: Unit tests that don't require external dependencies")
    config.addinivalue_line(
        "markers", "integration: Integration tests that may require mocked external services"
    )
    config.addinivalue_line("markers", "e2e: End-to-end tests requiring real Telegram API access")
    config.addinivalue_line("markers", "slow: Tests that take significant time to run")
    config.addinivalue_line("markers", "telegram: Tests that interact with Telegram API")
    config.addinivalue_line("markers", "security: Security-related tests")
    config.addinivalue_line("markers", "metrics: Metrics-related tests")
    config.addinivalue_line("markers", "rate_limit: Rate limiting tests")


# Test data fixtures
@pytest.fixture
def sample_message_data():
    """Sample message data for testing."""
    return {
        "id": 12345,
        "date": "2025-01-01T10:30:00Z",
        "from": {"peer_id": "channel:136817688", "kind": "channel", "display": "Telegram"},
        "text": "Test message content",
        "views": 1000,
        "forwards": 50,
        "replies": 25,
        "reactions": 10,
    }


@pytest.fixture
def sample_chat_data():
    """Sample chat data for testing."""
    return {
        "chat_id": "136817688",
        "kind": "channel",
        "title": "Telegram News",
        "member_count": 1000000,
    }


# E2E Test Fixtures


@pytest.fixture(scope="session")
def e2e_test_config():
    """Configuration for E2E tests."""
    return {
        "test_chat": "@telegram",
        "test_timeout": 30,
        "max_page_size": 50,
        "min_messages_for_large_test": 10,
    }


@pytest.fixture
def e2e_test_data():
    """Test data for E2E scenarios."""
    return {
        "valid_chats": [
            "@telegram",
            "https://t.me/telegram",
            "telegram",
        ],
        "invalid_chats": [
            "invalid_chat_123",
            "",
            "@",
        ],
        "test_page_sizes": [5, 10, 25, 50],
        "test_filters": {
            "basic": {},
            "with_media": {"has_media": True},
            "text_only": {"media_types": ["text"]},
            "popular": {"min_views": 100},
        },
    }


@pytest.fixture
def mock_mcp_request():
    """Mock MCP request for testing."""

    def _make_request(method: str, **params):
        return {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}

    return _make_request


@pytest.fixture
def expected_mcp_response():
    """Expected MCP response structure for validation."""
    return {
        "jsonrpc": "2.0",
        "id": 1,
        "result": {
            "content": [
                {
                    "type": "text",
                    "text": "{}",  # Will be filled with actual data
                }
            ]
        },
    }


@pytest.fixture()
def e2e_skip_without_credentials():
    """Skip E2E tests if Telegram credentials are not available."""
    required_vars = ["TELEGRAM_API_ID", "TELEGRAM_API_HASH"]
    missing = [var for var in required_vars if not os.getenv(var)]

    if missing:
        pytest.skip(f"E2E tests require: {', '.join(missing)}")


@pytest.fixture(scope="session")
def e2e_performance_thresholds():
    """Performance thresholds for E2E tests."""
    return {
        "chat_resolution_max_time": 5.0,  # seconds
        "message_fetch_max_time": 10.0,  # seconds
        "large_dataset_max_time": 15.0,  # seconds
        "min_messages_per_page": 1,
        "max_messages_per_page": 100,
    }


@pytest.fixture
def e2e_error_scenarios():
    """Error scenarios for E2E testing."""
    return {
        "invalid_chat": {"input": "invalid_chat_12345", "expected_error": "CHAT_NOT_FOUND"},
        "private_channel": {"input": "@some_private_channel", "expected_error": "CHANNEL_PRIVATE"},
        "invalid_parameters": {
            "chat": "@telegram",
            "page_size": 1000,  # Too large
            "expected_error": "VALIDATION_ERROR",
        },
        "rate_limit_exceeded": {"chat": "@telegram", "expected_error": "FLOOD_WAIT"},
    }


@pytest.fixture
def e2e_workflow_steps():
    """Complete workflow steps for E2E testing."""
    return [
        {
            "step": "discover_tools",
            "method": "tools/list",
            "expected_tools": ["tg.resolve_chat", "tg.fetch_history"],
        },
        {
            "step": "resolve_chat",
            "method": "tools/call",
            "tool": "tg.resolve_chat",
            "args": {"input": "@telegram"},
            "expected_fields": ["chat_id", "title", "kind"],
        },
        {
            "step": "fetch_history",
            "method": "tools/call",
            "tool": "tg.fetch_history",
            "args": {"chat": "@telegram", "page_size": 5},
            "expected_fields": ["messages", "page_info"],
        },
        {
            "step": "pagination",
            "method": "tools/call",
            "tool": "tg.fetch_history",
            "args": {"chat": "@telegram", "page_size": 10},
            "expected_pagination": ["has_more", "cursor"],
        },
    ]


@pytest.fixture
def e2e_concurrency_config():
    """Configuration for concurrent request testing."""
    return {
        "max_concurrent_requests": 5,
        "request_delay": 0.1,  # seconds between requests
        "timeout_per_request": 30,  # seconds
    }


@pytest.fixture
def e2e_monitoring_checks():
    """Monitoring and metrics validation for E2E tests."""
    return {
        "required_metrics": [
            "mcp_tool_calls_total",
            "telegram_api_calls_total",
            "telegram_messages_fetched_total",
            "telegram_toolkit_errors_total",
        ],
        "success_rate_threshold": 0.95,  # 95% success rate minimum
        "max_error_rate": 0.05,  # 5% error rate maximum
        "min_metrics_updates": 1,  # At least 1 metric should update
    }


@pytest.fixture
def e2e_cleanup_config():
    """Configuration for E2E test cleanup."""
    return {
        "temp_file_cleanup": True,
        "metric_reset": True,
        "connection_cleanup": True,
        "resource_cleanup_timeout": 5,  # seconds
    }


@pytest_asyncio.fixture
async def mcp_server():
    """MCP server instance for testing."""
    from telegram_toolkit_mcp.server import TelegramMCPServer

    # Create server (configuration loaded automatically from environment)
    server = TelegramMCPServer()

    # Use lifespan context manager for proper startup/shutdown
    async with server.lifespan():
        yield server


@pytest_asyncio.fixture
async def http_server():
    """HTTP server instance for E2E testing."""
    import asyncio
    import os
    import time

    from telegram_toolkit_mcp.server import TelegramMCPServer

    server = TelegramMCPServer()

    # Start HTTP server as subprocess
    server_ready_file = f"/tmp/mcp_server_ready_{os.getpid()}"

    # Remove ready file if exists
    if os.path.exists(server_ready_file):
        os.remove(server_ready_file)

    def run_http_server():
        """Run HTTP server as subprocess."""
        try:
            # Create new event loop
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            async def start_server():
                async with server.lifespan():
                    # Signal that server is ready
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(
                        None, lambda: open(server_ready_file, "w").__enter__().write("ready")
                    )
                    # Run HTTP server
                    server.run_server_sync()

            # Run the server
            loop.run_until_complete(start_server())
        except Exception as e:  # type: ignore[BLE001]
            print(f"HTTP server subprocess error: {e}")
        finally:
            # Cleanup ready file
            if os.path.exists(server_ready_file):
                os.remove(server_ready_file)

    # Start server in background thread with new event loop
    import threading

    def start_server_thread():
        """Start server in separate thread with new event loop."""
        server_thread = threading.Thread(target=run_http_server, daemon=True)
        server_thread.start()
        return server_thread

    start_server_thread()

    # Wait for server to be ready (with timeout)
    timeout = 20
    start_time = time.time()
    while time.time() - start_time < timeout:
        if os.path.exists(server_ready_file):
            # Give server a moment to fully initialize
            await asyncio.sleep(1)
            yield server
            # Cleanup
            if os.path.exists(server_ready_file):
                os.remove(server_ready_file)
            return
        await asyncio.sleep(0.1)

    # Timeout reached
    raise RuntimeError(f"HTTP server failed to start within {timeout} seconds")
