"""
Router DTE v2 — endpoints tipados con integración real MH.
"""
from fastapi import APIRouter, HTTPException

from app.models.dte_request import DTEEmitRequest, DTEStatusRequest
from app.models.dte_response import DTEEmitResponse
from app.services import auth_client, mh_client
from app.services import dte_service

router = APIRouter(prefix="/v2/dte", tags=["DTE"])


@router.post("/emit", response_model=DTEEmitResponse)
def emit_dte_v2(request: DTEEmitRequest) -> DTEEmitResponse:
    """
    Emite un DTE: valida schema, firma, transmite al MH y retorna resultado.

    Idempotente: misma idempotency_key retorna resultado cacheado sin reenviar.
    """
    try:
        return dte_service.emit(request)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc


@router.post("/status")
def get_dte_status(request: DTEStatusRequest) -> dict:
    """
    Consulta el estado de un DTE en el MH por código de generación.
    """
    try:
        token = auth_client.get_token(request.nit_emisor, request.ambiente)
        return mh_client.query_dte_status(
            codigo_generacion=request.codigo_generacion,
            ambiente=request.ambiente,
            token=token,
            nit_emisor=request.nit_emisor,
            tipo_dte=request.tipo_dte,
        )
    except RuntimeError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
