"""
MH Client — transmite DTEs al Ministerio de Hacienda y consulta su estado.

Retry: 3 intentos, timeout 8s cada uno, 1s de espera entre reintentos.
El token se obtiene externamente (desde auth_client) y se pasa como argumento.
"""

import logging
import time

import requests

from app.config import (
    MH_CONTINGENCY_PATH,
    MH_ENDPOINT_PROD,
    MH_ENDPOINT_TEST,
    MH_INVALIDATION_PATH,
    MH_QUERY_DTE_PATH,
    MH_RECEIVE_PATH,
    MH_SEND_RETRIES,
    MH_SEND_RETRY_SLEEP,
    MH_SEND_TIMEOUT,
)

logger = logging.getLogger(__name__)


def _base_url(ambiente: str) -> str:
    return MH_ENDPOINT_TEST if ambiente == "00" else MH_ENDPOINT_PROD


def send_dte(
    jws: str,
    codigo_generacion: str,
    tipo_dte: str,
    version: int,
    ambiente: str,
    token: str,
    id_envio: int = 1,
) -> dict:
    """
    Envía un DTE firmado al MH usando el formato de recepción uno a uno.

    Body: {ambiente, idEnvio, version, tipoDte, documento (JWS), codigoGeneracion}
    Retry: MH_SEND_RETRIES intentos con timeout MH_SEND_TIMEOUT cada uno.
    En caso de error HTTP 5xx o timeout, reintenta. Error 4xx no se reintenta.

    Args:
        jws:               JWS compact serialization del firmador.
        codigo_generacion: UUID v4 uppercase del DTE.
        tipo_dte:          "01", "03", "05", etc.
        version:           Versión del schema (1 para FE, 3 para CCF/NC).
        ambiente:          "00"=pruebas, "01"=producción.
        token:             Bearer token (sin prefijo "Bearer ").
        id_envio:          Correlativo de envío (entero, a discreción).

    Returns:
        Dict con la respuesta del MH (estado, selloRecibido, fhProcesamiento, etc.).

    Raises:
        RuntimeError: si todos los reintentos fallan.
    """
    url = f"{_base_url(ambiente)}{MH_RECEIVE_PATH}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "dte-gateway/2.0",
    }
    body = {
        "ambiente":         ambiente,
        "idEnvio":          id_envio,
        "version":          version,
        "tipoDte":          tipo_dte,
        "documento":        jws,
        "codigoGeneracion": codigo_generacion,
    }

    last_exc: Exception | None = None
    for attempt in range(1, MH_SEND_RETRIES + 1):
        try:
            logger.info(
                "mh_client: enviando DTE al MH tipo=%s ambiente=%s gen=%s intento=%d/%d",
                tipo_dte, ambiente, codigo_generacion, attempt, MH_SEND_RETRIES,
            )
            response = requests.post(
                url,
                json=body,
                headers=headers,
                timeout=MH_SEND_TIMEOUT,
            )
            # No reintentar en errores 4xx (problema en el DTE, no en el servidor)
            if 400 <= response.status_code < 500:
                response.raise_for_status()

            response.raise_for_status()
            result = response.json()
            logger.info(
                "mh_client: respuesta MH estado=%s sello=%s",
                result.get("estado"), result.get("selloRecibido"),
            )
            return result

        except requests.exceptions.Timeout as exc:
            last_exc = exc
            logger.warning("mh_client: timeout intento %d/%d", attempt, MH_SEND_RETRIES)
        except requests.exceptions.HTTPError as exc:
            # 4xx → no reintentar
            if exc.response is not None and 400 <= exc.response.status_code < 500:
                raise RuntimeError(f"MH rechazó el DTE (HTTP {exc.response.status_code}): {exc.response.text}") from exc
            last_exc = exc
            logger.warning("mh_client: HTTP error intento %d/%d: %s", attempt, MH_SEND_RETRIES, exc)
        except requests.exceptions.ConnectionError as exc:
            last_exc = exc
            logger.warning("mh_client: connection error intento %d/%d: %s", attempt, MH_SEND_RETRIES, exc)

        if attempt < MH_SEND_RETRIES:
            time.sleep(MH_SEND_RETRY_SLEEP)

    raise RuntimeError(
        f"MH no respondió después de {MH_SEND_RETRIES} intentos: {last_exc}"
    )


