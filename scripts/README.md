# Telegram Toolkit MCP - Scripts Directory

This directory contains utility scripts for testing, validation, and maintenance of the Telegram Toolkit MCP server.

## 📋 Available Scripts

### 🔧 Environment & Configuration

#### `validate_environment.py`
**Purpose**: Validate environment variables and configuration
- ✅ Checks required Telegram API credentials
- ✅ Validates .env file loading
- ✅ Verifies configuration completeness
- ✅ Provides actionable error messages

**Usage**:
```bash
python3 scripts/validate_environment.py
```

**When to use**:
- After initial setup
- When configuration issues occur
- Before running other scripts

### 🔐 Authentication & Authorization

#### `auth_telegram_session.py`
**Purpose**: Interactive Telegram session authorization
- 📱 Guides through phone number verification
- 🔑 Generates and stores session string
- 💾 Automatically updates .env file
- 🧪 Tests channel access (@telegram)

**Usage**:
```bash
python3 scripts/auth_telegram_session.py
```

**Requirements**:
- Valid TELEGRAM_API_ID and TELEGRAM_API_HASH
- Active phone number registered with Telegram
- Access to Telegram app for verification codes

#### `verify_telegram_auth.py`
**Purpose**: Verify current Telegram session status
- ✅ Checks user authorization status
- 👤 Retrieves and displays user information
- 🔍 Tests basic API functionality
- 📊 Provides connectivity confirmation

**Usage**:
```bash
python3 scripts/verify_telegram_auth.py
```

**When to use**:
- After session authorization
- When connectivity issues occur
- Before running E2E tests

### 🧪 Testing Scripts

#### `test_api_connectivity.py`
**Purpose**: Test basic Telegram API connectivity
- 🌐 Validates API credentials
- 📡 Tests network connectivity
- ⚡ Measures connection latency
- 🔍 Basic API response validation

**Usage**:
```bash
python3 scripts/test_api_connectivity.py
```

**Note**: Doesn't require user authorization

#### `test_resolve_chat_e2e.py`
**Purpose**: Comprehensive E2E testing of chat resolution
- 🧪 Real Telegram API testing
- 📊 Performance measurement
- ✅ Channel resolution validation (@telegram)
- 🔒 Security auditing integration

**Usage**:
```bash
python3 scripts/test_resolve_chat_e2e.py
```

**Requirements**:
- Authorized Telegram session
- Internet connection
- Valid API credentials

### 🚀 Performance & Load Testing

#### `run_performance_tests.py`
**Purpose**: Execute comprehensive performance testing
- 📈 Benchmark individual components
- 🔄 Load testing with configurable parameters
- 📊 Performance baseline establishment
- 📋 Detailed reporting and analysis

**Usage**:
```bash
python3 scripts/run_performance_tests.py
```

#### `run_e2e_tests.py`
**Purpose**: Run complete E2E test suite
- 🧪 Execute all E2E test cases
- 📊 Generate comprehensive reports
- 🔍 Validate end-to-end functionality
- 📈 Performance and reliability metrics

**Usage**:
```bash
python3 scripts/run_e2e_tests.py
```

## 🎯 Quick Start Guide

### 1. Initial Setup
```bash
# 1. Validate environment configuration
python3 scripts/validate_environment.py

# 2. Authorize Telegram session (if not already done)
python3 scripts/auth_telegram_session.py

# 3. Verify authorization
python3 scripts/verify_telegram_auth.py
```

### 2. Basic Testing
```bash
# Test API connectivity (no auth required)
python3 scripts/test_api_connectivity.py

# Run full E2E chat resolution test
python3 scripts/test_resolve_chat_e2e.py
```

### 3. Performance Validation
```bash
# Run performance benchmarks
python3 scripts/run_performance_tests.py

# Run complete E2E test suite
python3 scripts/run_e2e_tests.py
```

## 📁 Script Categories

| Category | Scripts | Purpose |
|----------|---------|---------|
| **Setup** | `validate_environment.py` | Configuration validation |
| **Auth** | `auth_telegram_session.py`<br>`verify_telegram_auth.py` | Session management |
| **Testing** | `test_api_connectivity.py`<br>`test_resolve_chat_e2e.py` | Functionality validation |
| **Performance** | `run_performance_tests.py`<br>`run_e2e_tests.py` | Performance analysis |

## 🔧 Troubleshooting

### Common Issues

#### ❌ "Missing API credentials"
**Solution**: Run `python3 scripts/validate_environment.py` to check configuration

#### ❌ "User not authorized"
**Solution**: Run `python3 scripts/auth_telegram_session.py` to authorize session

#### ❌ "Connection timeout"
**Solution**:
- Check internet connection
- Verify API credentials
- Try again later (Telegram API rate limits)

#### ❌ "Session expired"
**Solution**: Re-run `python3 scripts/auth_telegram_session.py`

## 📞 Support

If you encounter issues with any script:

1. Check the script's documentation header
2. Run `python3 scripts/validate_environment.py` first
3. Verify authorization with `python3 scripts/verify_telegram_auth.py`
4. Check the error messages for specific guidance

## 🚀 Next Steps

After successful script execution:

1. ✅ **E2E Testing**: Scripts validated real Telegram API functionality
2. 🎯 **Performance Testing**: Ready for comprehensive benchmarking
3. 🏗️ **Production Deployment**: Infrastructure tested and validated
4. 📊 **Monitoring**: Scripts provide detailed logging and metrics

**The Telegram Toolkit MCP is now fully validated and ready for production use!** 🎉
