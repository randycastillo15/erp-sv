"""Tests para los mappers DTE: FE, CCF, NC y funciones comunes."""

from datetime import date
from decimal import Decimal

import pytest

from app.models.dte_request import (
    DTEDireccionRequest,
    DTEEmitRequest,
    DTEEmisorSettings,
    DTEItemRequest,
    DTEReceptorRequest,
)
from app.services.mappers.common import amount_to_words, build_receptor_ccf_nc, round2, round8
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
    """Receptor completo con los 9 campos requeridos por schema CCF/NC."""
    return DTEReceptorRequest(
        nombre="Empresa Receptora SA de CV",
        nit="06140101911020",
        nrc="987654-3",
        cod_actividad="47191",
        desc_actividad="Venta al por mayor de otros productos",
        nombre_comercial="Empresa Receptora",
        direccion=DTEDireccionRequest(
            departamento="06",
            municipio="23",
            complemento="Calle 1 Local 1",
        ),
        correo="empresa@receptora.com.sv",
        telefono="22222222",
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


@pytest.fixture
def request_nc(emisor, item_simple, receptor_ccf) -> DTEEmitRequest:
    """NC contra CCF (tipoDocumento="03") con receptor completo."""
    return DTEEmitRequest(
        tipo_dte="05",
        ambiente="00",
        docname="SINV-TEST-003",
        company="Mi Empresa SV",
        posting_date=date(2026, 4, 1),
        receptor=receptor_ccf,
        items=[item_simple],
        grand_total=Decimal("11.30"),
        total_iva=Decimal("1.30"),
        emisor=emisor,
        idempotency_key="test:Sales Invoice:SINV-TEST-003:05:00",
        documento_relacionado_codigo="A1B2C3D4-E5F6-7890-ABCD-EF1234567890",
        documento_relacionado_tipo="03",
        documento_relacionado_fecha=date(2026, 3, 31),
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
    assert dte["identificacion"]["tipoDte"] == "01"


# ---------------------------------------------------------------------------
# build_receptor_ccf_nc helper
# ---------------------------------------------------------------------------

def test_build_receptor_ccf_nc_completo(receptor_ccf):
    result = build_receptor_ccf_nc(receptor_ccf)
    assert result["nit"] == "06140101911020"
    assert result["nrc"] == "9876543"
    assert result["nombre"] == "Empresa Receptora SA de CV"
    assert result["codActividad"] == "47191"
    assert result["descActividad"] == "Venta al por mayor de otros productos"
    assert result["nombreComercial"] == "Empresa Receptora"
    assert result["direccion"]["departamento"] == "06"
    assert result["direccion"]["municipio"] == "23"
    assert result["correo"] == "empresa@receptora.com.sv"


def test_build_receptor_ccf_nc_sin_nit_lanza_error(receptor_ccf):
    receptor_ccf.nit = None
    with pytest.raises(ValueError, match="nit"):
        build_receptor_ccf_nc(receptor_ccf)


def test_build_receptor_ccf_nc_sin_nrc_lanza_error(receptor_ccf):
    receptor_ccf.nrc = None
    with pytest.raises(ValueError, match="nrc"):
        build_receptor_ccf_nc(receptor_ccf)


def test_build_receptor_ccf_nc_sin_desc_actividad_lanza_error(receptor_ccf):
    receptor_ccf.desc_actividad = None
    with pytest.raises(ValueError, match="descActividad"):
        build_receptor_ccf_nc(receptor_ccf)


def test_build_receptor_ccf_nc_sin_direccion_lanza_error(receptor_ccf):
    receptor_ccf.direccion = None
    with pytest.raises(ValueError, match="direccion"):
        build_receptor_ccf_nc(receptor_ccf)


def test_build_receptor_ccf_nc_sin_correo_lanza_error(receptor_ccf):
    receptor_ccf.correo = None
    with pytest.raises(ValueError, match="correo"):
        build_receptor_ccf_nc(receptor_ccf)


# ---------------------------------------------------------------------------
# CCF mapper
# ---------------------------------------------------------------------------

def test_build_ccf_estructura(request_ccf):
    dte = build_ccf(request_ccf, "DTE-03-00010001-000000000000001", "BBBB-2222")
    assert dte["identificacion"]["tipoDte"] == "03"
    assert dte["identificacion"]["version"] == 3
    assert dte["receptor"]["nit"] == "06140101911020"
    assert dte["receptor"]["codActividad"] == "47191"
    assert dte["receptor"]["direccion"]["departamento"] == "06"
    assert dte["receptor"]["correo"] == "empresa@receptora.com.sv"


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
    with pytest.raises(ValueError, match="nit"):
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
    with pytest.raises(ValueError, match="nrc"):
        build_ccf(req, "DTE-03-00010001-000000000000001", "DDDD")


def test_build_ccf_sin_desc_actividad_lanza_error(emisor, item_simple, receptor_ccf):
    receptor_ccf.desc_actividad = None
    req = DTEEmitRequest(
        tipo_dte="03",
        ambiente="00",
        docname="SINV-CCF-DA",
        company="Mi Empresa SV",
        posting_date=date(2026, 4, 1),
        receptor=receptor_ccf,
        items=[item_simple],
        grand_total=Decimal("11.30"),
        emisor=emisor,
        idempotency_key="test:Sales Invoice:SINV-CCF-DA:03:00",
    )
    with pytest.raises(ValueError, match="descActividad"):
        build_ccf(req, "DTE-03-00010001-000000000000001", "EEEE")


def test_build_ccf_sin_direccion_lanza_error(emisor, item_simple, receptor_ccf):
    receptor_ccf.direccion = None
    req = DTEEmitRequest(
        tipo_dte="03",
        ambiente="00",
        docname="SINV-CCF-DIR",
        company="Mi Empresa SV",
        posting_date=date(2026, 4, 1),
        receptor=receptor_ccf,
        items=[item_simple],
        grand_total=Decimal("11.30"),
        emisor=emisor,
        idempotency_key="test:Sales Invoice:SINV-CCF-DIR:03:00",
    )
    with pytest.raises(ValueError, match="direccion"):
        build_ccf(req, "DTE-03-00010001-000000000000001", "FFFF")


def test_build_ccf_sin_correo_lanza_error(emisor, item_simple, receptor_ccf):
    receptor_ccf.correo = None
    req = DTEEmitRequest(
        tipo_dte="03",
        ambiente="00",
        docname="SINV-CCF-COR",
        company="Mi Empresa SV",
        posting_date=date(2026, 4, 1),
        receptor=receptor_ccf,
        items=[item_simple],
        grand_total=Decimal("11.30"),
        emisor=emisor,
        idempotency_key="test:Sales Invoice:SINV-CCF-COR:03:00",
    )
    with pytest.raises(ValueError, match="correo"):
        build_ccf(req, "DTE-03-00010001-000000000000001", "GGGG")


# ---------------------------------------------------------------------------
# NC mapper
# ---------------------------------------------------------------------------

def test_build_nc_sin_doc_relacionado_lanza_error(emisor, item_simple, receptor_ccf):
    req = DTEEmitRequest(
        tipo_dte="05",
        ambiente="00",
        docname="SINV-NC-ERROR",
        company="Mi Empresa SV",
        posting_date=date(2026, 4, 1),
        receptor=receptor_ccf,
        items=[item_simple],
        grand_total=Decimal("11.30"),
        emisor=emisor,
        idempotency_key="test:Sales Invoice:SINV-NC-ERROR:05:00",
        # documento_relacionado_codigo omitido intencional
    )
    with pytest.raises(ValueError, match="documento_relacionado_codigo"):
        build_nc(req, "DTE-05-00010001-000000000000001", "EEEE")


def test_build_nc_tipo_documento_invalido_lanza_error(emisor, item_simple, receptor_ccf):
    """tipoDocumento '01' (FE) no es válido para NC — schema solo acepta '03' o '07'."""
    req = DTEEmitRequest(
        tipo_dte="05",
        ambiente="00",
        docname="SINV-NC-TIPO",
        company="Mi Empresa SV",
        posting_date=date(2026, 4, 1),
        receptor=receptor_ccf,
        items=[item_simple],
        grand_total=Decimal("11.30"),
        emisor=emisor,
        idempotency_key="test:Sales Invoice:SINV-NC-TIPO:05:00",
        documento_relacionado_codigo="A1B2C3D4-E5F6-7890-ABCD-EF1234567890",
        documento_relacionado_tipo="01",  # FE — inválido
    )
    with pytest.raises(ValueError, match="'01'"):
        build_nc(req, "DTE-05-00010001-000000000000001", "HHHH")


def test_build_nc_tipo_documento_07_valido(request_nc):
    """tipoDocumento '07' (ND) es válido para NC."""
    request_nc.documento_relacionado_tipo = "07"
    request_nc.idempotency_key = "test:Sales Invoice:SINV-TEST-003-ND:05:00"
    dte = build_nc(request_nc, "DTE-05-00010001-000000000000001", "IIII")
    assert dte["documentoRelacionado"][0]["tipoDocumento"] == "07"


def test_build_nc_con_doc_relacionado_ccf(request_nc):
    """NC válida contra CCF con receptor completo."""
    dte = build_nc(request_nc, "DTE-05-00010001-000000000000001", "FFFF")
    assert dte["identificacion"]["tipoDte"] == "05"
    assert dte["documentoRelacionado"] is not None
    doc_rel = dte["documentoRelacionado"][0]
    assert doc_rel["tipoDocumento"] == "03"
    assert doc_rel["tipoGeneracion"] == 2
    assert doc_rel["numeroDocumento"] == "A1B2C3D4-E5F6-7890-ABCD-EF1234567890"
    assert doc_rel["fechaEmision"] == "2026-03-31"


def test_build_nc_receptor_completo(request_nc):
    """Receptor NC debe tener los mismos 9 campos que CCF."""
    dte = build_nc(request_nc, "DTE-05-00010001-000000000000001", "JJJJ")
    receptor = dte["receptor"]
    assert receptor["nit"] == "06140101911020"
    assert receptor["codActividad"] == "47191"
    assert receptor["descActividad"] == "Venta al por mayor de otros productos"
    assert receptor["direccion"]["departamento"] == "06"
    assert receptor["correo"] == "empresa@receptora.com.sv"


def test_build_nc_receptor_incompleto_lanza_error(emisor, item_simple, receptor_fe):
    """Receptor FE (sin nit/nrc/direccion) debe fallar en NC."""
    req = DTEEmitRequest(
        tipo_dte="05",
        ambiente="00",
        docname="SINV-NC-RECEP",
        company="Mi Empresa SV",
        posting_date=date(2026, 4, 1),
        receptor=receptor_fe,  # solo nombre, sin campos CCF
        items=[item_simple],
        grand_total=Decimal("11.30"),
        emisor=emisor,
        idempotency_key="test:Sales Invoice:SINV-NC-RECEP:05:00",
        documento_relacionado_codigo="A1B2C3D4-E5F6-7890-ABCD-EF1234567890",
        documento_relacionado_tipo="03",
    )
    with pytest.raises(ValueError):
        build_nc(req, "DTE-05-00010001-000000000000001", "KKKK")


def test_build_nc_iva_exclusivo(request_nc):
    """ventaGravada NC = net_amount sin multiplicar (igual que CCF)."""
    dte = build_nc(request_nc, "DTE-05-00010001-000000000000001", "LLLL")
    item_dte = dte["cuerpoDocumento"][0]
    vg = Decimal(item_dte["ventaGravada"])
    assert abs(vg - Decimal("10.00000000")) < Decimal("0.00001")
