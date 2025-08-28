#!/usr/bin/env python3
"""
Simple Telegram API connection test
"""
import sys
import os
import asyncio

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from telegram_toolkit_mcp.core.telegram_client import TelegramClientWrapper
from telegram_toolkit_mcp.utils.config import get_config
from dotenv import load_dotenv

async def test_connection():
    # Load environment variables first
    load_dotenv()
    try:
        config = get_config()
        print(f'📋 API ID: {config.telegram.api_id}')
        print(f'🔑 API Hash: {config.telegram.api_hash[:8]}...')
        session_status = 'Set' if config.telegram.session_string else 'Not set'
        print(f'🔐 Session String: {session_status}')

        # Create Telethon client
        from telethon import TelegramClient
        import tempfile
        import os

        # Use a temporary session file if no session string
        session_path = None
        if not config.telegram.session_string:
            temp_fd, session_path = tempfile.mkstemp(suffix='.session')
            os.close(temp_fd)

        telethon_client = TelegramClient(
            session=session_path or config.telegram.session_string,
            api_id=config.telegram.api_id,
            api_hash=config.telegram.api_hash
        )

        client = TelegramClientWrapper()

        print('🔄 Connecting to Telegram API...')
        await client.connect(telethon_client)

        if client._client.is_connected():
            print('✅ Successfully connected to Telegram API!')

            # Try to get our own info
            try:
                me = await client._client.get_me()
                if me:
                    print(f'👤 User Info: @{me.username} (ID: {me.id})')
                    print(f'📝 First Name: {me.first_name}')
                    print('✅ Session is authorized!')
                else:
                    print('⚠️  Session not authorized (first time use)')
                    print('   This is normal - authorization needed for full access')
            except Exception as e:
                print(f'⚠️  Cannot get user info: {e}')
                print('   This is normal for unauthorized sessions')

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

        # Clean up temporary session file
        if session_path and os.path.exists(session_path):
            os.unlink(session_path)

        print('✅ Connection test completed successfully!')
        return True

    except Exception as e:
        print(f'❌ Connection error: {e}')
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
        print("✅ Ready for E2E testing with @durov channel")
    else:
        print("❌ CONNECTION TEST FAILED!")
        print("🔧 Please check your API credentials")

    sys.exit(0 if result else 1)
