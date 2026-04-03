"""
STUB — Mapper NC (tipo 05) — Nota de Crédito.
Convierte DTEEmitRequest → JSON DTE oficial (schema fe-nc-v3.json).

Sprint 2: implementar según Especificación Técnica NC versión 3.

Reglas críticas:
  - Debe referenciar el DTE original (documento_relacionado_codigo + tipo + fecha)
  - El DTE original debe existir y tener sello de recepción del MH
  - Excepción: si el DTE relacionado es una NC o CL, no requiere sello previo
"""
from app.models.dte_request import DTEEmitRequest


def build_nc(request: DTEEmitRequest, settings: dict) -> dict:
    """
    Construye el JSON completo del DTE tipo NC (tipoDte=05).

    Raises:
        NotImplementedError: hasta Sprint 2.
    """
    raise NotImplementedError("nc_mapper.build_nc — pendiente Sprint 2")
