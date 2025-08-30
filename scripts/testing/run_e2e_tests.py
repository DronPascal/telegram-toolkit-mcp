#!/usr/bin/env python3
"""
E2E Tests Runner for Telegram Toolkit MCP

This script runs end-to-end tests with proper configuration and environment setup.
E2E tests validate complete workflows and real-world scenarios.
"""

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


def run_e2e_tests(
    verbose: bool = False, fail_fast: bool = False, subset: str = "all"
) -> tuple[int, str]:
    """Run E2E tests and return exit code and output."""
    print("🌐 Running E2E Tests...")

    # Check environment first
    missing_env = test_config.check_environment("e2e")
    if missing_env:
        error_msg = f"Missing required environment variables: {', '.join(missing_env)}"
        print(f"⚠️  {error_msg}")
        print("💡 Set TELEGRAM_API_ID and TELEGRAM_API_HASH to run E2E tests")
        return 1, error_msg

    # Build pytest command
    cmd = ["pytest", "--tb=short", "-v" if verbose else "-q", "--asyncio-mode=auto", "-m", "e2e"]

    if fail_fast:
        cmd.append("--maxfail=1")

    # Add test pattern based on subset
    if subset == "telegram":
        cmd.append("tests/e2e/test_telegram_toolkit_e2e.py")
    elif subset == "mcp":
        cmd.append("tests/e2e/test_mcp_server_e2e.py")
    else:
        cmd.append("tests/e2e/")

    # Set up environment
    env = test_config.get_environment_vars()

    try:
        result = subprocess.run(
            cmd,
            cwd=test_config.project_root,
            env=env,
            capture_output=True,
            text=True,
            timeout=test_config.get_timeout("e2e"),
            check=False,
        )

        return result.returncode, result.stdout + result.stderr

    except subprocess.TimeoutExpired:
        error_msg = f"E2E tests timed out after {test_config.get_timeout('e2e')} seconds"
        return 1, error_msg
    except Exception as e:
        return 1, f"Error running E2E tests: {e}"


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Run E2E Tests for Telegram Toolkit MCP")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first failure")
    parser.add_argument(
        "--subset",
        choices=["telegram", "mcp", "all"],
        default="all",
        help="Run specific subset of E2E tests",
    )

    args = parser.parse_args()

    # Run tests
    exit_code, output = run_e2e_tests(
        verbose=args.verbose, fail_fast=args.fail_fast, subset=args.subset
    )

    # Print output
    if output:
        print(output)

    # Exit with appropriate code
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
