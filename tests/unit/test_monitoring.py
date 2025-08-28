"""
Unit tests for monitoring and metrics functionality.

Tests Prometheus metrics collection, tool execution tracking,
error monitoring, and system health metrics.
"""

import pytest
import time
from unittest.mock import Mock, patch
from prometheus_client import CollectorRegistry

from src.telegram_toolkit_mcp.core.monitoring import (
    MetricsCollector,
    get_metrics_collector,
    init_metrics,
    reset_metrics,
    record_tool_success,
    record_tool_error,
    record_api_call,
    record_flood_wait_event,
    record_messages_fetched,
    record_page_served,
    record_ndjson_export,
    MetricsTimer
)


@pytest.fixture
def registry():
    """Create a test Prometheus registry."""
    return CollectorRegistry()


@pytest.fixture
def metrics_collector(registry):
    """Create a test metrics collector."""
    return MetricsCollector(registry=registry)


class TestMetricsCollector:
    """Test MetricsCollector functionality."""

    def test_init(self, registry):
        """Test metrics collector initialization."""
        collector = MetricsCollector(registry=registry)

        # Check that all expected metrics are created
        assert hasattr(collector, 'tool_calls_total')
        assert hasattr(collector, 'tool_duration_seconds')
        assert hasattr(collector, 'telegram_api_calls_total')
        assert hasattr(collector, 'telegram_api_duration_seconds')
        assert hasattr(collector, 'errors_total')
        assert hasattr(collector, 'flood_wait_events_total')
        assert hasattr(collector, 'flood_wait_duration_seconds')
        assert hasattr(collector, 'ndjson_exports_total')
        assert hasattr(collector, 'ndjson_export_size_bytes')
        assert hasattr(collector, 'messages_fetched_total')
        assert hasattr(collector, 'pages_served_total')
        assert hasattr(collector, 'active_connections')
        assert hasattr(collector, 'memory_usage_mb')

    def test_record_tool_call_success(self, metrics_collector):
        """Test recording successful tool calls."""
        metrics_collector.record_tool_call("tg.fetch_history", "success", "channel", 1.5)

        # Check metrics were recorded
        metrics = metrics_collector.get_metrics()
        assert 'mcp_tool_calls_total{chat_type="channel",status="success",tool="tg.fetch_history"} 1.0' in metrics
        assert 'mcp_tool_duration_seconds_sum{status="success",tool="tg.fetch_history"} 1.5' in metrics

    def test_record_tool_call_error(self, metrics_collector):
        """Test recording failed tool calls."""
        metrics_collector.record_tool_call("tg.resolve_chat", "error", "user")

        metrics = metrics_collector.get_metrics()
        assert 'mcp_tool_calls_total{chat_type="user",status="error",tool="tg.resolve_chat"} 1.0' in metrics

    def test_record_api_call(self, metrics_collector):
        """Test recording Telegram API calls."""
        metrics_collector.record_telegram_api_call("get_entity", "success", 0.5)

        metrics = metrics_collector.get_metrics()
        assert 'telegram_api_calls_total{method="get_entity",status="success"} 1.0' in metrics
        assert 'telegram_api_duration_seconds_sum{method="get_entity"} 0.5' in metrics

    def test_record_error(self, metrics_collector):
        """Test recording errors."""
        metrics_collector.record_error("flood_wait", "fetch_history")

        metrics = metrics_collector.get_metrics()
        assert 'telegram_toolkit_errors_total{component="fetch_history",error_type="flood_wait"} 1.0' in metrics

    def test_record_flood_wait(self, metrics_collector):
        """Test recording FLOOD_WAIT events."""
        metrics_collector.record_flood_wait("tg.fetch_history", 1, 5.0)

        metrics = metrics_collector.get_metrics()
        assert 'telegram_flood_wait_events_total{retry_attempt="1",tool="tg.fetch_history"} 1.0' in metrics
        assert 'telegram_flood_wait_duration_seconds_sum{tool="tg.fetch_history"} 5.0' in metrics

    def test_record_ndjson_export(self, metrics_collector):
        """Test recording NDJSON exports."""
        metrics_collector.record_ndjson_export("success", 1024)

        metrics = metrics_collector.get_metrics()
        assert 'telegram_ndjson_exports_total{status="success"} 1.0' in metrics
        assert 'telegram_ndjson_export_size_bytes_sum' in metrics

    def test_record_messages_fetched(self, metrics_collector):
        """Test recording fetched messages."""
        metrics_collector.record_messages_fetched("tg.fetch_history", 50, True)

        metrics = metrics_collector.get_metrics()
        assert 'telegram_messages_fetched_total{has_filters="True",tool="tg.fetch_history"} 50.0' in metrics

    def test_record_page_served(self, metrics_collector):
        """Test recording served pages."""
        metrics_collector.record_page_served("tg.fetch_history", "desc")

        metrics = metrics_collector.get_metrics()
        assert 'telegram_pages_served_total{direction="desc",tool="tg.fetch_history"} 1.0' in metrics

    def test_update_gauges(self, metrics_collector):
        """Test updating gauge metrics."""
        metrics_collector.update_active_connections(5)
        metrics_collector.update_memory_usage(128.5)

        metrics = metrics_collector.get_metrics()
        assert 'telegram_active_connections 5.0' in metrics
        assert 'telegram_memory_usage_mb 128.5' in metrics

    def test_get_metrics_format(self, metrics_collector):
        """Test metrics output format."""
        metrics_collector.record_tool_call("test_tool", "success")

        metrics = metrics_collector.get_metrics()
        assert isinstance(metrics, str)
        assert "# HELP" in metrics or "# TYPE" in metrics

    def test_get_metrics_response(self, metrics_collector):
        """Test metrics HTTP response format."""
        metrics_data, content_type = metrics_collector.get_metrics_response()

        assert isinstance(metrics_data, str)
        assert content_type == "text/plain; version=0.0.4; charset=utf-8"


