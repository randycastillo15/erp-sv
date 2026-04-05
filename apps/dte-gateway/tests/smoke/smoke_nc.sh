#!/usr/bin/env bash
# smoke_nc.sh — emite una NC (tipo 05) vinculada a un CCF
# Requiere: CCF_GEN_CODE (generation_code del CCF a acreditar)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"
require_jq

if [[ -z "${CCF_GEN_CODE:-}" ]]; then
    fail "Requiere env var CCF_GEN_CODE (generation_code del CCF a acreditar)"
fi

echo "=== SMOKE: emit NC (tipo 05) ==="

URL_FIRMADOR="${DTE_FIRMADOR_URL:-http://host.docker.internal:8113/firmardocumento/}"
RECEPTOR_NIT="${CCF_RECEPTOR_NIT:-040010231}"
IDEM_KEY="smoke:nc:$(date +%s)"
TODAY=$(date +%Y-%m-%d)

PAYLOAD=$(cat <<EOF
{
  "tipo_dte": "05",
  "ambiente": "$AMBIENTE",
  "docname": "SMOKE-NC-$(date +%s)",
  "company": "EMPRESA PRUEBA SA DE CV",
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
      "municipio": "23",
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
      "descripcion": "Devolucion parcial CCF smoke",
      "cantidad": "1",
      "precio_unitario": "20.00",
      "venta_gravada": "20.00",
      "tributos": ["20"]
    }
  ],
  "grand_total": "22.60",
  "total_iva": "2.60",
  "condicion_operacion": 1,
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
assert_key_starts_with "$RESP" "control_number" "DTE-05-"

GEN_CODE=$(echo "$RESP" | jq -r '.generation_code')
CTRL=$(echo "$RESP" | jq -r '.control_number')
ESTADO=$(echo "$RESP" | jq -r '.estado')

pass "NC emitida — generation_code=$GEN_CODE control_number=$CTRL estado=$ESTADO"
echo "export GEN_CODE_NC=$GEN_CODE"
