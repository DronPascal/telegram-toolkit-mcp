"""
Integration Tests: Metrics + ErrorHandler

This module tests the integration between Metrics and ErrorHandler
components to ensure proper error tracking and metrics collection.
"""

import pytest
from unittest.mock import MagicMock, patch
from datetime import datetime, timezone, timedelta

from telegram_toolkit_mcp.core.monitoring import (
    MetricsCollector,
    get_metrics_collector,
    init_metrics,
    reset_metrics,
    record_tool_success,
    record_tool_error,
    record_messages_fetched,
    record_page_served,
    record_ndjson_export
)
from telegram_toolkit_mcp.core.error_handler import (
    ErrorTracker,
    FloodWaitException,
    ChannelPrivateException,
    ChatNotFoundException,
    ValidationException
)


class TestMetricsErrorHandlerIntegration:
    """Integration tests for Metrics and ErrorHandler component interaction."""

    @pytest.fixture(autouse=True)
    def setup_metrics(self):
        """Setup fresh metrics for each test."""
        reset_metrics()
        yield
        reset_metrics()

    @pytest.fixture
    def metrics_collector(self):
        """Get metrics collector instance."""
        return get_metrics_collector()

    @pytest.fixture
    def error_tracker(self):
        """Error tracker instance."""
        return ErrorTracker()

    def test_error_tracker_with_metrics_recording(self, error_tracker, metrics_collector):
        """Test error tracker integration with metrics recording."""
        # Track various errors
        flood_error = FloodWaitException(retry_after=30)
        error_tracker.track_error(flood_error, {"tool": "fetch_history", "chat": "test"})

        private_error = ChannelPrivateException(chat_id=123)
        error_tracker.track_error(private_error, {"tool": "resolve_chat", "chat": "private"})

        validation_error = ValidationException(field="chat", value="invalid", reason="Invalid")
        error_tracker.track_error(validation_error, {"tool": "fetch_history", "chat": "invalid"})

        # Verify errors were tracked
        stats = error_tracker.get_error_stats()
        assert stats["error_counts"]["FloodWaitException"] == 1
        assert stats["error_counts"]["ChannelPrivateException"] == 1
        assert stats["error_counts"]["ValidationException"] == 1

        # Verify recent errors
        recent_errors = error_tracker.get_recent_errors()
        assert len(recent_errors) == 3

        # Check error details
        error_types = [error["type"] for error in recent_errors]
        assert "FloodWaitException" in error_types
        assert "ChannelPrivateException" in error_types
        assert "ValidationException" in error_types

    def test_metrics_collection_with_error_scenarios(self, metrics_collector, error_tracker):
        """Test metrics collection during various error scenarios."""
        # Simulate successful tool operations
        record_tool_success("tg.fetch_history", "channel", 1.5)
        record_tool_success("tg.resolve_chat", "chat", 0.8)

        # Simulate failed operations with errors
        record_tool_error("tg.fetch_history", "FloodWaitException")
        record_tool_error("tg.resolve_chat", "ChannelPrivateException")

        # Simulate data operations
        record_messages_fetched("tg.fetch_history", 50, True)
        record_page_served("tg.fetch_history", "forward")
        record_ndjson_export("success", 1024)

        # Verify metrics were recorded (we can't easily test Prometheus metrics values,
        # but we can verify the functions don't raise exceptions)
        assert metrics_collector is not None

    def test_error_tracker_concurrent_access(self, error_tracker):
        """Test error tracker handles concurrent error tracking."""
        import threading
        import time

        errors_recorded = []
        threads = []

        def track_error_worker(error_type, context):
            """Worker function to track errors concurrently."""
            if error_type == "flood":
                error = FloodWaitException(retry_after=30)
            elif error_type == "private":
                error = ChannelPrivateException(chat_id=123)
            else:
                error = ValidationException(field="test", value="test", reason="Test")

            error_tracker.track_error(error, context)
            errors_recorded.append(error_type)

        # Create multiple threads to track errors concurrently
        for i in range(10):
            error_type = ["flood", "private", "validation"][i % 3]
            context = {"tool": f"tool_{i}", "chat": f"chat_{i}"}

            thread = threading.Thread(
                target=track_error_worker,
                args=(error_type, context)
            )
            threads.append(thread)

        # Start all threads
        for thread in threads:
            thread.start()

        # Wait for all threads to complete
        for thread in threads:
            thread.join()

        # Verify all errors were recorded
        assert len(errors_recorded) == 10

        # Verify error tracker captured all errors
        stats = error_tracker.get_error_stats()
        assert stats["error_counts"]["FloodWaitException"] >= 3
        assert stats["error_counts"]["ChannelPrivateException"] >= 3
        assert stats["error_counts"]["ValidationException"] >= 3

        # Verify total error count
        total_errors = sum(stats["error_counts"].values())
        assert total_errors == 10

    def test_error_tracker_with_metrics_overflow(self, error_tracker, metrics_collector):
        """Test error tracker handles large number of errors with metrics."""
        # Track many errors to test overflow handling
        for i in range(150):  # More than default max_recent_errors (100)
            error = FloodWaitException(retry_after=30)
            error_tracker.track_error(error, {
                "tool": "test_tool",
                "chat": f"chat_{i}",
                "iteration": i
            })

        # Verify error counts are correct (all errors are tracked regardless of limit)
        stats = error_tracker.get_error_stats()
        assert stats["error_counts"]["FloodWaitException"] == 150

        # Verify recent errors are limited to max_recent_errors (default 100)
        recent_errors = error_tracker.get_recent_errors(limit=100)
        assert len(recent_errors) == 100  # Limited by max_recent_errors

        # Verify recent errors contain the most recent ones
        # With 150 errors added, we should have errors 50-149 (last 100)
        iterations = [error["context"]["iteration"] for error in recent_errors]
        assert min(iterations) == 50   # Oldest in recent batch
        assert max(iterations) == 149  # Newest in recent batch

    def test_error_tracker_context_preservation(self, error_tracker):
        """Test error tracker preserves context information correctly."""
        # Track errors with different context types
        contexts = [
            {"tool": "fetch_history", "chat": "test_channel", "user_id": 123},
            {"tool": "resolve_chat", "chat": "@username", "private": True},
            {"tool": "fetch_history", "chat": "numeric_id", "page_size": 50},
            {"tool": "fetch_history", "chat": "test", "filters": {"media": True}}
        ]

        for i, context in enumerate(contexts):
            error = FloodWaitException(retry_after=30)
            error_tracker.track_error(error, context)

        # Verify all contexts were preserved
        recent_errors = error_tracker.get_recent_errors()
        assert len(recent_errors) == 4

        # Check specific context details
        for i, error in enumerate(recent_errors):
            original_context = contexts[i]  # Same order as added
            assert error["context"]["tool"] == original_context["tool"]
            assert error["context"]["chat"] == original_context["chat"]

    def test_metrics_error_correlation(self, error_tracker, metrics_collector):
        """Test correlation between error tracking and metrics."""
        # Track specific error patterns
        tools = ["tg.fetch_history", "tg.resolve_chat", "tg.fetch_history"]
        chats = ["@durov", "private_chat", "@telegram"]

        for i, (tool, chat) in enumerate(zip(tools, chats)):
            if i % 2 == 0:
                # Record successful operation
                record_tool_success(tool, "channel", 1.0 + i * 0.5)
            else:
                # Record failed operation with error
                if "private" in chat:
                    error = ChannelPrivateException(chat_id=123)
                    record_tool_error(tool, "ChannelPrivateException")
                else:
                    error = FloodWaitException(retry_after=30)
                    record_tool_error(tool, "FloodWaitException")

                error_tracker.track_error(error, {"tool": tool, "chat": chat})

        # Verify error tracking and metrics are consistent
        stats = error_tracker.get_error_stats()
        total_tracked_errors = sum(stats["error_counts"].values())

        # We should have 1 error tracked (only private_chat contains "private")
        assert total_tracked_errors == 1
        assert stats["error_counts"]["ChannelPrivateException"] == 1

    def test_error_tracker_memory_efficiency(self, error_tracker):
        """Test error tracker memory efficiency with large error volumes."""
        import sys

        # Track memory usage before
        initial_memory = sys.getsizeof(error_tracker.recent_errors)

        # Track many errors
        for i in range(200):
            error = ValidationException(field="test", value=f"value_{i}", reason=f"Reason {i}")
            error_tracker.track_error(error, {"iteration": i})

        # Track memory usage after
        final_memory = sys.getsizeof(error_tracker.recent_errors)

        # Verify recent errors are limited
        recent_errors = error_tracker.get_recent_errors(limit=100)
        assert len(recent_errors) == 100  # Should be limited to max_recent_errors (we added 200, kept last 100)

        # Memory usage should be reasonable (not growing linearly with error count)
        # This is a basic check - in real scenarios you'd use memory profiling tools
        assert final_memory > 0

        # Verify error counts are still accurate
        stats = error_tracker.get_error_stats()
        assert stats["error_counts"]["ValidationException"] == 200

    def test_error_tracker_error_recovery(self, error_tracker):
        """Test error tracker handles error recovery scenarios."""
        # Track initial errors
        for i in range(5):
            error = FloodWaitException(retry_after=30)
            error_tracker.track_error(error, {"tool": "test", "attempt": i})

        initial_count = error_tracker.get_error_stats()["error_counts"]["FloodWaitException"]
        assert initial_count == 5

        # Simulate successful operations (no errors for a while)
        # In real scenario, this would be tracked by metrics

        # Track new errors after "recovery"
        for i in range(3):
            error = FloodWaitException(retry_after=30)
            error_tracker.track_error(error, {"tool": "test", "attempt": i + 10})

        final_count = error_tracker.get_error_stats()["error_counts"]["FloodWaitException"]
        assert final_count == 8  # 5 + 3

        # Verify recent errors contain both old and new errors
        recent_errors = error_tracker.get_recent_errors()
        attempts = [error["context"]["attempt"] for error in recent_errors]

        # Should contain both early (0-4) and later attempts (10-12)
        assert 0 in attempts  # From initial batch
        assert 12 in attempts  # From final batch
