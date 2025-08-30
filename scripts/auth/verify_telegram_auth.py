#!/usr/bin/env python3
"""
Telegram Authentication Verification Script

This script verifies the current Telegram session authentication status.
It checks if the user is properly authorized and can access Telegram API.

Usage:
    python3 scripts/auth/verify_telegram_auth.py

Features:
    - Verifies Telegram API credentials
    - Checks session authorization status
    - Validates user information retrieval
    - Confirms API connectivity

Requirements:
    - Valid TELEGRAM_API_ID and TELEGRAM_API_HASH in .env
    - Authorized Telegram session (use auth_telegram_session.py if needed)

Output:
    - Authorization status
    - User information (if authorized)
    - API connectivity confirmation
"""

import asyncio
import sys
from pathlib import Path

# Add src to Python path
src_path = Path(__file__).parent.parent.parent / "src"
sys.path.insert(0, str(src_path))

from telethon import TelegramClient
from telethon.sessions import StringSession
from telegram_toolkit_mcp.utils.config import get_config


async def verify_telegram_auth():
    """
    Verify Telegram authentication and session status.

    This function checks:
    1. API credentials configuration
    2. Session authorization status
    3. User information retrieval
    4. API connectivity

    Returns:
        bool: True if authentication is valid, False otherwise
    """
    print("🔐 Telegram Authentication Verification")
    print("=" * 50)

    try:
        # Load configuration
        config = get_config()
        print(f"📋 API ID: {config.telegram.api_id}")

        session_str = (
            config.telegram.session_string[:20] + "..."
            if config.telegram.session_string
            else "None"
        )
        print(f"🔑 Session: {session_str}")

        # Validate API credentials
        if not config.telegram.api_id or not config.telegram.api_hash:
            print("❌ Missing API credentials")
            print("   Please set TELEGRAM_API_ID and TELEGRAM_API_HASH in .env")
            return False

        # Create and configure client
        session = (
            StringSession(config.telegram.session_string)
            if config.telegram.session_string
            else StringSession()
        )
        client = TelegramClient(session, config.telegram.api_id, config.telegram.api_hash)

        print("\n🔄 Connecting to Telegram...")
        await client.start()

        # Check authorization status
        if await client.is_user_authorized():
            print("✅ User is authorized!")

            # Get user information
            try:
                me = await client.get_me()
                if me:
                    print("👤 User Information:")
                    print(f'   Name: {me.first_name} {me.last_name or ""}'.strip())
                    print(f'   Username: @{me.username or "not set"}')
                    print(f"   User ID: {me.id}")
                    print(f'   Phone: {me.phone or "not available"}')

                    # Test basic API functionality
                    print("\n🔍 Testing API functionality...")
                    dialogs = await client.get_dialogs(limit=1)
                    print(f"✅ API access confirmed (found {len(dialogs)} dialogs)")

                    return True
                else:
                    print("⚠️  User info unavailable (get_me() returned None)")
                    return False

            except Exception as e:
                print(f"❌ Error retrieving user info: {e}")
                return False
        else:
            print("❌ User is NOT authorized")
            print("   Please run: python3 scripts/auth_telegram_session.py")
            return False

    except Exception as e:
        print(f"❌ Authentication verification failed: {e}")
        import traceback

        traceback.print_exc()
        return False

    finally:
        # Ensure client is disconnected
        try:
            await client.disconnect()
        except:
            pass


if __name__ == "__main__":
    print("🚀 Starting Telegram Authentication Verification...")
    print("This script checks if your Telegram session is properly authorized.\n")

    success = asyncio.run(verify_telegram_auth())

    print("\n" + "=" * 50)
    if success:
        print("✅ AUTHENTICATION VERIFIED!")
        print("🎯 You can proceed with E2E testing")
    else:
        print("❌ AUTHENTICATION FAILED!")
        print("🔧 Please check your credentials and session")

    sys.exit(0 if success else 1)
