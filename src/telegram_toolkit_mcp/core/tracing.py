"""
OpenTelemetry distributed tracing for Telegram Toolkit MCP.

This module provides comprehensive distributed tracing capabilities for the MCP server,
enabling end-to-end observability of requests from MCP clients through to Telegram API calls.
"""

import asyncio
import functools
import time
from contextlib import asynccontextmanager
from typing import Any, Callable, Dict, Optional, Union
from unittest.mock import MagicMock

from telegram_toolkit_mcp.utils.config import get_config
from telegram_toolkit_mcp.utils.logging import get_logger


logger = get_logger(__name__)

# OpenTelemetry imports with fallbacks for when dependencies are not available
try:
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter as GrpcOTLPSpanExporter
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter as HttpOTLPSpanExporter
    from opentelemetry.exporter.jaeger import JaegerExporter
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.sdk.trace.sampling import TraceIdRatioBasedSampler
    from opentelemetry.trace import Status, StatusCode, SpanKind
    from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator
    from opentelemetry.distro import configure as configure_opentelemetry
    from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

    OPENTELEMETRY_AVAILABLE = True
except ImportError:
    # Fallback for when OpenTelemetry is not installed
    OPENTELEMETRY_AVAILABLE = False

    # Create mock classes
    class MockTracer:
        def start_as_current_span(self, name, **kwargs):
            return MockSpan()

        def get_current_span(self):
            return MockSpan()

    class MockSpan:
        def set_attribute(self, key, value):
            pass

        def set_status(self, status, description=None):
            pass

        def record_exception(self, exception):
            pass

        def add_event(self, name, attributes=None):
            pass

        def end(self):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

    trace = MagicMock()
    trace.get_tracer = lambda name: MockTracer()
    trace.set_tracer_provider = lambda provider: None
    SpanKind = MagicMock()
    Status = MagicMock()
    StatusCode = MagicMock()


class TracingManager:
    """Manages OpenTelemetry tracing for the MCP server."""

    def __init__(self):
        """Initialize the tracing manager."""
        self._tracer = None
        self._tracer_provider = None
        self._config = get_config()
        self._initialized = False

    def initialize(self) -> bool:
        """Initialize OpenTelemetry tracing.

        Returns:
            bool: True if tracing was successfully initialized, False otherwise
        """
        if not OPENTELEMETRY_AVAILABLE:
            logger.warning("OpenTelemetry not available. Tracing disabled.")
            return False

        if not self._config.observability.enable_opentelemetry_tracing:
            logger.info("OpenTelemetry tracing disabled in configuration.")
            return False

        try:
            # Configure tracer provider
            tracer_provider = TracerProvider(
                sampler=TraceIdRatioBasedSampler(
                    self._config.observability.trace_sampling_rate
                )
            )

            # Configure span processors based on exporter type
            span_processor = self._create_span_processor()
            if span_processor:
                tracer_provider.add_span_processor(span_processor)

            # Set global tracer provider
            trace.set_tracer_provider(tracer_provider)

            # Create tracer
            self._tracer = trace.get_tracer(
                self._config.observability.service_name,
                self._config.observability.service_version
            )

            self._tracer_provider = tracer_provider
            self._initialized = True

            logger.info(
                f"OpenTelemetry tracing initialized with {self._config.observability.otlp_exporter} exporter"
            )
            return True

        except Exception as e:
            logger.error(f"Failed to initialize OpenTelemetry tracing: {e}")
            return False

    def _create_span_processor(self):
        """Create appropriate span processor based on configuration."""
        if not self._config.observability.otlp_endpoint:
            # Use console exporter if no endpoint configured
            logger.info("No OTLP endpoint configured, using console exporter")
            return BatchSpanProcessor(ConsoleSpanExporter())

        exporter_type = self._config.observability.otlp_exporter.lower()

        try:
            if exporter_type == "grpc":
                exporter = GrpcOTLPSpanExporter(
                    endpoint=self._config.observability.otlp_endpoint,
                    insecure=True,  # For development; use proper TLS in production
                )
            elif exporter_type == "http":
                exporter = HttpOTLPSpanExporter(
                    endpoint=self._config.observability.otlp_endpoint,
                )
            elif exporter_type == "jaeger":
                exporter = JaegerExporter(
                    agent_host_name=self._config.observability.otlp_endpoint.split(":")[0],
                    agent_port=int(self._config.observability.otlp_endpoint.split(":")[1]),
                )
            else:
                logger.warning(f"Unknown exporter type '{exporter_type}', falling back to console")
                exporter = ConsoleSpanExporter()

            return BatchSpanProcessor(exporter)

        except Exception as e:
            logger.error(f"Failed to create span processor: {e}")
            return BatchSpanProcessor(ConsoleSpanExporter())

    def get_tracer(self):
        """Get the configured tracer."""
        if not self._initialized:
            if not self.initialize():
                # Return mock tracer if initialization failed
                return trace.get_tracer("mock-tracer")
        return self._tracer

    def shutdown(self):
        """Shutdown tracing gracefully."""
        if self._tracer_provider and hasattr(self._tracer_provider, 'shutdown'):
            try:
                self._tracer_provider.shutdown()
                logger.info("OpenTelemetry tracing shutdown successfully")
            except Exception as e:
                logger.error(f"Error during tracing shutdown: {e}")


