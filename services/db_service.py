import os
import numpy as np
import psycopg2
from psycopg2.extras import RealDictCursor
from pgvector.psycopg2 import register_vector


def _get_db_url() -> str:
    try:
        import streamlit as st
        url = st.secrets.get("DATABASE_URL")
        if url:
            return url
    except Exception:
        pass
    return os.getenv("DATABASE_URL", "")


def get_conn():
    url = _get_db_url()
    if not url:
        raise RuntimeError(
            "DATABASE_URL is not set. Add it to .env (local) or Streamlit secrets (cloud)."
        )
    conn = psycopg2.connect(url)
    register_vector(conn)
    return conn


def init_db():
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute("CREATE EXTENSION IF NOT EXISTS vector")
            cur.execute("""
                CREATE TABLE IF NOT EXISTS vendors (
                    id SERIAL PRIMARY KEY,
                    name TEXT NOT NULL,
                    phone TEXT,
                    company_name TEXT,
                    rate TEXT,
                    embedding vector(384),
                    created_at TIMESTAMP DEFAULT NOW()
                )
            """)
        conn.commit()


def save_vendor(name: str, phone: str, company_name: str, rate: str) -> int:
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO vendors (name, phone, company_name, rate) VALUES (%s, %s, %s, %s) RETURNING id",
                (name, phone, company_name, rate),
            )
            vendor_id = cur.fetchone()[0]
        conn.commit()
    return vendor_id


def update_embedding(vendor_id: int, embedding: list[float]):
    with get_conn() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "UPDATE vendors SET embedding = %s WHERE id = %s",
                (np.array(embedding), vendor_id),
            )
        conn.commit()


def get_all_vendors() -> list[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                "SELECT id, name, phone, company_name, rate, created_at FROM vendors ORDER BY created_at DESC"
            )
            return [dict(row) for row in cur.fetchall()]


def search_by_vector(embedding: list[float], top_k: int = 5) -> list[dict]:
    with get_conn() as conn:
        with conn.cursor(cursor_factory=RealDictCursor) as cur:
            cur.execute(
                """
                SELECT id, name, phone, company_name, rate,
                       embedding <=> %s AS distance
                FROM vendors
                WHERE embedding IS NOT NULL
                ORDER BY distance
                LIMIT %s
                """,
                (np.array(embedding), top_k),
            )
            return [dict(row) for row in cur.fetchall()]
