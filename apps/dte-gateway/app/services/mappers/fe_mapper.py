"""
Mapper FE (tipo 01) — Factura Electrónica.
Convierte DTEEmitRequest → JSON DTE oficial (schema fe-fc-v1.json).

IVA-inclusivo:
  ventaGravada_dte = net_amount (pre-IVA pasado por ERPNext) × 1.13
  ivaItem          = net_amount × 0.13
  precioUni_dte    = precio_unitario × 1.13

Regla DGII:
  Si grand_total < 25 000 USD y receptor sin NIT/NRC,
  NO incluir numDocumento ni correo en el receptor.
"""

from decimal import Decimal

from app.config import IVA_RATE
from app.models.dte_request import DTEEmitRequest

from .common import (
    amount_to_words,
    build_emisor,
    build_identificacion,
    build_pagos_default,
    fec_emi_str,
    hor_emi_str,
    round2,
    round8,
)

_IVA = Decimal(str(IVA_RATE))
_IVA_FACTOR = Decimal("1") + _IVA
_FE_VERSION = 1
_TRIBUTO_IVA = "20"


def build_fe(request: DTEEmitRequest, numero_control: str, codigo_generacion: str) -> dict:
    """
    Construye el JSON completo del DTE tipo FE (tipoDte=01).

    Args:
        request:          DTEEmitRequest validado (con emisor y items).
        numero_control:   Asignado por el gateway (dte_store.next_secuencial).
        codigo_generacion: UUID v4 uppercase asignado por el gateway.

    Returns:
        dict con la estructura completa del DTE según fe-fc-v1.json.
    """
    s = request.emisor
    fec = fec_emi_str(request.posting_date)
    hor = hor_emi_str(request.posting_time)

    identificacion = build_identificacion(
        tipo_dte="01",
        ambiente=request.ambiente,
        numero_control=numero_control,
        codigo_generacion=codigo_generacion,
        fec_emi=fec,
        hor_emi=hor,
        version=_FE_VERSION,
    )

    emisor = build_emisor(s)

    # ── Receptor ─────────────────────────────────────────────────────────────
    receptor = request.receptor
    grand_total = Decimal(str(request.grand_total))

    # Regla MH schema: si montoTotalOperacion >= $1,095 → tipoDocumento y numDocumento obligatorios
    # Para montos menores, el receptor puede ser anónimo (null)
    requiere_identificacion = grand_total >= Decimal("1095.00")
    tiene_identificacion = bool(receptor.tipo_doc_identificacion and receptor.num_documento)

    if requiere_identificacion and not tiene_identificacion:
        # Fallback: registrar como "Otro" sin documento individual identificado
        tipo_doc = "37"
        num_doc = "CF0"  # Consumidor Final — 3 chars mínimo requerido por schema
    else:
        tipo_doc = receptor.tipo_doc_identificacion if tiene_identificacion else None
        num_doc = receptor.num_documento if tiene_identificacion else None

    # Todos los campos son requeridos por el schema (pero permiten null)
    receptor_dte: dict = {
        "nombre":        receptor.nombre or "Consumidor Final",
        "tipoDocumento": tipo_doc,
        "numDocumento":  num_doc,
        "nrc":           None,   # FE: NRC siempre null (es campo de CCF)
        "codActividad":  None,
        "descActividad": None,
        "direccion":     None,
        "telefono":      receptor.telefono,
        "correo":        receptor.correo,
    }

    # ── Cuerpo del documento (ítems) ─────────────────────────────────────────
    cuerpo = []
    total_gravada = Decimal("0")
    total_iva = Decimal("0")
    total_no_sujeta = Decimal("0")
    total_exenta = Decimal("0")

    for item in request.items:
        vg_base = Decimal(str(item.venta_gravada))        # pre-IVA de ERPNext
        vg_dte = (vg_base * _IVA_FACTOR).quantize(Decimal("0.00000000"))
        iva_item = (vg_base * _IVA).quantize(Decimal("0.00000000"))
        precio_dte = (Decimal(str(item.precio_unitario)) * _IVA_FACTOR).quantize(Decimal("0.00000000"))
        descuento = Decimal(str(item.descuento))
        vns = Decimal(str(item.venta_no_sujeta))
        vex = Decimal(str(item.venta_exenta))

        total_gravada += vg_dte
        total_iva += iva_item
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
            "precioUni": round8(precio_dte),
            "montoDescu": round8(descuento),
            "ventaNoSuj": round8(vns),
            "ventaExenta": round8(vex),
            "ventaGravada": round8(vg_dte),
            "tributos": None,   # FE IVA-inclusivo: IVA va en ivaItem/totalIva, no en tributos
            "psv": 0,
            "noGravado": 0,
            "ivaItem": round8(iva_item),
        })

    monto_total = total_gravada + total_no_sujeta + total_exenta

    # ── Resumen ───────────────────────────────────────────────────────────────
    resumen = {
        "totalNoSuj": round2(total_no_sujeta),
        "totalExenta": round2(total_exenta),
        "totalGravada": round2(total_gravada),
        "subTotalVentas": round2(total_gravada + total_no_sujeta + total_exenta),
        "descuNoSuj": 0.0,
        "descuExenta": 0.0,
        "descuGravada": 0.0,
        "porcentajeDescuento": 0.0,
        "totalDescu": 0.0,
        "tributos": None,   # FE: IVA capturado en totalIva, no en tributos
        "subTotal": round2(total_gravada + total_no_sujeta + total_exenta),
        "ivaRete1": 0.0,
        "reteRenta": 0.0,
        "montoTotalOperacion": round2(monto_total),
        "totalNoGravado": 0.0,
        "totalPagar": round2(monto_total),
        "totalLetras": amount_to_words(monto_total.quantize(Decimal("0.01"))),
        "totalIva": round2(total_iva),
        "saldoFavor": 0.0,
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
