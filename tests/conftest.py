"""
Pytest configuration and fixtures for Telegram Toolkit MCP.
"""

import asyncio
import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import Mock, AsyncMock, MagicMock

import pytest
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
        "session_id": "test-session-456"
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
        "direction": "desc"
    }


@pytest.fixture
def mock_filter_params():
    """Fixture for mock filter parameters."""
    return {
        "media_types": ["photo", "video"],
        "has_media": True,
        "from_users": [67890, 67891],
        "min_views": 10,
        "max_views": 1000
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
                "verified": False
            },
            "views": 10 + i * 5,
            "forwards": i,
            "has_media": i % 3 == 0,  # Every third message has media
            "media_type": "photo" if i % 3 == 0 else None
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
