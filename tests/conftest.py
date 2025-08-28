"""
Pytest configuration and fixtures for Telegram Toolkit MCP.
"""

import asyncio
import tempfile
from collections.abc import Generator
from pathlib import Path

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
            api_id=12345,
            api_hash="test_hash_12345678901234567890123456789012",
            session_string=None
        ),
        server=ServerConfig(
            host="localhost",
            port=8000,
            log_level="DEBUG"
        ),
        performance=type('PerformanceConfig', (), {
            'flood_sleep_threshold': 30,
            'request_timeout': 10,
            'max_page_size': 50
        })(),
        resources=type('ResourceConfig', (), {
            'temp_dir': '/tmp/test-resources',
            'resource_max_age_hours': 1,
            'ndjson_chunk_size': 100
        })(),
        observability=type('ObservabilityConfig', (), {
            'enable_prometheus_metrics': False,
            'enable_opentelemetry_tracing': False,
            'otlp_endpoint': None
        })(),
        debug=True
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


# Test markers
def pytest_configure(config):
    """Configure pytest with custom markers."""
    config.addinivalue_line(
        "markers", "unit: Unit tests that don't require external dependencies"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests that may require mocked external services"
    )
    config.addinivalue_line(
        "markers", "e2e: End-to-end tests requiring real Telegram API access"
    )
    config.addinivalue_line(
        "markers", "slow: Tests that take significant time to run"
    )
    config.addinivalue_line(
        "markers", "telegram: Tests that interact with Telegram API"
    )


# Test data fixtures
@pytest.fixture
def sample_message_data():
    """Sample message data for testing."""
    return {
        "id": 12345,
        "date": "2025-01-01T10:30:00Z",
        "from": {
            "peer_id": "channel:136817688",
            "kind": "channel",
            "display": "Telegram"
        },
        "text": "Test message content",
        "views": 1000,
        "forwards": 50,
        "replies": 25,
        "reactions": 10
    }


@pytest.fixture
def sample_chat_data():
    """Sample chat data for testing."""
    return {
        "chat_id": "136817688",
        "kind": "channel",
        "title": "Telegram News",
        "member_count": 1000000
    }
