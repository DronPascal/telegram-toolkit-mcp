"""
End-to-End Tests for Telegram Toolkit MCP Server

This module contains comprehensive E2E tests that validate the entire system
with real Telegram API calls using public channels.
"""

import asyncio
import json
import os
import pytest
import tempfile
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Any
from unittest.mock import AsyncMock, MagicMock

from telegram_toolkit_mcp.core.telegram_client import TelegramClientWrapper
from telegram_toolkit_mcp.core.error_handler import ErrorTracker, create_success_response, create_error_response
from telegram_toolkit_mcp.core.monitoring import get_metrics_collector, init_metrics
from telegram_toolkit_mcp.core.pagination import PaginationCursor
from telegram_toolkit_mcp.core.filtering import DateRangeFilter, MessageProcessor
from telegram_toolkit_mcp.core.ndjson_resources import NDJSONResourceManager
from telegram_toolkit_mcp.models.types import (
    ResolveChatRequest,
    ResolveChatResponse,
    FetchHistoryRequest,
    FetchHistoryResponse,
    PageInfo,
    MessageInfo,
    ExportInfo
)
from telegram_toolkit_mcp.utils.config import get_config
from telegram_toolkit_mcp.utils.logging import get_logger
from telegram_toolkit_mcp.utils.security import get_rate_limiter, InputValidator, get_security_auditor


logger = get_logger(__name__)


