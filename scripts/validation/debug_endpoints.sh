#!/bin/bash
# Debug Endpoints - Check what each endpoint returns

echo "🔍 ENDPOINT DEBUGGING"
echo "===================="

echo ""
echo "1️⃣ Health Endpoint:"
echo "-------------------"
curl -s http://localhost:8000/health | jq . 2>/dev/null || curl -s http://localhost:8000/health

echo ""
echo ""
echo "2️⃣ Metrics Endpoint (first 10 lines):"
echo "--------------------------------------"
curl -s http://localhost:8000/metrics | head -10

echo ""
echo ""
echo "3️⃣ Debug Headers Endpoint:"
echo "--------------------------"
curl -s http://localhost:8000/debug/headers | jq . 2>/dev/null || curl -s http://localhost:8000/debug/headers

echo ""
echo ""
echo "4️⃣ MCP Endpoint - GET Request:"
echo "------------------------------"
curl -s http://localhost:8000/mcp

echo ""
echo ""
echo "5️⃣ MCP Endpoint - POST Request (simple):"
echo "----------------------------------------"
curl -X POST http://localhost:8000/mcp \
  -H 'Content-Type: application/json' \
  -d '{"test": "data"}' | head -5

echo ""
echo ""
echo "6️⃣ MCP Endpoint - POST Request (initialize):"
echo "--------------------------------------------"
curl -X POST http://localhost:8000/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
      "protocolVersion": "2025-06-18",
      "capabilities": {
        "roots": {"listChanged": false},
        "sampling": {}
      },
      "clientInfo": {
        "name": "debug-client",
        "version": "1.0.0"
      }
    }
  }' | head -10

echo ""
echo ""
echo "7️⃣ Container Status:"
echo "-------------------"
docker-compose ps

echo ""
echo "8️⃣ Recent Container Logs:"
echo "------------------------"
docker logs --tail 10 telegram-toolkit-mcp

echo ""
echo "🎯 DEBUG COMPLETE"