def send_anulacion(
    jws: str,
    codigo_generacion: str,
    ambiente: str,
    token: str,
    id_envio: int = 1,
) -> dict:
    """
    Envía un evento de invalidación firmado al MH.

    Schema anulacion-v2 → version=2, sin tipoDte en el body de transporte.

    Args:
        jws:               JWS compact serialization del evento de anulación.
        codigo_generacion: UUID v4 uppercase del evento (NO del DTE a anular).
        ambiente:          "00"=pruebas, "01"=producción.
        token:             Bearer token.
        id_envio:          Correlativo de envío.

    Returns:
        Dict con la respuesta del MH (estado, selloRecibido, etc.).

    Raises:
        RuntimeError: si todos los reintentos fallan.
    """
    url = f"{_base_url(ambiente)}{MH_INVALIDATION_PATH}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "dte-gateway/2.0",
    }
    body = {
        "ambiente":         ambiente,
        "idEnvio":          id_envio,
        "version":          2,
        "documento":        jws,
        "codigoGeneracion": codigo_generacion,
    }

    last_exc: Exception | None = None
    for attempt in range(1, MH_SEND_RETRIES + 1):
        try:
            logger.info(
                "mh_client: enviando anulación al MH ambiente=%s gen=%s intento=%d/%d",
                ambiente, codigo_generacion, attempt, MH_SEND_RETRIES,
            )
            response = requests.post(
                url, json=body, headers=headers, timeout=MH_SEND_TIMEOUT,
            )
            if 400 <= response.status_code < 500:
                response.raise_for_status()
            response.raise_for_status()
            result = response.json()
            logger.info(
                "mh_client: anulación MH estado=%s sello=%s",
                result.get("estado"), result.get("selloRecibido"),
            )
            return result
        except requests.exceptions.Timeout as exc:
            last_exc = exc
            logger.warning("mh_client: anulación timeout intento %d/%d", attempt, MH_SEND_RETRIES)
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and 400 <= exc.response.status_code < 500:
                raise RuntimeError(
                    f"MH rechazó la anulación (HTTP {exc.response.status_code}): {exc.response.text}"
                ) from exc
            last_exc = exc
            logger.warning("mh_client: anulación HTTP error intento %d/%d: %s", attempt, MH_SEND_RETRIES, exc)
        except requests.exceptions.ConnectionError as exc:
            last_exc = exc
            logger.warning("mh_client: anulación connection error intento %d/%d: %s", attempt, MH_SEND_RETRIES, exc)

        if attempt < MH_SEND_RETRIES:
            time.sleep(MH_SEND_RETRY_SLEEP)

    raise RuntimeError(
        f"MH no respondió a la anulación después de {MH_SEND_RETRIES} intentos: {last_exc}"
    )


def send_contingencia(
    jws: str,
    codigo_generacion: str,
    ambiente: str,
    token: str,
    id_envio: int = 1,
) -> dict:
    """
    Envía un evento de contingencia (tipo 14) firmado al MH.

    Schema contingencia-v3 → version=3.

    Args:
        jws:               JWS compact serialization del evento.
        codigo_generacion: UUID v4 uppercase del evento de contingencia.
        ambiente:          "00"=pruebas, "01"=producción.
        token:             Bearer token.
        id_envio:          Correlativo de envío.

    Returns:
        Dict con la respuesta del MH.

    Raises:
        RuntimeError: si todos los reintentos fallan.
    """
    url = f"{_base_url(ambiente)}{MH_CONTINGENCY_PATH}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "User-Agent": "dte-gateway/2.0",
    }
    body = {
        "ambiente":         ambiente,
        "idEnvio":          id_envio,
        "version":          3,
        "documento":        jws,
        "codigoGeneracion": codigo_generacion,
    }

    last_exc: Exception | None = None
    for attempt in range(1, MH_SEND_RETRIES + 1):
        try:
            logger.info(
                "mh_client: enviando contingencia al MH ambiente=%s gen=%s intento=%d/%d",
                ambiente, codigo_generacion, attempt, MH_SEND_RETRIES,
            )
            response = requests.post(
                url, json=body, headers=headers, timeout=MH_SEND_TIMEOUT,
            )
            if 400 <= response.status_code < 500:
                response.raise_for_status()
            response.raise_for_status()
            result = response.json()
            logger.info(
                "mh_client: contingencia MH estado=%s sello=%s",
                result.get("estado"), result.get("selloRecibido"),
            )
            return result
        except requests.exceptions.Timeout as exc:
            last_exc = exc
            logger.warning("mh_client: contingencia timeout intento %d/%d", attempt, MH_SEND_RETRIES)
        except requests.exceptions.HTTPError as exc:
            if exc.response is not None and 400 <= exc.response.status_code < 500:
                raise RuntimeError(
                    f"MH rechazó el evento de contingencia (HTTP {exc.response.status_code}): {exc.response.text}"
                ) from exc
            last_exc = exc
            logger.warning("mh_client: contingencia HTTP error intento %d/%d: %s", attempt, MH_SEND_RETRIES, exc)
        except requests.exceptions.ConnectionError as exc:
            last_exc = exc
            logger.warning("mh_client: contingencia connection error intento %d/%d: %s", attempt, MH_SEND_RETRIES, exc)

        if attempt < MH_SEND_RETRIES:
            time.sleep(MH_SEND_RETRY_SLEEP)

    raise RuntimeError(
        f"MH no respondió al evento de contingencia después de {MH_SEND_RETRIES} intentos: {last_exc}"
    )


def query_dte_status(
    codigo_generacion: str,
    ambiente: str,
    token: str,
    nit_emisor: str,
    tipo_dte: str,
) -> dict:
    """
    Consulta el estado de un DTE en el MH por su código de generación.

    MH requiere POST con cuerpo JSON {nitEmisor, tdte, codigoGeneracion}.

    Args:
        codigo_generacion: UUID v4 uppercase del DTE.
        ambiente:          "00"=pruebas, "01"=producción.
        token:             Bearer token (sin prefijo "Bearer ").
        nit_emisor:        NIT del emisor (sin guiones).
        tipo_dte:          Código tipo DTE ("01", "03", "05", etc.).

    Returns:
        Dict con la respuesta del MH (incluye campo "estado").
    """
    url = f"{_base_url(ambiente)}{MH_QUERY_DTE_PATH}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    body = {
        "nitEmisor":        nit_emisor,
        "tdte":             tipo_dte,
        "codigoGeneracion": codigo_generacion,
    }

    logger.info(
        "mh_client: consultando estado DTE codigo=%s tipo=%s",
        codigo_generacion, tipo_dte,
    )
    response = requests.post(url, json=body, headers=headers, timeout=MH_SEND_TIMEOUT)
    response.raise_for_status()
    return response.json()
