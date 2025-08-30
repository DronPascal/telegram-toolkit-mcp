#!/usr/bin/env python3
"""
Debug MCP 500 Error - Find the cause of Internal Server Error

This script helps diagnose why MCP endpoint returns 500 instead of 406.
"""

import json
import sys
import urllib.request
import urllib.error
from urllib.parse import urlparse


def test_mcp_with_details(base_url, method="GET", data=None, headers=None):
    """Test MCP endpoint and show detailed error information."""
    url = f"{base_url}/mcp"
    
    print(f"🔍 Testing MCP endpoint: {method} {url}")
    if headers:
        print(f"📋 Headers: {headers}")
    if data:
        print(f"📦 Data: {data}")
    
    try:
        if data:
            data = data.encode('utf-8') if isinstance(data, str) else data
            
        req = urllib.request.Request(url, data=data, method=method)
        
        if headers:
            for key, value in headers.items():
                req.add_header(key, value)
        
        with urllib.request.urlopen(req) as response:
            content = response.read().decode('utf-8')
            status = response.getcode()
            print(f"✅ Status: {status}")
            print(f"📄 Response: {content[:200]}...")
            return True
            
    except urllib.error.HTTPError as e:
        print(f"❌ HTTP Error: {e.code} {e.reason}")
        try:
            error_content = e.read().decode('utf-8')
            print(f"📄 Error Response: {error_content}")
        except:
            print("📄 No error content available")
        return False
        
    except Exception as e:
        print(f"💥 Exception: {e}")
        return False


def main():
    """Main diagnostic function."""
    if len(sys.argv) != 2:
        print("Usage: python3 debug_mcp_500.py <base_url>")
        print("Example: python3 debug_mcp_500.py http://localhost:8000")
        sys.exit(1)
    
    base_url = sys.argv[1].rstrip('/')
    
    print(f"🔍 MCP 500 Error Diagnostic")
    print(f"🎯 Target: {base_url}")
    print("=" * 50)
    
    # Test 1: Simple GET request
    print("\n1️⃣ Testing GET request (should return 406 or 500):")
    print("-" * 50)
    test_mcp_with_details(base_url, "GET")
    
    # Test 2: POST without headers
    print("\n2️⃣ Testing POST without headers:")
    print("-" * 50)
    test_mcp_with_details(
        base_url, 
        "POST", 
        data='{"test": "data"}',
        headers={"Content-Type": "application/json"}
    )
    
    # Test 3: POST with partial headers
    print("\n3️⃣ Testing POST with partial headers:")
    print("-" * 50)
    test_mcp_with_details(
        base_url, 
        "POST", 
        data='{"test": "data"}',
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
    )
    
    # Test 4: POST with correct headers (should still fail but differently)
    print("\n4️⃣ Testing POST with correct headers:")
    print("-" * 50)
    test_mcp_with_details(
        base_url, 
        "POST", 
        data=json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {"roots": {"listChanged": False}},
                "clientInfo": {"name": "debug", "version": "1.0.0"}
            }
        }),
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }
    )
    
    print("\n" + "=" * 50)
    print("💡 NEXT STEPS:")
    print("=" * 50)
    print("1. Check container logs: docker logs telegram-toolkit-mcp | tail -20")
    print("2. Look for Python exceptions or stack traces")
    print("3. Check if there are import errors or missing dependencies")
    print("4. Verify FastMCP version compatibility")


if __name__ == "__main__":
    main()