class TestGlobalFunctions:
    """Test global metrics functions."""

    def test_get_metrics_collector(self):
        """Test getting global metrics collector."""
        # Reset first to ensure clean state
        reset_metrics()

        collector1 = get_metrics_collector()
        collector2 = get_metrics_collector()

        assert collector1 is collector2  # Should be same instance

    def test_init_metrics(self):
        """Test initializing metrics with custom registry."""
        registry = CollectorRegistry()
        collector = init_metrics(registry)

        assert collector.registry is registry

    def test_reset_metrics(self):
        """Test resetting metrics."""
        collector1 = get_metrics_collector()
        reset_metrics()
        collector2 = get_metrics_collector()

        assert collector1 is not collector2  # Should be different instances after reset

    def test_record_tool_success_function(self):
        """Test record_tool_success convenience function."""
        reset_metrics()
        record_tool_success("test_tool", "channel", 2.0)

        collector = get_metrics_collector()
        metrics = collector.get_metrics()

        assert 'mcp_tool_calls_total{chat_type="channel",status="success",tool="test_tool"} 1.0' in metrics

    def test_record_tool_error_function(self):
        """Test record_tool_error convenience function."""
        reset_metrics()
        record_tool_error("test_tool", "user", 1.5)

        collector = get_metrics_collector()
        metrics = collector.get_metrics()

        assert 'mcp_tool_calls_total{chat_type="user",status="error",tool="test_tool"} 1.0' in metrics

    def test_record_api_call_function(self):
        """Test record_api_call convenience function."""
        reset_metrics()
        record_api_call("iter_messages", True, 0.8)

        collector = get_metrics_collector()
        metrics = collector.get_metrics()

        assert 'telegram_api_calls_total{method="iter_messages",status="success"} 1.0' in metrics

    def test_record_flood_wait_event_function(self):
        """Test record_flood_wait_event convenience function."""
        reset_metrics()
        record_flood_wait_event("test_tool", 2, 10.0)

        collector = get_metrics_collector()
        metrics = collector.get_metrics()

        assert 'telegram_flood_wait_events_total{retry_attempt="2",tool="test_tool"} 1.0' in metrics


