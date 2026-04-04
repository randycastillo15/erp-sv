"""Tests para dte_service: flujo completo con mocks."""

from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from app.models.dte_request import (
    DTEEmitRequest,
    DTEEmisorSettings,
    DTEItemRequest,
    DTEReceptorRequest,
)
import app.services.dte_store as store_module
from app.services import dte_service


@pytest.fixture(autouse=True)
def in_memory_db(tmp_path, monkeypatch):
    db_path = tmp_path / "test_service.db"
    monkeypatch.setattr(store_module, "_DB_PATH", db_path)
    store_module._init_db()
    yield


@pytest.fixture
def base_request() -> DTEEmitRequest:
    return DTEEmitRequest(
        tipo_dte="01",
        ambiente="00",
        docname="SINV-SVC-001",
        company="Mi Empresa SV",
        posting_date=date(2026, 4, 1),
        receptor=DTEReceptorRequest(nombre="Consumidor Final"),
        items=[
            DTEItemRequest(
                num_item=1,
                tipo_item=2,
                descripcion="Servicio",
                cantidad=Decimal("1"),
                precio_unitario=Decimal("10"),
                venta_gravada=Decimal("10"),
            )
        ],
        grand_total=Decimal("11.30"),
        total_iva=Decimal("1.30"),
        emisor=DTEEmisorSettings(
            nit="06140101911019",
            nrc="123456-7",
            nombre="Mi Empresa SV",
            cod_actividad="47191",
            desc_actividad="Comercio",
            tipo_establecimiento="02",
            cod_estable_mh="0001",
            cod_estable="0001",
            cod_punto_venta_mh="0001",
            cod_punto_venta="0001",
            departamento="06",
            municipio="23",
            complemento="Calle 1",
            url_firmador="http://localhost:8113/firma/firmardocumento/",
        ),
        idempotency_key="test:Sales Invoice:SINV-SVC-001:01:00",
        skip_schema_validation=True,  # tests de unit no tienen schema real
    )


def _mock_mh_procesado():
    return {
        "estado": "PROCESADO",
        "selloRecibido": "SELLO-123",
        "fhProcesamiento": "2026-04-01T12:00:00",
        "clasificaMsg": "1",
        "codigoMsg": "001",
        "observaciones": [],
    }


@patch("app.services.dte_service.signer_client.sign_dte", return_value="jws.header.sig")
@patch("app.services.dte_service.auth_client.get_token", return_value="bearer-token")
@patch("app.services.dte_service.mh_client.send_dte", return_value=_mock_mh_procesado())
def test_emit_procesado(mock_mh, mock_auth, mock_sign, base_request):
    response = dte_service.emit(base_request)
    assert response.status == "procesado"
    assert response.estado == "PROCESADO"
    assert response.sello_recibido == "SELLO-123"
    assert response.generation_code is not None
    assert response.control_number is not None
    # Verificar que send_dte recibe jws como kwarg
    call_kwargs = mock_mh.call_args
    assert call_kwargs.kwargs["jws"] == "jws.header.sig"


@patch("app.services.dte_service.signer_client.sign_dte", return_value="jws.header.sig")
@patch("app.services.dte_service.auth_client.get_token", return_value="bearer-token")
@patch("app.services.dte_service.mh_client.send_dte", return_value={"estado": "RECHAZADO", "observaciones": ["Error de prueba"]})
def test_emit_rechazado(mock_mh, mock_auth, mock_sign, base_request):
    response = dte_service.emit(base_request)
    assert response.status == "rechazado"
    assert response.estado == "RECHAZADO"


@patch("app.services.dte_service.signer_client.sign_dte", return_value="jws.header.sig")
@patch("app.services.dte_service.auth_client.get_token", return_value="bearer-token")
@patch("app.services.dte_service.mh_client.send_dte", return_value=_mock_mh_procesado())
def test_idempotencia_segunda_llamada_retorna_cached(mock_mh, mock_auth, mock_sign, base_request):
    r1 = dte_service.emit(base_request)
    r2 = dte_service.emit(base_request)
    assert r1.generation_code == r2.generation_code
    # MH solo se llama una vez
    assert mock_mh.call_count == 1


def test_tipo_dte_no_soportado_lanza_key_error(base_request):
    base_request.tipo_dte = "99"
    base_request.idempotency_key = "test:Sales Invoice:SINV-SVC-001:99:00"
    with pytest.raises(KeyError, match="99"):
        dte_service.emit(base_request)


@patch("app.services.dte_service.signer_client.sign_dte", side_effect=RuntimeError("Firmador caído"))
@patch("app.services.dte_service.auth_client.get_token", return_value="bearer-token")
def test_error_firmador_lanza_runtime(mock_auth, mock_sign, base_request):
    with pytest.raises(RuntimeError, match="Firmador"):
        dte_service.emit(base_request)
