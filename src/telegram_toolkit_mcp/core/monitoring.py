"""
Monitoring and metrics collection for Telegram Toolkit MCP.

This module provides Prometheus metrics for monitoring system performance,
error rates, and operational health.
"""

import time

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)

from ..utils.logging import get_logger

logger = get_logger(__name__)


class MetricsCollector:
    """Centralized metrics collection for the Telegram Toolkit MCP server."""

    def __init__(self, registry: CollectorRegistry | None = None):
        """Initialize metrics with optional custom registry."""
        self.registry = registry or CollectorRegistry()

        # Tool execution metrics
        self.tool_calls_total = Counter(
            "mcp_tool_calls_total",
            "Total number of MCP tool calls",
            ["tool", "status", "chat_type"],
            registry=self.registry,
        )

        self.tool_duration_seconds = Histogram(
            "mcp_tool_duration_seconds",
            "Duration of MCP tool execution in seconds",
            ["tool", "status"],
            buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
            registry=self.registry,
        )

        # Telegram API metrics
        self.telegram_api_calls_total = Counter(
            "telegram_api_calls_total",
            "Total number of Telegram API calls",
            ["method", "status"],
            registry=self.registry,
        )

        self.telegram_api_duration_seconds = Histogram(
            "telegram_api_duration_seconds",
            "Duration of Telegram API calls in seconds",
            ["method"],
            buckets=(0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0),
            registry=self.registry,
        )

        # Error metrics
        self.errors_total = Counter(
            "telegram_toolkit_errors_total",
            "Total number of errors by type",
            ["error_type", "component"],
            registry=self.registry,
        )

        # FLOOD_WAIT metrics
        self.flood_wait_events_total = Counter(
            "telegram_flood_wait_events_total",
            "Total number of FLOOD_WAIT events",
            ["tool", "retry_attempt"],
            registry=self.registry,
        )

        self.flood_wait_duration_seconds = Histogram(
            "telegram_flood_wait_duration_seconds",
            "Duration of FLOOD_WAIT delays in seconds",
            ["tool"],
            buckets=(1.0, 5.0, 10.0, 30.0, 60.0, 300.0, 600.0, 1800.0),
            registry=self.registry,
        )

        # Resource metrics
        self.ndjson_exports_total = Counter(
            "telegram_ndjson_exports_total",
            "Total number of NDJSON exports created",
            ["status"],
            registry=self.registry,
        )

        self.ndjson_export_size_bytes = Histogram(
            "telegram_ndjson_export_size_bytes",
            "Size of NDJSON exports in bytes",
            buckets=(1024, 10 * 1024, 100 * 1024, 1024 * 1024, 10 * 1024 * 1024, 100 * 1024 * 1024),
            registry=self.registry,
        )

        # Pagination metrics
        self.messages_fetched_total = Counter(
            "telegram_messages_fetched_total",
            "Total number of messages fetched",
            ["tool", "has_filters"],
            registry=self.registry,
        )

        self.pages_served_total = Counter(
            "telegram_pages_served_total",
            "Total number of pages served",
            ["tool", "direction"],
            registry=self.registry,
        )

        # System metrics
        self.active_connections = Gauge(
            "telegram_active_connections",
            "Number of active Telegram connections",
            registry=self.registry,
        )

        self.memory_usage_mb = Gauge(
            "telegram_memory_usage_mb", "Memory usage in MB", registry=self.registry
        )

        # Cache metrics (future use)
        self.cache_hits_total = Counter(
            "telegram_cache_hits_total",
            "Total number of cache hits",
            ["cache_type"],
            registry=self.registry,
        )

        self.cache_misses_total = Counter(
            "telegram_cache_misses_total",
            "Total number of cache misses",
            ["cache_type"],
            registry=self.registry,
        )

        logger.info("Metrics collector initialized", registry_type=type(self.registry).__name__)

    def record_tool_call(
        self, tool: str, status: str, chat_type: str = "unknown", duration: float | None = None
    ):
        """Record a tool call with optional duration."""
        self.tool_calls_total.labels(tool=tool, status=status, chat_type=chat_type).inc()

        if duration is not None:
            self.tool_duration_seconds.labels(tool=tool, status=status).observe(duration)

    def record_telegram_api_call(self, method: str, status: str, duration: float | None = None):
        """Record a Telegram API call."""
        self.telegram_api_calls_total.labels(method=method, status=status).inc()

        if duration is not None:
            self.telegram_api_duration_seconds.labels(method=method).observe(duration)

    def record_error(self, error_type: str, component: str):
        """Record an error occurrence."""
        self.errors_total.labels(error_type=error_type, component=component).inc()

    def record_flood_wait(self, tool: str, retry_attempt: int, duration: float):
        """Record a FLOOD_WAIT event."""
        self.flood_wait_events_total.labels(tool=tool, retry_attempt=str(retry_attempt)).inc()
        self.flood_wait_duration_seconds.labels(tool=tool).observe(duration)

    def record_ndjson_export(self, status: str, size_bytes: int | None = None):
        """Record NDJSON export creation."""
        self.ndjson_exports_total.labels(status=status).inc()

        if size_bytes is not None:
            self.ndjson_export_size_bytes.observe(size_bytes)

    def record_messages_fetched(self, tool: str, count: int, has_filters: bool):
        """Record messages fetched."""
        self.messages_fetched_total.labels(tool=tool, has_filters=str(has_filters)).inc(count)

    def record_page_served(self, tool: str, direction: str):
        """Record a page served."""
        self.pages_served_total.labels(tool=tool, direction=direction).inc()

    def update_active_connections(self, count: int):
        """Update the number of active connections."""
        self.active_connections.set(count)

    def update_memory_usage(self, mb: float):
        """Update memory usage in MB."""
        self.memory_usage_mb.set(mb)

    def record_cache_hit(self, cache_type: str):
        """Record a cache hit."""
        self.cache_hits_total.labels(cache_type=cache_type).inc()

    def record_cache_miss(self, cache_type: str):
        """Record a cache miss."""
        self.cache_misses_total.labels(cache_type=cache_type).inc()

    def get_metrics(self) -> str:
        """Get all metrics in Prometheus format."""
        return generate_latest(self.registry).decode("utf-8")

    def get_metrics_response(self) -> tuple[str, str]:
        """Get metrics response suitable for HTTP endpoint."""
        return self.get_metrics(), CONTENT_TYPE_LATEST


