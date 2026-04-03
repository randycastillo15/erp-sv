"""
Catálogos oficiales MH — datos de referencia para el gateway.

Fuente: Ministerio de Hacienda El Salvador, Sistema de Transmisión DTE.
Solo se incluyen los catálogos necesarios para los tipos FE (01), CCF (03) y NC (05).
"""

# CAT-001 — Ambiente
CAT_001: dict[str, str] = {
    "00": "Pruebas",
    "01": "Producción",
}

# CAT-002 — Tipo de Documento Tributario Electrónico
CAT_002: dict[str, str] = {
    "01": "Factura",
    "03": "Comprobante de Crédito Fiscal",
    "04": "Nota de Remisión",
    "05": "Nota de Crédito",
    "06": "Nota de Débito",
    "07": "Comprobante de Retención",
    "08": "Comprobante de Liquidación",
    "09": "Documento Contable de Liquidación",
    "11": "Factura de Exportación",
    "14": "Factura de Sujeto Excluido",
    "15": "Comprobante de Donación",
}

# CAT-003 — Modelo de Facturación
CAT_003: dict[int, str] = {
    1: "Previo",
    2: "Diferido",
}

# CAT-004 — Tipo de Operación
CAT_004: dict[int, str] = {
    1: "Normal",
    2: "Contingencia",
}

# CAT-009 — Tipo de Ítem
CAT_009: dict[int, str] = {
    1: "Bienes",
    2: "Servicios",
    3: "Ambos",
    4: "Otros Tributos",
}

# CAT-012 — Departamento
CAT_012: dict[str, str] = {
    "01": "Ahuachapán",
    "02": "Santa Ana",
    "03": "Sonsonate",
    "04": "Chalatenango",
    "05": "La Libertad",
    "06": "San Salvador",
    "07": "Cuscatlán",
    "08": "La Paz",
    "09": "Cabañas",
    "10": "San Vicente",
    "11": "Usulután",
    "12": "San Miguel",
    "13": "Morazán",
    "14": "La Unión",
}

# CAT-014 — Unidad de Medida (parcial — los más comunes)
CAT_014: dict[int, str] = {
    59: "Unidad",
    2:  "Kilogramo",
    3:  "Gramo",
    10: "Litro",
    11: "Mililitro",
    21: "Metro",
    27: "Metro cuadrado",
    28: "Metro cúbico",
    99: "Otra",
}

# CAT-016 — Condición de la Operación
CAT_016: dict[int, str] = {
    1: "Contado",
    2: "Al crédito",
    3: "Otro",
}

# CAT-017 — Tipo de Establecimiento
CAT_017: dict[str, str] = {
    "01": "Sucursal/Agencia",
    "02": "Casa Matriz",
    "04": "Bodega",
    "07": "Patio",
    "20": "Otros",
}

# CAT-022 — Tipo de Documento de Identificación del Receptor
CAT_022: dict[str, str] = {
    "13": "DUI",
    "02": "NIT",
    "03": "Pasaporte",
    "36": "NRC",
    "37": "Otro",
}

# Acceso unificado por código de catálogo
CATALOGS: dict[str, dict] = {
    "CAT-001": CAT_001,
    "CAT-002": CAT_002,
    "CAT-003": CAT_003,
    "CAT-004": CAT_004,
    "CAT-009": CAT_009,
    "CAT-012": CAT_012,
    "CAT-014": CAT_014,
    "CAT-016": CAT_016,
    "CAT-017": CAT_017,
    "CAT-022": CAT_022,
}
