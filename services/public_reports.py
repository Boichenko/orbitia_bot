from __future__ import annotations

import json
import os
import secrets
import shutil
import sqlite3
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("ORBITIA_DATA_DIR", str(PROJECT_ROOT / "data")))
DB_PATH = DATA_DIR / "payments.sqlite3"
REPORTS_DIR = DATA_DIR / "public_reports"
PUBLIC_BASE_URL = os.getenv(
    "ORBITIA_PUBLIC_BASE_URL", "https://orbitia.info/api/orbitia"
).rstrip("/")


@dataclass(frozen=True)
class PublicReport:
    token: str
    report_type: str
    report_json: dict[str, Any] | None
    pdf_path: str
    filename: str

    @property
    def report_url(self) -> str:
        return f"{PUBLIC_BASE_URL}/r/{self.token}"

    @property
    def pdf_url(self) -> str:
        return f"{PUBLIC_BASE_URL}/r/{self.token}/pdf"


def init_public_reports_db() -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS public_reports (
                token TEXT PRIMARY KEY,
                owner_key TEXT,
                report_type TEXT NOT NULL,
                report_json TEXT,
                pdf_path TEXT NOT NULL,
                filename TEXT NOT NULL,
                created_at INTEGER NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_public_reports_owner ON public_reports(owner_key)"
        )


def create_public_report(
    *,
    report_type: str,
    pdf_source_path: str,
    filename: str,
    report_json: dict[str, Any] | None,
    owner_key: str | None = None,
) -> PublicReport:
    init_public_reports_db()
    if owner_key:
        existing = get_public_report_by_owner(owner_key)
        if existing:
            return existing

    token = secrets.token_urlsafe(32)
    pdf_path = REPORTS_DIR / f"{token}.pdf"
    shutil.copy2(pdf_source_path, pdf_path)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO public_reports (
                token, owner_key, report_type, report_json, pdf_path, filename, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                token,
                owner_key,
                report_type,
                json.dumps(report_json, ensure_ascii=False) if report_json else None,
                str(pdf_path),
                filename,
                int(time.time()),
            ),
        )
    return PublicReport(token, report_type, report_json, str(pdf_path), filename)


def _row_to_report(row: sqlite3.Row | None) -> PublicReport | None:
    if not row:
        return None
    raw_json = row["report_json"]
    return PublicReport(
        token=row["token"],
        report_type=row["report_type"],
        report_json=json.loads(raw_json) if raw_json else None,
        pdf_path=row["pdf_path"],
        filename=row["filename"],
    )


def get_public_report(token: str) -> PublicReport | None:
    init_public_reports_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM public_reports WHERE token = ?", (token,)
        ).fetchone()
    return _row_to_report(row)


def get_public_report_by_owner(owner_key: str) -> PublicReport | None:
    init_public_reports_db()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute(
            "SELECT * FROM public_reports WHERE owner_key = ? ORDER BY created_at DESC LIMIT 1",
            (owner_key,),
        ).fetchone()
    return _row_to_report(row)
