"""
Contrato de entrada del gateway DTE — versión 1.
Define qué envía ERPNext al gateway por cada tipo de operación.
"""
from datetime import date
from decimal import Decimal
from typing import Optional

from pydantic import BaseModel, Field


class DTEItemRequest(BaseModel):
    """Ítem de la factura."""
    num_item: int
    tipo_item: int                          # CAT-009: 1=bienes, 2=servicios, 3=ambos
    descripcion: str
    cantidad: Decimal
    unidad_medida: int = 59                 # CAT-014: 59=Unidad por defecto
    precio_unitario: Decimal
    descuento: Decimal = Decimal("0")
    venta_no_sujeta: Decimal = Decimal("0")
    venta_exenta: Decimal = Decimal("0")
    venta_gravada: Decimal = Decimal("0")
    tributos: list[str] = Field(default_factory=list)   # ej: ["20"] = IVA
    codigo_interno: Optional[str] = None


class DTEReceptorRequest(BaseModel):
    """Datos del receptor (cliente)."""
    nombre: Optional[str] = None
    tipo_doc_identificacion: Optional[str] = None    # CAT-022
    num_documento: Optional[str] = None
    nit: Optional[str] = None
    nrc: Optional[str] = None
    correo: Optional[str] = None
    telefono: Optional[str] = None
    direccion_departamento: Optional[str] = None     # CAT-012
    direccion_municipio: Optional[str] = None        # CAT-013
    direccion_complemento: Optional[str] = None
    cod_actividad: Optional[str] = None              # CAT-019 (requerido para CCF)


class DTEEmitRequest(BaseModel):
    """Payload que envía ERPNext al gateway para emitir un DTE."""
    # Identificación del documento
    tipo_dte: str                            # "01"=FE, "03"=CCF, "05"=NC
    ambiente: str = "00"                    # CAT-001: "00"=pruebas, "01"=producción
    # Origen en ERPNext
    docname: str                            # ej: SINV-0001
    company: str
    posting_date: date
    posting_time: Optional[str] = None     # HH:MM:SS
    currency: str = "USD"
    # Receptor
    receptor: DTEReceptorRequest
    # Ítems y totales
    items: list[DTEItemRequest]
    grand_total: Decimal
    total_iva: Decimal = Decimal("0")
    condicion_operacion: int = 1            # CAT-016: 1=contado, 2=crédito, 3=otro
    # Pagos (lista de dicts con forma, monto, etc.)
    pagos: list[dict] = Field(default_factory=list)
    # NC: documento relacionado
    documento_relacionado_codigo: Optional[str] = None
    documento_relacionado_tipo: Optional[str] = None
    documento_relacionado_fecha: Optional[date] = None


class DTEStatusRequest(BaseModel):
    """Consulta de estado de un DTE previamente emitido."""
    tipo_dte: str
    codigo_generacion: str
    ambiente: str = "00"
