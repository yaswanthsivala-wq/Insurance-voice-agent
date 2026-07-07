"""
Persistent storage for intakes — Supabase (permanent) or SQLite (local fallback).

Backend selection is automatic:
  * If SUPABASE_URL and SUPABASE_KEY are set  -> Supabase (Postgres, permanent)
  * Otherwise                                 -> local SQLite file

Both backends expose the same four functions, so app.py doesn't care which is
active. Call backend_name() to see which one is in use (surfaced at /health).

Env vars:
    SUPABASE_URL   - your project URL (https://xxxx.supabase.co)
    SUPABASE_KEY   - a SECRET key (sb_secret_...) — server-side only, never in the browser
    DATABASE_PATH  - SQLite file path when Supabase isn't configured (default "intakes.db")

Supabase table (create once in the Supabase SQL editor):

    create table if not exists intakes (
        id         bigint generated always as identity primary key,
        created_at timestamptz not null default now(),
        type       text not null,
        summary    text not null,
        transcript text,
        language   text,
        source     text
    );
"""

import os
import sqlite3
from datetime import datetime, timezone

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
DB_PATH = os.getenv("DATABASE_PATH", "intakes.db")
TABLE = "intakes"

_USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)
_supabase = None


def backend_name():
    return "supabase" if _USE_SUPABASE else "sqlite"


# ----------------------------------------------------------------------------
# Supabase client (created lazily)
# ----------------------------------------------------------------------------
def _client():
    global _supabase
    if _supabase is None:
        from supabase import create_client
        _supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
    return _supabase


# ----------------------------------------------------------------------------
# SQLite helpers
# ----------------------------------------------------------------------------
def _connect():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    return conn


# ----------------------------------------------------------------------------
# Public interface
# ----------------------------------------------------------------------------
def init_db():
    """SQLite: create the table. Supabase: table is created once in the
    dashboard (see the SQL in this file's docstring), so this is a no-op."""
    if _USE_SUPABASE:
        return
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS intakes (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT    NOT NULL,
                type       TEXT    NOT NULL,
                summary    TEXT    NOT NULL,
                transcript TEXT,
                language   TEXT,
                source     TEXT
            )
            """
        )


def save_intake(type_, summary, transcript, language, source):
    """Insert one intake and return the saved row as a dict."""
    created_at = datetime.now(timezone.utc).isoformat()
    row = {
        "created_at": created_at,
        "type": type_,
        "summary": summary,
        "transcript": transcript,
        "language": language,
        "source": source,
    }

    if _USE_SUPABASE:
        resp = _client().table(TABLE).insert(row).execute()
        return resp.data[0] if resp.data else row

    with _connect() as conn:
        cur = conn.execute(
            """INSERT INTO intakes (created_at, type, summary, transcript, language, source)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (created_at, type_, summary, transcript, language, source),
        )
        row["id"] = cur.lastrowid
    return row


def get_all():
    """Return every intake, newest first."""
    if _USE_SUPABASE:
        resp = _client().table(TABLE).select("*").order("id", desc=True).execute()
        return resp.data or []

    with _connect() as conn:
        rows = conn.execute("SELECT * FROM intakes ORDER BY id DESC").fetchall()
    return [dict(r) for r in rows]


def clear_all():
    if _USE_SUPABASE:
        # delete needs a filter; id >= 0 matches every row
        _client().table(TABLE).delete().gte("id", 0).execute()
        return
    with _connect() as conn:
        conn.execute("DELETE FROM intakes")
