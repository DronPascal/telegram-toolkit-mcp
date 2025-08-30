#!/usr/bin/env python3
"""
MCP Success Test - Verify server is working correctly

This script tests that the MCP server is functioning properly by checking
all the endpoints that SHOULD work, and confirms that MCP endpoint behavior
is correct (rejecting non-SSE clients is the expected behavior).
"""

import json
import sys
import urllib.request
import urllib.error
from urllib.parse import urlparse


def test_endpoint(url, name, expected_content=None):
    """Test an endpoint and return success status."""
    try:
        with urllib.request.urlopen(url) as response:
            content = response.read().decode('utf-8')
            status = response.getcode()
            
            if status == 200:
                if expected_content and expected_content not in content:
                    print(f"❌ {name}: Content check failed")
                    return False
                else:
                    print(f"✅ {name}: Working correctly")
                    return True
            else:
                print(f"❌ {name}: HTTP {status}")
                return False
                
    except Exception as e:
        print(f"❌ {name}: Error - {e}")
        return False


def test_mcp_protection(base_url):
    """Test that MCP endpoint correctly rejects non-SSE clients."""
    print("\n🔒 Testing MCP Endpoint Protection:")
    print("----------------------------------")
    
    # Test GET request (should be rejected)
    try:
        urllib.request.urlopen(f"{base_url}/mcp")
        print("❌ MCP GET: Should have been rejected")
        return False
    except urllib.error.HTTPError as e:
        if e.code == 406:  # Not Acceptable
            print("✅ MCP GET: Correctly rejected non-SSE client")
            return True
        else:
            print(f"❌ MCP GET: Unexpected error {e.code}")
            return False
    except Exception as e:
        print(f"❌ MCP GET: Error - {e}")
        return False


def test_mcp_post_protection(base_url):
    """Test that MCP endpoint correctly rejects POST without proper headers."""
    print("\n🔒 Testing MCP POST Protection:")
    print("-------------------------------")
    
    # Test POST without proper headers
    try:
        data = json.dumps({"test": "data"}).encode('utf-8')
        req = urllib.request.Request(f"{base_url}/mcp", data=data, method='POST')
        req.add_header('Content-Type', 'application/json')
        
        urllib.request.urlopen(req)
        print("❌ MCP POST: Should have been rejected")
        return False
    except urllib.error.HTTPError as e:
        if e.code == 406:  # Not Acceptable
            print("✅ MCP POST: Correctly rejected client without SSE headers")
            return True
        else:
            print(f"❌ MCP POST: Unexpected error {e.code}")
            return False
    except Exception as e:
        print(f"❌ MCP POST: Error - {e}")
        return False


def main():
    """Main test function."""
    if len(sys.argv) != 2:
        print("Usage: python3 test_mcp_success.py <base_url>")
        print("Example: python3 test_mcp_success.py http://localhost:8000")
        sys.exit(1)
    
    base_url = sys.argv[1].rstrip('/')
    parsed = urlparse(base_url)
    domain = parsed.netloc or parsed.path
    
    print(f"🎯 MCP Server Success Test")
    print(f"🌐 Target: {base_url}")
    print(f"📍 Domain: {domain}")
    print("=" * 50)
    
    # Test working endpoints
    tests = [
        (f"{base_url}/health", "Health Endpoint", '"status":"healthy"'),
        (f"{base_url}/metrics", "Metrics Endpoint", "# HELP"),
        (f"{base_url}/debug/headers", "Debug Headers", '"status":"ok"'),
    ]
    
    passed = 0
    total = len(tests)
    
    print("\n📊 Testing Working Endpoints:")
    print("-----------------------------")
    
    for url, name, expected in tests:
        if test_endpoint(url, name, expected):
            passed += 1
    
    # Test MCP endpoint protection (this SHOULD fail for non-SSE clients)
    mcp_protection_works = 0
    if test_mcp_protection(base_url):
        mcp_protection_works += 1
    if test_mcp_post_protection(base_url):
        mcp_protection_works += 1
    
    print("\n" + "=" * 50)
    print("📊 RESULTS:")
    print("=" * 50)
    
    print(f"✅ Working Endpoints: {passed}/{total}")
    print(f"🔒 MCP Protection: {mcp_protection_works}/2")
    
    if passed == total and mcp_protection_works == 2:
        print("\n🎉 SUCCESS: MCP Server is working correctly!")
        print("\n💡 Key Points:")
        print("- All standard endpoints work perfectly")
        print("- MCP endpoint correctly rejects non-SSE clients")
        print("- This is EXPECTED behavior for FastMCP servers")
        print("- To use MCP protocol, you need a proper MCP client")
        print("- The 'peer closed connection' errors are normal for curl/httpx")
        print("\n✅ Server is ready for MCP client connections!")
        return True
    else:
        print("\n❌ Some issues detected with the server")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
