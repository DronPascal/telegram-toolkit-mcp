#!/bin/bash
# VPS Diagnostic Script - Quick server status check

echo "🔍 VPS Diagnostic Report"
echo "========================"

echo ""
echo "1️⃣ Git Status & Recent Commits:"
echo "--------------------------------"
git log --oneline -5

echo ""
echo "2️⃣ Docker Container Status:"
echo "----------------------------"
docker-compose ps

echo ""
echo "3️⃣ Container Logs (last 20 lines):"
echo "-----------------------------------"
docker logs --tail 20 telegram-toolkit-mcp

echo ""
echo "4️⃣ Local Health Check:"
echo "----------------------"
echo "Testing http://localhost:8000/health"
curl -s http://localhost:8000/health || echo "❌ Local health check failed"

echo ""
echo ""
echo "5️⃣ Local Metrics Check:"
echo "-----------------------"
echo "Testing http://localhost:8000/metrics"
curl -s http://localhost:8000/metrics | head -5 || echo "❌ Local metrics check failed"

echo ""
echo ""
echo "6️⃣ MCP Endpoint Check:"
echo "----------------------"
echo "Testing http://localhost:8000/mcp"
curl -I http://localhost:8000/mcp 2>/dev/null | head -5 || echo "❌ MCP endpoint check failed"

echo ""
echo ""
echo "7️⃣ Nginx Status (if applicable):"
echo "--------------------------------"
if command -v nginx >/dev/null 2>&1; then
    sudo nginx -t 2>/dev/null && echo "✅ Nginx config OK" || echo "❌ Nginx config error"
    systemctl is-active nginx 2>/dev/null && echo "✅ Nginx is running" || echo "❌ Nginx not running"
else
    echo "ℹ️  Nginx not installed or not in PATH"
fi

echo ""
echo "8️⃣ Port Status:"
echo "---------------"
echo "Checking if port 8000 is listening:"
netstat -tlnp | grep :8000 || echo "❌ Port 8000 not listening"

echo ""
echo "🎯 DIAGNOSTIC COMPLETE"
echo "======================"
echo ""
echo "💡 Next steps based on results:"
echo "- If containers not running: docker-compose up -d"
echo "- If health check fails: check container logs"
echo "- If git commits missing: git pull origin main"
echo "- If port not listening: check container binding"
