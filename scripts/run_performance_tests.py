#!/usr/bin/env python3
"""
Performance Testing Suite for Telegram Toolkit MCP

This script provides comprehensive performance testing, benchmarking,
and load testing capabilities for the MCP server.
"""

import argparse
import asyncio
import json
import os
import sys
import time
from pathlib import Path
from typing import Dict, List, Any

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from telegram_toolkit_mcp.core.performance import (
    PerformanceMetrics,
    LoadTestConfig,
    PerformanceProfiler,
    LoadTester,
    PerformanceOptimizer,
    benchmark_async,
    run_load_test,
    run_stress_test,
    get_performance_profiler
)
from telegram_toolkit_mcp.core.monitoring import get_metrics_collector
from telegram_toolkit_mcp.utils.logging import get_logger


logger = get_logger(__name__)


class PerformanceTestSuite:
    """Comprehensive performance test suite."""

    def __init__(self):
        """Initialize the test suite."""
        self.profiler = get_performance_profiler()
        self.optimizer = PerformanceOptimizer()
        self.metrics_collector = get_metrics_collector()

    async def run_benchmark_tests(self) -> Dict[str, PerformanceMetrics]:
        """Run benchmark tests for core operations."""
        logger.info("🧪 Running Benchmark Tests")

        results = {}

        # Benchmark chat resolution
        logger.info("📊 Benchmarking chat resolution...")
        try:
            from telegram_toolkit_mcp.core.telegram_client import TelegramClientWrapper
            from telegram_toolkit_mcp.utils.config import get_config

            config = get_config()
            client_wrapper = TelegramClientWrapper()

            async def resolve_chat_operation():
                # Mock operation for benchmarking
                await asyncio.sleep(0.01)  # Simulate network delay
                return {"chat_id": "@telegram", "title": "Telegram"}

            results["chat_resolution"] = await benchmark_async(
                resolve_chat_operation,
                iterations=50,
                warmup_iterations=5
            )

            logger.info("✅ Chat resolution benchmark completed")

        except Exception as e:
            logger.warning(f"❌ Chat resolution benchmark failed: {e}")

        # Benchmark message processing
        logger.info("📊 Benchmarking message processing...")
        try:
            async def process_message_operation():
                # Mock message processing
                await asyncio.sleep(0.02)  # Simulate processing time
                return {"processed": True, "message_count": 10}

            results["message_processing"] = await benchmark_async(
                process_message_operation,
                iterations=30,
                warmup_iterations=3
            )

            logger.info("✅ Message processing benchmark completed")

        except Exception as e:
            logger.warning(f"❌ Message processing benchmark failed: {e}")

        # Benchmark resource creation
        logger.info("📊 Benchmarking resource creation...")
        try:
            async def create_resource_operation():
                # Mock resource creation
                await asyncio.sleep(0.05)  # Simulate I/O operations
                return {"resource_id": "test_123", "size_mb": 2.5}

            results["resource_creation"] = await benchmark_async(
                create_resource_operation,
                iterations=20,
                warmup_iterations=2
            )

            logger.info("✅ Resource creation benchmark completed")

        except Exception as e:
            logger.warning(f"❌ Resource creation benchmark failed: {e}")

        return results

    async def run_load_tests(self) -> Dict[str, PerformanceMetrics]:
        """Run load tests for concurrent operations."""
        logger.info("🧪 Running Load Tests")

        results = {}

        # Configure load test
        config = LoadTestConfig(
            duration_seconds=30,
            concurrent_users=5,  # Conservative for demo
            ramp_up_seconds=5,
            collect_system_metrics=True
        )

        # Define test operations
        async def light_operation():
            """Lightweight operation simulation."""
            await asyncio.sleep(0.1)  # 100ms operation
            return {"result": "success", "operation": "light"}

        async def medium_operation():
            """Medium operation simulation."""
            await asyncio.sleep(0.5)  # 500ms operation
            return {"result": "success", "operation": "medium"}

        async def heavy_operation():
            """Heavy operation simulation."""
            await asyncio.sleep(1.0)  # 1s operation
            return {"result": "success", "operation": "heavy"}

        operations = [light_operation, medium_operation, heavy_operation]
        weights = [0.7, 0.2, 0.1]  # Favor lighter operations

        try:
            results = await run_load_test(operations, config)

            # Add summary
            total_requests = sum(m.total_requests for m in results.values())
            total_successful = sum(m.successful_requests for m in results.values())
            success_rate = (total_successful / max(1, total_requests)) * 100

            logger.info("✅ Load test completed"            logger.info(".1f"            logger.info(f"📊 Total requests: {total_requests}")

            for name, metrics in results.items():
                logger.info(f"📈 {name}: {metrics.throughput_rps:.1f} RPS, "
                           f"{metrics.p95_latency:.3f}s P95")

        except Exception as e:
            logger.error(f"❌ Load test failed: {e}")

        return results

    async def run_stress_tests(self) -> List[PerformanceMetrics]:
        """Run stress tests with increasing concurrency."""
        logger.info("🧪 Running Stress Tests")

        results = []

        async def stress_operation():
            """Stress test operation."""
            await asyncio.sleep(0.2)  # 200ms operation
            return {"stressed": True}

        try:
            results = await run_stress_test(
                stress_operation,
                max_concurrent=20,  # Up to 20 concurrent users
                step_size=5
            )

            logger.info("✅ Stress test completed")
            logger.info(f"📊 Tested up to {len(results) * 5} concurrent users")

            for i, metrics in enumerate(results):
                concurrent_users = (i + 1) * 5
                logger.info(f"📈 {concurrent_users} users: "
                           f"{metrics.throughput_rps:.1f} RPS, "
                           f"{metrics.p95_latency:.3f}s P95, "
                           f"{metrics.calculate_error_rate():.1f}% errors")

        except Exception as e:
            logger.error(f"❌ Stress test failed: {e}")

        return results

    async def run_performance_analysis(self) -> Dict[str, Any]:
        """Run comprehensive performance analysis."""
        logger.info("🧪 Running Performance Analysis")

        # Run all tests
        benchmark_results = await self.run_benchmark_tests()
        load_results = await self.run_load_tests()
        stress_results = await self.run_stress_tests()

        # Set baselines for analysis
        for name, metrics in benchmark_results.items():
            self.optimizer.set_baseline(name, metrics)

        # Analyze performance
        analyses = {}
        for name, metrics in benchmark_results.items():
            analyses[name] = self.optimizer.analyze_performance(metrics)

        # Generate optimization report
        report = self.optimizer.generate_optimization_report(analyses)

        # Save results
        results_dir = Path(__file__).parent.parent / "performance_results"
        results_dir.mkdir(exist_ok=True)

        timestamp = time.strftime("%Y%m%d_%H%M%S")

        # Save benchmark results
        benchmark_file = results_dir / f"benchmark_results_{timestamp}.json"
        with open(benchmark_file, 'w') as f:
            json.dump({
                name: metrics.get_summary()
                for name, metrics in benchmark_results.items()
            }, f, indent=2)

        # Save load test results
        load_file = results_dir / f"load_results_{timestamp}.json"
        with open(load_file, 'w') as f:
            json.dump({
                name: metrics.get_summary()
                for name, metrics in load_results.items()
            }, f, indent=2)

        # Save stress test results
        stress_file = results_dir / f"stress_results_{timestamp}.json"
        with open(stress_file, 'w') as f:
            json.dump([
                metrics.get_summary() for metrics in stress_results
            ], f, indent=2)

        # Save optimization report
        report_file = results_dir / f"optimization_report_{timestamp}.md"
        with open(report_file, 'w') as f:
            f.write(report)

        logger.info("✅ Performance analysis completed")
        logger.info(f"📁 Results saved to: {results_dir}")

        return {
            "benchmark_results": benchmark_results,
            "load_results": load_results,
            "stress_results": stress_results,
            "analyses": analyses,
            "report": report,
            "results_directory": str(results_dir)
        }


def main():
    """Main entry point for performance testing."""
    parser = argparse.ArgumentParser(
        description="Performance Testing Suite for Telegram Toolkit MCP"
    )

    parser.add_argument(
        "--test-type",
        choices=["benchmark", "load", "stress", "analysis", "all"],
        default="analysis",
        help="Type of performance test to run"
    )

    parser.add_argument(
        "--duration",
        type=int,
        default=30,
        help="Test duration in seconds for load tests"
    )

    parser.add_argument(
        "--concurrency",
        type=int,
        default=10,
        help="Number of concurrent users for load tests"
    )

    parser.add_argument(
        "--iterations",
        type=int,
        default=100,
        help="Number of iterations for benchmark tests"
    )

    parser.add_argument(
        "--output-dir",
        type=str,
        default="performance_results",
        help="Output directory for results"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )

    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Generate reports from existing results"
    )

    args = parser.parse_args()

    # Configure logging
    if args.verbose:
        os.environ["LOG_LEVEL"] = "DEBUG"
    else:
        os.environ["LOG_LEVEL"] = "INFO"

    # Run tests
    async def run_tests():
        suite = PerformanceTestSuite()

        try:
            if args.test_type == "benchmark":
                logger.info("🚀 Running benchmark tests only")
                results = await suite.run_benchmark_tests()

            elif args.test_type == "load":
                logger.info("🚀 Running load tests only")
                config = LoadTestConfig(
                    duration_seconds=args.duration,
                    concurrent_users=args.concurrency
                )
                results = await suite.run_load_tests()

            elif args.test_type == "stress":
                logger.info("🚀 Running stress tests only")
                results = await suite.run_stress_tests()

            elif args.test_type == "analysis":
                logger.info("🚀 Running full performance analysis")
                results = await suite.run_performance_analysis()

            elif args.test_type == "all":
                logger.info("🚀 Running all performance tests")

                # Run individual tests
                benchmark_results = await suite.run_benchmark_tests()
                load_results = await suite.run_load_tests()
                stress_results = await suite.run_stress_tests()

                # Run analysis
                analysis_results = await suite.run_performance_analysis()

                results = {
                    "benchmark": benchmark_results,
                    "load": load_results,
                    "stress": stress_results,
                    "analysis": analysis_results
                }

            # Print summary
            print_performance_summary(results, args.test_type)

        except KeyboardInterrupt:
            logger.info("⏹️ Performance testing interrupted by user")
        except Exception as e:
            logger.error(f"❌ Performance testing failed: {e}")
            sys.exit(1)

    asyncio.run(run_tests())


def print_performance_summary(results: Any, test_type: str):
    """Print performance test summary."""
    print("\n" + "="*60)
    print("📊 PERFORMANCE TEST SUMMARY")
    print("="*60)

    if test_type in ["benchmark", "all"]:
        print("\n🏃 BENCHMARK RESULTS:")
        if "benchmark" in results:
            benchmark_data = results["benchmark"]
        else:
            benchmark_data = results

        for name, metrics in benchmark_data.items():
            summary = metrics.get_summary()
            print(f"  {name}:")
            print(".2f")
            print(".2f")
            print(".2f")
            print(".1f")
            print(".1f")

    if test_type in ["load", "all"]:
        print("\n📈 LOAD TEST RESULTS:")
        if "load" in results:
            load_data = results["load"]
        else:
            load_data = results

        for name, metrics in load_data.items():
            print(f"  {name}:")
            print(".1f")
            print(".3f")
            print(".1f")

    if test_type in ["stress", "all"]:
        print("\n💪 STRESS TEST RESULTS:")
        if "stress" in results:
            stress_data = results["stress"]
        else:
            stress_data = results

        for i, metrics in enumerate(stress_data):
            concurrent = (i + 1) * 5  # Based on step_size=5
            print(f"  {concurrent} users:")
            print(".1f")
            print(".3f")
            print(".1f")

    if test_type in ["analysis", "all"]:
        print("\n🔍 PERFORMANCE ANALYSIS:")
        if "analysis" in results:
            analysis_data = results["analysis"]
            analyses = analysis_data.get("analyses", {})

            critical = sum(1 for a in analyses.values() if a.get("status") == "critical")
            warning = sum(1 for a in analyses.values() if a.get("status") == "warning")
            ok = sum(1 for a in analyses.values() if a.get("status") == "ok")

            print(f"  Status: {critical} critical, {warning} warnings, {ok} OK")
            print(f"  Report saved: {analysis_data.get('results_directory', 'N/A')}")

    print("\n" + "="*60)
    print("✅ Performance testing completed!")
    print("="*60)


if __name__ == "__main__":
    main()
