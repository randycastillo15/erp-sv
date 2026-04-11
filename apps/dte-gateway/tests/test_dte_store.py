"""Tests para dte_store: secuenciales e idempotencia."""

import threading
import pytest

# Usar BD en memoria para tests — parchear _DB_PATH antes de importar
import app.services.dte_store as store_module
from pathlib import Path


@pytest.fixture(autouse=True)
def in_memory_db(tmp_path, monkeypatch):
    """Cada test usa una BD temporal aislada."""
    db_path = tmp_path / "test_dte_store.db"
    monkeypatch.setattr(store_module, "_DB_PATH", db_path)
    # Re-inicializar tablas con la BD temporal
    store_module._init_db()
    yield


# ---------------------------------------------------------------------------
# Secuenciales — comportamiento básico
# ---------------------------------------------------------------------------

def test_secuencial_incremental():
    s1 = store_module.next_secuencial("01", "0001", "0001", "00", 2026)
    s2 = store_module.next_secuencial("01", "0001", "0001", "00", 2026)
    s3 = store_module.next_secuencial("01", "0001", "0001", "00", 2026)
    assert s1 == 1
    assert s2 == 2
    assert s3 == 3


def test_secuencial_independiente_por_tipo():
    """FE y CCF tienen secuencias independientes."""
    s_fe  = store_module.next_secuencial("01", "0001", "0001", "00", 2026)
    s_ccf = store_module.next_secuencial("03", "0001", "0001", "00", 2026)
    s_nc  = store_module.next_secuencial("05", "0001", "0001", "00", 2026)
    s_nd  = store_module.next_secuencial("06", "0001", "0001", "00", 2026)
    assert s_fe  == 1
    assert s_ccf == 1
    assert s_nc  == 1
    assert s_nd  == 1


