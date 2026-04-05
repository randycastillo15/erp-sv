#!/usr/bin/env bash
# smoke_fe.sh — emite una FE (tipo 01) mínima y verifica generation_code + estado
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"
require_jq

echo "=== SMOKE: emit FE (tipo 01) ==="

IDEM_KEY="smoke:fe:$(date +%s)"
TODAY=$(date +%Y-%m-%d)

PAYLOAD=$(cat <<EOF
{
  "tipo_dte": "01",
  "ambiente": "$AMBIENTE",
  "docname": "SMOKE-FE-$(date +%s)",
  "company": "Full House",
  "posting_date": "$TODAY",
  "currency": "USD",
  "receptor": {
    "nombre": "Consumidor Final"
  },
  "items": [
    {
      "num_item": 1,
      "tipo_item": 2,
      "descripcion": "Servicio de prueba smoke",
      "cantidad": "1",
      "precio_unitario": "10.00",
      "venta_gravada": "10.00"
    }
  ],
  "grand_total": "11.30",
  "total_iva": "1.30",
  "condicion_operacion": 1,
  "emisor": {
    "nit": "$NIT_EMISOR",
    "nrc": "$NRC_EMISOR",
    "nombre": "EDWIN EDUARDO PALMA ESCOBAR",
    "cod_actividad": "$COD_ACTIVIDAD",
    "desc_actividad": "$DESC_ACTIVIDAD",
    "tipo_establecimiento": "02",
    "cod_estable_mh": "M001",
    "cod_punto_venta_mh": "P001",
    "departamento": "05",
    "municipio": "25",
    "complemento": "Calle Prueba #1",
    "telefono": "22223333",
    "correo": "prueba@empresa.com",
    "url_firmador": "$URL_FIRMADOR",
    "nit_firmador": "$NIT_FIRMADOR"
  },
  "idempotency_key": "$IDEM_KEY"
}
EOF
)

RESP=$(curl -sf -X POST "$BASE_URL/v2/dte/emit" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")
echo "$RESP" | jq .

assert_key_present "$RESP" "generation_code"
assert_key_present "$RESP" "estado"

GEN_CODE=$(echo "$RESP" | jq -r '.generation_code')
ESTADO=$(echo "$RESP" | jq -r '.estado')

pass "FE emitida — generation_code=$GEN_CODE estado=$ESTADO"
echo "export GEN_CODE_FE=$GEN_CODE"
