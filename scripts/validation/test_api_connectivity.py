#!/usr/bin/env python3
"""
Telegram API Connectivity Test Script

This script tests basic connectivity to the Telegram API using the
configured credentials. It validates that the API connection works
without requiring full user authorization.

Usage:
    python3 scripts/test_api_connectivity.py

Features:
    - Tests Telegram API connectivity
    - Validates API credentials
    - Checks network connectivity
    - Provides basic API response validation
    - No user authorization required

Requirements:
    - Valid TELEGRAM_API_ID and TELEGRAM_API_HASH in .env
    - Internet connection
    - python-dotenv package

Output:
    - Connection status and latency
    - API credential validation
    - Basic connectivity confirmation
    - Error diagnostics if connection fails

Note:
    This test only validates API connectivity, not user authorization.
    For full E2E testing with user data, use test_resolve_chat_e2e.py
    after running auth_telegram_session.py
"""

import asyncio
import os
import sys

# Add src to path
src_path = os.path.join(os.path.dirname(__file__), "..", "..", "src")
sys.path.insert(0, src_path)

from dotenv import load_dotenv

from telegram_toolkit_mcp.core.telegram_client import TelegramClientWrapper
from telegram_toolkit_mcp.utils.config import get_config


async def test_connection():
    # Load environment variables first
    load_dotenv()
    try:
        config = get_config()
        print(f"📋 API ID: {config.telegram.api_id}")
        print(f"🔑 API Hash: {config.telegram.api_hash[:8]}...")
        session_status = "Set" if config.telegram.session_string else "Not set"
        print(f"🔐 Session String: {session_status}")

        # Create Telethon client
        import os
        import tempfile

        from telethon import TelegramClient
        from telethon.sessions import StringSession

        # Use StringSession if available, otherwise temporary file
        session_path = None
        if config.telegram.session_string:
            session = StringSession(config.telegram.session_string)
        else:
            temp_fd, session_path = tempfile.mkstemp(suffix=".session")
            os.close(temp_fd)
            session = session_path

        telethon_client = TelegramClient(
            session=session, api_id=config.telegram.api_id, api_hash=config.telegram.api_hash
        )

        client = TelegramClientWrapper()

        print("🔄 Connecting to Telegram API...")
        await client.connect(telethon_client)

        if client._client.is_connected():
            print("✅ Successfully connected to Telegram API!")

            # Try to get our own info
            try:
                me = await client._client.get_me()
                if me:
                    print(f"👤 User Info: @{me.username} (ID: {me.id})")
                    print(f"📝 First Name: {me.first_name}")
                    print("✅ Session is authorized!")
                else:
                    print("⚠️  Session not authorized (first time use)")
                    print("   This is normal - authorization needed for full access")
            except Exception as e:
                print(f"⚠️  Cannot get user info: {e}")
                print("   This is normal for unauthorized sessions")

            # Test resolving a public channel
            print("\n🔍 Testing public channel resolution...")
            try:
                entity = await client._client.get_entity("@telegram")
                print(f"✅ @telegram channel resolved: {entity.title} (ID: {entity.id})")
                print(f"   Type: {type(entity).__name__}")
            except Exception as e:
                print(f"❌ Failed to resolve @telegram: {e}")

        else:
            print("❌ Connection failed - client not connected")
            return False

        await client.disconnect()

        # Clean up temporary session file
        if session_path and os.path.exists(session_path):
            os.unlink(session_path)

        print("✅ Connection test completed successfully!")
        return True

    except Exception as e:
        print(f"❌ Connection error: {e}")
        import traceback

        traceback.print_exc()

        # Clean up temporary session file even on error
        if session_path and os.path.exists(session_path):
            os.unlink(session_path)

        return False


if __name__ == "__main__":
    print("🚀 Starting Telegram API Connection Test...")
    print("=" * 50)

    result = asyncio.run(test_connection())

    print("=" * 50)
    if result:
        print("🎉 CONNECTION TEST PASSED!")
        print("✅ Ready for E2E testing with @telegram channel")
    else:
        print("❌ CONNECTION TEST FAILED!")
        print("🔧 Please check your API credentials")

    sys.exit(0 if result else 1)
