"""
Mapper Contingencia (schema contingencia-v3.json).
Convierte ContingenciaEmitRequest → JSON del evento tipo 14.

Diferencias críticas respecto al DTE regular:
  - identificacion: usa fTransmision/hTransmision (NO fecEmi/horEmi), sin numeroControl
  - emisor: incluye nombreResponsable/tipoDocResponsable/numeroDocResponsable;
    NO incluye nrc/codActividad/descActividad/codEstable (additionalProperties: false)
  - Sin receptor, sin cuerpoDocumento, sin resumen
  - detalleDTE: array de {noItem, codigoGeneracion, tipoDoc} — max 1000 items
  - motivo: tipoContingencia 1-5; si tipo=5 motivoContingencia debe ser no vacío
"""

import uuid
from datetime import datetime, timezone

from app.models.dte_request import ContingenciaEmitRequest

# Etiquetas descriptivas por tipo de contingencia (para logs y opcionalmente el motivo)
_TIPO_CONTINGENCIA_LABEL = {
    1: "No disponibilidad por parte del Ministerio de Hacienda",
    2: "No disponibilidad de internet por parte del Emisor",
    3: "No disponibilidad del sistema del Emisor",
    4: "Otros (Condiciones climáticas/desastres naturales/caso fortuito o fuerza mayor)",
    5: "Otro",
}


def build_contingencia(request: ContingenciaEmitRequest) -> dict:
    """
    Construye el JSON completo del evento de contingencia tipo 14.

    Raises:
        ValueError: si tipoContingencia=5 y motivoContingencia está vacío,
                    o si detalle está vacío o supera 1000 items,
                    o si algún codigoGeneracion en detalle no es UUID válido.
    """
    # Validar motivo libre cuando tipoContingencia=5 (schema lo exige)
    if request.tipo_contingencia == 5 and not request.motivo_contingencia:
        raise ValueError(
            "tipoContingencia=5 (Otro) requiere motivoContingencia con descripción del motivo."
        )

    if not request.detalle:
        raise ValueError("detalle no puede estar vacío (minItems: 1).")
    if len(request.detalle) > 1000:
        raise ValueError(
            f"detalle supera el máximo de 1000 items (tiene {len(request.detalle)})."
        )

    now = datetime.now(timezone.utc)
    event_uuid = str(uuid.uuid4()).upper()
    f_transmision = now.strftime("%Y-%m-%d")
    h_transmision = now.strftime("%H:%M:%S")

    s = request.emisor

    # ── Identificación ────────────────────────────────────────────────────────
    # contingencia-v3: fTransmision/hTransmision (NOT fecEmi/horEmi), SIN numeroControl
    identificacion = {
        "version":          3,
        "ambiente":         request.ambiente,
        "codigoGeneracion": event_uuid,
        "fTransmision":     f_transmision,
        "hTransmision":     h_transmision,
    }

    # ── Emisor con campos específicos de contingencia ─────────────────────────
    # Schema required: nit, nombre, nombreResponsable, tipoDocResponsable,
    #                  numeroDocResponsable, tipoEstablecimiento, telefono, correo
    # additionalProperties: false — NO incluir nrc, codActividad, codEstable, etc.
    emisor = {
        "nit":                  s.nit,
        "nombre":               s.nombre,
        "nombreResponsable":    request.nombre_responsable,
        "tipoDocResponsable":   request.tipo_doc_responsable,
        "numeroDocResponsable": request.num_doc_responsable,
        "tipoEstablecimiento":  s.tipo_establecimiento,
        "codEstableMH":         s.cod_estable_mh or None,
        "codPuntoVenta":        s.cod_punto_venta or None,
        "telefono":             s.telefono or "",
        "correo":               s.correo or "",
    }

    # ── Detalle — array de DTEs offline ──────────────────────────────────────
    detalle_dte = [
        {
            "noItem":           item.no_item,
            "codigoGeneracion": item.codigo_generacion.upper(),
            "tipoDoc":          item.tipo_doc,
        }
        for item in request.detalle
    ]

    # ── Motivo ────────────────────────────────────────────────────────────────
    motivo = {
        "tipoContingencia":   request.tipo_contingencia,
        "motivoContingencia": request.motivo_contingencia or None,
        "fInicio":            request.f_inicio,
        "hInicio":            request.h_inicio,
        "fFin":               request.f_fin,
        "hFin":               request.h_fin,
    }

    return {
        "identificacion": identificacion,
        "emisor":         emisor,
        "detalleDTE":     detalle_dte,
        "motivo":         motivo,
        "_event_uuid":    event_uuid,   # clave interna — eliminada antes de firmar
    }
