"""Tests para los mappers DTE: FE, CCF, NC y funciones comunes."""

from datetime import date
from decimal import Decimal

import pytest

from app.models.dte_request import (
    DTEEmitRequest,
    DTEEmisorSettings,
    DTEItemRequest,
    DTEReceptorRequest,
)
from app.services.mappers.common import amount_to_words, round2, round8
from app.services.mappers.fe_mapper import build_fe
from app.services.mappers.ccf_mapper import build_ccf
from app.services.mappers.nc_mapper import build_nc


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def emisor() -> DTEEmisorSettings:
    return DTEEmisorSettings(
        nit="06140101911019",
        nrc="123456-7",
        nombre="Empresa de Prueba SA de CV",
        cod_actividad="47191",
        desc_actividad="Venta al por mayor de otros productos",
        tipo_establecimiento="02",
        cod_estable_mh="0001",
        cod_estable="0001",
        cod_punto_venta_mh="0001",
        cod_punto_venta="0001",
        departamento="06",
        municipio="23",
        complemento="Calle Principal #1",
        url_firmador="http://localhost:8113/firma/firmardocumento/",
    )


@pytest.fixture
def item_simple() -> DTEItemRequest:
    return DTEItemRequest(
        num_item=1,
        tipo_item=2,
        descripcion="Servicio de consultoría",
        cantidad=Decimal("1"),
        precio_unitario=Decimal("10.00"),
        venta_gravada=Decimal("10.00"),
    )


@pytest.fixture
def receptor_fe() -> DTEReceptorRequest:
    return DTEReceptorRequest(nombre="Juan Pérez")


@pytest.fixture
def receptor_ccf() -> DTEReceptorRequest:
    return DTEReceptorRequest(
        nombre="Empresa Receptora SA",
        nit="06140101911020",
        nrc="987654-3",
        cod_actividad="47191",
    )


@pytest.fixture
def request_fe(emisor, item_simple, receptor_fe) -> DTEEmitRequest:
    return DTEEmitRequest(
        tipo_dte="01",
        ambiente="00",
        docname="SINV-TEST-001",
        company="Mi Empresa SV",
        posting_date=date(2026, 4, 1),
        receptor=receptor_fe,
        items=[item_simple],
        grand_total=Decimal("11.30"),
        total_iva=Decimal("1.30"),
        emisor=emisor,
        idempotency_key="test:Sales Invoice:SINV-TEST-001:01:00",
    )


@pytest.fixture
def request_ccf(emisor, item_simple, receptor_ccf) -> DTEEmitRequest:
    return DTEEmitRequest(
        tipo_dte="03",
        ambiente="00",
        docname="SINV-TEST-002",
        company="Mi Empresa SV",
        posting_date=date(2026, 4, 1),
        receptor=receptor_ccf,
        items=[item_simple],
        grand_total=Decimal("11.30"),
        total_iva=Decimal("1.30"),
        emisor=emisor,
        idempotency_key="test:Sales Invoice:SINV-TEST-002:03:00",
    )


# ---------------------------------------------------------------------------
# amount_to_words
# ---------------------------------------------------------------------------

def test_amount_to_words_basic():
    result = amount_to_words(Decimal("11.30"))
    assert "ONCE" in result
    assert "30/100" in result
    assert "DOLARES" in result


def test_amount_to_words_zero_cents():
    result = amount_to_words(Decimal("100.00"))
    assert "00/100" in result
    assert "DOLARES" in result


# ---------------------------------------------------------------------------
# round helpers
# ---------------------------------------------------------------------------

def test_round8():
    assert round8(Decimal("10.123456789")) == pytest.approx(10.12345679, abs=1e-8)
    assert isinstance(round8(Decimal("10.0")), float)


def test_round2():
    assert round2(Decimal("10.125")) == pytest.approx(10.13, abs=1e-2)
    assert isinstance(round2(Decimal("10.0")), float)


# ---------------------------------------------------------------------------
# FE mapper
# ---------------------------------------------------------------------------

def test_build_fe_estructura(request_fe):
    dte = build_fe(request_fe, "DTE-01-00010001-000000000000001", "AAAA-1111")
    assert dte["identificacion"]["tipoDte"] == "01"
    assert dte["identificacion"]["version"] == 1
    assert dte["emisor"]["nit"] == "06140101911019"
    assert len(dte["cuerpoDocumento"]) == 1
    assert dte["resumen"] is not None


def test_build_fe_iva_inclusivo(request_fe):
    """ventaGravada_dte debe ser venta_gravada × 1.13."""
    dte = build_fe(request_fe, "DTE-01-00010001-000000000000001", "AAAA-1111")
    item_dte = dte["cuerpoDocumento"][0]
    vg = Decimal(item_dte["ventaGravada"])
    iva = Decimal(item_dte["ivaItem"])
    assert abs(vg - Decimal("11.30000000")) < Decimal("0.01")
    assert abs(iva - Decimal("1.30000000")) < Decimal("0.01")


def test_build_fe_receptor_consumidor_final_omite_doc(request_fe):
    """Para consumidor final con total < 25000 no debe incluir numDocumento."""
    dte = build_fe(request_fe, "DTE-01-00010001-000000000000001", "AAAA-1111")
    receptor = dte["receptor"]
    assert "tipoDocumento" not in receptor or receptor.get("tipoDocumento") is None
    assert receptor["nombre"] == "Juan Pérez"


