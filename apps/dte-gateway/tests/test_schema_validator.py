"""Tests para schema_validator: bloqueante cuando schema existe."""

import json
import pytest
from unittest.mock import patch

from app.services.schema_validator import validate_dte


def test_schema_ausente_no_bloquea(tmp_path, monkeypatch):
    """Si el schema no existe localmente, retorna lista vacía (no bloquea)."""
    import app.services.schema_validator as sv
    monkeypatch.setattr(sv, "_SCHEMA_DIR", tmp_path)
    sv._load_schema.cache_clear()
    errors = validate_dte({"cualquier": "dato"}, "01")
    assert errors == []


def test_schema_presente_valida_estructura(tmp_path, monkeypatch):
    """Con schema mínimo presente, un JSON vacío debe producir errores."""
    import app.services.schema_validator as sv
    # Schema mínimo: exige campo 'identificacion'
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": ["identificacion"],
        "properties": {
            "identificacion": {"type": "object"},
        },
    }
    schema_file = tmp_path / "fe-fc-v1.json"
    schema_file.write_text(json.dumps(schema), encoding="utf-8")

    monkeypatch.setattr(sv, "_SCHEMA_DIR", tmp_path)
    sv._load_schema.cache_clear()

    errors = validate_dte({}, "01")
    assert len(errors) > 0
    assert any("identificacion" in e for e in errors)


def test_schema_valido_retorna_lista_vacia(tmp_path, monkeypatch):
    """JSON que cumple el schema mínimo retorna []."""
    import app.services.schema_validator as sv
    schema = {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "type": "object",
        "required": ["identificacion"],
        "properties": {
            "identificacion": {"type": "object"},
        },
    }
    schema_file = tmp_path / "fe-fc-v1.json"
    schema_file.write_text(json.dumps(schema), encoding="utf-8")

    monkeypatch.setattr(sv, "_SCHEMA_DIR", tmp_path)
    sv._load_schema.cache_clear()

    errors = validate_dte({"identificacion": {}}, "01")
    assert errors == []


def test_tipo_dte_no_reconocido():
    """tipo_dte desconocido retorna un error descriptivo."""
    errors = validate_dte({}, "99")
    assert len(errors) == 1
    assert "99" in errors[0]
