#!/usr/bin/env python3
"""
Run Telegram Toolkit MCP Server with Podman

This script provides a convenient way to run the MCP server using Podman
with proper networking configuration for local and remote access.

Usage:
    python run_server_podman.py --transport http --host 0.0.0.0
    python run_server_podman.py --transport stdio  # For local MCP clients
    python run_server_podman.py --help
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


class PodmanServerRunner:
    """Podman runner for Telegram Toolkit MCP Server"""

    def __init__(self):
        self.project_root = Path(__file__).parent.parent.parent
        self.container_name = "telegram-toolkit-mcp"

    def check_podman(self) -> bool:
        """Check if Podman is installed and available"""
        try:
            result = subprocess.run(
                ["podman", "--version"], capture_output=True, text=True, check=True
            )
            print(f"✅ Podman available: {result.stdout.strip()}")
            return True
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("❌ Podman not found. Please install Podman first.")
            print("   Ubuntu/Debian: sudo apt install podman")
            print("   macOS: brew install podman")
            print("   Windows: winget install -e --id RedHat.Podman")
            return False

    def check_image(self) -> bool:
        """Check if Docker image exists"""
        try:
            result = subprocess.run(
                ["podman", "images", "telegram-toolkit-mcp:latest"],
                capture_output=True,
                text=True,
                check=True,
            )
            if "telegram-toolkit-mcp" in result.stdout:
                print("✅ Docker image found: telegram-toolkit-mcp:latest")
                return True
            else:
                print("❌ Docker image not found")
                return False
        except subprocess.CalledProcessError:
            print("❌ Error checking Docker images")
            return False

    def build_image(self) -> bool:
        """Build Docker image using Podman"""
        print("🔨 Building Docker image with Podman...")
        try:
            cmd = [
                "podman",
                "build",
                "-t",
                "telegram-toolkit-mcp:latest",
                "-f",
                str(self.project_root / "Dockerfile"),
                str(self.project_root),
            ]

            result = subprocess.run(cmd, cwd=self.project_root, check=False)
            if result.returncode == 0:
                print("✅ Docker image built successfully")
                return True
            else:
                print("❌ Failed to build Docker image")
                return False

        except Exception as e:
            print(f"❌ Error building image: {e}")
            return False

    def get_env_vars(self) -> list[str]:
        """Get environment variables from .env file and system"""
        env_vars = []

        # Load from .env file if exists
        env_file = self.project_root / ".env"
        if env_file.exists():
            try:
                from dotenv import load_dotenv

                load_dotenv(env_file)
                print("✅ Loaded environment from .env file")
            except ImportError:
                print("⚠️  python-dotenv not installed, using system environment")

        # Required variables
        required_vars = [
            "TELEGRAM_API_ID",
            "TELEGRAM_API_HASH",
        ]

        for var in required_vars:
            value = os.getenv(var)
            if value:
                env_vars.append(f"-e{var}={value}")
            else:
                print(f"⚠️  {var} not set - server may not work properly")

        # Optional variables with defaults
        optional_vars = {
            "TELEGRAM_STRING_SESSION": "",
            "MCP_SERVER_HOST": "0.0.0.0",
            "MCP_SERVER_PORT": "8000",
            "LOG_LEVEL": "INFO",
            "DEBUG": "false",
            "ENABLE_PROMETHEUS_METRICS": "true",
            "ENABLE_OPENTELEMETRY_TRACING": "false",
            "FLOOD_SLEEP_THRESHOLD": "60",
            "REQUEST_TIMEOUT": "30",
            "MAX_PAGE_SIZE": "100",
        }

        for var, default in optional_vars.items():
            value = os.getenv(var, default)
            env_vars.append(f"-e{var}={value}")

        return env_vars

    def stop_existing_container(self):
        """Stop and remove existing container if running"""
        try:
            # Check if container exists
            result = subprocess.run(
                ["podman", "ps", "-a", "--filter", f"name={self.container_name}"],
                capture_output=True,
                text=True,
                check=False,
            )

            if self.container_name in result.stdout:
                print(f"🛑 Stopping existing container: {self.container_name}")
                subprocess.run(["podman", "stop", self.container_name], check=False)
                subprocess.run(["podman", "rm", self.container_name], check=False)
                print("✅ Existing container stopped and removed")
        except Exception as e:
            print(f"⚠️  Error stopping existing container: {e}")

    def run_server(
        self, transport: str, host: str = "0.0.0.0", port: int = 8000, detached: bool = False
    ):
        """Run the MCP server with specified transport"""
        print(f"🚀 Starting Telegram Toolkit MCP Server with {transport} transport")

        # Stop existing container
        self.stop_existing_container()

        # Build command
        cmd = [
            "podman",
            "run",
            "--name",
            self.container_name,
            "-p",
            f"0.0.0.0:{port}:{port}",  # Explicitly publish to 0.0.0.0 for external access
            "--network",
            "host",  # Use host network for better connectivity
        ]

        # Add environment variables
        cmd.extend(self.get_env_vars())

        # Add volumes for data persistence
        data_dir = self.project_root / "data"
        logs_dir = self.project_root / "logs"
        data_dir.mkdir(exist_ok=True)
        logs_dir.mkdir(exist_ok=True)

        cmd.extend(
            [
                "-v",
                f"{data_dir}:/app/data:rw,Z",
                "-v",
                f"{logs_dir}:/app/logs:rw,Z",
            ]
        )

        if detached:
            cmd.append("-d")

        # Add image and command
        cmd.extend(
            [
                "telegram-toolkit-mcp:latest",
                "python",
                "-m",
                "telegram_toolkit_mcp.server",
                "--transport",
                transport,
                "--host",
                host,
                "--port",
                str(port),
            ]
        )

        print(f"📋 Running command: {' '.join(cmd)}")
        print(f"🌐 Server will be accessible at: http://{host}:{port}")
        print("📋 Available endpoints:")
        print(f"   • Health: http://{host}:{port}/health")
        print(f"   • Metrics: http://{host}:{port}/metrics")
        print(f"   • MCP API: http://{host}:{port}/mcp")
        print(f"   • SSE: http://{host}:{port}/sse")

        if detached:
            print(
                "🎯 Running in detached mode (use 'podman logs -f telegram-toolkit-mcp' to see logs)"
            )
        else:
            print("🎯 Running in foreground mode (Ctrl+C to stop)")

        # Run the container
        try:
            subprocess.run(cmd, cwd=self.project_root, check=False)
        except KeyboardInterrupt:
            print("\n🛑 Stopping server...")
            self.stop_existing_container()
        except Exception as e:
            print(f"❌ Error running server: {e}")
            return False

        return True

    def show_logs(self):
        """Show container logs"""
        try:
            subprocess.run(["podman", "logs", "-f", self.container_name], check=False)
        except Exception as e:
            print(f"❌ Error showing logs: {e}")

    def show_status(self):
        """Show container status"""
        try:
            result = subprocess.run(
                ["podman", "ps", "-a", "--filter", f"name={self.container_name}"],
                capture_output=True,
                text=True,
                check=False,
            )
            print("📊 Container Status:")
            print(result.stdout)
        except Exception as e:
            print(f"❌ Error getting status: {e}")


def main():
    """Main CLI function"""
    parser = argparse.ArgumentParser(
        description="Run Telegram Toolkit MCP Server with Podman",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Run HTTP server for remote access
  python run_server_podman.py --transport http --host 0.0.0.0 --port 8000

  # Run in detached mode
  python run_server_podman.py --transport http --detached

  # Run stdio server for local MCP clients
  python run_server_podman.py --transport stdio

  # Show container logs
  python run_server_podman.py --logs

  # Show container status
  python run_server_podman.py --status

  # Stop and cleanup
  python run_server_podman.py --cleanup
        """,
    )

    parser.add_argument(
        "--transport",
        choices=["stdio", "http", "sse", "auto"],
        default="http",
        help="Transport mode (default: http)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Server host (default: 0.0.0.0)")
    parser.add_argument("--port", type=int, default=8000, help="Server port (default: 8000)")
    parser.add_argument("--detached", action="store_true", help="Run in detached mode")
    parser.add_argument("--build", action="store_true", help="Force rebuild Docker image")
    parser.add_argument("--logs", action="store_true", help="Show container logs")
    parser.add_argument("--status", action="store_true", help="Show container status")
    parser.add_argument("--cleanup", action="store_true", help="Stop and remove container")

    args = parser.parse_args()

    runner = PodmanServerRunner()

    # Check Podman availability
    if not runner.check_podman():
        sys.exit(1)

    # Handle special commands
    if args.logs:
        runner.show_logs()
        return
    elif args.status:
        runner.show_status()
        return
    elif args.cleanup:
        runner.stop_existing_container()
        print("✅ Container stopped and removed")
        return

    # Check if image exists or needs to be built
    if args.build or not runner.check_image():
        if not runner.build_image():
            sys.exit(1)

    # Run the server
    success = runner.run_server(
        transport=args.transport, host=args.host, port=args.port, detached=args.detached
    )

    if not success:
        sys.exit(1)


if __name__ == "__main__":
    main()
