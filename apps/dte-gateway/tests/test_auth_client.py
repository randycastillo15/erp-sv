"""Tests para auth_client: cache hit/miss, invalidate_token."""

import time
import pytest
from unittest.mock import MagicMock, patch

import app.services.auth_client as auth_client_module


@pytest.fixture(autouse=True)
def clear_cache():
    """Limpia el cache de tokens antes de cada test."""
    with auth_client_module._cache_lock:
        auth_client_module._cache.clear()
    yield
    with auth_client_module._cache_lock:
        auth_client_module._cache.clear()


def _mock_mh_response(token: str = "test-jwt-token"):
    mock_resp = MagicMock()
    mock_resp.json.return_value = {"status": "OK", "body": {"token": f"Bearer {token}"}}
    mock_resp.raise_for_status.return_value = None
    return mock_resp


def test_get_token_llama_api_en_miss(monkeypatch):
    monkeypatch.setenv("MH_API_PASSWORD", "pwd")
    with patch("app.services.auth_client.requests.post", return_value=_mock_mh_response()) as mock_post:
        token = auth_client_module.get_token("06140101911019", "00")
    assert token == "test-jwt-token"
    assert mock_post.call_count == 1


def test_get_token_cache_hit_no_llama_api(monkeypatch):
    monkeypatch.setenv("MH_API_PASSWORD", "pwd")
    with patch("app.services.auth_client.requests.post", return_value=_mock_mh_response()) as mock_post:
        auth_client_module.get_token("06140101911019", "00")
        token2 = auth_client_module.get_token("06140101911019", "00")
    assert token2 == "test-jwt-token"
    assert mock_post.call_count == 1  # solo un HTTP call


def test_get_token_expirado_renueva(monkeypatch):
    monkeypatch.setenv("MH_API_PASSWORD", "pwd")
    with patch("app.services.auth_client.requests.post", return_value=_mock_mh_response("token-v2")) as mock_post:
        # Insertar token expirado manualmente
        with auth_client_module._cache_lock:
            auth_client_module._cache[("06140101911019", "00")] = ("old-token", time.monotonic() - 1)
        token = auth_client_module.get_token("06140101911019", "00")
    assert token == "token-v2"
    assert mock_post.call_count == 1


def test_invalidate_token_fuerza_renovacion(monkeypatch):
    monkeypatch.setenv("MH_API_PASSWORD", "pwd")
    with patch("app.services.auth_client.requests.post", return_value=_mock_mh_response()) as mock_post:
        auth_client_module.get_token("06140101911019", "00")
        auth_client_module.invalidate_token("06140101911019", "00")
        auth_client_module.get_token("06140101911019", "00")
    assert mock_post.call_count == 2
