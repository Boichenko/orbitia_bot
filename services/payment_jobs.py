"""Persistent input data for paid solar calculations.

FSM data belongs to the current conversation and may legitimately be cleared by
``/start``.  Paid jobs must outlive that state, so their input is stored in
SQLite before the invoice is sent.
"""

import json
import sqlite3
import time
import uuid
from typing import Any

from services.analytics import DB_PATH


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS payment_jobs (
            job_id TEXT PRIMARY KEY,
            user_id INTEGER NOT NULL,
            input_data TEXT NOT NULL,
            created_at INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending'
        )
        """
    )
    columns = {row[1] for row in conn.execute("PRAGMA table_info(payment_jobs)")}
    if "status" not in columns:
        conn.execute(
            "ALTER TABLE payment_jobs ADD COLUMN status TEXT NOT NULL DEFAULT 'pending'"
        )
        conn.commit()
    return conn


def create_payment_job(user_id: int, input_data: dict[str, Any]) -> str:
    job_id = uuid.uuid4().hex
    conn = _get_conn()
    try:
        conn.execute(
            """
            INSERT INTO payment_jobs (job_id, user_id, input_data, created_at)
            VALUES (?, ?, ?, ?)
            """,
            (job_id, user_id, json.dumps(input_data, ensure_ascii=False), int(time.time())),
        )
        conn.commit()
        return job_id
    finally:
        conn.close()


def get_payment_job(job_id: str, user_id: int) -> dict[str, Any] | None:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT input_data FROM payment_jobs WHERE job_id = ? AND user_id = ?",
            (job_id, user_id),
        ).fetchone()
        return json.loads(row[0]) if row else None
    finally:
        conn.close()


def mark_payment_job_active(job_id: str, user_id: int) -> None:
    _set_status(job_id, user_id, "active")


def finish_payment_job(job_id: str, user_id: int) -> None:
    conn = _get_conn()
    try:
        conn.execute(
            """
            UPDATE payment_jobs SET status = 'finished'
            WHERE job_id = ? AND user_id = ? AND status = 'active'
            """,
            (job_id, user_id),
        )
        conn.commit()
    finally:
        conn.close()


def cancel_payment_job(job_id: str, user_id: int) -> bool:
    conn = _get_conn()
    try:
        cursor = conn.execute(
            """
            UPDATE payment_jobs SET status = 'cancelled'
            WHERE job_id = ? AND user_id = ? AND status = 'active'
            """,
            (job_id, user_id),
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()


def get_active_payment_job(user_id: int) -> str | None:
    conn = _get_conn()
    try:
        row = conn.execute(
            """
            SELECT job_id FROM payment_jobs
            WHERE user_id = ? AND status = 'active'
            ORDER BY created_at DESC LIMIT 1
            """,
            (user_id,),
        ).fetchone()
        return row[0] if row else None
    finally:
        conn.close()


def is_payment_job_cancelled(job_id: str, user_id: int) -> bool:
    conn = _get_conn()
    try:
        row = conn.execute(
            "SELECT status FROM payment_jobs WHERE job_id = ? AND user_id = ?",
            (job_id, user_id),
        ).fetchone()
        return bool(row and row[0] == "cancelled")
    finally:
        conn.close()


def _set_status(job_id: str, user_id: int, status: str) -> int:
    conn = _get_conn()
    try:
        cursor = conn.execute(
            "UPDATE payment_jobs SET status = ? WHERE job_id = ? AND user_id = ?",
            (status, job_id, user_id),
        )
        conn.commit()
        return cursor.rowcount
    finally:
        conn.close()
