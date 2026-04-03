"""
Construye el payload intermedio ERP→Gateway desde un DTEEmitRequest.

En Sprint 1, este módulo valida el request y devuelve un dict preparado
para ser pasado al mapper correspondiente (fe_mapper, ccf_mapper, nc_mapper).
Los mappers están como stubs hasta Sprint 2.
"""
from app.models.dte_request import DTEEmitRequest


def build_intermediate_payload(request: DTEEmitRequest) -> dict:
    """
    Valida y normaliza un DTEEmitRequest para pasarlo al mapper de tipo específico.

    Retorna un dict con los campos garantizados que los mappers pueden consumir.
    No construye el JSON final del DTE — eso es responsabilidad de los mappers.
    """
    _validate_request(request)

    return {
        "tipo_dte": request.tipo_dte,
        "ambiente": request.ambiente,
        "docname": request.docname,
        "company": request.company,
        "posting_date": str(request.posting_date),
        "posting_time": request.posting_time or "00:00:00",
        "currency": request.currency,
        "receptor": request.receptor.model_dump(exclude_none=True),
        "items": [item.model_dump() for item in request.items],
        "grand_total": float(request.grand_total),
        "total_iva": float(request.total_iva),
        "condicion_operacion": request.condicion_operacion,
        "pagos": request.pagos,
        "documento_relacionado_codigo": request.documento_relacionado_codigo,
        "documento_relacionado_tipo": request.documento_relacionado_tipo,
        "documento_relacionado_fecha": (
            str(request.documento_relacionado_fecha)
            if request.documento_relacionado_fecha else None
        ),
    }


def _validate_request(request: DTEEmitRequest) -> None:
    if request.tipo_dte not in ("01", "03", "05"):
        raise ValueError(f"tipo_dte no soportado: {request.tipo_dte!r}. Válidos: 01, 03, 05")
    if request.ambiente not in ("00", "01"):
        raise ValueError(f"ambiente inválido: {request.ambiente!r}. Válidos: 00, 01")
    if not request.items:
        raise ValueError("La lista de ítems no puede estar vacía")
    if float(request.grand_total) < 0:
        raise ValueError("grand_total no puede ser negativo")
