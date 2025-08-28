#!/usr/bin/env python3
"""
Telegram Session Authorization Script

This script helps authorize a Telegram session for E2E testing.
Run this once to set up the session, then E2E tests will work.
"""
import sys
import os
import asyncio
from dotenv import load_dotenv

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from telegram_toolkit_mcp.utils.config import get_config

async def authorize_session():
    """Authorize Telegram session for E2E testing."""
    # Load environment variables
    load_dotenv()

    config = get_config()

    if not config.telegram.api_id or not config.telegram.api_hash:
        print("❌ Missing TELEGRAM_API_ID or TELEGRAM_API_HASH in .env file")
        return False

    print("🔐 Starting Telegram Session Authorization...")
    print(f"📋 API ID: {config.telegram.api_id}")
    print(f"🔑 API Hash: {config.telegram.api_hash[:8]}...")

    # Create Telethon client
    from telethon import TelegramClient
    from telethon.sessions import StringSession

    # Use StringSession for in-memory session management
    if config.telegram.session_string and config.telegram.session_string.strip():
        try:
            session = StringSession(config.telegram.session_string)
        except ValueError:
            print("⚠️  Existing session string is invalid, creating new session...")
            session = StringSession()
    else:
        session = StringSession()

    client = TelegramClient(
        session=session,
        api_id=config.telegram.api_id,
        api_hash=config.telegram.api_hash
    )

    try:
        print("\n🔄 Connecting to Telegram...")
        await client.start()

        if await client.is_user_authorized():
            print("✅ Session already authorized!")

            # Get user info
            me = await client.get_me()
            print(f"👤 Authorized as: @{me.username} (ID: {me.id})")

            # Save session string to .env if needed
            print("\n💾 Saving session string to .env file...")
            session_string = client.session.save()

            # Update .env file
            env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
            with open(env_path, 'r') as f:
                lines = f.readlines()

            # Replace or add TELEGRAM_STRING_SESSION
            session_found = False
            for i, line in enumerate(lines):
                if line.startswith('TELEGRAM_STRING_SESSION='):
                    lines[i] = f'TELEGRAM_STRING_SESSION={session_string}\n'
                    session_found = True
                    break

            if not session_found:
                lines.append(f'TELEGRAM_STRING_SESSION={session_string}\n')

            with open(env_path, 'w') as f:
                f.writelines(lines)

            print("✅ Session string saved to .env file")
            if session_string:
                print(f"🔐 Session: {session_string[:20]}...")
            else:
                print("🔐 Session: (empty string)")

        else:
            print("❌ Session not authorized. Please complete authorization:")

            # This will prompt for phone number and verification code
            print("\n📱 Please enter your phone number when prompted...")
            print("📧 You will receive a verification code via Telegram")
            print("🔢 Enter the code when prompted")

            await client.start()

            if await client.is_user_authorized():
                print("✅ Authorization successful!")

                # Get user info
                me = await client.get_me()
                print(f"👤 Authorized as: @{me.username} (ID: {me.id})")

                # Save session string
                print("\n💾 Saving session string...")
                session_string = client.session.save()

                # Update .env file
                env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
                with open(env_path, 'r') as f:
                    lines = f.readlines()

                # Replace or add TELEGRAM_STRING_SESSION
                session_found = False
                for i, line in enumerate(lines):
                    if line.startswith('TELEGRAM_STRING_SESSION='):
                        lines[i] = f'TELEGRAM_STRING_SESSION={session_string}\n'
                        session_found = True
                        break

                if not session_found:
                    lines.append(f'TELEGRAM_STRING_SESSION={session_string}\n')

                with open(env_path, 'w') as f:
                    f.writelines(lines)

                print("✅ Session string saved to .env file")
                if session_string:
                    print(f"🔐 Session: {session_string[:20]}...")
                else:
                    print("🔐 Session: (empty string)")

                # Test channel access
                print("\n🔍 Testing channel access...")
                try:
                    entity = await client.get_entity('@telegram')
                    print(f"✅ @telegram channel accessible: {entity.title}")
                except Exception as e:
                    print(f"⚠️  @telegram access failed: {e}")
                    print("   This may be due to privacy settings or channel restrictions")

            else:
                print("❌ Authorization failed")
                return False

        await client.disconnect()
        print("\n🎉 Session authorization complete!")
        print("✅ You can now run E2E tests with real Telegram API")
        return True

    except KeyboardInterrupt:
        print("\n⚠️  Authorization cancelled by user")
        return False
    except Exception as e:
        print(f"❌ Authorization error: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("🚀 Telegram Session Authorization for E2E Testing")
    print("=" * 60)
    print("This script will authorize your Telegram session for E2E testing.")
    print("You'll need your phone number and access to Telegram for verification.")
    print("=" * 60)

    try:
        success = asyncio.run(authorize_session())

        print("=" * 60)
        if success:
            print("✅ AUTHORIZATION SUCCESSFUL!")
            print("🎯 Ready to run E2E tests with real Telegram data")
        else:
            print("❌ AUTHORIZATION FAILED!")
            print("🔧 Please check your credentials and try again")

    except KeyboardInterrupt:
        print("\n⚠️  Operation cancelled")
        print("🔄 You can run this script again to complete authorization")

    sys.exit(0 if success else 1)
