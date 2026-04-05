#!/usr/bin/env bash
# smoke_health.sh — verifica que el gateway está online
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"
require_jq

echo "=== SMOKE: health ==="
RESP=$(curl -sf "$BASE_URL/health")
echo "$RESP" | jq .

STATUS=$(echo "$RESP" | jq -r '.status // empty')
if [[ "$STATUS" != "ok" ]]; then
    fail "Gateway /health no devolvió status=ok. Respuesta: $RESP"
fi

pass "Gateway online en $BASE_URL"
