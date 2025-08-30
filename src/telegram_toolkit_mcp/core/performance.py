"""
Performance optimization and load testing for Telegram Toolkit MCP.

This module provides comprehensive performance testing, benchmarking,
and optimization capabilities for enterprise-grade production deployment.
"""

import asyncio
import gc
import statistics
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any

import psutil

from ..utils.logging import get_logger
from .monitoring import get_metrics_collector
from .tracing import get_tracer

logger = get_logger(__name__)


@dataclass
class PerformanceMetrics:
    """Performance metrics for operations."""

    operation_name: str
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    response_times: list[float] = field(default_factory=list)
    error_rates: list[float] = field(default_factory=list)
    throughput_rps: float = 0.0
    p50_latency: float = 0.0
    p95_latency: float = 0.0
    p99_latency: float = 0.0
    min_latency: float = float("inf")
    max_latency: float = 0.0
    memory_usage_mb: float = 0.0
    cpu_usage_percent: float = 0.0

    def add_measurement(self, response_time: float, success: bool = True):
        """Add a performance measurement."""
        self.total_requests += 1
        self.response_times.append(response_time)

        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1

        # Update min/max
        self.min_latency = min(self.min_latency, response_time)
        self.max_latency = max(self.max_latency, response_time)

    def calculate_percentiles(self):
        """Calculate latency percentiles."""
        if not self.response_times:
            return

        sorted_times = sorted(self.response_times)
        n = len(sorted_times)

        self.p50_latency = sorted_times[int(n * 0.5)]
        self.p95_latency = sorted_times[int(n * 0.95)]
        self.p99_latency = sorted_times[int(n * 0.99)]

    def calculate_throughput(self, duration_seconds: float):
        """Calculate requests per second."""
        if duration_seconds > 0:
            self.throughput_rps = self.total_requests / duration_seconds

    def calculate_error_rate(self):
        """Calculate error rate percentage."""
        if self.total_requests > 0:
            error_rate = (self.failed_requests / self.total_requests) * 100
            self.error_rates.append(error_rate)
            return error_rate
        return 0.0

    def get_summary(self) -> dict[str, Any]:
        """Get performance summary."""
        self.calculate_percentiles()

        return {
            "operation": self.operation_name,
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "success_rate_percent": (self.successful_requests / max(1, self.total_requests)) * 100,
            "throughput_rps": self.throughput_rps,
            "latency_ms": {
                "min": self.min_latency * 1000,
                "max": self.max_latency * 1000,
                "p50": self.p50_latency * 1000,
                "p95": self.p95_latency * 1000,
                "p99": self.p99_latency * 1000,
                "avg": statistics.mean(self.response_times) * 1000 if self.response_times else 0,
            },
            "memory_usage_mb": self.memory_usage_mb,
            "cpu_usage_percent": self.cpu_usage_percent,
        }


@dataclass
class LoadTestConfig:
    """Configuration for load testing."""

    duration_seconds: int = 60
    concurrent_users: int = 10
    ramp_up_seconds: int = 10
    target_rps: int | None = None
    request_timeout: float = 30.0
    collect_system_metrics: bool = True
    enable_tracing: bool = False


