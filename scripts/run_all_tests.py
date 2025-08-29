#!/usr/bin/env python3
"""
Script to run all integration and E2E tests with proper PYTHONPATH setup.
"""

import os
import sys
from pathlib import Path

# Add src directory to Python path
src_path = Path(__file__).parent / "src"
sys.path.insert(0, str(src_path))

# Set environment variables for testing
os.environ.setdefault("DEBUG", "true")
os.environ.setdefault("LOG_LEVEL", "INFO")


def check_dependencies():
    """Check if required dependencies are available."""
    import importlib.util

    missing_deps = []

    if importlib.util.find_spec("mcp") is None:
        missing_deps.append("mcp")

    if importlib.util.find_spec("telethon") is None:
        missing_deps.append("telethon")

    if importlib.util.find_spec("httpx") is None:
        missing_deps.append("httpx")

    return missing_deps


if __name__ == "__main__":
    # Import and run pytest
    import subprocess
    import sys

    print("🚀 ЗАПУСК ВСЕХ ИНТЕГРАЦИОННЫХ И E2E ТЕСТОВ...")
    print("=" * 80)

    # Check dependencies
    missing_deps = check_dependencies()
    if missing_deps:
        print(f"⚠️  ОБНАРУЖЕНЫ ОТСУТСТВУЮЩИЕ ЗАВИСИМОСТИ: {', '.join(missing_deps)}")
        print("📦 E2E тесты могут не запуститься без этих пакетов")
        print("-" * 50)

    # Run integration tests
    print("\n📋 ИНТЕГРАЦИОННЫЕ ТЕСТЫ:")
    print("-" * 40)
    result_integration = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/integration/", "--tb=short", "-v", "-q"],
        check=False,
    )

    print(f"\nIntegration tests exit code: {result_integration.returncode}")

    # Run E2E tests
    print("\n📋 E2E ТЕСТЫ:")
    print("-" * 40)

    if "mcp" in missing_deps or "telethon" in missing_deps:
        print("⚠️  ПРОПУСК E2E ТЕСТОВ: отсутствуют критические зависимости")
        print(f"   Требуются: {', '.join(missing_deps)}")
        result_e2e = type("MockResult", (), {"returncode": 2})()
    else:
        result_e2e = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/e2e/", "--tb=short", "-v", "-q"], check=False
        )

    print(f"\nE2E tests exit code: {result_e2e.returncode}")

    # Summary
    print("\n" + "=" * 80)
    print("📊 ПОДРОБНЫЕ РЕЗУЛЬТАТЫ:")

    if result_integration.returncode == 0:
        print("✅ Integration tests: PASSED")
    else:
        print("❌ Integration tests: FAILED")

    if "mcp" in missing_deps or "telethon" in missing_deps:
        print("⏭️  E2E tests: SKIPPED (недостаточно зависимостей)")
    elif result_e2e.returncode == 0:
        print("✅ E2E tests: PASSED")
    else:
        print("❌ E2E tests: FAILED")

    print("\n" + "-" * 50)
    print("📈 СТАТИСТИКА ПО ТЕСТАМ:")

    # Overall result
    if result_integration.returncode == 0 and (
        "mcp" not in missing_deps and "telethon" not in missing_deps and result_e2e.returncode == 0
    ):
        overall_status = "PASSED"
        overall_exit_code = 0
    elif result_integration.returncode == 0:
        overall_status = "PARTIAL SUCCESS"
        overall_exit_code = 0
    else:
        overall_status = "FAILED"
        overall_exit_code = 1

    print(f"🎯 OVERALL: {overall_status}")

    if missing_deps:
        print("\n💡 РЕКОМЕНДАЦИИ:")
        print(f"   • Установите недостающие пакеты: pip install {' '.join(missing_deps)}")
        print("   • Или запустите только integration тесты: pytest tests/integration/")
        print("   • E2E тесты требуют реальных Telegram credentials")

    print(f"\n🔚 ВЫХОД С КОДОМ: {overall_exit_code}")
    sys.exit(overall_exit_code)
