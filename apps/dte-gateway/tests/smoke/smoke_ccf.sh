#!/usr/bin/env bash
# smoke_ccf.sh — emite un CCF (tipo 03) con receptor NIT y verifica generation_code + control_number
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"
require_jq

echo "=== SMOKE: emit CCF (tipo 03) ==="

RECEPTOR_NIT="${CCF_RECEPTOR_NIT:-040010231}"
IDEM_KEY="smoke:ccf:$(date +%s)"
TODAY=$(date +%Y-%m-%d)

PAYLOAD=$(cat <<EOF
{
  "tipo_dte": "03",
  "ambiente": "$AMBIENTE",
  "docname": "SMOKE-CCF-$(date +%s)",
  "company": "Full House",
  "posting_date": "$TODAY",
  "currency": "USD",
  "receptor": {
    "nombre": "RECEPTOR PRUEBA SA DE CV",
    "nit": "$RECEPTOR_NIT",
    "nrc": "123456",
    "cod_actividad": "46900",
    "desc_actividad": "Comercio",
    "direccion": {
      "departamento": "06",
      "municipio": "01",
      "complemento": "Av. Reforma"
    },
    "telefono": "22224444",
    "correo": "receptor@empresa.com"
  },
  "items": [
    {
      "num_item": 1,
      "tipo_item": 1,
      "descripcion": "Producto CCF smoke",
      "cantidad": "2",
      "precio_unitario": "50.00",
      "venta_gravada": "100.00",
      "tributos": ["20"]
    }
  ],
  "grand_total": "113.00",
  "total_iva": "13.00",
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
assert_key_present "$RESP" "control_number"
assert_key_present "$RESP" "estado"
assert_key_starts_with "$RESP" "control_number" "DTE-03-"

GEN_CODE=$(echo "$RESP" | jq -r '.generation_code')
CTRL=$(echo "$RESP" | jq -r '.control_number')
ESTADO=$(echo "$RESP" | jq -r '.estado')

pass "CCF emitido — generation_code=$GEN_CODE control_number=$CTRL estado=$ESTADO"
echo "export GEN_CODE_CCF=$GEN_CODE"
