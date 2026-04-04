"""
Mapper CCF (tipo 03) — Comprobante de Crédito Fiscal.
Convierte DTEEmitRequest → JSON DTE oficial (schema fe-ccf-v3.json).

IVA-exclusivo:
  ventaGravada = net_amount (pre-IVA, sin modificar)
  IVA se calcula en el resumen: totalGravada × 0.13
  montoTotalOperacion = totalGravada + totalIva

Receptor debe tener los 9 campos requeridos por schema. Lanza ValueError si faltan.
"""

from decimal import Decimal

from app.config import IVA_RATE
from app.models.dte_request import DTEEmitRequest

from .common import (
    amount_to_words,
    build_emisor,
    build_identificacion,
    build_pagos_default,
    build_receptor_ccf_nc,
    fec_emi_str,
    hor_emi_str,
    round2,
    round8,
)

_IVA = Decimal(str(IVA_RATE))
_CCF_VERSION = 3
_TRIBUTO_IVA = "20"


def build_ccf(request: DTEEmitRequest, numero_control: str, codigo_generacion: str) -> dict:
    """
    Construye el JSON completo del DTE tipo CCF (tipoDte=03).

    Raises:
        ValueError: si el receptor no tiene alguno de los 9 campos requeridos (nit, nrc, nombre,
            codActividad, descActividad, direccion, correo).
    """
    # Receptor completo — fail-fast en todos los campos requeridos por schema
    receptor_dte = build_receptor_ccf_nc(request.receptor)

    s = request.emisor
    fec = fec_emi_str(request.posting_date)
    hor = hor_emi_str(request.posting_time)

    identificacion = build_identificacion(
        tipo_dte="03",
        ambiente=request.ambiente,
        numero_control=numero_control,
        codigo_generacion=codigo_generacion,
        fec_emi=fec,
        hor_emi=hor,
        version=_CCF_VERSION,
    )

    emisor = build_emisor(s)

    # ── Cuerpo del documento (ítems) ─────────────────────────────────────────
    cuerpo = []
    total_gravada = Decimal("0")
    total_no_sujeta = Decimal("0")
    total_exenta = Decimal("0")

    for item in request.items:
        vg = Decimal(str(item.venta_gravada))   # pre-IVA sin modificar
        vns = Decimal(str(item.venta_no_sujeta))
        vex = Decimal(str(item.venta_exenta))
        descuento = Decimal(str(item.descuento))

        total_gravada += vg
        total_no_sujeta += vns
        total_exenta += vex

        cuerpo.append({
            "numItem": item.num_item,
            "tipoItem": item.tipo_item,
            "numeroDocumento": None,
            "codigo": item.codigo_interno,
            "codTributo": None,
            "descripcion": item.descripcion,
            "cantidad": round8(item.cantidad),
            "uniMedida": item.unidad_medida,
            "precioUni": round8(item.precio_unitario),
            "montoDescu": round8(descuento),
            "ventaNoSuj": round8(vns),
            "ventaExenta": round8(vex),
            "ventaGravada": round8(vg),
            "tributos": [_TRIBUTO_IVA] if vg > 0 else [],
            "psv": 0,
            "noGravado": 0,
        })

    total_iva = (total_gravada * _IVA).quantize(Decimal("0.01"))
    monto_total = total_gravada + total_iva + total_no_sujeta + total_exenta

    # ── Resumen ───────────────────────────────────────────────────────────────
    resumen = {
        "totalNoSuj": round2(total_no_sujeta),
        "totalExenta": round2(total_exenta),
        "totalGravada": round2(total_gravada),
        "subTotalVentas": round2(total_gravada + total_no_sujeta + total_exenta),
        "descuNoSuj": 0.00,
        "descuExenta": 0.00,
        "descuGravada": 0.00,
        "porcentajeDescuento": 0.00,
        "totalDescu": 0.00,
        "tributos": [
            {
                "codigo": _TRIBUTO_IVA,
                "descripcion": "Impuesto al Valor Agregado 13%",
                "valor": round2(total_iva),
            }
        ] if total_iva > 0 else [],
        "subTotal": round2(total_gravada + total_no_sujeta + total_exenta),
        "ivaPerci1": 0.00,
        "ivaRete1": 0.00,
        "reteRenta": 0.00,
        "montoTotalOperacion": round2(monto_total),
        "totalNoGravado": 0.00,
        "totalPagar": round2(monto_total),
        "totalLetras": amount_to_words(monto_total.quantize(Decimal("0.01"))),
        "saldoFavor": 0.00,
        "condicionOperacion": request.condicion_operacion,
        "pagos": build_pagos_default(monto_total, request.condicion_operacion) or request.pagos or [],
        "numPagoElectronico": None,
    }

    return {
        "identificacion": identificacion,
        "documentoRelacionado": None,
        "emisor": emisor,
        "receptor": receptor_dte,
        "otrosDocumentos": None,
        "ventaTercero": None,
        "cuerpoDocumento": cuerpo,
        "resumen": resumen,
        "extension": None,
        "apendice": None,
    }
