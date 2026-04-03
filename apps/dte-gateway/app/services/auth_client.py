"""
STUB — Auth Client para el API del Ministerio de Hacienda.

Sprint 2: implementar con cache de token 48h/24h.

API MH — endpoint de autenticación:
  POST https://apitest.dtes.mh.gob.sv/seguridad/auth     (pruebas)
  POST https://api.dtes.mh.gob.sv/seguridad/auth          (producción)
  Content-Type: application/x-www-form-urlencoded
  Body: user=<NIT_14DIGITS>&pwd=<API_PASSWORD>
  Response OK: {"status": "OK", "body": {"token": "Bearer eyJ...", ...}}

Reglas de cache:
  - Token válido 48 h en ambiente de pruebas
  - Token válido 24 h en ambiente de producción
  - Cachear hasta expiración; no regenerar por documento
"""


def get_token(nit: str, api_password: str, ambiente: str = "00") -> str:
    """
    Obtiene (o devuelve del cache) el token Bearer para la API del MH.

    Args:
        nit:          NIT del emisor, 14 dígitos sin guiones.
        api_password: Contraseña de la API del MH (diferente a la clave privada).
        ambiente:     "00" = pruebas, "01" = producción.

    Returns:
        Token Bearer como string (sin el prefijo "Bearer ").

    Raises:
        NotImplementedError: hasta Sprint 2.
    """
    raise NotImplementedError(
        "auth_client.get_token — pendiente Sprint 2.\n"
        "Endpoint: POST /seguridad/auth (form-urlencoded: user=NIT, pwd=PASSWORD).\n"
        "Token válido 48h (pruebas) / 24h (prod). Cachear hasta expiración."
    )
