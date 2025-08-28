#!/usr/bin/env python3
"""
E2E Test: Resolve Chat (@durov)
"""
import sys
import os
import asyncio
import json
import time

# Add src to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from telegram_toolkit_mcp.core.telegram_client import TelegramClientWrapper
from telegram_toolkit_mcp.utils.config import get_config
from telegram_toolkit_mcp.utils.logging import get_logger
from dotenv import load_dotenv

logger = get_logger(__name__)

async def test_resolve_chat():
    """Test resolving @durov channel."""
    # Load environment variables
    load_dotenv()

    config = get_config()

    # Check required environment variables
    if not config.telegram.api_id or not config.telegram.api_hash:
        print("❌ Missing TELEGRAM_API_ID or TELEGRAM_API_HASH")
        return False

    # Create Telethon client
    from telethon import TelegramClient
    import tempfile

    # Use a temporary session file
    temp_fd, session_path = tempfile.mkstemp(suffix='.session')
    os.close(temp_fd)

    telethon_client = TelegramClient(
        session=session_path,
        api_id=config.telegram.api_id,
        api_hash=config.telegram.api_hash
    )

    client = TelegramClientWrapper()
    await client.connect(telethon_client)

    try:
        print("🧪 Testing E2E: resolve_chat(@durov)")
        start_time = time.time()

        # Test input validation
        from telegram_toolkit_mcp.utils.security import InputValidator
        input_validator = InputValidator()
        sanitized = input_validator.sanitize_chat_identifier("@durov")
        assert sanitized == "@durov", f"Input sanitization failed: {sanitized}"
        print("✅ Input validation passed")

        # Test security audit
        from telegram_toolkit_mcp.utils.security import get_security_auditor
        security_auditor = get_security_auditor()
        security_auditor.log_security_event(
            event_type="chat_resolution_attempt",
            details={"chat": "@durov", "source": "e2e_test"}
        )
        print("✅ Security audit logged")

        # Execute chat resolution
        chat_info = await client.get_chat_info("@durov")

        resolve_time = time.time() - start_time

        # Validate response structure
        assert chat_info is not None, "Chat info is None"
        assert "id" in chat_info, "Missing 'id' in chat info"
        assert "title" in chat_info, "Missing 'title' in chat info"
        assert "durov" in chat_info.get("title", "").lower(), f"Title doesn't contain 'durov': {chat_info.get('title')}"
        assert chat_info.get("kind") == "channel", f"Expected 'channel', got '{chat_info.get('kind')}'"

        # Record success metrics
        from telegram_toolkit_mcp.core.monitoring import get_metrics_collector
        metrics_collector = get_metrics_collector()
        metrics_collector.record_success("tg.resolve_chat")

        logger.info("✅ Successfully resolved @durov channel")
        logger.info(f"📊 Chat info: {json.dumps(chat_info, indent=2, ensure_ascii=False)}")
        logger.info(f"⏱️  Resolve time: {resolve_time:.3f}s")

        # Validate reasonable performance
        assert resolve_time < 5.0, ".3f"

        print("🎉 E2E TEST PASSED!")
        return True

    except Exception as e:
        logger.error(f"❌ Failed to resolve @durov: {e}")

        # Record error metrics
        from telegram_toolkit_mcp.core.monitoring import get_metrics_collector
        metrics_collector = get_metrics_collector()
        metrics_collector.record_error("tg.resolve_chat", str(e))

        print(f"❌ E2E TEST FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        await client.disconnect()

        # Clean up temporary session file
        if os.path.exists(session_path):
            os.unlink(session_path)

if __name__ == "__main__":
    print("🚀 Starting E2E Test: Resolve Chat (@durov)")
    print("=" * 60)

    success = asyncio.run(test_resolve_chat())

    print("=" * 60)
    if success:
        print("✅ tg.resolve_chat functionality test PASSED!")
    else:
        print("❌ tg.resolve_chat functionality test FAILED!")

    sys.exit(0 if success else 1)
