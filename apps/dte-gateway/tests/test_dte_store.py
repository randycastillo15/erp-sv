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
# Secuenciales
# ---------------------------------------------------------------------------

def test_secuencial_incremental():
    s1 = store_module.next_secuencial("01", "0001", "0001")
    s2 = store_module.next_secuencial("01", "0001", "0001")
    s3 = store_module.next_secuencial("01", "0001", "0001")
    assert s1 == 1
    assert s2 == 2
    assert s3 == 3


def test_secuencial_independiente_por_tipo():
    s_fe = store_module.next_secuencial("01", "0001", "0001")
    s_ccf = store_module.next_secuencial("03", "0001", "0001")
    assert s_fe == 1
    assert s_ccf == 1


def test_secuencial_thread_safe():
    results = []
    errors = []

    def worker():
        try:
            seq = store_module.next_secuencial("01", "0001", "0001")
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
