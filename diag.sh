#!/bin/bash
echo "=== 1. Servislar holati ==="
sudo systemctl status telegram-mcp-upstream.service oisha-telegram-mcp-gateway.service --no-pager

echo -e "\n=== 2. Portlar tinglayaptimi ==="
ss -ltnp | grep -E '127.0.0.1:(8765|8766)'

echo -e "\n=== 3. Gateway’ga to‘g‘ridan-to‘g‘ri so‘rov ==="
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8766/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"diag","version":"1.0"}}}'

echo -e "\n=== 4. Upstream’ga to‘g‘ridan-to‘g‘ri so‘rov ==="
curl -s -o /dev/null -w "%{http_code}\n" -X POST http://127.0.0.1:8765/mcp \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2024-11-05","capabilities":{},"clientInfo":{"name":"diag","version":"1.0"}}}'

echo -e "\n=== 5. Loglarda 401 qayerdan kelayotganini aniqlash ==="
sudo journalctl -u oisha-telegram-mcp-gateway.service --since "10 minutes ago" | grep -i "401\|Unauthorized\|auth\|token" | tail -20
