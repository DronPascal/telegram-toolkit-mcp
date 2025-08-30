#!/usr/bin/env python3
"""
Test Configuration for Telegram Toolkit MCP

This module provides centralized configuration for all test suites,
including timeouts, dependencies, and test-specific settings.
"""

import os
from pathlib import Path

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
SRC_PATH = PROJECT_ROOT / "src"
TESTS_PATH = PROJECT_ROOT / "tests"

# Test directories
UNIT_TESTS = TESTS_PATH / "unit"
INTEGRATION_TESTS = TESTS_PATH / "integration"
E2E_TESTS = TESTS_PATH / "e2e"

# Default timeouts (seconds)
TIMEOUTS = {
    "unit": 60,  # 1 minute
    "integration": 120,  # 2 minutes
    "e2e": 300,  # 5 minutes
    "performance": 600,  # 10 minutes
    "overall": 1800,  # 30 minutes total
}

# Test dependencies by category
DEPENDENCIES = {
    "basic": ["pytest", "pytest_asyncio", "pytest_cov"],
    "e2e": ["telethon", "mcp", "httpx", "aiohttp"],
    "performance": ["psutil", "memory_profiler"],
    "optional": ["python-dotenv", "rich", "tabulate"],
}

# Environment variables required for different test types
REQUIRED_ENV_VARS = {
    "e2e": ["TELEGRAM_API_ID", "TELEGRAM_API_HASH"],
    "performance": [],  # No specific requirements
    "integration": [],  # No specific requirements
    "unit": [],  # No specific requirements
}

# Test patterns for different categories
TEST_PATTERNS = {
    "unit": ["test_*.py", "*_test.py"],
    "integration": ["test_*integration*.py", "*_integration_test.py"],
    "e2e": ["test_*e2e*.py", "*_e2e_test.py"],
    "performance": ["test_*performance*.py", "*_performance_test.py"],
}

# Pytest configuration
PYTEST_CONFIG = {
    "addopts": [
        "--strict-markers",
        "--strict-config",
        "--asyncio-mode=auto",
        "--tb=short",
        "--disable-warnings",
    ],
    "markers": [
        "unit: Unit tests",
        "integration: Integration tests",
        "e2e: End-to-end tests",
        "performance: Performance tests",
        "slow: Slow running tests",
        "flaky: Potentially unstable tests",
    ],
    "filterwarnings": ["ignore::DeprecationWarning", "ignore::PendingDeprecationWarning"],
}


class TestConfig:
    """Centralized test configuration."""

    def __init__(self):
        self._setup_paths()
        self._load_environment()

    def _setup_paths(self):
        """Setup test paths."""
        self.project_root = PROJECT_ROOT
        self.src_path = SRC_PATH
        self.tests_path = TESTS_PATH
        self.unit_tests = UNIT_TESTS
        self.integration_tests = INTEGRATION_TESTS
        self.e2e_tests = E2E_TESTS

    def _load_environment(self):
        """Load environment variables and .env file."""
        # Try to load .env file if available
        env_file = self.project_root / ".env"
        if env_file.exists():
            try:
                from dotenv import load_dotenv

                load_dotenv(env_file)
            except ImportError:
                pass  # python-dotenv not available

    def get_timeout(self, test_type: str) -> int:
        """Get timeout for specific test type."""
        return TIMEOUTS.get(test_type, TIMEOUTS["unit"])

    def get_dependencies(self, test_type: str) -> list[str]:
        """Get required dependencies for test type."""
        deps = DEPENDENCIES["basic"].copy()

        if test_type in DEPENDENCIES:
            deps.extend(DEPENDENCIES[test_type])

        return deps

    def check_dependencies(self, test_type: str) -> list[str]:
        """Check if required dependencies are installed."""
        import importlib.util

        required = self.get_dependencies(test_type)
        missing = []

        for dep in required:
            if importlib.util.find_spec(dep) is None:
                missing.append(dep)

        return missing

    def get_required_env_vars(self, test_type: str) -> list[str]:
        """Get required environment variables for test type."""
        return REQUIRED_ENV_VARS.get(test_type, [])

    def check_environment(self, test_type: str) -> list[str]:
        """Check if required environment variables are set."""
        required = self.get_required_env_vars(test_type)
        missing = []

        for var in required:
            if not os.getenv(var):
                missing.append(var)

        return missing

    def get_pytest_args(
        self, test_type: str, verbose: bool = False, fail_fast: bool = False
    ) -> list[str]:
        """Get pytest command line arguments for test type."""
        args = ["-m", "pytest"]

        # Add test type marker if applicable
        if test_type in ["e2e", "performance"]:
            args.extend(["-m", test_type])

        # Add verbosity
        if verbose:
            args.append("-v")
        else:
            args.append("-q")

        # Add fail fast
        if fail_fast:
            args.append("--maxfail=1")

        # Add timeout
        timeout = self.get_timeout(test_type)
        args.extend(["--timeout", str(timeout)])

        return args

    def get_test_paths(self, test_type: str) -> list[Path]:
        """Get test file paths for test type."""
        base_paths = {
            "unit": [self.unit_tests],
            "integration": [self.integration_tests],
            "e2e": [self.e2e_tests],
            "performance": [
                self.unit_tests,
                self.integration_tests,
                self.e2e_tests,
            ],  # Performance tests in all dirs
        }

        return base_paths.get(test_type, [])

    def is_test_ready(self, test_type: str) -> dict[str, any]:
        """Check if test type is ready to run."""
        result = {"ready": True, "missing_deps": [], "missing_env": [], "warnings": []}

        # Check dependencies
        missing_deps = self.check_dependencies(test_type)
        if missing_deps:
            result["missing_deps"] = missing_deps
            if test_type == "e2e":
                result["ready"] = False
                result["warnings"].append("E2E tests require missing dependencies")
            else:
                result["warnings"].append(f"Some dependencies missing: {missing_deps}")

        # Check environment
        missing_env = self.check_environment(test_type)
        if missing_env:
            result["missing_env"] = missing_env
            if test_type == "e2e":
                result["ready"] = False
                result["warnings"].append("E2E tests require environment variables")
            else:
                result["warnings"].append(f"Environment variables missing: {missing_env}")

        return result

    def get_environment_vars(self) -> dict[str, str]:
        """Get environment variables for test execution."""
        env = os.environ.copy()
        env["PYTHONPATH"] = str(self.src_path)
        env.setdefault("DEBUG", "true")
        env.setdefault("LOG_LEVEL", "INFO")

        return env


# Global configuration instance
config = TestConfig()


def get_test_config() -> TestConfig:
    """Get global test configuration instance."""
    return config