# Global metrics instance
_metrics_collector: MetricsCollector | None = None


def get_metrics_collector() -> MetricsCollector:
    """Get the global metrics collector instance."""
    global _metrics_collector
    if _metrics_collector is None:
        _metrics_collector = MetricsCollector()
    return _metrics_collector


def init_metrics(registry: CollectorRegistry | None = None) -> MetricsCollector:
    """Initialize global metrics collector."""
    global _metrics_collector
    _metrics_collector = MetricsCollector(registry)
    logger.info("Global metrics collector initialized")
    return _metrics_collector


def reset_metrics():
    """Reset all metrics (useful for testing)."""
    global _metrics_collector
    if _metrics_collector is not None:
        # Create new registry to effectively reset all metrics
        _metrics_collector = MetricsCollector()
        logger.info("Metrics reset")


# Convenience functions for common operations
def record_tool_success(tool: str, chat_type: str = "unknown", duration: float | None = None):
    """Record successful tool execution."""
    get_metrics_collector().record_tool_call(tool, "success", chat_type, duration)


def record_tool_error(tool: str, chat_type: str = "unknown", duration: float | None = None):
    """Record failed tool execution."""
    get_metrics_collector().record_tool_call(tool, "error", chat_type, duration)


def record_api_call(method: str, success: bool, duration: float | None = None):
    """Record Telegram API call."""
    status = "success" if success else "error"
    get_metrics_collector().record_telegram_api_call(method, status, duration)


def record_flood_wait_event(tool: str, retry_attempt: int, wait_seconds: float):
    """Record FLOOD_WAIT event."""
    get_metrics_collector().record_flood_wait(tool, retry_attempt, wait_seconds)


def record_messages_fetched(tool: str, count: int, has_filters: bool):
    """Record messages fetched."""
    get_metrics_collector().record_messages_fetched(tool, count, has_filters)


def record_page_served(tool: str, direction: str = "forward"):
    """Record page served."""
    get_metrics_collector().record_page_served(tool, direction)


def record_ndjson_export(status: str = "success", size_bytes: int | None = None):
    """Record NDJSON export."""
    get_metrics_collector().record_ndjson_export(status, size_bytes)


class MetricsTimer:
    """Context manager for timing operations."""

    def __init__(self, operation_type: str, operation_name: str):
        self.operation_type = operation_type
        self.operation_name = operation_name
        self.start_time: float | None = None

    def __enter__(self):
        self.start_time = time.time()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        if self.start_time is not None:
            duration = time.time() - self.start_time

            if self.operation_type == "tool":
                _status = "error" if exc_type else "success"
                record_tool_success(
                    self.operation_name, duration=duration
                ) if not exc_type else record_tool_error(self.operation_name, duration=duration)
            elif self.operation_type == "api":
                success = exc_type is None
                record_api_call(self.operation_name, success, duration)
