from __future__ import annotations

import hashlib
import hmac
import os
import sqlite3
import time
from pathlib import Path

DB_NAME = "users.db"


def get_connection() -> sqlite3.Connection:
    return sqlite3.connect(DB_NAME)


def _hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
    return f"pbkdf2_sha256${salt.hex()}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    if not stored:
        return False

    # Supports older plain-text demo users if you already created them.
    # After login, you can recreate accounts for stronger storage if needed.
    if not stored.startswith("pbkdf2_sha256$"):
        return password == stored

    try:
        _, salt_hex, digest_hex = stored.split("$", 2)
        salt = bytes.fromhex(salt_hex)
        expected = bytes.fromhex(digest_hex)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, 120_000)
        return hmac.compare_digest(actual, expected)
    except Exception:
        return False


def init_db() -> None:
    conn = get_connection()

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            username TEXT PRIMARY KEY,
            password TEXT NOT NULL,
            groq_key TEXT DEFAULT ''
        )
        """
    )

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS token_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            timestamp REAL NOT NULL,
            image_number INTEGER,
            file_name TEXT,
            prompt_tokens INTEGER DEFAULT 0,
            completion_tokens INTEGER DEFAULT 0,
            total_tokens INTEGER DEFAULT 0,
            duration_seconds REAL DEFAULT 0,
            model TEXT,
            status TEXT DEFAULT 'success',
            error_message TEXT DEFAULT ''
        )
        """
    )

    conn.commit()
    conn.close()


def create_user(username: str, password: str) -> bool:
    username = username.strip().lower()
    conn = get_connection()

    try:
        conn.execute(
            """
            INSERT INTO users (username, password, groq_key)
            VALUES (?, ?, '')
            """,
            (username, _hash_password(password)),
        )
        conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False
    finally:
        conn.close()


def validate_user(username: str, password: str) -> bool:
    username = username.strip().lower()
    conn = get_connection()

    row = conn.execute(
        "SELECT password FROM users WHERE username=?",
        (username,),
    ).fetchone()

    conn.close()

    if not row:
        return False

    return _verify_password(password, row[0])


def save_groq_key(username: str, encrypted_key: str) -> None:
    conn = get_connection()
    conn.execute(
        "UPDATE users SET groq_key=? WHERE username=?",
        (encrypted_key, username.strip().lower()),
    )
    conn.commit()
    conn.close()


def get_groq_key(username: str) -> str | None:
    conn = get_connection()
    row = conn.execute(
        "SELECT groq_key FROM users WHERE username=?",
        (username.strip().lower(),),
    ).fetchone()
    conn.close()

    if row and row[0]:
        return row[0]
    return None


def save_token_usage(
    *,
    username: str,
    image_number: int,
    file_name: str,
    prompt_tokens: int,
    completion_tokens: int,
    total_tokens: int,
    duration_seconds: float,
    model: str,
    status: str = "success",
    error_message: str = "",
) -> None:
    conn = get_connection()
    conn.execute(
        """
        INSERT INTO token_usage (
            username, timestamp, image_number, file_name,
            prompt_tokens, completion_tokens, total_tokens,
            duration_seconds, model, status, error_message
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            username.strip().lower(),
            time.time(),
            image_number,
            file_name,
            int(prompt_tokens or 0),
            int(completion_tokens or 0),
            int(total_tokens or 0),
            float(duration_seconds or 0),
            model,
            status,
            error_message or "",
        ),
    )
    conn.commit()
    conn.close()


def get_user_token_summary(username: str) -> dict:
    conn = get_connection()
    row = conn.execute(
        """
        SELECT
            COUNT(CASE WHEN status='success' THEN 1 END),
            COUNT(CASE WHEN status='error' THEN 1 END),
            COALESCE(SUM(CASE WHEN status='success' THEN prompt_tokens ELSE 0 END), 0),
            COALESCE(SUM(CASE WHEN status='success' THEN completion_tokens ELSE 0 END), 0),
            COALESCE(SUM(CASE WHEN status='success' THEN total_tokens ELSE 0 END), 0)
        FROM token_usage
        WHERE username=?
        """,
        (username.strip().lower(),),
    ).fetchone()
    conn.close()

    return {
        "total_requests": int(row[0] or 0),
        "failed_requests": int(row[1] or 0),
        "prompt_tokens": int(row[2] or 0),
        "completion_tokens": int(row[3] or 0),
        "total_tokens": int(row[4] or 0),
    }