class PerformanceProfiler:
    """Performance profiler for individual operations."""

    def __init__(self):
        """Initialize the performance profiler."""
        self.metrics_collector = get_metrics_collector()
        self.tracer = get_tracer("performance_profiler")

    @asynccontextmanager
    async def profile_operation(
        self, operation_name: str, collect_memory: bool = True, collect_cpu: bool = True
    ):
        """Profile an operation with comprehensive metrics."""
        start_time = time.time()
        start_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
        start_cpu = psutil.cpu_percent()

        with self.tracer.start_as_current_span(
            f"profile.{operation_name}",
            attributes={
                "operation.name": operation_name,
                "profiling.memory": collect_memory,
                "profiling.cpu": collect_cpu,
            },
        ) as span:
            try:
                yield span

                # Calculate metrics
                end_time = time.time()
                duration = end_time - start_time

                end_memory = psutil.Process().memory_info().rss / 1024 / 1024  # MB
                memory_delta = end_memory - start_memory

                end_cpu = psutil.cpu_percent()
                cpu_delta = end_cpu - start_cpu

                # Add span attributes
                span.set_attribute("operation.duration_seconds", duration)
                span.set_attribute("operation.memory_delta_mb", memory_delta)
                span.set_attribute("operation.cpu_delta_percent", cpu_delta)

                # Log performance
                logger.info(
                    f"Operation '{operation_name}' completed",
                    duration_seconds=duration,
                    memory_delta_mb=memory_delta,
                    cpu_delta_percent=cpu_delta,
                )

            except Exception as e:
                span.record_exception(e)
                span.set_status("ERROR", str(e))
                raise

    async def benchmark_operation(
        self, operation: Callable, iterations: int = 100, warmup_iterations: int = 10
    ) -> PerformanceMetrics:
        """Benchmark an operation with statistical analysis."""
        logger.info(f"Benchmarking operation with {iterations} iterations")

        metrics = PerformanceMetrics(operation.__name__)

        # Warmup
        logger.info(f"Running {warmup_iterations} warmup iterations")
        for i in range(warmup_iterations):
            try:
                await operation()
            except Exception:
                pass  # Ignore warmup errors

        # Force garbage collection
        gc.collect()

        # Benchmark iterations
        for i in range(iterations):
            start_time = time.time()

            try:
                await operation()
                success = True
            except Exception as e:
                logger.warning(f"Benchmark iteration {i+1} failed: {e}")
                success = False

            end_time = time.time()
            response_time = end_time - start_time

            metrics.add_measurement(response_time, success)

        # Calculate final metrics
        metrics.calculate_error_rate()
        metrics.memory_usage_mb = psutil.Process().memory_info().rss / 1024 / 1024
        metrics.cpu_usage_percent = psutil.cpu_percent()

        return metrics


class LoadTester:
    """Load testing framework for MCP server."""

    def __init__(self, config: LoadTestConfig):
        """Initialize load tester."""
        self.config = config
        self.profiler = PerformanceProfiler()
        self.metrics_collector = get_metrics_collector()
        self.tracer = get_tracer("load_tester")

    async def run_load_test(
        self, operations: list[Callable], operation_weights: list[float] | None = None
    ) -> dict[str, PerformanceMetrics]:
        """Run comprehensive load test."""
        logger.info("Starting load test", config=self.config.__dict__)

        if operation_weights is None:
            operation_weights = [1.0 / len(operations)] * len(operations)

        # Initialize metrics for each operation
        operation_metrics = {}
        for op in operations:
            operation_metrics[op.__name__] = PerformanceMetrics(op.__name__)

        start_time = time.time()

        # Create task pool
        semaphore = asyncio.Semaphore(self.config.concurrent_users)

        async def worker():
            """Worker coroutine for load generation."""
            while True:
                # Check if test duration exceeded
                if time.time() - start_time > self.config.duration_seconds:
                    break

                async with semaphore:
                    # Select operation based on weights
                    op = self._select_operation(operations, operation_weights)

                    # Execute operation
                    op_start_time = time.time()
                    try:
                        await op()
                        success = True
                    except Exception as e:
                        logger.warning(f"Load test operation failed: {e}")
                        success = False

                    op_end_time = time.time()
                    response_time = op_end_time - op_start_time

                    # Record metrics
                    operation_metrics[op.__name__].add_measurement(response_time, success)

                # Small delay to prevent overwhelming
                await asyncio.sleep(0.01)

        # Run workers
        workers = []
        for i in range(self.config.concurrent_users):
            task = asyncio.create_task(worker())
            workers.append(task)

        # Wait for test duration
        await asyncio.sleep(self.config.duration_seconds)

        # Cancel workers
        for task in workers:
            task.cancel()

        try:
            await asyncio.gather(*workers, return_exceptions=True)
        except asyncio.CancelledError:
            pass

        # Calculate final metrics
        total_duration = time.time() - start_time

        for metrics in operation_metrics.values():
            metrics.calculate_throughput(total_duration)
            metrics.calculate_error_rate()
            metrics.memory_usage_mb = psutil.Process().memory_info().rss / 1024 / 1024
            metrics.cpu_usage_percent = psutil.cpu_percent()

        logger.info(
            "Load test completed",
            total_duration_seconds=total_duration,
            operations_tested=len(operations),
        )

        return operation_metrics

    def _select_operation(self, operations: list[Callable], weights: list[float]) -> Callable:
        """Select operation based on weights."""
        import random

        return random.choices(operations, weights=weights)[0]

    async def run_stress_test(
        self, operation: Callable, max_concurrent: int = 100, step_size: int = 10
    ) -> list[PerformanceMetrics]:
        """Run stress test with increasing concurrency."""
        logger.info(f"Starting stress test up to {max_concurrent} concurrent users")

        results = []

        for concurrent in range(step_size, max_concurrent + 1, step_size):
            logger.info(f"Testing with {concurrent} concurrent users")

            config = LoadTestConfig(
                duration_seconds=30,  # Shorter duration for stress test
                concurrent_users=concurrent,
                ramp_up_seconds=5,
            )

            stress_tester = LoadTester(config)
            metrics = await stress_tester.run_load_test([operation])

            result = list(metrics.values())[0]
            results.append(result)

            # Check for performance degradation
            if result.p95_latency > 10.0:  # 10 seconds
                logger.warning(
                    f"High latency detected at {concurrent} users: {result.p95_latency:.2f}s"
                )

            if result.calculate_error_rate() > 20.0:  # 20% error rate
                logger.error(
                    f"High error rate detected at {concurrent} users: {result.calculate_error_rate():.1f}%"
                )

        return results