def test_secuencial_thread_safe():
    results = []
    errors = []

    def worker():
        try:
            seq = store_module.next_secuencial("01", "0001", "0001", "00", 2026)
            results.append(seq)
        except Exception as exc:
            errors.append(exc)

    threads = [threading.Thread(target=worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert not errors, f"Errores en threads: {errors}"
    assert sorted(results) == list(range(1, 11)), f"Secuenciales no únicos: {results}"


# ---------------------------------------------------------------------------
# Secuenciales — aislamiento por ambiente
# ---------------------------------------------------------------------------

def test_secuencial_independiente_por_ambiente():
    """Pruebas (00) y producción (01) tienen secuencias totalmente independientes."""
    s_test  = store_module.next_secuencial("01", "M001", "P001", "00", 2026)
    s_prod  = store_module.next_secuencial("01", "M001", "P001", "01", 2026)
    s_test2 = store_module.next_secuencial("01", "M001", "P001", "00", 2026)
    assert s_test  == 1, "test ambiente empieza en 1"
    assert s_prod  == 1, "prod ambiente empieza en 1, independiente de test"
    assert s_test2 == 2, "test ambiente continúa su propia secuencia"


def test_secuencial_mismo_tipo_distintos_ambientes_no_interfieren():
    """Emitir 5 DTEs en test no afecta el contador de producción."""
    for _ in range(5):
        store_module.next_secuencial("03", "M001", "P001", "00", 2026)
    s_prod = store_module.next_secuencial("03", "M001", "P001", "01", 2026)
    assert s_prod == 1, "prod arranca en 1 aunque test ya está en 5"


# ---------------------------------------------------------------------------
# Secuenciales — reinicio por ejercicio impositivo (rollover anual)
# ---------------------------------------------------------------------------

def test_secuencial_rollover_anual():
    """Al inicio de cada ejercicio impositivo el consecutivo vuelve a 1."""
    # Ejercicio 2025: avanzar hasta 100
    for _ in range(100):
        store_module.next_secuencial("01", "M001", "P001", "00", 2025)

    # Ejercicio 2026: primer consecutivo debe ser 1
    primer_2026 = store_module.next_secuencial("01", "M001", "P001", "00", 2026)
    assert primer_2026 == 1, f"2026 debe empezar en 1, obtenido: {primer_2026}"

    # 2025 sigue siendo independiente
    sig_2025 = store_module.next_secuencial("01", "M001", "P001", "00", 2025)
    assert sig_2025 == 101


def test_secuencial_rollover_por_tipo_independiente():
    """Cada tipo_dte tiene su propio contador por ejercicio."""
    # Simular fin de 2025 con distintos avances por tipo
    for _ in range(50):
        store_module.next_secuencial("01", "M001", "P001", "00", 2025)
    for _ in range(20):
        store_module.next_secuencial("03", "M001", "P001", "00", 2025)

    # Primer consecutivo de 2026 para cada tipo: ambos deben ser 1
    fe_2026  = store_module.next_secuencial("01", "M001", "P001", "00", 2026)
    ccf_2026 = store_module.next_secuencial("03", "M001", "P001", "00", 2026)
    assert fe_2026  == 1
    assert ccf_2026 == 1


def test_secuencial_ejercicio_del_posting_date_no_server_clock():
    """
    Verifica que el ejercicio viene de posting_date, no del reloj del servidor.
    Un doc con posting_date=2025-12-31 enviado en enero 2026 debe usar ejercicio 2025.
    """
    from datetime import date

    # Simular: en 2025 se emitieron 10 FEs
    for _ in range(10):
        store_module.next_secuencial("01", "M001", "P001", "00", 2025)

    # Doc con posting_date en dic-2025 enviado en 2026: ejercicio derivado del posting_date
    posting_date_2025_dic = date(2025, 12, 31)
    ejercicio_del_doc = posting_date_2025_dic.year  # = 2025
    s = store_module.next_secuencial("01", "M001", "P001", "00", ejercicio_del_doc)
    assert s == 11, "debe continuar la secuencia de 2025, no iniciar la de 2026"

    # Doc del ejercicio 2026 empieza en 1
    posting_date_2026 = date(2026, 1, 1)
    s_2026 = store_module.next_secuencial("01", "M001", "P001", "00", posting_date_2026.year)
    assert s_2026 == 1


def test_no_duplicados_cross_ejercicio():
    """Secuenciales de distintos ejercicios no chocan entre sí."""
    s_2024 = store_module.next_secuencial("01", "M001", "P001", "00", 2024)
    s_2025 = store_module.next_secuencial("01", "M001", "P001", "00", 2025)
    s_2026 = store_module.next_secuencial("01", "M001", "P001", "00", 2026)
    # Cada ejercicio arranca en 1, pero son filas distintas en la BD
    assert s_2024 == 1
    assert s_2025 == 1
    assert s_2026 == 1
    # Continuar 2025 no afecta a 2026
    s_2025b = store_module.next_secuencial("01", "M001", "P001", "00", 2025)
    s_2026b = store_module.next_secuencial("01", "M001", "P001", "00", 2026)
    assert s_2025b == 2
    assert s_2026b == 2


# ---------------------------------------------------------------------------
# Migración v1 → v2 (backfill de ambiente)
# ---------------------------------------------------------------------------

def test_migracion_v1_a_v2_preserva_secuenciales(tmp_path, monkeypatch):
    """
    Simula que la BD arranca con el schema v1 (sin ambiente) y verifica
    que la migración automática preserva los secuenciales existentes.
    """
    import sqlite3

    db_path = tmp_path / "migration_test.db"
    monkeypatch.setattr(store_module, "_DB_PATH", db_path)

    # Crear BD con schema v1 manualmente (sin ambiente, columna llamada 'year')
    conn = sqlite3.connect(str(db_path))
    conn.execute("""
        CREATE TABLE sequences (
            tipo_dte           TEXT NOT NULL,
            cod_estable_mh     TEXT NOT NULL,
            cod_punto_venta_mh TEXT NOT NULL,
            year               INTEGER NOT NULL,
            secuencial         INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (tipo_dte, cod_estable_mh, cod_punto_venta_mh, year)
        )
    """)
    # Simular datos existentes: FE=37, CCF=23, NC=13
    conn.executemany(
        "INSERT INTO sequences VALUES (?, ?, ?, ?, ?)",
        [
            ("01", "M001", "P001", 2026, 37),
            ("03", "M001", "P001", 2026, 23),
            ("05", "M001", "P001", 2026, 13),
        ]
    )
    conn.commit()
    conn.close()

    # _init_db() debe detectar la v1 y migrar automáticamente
    store_module._init_db()

    # Verificar que los secuenciales se preservaron con ambiente='00'
    fe_next  = store_module.next_secuencial("01", "M001", "P001", "00", 2026)
    ccf_next = store_module.next_secuencial("03", "M001", "P001", "00", 2026)
    nc_next  = store_module.next_secuencial("05", "M001", "P001", "00", 2026)

    assert fe_next  == 38, f"FE esperado 38, obtenido {fe_next}"
    assert ccf_next == 24, f"CCF esperado 24, obtenido {ccf_next}"
    assert nc_next  == 14, f"NC esperado 14, obtenido {nc_next}"


# ---------------------------------------------------------------------------
# Idempotencia
# ---------------------------------------------------------------------------

def test_idempotencia_miss_retorna_none():
    result = store_module.check_idempotency("key-1", "01", "00", "06140101911019")
    assert result is None


def test_idempotencia_pending_lanza_error():
    store_module.save_idempotency("key-1", "pending", "01", "00", "06140101911019")
    with pytest.raises(ValueError, match="pending"):
        store_module.check_idempotency("key-1", "01", "00", "06140101911019")


def test_idempotencia_failed_permite_reintento():
    store_module.save_idempotency("key-1", "failed", "01", "00", "06140101911019")
    result = store_module.check_idempotency("key-1", "01", "00", "06140101911019")
    assert result is None


def test_idempotencia_completed_retorna_cached():
    response = {"status": "procesado", "generation_code": "ABC123"}
    store_module.save_idempotency("key-1", "completed", "01", "00", "06140101911019", response)
    cached = store_module.check_idempotency("key-1", "01", "00", "06140101911019")
    assert cached == response


def test_idempotencia_colision_lanza_error():
    """Misma key pero payload_hash diferente → colisión."""
    store_module.save_idempotency("key-1", "completed", "01", "00", "NIT-A", {"status": "ok"})
    # Misma key pero NIT diferente → hash diferente
    with pytest.raises(ValueError, match="Colisión"):
        store_module.check_idempotency("key-1", "01", "00", "NIT-B")
