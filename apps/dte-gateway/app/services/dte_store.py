"""
dte_store — SQLite persistente para secuenciales e idempotencia.

Base de datos: /app/data/dte_store.db (Docker volume en producción).
Desarrollo local: usa el directorio del módulo como fallback.

Diseño:
  - Thread-safe mediante threading.Lock (un único proceso uvicorn con workers).
  - SQLite WAL mode para mejor concurrencia de lectura.
  - Secuencial NO se revierte si la operación posterior falla (huecos son aceptables per MH).
  - Idempotency incluye payload_hash para detectar colisiones (misma key, payload diferente).
  - Clave de secuencia: (tipo_dte, cod_estable_mh, cod_punto_venta_mh, ambiente, ejercicio)
    · ambiente separa test (00) de producción (01) — no comparten contadores.
    · ejercicio = año del posting_date del documento (fecha fiscal, no reloj del servidor).
    · Reinicio automático al inicio de cada ejercicio impositivo (año calendario).
"""

import hashlib
import json
import logging
import sqlite3
import threading
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

_LOCK = threading.Lock()

# Ruta de la BD: /app/data/ en contenedor, directorio del módulo en dev
_DATA_DIR = Path("/app/data")
if not _DATA_DIR.exists():
    _DATA_DIR = Path(__file__).parent.parent / "data"
    _DATA_DIR.mkdir(exist_ok=True)

_DB_PATH = _DATA_DIR / "dte_store.db"


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def _migrate_sequences_v2(conn: sqlite3.Connection) -> None:
    """
    Migración única: añade columnas 'ambiente' y renombra 'year' → 'ejercicio'
    en la tabla sequences.

    Antes (v1): PRIMARY KEY (tipo_dte, cod_estable_mh, cod_punto_venta_mh, year)
    Después (v2): PRIMARY KEY (tipo_dte, cod_estable_mh, cod_punto_venta_mh, ambiente, ejercicio)

    Backfill: todos los registros existentes son del ambiente '00' (pruebas).
    """
    cols = {row[1] for row in conn.execute("PRAGMA table_info(sequences)").fetchall()}
    if "ambiente" in cols:
        return  # ya migrado

    logger.info("dte_store: migrando tabla sequences a v2 (+ ambiente + ejercicio)")
    conn.execute("""
        CREATE TABLE sequences_v2 (
            tipo_dte           TEXT NOT NULL,
            cod_estable_mh     TEXT NOT NULL,
            cod_punto_venta_mh TEXT NOT NULL,
            ambiente           TEXT NOT NULL,
            ejercicio          INTEGER NOT NULL,
            secuencial         INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (tipo_dte, cod_estable_mh, cod_punto_venta_mh, ambiente, ejercicio)
        )
    """)
    # Backfill: los datos existentes son del entorno de pruebas (ambiente='00').
    # La columna 'year' se mapea a 'ejercicio'.
    if "year" in cols:
        conn.execute("""
            INSERT INTO sequences_v2
                (tipo_dte, cod_estable_mh, cod_punto_venta_mh, ambiente, ejercicio, secuencial)
            SELECT tipo_dte, cod_estable_mh, cod_punto_venta_mh, '00', year, secuencial
            FROM sequences
        """)
    conn.execute("DROP TABLE sequences")
    conn.execute("ALTER TABLE sequences_v2 RENAME TO sequences")
    logger.info("dte_store: migración sequences v2 completada")


def _init_db() -> None:
    with _get_conn() as conn:
        # Crear tabla sequences si no existe (schema v2 directamente)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS sequences (
                tipo_dte           TEXT NOT NULL,
                cod_estable_mh     TEXT NOT NULL,
                cod_punto_venta_mh TEXT NOT NULL,
                ambiente           TEXT NOT NULL,
                ejercicio          INTEGER NOT NULL,
                secuencial         INTEGER NOT NULL DEFAULT 0,
                PRIMARY KEY (tipo_dte, cod_estable_mh, cod_punto_venta_mh, ambiente, ejercicio)
            )
        """)
        # Migración desde v1 (sin ambiente) si la tabla ya existía con el schema anterior
        _migrate_sequences_v2(conn)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS idempotency (
                key             TEXT PRIMARY KEY,
                status          TEXT NOT NULL,
                payload_hash    TEXT NOT NULL,
                response_json   TEXT,
                created_at      TEXT NOT NULL,
                updated_at      TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS anulaciones (
                idempotency_key              TEXT PRIMARY KEY,
                codigo_generacion_original   TEXT NOT NULL,
                event_uuid                   TEXT,
                status                       TEXT NOT NULL,
                response_json                TEXT,
                created_at                   TEXT NOT NULL,
                updated_at                   TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS contingencia (
                idempotency_key  TEXT PRIMARY KEY,
                event_uuid       TEXT,
                status           TEXT NOT NULL,
                response_json    TEXT,
                created_at       TEXT NOT NULL,
                updated_at       TEXT NOT NULL
            )
        """)
        conn.commit()


