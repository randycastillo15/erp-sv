"""
Auth Client — obtiene y cachea el token Bearer del API MH.

Cache in-memory: {(nit, ambiente): (token, expiry_timestamp)}
TTL: 47h pruebas / 23h producción (conservador vs. las 48h/24h que otorga el MH).

El api_password se resuelve internamente via secret_resolver — nunca se recibe
como parámetro externo.
"""

import logging
import time
from threading import Lock

import requests

from app.config import (
    MH_AUTH_PATH,
    MH_ENDPOINT_PROD,
    MH_ENDPOINT_TEST,
    TOKEN_TTL_PROD,
    TOKEN_TTL_TEST,
)
from app.services.secret_resolver import get_mh_api_password

logger = logging.getLogger(__name__)

_cache: dict[tuple[str, str], tuple[str, float]] = {}
_cache_lock = Lock()


def get_token(nit: str, ambiente: str = "00") -> str:
    """
    Retorna el token Bearer para el NIT/ambiente dados.
    Usa cache hasta expiración; renueva automáticamente.

    Args:
        nit:     NIT del emisor, 14 dígitos sin guiones.
        ambiente: "00"=pruebas, "01"=producción.

    Returns:
        Token como string (sin prefijo "Bearer ").

    Raises:
        RuntimeError: si env var MH_API_PASSWORD no está configurada.
        requests.HTTPError: si el MH rechaza las credenciales.
    """
    cache_key = (nit, ambiente)
    now = time.monotonic()

    with _cache_lock:
        if cache_key in _cache:
            token, expiry = _cache[cache_key]
            if now < expiry:
                logger.debug("auth_client: token cache hit nit=%s ambiente=%s", nit, ambiente)
                return token

    # Cache miss o expirado — obtener nuevo token
    api_password = get_mh_api_password()
    base_url = MH_ENDPOINT_TEST if ambiente == "00" else MH_ENDPOINT_PROD
    url = f"{base_url}{MH_AUTH_PATH}"

    logger.info("auth_client: solicitando nuevo token nit=%s ambiente=%s", nit, ambiente)
    response = requests.post(
        url,
        data={"user": nit, "pwd": api_password},
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        timeout=10,
    )
    response.raise_for_status()

    body = response.json()
    if body.get("status") != "OK":
        raise RuntimeError(f"MH Auth error: {body}")

    token_raw: str = body["body"]["token"]
    # El MH devuelve "Bearer eyJ..." — extraer solo el JWT
    token = token_raw.removeprefix("Bearer ").strip()

    ttl = TOKEN_TTL_TEST if ambiente == "00" else TOKEN_TTL_PROD
    expiry = now + ttl

    with _cache_lock:
        _cache[cache_key] = (token, expiry)

    return token


def invalidate_token(nit: str, ambiente: str = "00") -> None:
    """Elimina el token del cache para forzar renovación en la próxima llamada."""
    with _cache_lock:
        _cache.pop((nit, ambiente), None)
