from __future__ import annotations

import json
import os
import shutil
import sqlite3
import time
import uuid
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Literal

import httpx

from services.report_runner import generate_solar_report, generate_synastry_report

PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
DATA_DIR = os.getenv("ORBITIA_DATA_DIR", os.path.join(PROJECT_ROOT, "data"))
DB_PATH = os.path.join(DATA_DIR, "payments.sqlite3")
REPORTS_DIR = os.path.join(DATA_DIR, "reports")

YOOKASSA_API_URL = "https://api.yookassa.ru/v3"
YOOKASSA_SHOP_ID = os.getenv("YOOKASSA_SHOP_ID", "").strip()
YOOKASSA_SECRET_KEY = os.getenv("YOOKASSA_SECRET_KEY", "").strip()
YOOKASSA_RETURN_URL = os.getenv("YOOKASSA_RETURN_URL", "https://orbitia.info/calculate").strip()
SOLAR_PRICE_RUB = Decimal(os.getenv("SOLAR_PRICE_RUB", "500"))
SYNASTRY_PRICE_RUB = Decimal(os.getenv("SYNASTRY_PRICE_RUB", "1500"))
STRIPE_API_URL = "https://api.stripe.com/v1"
STRIPE_SECRET_KEY = os.getenv("STRIPE_SECRET_KEY", "").strip()
STRIPE_RETURN_URL = os.getenv("STRIPE_RETURN_URL", "https://orbitia.info/calculate").strip()
SOLAR_PRICE_USD = Decimal(os.getenv("SOLAR_PRICE_USD", "6"))
SYNASTRY_PRICE_USD = Decimal(os.getenv("SYNASTRY_PRICE_USD", "17"))

ReportType = Literal["solar", "synastry"]
PaymentProvider = Literal["yookassa", "stripe"]


@dataclass
class Order:
    order_id: str
    payment_id: str | None
    provider: PaymentProvider
    report_type: ReportType
    payload: dict[str, Any]
    status: str
    amount: str
    currency: str
    confirmation_url: str | None = None
    report_path: str | None = None
    report_filename: str | None = None