# Inicializar al importar
_init_db()


# ---------------------------------------------------------------------------
# Secuenciales
# ---------------------------------------------------------------------------

def next_secuencial(
    tipo_dte: str,
    cod_estable_mh: str,
    cod_punto_venta_mh: str,
    ambiente: str,
    ejercicio: int,
) -> int:
    """
    Retorna el siguiente número secuencial para la combinación dada.

    Thread-safe. La secuencia reinicia al inicio de cada ejercicio impositivo
    (año fiscal derivado de posting_date del documento, no del reloj del servidor).

    Args:
        tipo_dte:           "01", "03", "05", "06", etc.
        cod_estable_mh:     Código establecimiento MH (4 chars, ej. "M001").
        cod_punto_venta_mh: Código punto de venta MH (4 chars, ej. "P001").
        ambiente:           "00"=pruebas, "01"=producción.
        ejercicio:          Año fiscal del documento (posting_date.year).

    Returns:
        Entero ≥ 1, único dentro de la combinación (tipo, estable, pv, ambiente, ejercicio).
        El secuencial NO se revierte si la operación posterior falla (huecos aceptables per MH).
    """
    with _LOCK:
        with _get_conn() as conn:
            conn.execute("""
                INSERT INTO sequences
                    (tipo_dte, cod_estable_mh, cod_punto_venta_mh, ambiente, ejercicio, secuencial)
                VALUES (?, ?, ?, ?, ?, 1)
                ON CONFLICT(tipo_dte, cod_estable_mh, cod_punto_venta_mh, ambiente, ejercicio)
                DO UPDATE SET secuencial = secuencial + 1
            """, (tipo_dte, cod_estable_mh, cod_punto_venta_mh, ambiente, ejercicio))
            conn.commit()
            row = conn.execute("""
                SELECT secuencial FROM sequences
                WHERE tipo_dte=? AND cod_estable_mh=? AND cod_punto_venta_mh=?
                  AND ambiente=? AND ejercicio=?
            """, (tipo_dte, cod_estable_mh, cod_punto_venta_mh, ambiente, ejercicio)).fetchone()
    return row[0]


# ---------------------------------------------------------------------------
# Idempotencia
# ---------------------------------------------------------------------------

def _hash_key_identity(tipo_dte: str, ambiente: str, nit_emisor: str) -> str:
    """
    Hash mínimo de los campos de identidad del request.
    Detecta colisiones: misma idempotency_key pero payload radicalmente diferente.
    No hashea el payload completo (demasiado frágil ante campos irrelevantes).
    """
    identity = f"{tipo_dte}|{ambiente}|{nit_emisor}"
    return hashlib.sha256(identity.encode()).hexdigest()[:16]


def check_idempotency(key: str, tipo_dte: str, ambiente: str, nit_emisor: str) -> dict | None:
    """
    Retorna la respuesta cacheada si la key existe con status='completed'
    y el mismo payload_hash.

    Retorna None si la key no existe.

    Lanza ValueError si:
      - La key existe con status='completed' pero payload_hash diferente (colisión).
      - La key existe con status='pending' (operación en vuelo — posible duplicado concurrente).
    """
    payload_hash = _hash_key_identity(tipo_dte, ambiente, nit_emisor)
    with _LOCK:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT status, payload_hash, response_json FROM idempotency WHERE key=?",
                (key,)
            ).fetchone()

    if row is None:
        return None

    status, stored_hash, response_json = row

    if stored_hash != payload_hash:
        raise ValueError(
            f"Colisión de idempotency_key: la clave '{key}' ya existe con un payload diferente. "
            "Revise que docname, tipo_dte y ambiente sean únicos por documento."
        )

    if status == "completed" and response_json:
        return json.loads(response_json)

    if status == "pending":
        raise ValueError(
            f"La key '{key}' tiene una operación en curso (status=pending). "
            "Espere a que termine o reintente en unos segundos."
        )

    # status='failed' → permitir reintento
    return None


