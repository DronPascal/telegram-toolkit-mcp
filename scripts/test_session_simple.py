#!/usr/bin/env python3
import asyncio
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from telegram_toolkit_mcp.utils.config import get_config
from telethon import TelegramClient
from telethon.sessions import StringSession

async def test_session():
    config = get_config()
    print(f'API ID: {config.telegram.api_id}')

    session_str = config.telegram.session_string[:20] + '...' if config.telegram.session_string else 'None'
    print(f'Session: {session_str}')

    try:
        session = StringSession(config.telegram.session_string) if config.telegram.session_string else StringSession()
        client = TelegramClient(session, config.telegram.api_id, config.telegram.api_hash)

        print('🔄 Starting client...')
        await client.start()

        if await client.is_user_authorized():
            print('✅ User authorized')
            try:
                me = await client.get_me()
                if me:
                    print(f'✅ User: {me.first_name} {me.last_name or ""} (@{me.username or "no_username"})')
                    print(f'✅ User ID: {me.id}')
                else:
                    print('⚠️  get_me() returned None')
            except Exception as e:
                print(f'❌ Error getting user info: {e}')
        else:
            print('❌ User not authorized')

        await client.disconnect()
        print('✅ Test completed')

    except Exception as e:
        print(f'❌ Session test error: {e}')
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(test_session())