def _ensure_storage() -> None:
    os.makedirs(DATA_DIR, exist_ok=True)
    os.makedirs(REPORTS_DIR, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                payment_id TEXT,
                provider TEXT NOT NULL DEFAULT 'yookassa',
                report_type TEXT NOT NULL,
                payload_json TEXT NOT NULL,
                status TEXT NOT NULL,
                amount TEXT NOT NULL,
                currency TEXT NOT NULL DEFAULT 'RUB',
                confirmation_url TEXT,
                report_path TEXT,
                report_filename TEXT,
                created_at INTEGER NOT NULL,
                updated_at INTEGER NOT NULL
            )
            """
        )
        existing_columns = {row[1] for row in conn.execute("PRAGMA table_info(orders)").fetchall()}
        if "provider" not in existing_columns:
            conn.execute("ALTER TABLE orders ADD COLUMN provider TEXT NOT NULL DEFAULT 'yookassa'")
        if "currency" not in existing_columns:
            conn.execute("ALTER TABLE orders ADD COLUMN currency TEXT NOT NULL DEFAULT 'RUB'")


def init_payments_db() -> None:
    _ensure_storage()


def _row_to_order(row: sqlite3.Row) -> Order:
    return Order(
        order_id=row["order_id"],
        payment_id=row["payment_id"],
        provider=row["provider"],
        report_type=row["report_type"],
        payload=json.loads(row["payload_json"]),
        status=row["status"],
        amount=row["amount"],
        currency=row["currency"],
        confirmation_url=row["confirmation_url"],
        report_path=row["report_path"],
        report_filename=row["report_filename"],
    )


def get_order(order_id: str) -> Order | None:
    _ensure_storage()
    with sqlite3.connect(DB_PATH) as conn:
        conn.row_factory = sqlite3.Row
        row = conn.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,)).fetchone()
    return _row_to_order(row) if row else None


def _insert_order(order: Order) -> None:
    now = int(time.time())
    _ensure_storage()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            INSERT INTO orders (
                order_id, payment_id, provider, report_type, payload_json, status, amount,
                currency, confirmation_url, report_path, report_filename, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order.order_id,
                order.payment_id,
                order.provider,
                order.report_type,
                json.dumps(order.payload, ensure_ascii=False),
                order.status,
                order.amount,
                order.currency,
                order.confirmation_url,
                order.report_path,
                order.report_filename,
                now,
                now,
            ),
        )


def _update_order(order: Order) -> None:
    now = int(time.time())
    _ensure_storage()
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute(
            """
            UPDATE orders
            SET payment_id = ?, provider = ?, status = ?, amount = ?, currency = ?,
                confirmation_url = ?, report_path = ?, report_filename = ?, updated_at = ?
            WHERE order_id = ?
            """,
            (
                order.payment_id,
                order.provider,
                order.status,
                order.amount,
                order.currency,
                order.confirmation_url,
                order.report_path,
                order.report_filename,
                now,
                order.order_id,
            ),
        )


def _price_for(report_type: ReportType, provider: PaymentProvider) -> Decimal:
    if provider == "stripe":
        return SYNASTRY_PRICE_USD if report_type == "synastry" else SOLAR_PRICE_USD
    return SYNASTRY_PRICE_RUB if report_type == "synastry" else SOLAR_PRICE_RUB


def _payment_description(report_type: ReportType) -> str:
    return "Совместимость партнёров в PDF" if report_type == "synastry" else "Прогноз на год в PDF"


def _require_yookassa_credentials() -> None:
    if not YOOKASSA_SHOP_ID or not YOOKASSA_SECRET_KEY:
        raise RuntimeError("YOOKASSA_SHOP_ID и YOOKASSA_SECRET_KEY не заданы")


def _require_stripe_credentials() -> None:
    if not STRIPE_SECRET_KEY:
        raise RuntimeError("STRIPE_SECRET_KEY не задан")


async def create_payment(
    report_type: ReportType,
    payload: dict[str, Any],
    provider: PaymentProvider = "yookassa",
) -> Order:
    if provider == "stripe":
        return await _create_stripe_payment(report_type, payload)
    return await _create_yookassa_payment(report_type, payload)


async def _create_yookassa_payment(report_type: ReportType, payload: dict[str, Any]) -> Order:
    _require_yookassa_credentials()
    order_id = str(uuid.uuid4())
    amount = _price_for(report_type, "yookassa").quantize(Decimal("0.01"))
    return_url = f"{YOOKASSA_RETURN_URL}?order_id={order_id}"
    order = Order(
        order_id=order_id,
        payment_id=None,
        provider="yookassa",
        report_type=report_type,
        payload=payload,
        status="created",
        amount=f"{amount:.2f}",
        currency="RUB",
    )
    _insert_order(order)

    body = {
        "amount": {"value": order.amount, "currency": "RUB"},
        "capture": True,
        "confirmation": {"type": "redirect", "return_url": return_url},
        "description": _payment_description(report_type),
        "metadata": {"order_id": order_id, "report_type": report_type},
    }
    headers = {"Idempotence-Key": order_id}

    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{YOOKASSA_API_URL}/payments",
            auth=(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY),
            headers=headers,
            json=body,
        )
    response.raise_for_status()
    payment = response.json()

    order.payment_id = payment["id"]
    order.status = payment["status"]
    order.confirmation_url = (payment.get("confirmation") or {}).get("confirmation_url")
    _update_order(order)
    return order


async def _create_stripe_payment(report_type: ReportType, payload: dict[str, Any]) -> Order:
    _require_stripe_credentials()
    order_id = str(uuid.uuid4())
    amount = _price_for(report_type, "stripe").quantize(Decimal("0.01"))
    unit_amount = int(amount * 100)
    success_url = f"{STRIPE_RETURN_URL}?order_id={order_id}"
    cancel_url = STRIPE_RETURN_URL
    order = Order(
        order_id=order_id,
        payment_id=None,
        provider="stripe",
        report_type=report_type,
        payload=payload,
        status="created",
        amount=f"{amount:.2f}",
        currency="USD",
    )
    _insert_order(order)

    data = {
        "mode": "payment",
        "success_url": success_url,
        "cancel_url": cancel_url,
        "client_reference_id": order_id,
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": "usd",
        "line_items[0][price_data][unit_amount]": str(unit_amount),
        "line_items[0][price_data][product_data][name]": _payment_description(report_type),
        "metadata[order_id]": order_id,
        "metadata[report_type]": report_type,
    }
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.post(
            f"{STRIPE_API_URL}/checkout/sessions",
            auth=(STRIPE_SECRET_KEY, ""),
            data=data,
        )
    response.raise_for_status()
    session = response.json()

    order.payment_id = session["id"]
    order.status = session.get("payment_status") or session.get("status") or "open"
    order.confirmation_url = session.get("url")
    _update_order(order)
    return order


async def refresh_payment_status(order: Order) -> Order:
    if not order.payment_id:
        return order
    if order.provider == "stripe":
        return await _refresh_stripe_payment_status(order)
    return await _refresh_yookassa_payment_status(order)


async def _refresh_yookassa_payment_status(order: Order) -> Order:
    _require_yookassa_credentials()
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{YOOKASSA_API_URL}/payments/{order.payment_id}",
            auth=(YOOKASSA_SHOP_ID, YOOKASSA_SECRET_KEY),
        )
    response.raise_for_status()
    payment = response.json()
    order.status = payment["status"]
    _update_order(order)
    return order


async def _refresh_stripe_payment_status(order: Order) -> Order:
    _require_stripe_credentials()
    async with httpx.AsyncClient(timeout=30) as client:
        response = await client.get(
            f"{STRIPE_API_URL}/checkout/sessions/{order.payment_id}",
            auth=(STRIPE_SECRET_KEY, ""),
        )
    response.raise_for_status()
    session = response.json()
    order.status = "succeeded" if session.get("payment_status") == "paid" else session.get("payment_status", "unpaid")
    _update_order(order)
    return order


def is_order_paid(order: Order) -> bool:
    return order.status == "succeeded"


async def ensure_order_report(order: Order) -> Order:
    if not is_order_paid(order):
        raise PermissionError("Заказ ещё не оплачен")
    if order.report_path and os.path.exists(order.report_path):
        return order

    report = (
        await generate_synastry_report(order.payload)
        if order.report_type == "synastry"
        else await generate_solar_report(order.payload)
    )
    safe_filename = report.filename or f"orbitia-{order.order_id}.pdf"
    output_path = os.path.join(REPORTS_DIR, f"{order.order_id}.pdf")
    shutil.move(report.path, output_path)
    order.report_path = output_path
    order.report_filename = safe_filename
    _update_order(order)
    return order


def public_order(order: Order) -> dict[str, Any]:
    return {
        "order_id": order.order_id,
        "payment_id": order.payment_id,
        "provider": order.provider,
        "report_type": order.report_type,
        "status": order.status,
        "paid": is_order_paid(order),
        "amount": order.amount,
        "currency": order.currency,
        "confirmation_url": order.confirmation_url,
        "report_ready": bool(order.report_path and os.path.exists(order.report_path)),
        "report_filename": order.report_filename,
    }
