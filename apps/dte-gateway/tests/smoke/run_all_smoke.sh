#!/usr/bin/env bash
# run_all_smoke.sh — ejecuta los smoke tests obligatorios y opcionales
#
# Tests obligatorios (sin env vars requeridas):
#   smoke_health.sh
#   smoke_fe.sh
#
# Tests opcionales (requieren env vars):
#   smoke_ccf.sh         — sin env vars adicionales (usa defaults)
#   smoke_status.sh      — requiere: GEN_CODE, TIPO_DTE
#   smoke_anulacion.sh   — requiere: GEN_CODE, SELLO, NUM_CONTROL, FEC_EMI, TIPO_DTE
#   smoke_nc.sh          — requiere: CCF_GEN_CODE, CCF_NUM_CONTROL
#   smoke_contingencia.sh— requiere: GEN_CODE_1, GEN_CODE_2
#
# Uso básico (solo obligatorios):
#   bash run_all_smoke.sh
#
# Uso completo:
#   GEN_CODE=xxx SELLO=yyy NUM_CONTROL=zzz FEC_EMI=2026-01-01 TIPO_DTE=01 \
#   bash run_all_smoke.sh

set -uo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PASS_COUNT=0
FAIL_COUNT=0
SKIP_COUNT=0

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

run_smoke() {
    local name="$1"
    local script="$SCRIPT_DIR/$1.sh"
    echo ""
    echo "------------------------------------------------------------"
    if bash "$script"; then
        PASS_COUNT=$((PASS_COUNT + 1))
    else
        FAIL_COUNT=$((FAIL_COUNT + 1))
        echo -e "${RED}FAILED${NC}: $name"
    fi
}

skip_smoke() {
    local name="$1"
    local reason="$2"
    echo -e "${YELLOW}SKIP${NC}: $name — $reason"
    SKIP_COUNT=$((SKIP_COUNT + 1))
}

# ---- Obligatorios ----
run_smoke "smoke_health"
run_smoke "smoke_fe"

# ---- Opcionales ----
if [[ -n "${CCF_GEN_CODE:-}" && -n "${CCF_NUM_CONTROL:-}" ]]; then
    run_smoke "smoke_nc"
else
    skip_smoke "smoke_nc" "requiere CCF_GEN_CODE y CCF_NUM_CONTROL"
fi

if [[ -n "${CCF_GEN_CODE:-}" ]]; then
    run_smoke "smoke_nd"
else
    skip_smoke "smoke_nd" "requiere CCF_GEN_CODE"
fi

if [[ -n "${GEN_CODE:-}" && -n "${TIPO_DTE:-}" ]]; then
    run_smoke "smoke_status"
else
    skip_smoke "smoke_status" "requiere GEN_CODE y TIPO_DTE"
fi

if [[ -n "${GEN_CODE:-}" && -n "${SELLO:-}" && -n "${NUM_CONTROL:-}" && -n "${FEC_EMI:-}" && -n "${TIPO_DTE:-}" ]]; then
    run_smoke "smoke_anulacion"
else
    skip_smoke "smoke_anulacion" "requiere GEN_CODE, SELLO, NUM_CONTROL, FEC_EMI, TIPO_DTE"
fi

if [[ -n "${GEN_CODE_1:-}" && -n "${GEN_CODE_2:-}" ]]; then
    run_smoke "smoke_contingencia"
else
    skip_smoke "smoke_contingencia" "requiere GEN_CODE_1 y GEN_CODE_2"
fi

echo ""
echo "============================================================"
echo -e "Resultados: ${GREEN}$PASS_COUNT PASS${NC} | ${RED}$FAIL_COUNT FAIL${NC} | ${YELLOW}$SKIP_COUNT SKIP${NC}"
echo "============================================================"

if [[ $FAIL_COUNT -gt 0 ]]; then
    exit 1
fi
exit 0
