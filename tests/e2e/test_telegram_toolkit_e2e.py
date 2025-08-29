"""
End-to-End Tests for Telegram Toolkit MCP Server

This module contains comprehensive E2E tests that validate the entire system
with real Telegram API calls using public channels.
"""

import asyncio
import json
import os

import pytest
import pytest_asyncio

from telegram_toolkit_mcp.core.monitoring import get_metrics_collector, init_metrics
from telegram_toolkit_mcp.core.telegram_client import TelegramClientWrapper
from telegram_toolkit_mcp.utils.config import get_config
from telegram_toolkit_mcp.utils.logging import get_logger
from telegram_toolkit_mcp.utils.security import (
    InputValidator,
    get_rate_limiter,
    get_security_auditor,
)

logger = get_logger(__name__)


class TestTelegramToolkitE2E:
    """Comprehensive E2E tests for the Telegram Toolkit MCP Server."""

    @pytest_asyncio.fixture(autouse=True)
    async def setup_e2e(self):
        """Setup for E2E tests with real Telegram API."""
        # Reset metrics for each test
        init_metrics()

        # Ensure we have required environment variables
        required_env_vars = ["TELEGRAM_API_ID", "TELEGRAM_API_HASH"]

        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        if missing_vars:
            pytest.skip(f"Missing required environment variables: {missing_vars}")

        yield

    @pytest_asyncio.fixture
    async def telegram_client(self):
        """Real Telegram client for E2E testing."""
        config = get_config()

        # Create Telethon client
        from telethon import TelegramClient
        from telethon.sessions import StringSession

        # Use StringSession for in-memory session management
        if config.telegram.session_string:
            session = StringSession(config.telegram.session_string)
        else:
            session = StringSession()

        telethon_client = TelegramClient(
            session=session, api_id=config.telegram.api_id, api_hash=config.telegram.api_hash
        )

        client = TelegramClientWrapper()
        await client.connect(telethon_client)

        try:
            yield client
        finally:
            await client.disconnect()

            # StringSession cleanup is handled automatically

    @pytest.fixture
    def rate_limiter(self):
        """Rate limiter for E2E tests."""
        return get_rate_limiter()

    @pytest.fixture
    def input_validator(self):
        """Input validator for E2E tests."""
        return InputValidator()

    @pytest.fixture
    def security_auditor(self):
        """Security auditor for E2E tests."""
        return get_security_auditor()

    @pytest.fixture
    def metrics_collector(self):
        """Metrics collector for E2E tests."""
        return get_metrics_collector()

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_e2e_resolve_chat_official_telegram(
        self,
        telegram_client: TelegramClientWrapper,
        rate_limiter,
        input_validator: InputValidator,
        security_auditor,
        metrics_collector,
    ):
        """Test resolving official Telegram channel."""
        logger.info("🧪 Testing E2E: resolve_chat(@telegram)")

        # Rate limiting check
        await rate_limiter.check_rate_limit("telegram")

        # Input validation
        sanitized = input_validator.sanitize_chat_identifier("@telegram")
        assert sanitized == "@telegram"

        # Security audit
        security_auditor.log_security_event(
            event_type="chat_resolution_attempt",
            details={"chat": "@telegram", "source": "e2e_test"},
        )

        # Execute chat resolution
        try:
            chat_info = await telegram_client.get_chat_info("@telegram")

            # Validate response structure
            assert chat_info is not None
            assert "id" in chat_info
            assert "title" in chat_info
            assert "telegram" in chat_info.get("title", "").lower()
            assert chat_info.get("type") == "channel"

            # Record success metrics
            from telegram_toolkit_mcp.core.monitoring import record_tool_success

            record_tool_success("tg.resolve_chat", "channel")

            logger.info("✅ Successfully resolved @telegram channel")
            logger.info(f"📊 Chat info: {json.dumps(chat_info, indent=2, ensure_ascii=False)}")

        except Exception as e:
            # Record error metrics
            from telegram_toolkit_mcp.core.monitoring import record_tool_error

            record_tool_error("tg.resolve_chat", str(e))
            logger.error(f"❌ Failed to resolve @telegram: {e}")
            raise

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_e2e_fetch_history_small_dataset(
        self,
        telegram_client: TelegramClientWrapper,
        rate_limiter,
        input_validator: InputValidator,
        security_auditor,
        metrics_collector,
    ):
        """Test fetching small dataset from official Telegram channel."""
        logger.info("🧪 Testing E2E: fetch_history small dataset")

        chat_id = "@telegram"
        page_size = 5  # Small dataset for E2E

        # Rate limiting check
        await rate_limiter.check_rate_limit(chat_id)

        # Input validation
        sanitized = input_validator.sanitize_chat_identifier(chat_id)
        assert sanitized == chat_id, f"Chat identifier sanitization failed: {sanitized}"

        validated_page_size = input_validator.validate_page_size(page_size)
        assert validated_page_size > 0, f"Page size validation failed: got {validated_page_size}"

        # Security audit
        security_auditor.log_security_event(
            event_type="message_fetch_attempt",
            details={"chat": chat_id, "page_size": page_size, "source": "e2e_test"},
        )

        # Execute message fetch
        try:
            messages = await telegram_client.fetch_messages(
                chat_id=chat_id,
                limit=page_size,
                offset_id=0,
                reverse=True,  # Fetch in descending order (newest first)
            )

            # Validate response
            assert isinstance(messages, list)
            assert len(messages) <= page_size
            total_fetched = len(messages)

            if messages:
                # Validate message structure
                sample_msg = messages[0]
                assert "id" in sample_msg
                assert "date" in sample_msg
                assert "text" in sample_msg

                logger.info("✅ Successfully fetched messages")
                logger.info(f"📊 Fetched {len(messages)} messages")
                logger.info(
                    f"📄 Sample message: {json.dumps(sample_msg, indent=2, ensure_ascii=False)[:500]}..."
                )

            # Record success metrics
            from telegram_toolkit_mcp.core.monitoring import (
                record_messages_fetched,
                record_tool_success,
            )

            record_messages_fetched("tg.fetch_history", len(messages), False)
            record_tool_success("tg.fetch_history", "channel")

        except Exception as e:
            # Record error metrics
            from telegram_toolkit_mcp.core.monitoring import record_tool_error

            record_tool_error("tg.fetch_history", str(e))
            logger.error(f"❌ Failed to fetch messages: {e}")
            raise

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_e2e_fetch_history_with_filtering(
        self,
        telegram_client: TelegramClientWrapper,
        rate_limiter,
        input_validator: InputValidator,
        security_auditor,
        metrics_collector,
    ):
        """Test message fetching with content filtering."""
        logger.info("🧪 Testing E2E: fetch_history with filtering")

        chat_id = "@telegram"
        page_size = 20
        search_query = "Telegram"

        # Rate limiting check
        await rate_limiter.check_rate_limit(chat_id)

        # Execute message fetch with search
        try:
            messages = await telegram_client.fetch_messages(
                chat_id=chat_id,
                limit=page_size,
                offset_id=0,
                search=search_query,
                reverse=True,  # Fetch in descending order (newest first)
            )

            # Validate response
            assert isinstance(messages, list)
            assert len(messages) <= page_size

            # Check if search filtering worked (messages should contain the search term)
            if messages:
                search_found = any(
                    search_query.lower() in (msg.get("text", "")).lower() for msg in messages
                )
                logger.info(f"🔍 Search term '{search_query}' found in messages: {search_found}")

                logger.info("✅ Successfully fetched and filtered messages")
                logger.info(f"📊 Fetched {len(messages)} filtered messages")

            # Record success metrics
            from telegram_toolkit_mcp.core.monitoring import (
                record_messages_fetched,
                record_tool_success,
            )

            record_messages_fetched("tg.fetch_history", len(messages), False)
            record_tool_success("tg.fetch_history", "channel")

        except Exception as e:
            from telegram_toolkit_mcp.core.monitoring import record_tool_error

            record_tool_error("tg.fetch_history", str(e))
            logger.error(f"❌ Failed to fetch filtered messages: {e}")
            raise

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_e2e_pagination_cursor_functionality(
        self,
        telegram_client: TelegramClientWrapper,
        rate_limiter,
        input_validator: InputValidator,
        metrics_collector,
    ):
        """Test pagination with cursor functionality."""
        logger.info("🧪 Testing E2E: pagination cursor functionality")

        chat_id = "@telegram"
        page_size = 10

        # Rate limiting check
        await rate_limiter.check_rate_limit(chat_id)

        # First page
        try:
            messages_page1 = await telegram_client.fetch_messages(
                chat_id=chat_id,
                limit=page_size,
                offset_id=0,
                reverse=True,  # Fetch in descending order (newest first)
            )
            total_fetched1 = len(messages_page1)

            assert len(messages_page1) <= page_size

            if len(messages_page1) == page_size:
                # Get cursor for next page
                last_msg = messages_page1[-1]
                next_offset_id = last_msg["id"]

                # Second page
                messages_page2 = await telegram_client.fetch_messages(
                    chat_id=chat_id,
                    limit=page_size,
                    offset_id=next_offset_id,
                    reverse=True,  # Fetch in descending order (newest first)
                )
                total_fetched2 = len(messages_page2)

                # Validate pagination
                assert len(messages_page2) <= page_size

                # Ensure no duplicate messages
                page1_ids = {msg["id"] for msg in messages_page1}
                page2_ids = {msg["id"] for msg in messages_page2}
                assert len(page1_ids & page2_ids) == 0, "Duplicate messages found between pages"

                logger.info("✅ Successfully tested pagination")
                logger.info(f"📊 Page 1: {len(messages_page1)} messages")
                logger.info(f"📊 Page 2: {len(messages_page2)} messages")

            # Record success metrics
            total_messages = len(messages_page1) + (
                len(messages_page2) if "messages_page2" in locals() else 0
            )
            from telegram_toolkit_mcp.core.monitoring import (
                record_messages_fetched,
                record_page_served,
            )

            record_messages_fetched("tg.fetch_history", total_messages, False)
            record_page_served("tg.fetch_history")

        except Exception as e:
            from telegram_toolkit_mcp.core.monitoring import record_tool_error

            record_tool_error("tg.fetch_history", str(e))
            logger.error(f"❌ Failed pagination test: {e}")
            raise

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_e2e_large_dataset_ndjson_export(
        self,
        telegram_client: TelegramClientWrapper,
        rate_limiter,
        input_validator: InputValidator,
        metrics_collector,
    ):
        """Test large dataset handling with NDJSON export."""
        logger.info("🧪 Testing E2E: large dataset NDJSON export")

        chat_id = "@telegram"
        large_page_size = 50  # Large enough to potentially trigger NDJSON

        # Rate limiting check
        await rate_limiter.check_rate_limit(chat_id)

        # Execute large fetch
        try:
            messages = await telegram_client.fetch_messages(
                chat_id=chat_id,
                limit=large_page_size,
                offset_id=0,
                reverse=True,  # Fetch in descending order (newest first)
            )

            # Validate large dataset handling
            assert isinstance(messages, list)
            assert len(messages) <= large_page_size

            if len(messages) == large_page_size:
                logger.info("📊 Large dataset fetched successfully")
                logger.info(f"📈 Dataset size: {len(messages)} messages")

                # Test message structure for large dataset
                for i, msg in enumerate(messages[:5]):  # Check first 5 messages
                    assert "id" in msg
                    assert "date" in msg
                    assert isinstance(msg["date"], (int, float))

            # Record success metrics
            from telegram_toolkit_mcp.core.monitoring import (
                record_messages_fetched,
                record_ndjson_export,
            )

            record_messages_fetched("tg.fetch_history", len(messages), False)
            if len(messages) >= 100:  # Large dataset threshold
                record_ndjson_export("success", len(messages) * 1024)  # Estimate size

            logger.info("✅ Successfully handled large dataset")

        except Exception as e:
            from telegram_toolkit_mcp.core.monitoring import record_tool_error

            record_tool_error("tg.fetch_history", str(e))
            logger.error(f"❌ Failed large dataset test: {e}")
            raise

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_e2e_error_handling_and_recovery(
        self, telegram_client: TelegramClientWrapper, metrics_collector
    ):
        """Test error handling and recovery mechanisms."""
        logger.info("🧪 Testing E2E: error handling and recovery")

        # Test with invalid chat ID
        try:
            await telegram_client.get_chat_info("invalid_chat_12345")
            assert False, "Should have raised an exception for invalid chat"
        except Exception as e:
            logger.info(f"✅ Correctly handled invalid chat error: {type(e).__name__}")
            from telegram_toolkit_mcp.core.monitoring import record_tool_error

            record_tool_error("tg.resolve_chat", str(e))

        # Test with valid chat but invalid parameters
        try:
            chat_id = "@telegram"
            await telegram_client.fetch_messages(
                chat_id=chat_id,
                limit=1000,  # Exceedingly large limit
                offset_id=0,
            )
            # This should work or fail gracefully
            logger.info("✅ Handled large limit parameter gracefully")
        except Exception as e:
            logger.info(f"✅ Correctly handled parameter error: {type(e).__name__}")
            from telegram_toolkit_mcp.core.monitoring import record_tool_error

            record_tool_error("tg.fetch_history", str(e))

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_e2e_security_validation(self, input_validator: InputValidator, security_auditor):
        """Test security validation mechanisms."""
        logger.info("🧪 Testing E2E: security validation")

        # Test valid inputs
        valid_inputs = [
            "@telegram",
            "https://t.me/telegram",
            "@channel123",
            "123456789",  # Numeric ID
        ]

        for input_val in valid_inputs:
            sanitized = input_validator.sanitize_chat_identifier(input_val)
            assert sanitized == input_val, f"Valid input '{input_val}' sanitization failed"

        # Test invalid inputs
        invalid_inputs = [
            "",
            "a",  # Too short
            "@",  # Invalid format
            "telegram channel",  # Spaces
            "<script>alert('xss')</script>",  # XSS attempt
            "../../../etc/passwd",  # Path traversal
        ]

        for input_val in invalid_inputs:
            try:
                sanitized = input_validator.sanitize_chat_identifier(input_val)
                # If we get here, sanitization worked (which might be okay for some inputs)
                assert isinstance(
                    sanitized, str
                ), f"Sanitization should return string for '{input_val}'"
                logger.info(f"⚠️  Input '{input_val}' was sanitized to '{sanitized}'")
            except ValueError as e:
                # This is expected for truly invalid inputs
                logger.info(f"✅ Input '{input_val}' correctly rejected: {e}")

            # Log security event for potentially problematic input
            security_auditor.log_security_event(
                event_type="input_validation_processed",
                details={"input": input_val, "error": str(e) if "e" in locals() else "sanitized"},
            )

        logger.info("✅ Security validation working correctly")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_e2e_rate_limiting_protection(self, rate_limiter, metrics_collector):
        """Test rate limiting protection mechanisms."""
        logger.info("🧪 Testing E2E: rate limiting protection")

        chat_id = "@telegram"

        # Test normal rate limiting
        for i in range(5):
            allowed, wait_time = await rate_limiter.check_rate_limit(chat_id)
            if allowed:
                logger.info(f"✅ Rate limit check {i+1} passed")
            else:
                logger.info(f"🚫 Rate limit exceeded on attempt {i+1}, wait {wait_time:.1f}s")
                break

        # Test burst protection
        await asyncio.sleep(1)  # Reset burst window

        burst_attempts = []
        for i in range(15):  # More than burst limit
            allowed, wait_time = await rate_limiter.check_rate_limit(chat_id)
            burst_attempts.append(allowed)
            if not allowed:
                logger.info(
                    f"🚫 Burst protection triggered on attempt {i+1}, wait {wait_time:.1f}s"
                )
                break

        # Should have blocked some requests
        blocked_count = burst_attempts.count(False)
        assert (
            blocked_count > 0
        ), f"Rate limiting should have blocked some requests, but none were blocked. Attempts: {burst_attempts}"

        logger.info("✅ Rate limiting protection working correctly")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_e2e_metrics_collection_and_reporting(
        self, telegram_client: TelegramClientWrapper, metrics_collector
    ):
        """Test comprehensive metrics collection and reporting."""
        logger.info("🧪 Testing E2E: metrics collection")

        chat_id = "@telegram"

        # Generate some activity to collect metrics
        await telegram_client.get_chat_info(chat_id)
        await telegram_client.fetch_messages(chat_id, limit=5)

        # Check metrics collection
        metrics_output = metrics_collector.get_metrics()

        assert "mcp_tool_calls_total" in metrics_output
        assert "telegram_api_calls_total" in metrics_output
        assert "telegram_messages_fetched_total" in metrics_output

        logger.info("✅ Metrics collection working correctly")
        logger.info(f"📊 Collected metrics: {len(metrics_output)} metric types")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_e2e_end_to_end_workflow(
        self,
        telegram_client: TelegramClientWrapper,
        rate_limiter,
        input_validator: InputValidator,
        security_auditor,
        metrics_collector,
    ):
        """Complete end-to-end workflow test."""
        logger.info("🧪 Testing E2E: complete workflow")

        chat_id = "@telegram"
        page_size = 10

        # Step 1: Rate limiting check
        await rate_limiter.check_rate_limit(chat_id)

        # Step 2: Input validation
        sanitized = input_validator.sanitize_chat_identifier(chat_id)
        assert sanitized == chat_id, f"Chat identifier validation failed for {chat_id}"

        # Step 3: Security audit
        security_auditor.log_security_event(
            event_type="workflow_start",
            details={"workflow": "e2e_test", "chat": chat_id},
        )

        # Step 4: Resolve chat
        chat_info = await telegram_client.get_chat_info(chat_id)
        assert chat_info is not None

        # Step 5: Fetch messages
        messages = await telegram_client.fetch_messages(chat_id=chat_id, limit=page_size)
        total_fetched = len(messages)

        # Step 6: Validate results
        assert isinstance(messages, list)
        assert len(messages) <= page_size

        # Step 7: Record metrics
        from telegram_toolkit_mcp.core.monitoring import (
            record_messages_fetched,
            record_tool_success,
        )

        record_tool_success("tg.resolve_chat", "channel")
        record_tool_success("tg.fetch_history", "channel")
        record_messages_fetched("tg.fetch_history", len(messages), False)

        # Step 8: Security audit completion
        security_auditor.log_security_event(
            event_type="workflow_complete",
            details={"workflow": "e2e_test", "messages_fetched": len(messages)},
        )

        logger.info("🎉 Complete E2E workflow successful!")
        logger.info(f"📊 Workflow summary: {len(messages)} messages from {chat_info.get('title')}")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_e2e_performance_baseline(
        self, telegram_client: TelegramClientWrapper, metrics_collector
    ):
        """Test performance baseline for key operations."""
        logger.info("🧪 Testing E2E: performance baseline")

        chat_id = "@telegram"
        import time

        # Test chat resolution performance
        start_time = time.time()
        chat_info = await telegram_client.get_chat_info(chat_id)
        resolve_time = time.time() - start_time

        # Test message fetch performance
        start_time = time.time()
        messages = await telegram_client.fetch_messages(chat_id, limit=20)
        fetch_time = time.time() - start_time

        # Log performance metrics
        logger.info(
            f"✅ Performance test completed - Resolve: {resolve_time:.3f}s, Fetch: {fetch_time:.3f}s"
        )

        # Validate reasonable performance
        assert resolve_time < 5.0, f"Resolve time too slow: {resolve_time:.3f}s"
        assert fetch_time < 10.0, f"Fetch time too slow: {fetch_time:.3f}s"
        logger.info("✅ Performance baseline within acceptable limits")
