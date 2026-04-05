#!/usr/bin/env bash
# smoke_contingencia.sh — reporta un evento de contingencia tipo 14
# Requiere: GEN_CODE_1 y GEN_CODE_2 de DTEs ya generados
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"
require_jq

if [[ -z "${GEN_CODE_1:-}" || -z "${GEN_CODE_2:-}" ]]; then
    fail "Requiere env vars GEN_CODE_1 y GEN_CODE_2 (generation_codes de DTEs offline)"
fi

TIPO_DTE_1="${TIPO_DTE_1:-01}"
TIPO_DTE_2="${TIPO_DTE_2:-01}"
URL_FIRMADOR="${DTE_FIRMADOR_URL:-http://host.docker.internal:8113/firmardocumento/}"

echo "=== SMOKE: contingencia tipo 14 con 2 DTEs ==="

TODAY=$(date +%Y-%m-%d)
NOW=$(date +%H:%M:%S)

PAYLOAD=$(cat <<EOF
{
  "ambiente": "$AMBIENTE",
  "emisor": {
    "nit": "$NIT_EMISOR",
    "nrc": "2862402",
    "nombre": "EMPRESA PRUEBA SA DE CV",
    "cod_actividad": "46900",
    "desc_actividad": "Venta al por mayor de otros productos",
    "tipo_establecimiento": "02",
    "cod_estable_mh": "M001",
    "cod_punto_venta_mh": "P001",
    "departamento": "05",
    "municipio": "25",
    "complemento": "Calle Prueba #1",
    "url_firmador": "$URL_FIRMADOR",
    "nit_firmador": "$NIT_FIRMADOR"
  },
  "nombre_responsable": "RESPONSABLE PRUEBA",
  "tipo_doc_responsable": "13",
  "num_doc_responsable": "061172006",
  "tipo_contingencia": 5,
  "motivo_contingencia": "Prueba smoke contingencia",
  "f_inicio": "$TODAY",
  "h_inicio": "00:00:00",
  "f_fin": "$TODAY",
  "h_fin": "$NOW",
  "detalle": [
    {"no_item": 1, "codigo_generacion": "$GEN_CODE_1", "tipo_doc": "$TIPO_DTE_1"},
    {"no_item": 2, "codigo_generacion": "$GEN_CODE_2", "tipo_doc": "$TIPO_DTE_2"}
  ],
  "idempotency_key": "smoke:contingencia:$(date +%s)"
}
EOF
)

RESP=$(curl -sf -X POST "$BASE_URL/v2/contingencia/emit" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")
echo "$RESP" | jq .

assert_key_present "$RESP" "event_uuid"

EVENT_UUID=$(echo "$RESP" | jq -r '.event_uuid')
ESTADO=$(echo "$RESP" | jq -r '.estado // "N/A"')

pass "Contingencia enviada — event_uuid=$EVENT_UUID estado=$ESTADO"
