"""
STUB — Mapper CCF (tipo 03) — Comprobante de Crédito Fiscal.
Convierte DTEEmitRequest → JSON DTE oficial (schema fe-ccf-v3.json).

Sprint 2: implementar según Especificación Técnica CCF versión 3.

Diferencias clave vs FE:
  - Receptor debe tener NIT y NRC válidos
  - Incluye IVA desglosado por ítem
  - Aplica retención si receptor tiene categoría especial
"""
from app.models.dte_request import DTEEmitRequest


def build_ccf(request: DTEEmitRequest, settings: dict) -> dict:
    """
    Construye el JSON completo del DTE tipo CCF (tipoDte=03).

    Raises:
        NotImplementedError: hasta Sprint 2.
    """
    raise NotImplementedError("ccf_mapper.build_ccf — pendiente Sprint 2")
