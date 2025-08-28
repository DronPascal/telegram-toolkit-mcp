#!/usr/bin/env python3
"""
Environment Variables Validation Script

This script validates that all required environment variables are properly
configured for the Telegram Toolkit MCP server. It checks both system
environment and .env file configuration.

Usage:
    python3 scripts/validate_environment.py

Features:
    - Validates required Telegram API credentials
    - Checks .env file loading
    - Verifies configuration completeness
    - Provides clear error messages and fixes

Requirements:
    - .env file in project root
    - python-dotenv package
    - Required environment variables set

Output:
    - Environment variable status
    - .env file content validation
    - Configuration completeness check
    - Actionable error messages
"""
import os
from dotenv import load_dotenv


def validate_environment():
    """
    Validate environment configuration for Telegram Toolkit MCP.

    This function checks:
    1. Environment variables before .env loading
    2. .env file loading capability
    3. Required Telegram API credentials
    4. Configuration completeness

    Returns:
        bool: True if environment is valid, False otherwise
    """
    print("🔍 Environment Variables Validation")
    print("=" * 50)

    success = True

    # Check environment before .env loading
    print("📋 Checking system environment (before .env):")
    api_id_before = os.getenv('TELEGRAM_API_ID', 'NOT SET')
    api_hash_before = os.getenv('TELEGRAM_API_HASH', 'NOT SET')
    session_before = os.getenv('TELEGRAM_STRING_SESSION', 'NOT SET')

    print(f'   TELEGRAM_API_ID: {api_id_before}')
    print(f'   TELEGRAM_API_HASH: {"*" * 8 if api_hash_before != "NOT SET" else "NOT SET"}')
    print(f'   TELEGRAM_STRING_SESSION: {"SET" if session_before != "NOT SET" else "NOT SET"}')

    # Try to load .env file
    print('\n🔄 Loading .env file...')
    try:
        load_dotenv()
        print('✅ .env file loaded successfully')
    except Exception as e:
        print(f'❌ Error loading .env file: {e}')
        return False

    # Check environment after .env loading
    print('\n📋 Checking environment (after .env loading):')
    api_id_after = os.getenv('TELEGRAM_API_ID', 'NOT SET')
    api_hash_after = os.getenv('TELEGRAM_API_HASH', 'NOT SET')
    session_after = os.getenv('TELEGRAM_STRING_SESSION', 'NOT SET')

    print(f'   TELEGRAM_API_ID: {api_id_after}')
    print(f'   TELEGRAM_API_HASH: {"*" * 8 if api_hash_after != "NOT SET" else "NOT SET"}')
    print(f'   TELEGRAM_STRING_SESSION: {"SET" if session_after != "NOT SET" else "NOT SET"}')

    # Validate required credentials
    print('\n🔍 Validating required credentials...')

    if api_id_after == 'NOT SET':
        print('❌ TELEGRAM_API_ID is not set')
        print('   Get it from: https://my.telegram.org/auth')
        success = False

    if api_hash_after == 'NOT SET':
        print('❌ TELEGRAM_API_HASH is not set')
        print('   Get it from: https://my.telegram.org/auth')
        success = False

    # Check .env file content
    print('\n📄 Checking .env file content...')
    try:
        with open('.env', 'r') as f:
            lines = f.readlines()

        telegram_vars = []
        for line in lines:
            line = line.strip()
            if line.startswith('TELEGRAM_') and not line.startswith('#'):
                telegram_vars.append(line)

        if telegram_vars:
            print('✅ Found Telegram configuration in .env:')
            for var in telegram_vars:
                if 'HASH' in var:
                    # Hide hash for security
                    key, value = var.split('=', 1)
                    print(f'   {key}=********')
                else:
                    print(f'   {var}')
        else:
            print('⚠️  No Telegram variables found in .env file')
            success = False

    except FileNotFoundError:
        print('❌ .env file not found')
        print('   Please create .env file in project root')
        success = False
    except Exception as e:
        print(f'❌ Error reading .env file: {e}')
        success = False

    # Check optional configuration
    print('\n📋 Checking optional configuration...')
    optional_vars = [
        ('MCP_SERVER_HOST', os.getenv('MCP_SERVER_HOST', 'localhost')),
        ('MCP_SERVER_PORT', os.getenv('MCP_SERVER_PORT', '8000')),
        ('DEBUG', os.getenv('DEBUG', 'false')),
    ]

    for name, value in optional_vars:
        status = '✅' if value != 'NOT SET' else '❌'
        print(f'   {status} {name}: {value}')

    return success


if __name__ == "__main__":
    print("🚀 Starting Environment Validation...")
    print("This script checks if all required environment variables are configured.\n")

    success = validate_environment()

    print("\n" + "=" * 50)
    if success:
        print("✅ ENVIRONMENT VALIDATION PASSED!")
        print("🎯 Configuration is ready for Telegram Toolkit MCP")
        print("\nNext steps:")
        print("1. Run: python3 scripts/verify_telegram_auth.py")
        print("2. If not authorized, run: python3 scripts/auth_telegram_session.py")
        print("3. Then proceed with E2E testing")
    else:
        print("❌ ENVIRONMENT VALIDATION FAILED!")
        print("🔧 Please fix the configuration issues above")

    exit(0 if success else 1)
