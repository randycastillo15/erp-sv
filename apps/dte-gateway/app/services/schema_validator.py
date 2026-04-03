"""
Validación de JSON DTE contra los schemas oficiales del MH.

Los schemas JSON (Draft 7) deben estar en app/schemas/, extraídos de
svfe-json-schemas.zip. Si el archivo de schema no existe, la validación
retorna una advertencia en lugar de lanzar una excepción, para no bloquear
el flujo mock durante el desarrollo.
"""
import json
import logging
from functools import lru_cache
from pathlib import Path

logger = logging.getLogger(__name__)

_SCHEMA_DIR = Path(__file__).parent.parent / "schemas"

_SCHEMA_MAP: dict[str, str] = {
    "01": "fe-fc-v1.json",
    "03": "fe-ccf-v3.json",
    "05": "fe-nc-v3.json",
    "06": "fe-nd-v3.json",
    "contingencia": "contingencia-schema-v3.json",
    "anulacion": "anulacion-schema-v2.json",
}


@lru_cache(maxsize=10)
def _load_schema(filename: str) -> dict | None:
    path = _SCHEMA_DIR / filename
    if not path.exists():
        logger.warning("Schema no encontrado: %s — validación omitida", path)
        return None
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def validate_dte(dte_json: dict, tipo_dte: str) -> list[str]:
    """
    Valida dte_json contra el schema oficial del MH.

    Returns:
        Lista de strings de error. Lista vacía = documento válido.
        Si el schema no está disponible localmente, retorna lista vacía
        con una advertencia en el log.
    """
    try:
        import jsonschema
    except ImportError:
        logger.warning("jsonschema no instalado — validación de schema omitida")
        return []

    schema_file = _SCHEMA_MAP.get(tipo_dte)
    if not schema_file:
        return [f"tipo_dte no reconocido: {tipo_dte!r}"]

    schema = _load_schema(schema_file)
    if schema is None:
        return []   # schema no disponible localmente — no bloquear

    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(dte_json), key=lambda e: str(e.path))
    return [
        f"{'.'.join(str(p) for p in e.path) or 'root'}: {e.message}"
        for e in errors
    ]
