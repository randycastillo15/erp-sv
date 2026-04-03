"""
Router DTE v2 — endpoints con modelos Pydantic tipados.

Montado opcionalmente en main.py (Sprint 1: solo estructura, no reemplaza mock).
Los endpoints reales (firma + transmisión MH) se activarán en Sprint 2.
"""
from fastapi import APIRouter, HTTPException

from app.models.dte_request import DTEEmitRequest, DTEStatusRequest
from app.models.dte_response import DTEEmitResponse
from app.services.control_number import generate_codigo_generacion, generate_numero_control

router = APIRouter(prefix="/v2/dte", tags=["DTE"])


@router.post("/emit", response_model=DTEEmitResponse)
def emit_dte_v2(request: DTEEmitRequest) -> DTEEmitResponse:
    """
    Emite un DTE (Sprint 1: mock tipado — valida contrato ERP→Gateway).

    Sprint 2: reemplazar por flujo completo: build → sign → transmit → respond.
    """
    gen_code = generate_codigo_generacion()
    control_num = generate_numero_control(
        tipo_dte=request.tipo_dte,
        cod_estable_mh="0001",          # TODO Sprint 2: leer de settings
        cod_punto_venta_mh="0001",
        secuencial=1,                   # TODO Sprint 2: secuencial persistente
    )

    return DTEEmitResponse(
        status="received",
        mode="mock_v2",
        generation_code=gen_code,
        uuid_dte=gen_code,              # compat legacy
        control_number=control_num,
        estado="MOCK",
    )


@router.post("/status")
def get_dte_status(request: DTEStatusRequest) -> dict:
    """
    Consulta el estado de un DTE — stub hasta Sprint 2.
    """
    return {
        "status": "stub",
        "codigo_generacion": request.codigo_generacion,
        "tipo_dte": request.tipo_dte,
        "ambiente": request.ambiente,
        "message": "Consulta de estado pendiente Sprint 2",
    }
