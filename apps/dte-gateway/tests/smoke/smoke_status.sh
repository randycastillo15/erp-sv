#!/usr/bin/env bash
# smoke_status.sh — consulta el estado de un DTE en el MH
# Requiere: GEN_CODE y TIPO_DTE
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"
require_jq

if [[ -z "${GEN_CODE:-}" ]]; then
    fail "Requiere env var GEN_CODE (generation_code del DTE a consultar)"
fi
if [[ -z "${TIPO_DTE:-}" ]]; then
    fail "Requiere env var TIPO_DTE (ej. '01', '03', '05')"
fi

echo "=== SMOKE: status DTE tipo=$TIPO_DTE gen=$GEN_CODE ==="

PAYLOAD=$(cat <<EOF
{
  "tipo_dte": "$TIPO_DTE",
  "codigo_generacion": "$GEN_CODE",
  "ambiente": "$AMBIENTE",
  "nit_emisor": "$NIT_EMISOR"
}
EOF
)

RESP=$(curl -sf -X POST "$BASE_URL/v2/dte/status" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")
echo "$RESP" | jq .

assert_key_present "$RESP" "estado"

ESTADO=$(echo "$RESP" | jq -r '.estado')
pass "Estado DTE: $ESTADO"
