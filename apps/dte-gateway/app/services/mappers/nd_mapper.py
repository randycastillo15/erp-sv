"""
Mapper ND (tipo 06) — Nota de Débito.
Convierte DTEEmitRequest → JSON DTE oficial (schema fe-nd-v3.json).

Reglas:
  - tipoDte="06", version=3 (confirmado en svfe-json-schemas.zip/fe-nd-v3.json).
  - documentoRelacionado.tipoDocumento: solo "03" (CCF) o "07".
    Lanza ValueError si el tipo relacionado es inválido.
  - documento_relacionado_codigo debe ser el codigoGeneracion UUID del CCF original.
  - Receptor igual que CCF/NC: 9 campos requeridos por schema.
  - Montos POSITIVOS — exclusiveMinimum: 0 en schema (ND es cargo adicional).
  - Lógica de cuerpo y resumen idéntica a NC (mismo schema).
"""

from decimal import Decimal

from app.config import IVA_RATE
from app.models.dte_request import DTEEmitRequest

from .common import (
    amount_to_words,
    build_emisor_nc,
    build_identificacion,
    build_receptor_ccf_nc,
    fec_emi_str,
    hor_emi_str,
    round2,
    round8,
)

_IVA = Decimal(str(IVA_RATE))
_ND_VERSION = 3
_TRIBUTO_IVA = "20"


def build_nd(request: DTEEmitRequest, numero_control: str, codigo_generacion: str) -> dict:
    """
    Construye el JSON completo del DTE tipo ND (tipoDte=06).

    Raises:
        ValueError: si documento_relacionado_codigo es None, si tipoDocumento relacionado
            no es "03" o "07", o si el receptor no tiene los 9 campos requeridos por schema.
    """
    if not request.documento_relacionado_codigo:
        raise ValueError(
            "ND (tipo 06) requiere documento_relacionado_codigo. "
            "Incluya el codigoGeneracion (UUID) del CCF original al que se aplica el débito."
        )

    # documentoRelacionado.tipoDocumento: schema enum ["03","07"]
    tipo_rel = request.documento_relacionado_tipo or "03"
    if tipo_rel not in ("03", "07"):
        raise ValueError(
            f"ND: tipoDocumento relacionado '{tipo_rel}' no válido. "
            "Solo '03' (CCF) o '07' son aceptados por schema MH."
        )

    # Receptor completo — misma exigencia que CCF/NC (9 campos requeridos)
    receptor_dte = build_receptor_ccf_nc(request.receptor)

    s = request.emisor
    fec = fec_emi_str(request.posting_date)
    hor = hor_emi_str(request.posting_time)

    identificacion = build_identificacion(
        tipo_dte="06",
        ambiente=request.ambiente,
        numero_control=numero_control,
        codigo_generacion=codigo_generacion,
        fec_emi=fec,
        hor_emi=hor,
        version=_ND_VERSION,
    )

    # ND emisor: igual que NC (sin codEstable/MH, sin codPuntoVenta/MH)
    emisor = build_emisor_nc(s)

    # ── Documento relacionado ─────────────────────────────────────────────────
    documento_relacionado = [{
        "tipoDocumento":   tipo_rel,
        "tipoGeneracion":  2,   # 2 = DTE electrónico
        "numeroDocumento": request.documento_relacionado_codigo,
        "fechaEmision":    str(request.documento_relacionado_fecha) if request.documento_relacionado_fecha else fec,
    }]

    # ── Cuerpo del documento (ítems) ─────────────────────────────────────────
    # ND: schema exige cantidad y montos POSITIVOS (exclusiveMinimum: 0).
    # El cargo adicional está implícito en el tipo de documento ND.
    # tributos: ["20"] o null — NOT [] (schema minItems: 1 cuando es array).
    # numeroDocumento: UUID del CCF relacionado (≤36 chars).
    cuerpo = []
    total_gravada = Decimal("0")
    total_no_sujeta = Decimal("0")
    total_exenta = Decimal("0")

    for item in request.items:
        vg = abs(Decimal(str(item.venta_gravada)))
        vns = abs(Decimal(str(item.venta_no_sujeta)))
        vex = abs(Decimal(str(item.venta_exenta)))
        descuento = abs(Decimal(str(item.descuento)))
        cantidad = abs(Decimal(str(item.cantidad)))
        precio_uni = abs(Decimal(str(item.precio_unitario)))

        total_gravada += vg
        total_no_sujeta += vns
        total_exenta += vex

        cuerpo.append({
            "numItem":         item.num_item,
            "tipoItem":        item.tipo_item,
            "numeroDocumento": request.documento_relacionado_codigo,
            "codigo":          item.codigo_interno,
            "codTributo":      None,
            "descripcion":     item.descripcion,
            "cantidad":        round8(cantidad),
            "uniMedida":       item.unidad_medida,
            "precioUni":       round8(precio_uni),
            "montoDescu":      round8(descuento),
            "ventaNoSuj":      round8(vns),
            "ventaExenta":     round8(vex),
            "ventaGravada":    round8(vg),
            "tributos":        [_TRIBUTO_IVA] if vg > 0 else None,
        })

    total_iva = (total_gravada * _IVA).quantize(Decimal("0.01"))
    monto_total = total_gravada + total_iva + total_no_sujeta + total_exenta

    # ── Resumen ───────────────────────────────────────────────────────────────
    resumen = {
        "totalNoSuj":        round2(total_no_sujeta),
        "totalExenta":       round2(total_exenta),
        "totalGravada":      round2(total_gravada),
        "subTotalVentas":    round2(total_gravada + total_no_sujeta + total_exenta),
        "descuNoSuj":        0.00,
        "descuExenta":       0.00,
        "descuGravada":      0.00,
        "totalDescu":        0.00,
        "tributos": [
            {
                "codigo": _TRIBUTO_IVA,
                "descripcion": "Impuesto al Valor Agregado 13%",
                "valor": round2(total_iva),
            }
        ] if total_iva > 0 else [],
        "subTotal":            round2(total_gravada + total_no_sujeta + total_exenta),
        "ivaPerci1":           0.00,
        "ivaRete1":            0.00,
        "reteRenta":           0.00,
        "montoTotalOperacion": round2(monto_total),
        "totalLetras":         amount_to_words(monto_total.quantize(Decimal("0.01"))),
        "condicionOperacion":  request.condicion_operacion,
        "numPagoElectronico":  None,   # requerido por fe-nd-v3.json; null válido (type: [string, null])
    }

    return {
        "identificacion":       identificacion,
        "documentoRelacionado": documento_relacionado,
        "emisor":               emisor,
        "receptor":             receptor_dte,
        "ventaTercero":         None,
        "cuerpoDocumento":      cuerpo,
        "resumen":              resumen,
        "extension":            None,
        "apendice":             None,
    }
