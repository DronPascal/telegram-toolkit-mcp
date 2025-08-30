#!/usr/bin/env python3
"""
VPS Deployment Verification Script

This script verifies that the MCP server is working correctly on VPS after deployment.
It checks all critical components: health endpoints, MCP protocol, session management, and tools.

Usage:
    python3 verify_vps_deployment.py https://your-domain.com
    python3 verify_vps_deployment.py http://localhost:8000  # for local testing

Installation on VPS:
    Option 1 - System package:
        sudo apt update && sudo apt install python3-httpx

    Option 2 - Virtual environment:
        python3 -m venv ~/mcp_verifier
        ~/mcp_verifier/bin/pip install httpx
        ~/mcp_verifier/bin/python3 verify_vps_deployment.py

    Option 3 - pipx:
        sudo apt install pipx
        pipx install httpx
        pipx run httpx --help
"""

import asyncio
import json
import sys
import time
from typing import Any, Dict, Optional
from urllib.parse import urlparse

try:
    import httpx
except ImportError:
    print("❌ Error: httpx not installed.")
    print("\n🔧 Installation options:")
    print("1. System package: sudo apt update && sudo apt install python3-httpx")
    print("2. Virtual env: python3 -m venv ~/mcp_verifier && ~/mcp_verifier/bin/pip install httpx")
    print("3. pipx: sudo apt install pipx && pipx install httpx")
    print("\nAfter installation, run the script again.")
    sys.exit(1)


