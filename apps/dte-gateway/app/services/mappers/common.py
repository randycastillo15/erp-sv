"""
Funciones compartidas entre los mappers DTE (FE, CCF, NC).
"""

from datetime import date, datetime, timezone
from decimal import ROUND_HALF_UP, Decimal
from typing import Optional

from num2words import num2words

from app.models.dte_request import DTEEmisorSettings


def round8(value) -> float:
    """Redondea a 8 decimales y retorna float (ítems del DTE — schema exige number)."""
    return float(Decimal(str(value)).quantize(Decimal("0.00000000"), rounding=ROUND_HALF_UP))


def round2(value) -> float:
    """Redondea a 2 decimales y retorna float (resumen del DTE — schema exige number)."""
    return float(Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def amount_to_words(amount: Decimal) -> str:
    """
    Convierte un monto a palabras en formato MH.
    Ej: Decimal("11.30") → "ONCE 30/100 DOLARES"
    """
    entero = int(amount)
    centavos = int(round((amount - entero) * 100))
    palabras = num2words(entero, lang="es").upper()
    # Normalizar separadores que num2words puede variar
    palabras = palabras.replace(" Y ", " ").strip()
    return f"{palabras} {centavos:02d}/100 DOLARES"


def build_identificacion(
    tipo_dte: str,
    ambiente: str,
    numero_control: str,
    codigo_generacion: str,
    fec_emi: str,
    hor_emi: str,
    version: int,
    tipo_operacion: int = 1,
    tipo_modelo: int = 1,
) -> dict:
    """Construye el bloque 'identificacion' del DTE."""
    return {
        "version": version,
        "ambiente": ambiente,
        "tipoDte": tipo_dte,
        "numeroControl": numero_control,
        "codigoGeneracion": codigo_generacion,
        "tipoModelo": tipo_modelo,
        "tipoOperacion": tipo_operacion,
        "tipoContingencia": None,
        "motivoContin": None,
        "fecEmi": fec_emi,
        "horEmi": hor_emi,
        "tipoMoneda": "USD",
    }


def build_emisor(s: DTEEmisorSettings) -> dict:
    """Construye el bloque 'emisor' del DTE a partir de DTEEmisorSettings."""
    return {
        "nit": s.nit,
        "nrc": s.nrc,
        "nombre": s.nombre,
        "codActividad": s.cod_actividad,
        "descActividad": s.desc_actividad,
        "nombreComercial": s.nombre_comercial,
        "tipoEstablecimiento": s.tipo_establecimiento,
        "direccion": {
            "departamento": s.departamento,
            "municipio": s.municipio,
            "complemento": s.complemento,
        },
        "telefono": s.telefono,
        "correo": s.correo,
        "codEstableMH": s.cod_estable_mh,
        "codEstable": s.cod_estable,
        "codPuntoVentaMH": s.cod_punto_venta_mh,
        "codPuntoVenta": s.cod_punto_venta,
    }


def build_pagos_default(total: Decimal, condicion: int) -> list[dict]:
    """
    Construye la lista de pagos por defecto.
    condicion=1 (contado) → efectivo "01"
    condicion=2 (crédito) → crédito "03"
    Otros → sin pagos (vacío).
    """
    if condicion == 1:
        return [{"codigo": "01", "montoPago": round2(total), "referencia": None, "plazo": None, "periodo": None}]
    if condicion == 2:
        return [{"codigo": "03", "montoPago": round2(total), "referencia": None, "plazo": None, "periodo": None}]
    return []


def fec_emi_str(posting_date: date) -> str:
    """Formatea la fecha de emisión como YYYY-MM-DD."""
    return str(posting_date)


def hor_emi_str(posting_time: Optional[str]) -> str:
    """Formatea la hora de emisión como HH:MM:SS. Usa hora UTC actual si no se provee."""
    if posting_time:
        # Strip microseconds: "4:48:49.839007" → "4:48:49"
        raw = str(posting_time).split(".")[0]
        parts = raw.split(":")
        while len(parts) < 3:
            parts.append("00")
        # Ensure zero-padded HH:MM:SS
        h, m, s = parts[0], parts[1], parts[2]
        return f"{int(h):02d}:{int(m):02d}:{int(s):02d}"
    return datetime.now(timezone.utc).strftime("%H:%M:%S")
