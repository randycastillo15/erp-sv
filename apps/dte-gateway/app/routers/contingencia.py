"""
Router Contingencia — endpoint para transmitir un evento de contingencia tipo 14.

POST /v2/contingencia/emit
  - Idempotente: misma idempotency_key retorna respuesta cacheada.
  - Flujo: build_contingencia → schema validation → sign → send_contingencia (MH).
"""

import logging

from fastapi import APIRouter, HTTPException

from app.models.dte_request import ContingenciaEmitRequest
from app.services import auth_client, mh_client, dte_store
from app.services.mappers.contingencia_mapper import build_contingencia
from app.services.schema_validator import validate_dte
from app.services.signer_client import sign_dte

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v2/contingencia", tags=["Contingencia"])


@router.post("/emit")
def emit_contingencia(request: ContingenciaEmitRequest) -> dict:
    """
    Transmite un evento de contingencia tipo 14 al MH.

    El evento agrupa hasta 1000 DTEs que fueron emitidos offline durante
    un período sin disponibilidad de MH.

    Pasos:
    1. Idempotencia — si ya se transmitió, retorna resultado cacheado.
    2. build_contingencia → JSON del evento (con _event_uuid interno).
    3. Validación schema contingencia-v3.
    4. Firma con firmador.
    5. Transmisión al MH vía /fesv/contingencia.
    6. Persistencia del resultado.

    Returns:
        {event_uuid, sello_recibido, estado, descripcion_msg, ...}
    """
    key = request.idempotency_key

    # Idempotencia
    try:
        cached = dte_store.check_contingencia(key)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if cached:
        logger.info("contingencia: respuesta cacheada para key=%s", key)
        return cached

    # Marcar como pending
    dte_store.save_contingencia(key=key, event_uuid=None, status="pending")

    try:
        # Construir JSON del evento
        try:
            contingencia_json = build_contingencia(request)
        except ValueError as exc:
            dte_store.save_contingencia(key, None, "failed")
            raise HTTPException(status_code=422, detail=str(exc)) from exc

        # Extraer UUID del evento (campo interno — no parte del schema)
        event_uuid = contingencia_json.pop("_event_uuid")

        # Validar contra schema contingencia-v3
        errors = validate_dte(contingencia_json, "contingencia")
        if errors:
            dte_store.save_contingencia(key, event_uuid, "failed")
            raise HTTPException(
                status_code=422,
                detail=f"Schema contingencia-v3 inválido: {'; '.join(errors)}"
            )

        # Firma
        s = request.emisor
        try:
            jws = sign_dte(
                dte_json=contingencia_json,
                nit=s.nit,
                url_firmador=s.url_firmador,
                firmador_nit=s.nit_firmador,
            )
        except RuntimeError as exc:
            dte_store.save_contingencia(key, event_uuid, "failed")
            raise HTTPException(status_code=502, detail=f"Firmador: {exc}") from exc

        # Auth token
        try:
            token = auth_client.get_token(s.nit, request.ambiente)
        except RuntimeError as exc:
            dte_store.save_contingencia(key, event_uuid, "failed")
            raise HTTPException(status_code=502, detail=f"Auth MH: {exc}") from exc

        # Transmitir al MH
        try:
            mh_result = mh_client.send_contingencia(
                jws=jws,
                codigo_generacion=event_uuid,
                ambiente=request.ambiente,
                token=token,
            )
        except RuntimeError as exc:
            dte_store.save_contingencia(key, event_uuid, "failed")
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
            "dtes_incluidos":  len(request.detalle),
        }

        dte_store.save_contingencia(key, event_uuid, "completed", result)
        logger.info(
            "contingencia: completada event_uuid=%s estado=%s dtes=%d",
            event_uuid, result.get("estado"), len(request.detalle),
        )
        return result

    except HTTPException:
        raise
    except Exception as exc:
        dte_store.save_contingencia(key, None, "failed")
        logger.exception("contingencia: error inesperado key=%s: %s", key, exc)
        raise HTTPException(status_code=500, detail=f"Error interno: {exc}") from exc
