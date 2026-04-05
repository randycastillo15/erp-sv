#!/usr/bin/env bash
# common.sh — variables y helpers compartidos por todos los smoke tests

BASE_URL="${DTE_GATEWAY_URL:-http://localhost:8100}"
NIT_EMISOR="${DTE_NIT_EMISOR:-061172006}"
NIT_FIRMADOR="${DTE_NIT_FIRMADOR:-06141310001389}"
NRC_EMISOR="${DTE_NRC_EMISOR:-2862402}"
COD_ACTIVIDAD="${DTE_COD_ACTIVIDAD:-47522}"
DESC_ACTIVIDAD="${DTE_DESC_ACTIVIDAD:-Venta al por menor de articulos de ferreteria}"
URL_FIRMADOR="${DTE_FIRMADOR_URL:-http://host.docker.internal:8113/firmardocumento/}"
AMBIENTE="${DTE_AMBIENTE:-00}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

pass() { echo -e "${GREEN}PASS${NC}: $1"; }
fail() { echo -e "${RED}FAIL${NC}: $1"; exit 1; }
warn() { echo -e "${YELLOW}WARN${NC}: $1"; }

# Verifica que jq está disponible
require_jq() {
    if ! command -v jq &>/dev/null; then
        fail "jq es requerido. Instala con: sudo apt install jq"
    fi
}

# Verifica que una clave existe y no es null en el JSON de respuesta
assert_key_present() {
    local json="$1" key="$2"
    local val
    val=$(echo "$json" | jq -r ".$key // empty")
    if [[ -z "$val" ]]; then
        fail "Campo '$key' ausente o null en respuesta: $json"
    fi
}

# Verifica que una clave empieza con un prefijo dado
assert_key_starts_with() {
    local json="$1" key="$2" prefix="$3"
    local val
    val=$(echo "$json" | jq -r ".$key // empty")
    if [[ "$val" != "$prefix"* ]]; then
        fail "Campo '$key' esperaba prefijo '$prefix', obtenido: '$val'"
    fi
}
