# 🚀 VPS Deployment Quick Guide

## Step 1: Deploy Server Fixes

```bash
# Connect to your VPS
ssh user@your-vps

# Navigate to project directory
cd /opt/telegram-toolkit-mcp

# Pull latest changes with critical fixes
git pull origin main

# Rebuild and restart with fixes
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```

## Step 2: Verify Deployment

### Option 1: Simple Check (No Dependencies Required)

```bash
# Download and run simple verification script
python3 scripts/validation/simple_vps_check.py https://your-domain.com
```

### Option 2: Full Verification (Requires httpx)

```bash
# Install dependencies (choose one option):

# Option A: System package (recommended)
sudo apt update && sudo apt install python3-httpx

# Option B: Virtual environment
python3 -m venv ~/mcp_verifier
~/mcp_verifier/bin/pip install httpx
alias python3="~/mcp_verifier/bin/python3"

# Option C: pipx (if available)
sudo apt install pipx && pipx install httpx

# Run full verification
python3 scripts/validation/verify_vps_deployment.py https://your-domain.com
```

## Expected Output

```
🚀 VPS Deployment Verification
🎯 Target: https://your-domain.com

✅ PASS HTTP Connectivity
✅ PASS Health Check
✅ PASS Metrics Endpoint
✅ PASS Debug Headers
✅ PASS MCP Session Creation
✅ PASS MCP Initialize Response
✅ PASS MCP Tools List
✅ PASS MCP Tool Call

📊 Results: 7/7 tests passed (100.0%)
🎉 ALL TESTS PASSED - VPS deployment is fully operational!
```

## What Was Fixed

- ✅ **FastMCP TypeError Issues** - Server no longer crashes during session creation
- ✅ **Session Stability** - MCP sessions create and persist properly
- ✅ **Protocol Compliance** - Full MCP 2025-06-18 protocol support
- ✅ **Production Ready** - Server runs stably in Docker container

## Troubleshooting

If verification fails:

1. **Check container status:**
   ```bash
   docker-compose ps
   docker logs telegram-toolkit-mcp
   ```

2. **Look for TypeError in logs** - indicates fixes weren't applied
3. **Rebuild container** if needed:
   ```bash
   docker-compose build --no-cache
   docker-compose up -d
   ```

## Next Steps

After successful verification:
- Connect MCP clients (Claude Desktop, etc.)
- Monitor server performance
- Begin production usage
