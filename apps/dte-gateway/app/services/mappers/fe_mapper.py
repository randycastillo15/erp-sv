"""
STUB — Mapper FE (tipo 01) — Factura Electrónica.
Convierte DTEEmitRequest → JSON DTE oficial (schema fe-fc-v1.json).

Sprint 2: implementar según Especificación Técnica FE versión 1.

Regla crítica (Aviso DGII):
  Si grand_total < 25 000 USD y el receptor es consumidor final,
  NO exigir numDocumento ni correo en el receptor.
"""
from app.models.dte_request import DTEEmitRequest


def build_fe(request: DTEEmitRequest, settings: dict) -> dict:
    """
    Construye el JSON completo del DTE tipo FE (tipoDte=01).

    Args:
        request:  DTEEmitRequest validado.
        settings: Configuración del emisor (NIT, NRC, establecimiento, etc.)

    Returns:
        dict con la estructura completa del DTE según fe-fc-v1.json.

    Raises:
        NotImplementedError: hasta Sprint 2.
    """
    raise NotImplementedError("fe_mapper.build_fe — pendiente Sprint 2")
