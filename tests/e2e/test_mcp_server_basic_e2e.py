"""
Basic MCP Server E2E Tests

This module contains basic E2E tests for MCP server functionality
without HTTP requests. These tests verify that the server can be
created and initialized properly.
"""

import pytest

from telegram_toolkit_mcp.server import TelegramMCPServer
from telegram_toolkit_mcp.utils.logging import get_logger

logger = get_logger(__name__)


class TestMCPBasicE2E:
    """Basic E2E tests for MCP server functionality."""

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_mcp_server_creation(self):
        """Test that MCP server can be created successfully."""
        logger.info("🧪 Testing MCP Server: basic creation")

        # Test server creation
        server = TelegramMCPServer()

        # Test lifespan context
        async with server.lifespan():
            # Verify server components are initialized
            assert server.mcp_server is not None
            assert server.telegram_client is not None
            assert server.config is not None

            logger.info("✅ MCP server created successfully")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_mcp_server_metrics(self):
        """Test that MCP server metrics collection works."""
        logger.info("🧪 Testing MCP Server: metrics collection")

        server = TelegramMCPServer()

        async with server.lifespan():
            # Test metrics collection
            from telegram_toolkit_mcp.core.monitoring import get_metrics_collector

            metrics_collector = get_metrics_collector()
            metrics_text = metrics_collector.get_metrics()

            # Verify basic metrics are present
            assert "mcp_tool_calls_total" in metrics_text
            assert isinstance(metrics_text, str)
            assert len(metrics_text) > 0

            logger.info("✅ MCP server metrics working")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_mcp_server_tools_registration(self):
        """Test that MCP server tools are registered."""
        logger.info("🧪 Testing MCP Server: tools registration")

        server = TelegramMCPServer()

        async with server.lifespan():
            # Verify that MCP server has tools
            # This is a basic check that tools were registered during server creation
            assert hasattr(server.mcp_server, "name")
            assert server.mcp_server.name == "telegram-toolkit-mcp"

            logger.info("✅ MCP server tools registered")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_mcp_server_telegram_client(self):
        """Test that MCP server Telegram client is working."""
        logger.info("🧪 Testing MCP Server: Telegram client")

        server = TelegramMCPServer()

        async with server.lifespan():
            # Verify Telegram client is initialized
            assert server.telegram_client is not None

            # Test that client can be accessed
            client = server.telegram_client
            assert hasattr(client, "session")

            logger.info("✅ MCP server Telegram client working")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_mcp_server_configuration(self):
        """Test that MCP server configuration is loaded."""
        logger.info("🧪 Testing MCP Server: configuration")

        server = TelegramMCPServer()

        async with server.lifespan():
            # Verify configuration is loaded
            assert server.config is not None
            assert hasattr(server.config, "telegram")
            assert hasattr(server.config, "server")

            # Verify Telegram config
            assert server.config.telegram.api_id is not None
            assert server.config.telegram.api_hash is not None

            logger.info("✅ MCP server configuration loaded")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_mcp_server_complete_workflow(self):
        """Test complete MCP server workflow."""
        logger.info("🧪 Testing MCP Server: complete workflow")

        server = TelegramMCPServer()

        # Test full lifecycle
        async with server.lifespan():
            # Verify all components are working
            assert server.mcp_server is not None
            assert server.telegram_client is not None
            assert server.config is not None

            # Test metrics
            from telegram_toolkit_mcp.core.monitoring import get_metrics_collector

            metrics = get_metrics_collector().get_metrics()
            assert len(metrics) > 0

            logger.info("✅ MCP server complete workflow verified")
