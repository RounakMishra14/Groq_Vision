from __future__ import annotations

import hashlib
import sqlite3
from datetime import date

DAILY_USAGE_DB_NAME = "users.db"


def _hash_api_key(api_key: str) -> str:
    """Hash the API key so raw keys are never used as database identifiers."""
    return hashlib.sha256((api_key or "").encode("utf-8")).hexdigest()


def init_api_daily_usage_table() -> None:
    """Create a small app-side daily usage table for each Groq API key."""
    conn = sqlite3.connect(DAILY_USAGE_DB_NAME)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS api_daily_usage (
            api_key_hash TEXT NOT NULL,
            usage_date TEXT NOT NULL,
            total_tokens INTEGER DEFAULT 0,
            total_requests INTEGER DEFAULT 0,
            PRIMARY KEY (api_key_hash, usage_date)
        )
        """
    )
    conn.commit()
    conn.close()


def add_api_daily_usage(api_key: str, tokens: int) -> None:
    """Add successful request tokens to today's usage for this API key."""
    api_key_hash = _hash_api_key(api_key)
    today = date.today().isoformat()

    conn = sqlite3.connect(DAILY_USAGE_DB_NAME)
    conn.execute(
        """
        INSERT INTO api_daily_usage (
            api_key_hash,
            usage_date,
            total_tokens,
            total_requests
        )
        VALUES (?, ?, ?, 1)
        ON CONFLICT(api_key_hash, usage_date)
        DO UPDATE SET
            total_tokens = total_tokens + excluded.total_tokens,
            total_requests = total_requests + 1
        """,
        (api_key_hash, today, int(tokens or 0)),
    )
    conn.commit()
    conn.close()


def get_api_daily_usage(api_key: str) -> dict:
    """Return today's app-side usage for this Groq API key."""
    init_api_daily_usage_table()

    api_key_hash = _hash_api_key(api_key)
    today = date.today().isoformat()

    conn = sqlite3.connect(DAILY_USAGE_DB_NAME)
    row = conn.execute(
        """
        SELECT total_tokens, total_requests
        FROM api_daily_usage
        WHERE api_key_hash=? AND usage_date=?
        """,
        (api_key_hash, today),
    ).fetchone()
    conn.close()

    if not row:
        return {"tokens": 0, "requests": 0}

    return {"tokens": int(row[0] or 0), "requests": int(row[1] or 0)}
