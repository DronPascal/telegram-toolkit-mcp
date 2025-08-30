#!/usr/bin/env python3
"""
Master Test Runner - Run All Tests

This script runs all test types in sequence and provides a unified summary.
It executes: Unit → Integration → E2E → Performance → Transport tests.

Usage:
    python3 scripts/testing/run_all_tests.py [--verbose] [--fail-fast]
"""

import argparse
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TestResult:
    """Result of a test suite execution."""

    name: str
    exit_code: int
    output: str = ""


def run_test_script(script_name: str, args: list[str] = None) -> TestResult:
    """Run a test script and return result."""
    if args is None:
        args = []

    project_root = Path(__file__).parent.parent.parent
    script_path = project_root / "scripts" / "testing" / script_name

    # Special handling for tests that need virtual environment
    if script_name in ["run_performance_tests.py", "test_transports.py"]:
        # Use virtual environment for performance and transport tests
        venv_python = project_root / ".venv" / "bin" / "python"
        env_cmd = f"cd {project_root} && PYTHONPATH={project_root}/src {venv_python} {script_path}"
        if args:
            env_cmd += " " + " ".join(args)
        cmd = ["bash", "-c", env_cmd]
    else:
        # Regular execution for other tests
        python_executable = "python3"
        env_cmd = (
            f"cd {project_root} && PYTHONPATH={project_root}/src {python_executable} {script_path}"
        )
        if args:
            env_cmd += " " + " ".join(args)
        cmd = ["bash", "-c", env_cmd]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, cwd=project_root, check=False)
        return TestResult(
            name=script_name, exit_code=result.returncode, output=result.stdout + result.stderr
        )
    except (subprocess.SubprocessError, OSError) as e:
        return TestResult(name=script_name, exit_code=1, output=f"Failed to run {script_name}: {e}")


def print_test_result(result: TestResult):
    """Print test result."""
    status_icon = "✅" if result.exit_code == 0 else "❌"
    status_text = "PASSED" if result.exit_code == 0 else "FAILED"

    print(f"\n{status_icon} {result.name}: {status_text}")

    # Print output if failed or verbose
    if result.exit_code != 0 or "--verbose" in sys.argv:
        if result.output.strip():
            print(f"   Output: {result.output.strip()}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Run All Tests for Telegram Toolkit MCP")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first failure")

    args = parser.parse_args()

    print("🚀 RUNNING ALL TESTS")
    print("=" * 50)

    # Define test scripts to run
    test_scripts = [
        ("run_unit_tests.py", "Unit Tests"),
        ("run_integration_tests.py", "Integration Tests"),
        ("run_e2e_tests.py", "E2E Tests"),
        ("run_performance_tests.py", "Performance Tests"),
        ("test_transports.py", "Transport Tests"),
    ]

    results = []
    total_passed = 0
    total_failed = 0

    # Run each test script
    for script_name, display_name in test_scripts:
        print(f"\n📋 Running {display_name}...")

        # Prepare arguments
        script_args = []
        if script_name == "test_transports.py":
            # Transport tests need --all to test all transport modes
            script_args.append("--all")
        if args.verbose:
            script_args.append("--verbose")
        if args.fail_fast:
            script_args.append("--fail-fast")

        # Run test
        result = run_test_script(script_name, script_args)
        result.name = display_name  # Update display name
        results.append(result)

        # Print result
        print_test_result(result)

        # Update counters
        if result.exit_code == 0:
            total_passed += 1
        else:
            total_failed += 1

        # Fail fast if requested
        if args.fail_fast and result.exit_code != 0:
            print(f"\n⏹️  Stopping due to failure in {display_name}")
            break

    # Print summary
    print("\n" + "=" * 50)
    print("📊 FINAL SUMMARY")
    print("=" * 50)

    print(f"📋 Total test suites run: {len(results)}")
    print(f"✅ Passed: {total_passed}")
    print(f"❌ Failed: {total_failed}")

    # Calculate success rate
    if len(results) > 0:
        success_rate = (total_passed / len(results)) * 100
        print(f"📈 Success rate: {success_rate:.1f}%")

    # Overall status
    if total_failed == 0:
        overall_status = "ALL PASSED"
        exit_code = 0
    elif total_passed > 0:
        overall_status = "PARTIAL SUCCESS"
        exit_code = 0
    else:
        overall_status = "ALL FAILED"
        exit_code = 1

    print(f"🎯 Overall: {overall_status}")

    # Recommendations if any failed
    if total_failed > 0:
        print("\n💡 Recommendations:")
        print("   • Check individual test outputs above for details")
        print("   • Run failed test suites individually for more info")
        print("   • Ensure all dependencies are installed")

    print(f"\n🔚 Exit code: {exit_code}")
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
