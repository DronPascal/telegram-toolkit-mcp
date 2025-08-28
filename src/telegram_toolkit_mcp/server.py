"""
Telegram Toolkit MCP Server - FastMCP-based server implementation.

This module provides the main MCP server implementation with lifespan management,
tool registration, and resource handling for Telegram message extraction.
"""

import asyncio
import signal
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

try:
    from mcp import FastMCP
except ImportError:
    # Fallback for development
    FastMCP = None

from .utils.config import get_config, validate_telegram_credentials
from .utils.logging import get_logger
from .core.monitoring import init_metrics, get_metrics_collector
from .core.tracing import init_tracing, shutdown_tracing, instrument_fastapi

logger = get_logger(__name__)


class TelegramMCPServer:
    """
    MCP Server for Telegram message history extraction.

    This server provides MCP tools for safely accessing public Telegram
    chat history with proper pagination, filtering, and error handling.
    """

    def __init__(self) -> None:
        """Initialize the MCP server with configuration."""
        self.config = get_config()
        self.mcp_server: FastMCP | None = None
        self.telegram_client = None
        self._shutdown_event = asyncio.Event()

        # Validate configuration on startup
        self._validate_configuration()

        # Initialize metrics
        self.metrics_collector = init_metrics()
        logger.info("Metrics collector initialized")

    def _validate_configuration(self) -> None:
        """Validate server configuration and credentials."""
        logger.info("Validating server configuration", config_valid=True)

        # Validate Telegram credentials
        if not validate_telegram_credentials(self.config):
            logger.error(
                "Invalid Telegram API credentials",
                api_id_provided=bool(self.config.telegram.api_id),
                api_hash_provided=bool(self.config.telegram.api_hash),
            )
            raise ValueError(
                "Invalid Telegram API credentials. Please check TELEGRAM_API_ID "
                "and TELEGRAM_API_HASH environment variables."
            )

        logger.info("Configuration validation successful")

    async def initialize_telegram_client(self) -> None:
        """
        Initialize and start the Telegram client.

        This method sets up the Telethon client with proper session management
        and connects to Telegram servers.
        """
        try:
            # Import Telethon here to allow for fallback if not installed
            from telethon import TelegramClient
            from telethon.sessions import StringSession

            logger.info("Initializing Telegram client")

            # Create client with session string or memory session
            if self.config.telegram.session_string:
                session = StringSession(self.config.telegram.session_string)
                logger.info("Using provided session string")
            else:
                session = StringSession()
                logger.warning(
                    "No session string provided - will need to authenticate", auth_required=True
                )

            # Create and configure client
            self.telegram_client = TelegramClient(
                session=session,
                api_id=self.config.telegram.api_id,
                api_hash=self.config.telegram.api_hash,
                connection_retries=self.config.performance.request_timeout,
                flood_sleep_threshold=self.config.performance.flood_sleep_threshold,
            )

            # Start the client
            await self.telegram_client.start()

            # Check if we need to authenticate
            if not await self.telegram_client.is_user_authorized():
                logger.error(
                    "Telegram client not authorized",
                    auth_required=True,
                    auth_url="https://my.telegram.org/auth",
                )
                raise RuntimeError(
                    "Telegram client not authorized. Please authenticate first "
                    "or provide a valid session string."
                )

            logger.info(
                "Telegram client initialized successfully",
                authorized=True,
                user_id=self.telegram_client.session.user_id,
            )

        except ImportError:
            logger.error("Telethon not installed", install_required=True)
            raise ImportError("Telethon is required for Telegram client functionality")
        except Exception as e:
            logger.error("Failed to initialize Telegram client", error=str(e))
            raise

    async def shutdown_telegram_client(self) -> None:
        """Shutdown and cleanup the Telegram client."""
        if self.telegram_client:
            try:
                logger.info("Shutting down Telegram client")
                await self.telegram_client.disconnect()
                self.telegram_client = None
                logger.info("Telegram client shutdown complete")
            except Exception as e:
                logger.error("Error during Telegram client shutdown", error=str(e))

    @asynccontextmanager
    async def lifespan(self) -> AsyncGenerator[None, None]:
        """
        Lifespan context manager for MCP server.

        Handles startup and shutdown of the Telegram client and other resources.
        """
        logger.info("Starting Telegram Toolkit MCP Server")

        try:
            # Startup phase
            # Initialize OpenTelemetry tracing
            tracing_enabled = init_tracing()
            if tracing_enabled:
                logger.info("OpenTelemetry tracing initialized successfully")
            else:
                logger.info("OpenTelemetry tracing disabled or not available")

            await self.initialize_telegram_client()
            self.metrics_collector.update_active_connections(1)
            logger.info("Server startup complete")

            yield

        except Exception as e:
            logger.error("Server startup failed", error=str(e))
            raise
        finally:
            # Shutdown phase
            self.metrics_collector.update_active_connections(0)
            await self.shutdown_telegram_client()

            # Shutdown tracing
            shutdown_tracing()

            logger.info("Server shutdown complete")

    def create_mcp_server(self) -> FastMCP:
        """
        Create and configure the FastMCP server instance.

        Returns:
            FastMCP: Configured MCP server instance
        """
        if FastMCP is None:
            raise ImportError("MCP SDK not installed")

        # Create MCP server with lifespan management
        self.mcp_server = FastMCP(
            name="telegram-toolkit-mcp",
            version="0.1.0",
            description="Read-only MCP server for Telegram message history extraction",
            lifespan=self.lifespan,
        )

        # Register tools will be added here
        self._register_tools()

        # Instrument FastAPI app for tracing
        if hasattr(self.mcp_server, 'app'):
            instrument_fastapi(self.mcp_server.app)

        logger.info("MCP server created and configured")
        return self.mcp_server

    def _register_tools(self) -> None:
        """Register MCP tools with the server."""
        if not self.mcp_server:
            return

        try:
            # Import and register tools
            from .tools.resolve_chat import resolve_chat_tool
            from .tools.fetch_history import fetch_history_tool

            # Register tools
            self.mcp_server.add_tool(resolve_chat_tool)
            self.mcp_server.add_tool(fetch_history_tool)

            # Register resource handlers
            self._register_resource_handlers()

            # Add metrics endpoint
            self._add_metrics_endpoint()

            logger.info("Successfully registered MCP tools and resources")

        except ImportError as e:
            logger.error("Failed to import tools", error=str(e))
            raise
        except Exception as e:
            logger.error("Failed to register tools", error=str(e))
            raise

    def _register_resource_handlers(self) -> None:
        """Register MCP resource handlers."""
        if not self.mcp_server:
            return

        try:
            from .core.ndjson_resources import MCPResourceAdapter, get_resource_manager

            # Create resource adapter
            resource_adapter = MCPResourceAdapter(get_resource_manager())

            # Note: Resource registration depends on FastMCP API
            # This would be implemented when integrating with actual MCP server
            logger.info("Resource handlers prepared (implementation depends on FastMCP API)")

        except Exception as e:
            logger.error("Failed to register resource handlers", error=str(e))
            # Don't raise here - resources are optional

    def _add_metrics_endpoint(self) -> None:
        """Add HTTP endpoint for Prometheus metrics."""
        if not self.mcp_server:
            return

        try:
            # Add metrics endpoint using FastMCP's HTTP capabilities
            # Note: This assumes FastMCP supports custom HTTP routes
            # If not supported, metrics can be exposed via separate HTTP server

            @self.mcp_server.app.get("/metrics")
            async def metrics_endpoint():
                """Prometheus metrics endpoint."""
                metrics_data, content_type = self.metrics_collector.get_metrics_response()
                from fastapi import Response
                return Response(content=metrics_data, media_type=content_type)

            logger.info("Metrics endpoint added at /metrics")

        except Exception as e:
            logger.warning("Failed to add metrics endpoint", error=str(e))
            logger.info("Metrics available via get_metrics_collector().get_metrics()")

    async def run_server(self) -> None:
        """
        Run the MCP server with proper signal handling.

        This method sets up signal handlers and runs the server until
        interrupted or shutdown is requested.
        """
        if not self.mcp_server:
            raise RuntimeError("MCP server not created. Call create_mcp_server() first.")

        # Set up signal handlers
        def signal_handler(signum: int, frame: Any) -> None:
            logger.info(f"Received signal {signum}, initiating shutdown")
            self._shutdown_event.set()

        signal.signal(signal.SIGINT, signal_handler)
        signal.signal(signal.SIGTERM, signal_handler)

        try:
            logger.info(
                "Starting MCP server", host=self.config.server.host, port=self.config.server.port
            )

            # Run the MCP server
            await self.mcp_server.run()

        except asyncio.CancelledError:
            logger.info("Server cancelled")
        except Exception as e:
            logger.error("Server error", error=str(e))
            raise
        finally:
            logger.info("Server stopped")


def create_server() -> TelegramMCPServer:
    """
    Factory function to create a configured server instance.

    Returns:
        TelegramMCPServer: Configured server instance
    """
    return TelegramMCPServer()


async def main() -> None:
    """
    Main entry point for running the MCP server.

    This function creates and runs the server with proper error handling.
    """
    try:
        # Create and configure server
        server = create_server()

        # Create MCP server instance
        mcp_server = server.create_mcp_server()

        # Run the server
        await server.run_server()

    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error("Fatal server error", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    # Run the server
    asyncio.run(main())