class PerformanceOptimizer:
    """Performance optimization recommendations and analysis."""

    def __init__(self):
        """Initialize performance optimizer."""
        self.baseline_metrics = {}

    def set_baseline(self, operation_name: str, metrics: PerformanceMetrics):
        """Set baseline performance metrics."""
        self.baseline_metrics[operation_name] = metrics

    def analyze_performance(self, current_metrics: PerformanceMetrics) -> dict[str, Any]:
        """Analyze performance against baseline."""
        if current_metrics.operation_name not in self.baseline_metrics:
            return {"status": "no_baseline", "recommendations": []}

        baseline = self.baseline_metrics[current_metrics.operation_name]

        analysis = {
            "operation": current_metrics.operation_name,
            "status": "ok",
            "recommendations": [],
            "comparisons": {},
        }

        # Compare key metrics
        comparisons = {
            "latency_p50": (current_metrics.p50_latency, baseline.p50_latency),
            "latency_p95": (current_metrics.p95_latency, baseline.p95_latency),
            "throughput": (current_metrics.throughput_rps, baseline.throughput_rps),
            "error_rate": (current_metrics.calculate_error_rate(), baseline.calculate_error_rate()),
        }

        analysis["comparisons"] = comparisons

        # Generate recommendations
        recommendations = []

        # Latency analysis
        if current_metrics.p95_latency > baseline.p95_latency * 1.5:
            recommendations.append(
                {
                    "type": "latency",
                    "severity": "high",
                    "message": ".2f",
                    "suggestions": [
                        "Consider optimizing database queries",
                        "Implement response caching",
                        "Review network latency",
                        "Check for memory leaks",
                    ],
                }
            )

        # Throughput analysis
        if current_metrics.throughput_rps < baseline.throughput_rps * 0.8:
            recommendations.append(
                {
                    "type": "throughput",
                    "severity": "medium",
                    "message": ".2f",
                    "suggestions": [
                        "Optimize concurrent request handling",
                        "Implement request queuing",
                        "Review resource allocation",
                        "Consider horizontal scaling",
                    ],
                }
            )

        # Error rate analysis
        if current_metrics.calculate_error_rate() > baseline.calculate_error_rate() * 2:
            recommendations.append(
                {
                    "type": "reliability",
                    "severity": "high",
                    "message": ".1f",
                    "suggestions": [
                        "Review error handling logic",
                        "Check for resource exhaustion",
                        "Implement circuit breaker pattern",
                        "Add comprehensive logging",
                    ],
                }
            )

        analysis["recommendations"] = recommendations

        # Determine overall status
        if any(r["severity"] == "high" for r in recommendations):
            analysis["status"] = "critical"
        elif recommendations:
            analysis["status"] = "warning"

        return analysis

    def generate_optimization_report(self, analyses: dict[str, dict]) -> str:
        """Generate comprehensive optimization report."""
        report_lines = [
            "# Performance Optimization Report",
            "",
            f"Generated: {time.strftime('%Y-%m-%d %H:%M:%S')}",
            "",
            "## Summary",
            "",
        ]

        critical_count = sum(1 for a in analyses.values() if a.get("status") == "critical")
        warning_count = sum(1 for a in analyses.values() if a.get("status") == "warning")
        ok_count = sum(1 for a in analyses.values() if a.get("status") == "ok")

        report_lines.extend(
            [
                f"- Critical Issues: {critical_count}",
                f"- Warning Issues: {warning_count}",
                f"- OK Operations: {ok_count}",
                "",
                "## Detailed Analysis",
                "",
            ]
        )

        for operation, analysis in analyses.items():
            report_lines.extend(
                [
                    f"### {operation}",
                    "",
                    f"**Status:** {analysis.get('status', 'unknown').upper()}",
                    "",
                    "#### Key Metrics",
                ]
            )

            comparisons = analysis.get("comparisons", {})
            for metric, (current, baseline) in comparisons.items():
                change = ((current - baseline) / baseline * 100) if baseline > 0 else 0
                report_lines.append(
                    f"- {metric}: {current:.2f} (vs {baseline:.2f}, {change:+.1f}%)"
                )

            recommendations = analysis.get("recommendations", [])
            if recommendations:
                report_lines.extend(
                    [
                        "",
                        "#### Recommendations",
                    ]
                )
                for rec in recommendations:
                    report_lines.extend(
                        [
                            f"- **{rec['type'].upper()}** ({rec['severity']}): {rec['message']}",
                            f"  - Suggestions: {', '.join(rec['suggestions'])}",
                        ]
                    )

            report_lines.append("")

        return "\n".join(report_lines)