def save_idempotency(
    key: str,
    status: str,
    tipo_dte: str,
    ambiente: str,
    nit_emisor: str,
    response: dict | None = None,
) -> None:
    """
    Persiste o actualiza el estado de una operación.

    Llamar con status='pending' al iniciar, 'completed'/'failed' al terminar.
    """
    payload_hash = _hash_key_identity(tipo_dte, ambiente, nit_emisor)
    now = datetime.now(timezone.utc).isoformat()
    response_json = json.dumps(response) if response is not None else None

    with _LOCK:
        with _get_conn() as conn:
            conn.execute("""
                INSERT INTO idempotency (key, status, payload_hash, response_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET
                    status       = excluded.status,
                    payload_hash = excluded.payload_hash,
                    response_json = excluded.response_json,
                    updated_at   = excluded.updated_at
            """, (key, status, payload_hash, response_json, now, now))
            conn.commit()


# ---------------------------------------------------------------------------
# Anulaciones
# ---------------------------------------------------------------------------

def check_anulacion(key: str) -> dict | None:
    """
    Retorna la respuesta cacheada si la key existe con status='completed'.
    Retorna None si no existe o si status='failed' (permite reintento).
    Lanza ValueError si status='pending' (operación en vuelo).
    """
    with _LOCK:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT status, response_json FROM anulaciones WHERE idempotency_key=?",
                (key,)
            ).fetchone()

    if row is None:
        return None
    status, response_json = row
    if status == "completed" and response_json:
        return json.loads(response_json)
    if status == "pending":
        raise ValueError(
            f"Anulación '{key}' tiene una operación en curso (status=pending). "
            "Espere a que termine o reintente en unos segundos."
        )
    return None  # status='failed' → permitir reintento


def save_anulacion(
    key: str,
    codigo_generacion_original: str,
    event_uuid: str | None,
    status: str,
    response: dict | None = None,
) -> None:
    """Persiste o actualiza el estado de una operación de anulación."""
    now = datetime.now(timezone.utc).isoformat()
    response_json = json.dumps(response) if response is not None else None
    with _LOCK:
        with _get_conn() as conn:
            conn.execute("""
                INSERT INTO anulaciones
                    (idempotency_key, codigo_generacion_original, event_uuid, status, response_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(idempotency_key) DO UPDATE SET
                    event_uuid    = excluded.event_uuid,
                    status        = excluded.status,
                    response_json = excluded.response_json,
                    updated_at    = excluded.updated_at
            """, (key, codigo_generacion_original, event_uuid, status, response_json, now, now))
            conn.commit()


# ---------------------------------------------------------------------------
# Contingencia
# ---------------------------------------------------------------------------

def check_contingencia(key: str) -> dict | None:
    """
    Retorna la respuesta cacheada si la key existe con status='completed'.
    Retorna None si no existe o si status='failed'.
    Lanza ValueError si status='pending'.
    """
    with _LOCK:
        with _get_conn() as conn:
            row = conn.execute(
                "SELECT status, response_json FROM contingencia WHERE idempotency_key=?",
                (key,)
            ).fetchone()

    if row is None:
        return None
    status, response_json = row
    if status == "completed" and response_json:
        return json.loads(response_json)
    if status == "pending":
        raise ValueError(
            f"Contingencia '{key}' tiene una operación en curso (status=pending). "
            "Espere a que termine o reintente en unos segundos."
        )
    return None


def save_contingencia(
    key: str,
    event_uuid: str | None,
    status: str,
    response: dict | None = None,
) -> None:
    """Persiste o actualiza el estado de un evento de contingencia."""
    now = datetime.now(timezone.utc).isoformat()
    response_json = json.dumps(response) if response is not None else None
    with _LOCK:
        with _get_conn() as conn:
            conn.execute("""
                INSERT INTO contingencia
                    (idempotency_key, event_uuid, status, response_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(idempotency_key) DO UPDATE SET
                    event_uuid    = excluded.event_uuid,
                    status        = excluded.status,
                    response_json = excluded.response_json,
                    updated_at    = excluded.updated_at
            """, (key, event_uuid, status, response_json, now, now))
            conn.commit()
