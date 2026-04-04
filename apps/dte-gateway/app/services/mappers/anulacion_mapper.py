"""
Mapper Anulación (schema anulacion-v2.json).
Convierte AnulacionRequest → JSON del evento de invalidación DTE.

Reglas schema:
  - version = 2 (const)
  - identificacion: codigoGeneracion (UUID nuevo), fecAnula, horAnula — SIN numeroControl
  - emisor: campos propios del schema (sin nrc/codActividad/descActividad)
  - documento.codigoGeneracionR:
      - tipoAnulacion=2 → DEBE ser null (schema type: "null")
      - tipoAnulacion=1 o 3 → DEBE ser UUID string no vacío
  - documento.montoIva: type ["number","null"] — permitido null (documentos legacy)
  - motivo.motivoAnulacion: type ["string","null"] — permitido null
"""

import uuid
from datetime import datetime, timezone

from app.models.dte_request import AnulacionRequest


def build_anulacion(request: AnulacionRequest) -> dict:
    """
    Construye el JSON completo del evento de invalidación DTE.

    Raises:
        ValueError: si tipo_anulacion 1 o 3 no tienen codigo_generacion_reemplazo,
                    o si tipo_anulacion 2 tiene codigo_generacion_reemplazo no nulo.
    """
    # Validar lógica codigoGeneracionR según tipoAnulacion
    if request.tipo_anulacion == 2:
        if request.codigo_generacion_reemplazo:
            raise ValueError(
                "tipoAnulacion=2 (sin reemplazo): codigoGeneracionR debe ser null. "
                "No incluya codigo_generacion_reemplazo para este tipo de anulación."
            )
        codigo_generacion_r = None
    elif request.tipo_anulacion in (1, 3):
        if not request.codigo_generacion_reemplazo:
            raise ValueError(
                f"tipoAnulacion={request.tipo_anulacion} requiere codigo_generacion_reemplazo "
                "(UUID del DTE que reemplaza al anulado)."
            )
        codigo_generacion_r = request.codigo_generacion_reemplazo.upper()
    else:
        raise ValueError(
            f"tipoAnulacion='{request.tipo_anulacion}' inválido. Solo se permiten 1, 2 o 3."
        )

    now = datetime.now(timezone.utc)
    event_uuid = str(uuid.uuid4()).upper()
    fec_anula = request.fecha_anula
    hor_anula = now.strftime("%H:%M:%S")

    s = request.emisor

    # ── Identificación del evento ─────────────────────────────────────────────
    # anulacion-v2: sin numeroControl, usa fecAnula/horAnula
    identificacion = {
        "version":          2,
        "ambiente":         request.ambiente,
        "codigoGeneracion": event_uuid,
        "fecAnula":         fec_anula,
        "horAnula":         hor_anula,
    }

    # ── Emisor — campos específicos del schema anulacion-v2 ──────────────────
    # Schema: required = [nit, nombre, tipoEstablecimiento, telefono, correo, codEstable,
    #                      codPuntoVenta, nomEstablecimiento]
    # additionalProperties: false — NO incluir nrc, codActividad, descActividad
    emisor = {
        "nit":                s.nit,
        "nombre":             s.nombre,
        "tipoEstablecimiento": s.tipo_establecimiento,
        "nomEstablecimiento": s.nombre_comercial or None,
        "codEstableMH":       s.cod_estable_mh or None,
        "codEstable":         s.cod_estable or None,
        "codPuntoVentaMH":    s.cod_punto_venta_mh or None,
        "codPuntoVenta":      s.cod_punto_venta or None,
        "telefono":           s.telefono or None,
        "correo":             s.correo,
    }

    # ── Documento a anular ───────────────────────────────────────────────────
    documento = {
        "tipoDte":           request.tipo_dte,
        "codigoGeneracion":  request.codigo_generacion_original.upper(),
        "selloRecibido":     request.sello_recibido,
        "numeroControl":     request.numero_control,
        "fecEmi":            request.fec_emi,
        "montoIva":          request.monto_iva,   # null si legacy
        "codigoGeneracionR": codigo_generacion_r,
        "tipoDocumento":     request.tipo_documento_receptor,
        "numDocumento":      request.num_documento_receptor,
        "nombre":            request.nombre_receptor,
    }

    # ── Motivo ────────────────────────────────────────────────────────────────
    motivo = {
        "tipoAnulacion":    request.tipo_anulacion,
        "motivoAnulacion":  request.motivo_anulacion or None,
        "nombreResponsable": request.nombre_responsable,
        "tipDocResponsable": request.tip_doc_responsable,
        "numDocResponsable": request.num_doc_responsable,
        "nombreSolicita":   request.nombre_solicita,
        "tipDocSolicita":   request.tip_doc_solicita,
        "numDocSolicita":   request.num_doc_solicita,
    }

    return {
        "identificacion": identificacion,
        "emisor":         emisor,
        "documento":      documento,
        "motivo":         motivo,
        "_event_uuid":    event_uuid,   # clave interna — eliminada antes de firmar
    }
