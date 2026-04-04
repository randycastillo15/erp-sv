"""
Contrato de entrada del gateway DTE — versión 2.
Define qué envía ERPNext al gateway por cada tipo de operación.

IMPORTANTE: DTEEmisorSettings NO incluye secretos (password_pri, api_password).
El gateway los resuelve internamente via secret_resolver.py.
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
    tributos: Optional[list[str]] = Field(default_factory=list)   # códigos de tributos especiales (no IVA en FE)
    codigo_interno: Optional[str] = None


class DTEDireccionRequest(BaseModel):
    """Dirección del receptor (CCF y NC)."""
    departamento: str    # CAT-012
    municipio: str       # CAT-013
    complemento: str


class DTEReceptorRequest(BaseModel):
    """Datos del receptor (cliente)."""
    nombre: Optional[str] = None
    tipo_doc_identificacion: Optional[str] = None    # CAT-022
    num_documento: Optional[str] = None
    nit: Optional[str] = None
    nrc: Optional[str] = None
    correo: Optional[str] = None
    telefono: Optional[str] = None
    cod_actividad: Optional[str] = None              # CAT-019 (requerido para CCF)
    desc_actividad: Optional[str] = None             # requerido para CCF/NC
    nombre_comercial: Optional[str] = None           # nullable en schema, incluir siempre
    direccion: Optional[DTEDireccionRequest] = None  # requerido para CCF/NC


class DTEEmisorSettings(BaseModel):
    """
    Datos del emisor enviados desde ERPNext.

    SIN credenciales: password_pri y api_password NO se incluyen aquí.
    El gateway los resuelve internamente desde variables de entorno.
    """
    nit: str                          # 14 dígitos sin guiones
    nrc: str
    nombre: str
    nombre_comercial: Optional[str] = None
    cod_actividad: str
    desc_actividad: str
    tipo_establecimiento: str         # CAT-017
    cod_estable_mh: str               # 4 chars — asignado por MH (ej. "M001")
    cod_estable: Optional[str] = None
    cod_punto_venta_mh: str           # 4 chars — asignado por MH (ej. "P001")
    cod_punto_venta: Optional[str] = None
    departamento: str                 # CAT-012
    municipio: str
    complemento: str
    telefono: Optional[str] = None
    correo: Optional[str] = None
    url_firmador: str                 # URL del firmador (no es secreto)
    nit_firmador: Optional[str] = None  # NIT 14 dígitos para lookup de cert; si None usa nit


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
    # Sprint 2: emisor + idempotencia
    emisor: DTEEmisorSettings
    idempotency_key: str                  # "{site}:{doctype}:{docname}:{tipo_dte}:{ambiente}"
    skip_schema_validation: bool = False  # escape hatch diagnóstico — no usar en producción


class DTEStatusRequest(BaseModel):
    """Consulta de estado de un DTE previamente emitido."""
    tipo_dte: str
    codigo_generacion: str
    ambiente: str = "00"
    nit_emisor: str                   # el gateway lo usa como clave de cache de token
    # api_password NO se incluye — el gateway lo resuelve via secret_resolver


class AnulacionRequest(BaseModel):
    """
    Payload para anular un DTE ya PROCESADO por MH (schema anulacion-v2.json).

    `sello_recibido` y `numero_control` se leen de sv_sello_recepcion y
    sv_dte_control_number del Sales Invoice original.

    `monto_iva` → fuente principal: sv_total_iva (persistido en emit_dte).
    Si vacío (documento legacy pre-Sprint 4), fallback a total_taxes_and_charges
    con log de advertencia. Si ambos vacíos: None (schema lo permite).
    """
    ambiente: str = "00"
    emisor: DTEEmisorSettings
    # DTE a anular
    tipo_dte: str                            # "01", "03", "05", etc.
    codigo_generacion_original: str          # UUID — sv_dte_generation_code
    sello_recibido: str                      # 40 chars A-Z0-9 — sv_sello_recepcion
    numero_control: str                      # sv_dte_control_number
    fec_emi: str                             # YYYY-MM-DD del DTE original
    monto_iva: Optional[float] = None        # null permitido por schema
    # Receptor del DTE original
    tipo_documento_receptor: str             # CAT-022: "36"=NIT, "13"=DUI
    num_documento_receptor: str
    nombre_receptor: str
    # Motivo de anulación
    tipo_anulacion: int                      # 1=Error/reemplazar, 2=Sin reemplazo, 3=Devolución
    motivo_anulacion: str
    codigo_generacion_reemplazo: Optional[str] = None   # UUID solo si tipo 1 o 3
    # Responsable técnico que ejecuta la anulación
    nombre_responsable: str
    tip_doc_responsable: str
    num_doc_responsable: str
    # Solicitante (quien pide la anulación)
    nombre_solicita: str
    tip_doc_solicita: str
    num_doc_solicita: str
    fecha_anula: str                         # YYYY-MM-DD
    idempotency_key: str


class ContingenciaDTEItem(BaseModel):
    """Un DTE emitido offline incluido en el evento de contingencia."""
    no_item: int
    codigo_generacion: str   # UUID del DTE offline
    tipo_doc: str            # "01", "03", "05", etc.


class ContingenciaEmitRequest(BaseModel):
    """
    Payload para transmitir un evento de contingencia tipo 14 (schema contingencia-v3.json).

    El evento agrupa hasta 1000 DTEs emitidos offline durante un período sin MH disponible.
    Tiene su propio codigoGeneracion (UUID nuevo, distinto a los DTEs listados).
    No tiene numeroControl — identificacion usa fTransmision/hTransmision.
    """
    ambiente: str = "00"
    emisor: DTEEmisorSettings
    # Responsable técnico — 3 campos extra del emisor de contingencia (no presentes en emisor regular)
    nombre_responsable: str
    tipo_doc_responsable: str
    num_doc_responsable: str
    # Período de contingencia
    tipo_contingencia: int              # 1-5
    motivo_contingencia: Optional[str] = None   # requerido si tipo=5
    f_inicio: str                       # YYYY-MM-DD
    h_inicio: str              # HH:MM:SS
    f_fin: str                 # YYYY-MM-DD
    h_fin: str                 # HH:MM:SS
    # DTEs offline a reportar (1-1000)
    detalle: list[ContingenciaDTEItem]
    idempotency_key: str
