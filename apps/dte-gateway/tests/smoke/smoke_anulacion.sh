#!/usr/bin/env bash
# smoke_anulacion.sh — anula un DTE PROCESADO
# Requiere: GEN_CODE, SELLO, NUM_CONTROL, FEC_EMI, TIPO_DTE
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$SCRIPT_DIR/common.sh"
require_jq

for VAR in GEN_CODE SELLO NUM_CONTROL FEC_EMI TIPO_DTE; do
    if [[ -z "${!VAR:-}" ]]; then
        fail "Requiere env var $VAR"
    fi
done

RECEPTOR_NIT="${RECEPTOR_NIT:-040010231}"
RECEPTOR_TIPO="${RECEPTOR_TIPO:-36}"
URL_FIRMADOR="${DTE_FIRMADOR_URL:-http://host.docker.internal:8113/firmardocumento/}"

echo "=== SMOKE: anular DTE tipo=$TIPO_DTE gen=$GEN_CODE ==="

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
  "tipo_dte": "$TIPO_DTE",
  "codigo_generacion_original": "$GEN_CODE",
  "sello_recibido": "$SELLO",
  "numero_control": "$NUM_CONTROL",
  "fec_emi": "$FEC_EMI",
  "monto_iva": null,
  "tipo_documento_receptor": "$RECEPTOR_TIPO",
  "num_documento_receptor": "$RECEPTOR_NIT",
  "nombre_receptor": "RECEPTOR PRUEBA SA DE CV",
  "tipo_anulacion": 2,
  "motivo_anulacion": "Prueba smoke anulacion sin reemplazo",
  "codigo_generacion_reemplazo": null,
  "nombre_responsable": "RESPONSABLE PRUEBA",
  "tip_doc_responsable": "13",
  "num_doc_responsable": "061172006",
  "nombre_solicita": "RESPONSABLE PRUEBA",
  "tip_doc_solicita": "13",
  "num_doc_solicita": "061172006",
  "fecha_anula": "$(date +%Y-%m-%d)",
  "idempotency_key": "smoke:anulacion:$GEN_CODE:$(date +%s)"
}
EOF
)

RESP=$(curl -sf -X POST "$BASE_URL/v2/dte/anular" \
    -H "Content-Type: application/json" \
    -d "$PAYLOAD")
echo "$RESP" | jq .

assert_key_present "$RESP" "event_uuid"

EVENT_UUID=$(echo "$RESP" | jq -r '.event_uuid')
ESTADO=$(echo "$RESP" | jq -r '.estado // "N/A"')
SELLO_OUT=$(echo "$RESP" | jq -r '.sello_recibido // "N/A"')

pass "Anulación enviada — event_uuid=$EVENT_UUID estado=$ESTADO sello=$SELLO_OUT"