# Global performance utilities
_performance_profiler = None


def get_performance_profiler() -> PerformanceProfiler:
    """Get global performance profiler instance."""
    global _performance_profiler
    if _performance_profiler is None:
        _performance_profiler = PerformanceProfiler()
    return _performance_profiler


async def profile_async(func: Callable, *args, **kwargs) -> Any:
    """Profile an async function execution."""
    profiler = get_performance_profiler()

    async with profiler.profile_operation(func.__name__):
        return await func(*args, **kwargs)


def profile_sync(func: Callable, *args, **kwargs) -> Any:
    """Profile a sync function execution."""
    profiler = get_performance_profiler()

    with profiler.profile_operation(func.__name__):
        return func(*args, **kwargs)


async def benchmark_async(
    func: Callable, iterations: int = 100, warmup_iterations: int = 10, *args, **kwargs
) -> PerformanceMetrics:
    """Benchmark an async function."""
    profiler = get_performance_profiler()

    async def operation():
        return await func(*args, **kwargs)

    return await profiler.benchmark_operation(operation, iterations, warmup_iterations)


def benchmark_sync(
    func: Callable, iterations: int = 100, warmup_iterations: int = 10, *args, **kwargs
) -> PerformanceMetrics:
    """Benchmark a sync function."""
    profiler = get_performance_profiler()

    def operation():
        return func(*args, **kwargs)

    # Convert sync benchmark to async
    async def async_operation():
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as executor:
            return await loop.run_in_executor(executor, operation)

    return asyncio.run(profiler.benchmark_operation(async_operation, iterations, warmup_iterations))


async def run_load_test(
    operations: list[Callable], config: LoadTestConfig | None = None
) -> dict[str, PerformanceMetrics]:
    """Run load test with default configuration."""
    if config is None:
        config = LoadTestConfig()

    tester = LoadTester(config)
    return await tester.run_load_test(operations)


async def run_stress_test(
    operation: Callable,
    max_concurrent: int = 100,
    config: LoadTestConfig | None = None,
    step_size: int = 5,
) -> list[PerformanceMetrics]:
    """Run stress test with default configuration.

    Args:
        operation: Async callable to test
        max_concurrent: Maximum number of concurrent operations
        config: Load test configuration (optional)
        step_size: Step size for increasing concurrent users (default: 5)

    Returns:
        List of performance metrics for each concurrency level
    """
    if config is None:
        config = LoadTestConfig(duration_seconds=30, ramp_up_seconds=5)

    tester = LoadTester(config)
    return await tester.run_stress_test(operation, max_concurrent, step_size)
