"""Tests para los mappers DTE: FE, CCF, NC, Anulación y Contingencia."""

from datetime import date
from decimal import Decimal

import pytest

from app.models.dte_request import (
    AnulacionRequest,
    ContingenciaDTEItem,
    ContingenciaEmitRequest,
    DTEDireccionRequest,
    DTEEmitRequest,
    DTEEmisorSettings,
    DTEItemRequest,
    DTEReceptorRequest,
)
from app.services.mappers.anulacion_mapper import build_anulacion
from app.services.mappers.common import amount_to_words, build_receptor_ccf_nc, round2, round8
from app.services.mappers.contingencia_mapper import build_contingencia
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


# ===========================================================================
# Fixtures — Anulación y Contingencia
# ===========================================================================

UUID_ORIGINAL = "EFD95023-61B3-4C87-A343-FF95CB6FE080"
UUID_REEMPLAZO = "AD8F4B7D-82F3-4D1B-BAE4-92CADC7123E2"
SELLO_40 = "2026B8557E6E01EE42D89F3ED243C74B3242YTZL"
NUMERO_CONTROL = "DTE-03-M0010001-000000000000001"


@pytest.fixture
def anulacion_base(emisor) -> AnulacionRequest:
    """AnulacionRequest mínimo válido (tipoAnulacion=2, sin reemplazo)."""
    return AnulacionRequest(
        ambiente="00",
        emisor=emisor,
        tipo_dte="03",
        codigo_generacion_original=UUID_ORIGINAL,
        sello_recibido=SELLO_40,
        numero_control=NUMERO_CONTROL,
        fec_emi="2026-04-04",
        monto_iva=13.00,
        tipo_documento_receptor="36",
        num_documento_receptor="040010231",
        nombre_receptor="Ferreteria Gustavo",
        tipo_anulacion=2,
        motivo_anulacion="Prueba de anulación sin reemplazo",
        nombre_responsable="Juan Rodriguez",
        tip_doc_responsable="13",
        num_doc_responsable="12345678-9",
        nombre_solicita="Maria Lopez",
        tip_doc_solicita="13",
        num_doc_solicita="98765432-1",
        fecha_anula="2026-04-04",
        idempotency_key="test:anulacion:00001",
    )


@pytest.fixture
def contingencia_base(emisor) -> ContingenciaEmitRequest:
    """ContingenciaEmitRequest mínimo válido (tipoContingencia=2)."""
    return ContingenciaEmitRequest(
        ambiente="00",
        emisor=emisor,
        nombre_responsable="Juan Rodriguez",
        tipo_doc_responsable="13",
        num_doc_responsable="12345678-9",
        tipo_contingencia=2,
        motivo_contingencia=None,
        f_inicio="2026-04-04",
        h_inicio="08:00:00",
        f_fin="2026-04-04",
        h_fin="10:00:00",
        detalle=[
            ContingenciaDTEItem(no_item=1, codigo_generacion=UUID_ORIGINAL, tipo_doc="03"),
            ContingenciaDTEItem(no_item=2, codigo_generacion=UUID_REEMPLAZO, tipo_doc="01"),
        ],
        idempotency_key="test:contingencia:00001",
    )


# ===========================================================================
# Tests — Anulación mapper
# ===========================================================================

class TestAnulacionMapper:
    def test_tipo2_codigo_reemplazo_es_null(self, anulacion_base):
        """tipoAnulacion=2: codigoGeneracionR debe ser null en el JSON."""
        result = build_anulacion(anulacion_base)
        assert result["documento"]["codigoGeneracionR"] is None

    def test_tipo2_con_reemplazo_lanza_error(self, anulacion_base):
        """tipoAnulacion=2 no debe aceptar codigo_generacion_reemplazo."""
        anulacion_base.tipo_anulacion = 2
        anulacion_base.codigo_generacion_reemplazo = UUID_REEMPLAZO
        with pytest.raises(ValueError, match="codigoGeneracionR debe ser null"):
            build_anulacion(anulacion_base)

    def test_tipo1_sin_reemplazo_lanza_error(self, anulacion_base):
        """tipoAnulacion=1 requiere codigo_generacion_reemplazo."""
        anulacion_base.tipo_anulacion = 1
        anulacion_base.codigo_generacion_reemplazo = None
        with pytest.raises(ValueError, match="requiere codigo_generacion_reemplazo"):
            build_anulacion(anulacion_base)

    def test_tipo3_con_reemplazo_valido(self, anulacion_base):
        """tipoAnulacion=3 con reemplazo: codigoGeneracionR == UUID reemplazo."""
        anulacion_base.tipo_anulacion = 3
        anulacion_base.codigo_generacion_reemplazo = UUID_REEMPLAZO
        result = build_anulacion(anulacion_base)
        assert result["documento"]["codigoGeneracionR"] == UUID_REEMPLAZO.upper()

    def test_tipo_invalido_lanza_error(self, anulacion_base):
        """tipoAnulacion fuera de rango 1-3 lanza ValueError."""
        anulacion_base.tipo_anulacion = 9
        with pytest.raises(ValueError, match="inválido"):
            build_anulacion(anulacion_base)

    def test_emisor_sin_nrc_ni_codactividad(self, anulacion_base):
        """Emisor de anulación NO incluye nrc ni codActividad (additionalProperties: false)."""
        result = build_anulacion(anulacion_base)
        emisor_json = result["emisor"]
        assert "nrc" not in emisor_json
        assert "codActividad" not in emisor_json
        assert "descActividad" not in emisor_json
        assert "nit" in emisor_json
        assert "nombre" in emisor_json

    def test_receptor_tipo_documento_cat22(self, anulacion_base):
        """tipoDocumento del receptor respeta el valor pasado (CAT-22)."""
        anulacion_base.tipo_documento_receptor = "36"
        result = build_anulacion(anulacion_base)
        assert result["documento"]["tipoDocumento"] == "36"

    def test_identificacion_sin_numero_control(self, anulacion_base):
        """Identificacion de anulación no tiene numeroControl."""
        result = build_anulacion(anulacion_base)
        assert "numeroControl" not in result["identificacion"]
        assert "codigoGeneracion" in result["identificacion"]
        assert "fecAnula" in result["identificacion"]
        assert "horAnula" in result["identificacion"]

    def test_event_uuid_interno_presente(self, anulacion_base):
        """build_anulacion devuelve _event_uuid para que el router lo extraiga."""
        result = build_anulacion(anulacion_base)
        assert "_event_uuid" in result
        assert len(result["_event_uuid"]) == 36   # UUID con guiones

    def test_monto_iva_null_permitido(self, anulacion_base):
        """montoIva puede ser None (schema type ["number","null"])."""
        anulacion_base.monto_iva = None
        result = build_anulacion(anulacion_base)
        assert result["documento"]["montoIva"] is None

    def test_version_es_2(self, anulacion_base):
        """Versión del schema de anulación debe ser 2."""
        result = build_anulacion(anulacion_base)
        assert result["identificacion"]["version"] == 2


