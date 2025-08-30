# Telegram Toolkit MCP - Scripts Directory

This directory contains utility scripts for testing, validation, deployment, and maintenance of the Telegram Toolkit MCP server.

## 🏗️ New Unified Testing Architecture (2024)

**✨ MAJOR UPDATE**: We've introduced a unified testing system with centralized configuration and master test runner.

### Key Improvements:
- 🎯 **Unified Interface**: Single entry point for all test types
- 📊 **Centralized Reporting**: Consistent test results and metrics
- ⚙️ **Configuration Management**: Shared settings across all test scripts
- 🔄 **Backward Compatibility**: Legacy scripts still work with deprecation warnings

## 📁 Directory Structure

### `validation/` - Environment & Configuration Scripts
- `validate_environment.py` - Validates environment variables and .env configuration
- `test_api_connectivity.py` - Tests basic Telegram API connectivity and credentials
- `test_resolve_chat_e2e.py` - E2E testing of chat resolution functionality

### `auth/` - Authentication & Authorization Scripts
- `auth_telegram_session.py` - Interactive Telegram session authorization
- `verify_telegram_auth.py` - Verifies current Telegram session status

### `testing/` - Test Execution Scripts
- `run_all_tests.py` 🎯 **MASTER RUNNER** - Runs all test types in sequence
- `run_unit_tests.py` - Unit tests (fast, isolated component tests)
- `run_integration_tests.py` - Integration tests (component interactions)
- `run_e2e_tests.py` - End-to-end tests (complete workflow validation)
- `run_performance_tests.py` - Performance tests (benchmarking and load testing)
- `test_config.py` ⚙️ **CONFIG MODULE** - Centralized test configuration

### `deploy/` - Deployment Scripts
- `deploy.sh` - Automated deployment script for VPS/Docker environments
- `DEPLOYMENT.md` - Complete deployment guide and documentation

## 🚀 Quick Start

```bash
# 1. Validate environment
python3 scripts/validation/validate_environment.py

# 2. Authorize Telegram session
python3 scripts/auth/auth_telegram_session.py

# 3. Run ALL tests (recommended)
python3 scripts/testing/run_all_tests.py

# 4. Run specific test types
python3 scripts/testing/run_unit_tests.py         # Only unit tests
python3 scripts/testing/run_integration_tests.py # Only integration tests
python3 scripts/testing/run_e2e_tests.py          # Only E2E tests
python3 scripts/testing/run_performance_tests.py --test-type benchmark

# 5. Deploy to production
./scripts/deploy/deploy.sh your-domain.com
```

## 📋 Master Test Runner

The `run_all_tests.py` script provides a simple, sequential execution of all test types:

### ✨ Features:
- **Sequential Execution**: Runs Unit → Integration → E2E → Performance tests
- **Unified Summary**: Single report with overall statistics
- **Fail-Fast Support**: Stop on first failure option
- **Minimal Logic**: Simple orchestration, detailed work in specialized scripts
- **Consistent Interface**: Same CLI options across all test scripts

### 🎯 Usage Examples:

```bash
# Run ALL tests (recommended for CI/CD)
python3 scripts/testing/run_all_tests.py

# Verbose output with all details
python3 scripts/testing/run_all_tests.py --verbose

# Stop on first failure (fast feedback)
python3 scripts/testing/run_all_tests.py --fail-fast
```

### 📊 Sample Output:
```
🚀 RUNNING ALL TESTS
==================================================

📋 Running Unit Tests...
✅ Unit Tests: PASSED

📋 Running Integration Tests...
✅ Integration Tests: PASSED

📋 Running E2E Tests...
✅ E2E Tests: PASSED

📋 Running Performance Tests...
✅ Performance Tests: PASSED

==================================================
📊 FINAL SUMMARY
==================================================
📋 Total test suites run: 4
✅ Passed: 4
❌ Failed: 0
📈 Success rate: 100.0%
🎯 Overall: ALL PASSED

🔚 Exit code: 0
```

## 🔧 Configuration System

The new `test_config.py` provides centralized configuration:

- **Timeouts**: Configurable timeouts for different test types
- **Dependencies**: Centralized dependency checking
- **Environment**: Required environment variables by test type
- **Paths**: Standardized paths for test directories
- **Pytest Settings**: Unified pytest configuration

## 🎯 Categories Overview

| Category | Purpose | Key Scripts | Status |
|----------|---------|-------------|---------|
| **Validation** | Configuration and connectivity validation | Environment setup, API testing | ✅ Active |
| **Auth** | Telegram session management | Authorization, verification | ✅ Active |
| **Testing** | Test execution and quality assurance | 5 specialized test runners | ✅ **MODULAR ARCHITECTURE** |
| **Deploy** | Production deployment automation | Docker, Nginx, SSL setup | ✅ Active |

## 🔧 Common Workflows

### Development Setup
1. Validate environment configuration
2. Authorize Telegram session
3. Run all tests: `python3 scripts/testing/run_all_tests.py`
4. Check results and fix any issues
5. Deploy to staging/production

### CI/CD Integration
```bash
# Full test suite (recommended)
python3 scripts/testing/run_all_tests.py --verbose

# Fast feedback (stop on first failure)
python3 scripts/testing/run_all_tests.py --fail-fast

# Individual test suites
python3 scripts/testing/run_unit_tests.py
python3 scripts/testing/run_integration_tests.py
python3 scripts/testing/run_e2e_tests.py
```

## 📞 Support & Documentation

### Test Scripts:
- **Master Runner**: `python3 scripts/testing/run_all_tests.py --help`
- **Unit Tests**: `python3 scripts/testing/run_unit_tests.py --help`
- **Integration Tests**: `python3 scripts/testing/run_integration_tests.py --help`
- **E2E Tests**: `python3 scripts/testing/run_e2e_tests.py --help`
- **Performance Tests**: `python3 scripts/testing/run_performance_tests.py --help`

### Configuration:
- **Test Config**: Check `test_config.py` for centralized settings
- **Environment Setup**: See `scripts/validation/validate_environment.py`
- **Dependencies**: All test scripts use shared dependency checking

### General:
- **Individual Scripts**: Each script has comprehensive docstrings
- **Deployment**: Refer to `DEPLOYMENT.md` for production setup
- **Troubleshooting**: Run any script with `--help` flag for options

---

**🎯 Perfect separation of concerns: 5 specialized scripts with minimal master runner!**
