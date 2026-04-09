#!/usr/bin/env bash
# smoke_nd.sh — emite una ND (tipo 06) vinculada a un CCF
# Requiere: CCF_GEN_CODE (generation_code del CCF al que se aplica el débito)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"
require_jq

if [[ -z "${CCF_GEN_CODE:-}" ]]; then
    fail "Requiere env var CCF_GEN_CODE (generation_code del CCF relacionado)"
fi

echo "=== SMOKE: emit ND (tipo 06) ==="

URL_FIRMADOR="${DTE_FIRMADOR_URL:-http://host.docker.internal:8113/firmardocumento/}"
RECEPTOR_NIT="${CCF_RECEPTOR_NIT:-040010231}"
RECEPTOR_NRC="${CCF_RECEPTOR_NRC:-3074618}"
IDEM_KEY="smoke:nd:$(date +%s)"
TODAY=$(date +%Y-%m-%d)

PAYLOAD=$(cat <<EOF
{
  "tipo_dte": "06",
  "ambiente": "$AMBIENTE",
  "docname": "SMOKE-ND-$(date +%s)",
  "company": "EMPRESA PRUEBA SA DE CV",
  "posting_date": "$TODAY",
  "currency": "USD",
  "receptor": {
    "nombre": "RECEPTOR PRUEBA SA DE CV",
    "nit": "$RECEPTOR_NIT",
    "nrc": "$RECEPTOR_NRC",
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
  "documento_relacionado_codigo": "$CCF_GEN_CODE",
  "documento_relacionado_tipo": "03",
  "documento_relacionado_fecha": "$TODAY",
  "items": [
    {
      "num_item": 1,
      "tipo_item": 1,
      "descripcion": "Cargo adicional CCF smoke",
      "cantidad": "1",
      "precio_unitario": "15.00",
      "venta_gravada": "15.00",
      "tributos": ["20"]
    }
  ],
  "grand_total": "16.95",
  "total_iva": "1.95",
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
    "municipio": "14",
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
assert_key_starts_with "$RESP" "control_number" "DTE-06-"

GEN_CODE=$(echo "$RESP" | jq -r '.generation_code')
CTRL=$(echo "$RESP" | jq -r '.control_number')
ESTADO=$(echo "$RESP" | jq -r '.estado')

pass "ND emitida — generation_code=$GEN_CODE control_number=$CTRL estado=$ESTADO"
echo "export GEN_CODE_ND=$GEN_CODE"