# Global tracing manager instance
_tracing_manager = None


def get_tracing_manager() -> TracingManager:
    """Get the global tracing manager instance."""
    global _tracing_manager
    if _tracing_manager is None:
        _tracing_manager = TracingManager()
    return _tracing_manager


def init_tracing() -> bool:
    """Initialize OpenTelemetry tracing globally.

    Returns:
        bool: True if tracing was successfully initialized
    """
    manager = get_tracing_manager()
    return manager.initialize()


def shutdown_tracing():
    """Shutdown OpenTelemetry tracing globally."""
    manager = get_tracing_manager()
    manager.shutdown()


def get_tracer(name: str = "telegram-toolkit-mcp"):
    """Get a tracer instance for the given name.

    Args:
        name: Name of the tracer component

    Returns:
        Tracer instance (real or mock)
    """
    manager = get_tracing_manager()
    tracer = manager.get_tracer()

    if OPENTELEMETRY_AVAILABLE:
        return tracer
    else:
        # Return mock tracer
        return trace.get_tracer(name)


class TracingContext:
    """Context manager for tracing spans with automatic error handling."""

    def __init__(
        self,
        name: str,
        kind: SpanKind = SpanKind.INTERNAL,
        attributes: Optional[Dict[str, Union[str, int, float, bool]]] = None
    ):
        """Initialize tracing context.

        Args:
            name: Span name
            kind: Span kind (INTERNAL, SERVER, CLIENT, etc.)
            attributes: Initial span attributes
        """
        self.name = name
        self.kind = kind
        self.attributes = attributes or {}
        self.span = None
        self.start_time = None

    async def __aenter__(self):
        """Enter the tracing context."""
        tracer = get_tracer()
        self.start_time = time.time()

        if OPENTELEMETRY_AVAILABLE:
            self.span = tracer.start_as_current_span(
                self.name,
                kind=self.kind,
                attributes=self.attributes
            )
            return self.span
        else:
            # Mock span for when OpenTelemetry is not available
            self.span = MockSpan()
            return self.span

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Exit the tracing context."""
        if self.span:
            if exc_val:
                # Record exception if one occurred
                if OPENTELEMETRY_AVAILABLE and hasattr(self.span, 'record_exception'):
                    self.span.record_exception(exc_val)
                    self.span.set_status(Status(StatusCode.ERROR, str(exc_val)))

            # Record duration
            if self.start_time:
                duration = time.time() - self.start_time
                self.span.set_attribute("duration_seconds", duration)

            self.span.end()


def traced_async(
    name: Optional[str] = None,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Optional[Dict[str, Union[str, int, float, bool]]] = None
):
    """Decorator for tracing async functions.

    Args:
        name: Custom span name (defaults to function name)
        kind: Span kind
        attributes: Additional span attributes
    """
    def decorator(func: Callable):
        span_name = name or f"{func.__module__}.{func.__qualname__}"

        @functools.wraps(func)
        async def wrapper(*args, **kwargs):
            async with TracingContext(
                span_name,
                kind=kind,
                attributes=attributes
            ) as span:
                # Add function arguments as span attributes (safely)
                if OPENTELEMETRY_AVAILABLE:
                    try:
                        # Add basic function info
                        span.set_attribute("function.module", func.__module__)
                        span.set_attribute("function.name", func.__name__)

                        # Add argument count (without sensitive data)
                        span.set_attribute("args.count", len(args))
                        span.set_attribute("kwargs.count", len(kwargs))

                    except Exception:
                        # Ignore attribute setting errors
                        pass

                return await func(*args, **kwargs)

        return wrapper
    return decorator


def traced_sync(
    name: Optional[str] = None,
    kind: SpanKind = SpanKind.INTERNAL,
    attributes: Optional[Dict[str, Union[str, int, float, bool]]] = None
):
    """Decorator for tracing sync functions.

    Args:
        name: Custom span name (defaults to function name)
        kind: Span kind
        attributes: Additional span attributes
    """
    def decorator(func: Callable):
        span_name = name or f"{func.__module__}.{func.__qualname__}"

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()

            if OPENTELEMETRY_AVAILABLE:
                with tracer.start_as_current_span(
                    span_name,
                    kind=kind,
                    attributes=attributes
                ) as span:
                    try:
                        # Add function info
                        span.set_attribute("function.module", func.__module__)
                        span.set_attribute("function.name", func.__name__)
                        span.set_attribute("args.count", len(args))
                        span.set_attribute("kwargs.count", len(kwargs))

                        result = func(*args, **kwargs)
                        return result

                    except Exception as e:
                        span.record_exception(e)
                        span.set_status(Status(StatusCode.ERROR, str(e)))
                        raise
            else:
                # Execute without tracing
                return func(*args, **kwargs)

        return wrapper
    return decorator


# MCP-specific tracing utilities
def trace_mcp_tool_call(tool_name: str, arguments: Dict[str, Any]):
    """Create a span for MCP tool calls.

    Args:
        tool_name: Name of the MCP tool
        arguments: Tool arguments

    Returns:
        TracingContext for the tool call
    """
    attributes = {
        "mcp.tool.name": tool_name,
        "mcp.tool.args_count": len(arguments),
    }

    # Add safe argument info (without sensitive data)
    for key, value in arguments.items():
        if key in ["chat", "input"]:  # Safe fields
            attributes[f"mcp.tool.arg.{key}"] = str(value)[:100]  # Truncate for safety

    return TracingContext(
        f"mcp.tool.{tool_name}",
        kind=SpanKind.SERVER,
        attributes=attributes
    )


def trace_telegram_api_call(method: str, **kwargs):
    """Create a span for Telegram API calls.

    Args:
        method: Telegram API method name
        **kwargs: API call parameters

    Returns:
        TracingContext for the API call
    """
    attributes = {
        "telegram.api.method": method,
        "telegram.api.has_chat": "chat" in kwargs,
        "telegram.api.has_limit": "limit" in kwargs,
    }

    if "limit" in kwargs:
        attributes["telegram.api.limit"] = kwargs["limit"]

    return TracingContext(
        f"telegram.api.{method}",
        kind=SpanKind.CLIENT,
        attributes=attributes
    )


def trace_resource_operation(operation: str, resource_uri: str):
    """Create a span for resource operations.

    Args:
        operation: Operation type (read, write, delete)
        resource_uri: Resource URI

    Returns:
        TracingContext for the resource operation
    """
    attributes = {
        "resource.operation": operation,
        "resource.uri": resource_uri[:200],  # Truncate for safety
    }

    return TracingContext(
        f"resource.{operation}",
        kind=SpanKind.INTERNAL,
        attributes=attributes
    )


# FastAPI instrumentation helper
def instrument_fastapi(app):
    """Instrument FastAPI application with OpenTelemetry.

    Args:
        app: FastAPI application instance
    """
    if OPENTELEMETRY_AVAILABLE:
        try:
            FastAPIInstrumentor.instrument_app(app)
            logger.info("FastAPI instrumentation enabled")
        except Exception as e:
            logger.warning(f"Failed to instrument FastAPI: {e}")
    else:
        logger.info("OpenTelemetry not available, FastAPI instrumentation skipped")


# Utility functions for manual span management
def start_span(name: str, **attributes) -> Any:
    """Start a new span manually.

    Args:
        name: Span name
        **attributes: Span attributes

    Returns:
        Span object or None if tracing not available
    """
    tracer = get_tracer()
    if OPENTELEMETRY_AVAILABLE:
        return tracer.start_as_current_span(name, attributes=attributes)
    return None


def get_current_span() -> Any:
    """Get the current active span.

    Returns:
        Current span or None
    """
    if OPENTELEMETRY_AVAILABLE:
        return trace.get_current_span()
    return None


def add_span_attribute(key: str, value: Union[str, int, float, bool]):
    """Add attribute to current span.

    Args:
        key: Attribute key
        value: Attribute value
    """
    span = get_current_span()
    if span and hasattr(span, 'set_attribute'):
        span.set_attribute(key, value)


def add_span_event(name: str, attributes: Optional[Dict[str, Any]] = None):
    """Add event to current span.

    Args:
        name: Event name
        attributes: Event attributes
    """
    span = get_current_span()
    if span and hasattr(span, 'add_event'):
        span.add_event(name, attributes or {})
