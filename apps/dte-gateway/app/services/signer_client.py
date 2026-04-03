"""
STUB — Signer Client para svfe-api-firmador.

Sprint 2: implementar llamada HTTP al firmador oficial (Spring Boot, :8113).

Firmador — endpoint de firma:
  POST http://localhost:8113/firma/firmardocumento/
  Content-Type: application/json
  Body: {
    "nit": "<NIT_14DIGITS>",
    "passwordPri": "<CLAVE_PRIVADA>",
    "activo": true,
    "dteJson": <objeto JSON del DTE sin firmar>
  }
  Response OK:  {"status": "OK",    "body": "<JWS_compact_serialization>"}
  Response Err: {"status": "ERROR", "body": {"codigo": "...", "mensaje": [...]}}

El JWS compact serialization resultante se coloca en el campo
"firmaElectronica" del DTE antes de enviarlo al MH.
"""


def sign_dte(dte_json: dict, nit: str, password_pri: str) -> str:
    """
    Firma un DTE JSON y retorna el JWS compact serialization.

    Args:
        dte_json:     Objeto JSON del DTE sin firmar.
        nit:          NIT del emisor (14 dígitos).
        password_pri: Contraseña de la clave privada del certificado.

    Returns:
        JWS compact serialization — va como "firmaElectronica" en el DTE final.

    Raises:
        NotImplementedError: hasta Sprint 2.
    """
    raise NotImplementedError(
        "signer_client.sign_dte — pendiente Sprint 2.\n"
        "Firmador: POST http://localhost:8113/firma/firmardocumento/.\n"
        "El resultado (body) se agrega como firmaElectronica al DTE antes de enviarlo al MH."
    )
