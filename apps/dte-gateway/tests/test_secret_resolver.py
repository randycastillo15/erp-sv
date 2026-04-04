"""Tests para secret_resolver: error descriptivo cuando env var falta."""

import pytest
import app.services.secret_resolver as resolver


def test_get_mh_api_password_sin_env_lanza_error(monkeypatch):
    monkeypatch.delenv("MH_API_PASSWORD", raising=False)
    with pytest.raises(RuntimeError, match="MH_API_PASSWORD"):
        resolver.get_mh_api_password()


def test_get_firmador_password_sin_env_lanza_error(monkeypatch):
    monkeypatch.delenv("FIRMADOR_PASSWORD_PRI", raising=False)
    with pytest.raises(RuntimeError, match="FIRMADOR_PASSWORD_PRI"):
        resolver.get_firmador_password()


def test_get_mh_api_password_con_env(monkeypatch):
    monkeypatch.setenv("MH_API_PASSWORD", "secreto123")
    assert resolver.get_mh_api_password() == "secreto123"


def test_get_firmador_password_con_env(monkeypatch):
    monkeypatch.setenv("FIRMADOR_PASSWORD_PRI", "clave_privada_456")
    assert resolver.get_firmador_password() == "clave_privada_456"
