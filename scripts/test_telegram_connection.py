#!/usr/bin/env python3
"""
Test script to verify Telegram API connection
"""
import os
import asyncio
import sys
from dotenv import load_dotenv
from telegram_toolkit_mcp.core.telegram_client import TelegramClientWrapper
from telegram_toolkit_mcp.utils.config import get_config

# Load environment variables
load_dotenv()

async def test_connection():
    try:
        config = get_config()
        print(f'📋 API ID: {config.telegram.api_id}')
        print(f'🔑 API Hash: {config.telegram.api_hash[:8]}...')
        session_status = "Set" if config.telegram.session_string else "Not set"
        print(f'🔐 Session String: {session_status}')

        client = TelegramClientWrapper(
            api_id=config.telegram.api_id,
            api_hash=config.telegram.api_hash,
            session_string=config.telegram.session_string
        )

        print('🔄 Connecting to Telegram API...')
        await client.connect()

        if client._client.is_connected():
            print('✅ Successfully connected to Telegram API!')

            # Try to get our own info
            me = await client._client.get_me()
            print(f'👤 User Info: @{me.username} (ID: {me.id})')
            print(f'📝 First Name: {me.first_name}')
            print(f'📝 Last Name: {me.last_name if me.last_name else "N/A"}')

            # Test resolving a public channel
            print('\n🔍 Testing public channel resolution...')
            try:
                entity = await client._client.get_entity('@durov')
                print(f'✅ @durov channel resolved: {entity.title} (ID: {entity.id})')
                print(f'   Type: {type(entity).__name__}')
            except Exception as e:
                print(f'❌ Failed to resolve @durov: {e}')

        else:
            print('❌ Connection failed - client not connected')
            return False

        await client.disconnect()
        print('✅ Connection test completed successfully!')
        return True

    except Exception as e:
        print(f'❌ Connection error: {e}')
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Starting Telegram API Connection Test...")
    print("=" * 50)

    success = asyncio.run(test_connection())

    print("=" * 50)
    if success:
        print("🎉 CONNECTION TEST PASSED!")
        print("✅ Ready for E2E testing with @durov channel")
    else:
        print("❌ CONNECTION TEST FAILED!")
        print("🔧 Please check your API credentials")

    sys.exit(0 if success else 1)
