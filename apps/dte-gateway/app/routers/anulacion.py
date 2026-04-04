"""
Router Anulación — endpoint para invalidar un DTE ya PROCESADO por MH.

POST /v2/dte/anular
  - Idempotente: misma idempotency_key retorna respuesta cacheada.
  - Flujo: build_anulacion → schema validation → sign → send_anulacion (MH).
  - El campo interno _event_uuid se extrae del dict antes de firmar.
"""

import logging

from fastapi import APIRouter, HTTPException

from app.models.dte_request import AnulacionRequest
from app.services import auth_client, mh_client, dte_store
from app.services.mappers.anulacion_mapper import build_anulacion
from app.services.schema_validator import validate_dte
from app.services.signer_client import sign_dte

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v2/dte", tags=["Anulación"])


@router.post("/anular")
def anular_dte(request: AnulacionRequest) -> dict:
    """
    Invalida un DTE previamente PROCESADO por MH.

    Pasos:
    1. Idempotencia — si ya se anuló, retorna resultado cacheado.
    2. build_anulacion → JSON del evento (incluye _event_uuid interno).
    3. Validación schema anulacion-v2.
    4. Firma con firmador (extrae _event_uuid antes de firmar).
    5. Transmisión al MH vía /fesv/anulardte.
    6. Persistencia del resultado.

    Returns:
        {event_uuid, sello_recibido, estado, descripcion_msg, ...}
    """
    key = request.idempotency_key

    # Idempotencia
    try:
        cached = dte_store.check_anulacion(key)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if cached:
        logger.info("anulacion: respuesta cacheada para key=%s", key)
        return cached

    # Marcar como pending
    dte_store.save_anulacion(
        key=key,
        codigo_generacion_original=request.codigo_generacion_original,
        event_uuid=None,
        status="pending",
    )

    try:
        # Construir JSON del evento
        try:
            anulacion_json = build_anulacion(request)
        except ValueError as exc:
            dte_store.save_anulacion(key, request.codigo_generacion_original, None, "failed")
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        # Extraer UUID del evento (campo interno — no forma parte del schema JSON)
        event_uuid = anulacion_json.pop("_event_uuid")

        # Validar contra schema anulacion-v2
        errors = validate_dte(anulacion_json, "anulacion")
        if errors:
            dte_store.save_anulacion(key, request.codigo_generacion_original, event_uuid, "failed")
            raise HTTPException(
                status_code=422,
                detail=f"Schema anulacion-v2 inválido: {'; '.join(errors)}"
            )

        # Firma
        s = request.emisor
        try:
            jws = sign_dte(
                dte_json=anulacion_json,
                nit=s.nit,
                url_firmador=s.url_firmador,
                firmador_nit=s.nit_firmador,
            )
        except RuntimeError as exc:
            dte_store.save_anulacion(key, request.codigo_generacion_original, event_uuid, "failed")
            raise HTTPException(status_code=502, detail=f"Firmador: {exc}") from exc

        # Auth token
        try:
            token = auth_client.get_token(s.nit, request.ambiente)
        except RuntimeError as exc:
            dte_store.save_anulacion(key, request.codigo_generacion_original, event_uuid, "failed")
            raise HTTPException(status_code=502, detail=f"Auth MH: {exc}") from exc

        # Transmitir al MH
        try:
            mh_result = mh_client.send_anulacion(
                jws=jws,
                codigo_generacion=event_uuid,
                ambiente=request.ambiente,
                token=token,
            )
        except RuntimeError as exc:
            dte_store.save_anulacion(key, request.codigo_generacion_original, event_uuid, "failed")
            raise HTTPException(status_code=502, detail=str(exc)) from exc

        # Construir respuesta
        result = {
            "event_uuid":      event_uuid,
            "sello_recibido":  mh_result.get("selloRecibido"),
            "estado":          mh_result.get("estado"),
            "descripcion_msg": mh_result.get("descripcionMsg"),
            "clasifica_msg":   mh_result.get("clasificaMsg"),
            "codigo_msg":      mh_result.get("codigoMsg"),
            "observaciones":   mh_result.get("observaciones") or [],
        }

        dte_store.save_anulacion(
            key, request.codigo_generacion_original, event_uuid, "completed", result
        )
        logger.info(
            "anulacion: completada gen_original=%s event_uuid=%s estado=%s",
            request.codigo_generacion_original, event_uuid, result.get("estado"),
        )
        return result

    except HTTPException:
        raise
    except Exception as exc:
        dte_store.save_anulacion(key, request.codigo_generacion_original, None, "failed")
        logger.exception("anulacion: error inesperado key=%s: %s", key, exc)
        raise HTTPException(status_code=500, detail=f"Error interno: {exc}") from exc
