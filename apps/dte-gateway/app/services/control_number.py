"""Generación de Número de Control y Código de Generación (formato oficial MH)."""
import uuid


def generate_codigo_generacion() -> str:
    """
    UUID v4 en MAYÚSCULAS.
    Formato: XXXXXXXX-XXXX-4XXX-YXXX-XXXXXXXXXXXX (36 chars con guiones).
    """
    return str(uuid.uuid4()).upper()


def generate_numero_control(
    tipo_dte: str,
    cod_estable_mh: str,
    cod_punto_venta_mh: str,
    secuencial: int,
) -> str:
    """
    Genera el Número de Control en el formato oficial MH.

    Formato: DTE-{tipoDte}-{codEstable}{codPuntoVenta}-{secuencial15d}
    Total:   31 caracteres incluyendo guiones.
    Ejemplo: DTE-01-00010001-000000000000001

    Args:
        tipo_dte:           "01", "03", "05"
        cod_estable_mh:     4 chars (código establecimiento asignado por MH)
        cod_punto_venta_mh: 4 chars (código punto de venta asignado por MH)
        secuencial:         entero 1..999_999_999_999_999 (reinicia cada año)

    Raises:
        ValueError: si algún argumento no cumple el formato requerido.
    """
    if len(cod_estable_mh) != 4:
        raise ValueError(f"cod_estable_mh debe tener exactamente 4 chars: {cod_estable_mh!r}")
    if len(cod_punto_venta_mh) != 4:
        raise ValueError(f"cod_punto_venta_mh debe tener exactamente 4 chars: {cod_punto_venta_mh!r}")
    if not 1 <= secuencial <= 999_999_999_999_999:
        raise ValueError(f"secuencial fuera de rango [1, 999999999999999]: {secuencial}")

    ocho_chars = f"{cod_estable_mh}{cod_punto_venta_mh}"
    return f"DTE-{tipo_dte}-{ocho_chars}-{secuencial:015d}"
