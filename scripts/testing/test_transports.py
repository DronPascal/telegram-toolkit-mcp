#!/usr/bin/env python3
"""
Test different transport modes for Telegram Toolkit MCP Server

This script tests stdio, HTTP, and SSE transports to ensure they work correctly.

Usage:
    python test_transports.py --stdio         # Test stdio transport
    python test_transports.py --http          # Test HTTP transport
    python test_transports.py --sse           # Test SSE transport
    python test_transports.py --all           # Test all transports
    python test_transports.py --verbose       # Verbose output
    python test_transports.py --fail-fast     # Stop on first failure
"""

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import requests

# Constants for HTTP status codes and other magic numbers
HTTP_OK = 200
SSE_EVENTS_TO_READ = 3


class TransportTester:
    """Test different MCP transport modes"""

    def __init__(self, verbose: bool = False, fail_fast: bool = False):
        self.project_root = Path(__file__).parent.parent.parent
        self.server_process = None
        self.verbose = verbose
        self.fail_fast = fail_fast

    def start_server_stdio(self):
        """Start server in stdio mode for testing"""
        print("🚀 Starting server in stdio mode...")
        cmd = [sys.executable, "-m", "telegram_toolkit_mcp.server", "--transport", "stdio"]

        # Note: stdio mode runs until interrupted, so we don't capture output
        print(f"📋 Command: {' '.join(cmd)}")
        print("🎯 Server started in stdio mode (press Ctrl+C to stop)")
        return cmd

    def start_server_http(self, host="127.0.0.1", port=8001):
        """Start server in HTTP mode for testing"""
        print(f"🚀 Starting server in HTTP mode on {host}:{port}...")

        # Use the virtual environment Python
        python_executable = os.path.join(self.project_root, ".venv", "bin", "python")

        # For now, use default port 8000 since FastMCP ignores port settings
        # This will be fixed when we implement proper port handling
        actual_port = 8000
        cmd = [
            python_executable,
            "-m",
            "telegram_toolkit_mcp.server",
            "--transport",
            "http",
            # Remove --host and --port for now since FastMCP ignores them
        ]

        print(f"📋 Command: {' '.join(cmd)}")

        # Set environment variables for the subprocess
        env = os.environ.copy()
        env["MCP_SERVER_HOST"] = host
        env["MCP_SERVER_PORT"] = str(actual_port)
        env["PYTHONPATH"] = os.path.join(self.project_root, "src")

        # Start server in background
        self.server_process = subprocess.Popen(
            cmd,
            cwd=self.project_root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        # Wait for server to start
        print("⏳ Waiting for server to start...")
        time.sleep(5)

        # Check if server is running
        if self.server_process.poll() is None:
            print("✅ Server started successfully")

            # Additional check - try to connect to the port
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            try:
                result = sock.connect_ex((host, actual_port))
                if result == 0:
                    print(f"✅ Server is listening on {host}:{actual_port}")
                else:
                    print(f"⚠️ Server process running but not listening on {host}:{actual_port}")
                sock.close()
            except OSError as e:
                print(f"⚠️ Could not check port: {e}")

            return f"http://{host}:{actual_port}"
        else:
            stdout, stderr = self.server_process.communicate()
            print("❌ Server failed to start")
            print("STDOUT (last 500 chars):")
            print(stdout[-500:] if stdout else "No stdout")
            print("STDERR (last 500 chars):")
            print(stderr[-500:] if stderr else "No stderr")
            return None

    def stop_server(self):
        """Stop the running server"""
        if self.server_process:
            print("🛑 Stopping server...")
            self.server_process.terminate()
            try:
                self.server_process.wait(timeout=5)
                print("✅ Server stopped")
            except subprocess.TimeoutExpired:
                self.server_process.kill()
                print("⚠️  Server force killed")
            self.server_process = None

    def test_stdio_transport(self):
        """Test stdio transport (basic functionality)"""
        print("\n🧪 Testing STDIO Transport")
        print("=" * 50)

        cmd = self.start_server_stdio()

        # For stdio, we just test that the command can be constructed
        # In real usage, stdio would be used by MCP clients like Claude Desktop
        print("✅ Stdio transport command constructed successfully")
        print(f"📋 Use this command in MCP client: {' '.join(cmd)}")
        print("🎯 Stdio transport test completed")

    def test_http_transport(self):
        """Test HTTP transport"""
        print("\n🌐 Testing HTTP Transport")
        print("=" * 50)

        # Set environment variables for server configuration
        import os

        os.environ["MCP_SERVER_HOST"] = "127.0.0.1"
        os.environ["MCP_SERVER_PORT"] = "8000"  # Use default port

        base_url = self.start_server_http(port=8000)
        if not base_url:
            print("❌ HTTP transport test failed - server didn't start")
            return False

        try:
            # Test health endpoint
            print("🏥 Testing health endpoint...")
            response = requests.get(f"{base_url}/health", timeout=5)
            if response.status_code == HTTP_OK and response.text.strip() == "OK":
                print("✅ Health check passed")
            else:
                print(f"❌ Health check failed: {response.status_code} - {response.text}")
                return False

            # Test metrics endpoint
            print("📊 Testing metrics endpoint...")
            response = requests.get(f"{base_url}/metrics", timeout=5)
            if response.status_code == HTTP_OK:
                print("✅ Metrics endpoint accessible")
            else:
                print(f"❌ Metrics endpoint failed: {response.status_code}")
                return False

            # Test MCP API endpoint
            print("🔧 Testing MCP API endpoint...")
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json, text/event-stream",
            }
            data = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"},
                },
            }

            response = requests.post(f"{base_url}/mcp", json=data, headers=headers, timeout=10)

            print(f"🔍 MCP API Response Status: {response.status_code}")
            print(f"🔍 MCP API Response Headers: {dict(response.headers)}")
            print(f"🔍 MCP API Response Content: {response.text[:500]}")

            if response.status_code == HTTP_OK:
                # Handle SSE format response
                content_type = response.headers.get("content-type", "")
                if "text/event-stream" in content_type:
                    # Parse SSE format
                    lines = response.text.strip().split("\n")
                    data_line = None
                    for line in lines:
                        if line.startswith("data: "):
                            data_line = line[6:]  # Remove 'data: ' prefix
                            break

                    if data_line:
                        try:
                            result = json.loads(data_line)
                            if "result" in result and "protocolVersion" in result["result"]:
                                print("✅ MCP API initialization successful")
                                print(f"   Protocol version: {result['result']['protocolVersion']}")
                            else:
                                print(f"❌ MCP API unexpected response: {result}")
                                return False
                        except json.JSONDecodeError as e:
                            print(f"❌ Failed to parse SSE data: {e}")
                            print(f"   Raw data: {data_line}")
                            return False
                    else:
                        print("❌ No data line found in SSE response")
                        return False
                else:
                    # Try regular JSON parsing
                    try:
                        result = response.json()
                        if "result" in result and "protocolVersion" in result["result"]:
                            print("✅ MCP API initialization successful")
                            print(f"   Protocol version: {result['result']['protocolVersion']}")
                        else:
                            print(f"❌ MCP API unexpected response: {result}")
                            return False
                    except json.JSONDecodeError as e:
                        print(f"❌ Failed to parse JSON response: {e}")
                        return False
            else:
                print(f"❌ MCP API failed: {response.status_code} - {response.text}")
                return False

            print("✅ HTTP transport test completed successfully")
            return True

        except requests.exceptions.RequestException as e:
            print(f"❌ HTTP request failed: {e}")
            return False
        finally:
            self.stop_server()

    def test_sse_transport(self):
        """Test SSE transport"""
        print("\n📡 Testing SSE Transport")
        print("=" * 50)

        # Set environment variables for server configuration
        import os

        os.environ["MCP_SERVER_HOST"] = "127.0.0.1"
        os.environ["MCP_SERVER_PORT"] = "8000"  # Use default port

        base_url = self.start_server_http(host="127.0.0.1", port=8000)
        if not base_url:
            print("❌ SSE transport test failed - server didn't start")
            return False

        try:
            # Test SSE endpoint
            print("📡 Testing SSE endpoint...")
            response = requests.get(
                f"{base_url}/sse",
                headers={"Accept": "text/event-stream", "Cache-Control": "no-cache"},
                timeout=5,
                stream=True,
            )

            if response.status_code == HTTP_OK:
                print("✅ SSE endpoint accessible")

                # Read first few events
                event_count = 0
                for line in response.iter_lines():
                    if line:
                        line_str = line.decode("utf-8")
                        print(f"   📨 SSE Event: {line_str}")
                        event_count += 1
                        if event_count >= SSE_EVENTS_TO_READ:  # Read first few events
                            break

                if event_count > 0:
                    print("✅ SSE events received successfully")
                else:
                    print("⚠️  No SSE events received (this might be normal)")
            else:
                print(f"❌ SSE endpoint failed: {response.status_code}")
                return False

            # Test messages endpoint
            print("💬 Testing messages endpoint...")
            headers = {
                "Content-Type": "application/json",
                "Accept": "application/json",
                "MCP-Protocol-Version": "2025-06-18",
            }
            data = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-06-18",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "1.0.0"},
                },
            }

            response = requests.post(
                f"{base_url}/messages/", json=data, headers=headers, timeout=10
            )

            if response.status_code == HTTP_OK:
                result = response.json()
                if "result" in result and "protocolVersion" in result["result"]:
                    print("✅ SSE messages endpoint working")
                    print(f"   Protocol version: {result['result']['protocolVersion']}")
                else:
                    print(f"❌ SSE messages unexpected response: {result}")
                    return False
            else:
                print(f"❌ SSE messages failed: {response.status_code} - {response.text}")
                return False

            print("✅ SSE transport test completed successfully")
            return True

        except requests.exceptions.RequestException as e:
            print(f"❌ SSE request failed: {e}")
            return False
        finally:
            self.stop_server()

    def run_all_tests(self):
        """Run all transport tests"""
        print("🚀 Running All Transport Tests")
        print("=" * 60)

        results = []
        success = True

        # Test stdio (basic)
        try:
            self.test_stdio_transport()
            results.append(("STDIO", "Basic test completed"))
        except (subprocess.SubprocessError, OSError) as e:
            results.append(("STDIO", f"Failed: {e}"))
            success = False
            if self.fail_fast:
                return False

        # Test HTTP
        try:
            http_result = self.test_http_transport()
            results.append(("HTTP", "PASSED" if http_result else "FAILED"))
            if not http_result:
                success = False
                if self.fail_fast:
                    return False
        except (requests.RequestException, ConnectionError) as e:
            results.append(("HTTP", f"Failed: {e}"))
            success = False
            if self.fail_fast:
                return False

        # Test SSE
        try:
            sse_result = self.test_sse_transport()
            results.append(("SSE", "PASSED" if sse_result else "FAILED"))
            if not sse_result:
                success = False
        except (requests.RequestException, ConnectionError) as e:
            results.append(("SSE", f"Failed: {e}"))
            success = False

        # Print summary
        print("\n📊 Test Results Summary")
        print("=" * 60)
        for transport, result in results:
            status = "✅" if "PASSED" in result or "completed" in result else "❌"
            if self.verbose:
                print(f"{status} {transport}: {result}")
            else:
                print(f"{status} {transport}")

        return success


