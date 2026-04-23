import os
import json
import sqlite3
import numpy as np

_BACKEND = None
_SQLITE_PATH = os.getenv("DB_PATH", "db/vendor_ai_tracker.db")


# ── Backend detection ──────────────────────────────────────────────────────────

def _get_db_url() -> str:
    try:
        import streamlit as st
        url = st.secrets.get("DATABASE_URL")
        if url:
            return url
    except Exception:
        pass
    return os.getenv("DATABASE_URL", "")


def _detect_backend() -> str:
    global _BACKEND
    if _BACKEND:
        return _BACKEND
    url = _get_db_url()
    if url:
        try:
            import psycopg2
            conn = psycopg2.connect(url, connect_timeout=5)
            conn.close()
            _BACKEND = "pg"
            return "pg"
        except Exception:
            pass
    _BACKEND = "sqlite"
    return "sqlite"


# ── Connection helpers ─────────────────────────────────────────────────────────

def _pg_conn():
    import psycopg2
    from pgvector.psycopg2 import register_vector
    conn = psycopg2.connect(_get_db_url())
    register_vector(conn)
    return conn


def _sqlite_conn():
    os.makedirs(os.path.dirname(_SQLITE_PATH) or ".", exist_ok=True)
    return sqlite3.connect(_SQLITE_PATH)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    va, vb = np.array(a), np.array(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    return float(np.dot(va, vb) / denom) if denom else 0.0


# ── Schema helpers ─────────────────────────────────────────────────────────────

def _sqlite_has_fields_column() -> bool:
    with _sqlite_conn() as conn:
        cur = conn.execute("PRAGMA table_info(vendors)")
        return any(row[1] == "fields" for row in cur.fetchall())


def _pg_has_fields_column(conn) -> bool:
    with conn.cursor() as cur:
        cur.execute(
            "SELECT 1 FROM information_schema.columns "
            "WHERE table_name='vendors' AND column_name='fields'"
        )
        return cur.fetchone() is not None


# ── Public API ─────────────────────────────────────────────────────────────────

def init_db():
    if _detect_backend() == "pg":
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                if not _pg_has_fields_column(conn):
                    cur.execute("DROP TABLE IF EXISTS vendors")
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS vendors (
                        id SERIAL PRIMARY KEY,
                        fields JSONB NOT NULL DEFAULT '{}',
                        embedding vector(384),
                        created_at TIMESTAMP DEFAULT NOW()
                    )
                """)
            conn.commit()
    else:
        if not _sqlite_has_fields_column():
            with _sqlite_conn() as conn:
                conn.execute("DROP TABLE IF EXISTS vendors")
                conn.commit()
        with _sqlite_conn() as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS vendors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fields TEXT NOT NULL DEFAULT '{}',
                    embedding TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()


def save_vendor(fields: dict) -> int:
    """Save a vendor with any set of fields. Returns the new vendor id."""
    clean = {k: v for k, v in fields.items() if v and str(v).lower() != "nan"}
    if _detect_backend() == "pg":
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO vendors (fields) VALUES (%s) RETURNING id",
                    (json.dumps(clean),),
                )
                vendor_id = cur.fetchone()[0]
            conn.commit()
        return vendor_id
    else:
        with _sqlite_conn() as conn:
            cur = conn.execute(
                "INSERT INTO vendors (fields) VALUES (?)",
                (json.dumps(clean),),
            )
            conn.commit()
            return cur.lastrowid


def update_embedding(vendor_id: int, embedding: list[float]):
    if _detect_backend() == "pg":
        with _pg_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE vendors SET embedding = %s WHERE id = %s",
                    (np.array(embedding), vendor_id),
                )
            conn.commit()
    else:
        with _sqlite_conn() as conn:
            conn.execute(
                "UPDATE vendors SET embedding = ? WHERE id = ?",
                (json.dumps(embedding), vendor_id),
            )
            conn.commit()


def _row_to_dict(vendor_id, fields_raw, created_at) -> dict:
    fields = json.loads(fields_raw) if isinstance(fields_raw, str) else (fields_raw or {})
    return {"id": vendor_id, **fields, "created_at": created_at}


def get_all_vendors() -> list[dict]:
    if _detect_backend() == "pg":
        from psycopg2.extras import RealDictCursor
        with _pg_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    "SELECT id, fields, created_at FROM vendors ORDER BY created_at DESC"
                )
                return [_row_to_dict(r["id"], r["fields"], r["created_at"]) for r in cur.fetchall()]
    else:
        with _sqlite_conn() as conn:
            rows = conn.execute(
                "SELECT id, fields, created_at FROM vendors ORDER BY created_at DESC"
            ).fetchall()
        return [_row_to_dict(r[0], r[1], r[2]) for r in rows]


def search_by_vector(embedding: list[float], top_k: int = 5) -> list[dict]:
    if _detect_backend() == "pg":
        from psycopg2.extras import RealDictCursor
        with _pg_conn() as conn:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(
                    """
                    SELECT id, fields, created_at, embedding <=> %s AS distance
                    FROM vendors
                    WHERE embedding IS NOT NULL
                    ORDER BY distance
                    LIMIT %s
                    """,
                    (np.array(embedding), top_k),
                )
                return [
                    {**_row_to_dict(r["id"], r["fields"], r["created_at"]), "distance": r["distance"]}
                    for r in cur.fetchall()
                ]
    else:
        with _sqlite_conn() as conn:
            rows = conn.execute(
                "SELECT id, fields, created_at, embedding FROM vendors WHERE embedding IS NOT NULL"
            ).fetchall()
        scored = []
        for r in rows:
            stored = json.loads(r[3])
            sim = _cosine_similarity(embedding, stored)
            scored.append({**_row_to_dict(r[0], r[1], r[2]), "distance": 1 - sim})
        scored.sort(key=lambda x: x["distance"])
        return scored[:top_k]