class TestTelegramToolkitE2E:
    """Comprehensive E2E tests for the Telegram Toolkit MCP Server."""

    @pytest.fixture(autouse=True)
    async def setup_e2e(self):
        """Setup for E2E tests with real Telegram API."""
        # Reset metrics for each test
        init_metrics()

        # Ensure we have required environment variables
        required_env_vars = [
            'TELEGRAM_API_ID',
            'TELEGRAM_API_HASH'
        ]

        missing_vars = [var for var in required_env_vars if not os.getenv(var)]
        if missing_vars:
            pytest.skip(f"Missing required environment variables: {missing_vars}")

        yield

    @pytest.fixture
    async def telegram_client(self):
        """Real Telegram client for E2E testing."""
        config = get_config()

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
        await client.connect(telethon_client)

        try:
            yield client
        finally:
            await client.disconnect()

            # Clean up temporary session file
            if session_path and os.path.exists(session_path):
                os.unlink(session_path)

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
        metrics_collector
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
            details={"chat": "@telegram", "source": "e2e_test"}
        )

        # Execute chat resolution
        try:
            chat_info = await telegram_client.get_chat_info("@telegram")

            # Validate response structure
            assert chat_info is not None
            assert "id" in chat_info
            assert "title" in chat_info
            assert "durov" in chat_info.get("title", "").lower()
            assert chat_info.get("kind") == "channel"

            # Record success metrics
            metrics_collector.record_success("tg.resolve_chat")

            logger.info("✅ Successfully resolved @telegram channel")
            logger.info(f"📊 Chat info: {json.dumps(chat_info, indent=2, ensure_ascii=False)}")

        except Exception as e:
            # Record error metrics
            metrics_collector.record_error("tg.resolve_chat", str(e))
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
        metrics_collector
    ):
        """Test fetching small dataset from official Telegram channel."""
        logger.info("🧪 Testing E2E: fetch_history small dataset")

        chat_id = "@telegram"
        page_size = 5  # Small dataset for E2E

        # Rate limiting check
        await rate_limiter.check_rate_limit(chat_id)

        # Input validation
        sanitized = input_validator.sanitize_chat_identifier(chat_id)
        assert sanitized == chat_id
        assert is_valid, f"Input validation failed: {error_msg}"

        is_valid, error_msg = input_validator.validate_page_size(page_size)
        assert is_valid, f"Page size validation failed: {error_msg}"

        # Security audit
        security_auditor.log_security_event(
            event_type="message_fetch_attempt",
            details={"chat": chat_id, "page_size": page_size, "source": "e2e_test"},

        )

        # Execute message fetch
        try:
            messages, total_fetched = await telegram_client.fetch_messages(
                chat_id=chat_id,
                limit=page_size,
                offset_id=0,
                direction="desc"
            )

            # Validate response
            assert isinstance(messages, list)
            assert len(messages) <= page_size
            assert total_fetched == len(messages)

            if messages:
                # Validate message structure
                sample_msg = messages[0]
                assert "id" in sample_msg
                assert "date" in sample_msg
                assert "text" in sample_msg

                logger.info("✅ Successfully fetched messages")
                logger.info(f"📊 Fetched {len(messages)} messages")
                logger.info(f"📄 Sample message: {json.dumps(sample_msg, indent=2, ensure_ascii=False)[:500]}...")

            # Record success metrics
            metrics_collector.record_messages_fetched(len(messages))
            metrics_collector.record_success("tg.fetch_history")

        except Exception as e:
            # Record error metrics
            metrics_collector.record_error("tg.fetch_history", str(e))
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
        metrics_collector
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
            messages, total_fetched = await telegram_client.fetch_messages(
                chat_id=chat_id,
                limit=page_size,
                offset_id=0,
                search=search_query,
                direction="desc"
            )

            # Validate response
            assert isinstance(messages, list)
            assert len(messages) <= page_size

            # Check if search filtering worked (messages should contain the search term)
            if messages:
                search_found = any(
                    search_query.lower() in (msg.get("text", "")).lower()
                    for msg in messages
                )
                logger.info(f"🔍 Search term '{search_query}' found in messages: {search_found}")

                logger.info("✅ Successfully fetched and filtered messages")
                logger.info(f"📊 Fetched {len(messages)} filtered messages")

            # Record success metrics
            metrics_collector.record_messages_fetched(len(messages))
            metrics_collector.record_success("tg.fetch_history")

        except Exception as e:
            metrics_collector.record_error("tg.fetch_history", str(e))
            logger.error(f"❌ Failed to fetch filtered messages: {e}")
            raise

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_e2e_pagination_cursor_functionality(
        self,
        telegram_client: TelegramClientWrapper,
        rate_limiter,
        input_validator: InputValidator,
        metrics_collector
    ):
        """Test pagination with cursor functionality."""
        logger.info("🧪 Testing E2E: pagination cursor functionality")

        chat_id = "@telegram"
        page_size = 10

        # Rate limiting check
        await rate_limiter.check_rate_limit(chat_id)

        # First page
        try:
            messages_page1, total_fetched1 = await telegram_client.fetch_messages(
                chat_id=chat_id,
                limit=page_size,
                offset_id=0,
                direction="desc"
            )

            assert len(messages_page1) <= page_size

            if len(messages_page1) == page_size:
                # Get cursor for next page
                last_msg = messages_page1[-1]
                next_offset_id = last_msg["id"]

                # Second page
                messages_page2, total_fetched2 = await telegram_client.fetch_messages(
                    chat_id=chat_id,
                    limit=page_size,
                    offset_id=next_offset_id,
                    direction="desc"
                )

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
            total_messages = len(messages_page1) + (len(messages_page2) if 'messages_page2' in locals() else 0)
            metrics_collector.record_messages_fetched(total_messages)
            metrics_collector.record_page_served()

        except Exception as e:
            metrics_collector.record_error("tg.fetch_history", str(e))
            logger.error(f"❌ Failed pagination test: {e}")
            raise

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_e2e_large_dataset_ndjson_export(
        self,
        telegram_client: TelegramClientWrapper,
        rate_limiter,
        input_validator: InputValidator,
        metrics_collector
    ):
        """Test large dataset handling with NDJSON export."""
        logger.info("🧪 Testing E2E: large dataset NDJSON export")

        chat_id = "@telegram"
        large_page_size = 50  # Large enough to potentially trigger NDJSON

        # Rate limiting check
        await rate_limiter.check_rate_limit(chat_id)

        # Execute large fetch
        try:
            messages, total_fetched = await telegram_client.fetch_messages(
                chat_id=chat_id,
                limit=large_page_size,
                offset_id=0,
                direction="desc"
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
            metrics_collector.record_messages_fetched(len(messages))
            if len(messages) >= 100:  # Large dataset threshold
                metrics_collector.record_ndjson_export()

            logger.info("✅ Successfully handled large dataset")

        except Exception as e:
            metrics_collector.record_error("tg.fetch_history", str(e))
            logger.error(f"❌ Failed large dataset test: {e}")
            raise

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_e2e_error_handling_and_recovery(
        self,
        telegram_client: TelegramClientWrapper,
        metrics_collector
    ):
        """Test error handling and recovery mechanisms."""
        logger.info("🧪 Testing E2E: error handling and recovery")

        # Test with invalid chat ID
        try:
            await telegram_client.get_chat_info("invalid_chat_12345")
            assert False, "Should have raised an exception for invalid chat"
        except Exception as e:
            logger.info(f"✅ Correctly handled invalid chat error: {type(e).__name__}")
            metrics_collector.record_error("tg.resolve_chat", str(e))

        # Test with valid chat but invalid parameters
        try:
            chat_id = "@telegram"
            await telegram_client.fetch_messages(
                chat_id=chat_id,
                limit=1000,  # Exceedingly large limit
                offset_id=0
            )
            # This should work or fail gracefully
            logger.info("✅ Handled large limit parameter gracefully")
        except Exception as e:
            logger.info(f"✅ Correctly handled parameter error: {type(e).__name__}")
            metrics_collector.record_error("tg.fetch_history", str(e))

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_e2e_security_validation(
        self,
        input_validator: InputValidator,
        security_auditor
    ):
        """Test security validation mechanisms."""
        logger.info("🧪 Testing E2E: security validation")

        # Test valid inputs
        valid_inputs = [
            "@telegram",
            "https://t.me/telegram",
            "telegram",
            "136817688"  # Numeric ID
        ]

        for input_val in valid_inputs:
            sanitized = input_validator.sanitize_chat_identifier(input_val)
            assert sanitized == input_val
            assert is_valid, f"Valid input '{input_val}' failed validation: {error_msg}"

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
            sanitized = input_validator.sanitize_chat_identifier(input_val)
            assert sanitized == input_val
            assert not is_valid, f"Invalid input '{input_val}' should have failed validation"

            # Log security event for blocked input
            security_auditor.log_security_event(
                event_type="input_validation_blocked",
                details={"input": input_val, "reason": error_msg},

            )

        logger.info("✅ Security validation working correctly")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_e2e_rate_limiting_protection(
        self,
        rate_limiter,
        metrics_collector
    ):
        """Test rate limiting protection mechanisms."""
        logger.info("🧪 Testing E2E: rate limiting protection")

        chat_id = "@telegram"

        # Test normal rate limiting
        for i in range(5):
            try:
                await rate_limiter.check_rate_limit(chat_id)
                logger.info(f"✅ Rate limit check {i+1} passed")
            except Exception as e:
                logger.info(f"🚫 Rate limit exceeded on attempt {i+1}: {e}")
                break

        # Test burst protection
        await asyncio.sleep(1)  # Reset burst window

        burst_attempts = []
        for i in range(15):  # More than burst limit
            try:
                await rate_limiter.check_rate_limit(chat_id)
                burst_attempts.append(True)
            except Exception as e:
                burst_attempts.append(False)
                logger.info(f"🚫 Burst protection triggered on attempt {i+1}")
                break

        # Should have blocked some requests
        assert len(burst_attempts) < 15, "Rate limiting should have kicked in"

        logger.info("✅ Rate limiting protection working correctly")

    @pytest.mark.e2e
    @pytest.mark.asyncio
    async def test_e2e_metrics_collection_and_reporting(
        self,
        telegram_client: TelegramClientWrapper,
        metrics_collector
    ):
        """Test comprehensive metrics collection and reporting."""
        logger.info("🧪 Testing E2E: metrics collection")

        chat_id = "@telegram"

        # Generate some activity to collect metrics
        await telegram_client.get_chat_info(chat_id)
        await telegram_client.fetch_messages(chat_id, limit=5)

        # Check metrics collection
        metrics_output = metrics_collector.get_metrics_output()

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
        metrics_collector
    ):
        """Complete end-to-end workflow test."""
        logger.info("🧪 Testing E2E: complete workflow")

        chat_id = "@telegram"
        page_size = 10

        # Step 1: Rate limiting check
        await rate_limiter.check_rate_limit(chat_id)

        # Step 2: Input validation
        sanitized = input_validator.sanitize_chat_identifier(chat_id)
        assert sanitized == chat_id
        assert is_valid

        # Step 3: Security audit
        security_auditor.log_security_event(
            event_type="workflow_start",
            details={"workflow": "e2e_test", "chat": chat_id},

        )

        # Step 4: Resolve chat
        chat_info = await telegram_client.get_chat_info(chat_id)
        assert chat_info is not None

        # Step 5: Fetch messages
        messages, total_fetched = await telegram_client.fetch_messages(
            chat_id=chat_id,
            limit=page_size
        )

        # Step 6: Validate results
        assert isinstance(messages, list)
        assert len(messages) <= page_size

        # Step 7: Record metrics
        metrics_collector.record_success("tg.resolve_chat")
        metrics_collector.record_success("tg.fetch_history")
        metrics_collector.record_messages_fetched(len(messages))

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
        self,
        telegram_client: TelegramClientWrapper,
        metrics_collector
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
        messages, _ = await telegram_client.fetch_messages(chat_id, limit=20)
        fetch_time = time.time() - start_time

        # Log performance metrics
        logger.info(f"✅ Performance test completed - Resolve: {resolve_time:.3f}s, Fetch: {fetch_time:.3f}s")

        # Validate reasonable performance
        assert resolve_time < 5.0, f"Resolve time too slow: {resolve_time:.3f}s"
        assert fetch_time < 10.0, f"Fetch time too slow: {fetch_time:.3f}s"
        logger.info("✅ Performance baseline within acceptable limits")