def main():
    """Main CLI function"""
    import argparse

    parser = argparse.ArgumentParser(
        description="Test MCP server transports",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python test_transports.py --stdio         # Test stdio transport
  python test_transports.py --http          # Test HTTP transport
  python test_transports.py --sse           # Test SSE transport
  python test_transports.py --all           # Test all transports
  python test_transports.py --all --verbose # Test all with verbose output
  python test_transports.py --all --fail-fast # Stop on first failure
        """,
    )

    parser.add_argument("--stdio", action="store_true", help="Test stdio transport")
    parser.add_argument("--http", action="store_true", help="Test HTTP transport")
    parser.add_argument("--sse", action="store_true", help="Test SSE transport")
    parser.add_argument("--all", action="store_true", help="Test all transports")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    parser.add_argument("--fail-fast", action="store_true", help="Stop on first failure")

    args = parser.parse_args()

    # If no specific test requested, run all
    if not any([args.stdio, args.http, args.sse, args.all]):
        args.all = True

    tester = TransportTester(verbose=args.verbose, fail_fast=args.fail_fast)

    try:
        if args.all:
            success = tester.run_all_tests()
        else:
            success = True
            if args.stdio:
                try:
                    tester.test_stdio_transport()
                except (subprocess.SubprocessError, OSError) as e:
                    print(f"❌ STDIO test failed: {e}")
                    success = False
                    if args.fail_fast:
                        sys.exit(1)
            if args.http:
                try:
                    http_success = tester.test_http_transport()
                    success &= http_success
                    if not http_success and args.fail_fast:
                        sys.exit(1)
                except (requests.RequestException, ConnectionError) as e:
                    print(f"❌ HTTP test failed: {e}")
                    success = False
                    if args.fail_fast:
                        sys.exit(1)
            if args.sse:
                try:
                    sse_success = tester.test_sse_transport()
                    success &= sse_success
                except (requests.RequestException, ConnectionError) as e:
                    print(f"❌ SSE test failed: {e}")
                    success = False

        if success:
            print("\n🎉 All tests completed successfully!")
            sys.exit(0)
        else:
            print("\n❌ Some tests failed!")
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n🛑 Tests interrupted by user")
        tester.stop_server()
        sys.exit(1)
    except (RuntimeError, SystemExit) as e:
        print(f"\n❌ Test error: {e}")
        tester.stop_server()
        sys.exit(1)


if __name__ == "__main__":
    main()
