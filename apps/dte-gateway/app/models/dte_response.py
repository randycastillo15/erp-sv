"""Contratos de respuesta del gateway hacia ERPNext."""
from typing import Optional

from pydantic import BaseModel


class DTEEmitResponse(BaseModel):
    """Respuesta del gateway tras emitir un DTE."""
    # Estado del gateway
    status: str                              # "received", "error", "mock"
    mode: str = "mock"
    # Identificadores DTE
    generation_code: Optional[str] = None   # UUID v4 MAYÚSCULAS (codigoGeneracion)
    control_number: Optional[str] = None    # DTE-01-XXXXXXXX-000000000000001
    # Respuesta MH (disponible cuando haya integración real)
    estado: Optional[str] = None            # PROCESADO / RECHAZADO
    sello_recibido: Optional[str] = None
    fh_procesamiento: Optional[str] = None
    clasifica_msg: Optional[str] = None
    codigo_msg: Optional[str] = None
    observaciones: list[str] = []
    # Campo legacy — mantenido por compat con mock y api/dte.py v1.0
    uuid_dte: Optional[str] = None
