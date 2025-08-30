# VPS Deployment Validation Scripts

This directory contains scripts for validating MCP server deployment on VPS.

## Scripts

### `verify_vps_deployment.py`

Comprehensive verification script that tests all aspects of the MCP server deployment.

#### Features

- ✅ **Basic Connectivity** - HTTP connection to server
- ✅ **Health Endpoint** - `/health` endpoint validation
- ✅ **Metrics Endpoint** - `/metrics` Prometheus metrics
- ✅ **Debug Headers** - `/debug/headers` endpoint
- ✅ **MCP Protocol** - Full MCP initialization flow
- ✅ **Session Management** - MCP session creation and persistence
- ✅ **Tools Validation** - MCP tools listing and execution

#### Usage

```bash
# Test production deployment
python3 verify_vps_deployment.py https://your-domain.com

# Test local deployment
python3 verify_vps_deployment.py http://localhost:8000
```

#### Requirements

```bash
pip install httpx
```

#### Example Output

```
🚀 VPS Deployment Verification
🎯 Target: https://your-domain.com
🌐 Domain: your-domain.com

============================================================
🔍 Basic Connectivity Test
============================================================
✅ PASS HTTP Connectivity
    Status: 200, Server reachable

============================================================
🔍 Health Endpoint Test
============================================================
✅ PASS Health Check
    Service: telegram-toolkit-mcp, Version: 1.0.0

============================================================
🔍 MCP Protocol Initialization Test
============================================================
✅ PASS MCP Session Creation
    Session ID: 6f3b0a585b5c40ce...
✅ PASS MCP Initialize Response
    Server info and protocol version present

============================================================
🔍 Verification Results
============================================================
📊 Results: 7/7 tests passed (100.0%)
🎉 ALL TESTS PASSED - VPS deployment is fully operational!
```

## Deployment Process

### 1. Deploy Server Fixes to VPS

```bash
# Connect to VPS
ssh user@your-vps

# Navigate to project directory
cd /opt/telegram-toolkit-mcp

# Pull latest changes with fixes
git pull origin main

# Rebuild container with fixes
docker-compose down
docker-compose build --no-cache
docker-compose up -d

# Check container status
docker-compose ps
docker logs telegram-toolkit-mcp
```

### 2. Verify Deployment

```bash
# Download verification script to VPS
curl -O https://raw.githubusercontent.com/your-repo/telegram-toolkit-mcp/main/scripts/validation/verify_vps_deployment.py

# Install dependencies
pip3 install httpx

# Run verification
python3 verify_vps_deployment.py https://your-domain.com
```

### 3. Local Testing (Alternative)

```bash
# From your local machine, test the VPS deployment
cd /path/to/telegram-toolkit-mcp
python3 scripts/validation/verify_vps_deployment.py https://your-domain.com
```

## Troubleshooting

### Common Issues

1. **Connection Refused**
   - Check if Docker container is running: `docker-compose ps`
   - Check container logs: `docker logs telegram-toolkit-mcp`
   - Verify firewall settings

2. **SSL Certificate Issues**
   - Check certificate status: `certbot certificates`
   - Renew if needed: `certbot renew`

3. **MCP Protocol Errors**
   - Check server logs for TypeError issues
   - Verify FastMCP fixes are applied
   - Ensure container was rebuilt with latest code

4. **Session Creation Failures**
   - This indicates the critical FastMCP fixes are needed
   - Rebuild container with latest code
   - Check for TypeError in docker logs

### Success Criteria

- ✅ All 7 tests should pass for full operational status
- ✅ At least 5 tests passing indicates core functionality works
- ❌ Less than 5 tests passing indicates critical issues

### Next Steps After Successful Verification

1. **MCP Client Integration** - Connect Claude Desktop or other MCP clients
2. **Performance Monitoring** - Monitor server performance and resource usage
3. **Production Usage** - Begin using the server for actual Telegram data extraction
4. **Scaling Considerations** - Monitor load and scale if needed
