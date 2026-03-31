from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

SAMPLE_PAYLOAD = {
    "doctype": "Sales Invoice",
    "docname": "SINV-TEST-001",
    "company": "Mi Empresa SV",
    "posting_date": "2026-03-31",
    "currency": "USD",
    "grand_total": 113.0,
    "customer": "Cliente de Prueba",
}


def test_emit_dte_returns_received():
    response = client.post("/dte/emit", json=SAMPLE_PAYLOAD)
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "received"
    assert body["uuid_dte"] is not None
    assert body["received_at"] is not None
    assert body["mode"] == "mock"
    assert body["echo"] == SAMPLE_PAYLOAD


def test_emit_dte_uuid_is_unique():
    r1 = client.post("/dte/emit", json=SAMPLE_PAYLOAD)
    r2 = client.post("/dte/emit", json=SAMPLE_PAYLOAD)
    assert r1.json()["uuid_dte"] != r2.json()["uuid_dte"]
