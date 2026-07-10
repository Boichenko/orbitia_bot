"""
Простая аналитика на SQLite: откуда пришёл пользователь (через ?start=...
параметр в deep-link) и какие события воронки он прошёл.

Файл базы — analytics.db рядом с main.py. Никаких внешних сервисов не нужно.
"""

from __future__ import annotations

import os
import sqlite3
import time

DB_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), "analytics.db")


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db() -> None:
    conn = _get_conn()
    try:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                source TEXT,
                first_seen_at INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS events (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                event TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_event ON events(event)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id)")
        conn.commit()
    finally:
        conn.close()


def register_user_source(user_id: int, source: str | None) -> None:
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id, source, first_seen_at) VALUES (?, ?, ?)",
            (user_id, source, int(time.time())),
        )
        conn.commit()
    finally:
        conn.close()


def log_event(user_id: int, event: str) -> None:
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT INTO events (user_id, event, created_at) VALUES (?, ?, ?)",
            (user_id, event, int(time.time())),
        )
        conn.commit()
    finally:
        conn.close()


def funnel_summary(source: str | None = None) -> dict[str, int]:
    conn = _get_conn()
    try:
        if source is not None:
            rows = conn.execute(
                """
                SELECT e.event, COUNT(DISTINCT e.user_id)
                FROM events e
                JOIN users u ON u.user_id = e.user_id
                WHERE u.source = ?
                GROUP BY e.event
                """,
                (source,),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT event, COUNT(DISTINCT user_id) FROM events GROUP BY event"
            ).fetchall()
        return dict(rows)
    finally:
        conn.close()


def count_users_with_events(events: tuple[str, ...], source: str | None = None) -> int:
    if not events:
        return 0

    placeholders = ",".join("?" for _ in events)
    params: list[object] = list(events)
    source_join = ""
    source_where = ""
    if source is not None:
        source_join = "JOIN users u ON u.user_id = e.user_id"
        source_where = "AND u.source = ?"
        params.append(source)

    conn = _get_conn()
    try:
        row = conn.execute(
            f"""
            SELECT COUNT(*)
            FROM (
                SELECT e.user_id
                FROM events e
                {source_join}
                WHERE e.event IN ({placeholders})
                {source_where}
                GROUP BY e.user_id
                HAVING COUNT(DISTINCT e.event) = ?
            ) matched_users
            """,
            (*params, len(events)),
        ).fetchone()
        return int(row[0] if row else 0)
    finally:
        conn.close()


def count_users_with_any_event(events: tuple[str, ...], source: str | None = None) -> int:
    if not events:
        return 0

    placeholders = ",".join("?" for _ in events)
    params: list[object] = list(events)
    source_join = ""
    source_where = ""
    if source is not None:
        source_join = "JOIN users u ON u.user_id = e.user_id"
        source_where = "AND u.source = ?"
        params.append(source)

    conn = _get_conn()
    try:
        row = conn.execute(
            f"""
            SELECT COUNT(DISTINCT e.user_id)
            FROM events e
            {source_join}
            WHERE e.event IN ({placeholders})
            {source_where}
            """,
            params,
        ).fetchone()
        return int(row[0] if row else 0)
    finally:
        conn.close()


def list_sources() -> list[tuple[str, int]]:
    conn = _get_conn()
    try:
        rows = conn.execute(
            """
            SELECT COALESCE(source, '(без метки)') AS src, COUNT(*) AS cnt
            FROM users
            GROUP BY src
            ORDER BY cnt DESC
            """
        ).fetchall()
        return rows
    finally:
        conn.close()