# ===========================================================================
# Tests — Contingencia mapper
# ===========================================================================

class TestContingenciaMapper:
    def test_identificacion_usa_fTransmision(self, contingencia_base):
        """identificacion usa fTransmision/hTransmision, NO fecEmi/horEmi."""
        result = build_contingencia(contingencia_base)
        ident = result["identificacion"]
        assert "fTransmision" in ident
        assert "hTransmision" in ident
        assert "fecEmi" not in ident
        assert "horEmi" not in ident

    def test_sin_numero_control(self, contingencia_base):
        """identificacion de contingencia NO tiene numeroControl."""
        result = build_contingencia(contingencia_base)
        assert "numeroControl" not in result["identificacion"]

    def test_version_es_3(self, contingencia_base):
        """Versión del schema de contingencia debe ser 3."""
        result = build_contingencia(contingencia_base)
        assert result["identificacion"]["version"] == 3

    def test_emisor_incluye_responsable(self, contingencia_base):
        """Emisor de contingencia incluye nombreResponsable/tipoDocResponsable/numeroDocResponsable."""
        result = build_contingencia(contingencia_base)
        emisor = result["emisor"]
        assert emisor["nombreResponsable"] == "Juan Rodriguez"
        assert emisor["tipoDocResponsable"] == "13"
        assert emisor["numeroDocResponsable"] == "12345678-9"

    def test_emisor_sin_nrc_ni_codactividad(self, contingencia_base):
        """Emisor de contingencia NO incluye nrc/codActividad (additionalProperties: false)."""
        result = build_contingencia(contingencia_base)
        emisor = result["emisor"]
        assert "nrc" not in emisor
        assert "codActividad" not in emisor

    def test_detalle_items(self, contingencia_base):
        """detalleDTE tiene noItem, codigoGeneracion, tipoDoc — sin campos extras."""
        result = build_contingencia(contingencia_base)
        item = result["detalleDTE"][0]
        assert set(item.keys()) == {"noItem", "codigoGeneracion", "tipoDoc"}
        assert item["codigoGeneracion"] == UUID_ORIGINAL.upper()

    def test_detalle_vacio_lanza_error(self, contingencia_base):
        """detalle vacío debe lanzar ValueError."""
        contingencia_base.detalle = []
        with pytest.raises(ValueError, match="minItems"):
            build_contingencia(contingencia_base)

    def test_detalle_supera_1000_lanza_error(self, contingencia_base, emisor):
        """detalle con más de 1000 items lanza ValueError."""
        contingencia_base.detalle = [
            ContingenciaDTEItem(no_item=i, codigo_generacion=UUID_ORIGINAL, tipo_doc="01")
            for i in range(1, 1002)
        ]
        with pytest.raises(ValueError, match="1000"):
            build_contingencia(contingencia_base)

    def test_tipo5_sin_motivo_lanza_error(self, contingencia_base):
        """tipoContingencia=5 requiere motivoContingencia no vacío."""
        contingencia_base.tipo_contingencia = 5
        contingencia_base.motivo_contingencia = None
        with pytest.raises(ValueError, match="motivoContingencia"):
            build_contingencia(contingencia_base)

    def test_tipo5_con_motivo_valido(self, contingencia_base):
        """tipoContingencia=5 con motivo: construye correctamente."""
        contingencia_base.tipo_contingencia = 5
        contingencia_base.motivo_contingencia = "Corte de energía en datacenter"
        result = build_contingencia(contingencia_base)
        assert result["motivo"]["motivoContingencia"] == "Corte de energía en datacenter"

    def test_event_uuid_interno_presente(self, contingencia_base):
        """build_contingencia devuelve _event_uuid para extracción por el router."""
        result = build_contingencia(contingencia_base)
        assert "_event_uuid" in result
        assert len(result["_event_uuid"]) == 36

    def test_motivo_periodo(self, contingencia_base):
        """motivo contiene fInicio/hInicio/fFin/hFin del request."""
        result = build_contingencia(contingencia_base)
        motivo = result["motivo"]
        assert motivo["fInicio"] == "2026-04-04"
        assert motivo["hInicio"] == "08:00:00"
        assert motivo["fFin"] == "2026-04-04"
        assert motivo["hFin"] == "10:00:00"
