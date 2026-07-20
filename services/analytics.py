"""
Простая аналитика на SQLite: откуда пришёл пользователь (через ?start=...
параметр в deep-link) и какие события воронки он прошёл.

Файл базы — analytics.db рядом с main.py. Никаких внешних сервисов не нужно.
"""

from __future__ import annotations

import json
import os
import sqlite3
import time
import uuid

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
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS source_visits (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                source TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS payments (
                telegram_charge_id TEXT PRIMARY KEY,
                provider_charge_id TEXT,
                user_id INTEGER NOT NULL,
                report_type TEXT NOT NULL,
                amount INTEGER NOT NULL,
                currency TEXT NOT NULL,
                source TEXT,
                job_id TEXT,
                created_at INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS report_artifacts (
                artifact_id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                report_type TEXT NOT NULL,
                job_id TEXT,
                prompts_json TEXT NOT NULL,
                response_text TEXT,
                filename TEXT,
                created_at INTEGER NOT NULL
            )
            """
        )
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_event ON events(event)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_events_user ON events(user_id)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_source_visits_source ON source_visits(source)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_payments_source ON payments(source)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_report_artifacts_user ON report_artifacts(user_id)")
        conn.commit()
    finally:
        conn.close()


def register_user_source(user_id: int, source: str | None) -> None:
    source = source.strip() if source else None
    conn = _get_conn()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO users (user_id, source, first_seen_at) VALUES (?, ?, ?)",
            (user_id, source, int(time.time())),
        )
        # A first unlabelled visit must not permanently hide a later labelled
        # deep-link visit. Keep the latest explicit attribution on the user.
        if source:
            conn.execute("UPDATE users SET source = ? WHERE user_id = ?", (source, user_id))
            conn.execute(
                """
                INSERT INTO source_visits (user_id, source, created_at)
                VALUES (?, ?, ?)
                """,
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
            SELECT COALESCE(source, '(без метки)') AS src, COUNT(DISTINCT user_id) AS cnt
            FROM (
                SELECT user_id, source FROM users
                UNION ALL
                SELECT user_id, source FROM source_visits
            )
            GROUP BY src
            ORDER BY cnt DESC
            """
        ).fetchall()
        return rows
    finally:
        conn.close()


def list_sources_for_any_event(events: tuple[str, ...]) -> list[tuple[str, int]]:
    if not events:
        return []

    placeholders = ",".join("?" for _ in events)
    conn = _get_conn()
    try:
        rows = conn.execute(
            f"""
            SELECT COALESCE(attributions.source, '(без метки)') AS src,
                   COUNT(DISTINCT selected_users.user_id) AS cnt
            FROM (
                SELECT DISTINCT user_id
                FROM events
                WHERE event IN ({placeholders})
            ) selected_users
            LEFT JOIN (
                SELECT user_id, source FROM users
                UNION
                SELECT user_id, source FROM source_visits
            ) attributions ON attributions.user_id = selected_users.user_id
            GROUP BY src
            ORDER BY cnt DESC
            """,
            events,
        ).fetchall()
        return rows
    finally:
        conn.close()


def record_payment(
    *,
    telegram_charge_id: str,
    provider_charge_id: str | None,
    user_id: int,
    report_type: str,
    amount: int,
    currency: str,
    job_id: str | None,
) -> None:
    """Persist an actual Telegram payment, idempotently."""
    conn = _get_conn()
    try:
        source_row = conn.execute(
            "SELECT source FROM users WHERE user_id = ?", (user_id,)
        ).fetchone()
        source = source_row[0] if source_row else None
        conn.execute(
            """
            INSERT OR IGNORE INTO payments (
                telegram_charge_id, provider_charge_id, user_id, report_type,
                amount, currency, source, job_id, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                telegram_charge_id,
                provider_charge_id,
                user_id,
                report_type,
                amount,
                currency,
                source,
                job_id,
                int(time.time()),
            ),
        )
        conn.commit()
    finally:
        conn.close()


def payment_summary() -> list[tuple[str, str, str, int, int]]:
    """report_type, currency, source, payment count, total amount."""
    conn = _get_conn()
    try:
        return conn.execute(
            """
            SELECT report_type, currency, COALESCE(source, '(без метки)'),
                   COUNT(*), SUM(amount)
            FROM payments
            GROUP BY report_type, currency, COALESCE(source, '(без метки)')
            ORDER BY report_type, currency, SUM(amount) DESC
            """
        ).fetchall()
    finally:
        conn.close()


def save_report_artifact(
    *,
    user_id: int,
    report_type: str,
    job_id: str | None,
    prompts: list[dict[str, str]],
    response_text: str,
    filename: str,
) -> str:
    """Save every prompt used for the PDF after the PDF was built."""
    artifact_id = uuid.uuid4().hex
    conn = _get_conn()
    try:
        conn.execute(
            """
            INSERT INTO report_artifacts (
                artifact_id, user_id, report_type, job_id, prompts_json,
                response_text, filename, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                artifact_id,
                user_id,
                report_type,
                job_id,
                json.dumps(prompts, ensure_ascii=False),
                response_text,
                filename,
                int(time.time()),
            ),
        )
        conn.commit()
        return artifact_id
    finally:
        conn.close()
