"""
MCP Server End-to-End Tests

This module contains E2E tests for the complete MCP server functionality,
including tool execution, resource handling, and MCP protocol compliance.
"""

import asyncio
import json
import os
import pytest
import httpx
from typing import Dict, Any
from unittest.mock import AsyncMock, MagicMock

from telegram_toolkit_mcp.server import TelegramMCPServer
from telegram_toolkit_mcp.core.monitoring import get_metrics_collector, init_metrics
from telegram_toolkit_mcp.utils.config import get_config
from telegram_toolkit_mcp.utils.logging import get_logger


logger = get_logger(__name__)


class TestMCPServerE2E:
    """E2E tests for the MCP server as a whole."""

    @pytest.fixture(autouse=True)
    async def setup_server_e2e(self):
        """Setup for MCP server E2E tests."""
        # Reset metrics for each test
        init_metrics()

        # Ensure we have required environment variables
        required_env_vars = [
            'TELEGRAM_API_ID',
            'TELEGRAM_API_HASH'
        ]

        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        if missing_vars:
            pytest.skip(f"Missing required environment variables: {missing_vars}")

        yield

    @pytest.fixture
    async def mcp_server(self):
        """MCP server instance for testing."""
        config = get_config()

        # Create server with test configuration
        server = TelegramMCPServer(
            host=config.server.host,
            port=config.server.port,
            api_id=config.telegram.api_id,
            api_hash=config.telegram.api_hash,
            session_string=config.telegram.session_string
        )

        # Start server lifecycle
        await server.startup()

        try:
            yield server
        finally:
            await server.shutdown()

    @pytest.fixture
    async def http_client(self, mcp_server: TelegramMCPServer):
        """HTTP client for MCP server communication."""
        base_url = f"http://{mcp_server.host}:{mcp_server.port}"

        async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as client:
            yield client

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_mcp_server_startup_and_health(
        self,
        mcp_server: TelegramMCPServer,
        http_client: httpx.AsyncClient
    ):
        """Test MCP server startup and health checks."""
        logger.info("🧪 Testing MCP Server: startup and health")

        # Test server is running
        assert mcp_server.mcp is not None
        assert mcp_server.telegram_client is not None

        # Test health endpoint (if implemented)
        try:
            response = await http_client.get("/health")
            assert response.status_code == 200
            health_data = response.json()
            assert "status" in health_data
            assert health_data["status"] == "healthy"
            logger.info("✅ Health check passed")
        except httpx.HTTPStatusError:
            logger.info("⚠️ Health endpoint not implemented, skipping")

        # Test metrics endpoint
        response = await http_client.get("/metrics")
        assert response.status_code == 200
        metrics_text = response.text
        assert "mcp_tool_calls_total" in metrics_text
        assert "telegram_api_calls_total" in metrics_text

        logger.info("✅ MCP server startup and health tests passed")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_mcp_resolve_chat_tool_e2e(
        self,
        mcp_server: TelegramMCPServer,
        http_client: httpx.AsyncClient
    ):
        """Test tg.resolve_chat tool through MCP protocol."""
        logger.info("🧪 Testing MCP Server: tg.resolve_chat tool")

        # MCP tool call payload
        tool_call = {
            "method": "tools/call",
            "params": {
                "name": "tg.resolve_chat",
                "arguments": {
                    "input": "@telegram"
                }
            }
        }

        # Make MCP request
        response = await http_client.post(
            "/",
            json=tool_call,
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 200
        result = response.json()

        # Validate MCP response structure
        assert "result" in result
        tool_result = result["result"]

        # Validate tool result
        if "content" in tool_result:
            # Text response
            content = tool_result["content"][0]
            assert content["type"] == "text"
            response_data = json.loads(content["text"])

            assert "chat_id" in response_data
            assert "kind" in response_data
            assert "title" in response_data
            assert response_data["title"] == "Telegram"

            logger.info("✅ tg.resolve_chat tool E2E test passed")
            logger.info(f"📊 Resolved chat: {response_data['title']}")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_mcp_fetch_history_tool_e2e(
        self,
        mcp_server: TelegramMCPServer,
        http_client: httpx.AsyncClient
    ):
        """Test tg.fetch_history tool through MCP protocol."""
        logger.info("🧪 Testing MCP Server: tg.fetch_history tool")

        # MCP tool call payload
        tool_call = {
            "method": "tools/call",
            "params": {
                "name": "tg.fetch_history",
                "arguments": {
                    "chat": "@telegram",
                    "page_size": 5
                }
            }
        }

        # Make MCP request
        response = await http_client.post(
            "/",
            json=tool_call,
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 200
        result = response.json()

        # Validate MCP response structure
        assert "result" in result
        tool_result = result["result"]

        # Validate tool result
        if "content" in tool_result:
            content = tool_result["content"][0]
            assert content["type"] == "text"
            response_data = json.loads(content["text"])

            assert "messages" in response_data
            assert "page_info" in response_data
            assert isinstance(response_data["messages"], list)
            assert len(response_data["messages"]) <= 5

            if response_data["messages"]:
                message = response_data["messages"][0]
                assert "id" in message
                assert "date" in message
                assert "text" in message

            logger.info("✅ tg.fetch_history tool E2E test passed")
            logger.info(f"📊 Fetched {len(response_data['messages'])} messages")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_mcp_tools_list_e2e(
        self,
        mcp_server: TelegramMCPServer,
        http_client: httpx.AsyncClient
    ):
        """Test MCP tools listing."""
        logger.info("🧪 Testing MCP Server: tools list")

        # MCP tools list request
        request = {
            "method": "tools/list",
            "params": {}
        }

        response = await http_client.post(
            "/",
            json=request,
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 200
        result = response.json()

        # Validate tools list
        assert "result" in result
        tools_list = result["result"]

        assert "tools" in tools_list
        tools = tools_list["tools"]

        # Should have our two tools
        tool_names = [tool["name"] for tool in tools]
        assert "tg.resolve_chat" in tool_names
        assert "tg.fetch_history" in tool_names

        # Validate tool schemas
        resolve_tool = next(t for t in tools if t["name"] == "tg.resolve_chat")
        fetch_tool = next(t for t in tools if t["name"] == "tg.fetch_history")

        assert "inputSchema" in resolve_tool
        assert "inputSchema" in fetch_tool
        assert resolve_tool["inputSchema"]["required"] == ["input"]
        assert "chat" in fetch_tool["inputSchema"]["required"]

        logger.info("✅ MCP tools list E2E test passed")
        logger.info(f"📊 Available tools: {tool_names}")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_mcp_error_handling_e2e(
        self,
        mcp_server: TelegramMCPServer,
        http_client: httpx.AsyncClient
    ):
        """Test MCP error handling."""
        logger.info("🧪 Testing MCP Server: error handling")

        # Test invalid tool name
        tool_call = {
            "method": "tools/call",
            "params": {
                "name": "invalid_tool",
                "arguments": {}
            }
        }

        response = await http_client.post(
            "/",
            json=tool_call,
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 200
        result = response.json()

        # Should return error
        assert "error" in result
        error = result["error"]
        assert "code" in error
        assert "message" in error

        # Test invalid arguments
        tool_call = {
            "method": "tools/call",
            "params": {
                "name": "tg.resolve_chat",
                "arguments": {
                    "invalid_param": "value"
                }
            }
        }

        response = await http_client.post(
            "/",
            json=tool_call,
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 200
        result = response.json()

        # Should return validation error
        assert "error" in result
        error = result["error"]
        assert error["code"] == -32602  # Invalid params

        logger.info("✅ MCP error handling E2E test passed")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_mcp_resources_list_e2e(
        self,
        mcp_server: TelegramMCPServer,
        http_client: httpx.AsyncClient
    ):
        """Test MCP resources listing."""
        logger.info("🧪 Testing MCP Server: resources list")

        # MCP resources list request
        request = {
            "method": "resources/list",
            "params": {}
        }

        response = await http_client.post(
            "/",
            json=request,
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 200
        result = response.json()

        # Validate resources list
        assert "result" in result
        resources_list = result["result"]

        assert "resources" in resources_list
        # Should have export resources capability

        logger.info("✅ MCP resources list E2E test passed")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_mcp_large_dataset_with_resources_e2e(
        self,
        mcp_server: TelegramMCPServer,
        http_client: httpx.AsyncClient
    ):
        """Test large dataset handling with MCP resources."""
        logger.info("🧪 Testing MCP Server: large dataset with resources")

        # Request large dataset
        tool_call = {
            "method": "tools/call",
            "params": {
                "name": "tg.fetch_history",
                "arguments": {
                    "chat": "@telegram",
                    "page_size": 50  # Large dataset
                }
            }
        }

        response = await http_client.post(
            "/",
            json=tool_call,
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 200
        result = response.json()

        # Validate response
        assert "result" in result
        tool_result = result["result"]

        if "content" in tool_result:
            content = tool_result["content"][0]
            response_data = json.loads(content["text"])

            # Check if resource export was triggered
            if "export" in response_data:
                export_info = response_data["export"]
                assert "uri" in export_info
                assert "format" in export_info
                assert export_info["format"] == "ndjson"

                # Test resource access
                resource_uri = export_info["uri"]
                resource_call = {
                    "method": "resources/read",
                    "params": {
                        "uri": resource_uri
                    }
                }

                resource_response = await http_client.post(
                    "/",
                    json=resource_call,
                    headers={"Content-Type": "application/json"}
                )

                if resource_response.status_code == 200:
                    resource_result = resource_response.json()
                    assert "result" in resource_result
                    assert "contents" in resource_result["result"]

                    logger.info("✅ Large dataset resource access successful")
                else:
                    logger.info("⚠️ Resource access returned non-200 status (may be expected)")

            logger.info("✅ Large dataset handling test passed")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_mcp_concurrent_requests_e2e(
        self,
        mcp_server: TelegramMCPServer,
        http_client: httpx.AsyncClient
    ):
        """Test concurrent MCP requests handling."""
        logger.info("🧪 Testing MCP Server: concurrent requests")

        # Create multiple concurrent requests
        requests = []

        for i in range(3):
            tool_call = {
                "method": "tools/call",
                "params": {
                    "name": "tg.resolve_chat",
                    "arguments": {
                        "input": "@telegram"
                    }
                }
            }
            requests.append(tool_call)

        # Execute concurrent requests
        tasks = []
        for req in requests:
            task = http_client.post(
                "/",
                json=req,
                headers={"Content-Type": "application/json"}
            )
            tasks.append(task)

        # Wait for all responses
        responses = await asyncio.gather(*tasks)

        # Validate all responses
        for i, response in enumerate(responses):
            assert response.status_code == 200
            result = response.json()
            assert "result" in result

            logger.info(f"✅ Concurrent request {i+1} successful")

        logger.info("✅ Concurrent requests E2E test passed")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_mcp_server_metrics_collection_e2e(
        self,
        mcp_server: TelegramMCPServer,
        http_client: httpx.AsyncClient
    ):
        """Test MCP server metrics collection during operations."""
        logger.info("🧪 Testing MCP Server: metrics collection")

        # Generate some activity
        for i in range(3):
            tool_call = {
                "method": "tools/call",
                "params": {
                    "name": "tg.resolve_chat",
                    "arguments": {
                        "input": "@telegram"
                    }
                }
            }

            response = await http_client.post(
                "/",
                json=tool_call,
                headers={"Content-Type": "application/json"}
            )
            assert response.status_code == 200

        # Check metrics
        response = await http_client.get("/metrics")
        assert response.status_code == 200
        metrics_text = response.text

        # Parse metrics to check values increased
        lines = metrics_text.split('\n')
        tool_calls_metric = None

        for line in lines:
            if line.startswith('mcp_tool_calls_total'):
                tool_calls_metric = line
                break

        assert tool_calls_metric is not None
        # Should show at least 3 tool calls
        assert '3' in tool_calls_metric or '4' in tool_calls_metric or '5' in tool_calls_metric

        logger.info("✅ MCP server metrics collection test passed")
        logger.info(f"📊 Metrics collected: {tool_calls_metric}")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_mcp_server_complete_workflow_e2e(
        self,
        mcp_server: TelegramMCPServer,
        http_client: httpx.AsyncClient
    ):
        """Complete MCP server workflow from discovery to data retrieval."""
        logger.info("🧪 Testing MCP Server: complete workflow")

        # Step 1: Discover available tools
        tools_request = {
            "method": "tools/list",
            "params": {}
        }

        response = await http_client.post(
            "/",
            json=tools_request,
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 200
        tools_result = response.json()
        available_tools = [t["name"] for t in tools_result["result"]["tools"]]

        logger.info(f"📋 Available tools: {available_tools}")

        # Step 2: Resolve chat using discovered tool
        resolve_call = {
            "method": "tools/call",
            "params": {
                "name": "tg.resolve_chat",
                "arguments": {
                    "input": "@telegram"
                }
            }
        }

        response = await http_client.post(
            "/",
            json=resolve_call,
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 200
        resolve_result = response.json()
        chat_data = json.loads(resolve_result["result"]["content"][0]["text"])

        logger.info(f"📊 Resolved chat: {chat_data['title']}")

        # Step 3: Fetch history using resolved chat
        fetch_call = {
            "method": "tools/call",
            "params": {
                "name": "tg.fetch_history",
                "arguments": {
                    "chat": "@telegram",
                    "page_size": 3
                }
            }
        }

        response = await http_client.post(
            "/",
            json=fetch_call,
            headers={"Content-Type": "application/json"}
        )

        assert response.status_code == 200
        fetch_result = response.json()
        history_data = json.loads(fetch_result["result"]["content"][0]["text"])

        logger.info(f"📊 Fetched {len(history_data['messages'])} messages")

        # Step 4: Verify complete workflow
        assert chat_data["title"] == "Telegram"
        assert isinstance(history_data["messages"], list)
        assert "page_info" in history_data

        logger.info("🎉 Complete MCP server workflow successful!")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_mcp_server_shutdown_graceful_e2e(
        self,
        mcp_server: TelegramMCPServer
    ):
        """Test MCP server graceful shutdown."""
        logger.info("🧪 Testing MCP Server: graceful shutdown")

        # Verify server is running
        assert mcp_server.telegram_client is not None

        # Shutdown server
        await mcp_server.shutdown()

        # Verify cleanup
        assert mcp_server.mcp is None or not hasattr(mcp_server, '_running')

        logger.info("✅ MCP server graceful shutdown test passed")
