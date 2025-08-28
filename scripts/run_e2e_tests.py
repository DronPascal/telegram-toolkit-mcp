#!/usr/bin/env python3
"""
E2E Test Runner for Telegram Toolkit MCP

This script provides a convenient way to run E2E tests with proper configuration
and environment setup.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


def main():
    """Main entry point for E2E test runner."""
    parser = argparse.ArgumentParser(
        description="Run E2E tests for Telegram Toolkit MCP"
    )

    parser.add_argument(
        "--pattern",
        default="test_*e2e*",
        help="Test pattern to run (default: test_*e2e*)"
    )

    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Verbose output"
    )

    parser.add_argument(
        "--no-skip",
        action="store_true",
        help="Don't skip tests even if credentials are missing"
    )

    parser.add_argument(
        "--subset",
        choices=["telegram", "mcp", "all"],
        default="all",
        help="Run specific subset of E2E tests"
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        help="Test timeout in seconds (default: 300)"
    )

    args = parser.parse_args()

    # Check environment
    check_environment(args.no_skip)

    # Build pytest command
    cmd = ["python", "-m", "pytest"]

    if args.verbose:
        cmd.append("-v")
    else:
        cmd.append("-q")

    # Add E2E specific options
    cmd.extend([
        "--tb=short",
        "--asyncio-mode=auto",
        "--disable-warnings",
        f"--timeout={args.timeout}",
        "-m", "e2e"
    ])

    # Add test pattern
    if args.subset == "telegram":
        cmd.append("tests/e2e/test_telegram_toolkit_e2e.py")
    elif args.subset == "mcp":
        cmd.append("tests/e2e/test_mcp_server_e2e.py")
    else:
        cmd.append(f"tests/e2e/{args.pattern}.py")

    # Add coverage if available
    try:
        import pytest_cov
        cmd.extend([
            "--cov=src/telegram_toolkit_mcp",
            "--cov-report=term-missing",
            "--cov-report=html:htmlcov_e2e"
        ])
    except ImportError:
        print("⚠️  pytest-cov not available, skipping coverage")

    print("🚀 Running E2E tests...")
    print(f"📋 Command: {' '.join(cmd)}")
    print()

    # Run tests
    try:
        result = subprocess.run(cmd, cwd=Path(__file__).parent.parent)
        sys.exit(result.returncode)
    except KeyboardInterrupt:
        print("\n⏹️  E2E tests interrupted by user")
        sys.exit(130)
    except Exception as e:
        print(f"❌ Error running E2E tests: {e}")
        sys.exit(1)


def check_environment(no_skip: bool = False):
    """Check if environment is ready for E2E tests."""
    print("🔍 Checking E2E test environment...")

    required_vars = [
        "TELEGRAM_API_ID",
        "TELEGRAM_API_HASH"
    ]

    missing = []
    for var in required_vars:
        if not os.getenv(var):
            missing.append(var)

    if missing:
        if no_skip:
            print(f"⚠️  Missing required environment variables: {', '.join(missing)}")
            print("   E2E tests will fail without these credentials")
        else:
            print("⏭️  Skipping E2E tests due to missing credentials:"            for var in missing:
                print(f"   - {var}")
            print()
            print("💡 To run E2E tests:")
            print("   1. Set your Telegram API credentials:")
            print("      export TELEGRAM_API_ID=your_api_id")
            print("      export TELEGRAM_API_HASH=your_api_hash")
            print("   2. Or use --no-skip to force run tests")
            sys.exit(0)

    # Check Python version
    if sys.version_info < (3, 11):
        print(f"⚠️  Python {sys.version_info.major}.{sys.version_info.minor} detected")
        print("   E2E tests require Python 3.11+")
        if not no_skip:
            sys.exit(0)

    print("✅ Environment check passed")
    print()


if __name__ == "__main__":
    main()
