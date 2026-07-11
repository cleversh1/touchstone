"""Database access layer: connection pooling, schema, and all SQL.

Uses psycopg 3 with a connection pool and pgvector for similarity search.
All functions here are synchronous; callers that run inside the async server
invoke them via a worker thread (FastMCP runs sync tools in a threadpool, and
the auth middleware wraps calls in anyio.to_thread).
"""

from __future__ import annotations

import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import numpy as np
from pgvector.psycopg import register_vector
from psycopg import sql
from psycopg.rows import dict_row
from psycopg_pool import ConnectionPool

from . import config

_pool: Optional[ConnectionPool] = None

SCHEMA_PATH = Path(__file__).resolve().parent.parent / "schema.sql"


def _configure(conn) -> None:
    """Register the pgvector type adapter on every pooled connection."""
    register_vector(conn)


def get_pool() -> ConnectionPool:
    global _pool
    if _pool is None:
        if not config.DATABASE_URL:
            raise RuntimeError("DATABASE_URL is not set.")
        _pool = ConnectionPool(
            config.DATABASE_URL,
            min_size=1,
            max_size=10,
            configure=_configure,
            kwargs={"row_factory": dict_row},
            open=True,
        )
    return _pool


def init_schema() -> None:
    """Apply schema.sql. Idempotent (all statements use IF NOT EXISTS)."""
    ddl = SCHEMA_PATH.read_text()
    # The vector extension must exist before we can register its type adapter,
    # so run the DDL on a raw connection that doesn't try to configure pgvector.
    with ConnectionPool(config.DATABASE_URL, min_size=1, max_size=1, open=True) as pool:
        with pool.connection() as conn:
            conn.execute(ddl)
            conn.commit()


def close_pool() -> None:
    global _pool
    if _pool is not None:
        _pool.close()
        _pool = None


# --------------------------------------------------------------------------
# Observations
# --------------------------------------------------------------------------

def insert_observation(
    text: str,
    embedding: np.ndarray,
    category: str,
    stored_by: str,
    source_summary: str,
) -> str:
    with get_pool().connection() as conn:
        row = conn.execute(
            """
            INSERT INTO observations (text, embedding, category, stored_by, source_summary)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id
            """,
            (text, embedding, category, stored_by, source_summary),
        ).fetchone()
        conn.commit()
        return str(row["id"])


def search_nearest(embedding: np.ndarray, limit: int) -> list[dict[str, Any]]:
    """Return the `limit` most similar observations, with a cosine `relevance`.

    relevance = 1 - cosine_distance, so 1.0 == identical, 0.0 == orthogonal.
    """
    with get_pool().connection() as conn:
        rows = conn.execute(
            """
            SELECT id, text, category, stored_by, source_summary, created_at,
                   1 - (embedding <=> %s) AS relevance
            FROM observations
            ORDER BY embedding <=> %s
            LIMIT %s
            """,
            (embedding, embedding, limit),
        ).fetchall()
        return rows


def delete_observation(obs_id: str) -> bool:
    try:
        parsed = uuid.UUID(obs_id)
    except (ValueError, AttributeError):
        return False
    with get_pool().connection() as conn:
        cur = conn.execute("DELETE FROM observations WHERE id = %s", (parsed,))
        conn.commit()
        return cur.rowcount > 0


def list_observations(
    category: Optional[str] = None,
    stored_by: Optional[str] = None,
    keyword: Optional[str] = None,
    limit: int = 500,
) -> list[dict[str, Any]]:
    """List observations for the admin dashboard, newest first, with optional filters."""
    clauses: list[sql.Composable] = []
    params: list[Any] = []

    if category:
        clauses.append(sql.SQL("category = %s"))
        params.append(category)
    if stored_by:
        clauses.append(sql.SQL("stored_by = %s"))
        params.append(stored_by)
    if keyword:
        clauses.append(sql.SQL("(text ILIKE %s OR source_summary ILIKE %s)"))
        like = f"%{keyword}%"
        params.extend([like, like])

    where = sql.SQL("")
    if clauses:
        where = sql.SQL("WHERE ") + sql.SQL(" AND ").join(clauses)

    query = sql.SQL(
        """
        SELECT id, text, category, stored_by, source_summary, created_at
        FROM observations
        {where}
        ORDER BY created_at DESC
        LIMIT {limit}
        """
    ).format(where=where, limit=sql.Literal(limit))

    with get_pool().connection() as conn:
        return conn.execute(query, params).fetchall()


def distinct_contributors() -> list[str]:
    with get_pool().connection() as conn:
        rows = conn.execute(
            "SELECT DISTINCT stored_by FROM observations ORDER BY stored_by"
        ).fetchall()
        return [r["stored_by"] for r in rows]


# --------------------------------------------------------------------------
# API keys
# --------------------------------------------------------------------------

def insert_api_key(name: str, key_hash: str) -> str:
    with get_pool().connection() as conn:
        row = conn.execute(
            "INSERT INTO api_keys (name, key_hash) VALUES (%s, %s) RETURNING id",
            (name, key_hash),
        ).fetchone()
        conn.commit()
        return str(row["id"])


def get_active_keys() -> list[dict[str, Any]]:
    with get_pool().connection() as conn:
        return conn.execute(
            "SELECT id, name, key_hash FROM api_keys WHERE active = true"
        ).fetchall()


def list_api_keys() -> list[dict[str, Any]]:
    with get_pool().connection() as conn:
        return conn.execute(
            "SELECT id, name, active, created_at FROM api_keys ORDER BY created_at"
        ).fetchall()


def deactivate_api_key(key_id: str) -> bool:
    try:
        parsed = uuid.UUID(key_id)
    except (ValueError, AttributeError):
        return False
    with get_pool().connection() as conn:
        cur = conn.execute(
            "UPDATE api_keys SET active = false WHERE id = %s", (parsed,)
        )
        conn.commit()
        return cur.rowcount > 0


def iso(value: datetime) -> str:
    """Serialize a timestamp to ISO 8601 for JSON output."""
    return value.isoformat() if isinstance(value, datetime) else str(value)
