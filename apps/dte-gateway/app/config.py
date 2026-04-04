"""
Constantes de configuración del DTE Gateway.
"""

MH_ENDPOINT_TEST = "https://apitest.dtes.mh.gob.sv"
MH_ENDPOINT_PROD = "https://api.dtes.mh.gob.sv"
MH_AUTH_PATH          = "/seguridad/auth"
MH_RECEIVE_PATH       = "/fesv/recepciondte"
MH_QUERY_DTE_PATH     = "/fesv/recepcion/consultadte/"
MH_INVALIDATION_PATH  = "/fesv/anulardte"
MH_CONTINGENCY_PATH   = "/fesv/contingencia"

IVA_RATE = 0.13

# Token cache TTL (segundos) — conservador para evitar expiración inesperada
TOKEN_TTL_TEST = 47 * 3600   # 47h (MH otorga 48h)
TOKEN_TTL_PROD = 23 * 3600   # 23h (MH otorga 24h)

# Retry para envío al MH
MH_SEND_RETRIES = 3
MH_SEND_TIMEOUT = 8          # segundos por intento
MH_SEND_RETRY_SLEEP = 1      # segundos entre intentos

# Firmador
FIRMADOR_TIMEOUT = 15        # segundos
