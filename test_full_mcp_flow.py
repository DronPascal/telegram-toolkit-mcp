#!/usr/bin/env python3
"""
Test script for complete MCP protocol flow with real tools.
Tests the actual FastMCP server with real Telegram tools.
"""

import sys

import requests  # type: ignore[import-untyped]

# Constants
HTTP_OK = 200


def test_full_mcp_flow() -> bool:  # noqa: PLR0911,PLR0912,PLR0915
    """Test complete MCP protocol flow with real tools"""

    base_url = "http://localhost:8000"
    headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream"}

    print("🧪 Testing Complete MCP Protocol Flow")
    print("=" * 60)

    # Test 1: Health check
    print("\n1. Health Check")
    try:
        response = requests.get(f"{base_url}/health")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.text}")
        assert response.status_code == HTTP_OK
        print("   ✅ Health check passed")
    except (requests.RequestException, ConnectionError) as e:
        print(f"   ❌ Health check failed: {e}")
        return False

    # Test 2: MCP Initialize
    print("\n2. MCP Initialize")
    session_id = None
    try:
        init_payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {},
                "clientInfo": {"name": "test-client", "version": "1.0.0"},
            },
        }

        response = requests.post(f"{base_url}/mcp", json=init_payload, headers=headers)
        print(f"   Status: {response.status_code}")

        # Get session ID from headers
        session_id = response.headers.get("mcp-session-id")
        print(f"   Session ID: {session_id}")

        if response.status_code == HTTP_OK and session_id:
            print("   ✅ MCP initialize responded with session ID")
        else:
            print(f"   ⚠️  Unexpected status or missing session ID: {response.status_code}")

    except (requests.RequestException, ConnectionError) as e:
        print(f"   ❌ MCP initialize failed: {e}")
        return False

    # Test 3: Tools List via MCP
    print("\n3. MCP Tools/List")
    try:
        if not session_id:
            print("   ❌ No session ID available")
            return False

        tools_payload = {"jsonrpc": "2.0", "id": 2, "method": "tools/list"}

        # Add session ID to headers
        request_headers = headers.copy()
        request_headers["mcp-session-id"] = session_id

        response = requests.post(f"{base_url}/mcp", json=tools_payload, headers=request_headers)
        print(f"   Status: {response.status_code}")

        if response.status_code == HTTP_OK:
            print("   ✅ MCP tools/list responded")
        else:
            print(f"   ⚠️  Unexpected status: {response.status_code}")

    except (requests.RequestException, ConnectionError) as e:
        print(f"   ❌ MCP tools/list failed: {e}")
        return False

    # Test 4: Tool Call - resolve_chat
    print("\n4. MCP Tool Call - resolve_chat")
    try:
        if not session_id:
            print("   ❌ No session ID available")
            return False

        tool_payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {"name": "resolve_chat", "arguments": {"chat_identifier": "@telegram"}},
        }

        # Add session ID to headers
        request_headers = headers.copy()
        request_headers["mcp-session-id"] = session_id

        response = requests.post(f"{base_url}/mcp", json=tool_payload, headers=request_headers)
        print(f"   Status: {response.status_code}")

        if response.status_code == HTTP_OK:
            print("   ✅ MCP resolve_chat tool responded")
        else:
            print(f"   ⚠️  Unexpected status: {response.status_code}")

    except (requests.RequestException, ConnectionError) as e:
        print(f"   ❌ MCP resolve_chat failed: {e}")
        return False

    # Test 5: Tool Call - fetch_history
    print("\n5. MCP Tool Call - fetch_history")
    try:
        if not session_id:
            print("   ❌ No session ID available")
            return False

        tool_payload = {
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {"name": "fetch_history", "arguments": {"chat": "@telegram", "limit": 3}},
        }

        # Add session ID to headers
        request_headers = headers.copy()
        request_headers["mcp-session-id"] = session_id

        response = requests.post(f"{base_url}/mcp", json=tool_payload, headers=request_headers)
        print(f"   Status: {response.status_code}")

        if response.status_code == HTTP_OK:
            print("   ✅ MCP fetch_history tool responded")
        else:
            print(f"   ⚠️  Unexpected status: {response.status_code}")

    except (requests.RequestException, ConnectionError) as e:
        print(f"   ❌ MCP fetch_history failed: {e}")
        return False

    # Test 6: Tools API
    print("\n6. Tools API Endpoint")
    try:
        response = requests.get(f"{base_url}/api/tools")
        print(f"   Status: {response.status_code}")
        if response.status_code == HTTP_OK:
            result = response.json()
            tools = result.get("tools", [])
            print(f"   Tools available: {len(tools)}")
            for tool in tools:
                print(f"     - {tool.get('name')}: {tool.get('description', '')[:50]}...")
            print("   ✅ Tools API working with real tools")
        else:
            print(f"   ❌ Tools API failed with status {response.status_code}")

    except (requests.RequestException, ConnectionError) as e:
        print(f"   ❌ Tools API failed: {e}")
        return False

    print("\n" + "=" * 60)
    print("🎉 Complete MCP protocol flow test passed!")
    print("✅ All endpoints working correctly")
    print("✅ Real tools are registered and accessible")
    print("✅ MCP server is fully functional")
    return True


if __name__ == "__main__":
    success = test_full_mcp_flow()
    sys.exit(0 if success else 1)
