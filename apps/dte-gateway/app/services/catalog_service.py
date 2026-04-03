"""
Servicio de acceso a catálogos oficiales MH.

Los catálogos se mantienen en app/catalogs/cat_data.py.
Este módulo provee la API de acceso para el resto de los servicios.
"""
from app.catalogs.cat_data import CATALOGS


def get_label(cat_code: str, key) -> str | None:
    """
    Retorna la descripción de una clave dentro de un catálogo MH.

    Args:
        cat_code: Código del catálogo, ej. "CAT-002".
        key:      Clave a buscar (str o int según el catálogo).

    Returns:
        Descripción o None si no se encuentra.
    """
    return CATALOGS.get(cat_code, {}).get(key)


def validate_catalog_key(cat_code: str, key) -> bool:
    """Verifica que una clave exista en el catálogo indicado."""
    return key in CATALOGS.get(cat_code, {})
