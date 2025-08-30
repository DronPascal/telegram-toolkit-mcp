#!/usr/bin/env python3
"""
Integration Tests Runner for Telegram Toolkit MCP

This script runs integration tests with proper configuration and environment setup.
Integration tests validate component interactions and data flow between modules.
"""

import os
import subprocess
import sys
from pathlib import Path

# Add src to path
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

# Import test configuration
from test_config import get_test_config

# Initialize configuration
test_config = get_test_config()


def run_integration_tests(verbose: bool = False, fail_fast: bool = False) -> tuple[int, str]:
    """Run integration tests and return exit code and output."""
    print("🔗 Running Integration Tests...")

    # Build pytest command
    cmd = [
        "pytest",
        "tests/integration/",
        "--tb=short",
        "-v" if verbose else "-q",
        "--asyncio-mode=auto"
    ]

    if fail_fast:
        cmd.append("--maxfail=1")

    # Set up environment
    env = test_config.get_environment_vars()

    try:
        result = subprocess.run(
            cmd,
            cwd=test_config.project_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=test_config.get_timeout("integration")
        )

        return result.returncode, result.stdout + result.stderr

    except subprocess.TimeoutExpired:
        error_msg = f"Integration tests timed out after {test_config.get_timeout('integration')} seconds"
        return 1, error_msg
    except Exception as e:
        return 1, f"Error running integration tests: {e}"


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Run Integration Tests for Telegram Toolkit MCP")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first failure")

    args = parser.parse_args()

    # Run tests
    exit_code, output = run_integration_tests(verbose=args.verbose, fail_fast=args.fail_fast)

    # Print output
    if output:
        print(output)

    # Exit with appropriate code
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
