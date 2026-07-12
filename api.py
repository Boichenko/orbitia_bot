from __future__ import annotations

import os
from typing import Annotated, Literal, Optional

from dotenv import load_dotenv
from fastapi import Depends, FastAPI, Header, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, field_validator
from starlette.background import BackgroundTask

from services.geocoding import search_city
from services.payments import (
    create_payment,
    ensure_order_report,
    get_order,
    init_payments_db,
    public_order,
    refresh_payment_status,
)
from services.report_runner import generate_solar_report, generate_synastry_report

load_dotenv()

API_TOKEN = os.getenv("ORBITIA_API_TOKEN", "").strip()
ALLOW_FREE_REPORTS = os.getenv("ORBITIA_ALLOW_FREE_REPORTS", "false").strip().lower() == "true"
ALLOWED_ORIGINS = [
    origin.strip()
    for origin in os.getenv(
        "ORBITIA_API_ALLOWED_ORIGINS",
        "http://localhost:5173,http://127.0.0.1:5173,http://localhost:3000,http://127.0.0.1:3000,https://orbitia.info",
    ).split(",")
    if origin.strip()
]

app = FastAPI(title="Orbitia Reports API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["authorization", "content-type"],
)


class City(BaseModel):
    label: str
    display_name: str | None = None
    lat: float
    lon: float


class SolarReportRequest(BaseModel):
    report_type: Literal["solar"] = "solar"
    person_name: str = Field(min_length=1, max_length=50)
    birth_date: str = Field(pattern=r"^\d{2}\.\d{2}\.\d{4}$")
    birth_time: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    birth_place: City
    solar_place: City
    solar_cycle_year: int = Field(ge=1900, le=2100)
    user_context: Optional[str] = Field(default=None, max_length=1200)

    @field_validator("birth_time")
    @classmethod
    def validate_time(cls, value: str | None) -> str | None:
        if value is None:
            return value
        hour, minute = (int(part) for part in value.split(":"))
        if hour > 23 or minute > 59:
            raise ValueError("invalid time")
        return value


class SynastryReportRequest(BaseModel):
    report_type: Literal["synastry"] = "synastry"
    person_name: str = Field(min_length=1, max_length=50)
    birth_date: str = Field(pattern=r"^\d{2}\.\d{2}\.\d{4}$")
    birth_time: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    birth_place: City
    partner_name: str = Field(min_length=1, max_length=50)
    partner_birth_date: str = Field(pattern=r"^\d{2}\.\d{2}\.\d{4}$")
    partner_birth_time: Optional[str] = Field(default=None, pattern=r"^\d{2}:\d{2}$")
    partner_birth_place: City

    @field_validator("birth_time", "partner_birth_time")
    @classmethod
    def validate_time(cls, value: str | None) -> str | None:
        if value is None:
            return value
        hour, minute = (int(part) for part in value.split(":"))
        if hour > 23 or minute > 59:
            raise ValueError("invalid time")
        return value


class CreatePaymentRequest(BaseModel):
    report_type: Literal["solar", "synastry"]
    payload: dict


async def require_api_token(authorization: Annotated[str | None, Header()] = None) -> None:
    if not API_TOKEN:
        return
    expected = f"Bearer {API_TOKEN}"
    if authorization != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@app.on_event("startup")
async def startup() -> None:
    init_payments_db()


@app.get("/cities", dependencies=[Depends(require_api_token)])
async def cities(q: str = Query(min_length=2), limit: int = Query(default=5, ge=1, le=8)):
    return await search_city(q, limit=limit)


@app.post("/payments", dependencies=[Depends(require_api_token)])
async def payment_create(payload: CreatePaymentRequest):
    if payload.report_type == "solar":
        report_payload = SolarReportRequest.model_validate(payload.payload).model_dump()
    else:
        report_payload = SynastryReportRequest.model_validate(payload.payload).model_dump()

    try:
        order = await create_payment(payload.report_type, report_payload)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Не удалось создать платёж: {exc}") from exc
    return public_order(order)


@app.get("/payments/orders/{order_id}", dependencies=[Depends(require_api_token)])
async def payment_status(order_id: str):
    order = get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    try:
        order = await refresh_payment_status(order)
    except Exception as exc:
        raise HTTPException(status_code=502, detail=f"Не удалось проверить платёж: {exc}") from exc
    return public_order(order)


@app.post("/payments/orders/{order_id}/report", dependencies=[Depends(require_api_token)])
async def paid_report(order_id: str):
    order = get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail="Заказ не найден")
    order = await refresh_payment_status(order)
    if not order.status == "succeeded":
        raise HTTPException(status_code=402, detail="Заказ ещё не оплачен")

    try:
        order = await ensure_order_report(order)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Не удалось сформировать PDF: {exc}") from exc
    return FileResponse(
        order.report_path,
        media_type="application/pdf",
        filename=order.report_filename or "orbitia-report.pdf",
    )


@app.post("/reports/solar", dependencies=[Depends(require_api_token)])
async def solar_report(payload: SolarReportRequest):
    if not ALLOW_FREE_REPORTS:
        raise HTTPException(status_code=403, detail="Прямой расчёт отключён. Сначала создайте платёж.")
    report = await generate_solar_report(payload.model_dump())
    return FileResponse(
        report.path,
        media_type="application/pdf",
        filename=report.filename,
        background=BackgroundTask(lambda path: os.path.exists(path) and os.remove(path), report.path),
    )


@app.post("/reports/synastry", dependencies=[Depends(require_api_token)])
async def synastry_report(payload: SynastryReportRequest):
    if not ALLOW_FREE_REPORTS:
        raise HTTPException(status_code=403, detail="Прямой расчёт отключён. Сначала создайте платёж.")
    report = await generate_synastry_report(payload.model_dump())
    return FileResponse(
        report.path,
        media_type="application/pdf",
        filename=report.filename,
        background=BackgroundTask(lambda path: os.path.exists(path) and os.remove(path), report.path),
    )