class TestMetricsTimer:
    """Test MetricsTimer context manager."""

    def test_timer_success_path(self):
        """Test timer with successful operation."""
        reset_metrics()

        with MetricsTimer('tool', 'test_tool'):
            time.sleep(0.01)  # Small delay

        collector = get_metrics_collector()
        metrics = collector.get_metrics()

        assert 'mcp_tool_calls_total{chat_type="unknown",status="success",tool="test_tool"}' in metrics

    def test_timer_error_path(self):
        """Test timer with failed operation."""
        reset_metrics()

        try:
            with MetricsTimer('tool', 'test_tool'):
                raise ValueError("Test error")
        except ValueError:
            pass

        collector = get_metrics_collector()
        metrics = collector.get_metrics()

        assert 'mcp_tool_calls_total{chat_type="unknown",status="error",tool="test_tool"}' in metrics

    def test_timer_api_operation(self):
        """Test timer with API operation."""
        reset_metrics()

        with MetricsTimer('api', 'test_method'):
            time.sleep(0.01)

        collector = get_metrics_collector()
        metrics = collector.get_metrics()

        assert 'telegram_api_calls_total{method="test_method",status="success"} 1.0' in metrics

    def test_timer_api_error(self):
        """Test timer with API error."""
        reset_metrics()

        try:
            with MetricsTimer('api', 'test_method'):
                raise Exception("API error")
        except Exception:
            pass

        collector = get_metrics_collector()
        metrics = collector.get_metrics()

        assert 'telegram_api_calls_total{method="test_method",status="error"} 1.0' in metrics


class TestMetricsIntegration:
    """Test metrics integration with other components."""

    @pytest.fixture
    def mock_message_processor(self):
        """Mock message processor for testing."""
        with patch('src.telegram_toolkit_mcp.core.filtering.get_message_processor') as mock_get:
            processor = Mock()
            processor.process_messages.return_value = []
            mock_get.return_value = processor
            yield processor

    @pytest.fixture
    def mock_paginator(self):
        """Mock paginator for testing."""
        with patch('src.telegram_toolkit_mcp.tools.fetch_history.Paginator') as mock_p:
            paginator = Mock()
            paginator.validate_page_size.return_value = 50
            paginator.should_continue_pagination.return_value = False
            mock_p.return_value = paginator
            yield paginator

    @pytest.mark.skip(reason="Requires MCP dependencies and complex setup")
    def test_metrics_with_fetch_history(self, mock_message_processor, mock_paginator):
        """Test metrics collection during fetch_history operation."""
        from src.telegram_toolkit_mcp.tools.fetch_history import fetch_history_tool

        # This would be a more comprehensive integration test
        # For now, just verify the metrics functions are callable
        reset_metrics()

        # Record some metrics manually
        record_messages_fetched("tg.fetch_history", 25, True)
        record_page_served("tg.fetch_history", "desc")
        record_ndjson_export("success", 2048)

        collector = get_metrics_collector()
        metrics = collector.get_metrics()

        # Verify all metrics are present
        assert 'telegram_messages_fetched_total{has_filters="True",tool="tg.fetch_history"} 25.0' in metrics
        assert 'telegram_pages_served_total{direction="desc",tool="tg.fetch_history"} 1.0' in metrics
        assert 'telegram_ndjson_exports_total{status="success"} 1.0' in metrics

    def test_metrics_with_resolve_chat(self):
        """Test metrics collection during resolve_chat operation."""
        reset_metrics()

        # Simulate resolve_chat metrics
        record_tool_success("tg.resolve_chat", "channel", 0.3)

        collector = get_metrics_collector()
        metrics = collector.get_metrics()

        assert 'mcp_tool_calls_total{chat_type="channel",status="success",tool="tg.resolve_chat"} 1.0' in metrics
        assert 'mcp_tool_duration_seconds_sum{status="success",tool="tg.resolve_chat"} 0.3' in metrics

    def test_metrics_error_scenarios(self):
        """Test metrics collection for error scenarios."""
        reset_metrics()

        # Record various error metrics
        record_tool_error("tg.fetch_history", "channel", 2.1)

        collector = get_metrics_collector()
        metrics = collector.get_metrics()

        assert 'mcp_tool_calls_total{chat_type="channel",status="error",tool="tg.fetch_history"} 1.0' in metrics

    def test_metrics_performance_scenarios(self):
        """Test metrics collection for performance scenarios."""
        reset_metrics()

        # Simulate high-load scenario
        for i in range(100):
            record_messages_fetched("tg.fetch_history", 50, False)

        collector = get_metrics_collector()
        metrics = collector.get_metrics()

        assert 'telegram_messages_fetched_total{has_filters="False",tool="tg.fetch_history"} 5000.0' in metrics

    def test_metrics_histogram_buckets(self, metrics_collector):
        """Test histogram bucket distribution."""
        # Record various durations
        durations = [0.1, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0]

        for duration in durations:
            metrics_collector.record_tool_call("test_tool", "success", duration=duration)

        metrics = metrics_collector.get_metrics()

        # Check that histogram buckets are working
        assert 'mcp_tool_duration_seconds_bucket{le="0.1",status="success",tool="test_tool"}' in metrics
        assert 'mcp_tool_duration_seconds_bucket{le="1.0",status="success",tool="test_tool"}' in metrics
        assert 'mcp_tool_duration_seconds_bucket{le="10.0",status="success",tool="test_tool"}' in metrics


