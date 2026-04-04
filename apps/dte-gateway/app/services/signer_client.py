"""
Signer Client — firma un DTE JSON usando el svfe-api-firmador (Spring Boot :8113).

La password_pri se resuelve internamente via secret_resolver — nunca se recibe
como parámetro externo.

Firmador endpoint:
  POST <url_firmador>
  Content-Type: application/json
  Body: {"nit": str, "passwordPri": str, "activo": true, "dteJson": dict}
  Response OK:  {"status": "OK",    "body": "<JWS_compact_serialization>"}
  Response Err: {"status": "ERROR", "body": {"codigo": "...", "mensaje": [...]}}
"""

import logging

import requests

from app.config import FIRMADOR_TIMEOUT
from app.services.secret_resolver import get_firmador_password

logger = logging.getLogger(__name__)


def sign_dte(dte_json: dict, nit: str, url_firmador: str, firmador_nit: str | None = None) -> str:
    """
    Firma el DTE JSON y retorna el JWS compact serialization.

    Args:
        dte_json:     Objeto JSON del DTE sin firmar.
        nit:          NIT/DUI del emisor en el DTE (puede ser 9 dígitos DUI o 14 dígitos NIT).
        url_firmador: URL del endpoint del firmador.
        firmador_nit: NIT de 14 dígitos para lookup del certificado. Si None, usa nit.
                      Necesario cuando el DTE usa DUI (9 dígitos) pero el cert está registrado
                      con el NIT completo (14 dígitos) en el firmador.

    Returns:
        JWS compact serialization.

    Raises:
        RuntimeError: si el firmador responde con ERROR o no está disponible.
        RuntimeError: si FIRMADOR_PASSWORD_PRI no está configurada.
    """
    password_pri = get_firmador_password()
    cert_nit = firmador_nit or nit

    payload = {
        "nit": cert_nit,
        "passwordPri": password_pri,
        "activo": True,
        "dteJson": dte_json,
    }

    logger.info("signer_client: firmando DTE nit=%s cert_nit=%s url=%s", nit, cert_nit, url_firmador)
    try:
        response = requests.post(
            url_firmador,
            json=payload,
            timeout=FIRMADOR_TIMEOUT,
        )
        response.raise_for_status()
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError(f"No se pudo conectar al firmador en {url_firmador}: {exc}") from exc
    except requests.exceptions.Timeout:
        raise RuntimeError(
            f"Timeout al contactar firmador ({FIRMADOR_TIMEOUT}s): {url_firmador}"
        )

    body = response.json()
    if body.get("status") != "OK":
        error_detail = body.get("body", body)
        raise RuntimeError(f"Firmador respondió con ERROR: {error_detail}")

    jws: str = body["body"]
    if not jws or not isinstance(jws, str):
        raise RuntimeError(f"Firmador retornó body inesperado: {body!r}")

    logger.info("signer_client: firma exitosa nit=%s cert_nit=%s", nit, cert_nit)
    return jws