def test_build_fe_receptor_grande_incluye_doc(emisor, item_simple):
    """Total >= 25000 con receptor sin NIT/NRC debería no omitir (aunque siga sin doc)."""
    receptor = DTEReceptorRequest(nombre="Cliente Grande")
    req = DTEEmitRequest(
        tipo_dte="01",
        ambiente="00",
        docname="SINV-BIG",
        company="Mi Empresa SV",
        posting_date=date(2026, 4, 1),
        receptor=receptor,
        items=[item_simple],
        grand_total=Decimal("25000.01"),
        emisor=emisor,
        idempotency_key="test:Sales Invoice:SINV-BIG:01:00",
    )
    dte = build_fe(req, "DTE-01-00010001-000000000000001", "AAAA")
    # No debe lanzar excepción
    assert dte["identificacion"]["tipoDte"] == "01"


# ---------------------------------------------------------------------------
# CCF mapper
# ---------------------------------------------------------------------------

def test_build_ccf_estructura(request_ccf):
    dte = build_ccf(request_ccf, "DTE-03-00010001-000000000000001", "BBBB-2222")
    assert dte["identificacion"]["tipoDte"] == "03"
    assert dte["identificacion"]["version"] == 3
    assert dte["receptor"]["nit"] == "06140101911020"


def test_build_ccf_iva_exclusivo(request_ccf):
    """ventaGravada CCF = net_amount sin multiplicar."""
    dte = build_ccf(request_ccf, "DTE-03-00010001-000000000000001", "BBBB-2222")
    item_dte = dte["cuerpoDocumento"][0]
    vg = Decimal(item_dte["ventaGravada"])
    assert abs(vg - Decimal("10.00000000")) < Decimal("0.00001")


def test_build_ccf_sin_nit_lanza_error(emisor, item_simple):
    receptor = DTEReceptorRequest(nombre="Sin NIT", nrc="123456-7")
    req = DTEEmitRequest(
        tipo_dte="03",
        ambiente="00",
        docname="SINV-CCF-ERROR",
        company="Mi Empresa SV",
        posting_date=date(2026, 4, 1),
        receptor=receptor,
        items=[item_simple],
        grand_total=Decimal("11.30"),
        emisor=emisor,
        idempotency_key="test:Sales Invoice:SINV-CCF-ERROR:03:00",
    )
    with pytest.raises(ValueError, match="NIT"):
        build_ccf(req, "DTE-03-00010001-000000000000001", "CCCC")


def test_build_ccf_sin_nrc_lanza_error(emisor, item_simple):
    receptor = DTEReceptorRequest(nombre="Sin NRC", nit="06140101911020")
    req = DTEEmitRequest(
        tipo_dte="03",
        ambiente="00",
        docname="SINV-CCF-NRC",
        company="Mi Empresa SV",
        posting_date=date(2026, 4, 1),
        receptor=receptor,
        items=[item_simple],
        grand_total=Decimal("11.30"),
        emisor=emisor,
        idempotency_key="test:Sales Invoice:SINV-CCF-NRC:03:00",
    )
    with pytest.raises(ValueError, match="NRC"):
        build_ccf(req, "DTE-03-00010001-000000000000001", "DDDD")


# ---------------------------------------------------------------------------
# NC mapper
# ---------------------------------------------------------------------------

def test_build_nc_sin_doc_relacionado_lanza_error(emisor, item_simple, receptor_fe):
    req = DTEEmitRequest(
        tipo_dte="05",
        ambiente="00",
        docname="SINV-NC-ERROR",
        company="Mi Empresa SV",
        posting_date=date(2026, 4, 1),
        receptor=receptor_fe,
        items=[item_simple],
        grand_total=Decimal("11.30"),
        emisor=emisor,
        idempotency_key="test:Sales Invoice:SINV-NC-ERROR:05:00",
        # documento_relacionado_codigo omitido intencional
    )
    with pytest.raises(ValueError, match="documento_relacionado_codigo"):
        build_nc(req, "DTE-05-00010001-000000000000001", "EEEE")


def test_build_nc_con_doc_relacionado(emisor, item_simple, receptor_fe):
    req = DTEEmitRequest(
        tipo_dte="05",
        ambiente="00",
        docname="SINV-NC-OK",
        company="Mi Empresa SV",
        posting_date=date(2026, 4, 1),
        receptor=receptor_fe,
        items=[item_simple],
        grand_total=Decimal("11.30"),
        emisor=emisor,
        idempotency_key="test:Sales Invoice:SINV-NC-OK:05:00",
        documento_relacionado_codigo="ORIG-AAAA-1111",
        documento_relacionado_tipo="01",
        documento_relacionado_fecha=date(2026, 3, 31),
    )
    dte = build_nc(req, "DTE-05-00010001-000000000000001", "FFFF")
    assert dte["identificacion"]["tipoDte"] == "05"
    assert dte["documentoRelacionado"] is not None
    assert dte["documentoRelacionado"][0]["numeroDocumento"] == "ORIG-AAAA-1111"
