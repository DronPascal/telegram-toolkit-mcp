"""
Telegram Toolkit MCP Server - FastMCP-based server implementation.

This module provides the main MCP server implementation with lifespan management,
tool registration, and resource handling for Telegram message extraction.
"""

import asyncio
import sys
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

try:
    from mcp.server import FastMCP
    from starlette.responses import PlainTextResponse
except ImportError:
    # Fallback for development
    FastMCP = None
    PlainTextResponse = None

from datetime import UTC

from .core.monitoring import init_metrics
from .core.tracing import init_tracing, shutdown_tracing
from .utils.config import get_config, validate_telegram_credentials
from .utils.logging import get_logger

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
                user_id=getattr(self.telegram_client.session, "user_id", None),
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
            except Exception as e:  # type: ignore[BLE001]
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

            # Create MCP server if not exists
            if not self.mcp_server:
                self.create_mcp_server()

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
            instructions="Read-only MCP server for Telegram message history extraction",
            lifespan=self.lifespan,
        )

        # Register tools will be added here
        self._register_tools()

        logger.info("MCP server created and configured")
        return self.mcp_server

    def _register_tools(self) -> None:
        """Register MCP tools with the server."""
        if not self.mcp_server:
            return

        try:
            # Import and register tools
            from .tools.fetch_history import fetch_history_tool
            from .tools.resolve_chat import resolve_chat_tool

            # Register tools
            self.mcp_server.add_tool(resolve_chat_tool)
            self.mcp_server.add_tool(fetch_history_tool)

            # Register resource handlers
            self._register_resource_handlers()

            # Add custom routes to FastMCP server
            self._add_custom_routes()

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
            # Note: Resource registration depends on FastMCP API
            # This would be implemented when integrating with actual MCP server
            logger.info("Resource handlers prepared (implementation depends on FastMCP API)")

        except Exception as e:  # type: ignore[BLE001]
            logger.error("Failed to register resource handlers", error=str(e))
            # Don't raise here - resources are optional

    def _add_custom_routes(self) -> None:
        """Add custom routes to FastMCP server using @custom_route decorator."""
        logger.info("🔧 Adding custom routes to FastMCP server...")

        # Health check route
        @self.mcp_server.custom_route("/health", methods=["GET"])
        async def health_endpoint(request):
            """Health check endpoint for load balancers and monitoring."""
            logger.info("🏥 Health check requested")
            from datetime import datetime

            from starlette.responses import JSONResponse

            return JSONResponse(
                {
                    "status": "healthy",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "service": "telegram-toolkit-mcp",
                    "version": "1.0.0",
                }
            )

        # Metrics route
        @self.mcp_server.custom_route("/metrics", methods=["GET"])
        async def metrics_endpoint(request):
            """Prometheus metrics endpoint."""
            logger.info("📊 Metrics requested")
            try:
                metrics_data, content_type = self.metrics_collector.get_metrics_response()
                from starlette.responses import Response

                return Response(content=metrics_data, media_type=content_type)
            except Exception as e:
                logger.error(f"❌ Metrics collection error: {e}")
                return PlainTextResponse("Metrics collection failed", status_code=500)

        # Debug headers endpoint
        @self.mcp_server.custom_route("/debug/headers", methods=["GET"])
        async def debug_headers_endpoint(request):
            """Debug endpoint that shows request headers."""
            logger.info("🐛 Debug headers requested")
            from starlette.responses import JSONResponse

            headers = dict(request.headers)
            # Mask sensitive headers
            sensitive = ["authorization", "cookie", "x-api-key"]
            for key in sensitive:
                if key in headers:
                    headers[key] = "***masked***"

            from datetime import datetime

            return JSONResponse(
                {
                    "status": "ok",
                    "timestamp": datetime.now(UTC).isoformat(),
                    "headers": headers,
                    "method": request.method,
                    "url": str(request.url),
                    "client": request.client.host if request.client else None,
                }
            )

        logger.info("✅ Custom routes added to FastMCP server")
        logger.info("✅ Health endpoint available at: /health")
        logger.info("✅ Metrics endpoint available at: /metrics")
        logger.info("✅ Debug headers endpoint available at: /debug/headers")
        logger.info("✅ MCP endpoint available at: /mcp (SSE)")

    def run_server_sync(self) -> None:
        """
        Run the MCP server synchronously with HTTP transport.

        This method runs the FastMCP server with streamable-http transport,
        which is the recommended approach for HTTP-based MCP servers.
        """
        if not self.mcp_server:
            raise RuntimeError("MCP server not created. Call create_mcp_server() first.")

        try:
            logger.info(
                "Starting MCP server with streamable-http transport",
                host=self.config.server.host,
                port=self.config.server.port,
            )

            # Use streamable-http transport - check FastMCP version compatibility
            logger.info("🚀 Running FastMCP with streamable-http transport...")

            # Try different approaches based on FastMCP version
            try:
                # Try with host/port parameters (newer versions)
                self.mcp_server.run(
                    transport="streamable-http",
                    host=self.config.server.host,
                    port=self.config.server.port,
                )
            except TypeError as e:
                if "unexpected keyword argument" in str(e):
                    logger.warning(
                        "FastMCP version doesn't support host/port parameters, using manual ASGI server"
                    )
                    # Use manual ASGI server with proper host/port configuration
                    self._run_manual_asgi_server()
                else:
                    raise e

        except Exception as e:
            logger.error("Failed to start FastMCP server", error=str(e))
            logger.info("💡 Make sure FastMCP dependencies are properly installed")
            logger.info("💡 Check that no other service is using the same port")
            logger.info("💡 FastMCP version may not support streamable-http transport")

            # Try alternative approach for older FastMCP versions
            logger.info("🔄 Trying alternative approach for older FastMCP versions...")
            try:
                self._run_legacy_fastmcp()
            except Exception as legacy_error:
                logger.error(f"Legacy approach also failed: {legacy_error}")
                logger.info("💡 Consider updating FastMCP to a newer version")
                logger.info("💡 Or use the working custom endpoints on port 8001")
                raise legacy_error

    def _run_legacy_fastmcp(self) -> None:
        """
        Alternative approach for older FastMCP versions that don't support
        host/port parameters or streamable-http transport.
        """
        logger.info("🔧 Starting FastMCP with legacy approach...")

        # For older versions, try stdio transport with external web server
        # This requires setting up a reverse proxy or separate web server
        logger.info("📡 Using stdio transport (requires external web server)")

        try:
            # Try stdio transport (most compatible)
            self.mcp_server.run(transport="stdio")
        except Exception as stdio_error:
            logger.error(f"Stdio transport failed: {stdio_error}")

            # Last resort: try to create ASGI app manually
            logger.info("🔄 Attempting manual ASGI app creation...")
            try:
                # Try to get the ASGI app
                if hasattr(self.mcp_server, "app"):
                    logger.info("✅ Found ASGI app, attempting manual server setup...")
                    self._run_manual_asgi_server()
                else:
                    logger.error("❌ No ASGI app found in FastMCP instance")
                    raise RuntimeError("FastMCP version incompatible - no ASGI app available")
            except Exception as manual_error:
                logger.error(f"Manual ASGI setup failed: {manual_error}")
                raise manual_error

    def _run_manual_asgi_server(self) -> None:
        """
        Manually run the ASGI app using uvicorn for FastMCP versions.
        """
        logger.info("🚀 Starting manual ASGI server...")

        try:
            import uvicorn
            from fastmcp import FastMCP

            # Try different ways to get ASGI app
            asgi_app = None

            # Method 1: FastMCP streamable_http_app (preferred for HTTP)
            if hasattr(self.mcp_server, "streamable_http_app"):
                asgi_app = self.mcp_server.streamable_http_app
                logger.info("✅ ASGI app obtained via .streamable_http_app")

            # Method 2: FastMCP sse_app (fallback)
            elif hasattr(self.mcp_server, "sse_app"):
                asgi_app = self.mcp_server.sse_app
                logger.info("✅ ASGI app obtained via .sse_app")

            # Method 3: Direct app attribute (legacy)
            elif hasattr(self.mcp_server, "app"):
                asgi_app = self.mcp_server.app
                logger.info("✅ ASGI app obtained via .app attribute")

            # Method 4: Try to create ASGI app
            elif hasattr(self.mcp_server, "create_app"):
                asgi_app = self.mcp_server.create_app()
                logger.info("✅ ASGI app created via create_app()")

            # Method 5: Check if mcp_server is already an ASGI app
            elif hasattr(self.mcp_server, "__call__"):
                asgi_app = self.mcp_server
                logger.info("✅ Using mcp_server directly as ASGI app")

            if asgi_app:
                logger.info(
                    f"🚀 Starting uvicorn on {self.config.server.host}:{self.config.server.port}"
                )

                # Run with uvicorn
                uvicorn.run(
                    asgi_app,
                    host=self.config.server.host,
                    port=self.config.server.port,
                    log_level="info",
                )
            else:
                logger.error("❌ Could not obtain ASGI app from FastMCP server")
                logger.error(f"Available attributes: {dir(self.mcp_server)}")
                raise AttributeError("No ASGI app available")

        except ImportError as e:
            logger.error(f"❌ Import error: {e}")
            raise ImportError(f"Required packages not installed: {e}")
        except Exception as e:
            logger.error(f"❌ Manual ASGI server failed: {e}")
            logger.error(f"FastMCP type: {type(self.mcp_server)}")
            raise

    async def shutdown(self) -> None:
        """
        Gracefully shutdown the MCP server and its resources.

        This method ensures proper cleanup of:
        - Telegram client connections
        - Metrics collector
        - Tracing resources
        """
        logger.info("Initiating MCP server shutdown")

        try:
            # Set shutdown event
            self._shutdown_event.set()

            # Shutdown Telegram client
            if self.telegram_client:
                logger.info("Shutting down Telegram client")
                await self.telegram_client.disconnect()
                logger.info("Telegram client shutdown complete")

            # Shutdown tracing
            try:
                await shutdown_tracing()
                logger.info("Tracing shutdown complete")
            except Exception as e:  # type: ignore[BLE001]
                logger.warning("Tracing shutdown failed", error=str(e))

            logger.info("Server shutdown complete")

        except Exception as e:  # type: ignore[BLE001]
            logger.error("Shutdown error", error=str(e))
            raise


def create_server() -> TelegramMCPServer:
    """
    Factory function to create a configured server instance.

    Returns:
        TelegramMCPServer: Configured server instance
    """
    return TelegramMCPServer()


def main() -> None:
    """
    Main entry point for running the MCP server.

    This function creates and runs the server with proper error handling.
    """
    try:
        # Create and configure server
        server = create_server()

        # Create MCP server instance
        server.create_mcp_server()

        # Run the server with HTTP transport
        server.run_server_sync()

    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:  # type: ignore[BLE001]
        logger.error("Fatal server error", error=str(e))
        sys.exit(1)


if __name__ == "__main__":
    # Run the server
    main()