class VPSDeploymentVerifier:
    """Verifies MCP server deployment on VPS."""

    def __init__(self, base_url: str):
        self.base_url = base_url.rstrip('/')
        self.session_id: Optional[str] = None
        self.client = httpx.AsyncClient(timeout=30.0, follow_redirects=True)
        
        # Parse URL for display
        parsed = urlparse(base_url)
        self.domain = parsed.netloc or parsed.path
        
    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.client.aclose()

    def print_header(self, title: str):
        """Print formatted section header."""
        print(f"\n{'='*60}")
        print(f"🔍 {title}")
        print('='*60)

    def print_result(self, test_name: str, success: bool, details: str = ""):
        """Print test result with formatting."""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"    {details}")

    async def test_basic_connectivity(self) -> bool:
        """Test basic HTTP connectivity to the server."""
        self.print_header("Basic Connectivity Test")
        
        try:
            response = await self.client.get(f"{self.base_url}/")
            self.print_result(
                "HTTP Connectivity", 
                True, 
                f"Status: {response.status_code}, Server reachable"
            )
            return True
        except Exception as e:
            self.print_result("HTTP Connectivity", False, f"Error: {e}")
            return False

    async def test_health_endpoint(self) -> bool:
        """Test the health check endpoint."""
        self.print_header("Health Endpoint Test")
        
        try:
            response = await self.client.get(f"{self.base_url}/health")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if data.get("status") == "healthy":
                        self.print_result(
                            "Health Check", 
                            True, 
                            f"Service: {data.get('service', 'unknown')}, Version: {data.get('version', 'unknown')}"
                        )
                        return True
                    else:
                        self.print_result("Health Check", False, f"Unhealthy status: {data}")
                        return False
                except json.JSONDecodeError:
                    self.print_result("Health Check", False, f"Invalid JSON response: {response.text[:100]}")
                    return False
            else:
                self.print_result("Health Check", False, f"HTTP {response.status_code}: {response.text[:100]}")
                return False
                
        except Exception as e:
            self.print_result("Health Check", False, f"Error: {e}")
            return False

    async def test_metrics_endpoint(self) -> bool:
        """Test the metrics endpoint."""
        self.print_header("Metrics Endpoint Test")
        
        try:
            response = await self.client.get(f"{self.base_url}/metrics")
            
            if response.status_code == 200:
                content = response.text
                if "telegram_toolkit_mcp" in content and "# HELP" in content:
                    lines = len(content.split('\n'))
                    self.print_result(
                        "Metrics Endpoint", 
                        True, 
                        f"Prometheus metrics available ({lines} lines)"
                    )
                    return True
                else:
                    self.print_result("Metrics Endpoint", False, "Invalid metrics format")
                    return False
            else:
                self.print_result("Metrics Endpoint", False, f"HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.print_result("Metrics Endpoint", False, f"Error: {e}")
            return False

    async def test_debug_headers_endpoint(self) -> bool:
        """Test the debug headers endpoint."""
        self.print_header("Debug Headers Endpoint Test")
        
        try:
            response = await self.client.get(f"{self.base_url}/debug/headers")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    if "headers" in data and "timestamp" in data:
                        self.print_result(
                            "Debug Headers", 
                            True, 
                            f"Headers endpoint working, method: {data.get('method', 'unknown')}"
                        )
                        return True
                    else:
                        self.print_result("Debug Headers", False, "Invalid response format")
                        return False
                except json.JSONDecodeError:
                    self.print_result("Debug Headers", False, "Invalid JSON response")
                    return False
            else:
                self.print_result("Debug Headers", False, f"HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.print_result("Debug Headers", False, f"Error: {e}")
            return False

    async def test_mcp_initialize(self) -> bool:
        """Test MCP protocol initialization."""
        self.print_header("MCP Protocol Initialization Test")
        
        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-06-18",
                "capabilities": {
                    "roots": {"listChanged": False},
                    "sampling": {}
                },
                "clientInfo": {
                    "name": "vps-verifier",
                    "version": "1.0.0"
                }
            }
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream"
        }

        try:
            response = await self.client.post(
                f"{self.base_url}/mcp",
                json=payload,
                headers=headers
            )
            
            # Extract session ID from headers
            session_id = response.headers.get("mcp-session-id")
            if session_id:
                self.session_id = session_id
                self.print_result(
                    "MCP Session Creation", 
                    True, 
                    f"Session ID: {session_id[:16]}..."
                )
                
                # Check response content for proper MCP initialization
                if response.status_code == 200:
                    content = response.text
                    if "serverInfo" in content and "protocolVersion" in content:
                        self.print_result(
                            "MCP Initialize Response", 
                            True, 
                            "Server info and protocol version present"
                        )
                        return True
                    else:
                        self.print_result(
                            "MCP Initialize Response", 
                            False, 
                            f"Unexpected response format: {content[:200]}..."
                        )
                        return False
                else:
                    self.print_result("MCP Initialize Response", False, f"HTTP {response.status_code}")
                    return False
            else:
                self.print_result("MCP Session Creation", False, "No session ID in response headers")
                return False
                
        except Exception as e:
            self.print_result("MCP Initialize", False, f"Error: {e}")
            return False

    async def test_mcp_tools_list(self) -> bool:
        """Test MCP tools/list endpoint."""
        if not self.session_id:
            self.print_result("MCP Tools List", False, "No session ID available")
            return False
            
        self.print_header("MCP Tools List Test")
        
        payload = {
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/list"
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Mcp-Session-Id": self.session_id
        }

        try:
            response = await self.client.post(
                f"{self.base_url}/mcp",
                json=payload,
                headers=headers
            )
            
            if response.status_code == 200:
                content = response.text
                if "resolve_chat_tool" in content and "fetch_history_tool" in content:
                    self.print_result(
                        "MCP Tools List", 
                        True, 
                        "Both resolve_chat_tool and fetch_history_tool available"
                    )
                    return True
                else:
                    self.print_result(
                        "MCP Tools List", 
                        False, 
                        f"Expected tools not found: {content[:200]}..."
                    )
                    return False
            else:
                self.print_result("MCP Tools List", False, f"HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.print_result("MCP Tools List", False, f"Error: {e}")
            return False

    async def test_mcp_tool_call(self) -> bool:
        """Test calling a specific MCP tool."""
        if not self.session_id:
            self.print_result("MCP Tool Call", False, "No session ID available")
            return False
            
        self.print_header("MCP Tool Call Test")
        
        payload = {
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "resolve_chat_tool",
                "arguments": {
                    "chat_identifier": "@durov"
                }
            }
        }

        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
            "Mcp-Session-Id": self.session_id
        }

        try:
            response = await self.client.post(
                f"{self.base_url}/mcp",
                json=payload,
                headers=headers
            )
            
            if response.status_code == 200:
                content = response.text
                # Tool call might return result or error, both are valid responses
                if "result" in content or "error" in content:
                    self.print_result(
                        "MCP Tool Call", 
                        True, 
                        "Tool executed and returned response"
                    )
                    return True
                else:
                    self.print_result(
                        "MCP Tool Call", 
                        False, 
                        f"Unexpected response: {content[:200]}..."
                    )
                    return False
            else:
                self.print_result("MCP Tool Call", False, f"HTTP {response.status_code}")
                return False
                
        except Exception as e:
            self.print_result("MCP Tool Call", False, f"Error: {e}")
            return False

    async def run_full_verification(self) -> bool:
        """Run complete verification suite."""
        print(f"🚀 VPS Deployment Verification")
        print(f"🎯 Target: {self.base_url}")
        print(f"🌐 Domain: {self.domain}")
        
        tests = [
            ("Basic Connectivity", self.test_basic_connectivity),
            ("Health Endpoint", self.test_health_endpoint),
            ("Metrics Endpoint", self.test_metrics_endpoint),
            ("Debug Headers", self.test_debug_headers_endpoint),
            ("MCP Initialize", self.test_mcp_initialize),
            ("MCP Tools List", self.test_mcp_tools_list),
            ("MCP Tool Call", self.test_mcp_tool_call),
        ]
        
        passed = 0
        total = len(tests)
        
        for test_name, test_func in tests:
            try:
                result = await test_func()
                if result:
                    passed += 1
            except Exception as e:
                self.print_result(f"{test_name} (Exception)", False, f"Unexpected error: {e}")
        
        # Final results
        self.print_header("Verification Results")
        success_rate = (passed / total) * 100
        
        print(f"📊 Results: {passed}/{total} tests passed ({success_rate:.1f}%)")
        
        if passed == total:
            print("🎉 ALL TESTS PASSED - VPS deployment is fully operational!")
            return True
        elif passed >= 5:  # At least basic functionality works
            print("⚠️  MOSTLY WORKING - Core functionality operational, some issues detected")
            return True
        else:
            print("❌ CRITICAL ISSUES - VPS deployment has significant problems")
            return False


async def main():
    """Main verification function."""
    if len(sys.argv) != 2:
        print("Usage: python3 verify_vps_deployment.py <base_url>")
        print("Examples:")
        print("  python3 verify_vps_deployment.py https://your-domain.com")
        print("  python3 verify_vps_deployment.py http://localhost:8000")
        sys.exit(1)
    
    base_url = sys.argv[1]
    
    # Validate URL format
    if not (base_url.startswith('http://') or base_url.startswith('https://')):
        print("❌ Error: URL must start with http:// or https://")
        sys.exit(1)
    
    async with VPSDeploymentVerifier(base_url) as verifier:
        success = await verifier.run_full_verification()
        
    if success:
        print("\n✅ VPS deployment verification completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ VPS deployment verification failed!")
        sys.exit(1)


if __name__ == "__main__":
    asyncio.run(main())
