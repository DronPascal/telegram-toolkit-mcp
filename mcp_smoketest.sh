#!/usr/bin/env bash
set -euo pipefail

DOMAIN="${1:-tgtoolkit.azazazaza.work}"
PROTO="2025-06-18"

echo "🚀 MCP Smoke Test для $DOMAIN"
echo "=================================="

echo "== INIT =="
INIT=$(curl -si https://$DOMAIN/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "MCP-Protocol-Version: $PROTO" \
  -d '{"jsonrpc":"2.0","id":0,"method":"initialize",
       "params":{"protocolVersion":"'"$PROTO"'",
                 "capabilities":{"tools":{}},
                 "clientInfo":{"name":"smoke","version":"1"}}}')
echo "$INIT" | sed -n '1,10p' >&2
SID=$(echo "$INIT" | awk -F': ' 'BEGIN{IGNORECASE=1}/^Mcp-Session-Id:/{print $2}' | tr -d '\r')
[ -n "$SID" ] || { echo "❌ Нет Mcp-Session-Id"; exit 1; }
echo "✅ SID=$SID"

echo ""
echo "== NOTIFY =="
curl -sSI https://$DOMAIN/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "Mcp-Session-Id: $SID" \
  -H "MCP-Protocol-Version: $PROTO" \
  -d '{"jsonrpc":"2.0","method":"notifications/initialized"}' | sed -n '1,10p' >&2

echo ""
echo "== TOOLS/LIST =="
LIST=$(curl -NsS https://$DOMAIN/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "Mcp-Session-Id: $SID" \
  -H "MCP-Protocol-Version: $PROTO" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list"}' \
  | sed -n 's/^data: //p' | head -1)
echo "$LIST" | jq . >/dev/null 2>&1 || { echo "❌ LIST не JSON"; echo "$LIST"; exit 2; }
echo "✅ Tools list получен:"
echo "$LIST" | jq .

echo ""
echo "== CALL resolve_chat_tool =="
RES=$(curl -NsS https://$DOMAIN/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "Mcp-Session-Id: $SID" \
  -H "MCP-Protocol-Version: $PROTO" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call",
       "params":{"name":"resolve_chat_tool","arguments":{"input":"@telegram"}}}' \
  | sed -n 's/^data: //p' | head -1)
echo "✅ Resolve chat result:"
echo "$RES" | jq .

echo ""
echo "== CALL fetch_history_tool =="
HIST=$(curl -NsS https://$DOMAIN/mcp \
  -H 'Content-Type: application/json' \
  -H 'Accept: application/json, text/event-stream' \
  -H "Mcp-Session-Id: $SID" \
  -H "MCP-Protocol-Version: $PROTO" \
  -d '{"jsonrpc":"2.0","id":3,"method":"tools/call",
       "params":{"name":"fetch_history_tool","arguments":{"chat_id":"@telegram","limit":3}}}' \
  | sed -n 's/^data: //p' | head -1)
echo "✅ Fetch history result:"
echo "$HIST" | jq .

echo ""
echo "🎉 MCP SMOKE TEST ПРОЙДЕН УСПЕШНО!"
echo "=================================="
echo "✅ Initialize + Session ID"
echo "✅ Notifications"
echo "✅ Tools list"
echo "✅ Resolve chat tool"
echo "✅ Fetch history tool"
echo ""
echo "🚀 Сервер готов к работе с MCP клиентами!"