class TestMetricsEdgeCases:
    """Test metrics edge cases and error conditions."""

    def test_metrics_with_none_values(self, metrics_collector):
        """Test metrics handling of None values."""
        metrics_collector.record_tool_call("test_tool", "success", duration=None)
        metrics_collector.record_telegram_api_call("test_method", "success", duration=None)
        metrics_collector.record_ndjson_export("success", size_bytes=None)

        # Should not raise exceptions
        metrics = metrics_collector.get_metrics()
        assert isinstance(metrics, str)

    def test_metrics_with_special_characters(self, metrics_collector):
        """Test metrics with special characters in labels."""
        metrics_collector.record_tool_call("test_tool_with_特殊字符", "success")
        metrics_collector.record_telegram_api_call("method_with_特殊字符", "success")

        metrics = metrics_collector.get_metrics()
        assert isinstance(metrics, str)

    def test_metrics_concurrent_access(self, metrics_collector):
        """Test metrics under concurrent access."""
        import asyncio

        async def record_metrics(worker_id: int):
            for i in range(10):
                metrics_collector.record_tool_call(f"worker_{worker_id}", "success", duration=0.1)

        async def run_concurrent():
            tasks = [record_metrics(i) for i in range(5)]
            await asyncio.gather(*tasks)

        asyncio.run(run_concurrent())

        metrics = metrics_collector.get_metrics()
        # Should have recorded 50 total calls (5 workers * 10 calls each)
        assert 'mcp_tool_calls_total{chat_type="unknown",status="success",tool="worker_0"}' in metrics

    def test_metrics_memory_efficiency(self, metrics_collector):
        """Test that metrics don't consume excessive memory."""
        # Record many metrics
        for i in range(1000):
            metrics_collector.record_tool_call(f"tool_{i % 10}", "success")

        # Should still be able to generate metrics without issues
        metrics = metrics_collector.get_metrics()
        assert len(metrics) > 0
        assert len(metrics.split('\n')) < 2000  # Reasonable limit
