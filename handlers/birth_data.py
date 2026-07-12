from __future__ import annotations

import asyncio
import os
import re
import time
from datetime import date, datetime
from typing import Optional

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputMediaPhoto,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
    User,
)

from handlers.start import start_flow
from services.analytics import (
    count_users_with_any_event,
    count_users_with_events,
    funnel_summary,
    list_sources_for_any_event,
    log_event,
)
from services.claude_client import interpret_solar_chart
from services.geocoding import search_city
from services.prompt_builder import (
    build_solar_json_prompt,
    build_solar_prompt,
    build_synastry_json_prompt,
    build_synastry_prompt,
)
from services.report_file import extract_main_theme
from services.report_json import (
    normalize_solar_report,
    normalize_synastry_report,
    parse_report_json,
    structured_report_to_teaser,
)
from services.report_insights import build_solar_profile, build_synastry_profile
from services.report_pdf import markdown_to_pdf, structured_solar_to_pdf, structured_synastry_to_pdf
from services.solar_chart import compute_solar_return
from services.synastry_chart import compute_synastry
from services.timezone_lookup import get_timezone
from services.url_builder import compute_solar_cycle_year
from states import SolarStates

router = Router()

DATE_RE = re.compile(r"^(\d{2})\.(\d{2})\.(\d{4})$")
TIME_RE = re.compile(r"^(\d{2}):(\d{2})$")
YEAR_RE = re.compile(r"^(\d{4})$")
NO_TIME_ANSWERS = {"не знаю", "не знаю точно", "незнаю", "не помню"}

SOLAR_STARS_PRICE = int(os.getenv("SOLAR_STARS_PRICE", "100"))
SYNASTRY_STARS_PRICE = int(os.getenv("SYNASTRY_STARS_PRICE", "500"))
PAYMENTS_ENABLED = os.getenv("PAYMENTS_ENABLED", "false").strip().lower() == "true"
ADMIN_USER_ID = os.getenv("ADMIN_USER_ID", "").strip()
REPORT_TYPES = {"solar", "synastry"}
PROJECT_ROOT = os.path.dirname(os.path.dirname(__file__))
TEST_ANNA_BIRTH_PLACE = {
    "label": "Холмск, Сахалинская область, Россия",
    "lat": 47.0408,
    "lon": 142.0417,
}
TEST_SOLAR_PLACE = {
    "label": "Варшава, Польша",
    "lat": 52.2297,
    "lon": 21.0122,
}
TEST_ALEXANDER_BIRTH_PLACE = {
    "label": "Минск, Беларусь",
    "lat": 53.9006,
    "lon": 27.5590,
}
PREVIEW_PATHS = {
    "solar": [
        (
            os.path.join(PROJECT_ROOT, "assets", "previews", "solar_year_map.png"),
            "Карта года в одном экране: сферы, баллы и краткий анализ. Это пример визуализации, твои значения будут рассчитаны персонально.",
        ),
        (
            os.path.join(PROJECT_ROOT, "assets", "previews", "solar_main_theme.png"),
            "Главная тема года и дополнительные акценты: в твоём отчёте формулировки будут собраны по личному расчёту.",
        ),
        (
            os.path.join(PROJECT_ROOT, "assets", "previews", "solar_category.png"),
            "Пример глубокой страницы категории: события, риски, действия и астрологическое основание. Текст в твоём отчёте будет индивидуальным.",
        ),
    ],
    "synastry": [
        (
            os.path.join(PROJECT_ROOT, "assets", "previews", "synastry_wheel.png"),
            "Пример визуализации. В твоей синастрии значения будут рассчитаны персонально.",
        ),
        (
            os.path.join(PROJECT_ROOT, "assets", "previews", "synastry_recommendations.png"),
            "Пример фрагмента. После оплаты бот сформирует индивидуальный разбор пары.",
        ),
    ],
}
MONTH_NAMES = {
    1: "января",
    2: "февраля",
    3: "марта",
    4: "апреля",
    5: "мая",
    6: "июня",
    7: "июля",
    8: "августа",
    9: "сентября",
    10: "октября",
    11: "ноября",
    12: "декабря",
}


def _is_admin(user_id: Optional[int]) -> bool:
    return bool(ADMIN_USER_ID) and str(user_id) == ADMIN_USER_ID


def _test_place(place: dict) -> dict:
    return dict(place)


def _log_report_event(user_id: int, data: dict, step: str) -> None:
    report_type = data.get("report_type")
    if report_type in REPORT_TYPES:
        log_event(user_id, f"{report_type}_{step}")


def _log_generated_event(user_id: int, data: dict, report_type: str) -> None:
    log_event(user_id, f"{report_type}_generated")
    if data.get("payment_confirmed"):
        log_event(user_id, f"{report_type}_generated_after_payment")
    elif data.get("is_test_report"):
        log_event(user_id, f"{report_type}_generated_test")
    else:
        log_event(user_id, f"{report_type}_generated_free")


# ---------------------------------------------------------------------------
# Выбор типа разбора
# ---------------------------------------------------------------------------


@router.callback_query(SolarStates.choosing_report_type, F.data.startswith("report:"))
async def process_report_type(callback: CallbackQuery, state: FSMContext):
    report_type = callback.data.split(":")[1]
    await callback.answer()

    await _begin_report_type(callback.message, state, callback.from_user.id, report_type, edit=True)


async def _begin_report_type(answer_target, state: FSMContext, user_id: int, report_type: str, edit: bool = False) -> None:
    if report_type not in {"solar", "synastry"}:
        await answer_target.answer("Не поняла тип расчёта. Нажми /start и выбери ещё раз.")
        return

    log_event(user_id, f"{report_type}_selected")
    await state.update_data(report_type=report_type)
    if report_type == "synastry":
        text = "Считаем синастрию / совместимость 💞\n\nСначала соберём твои данные. Как тебя зовут?"
    else:
        text = "Считаем соляр 🌞\n\nКак зовут человека, для которого считаем?"
    if edit:
        await answer_target.edit_text(text)
    else:
        await answer_target.answer(text)
    await state.set_state(SolarStates.waiting_name)


@router.message(Command("test_solar"))
async def cmd_test_solar(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id if message.from_user else None):
        return

    await state.clear()
    await state.update_data(
        report_type="solar",
        person_name="Анна",
        birth_date="25.10.1992",
        birth_time="04:00",
        birth_place=_test_place(TEST_ANNA_BIRTH_PLACE),
        solar_place=_test_place(TEST_SOLAR_PLACE),
        solar_cycle_year=2026,
        user_context=None,
        is_test_report=True,
    )
    await message.answer("🧪 Запускаю тестовый соляр: Анна, 25.10.1992 04:00, Холмск → Варшава, 2026-2027.")
    await _run_solar_analysis(message, message.from_user, state)


@router.message(Command("test_sin"))
@router.message(Command("test_synastry"))
@router.message(Command("test_sin3"))
async def cmd_test_synastry(message: Message, state: FSMContext):
    if not _is_admin(message.from_user.id if message.from_user else None):
        return

    await state.clear()
    await state.update_data(
        report_type="synastry",
        person_name="Анна",
        birth_date="25.10.1992",
        birth_time="04:00",
        birth_place=_test_place(TEST_ANNA_BIRTH_PLACE),
        partner_name="Александр",
        partner_birth_date="01.06.1992",
        partner_birth_time="04:24",
        partner_birth_place=_test_place(TEST_ALEXANDER_BIRTH_PLACE),
        is_test_report=True,
    )
    await message.answer("🧪 Запускаю тестовую синастрию: Анна + Александр.")
    await _run_synastry_analysis(message, message.from_user, state)


# ---------------------------------------------------------------------------
# Имя
# ---------------------------------------------------------------------------


@router.message(SolarStates.waiting_name)
async def process_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if not name:
        await message.answer("Напиши имя текстом.")
        return

    await state.update_data(person_name=name[:50])

    data = await state.get_data()
    if data.get("return_to_confirmation"):
        await state.update_data(return_to_confirmation=False)
        await show_confirmation(message, state)
        return

    data = await state.get_data()
    log_event(message.from_user.id, "name_entered")
    _log_report_event(message.from_user.id, data, "name_entered")
    if data.get("report_type") == "synastry":
        await message.answer(
            "Принято. Теперь укажи свою дату рождения в формате ДД.ММ.ГГГГ, например 14.03.1990"
        )
    else:
        await message.answer(
            "Принято. Теперь укажи дату рождения в формате ДД.ММ.ГГГГ, например 14.03.1990"
        )
    await state.set_state(SolarStates.waiting_birth_date)


# ---------------------------------------------------------------------------
# Дата и время рождения
# ---------------------------------------------------------------------------


@router.message(SolarStates.waiting_birth_date)
async def process_birth_date(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    match = DATE_RE.match(text)
    if not match:
        await message.answer("Не понял дату. Пришли в формате ДД.ММ.ГГГГ, например 14.03.1990")
        return

    day, month, year = match.groups()
    try:
        datetime(int(year), int(month), int(day))
    except ValueError:
        await message.answer("Такой даты не существует. Проверь и пришли ещё раз.")
        return

    await state.update_data(birth_date=text)

    data = await state.get_data()
    if data.get("return_to_confirmation"):
        await state.update_data(return_to_confirmation=False)
        await show_confirmation(message, state)
        return

    log_event(message.from_user.id, "birth_date_entered")
    _log_report_event(message.from_user.id, data, "birth_date_entered")

    await message.answer(
        "Принято. Теперь укажи время рождения в формате ЧЧ:ММ (24-часовой формат).\n"
        "Если точное время неизвестно — напиши «не знаю»."
    )
    await state.set_state(SolarStates.waiting_birth_time)


@router.message(SolarStates.waiting_birth_time)
async def process_birth_time(message: Message, state: FSMContext):
    text = (message.text or "").strip().lower()

    if text in NO_TIME_ANSWERS:
        await state.update_data(birth_time=None, birth_time_known=False)
    else:
        match = TIME_RE.match(text)
        if not match:
            await message.answer(
                "Формат не подошёл. Пришли время как ЧЧ:ММ, например 07:45, или напиши «не знаю»."
            )
            return
        hour, minute = int(match.group(1)), int(match.group(2))
        if not (0 <= hour < 24 and 0 <= minute < 60):
            await message.answer("Похоже на опечатку во времени. Проверь и пришли ещё раз.")
            return
        await state.update_data(birth_time=text, birth_time_known=True)

    data = await state.get_data()
    if data.get("return_to_confirmation"):
        await state.update_data(return_to_confirmation=False)
        await show_confirmation(message, state)
        return

    _log_report_event(message.from_user.id, data, "birth_time_entered")

    await message.answer("Хорошо. Теперь напиши город рождения.")
    await state.set_state(SolarStates.waiting_birth_place)


# ---------------------------------------------------------------------------
# Города (с возможностью "ввести заново")
# ---------------------------------------------------------------------------


async def _offer_city_candidates(
    message: Message,
    state: FSMContext,
    query: str,
    prefix: str,
    next_state,
) -> None:
    if not query:
        await message.answer("Пришли название города текстом.")
        return

    candidates = await search_city(query)
    if not candidates:
        await message.answer(
            "Ничего не нашёл по этому названию. Попробуй написать иначе "
            "(например, добавь страну: «Краков, Польша»)."
        )
        return

    await state.update_data(**{f"{prefix}_candidates": candidates})

    buttons = [
        [InlineKeyboardButton(text=c["label"], callback_data=f"{prefix}:{i}")]
        for i, c in enumerate(candidates)
    ]
    buttons.append(
        [InlineKeyboardButton(text="🔄 Это не то, ввести заново", callback_data=f"{prefix}:retry")]
    )
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await message.answer("Уточни, какой из вариантов твой:", reply_markup=kb)
    await state.set_state(next_state)


@router.message(SolarStates.waiting_birth_place)
async def process_birth_place(message: Message, state: FSMContext):
    await _offer_city_candidates(
        message,
        state,
        (message.text or "").strip(),
        prefix="birthcity",
        next_state=SolarStates.waiting_birth_place_choice,
    )


@router.callback_query(SolarStates.waiting_birth_place_choice, F.data.startswith("birthcity:"))
async def process_birth_place_choice(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":")[1]
    await callback.answer()

    if value == "retry":
        await callback.message.edit_text("Хорошо, напиши город рождения ещё раз.")
        await state.set_state(SolarStates.waiting_birth_place)
        return

    data = await state.get_data()
    candidate = data["birthcity_candidates"][int(value)]
    await state.update_data(birth_place=candidate)
    await callback.message.edit_text(f"Место рождения: {candidate['label']}")

    data = await state.get_data()
    if data.get("return_to_confirmation"):
        await state.update_data(return_to_confirmation=False)
        await show_confirmation(callback.message, state)
        return

    _log_report_event(callback.from_user.id, data, "birth_place_entered")

    if data.get("report_type") == "synastry":
        await _ask_partner_name(callback.message, state)
    else:
        await _ask_cycle_year(callback.message, state)


# ---------------------------------------------------------------------------
# Данные партнера для синастрии
# ---------------------------------------------------------------------------


async def _ask_partner_name(answer_target, state: FSMContext) -> None:
    await answer_target.answer("Теперь данные партнёра. Как его/её зовут?")
    await state.set_state(SolarStates.waiting_partner_name)


@router.message(SolarStates.waiting_partner_name)
async def process_partner_name(message: Message, state: FSMContext):
    name = (message.text or "").strip()
    if not name:
        await message.answer("Напиши имя партнёра текстом.")
        return

    await state.update_data(partner_name=name[:50])

    data = await state.get_data()
    if data.get("return_to_confirmation"):
        await state.update_data(return_to_confirmation=False)
        await show_confirmation(message, state)
        return

    _log_report_event(message.from_user.id, data, "partner_name_entered")

    await message.answer(
        "Принято. Теперь укажи дату рождения партнёра в формате ДД.ММ.ГГГГ, например 14.03.1990"
    )
    await state.set_state(SolarStates.waiting_partner_birth_date)


@router.message(SolarStates.waiting_partner_birth_date)
async def process_partner_birth_date(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    match = DATE_RE.match(text)
    if not match:
        await message.answer("Не понял дату. Пришли в формате ДД.ММ.ГГГГ, например 14.03.1990")
        return

    day, month, year = match.groups()
    try:
        datetime(int(year), int(month), int(day))
    except ValueError:
        await message.answer("Такой даты не существует. Проверь и пришли ещё раз.")
        return

    await state.update_data(partner_birth_date=text)

    data = await state.get_data()
    if data.get("return_to_confirmation"):
        await state.update_data(return_to_confirmation=False)
        await show_confirmation(message, state)
        return

    _log_report_event(message.from_user.id, data, "partner_birth_date_entered")

    await message.answer(
        "Теперь укажи время рождения партнёра в формате ЧЧ:ММ (24-часовой формат).\n"
        "Если точное время неизвестно — напиши «не знаю»."
    )
    await state.set_state(SolarStates.waiting_partner_birth_time)


@router.message(SolarStates.waiting_partner_birth_time)
async def process_partner_birth_time(message: Message, state: FSMContext):
    text = (message.text or "").strip().lower()

    if text in NO_TIME_ANSWERS:
        await state.update_data(partner_birth_time=None, partner_birth_time_known=False)
    else:
        match = TIME_RE.match(text)
        if not match:
            await message.answer(
                "Формат не подошёл. Пришли время как ЧЧ:ММ, например 07:45, или напиши «не знаю»."
            )
            return
        hour, minute = int(match.group(1)), int(match.group(2))
        if not (0 <= hour < 24 and 0 <= minute < 60):
            await message.answer("Похоже на опечатку во времени. Проверь и пришли ещё раз.")
            return
        await state.update_data(partner_birth_time=text, partner_birth_time_known=True)

    data = await state.get_data()
    if data.get("return_to_confirmation"):
        await state.update_data(return_to_confirmation=False)
        await show_confirmation(message, state)
        return

    _log_report_event(message.from_user.id, data, "partner_birth_time_entered")

    await message.answer("Хорошо. Теперь напиши город рождения партнёра.")
    await state.set_state(SolarStates.waiting_partner_birth_place)


@router.message(SolarStates.waiting_partner_birth_place)
async def process_partner_birth_place(message: Message, state: FSMContext):
    await _offer_city_candidates(
        message,
        state,
        (message.text or "").strip(),
        prefix="partnercity",
        next_state=SolarStates.waiting_partner_birth_place_choice,
    )


@router.callback_query(
    SolarStates.waiting_partner_birth_place_choice, F.data.startswith("partnercity:")
)
async def process_partner_birth_place_choice(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":")[1]
    await callback.answer()

    if value == "retry":
        await callback.message.edit_text("Хорошо, напиши город рождения партнёра ещё раз.")
        await state.set_state(SolarStates.waiting_partner_birth_place)
        return

    data = await state.get_data()
    candidate = data["partnercity_candidates"][int(value)]
    await state.update_data(partner_birth_place=candidate)
    await callback.message.edit_text(f"Место рождения партнёра: {candidate['label']}")

    data = await state.get_data()
    if data.get("return_to_confirmation"):
        await state.update_data(return_to_confirmation=False)
        await show_confirmation(callback.message, state)
        return

    _log_report_event(callback.from_user.id, data, "partner_birth_place_entered")

    await show_confirmation(callback.message, state)


@router.message(SolarStates.waiting_solar_place)
async def process_solar_place(message: Message, state: FSMContext):
    await _offer_city_candidates(
        message,
        state,
        (message.text or "").strip(),
        prefix="solarcity",
        next_state=SolarStates.waiting_solar_place_choice,
    )


@router.callback_query(SolarStates.waiting_solar_place_choice, F.data.startswith("solarcity:"))
async def process_solar_place_choice(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":")[1]
    await callback.answer()

    if value == "retry":
        await callback.message.edit_text("Хорошо, напиши город соляра ещё раз.")
        await state.set_state(SolarStates.waiting_solar_place)
        return

    data = await state.get_data()
    candidate = data["solarcity_candidates"][int(value)]
    await state.update_data(solar_place=candidate)
    await callback.message.edit_text(f"Место соляра: {candidate['label']}")

    data = await state.get_data()
    if data.get("return_to_confirmation"):
        await state.update_data(return_to_confirmation=False)
        await show_confirmation(callback.message, state)
        return

    log_event(callback.from_user.id, "city_entered")
    _log_report_event(callback.from_user.id, data, "place_entered")

    await _ask_context(callback.message, state)


# ---------------------------------------------------------------------------
# Год расчёта соляра
# ---------------------------------------------------------------------------


async def _ask_cycle_year(answer_target, state: FSMContext) -> None:
    data = await state.get_data()
    day, month, _ = (int(x) for x in data["birth_date"].split("."))
    default_year = compute_solar_cycle_year(day, month)

    buttons = [
        [
            InlineKeyboardButton(
                text=f"{default_year - 1} → {default_year}",
                callback_data=f"cycleyear:{default_year - 1}",
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{default_year} → {default_year + 1} (текущий)",
                callback_data=f"cycleyear:{default_year}",
            )
        ],
        [
            InlineKeyboardButton(
                text=f"{default_year + 1} → {default_year + 2}",
                callback_data=f"cycleyear:{default_year + 1}",
            )
        ],
        [InlineKeyboardButton(text="Другой год", callback_data="cycleyear:custom")],
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await answer_target.answer("На какой годовой цикл считаем соляр?", reply_markup=kb)
    await state.set_state(SolarStates.waiting_cycle_year)


@router.callback_query(SolarStates.waiting_cycle_year, F.data.startswith("cycleyear:"))
async def process_cycle_year(callback: CallbackQuery, state: FSMContext):
    value = callback.data.split(":")[1]
    await callback.answer()

    if value == "custom":
        await callback.message.edit_text("Напиши год начала цикла (например 2025):")
        await state.set_state(SolarStates.waiting_cycle_year_custom)
        return

    year = int(value)
    await state.update_data(solar_cycle_year=year)
    data = await state.get_data()
    _log_report_event(callback.from_user.id, data, "cycle_year_entered")
    await callback.message.edit_text(f"Год расчёта: {year} → {year + 1}")
    await _after_cycle_year(callback.message, state)


@router.message(SolarStates.waiting_cycle_year_custom)
async def process_cycle_year_custom(message: Message, state: FSMContext):
    text = (message.text or "").strip()
    if not YEAR_RE.match(text):
        await message.answer("Пришли год четырьмя цифрами, например 2025.")
        return

    year = int(text)
    await state.update_data(solar_cycle_year=year)
    data = await state.get_data()
    _log_report_event(message.from_user.id, data, "cycle_year_entered")
    await message.answer(f"Год расчёта: {year} → {year + 1}")
    await _after_cycle_year(message, state)


async def _after_cycle_year(answer_target, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("return_to_confirmation"):
        await state.update_data(return_to_confirmation=False)
        await show_confirmation(answer_target, state)
        return
    await _ask_solar_place(answer_target, state)


async def _ask_solar_place(answer_target, state: FSMContext) -> None:
    """Формулировка зависит от того, выбран прошлый/текущий или будущий цикл соляра."""
    data = await state.get_data()
    day, month, _ = (int(x) for x in data["birth_date"].split("."))
    default_year = compute_solar_cycle_year(day, month)
    cycle_year = data["solar_cycle_year"]

    if cycle_year <= default_year:
        prompt_text = (
            "Теперь напиши город, где ты праздновал(а) (или встречал(а)) "
            "этот день рождения."
        )
    else:
        prompt_text = "Теперь напиши город, где будешь праздновать этот день рождения."

    await answer_target.answer(prompt_text)
    await state.set_state(SolarStates.waiting_solar_place)


# ---------------------------------------------------------------------------
# Необязательный контекст за прошлый год
# ---------------------------------------------------------------------------


async def _ask_context(answer_target, state: FSMContext) -> None:
    kb = InlineKeyboardMarkup(
        inline_keyboard=[[InlineKeyboardButton(text="Пропустить", callback_data="context:skip")]]
    )
    await answer_target.answer(
        "Расскажи немного о годе, который заканчивается (или уже закончился): что происходило, "
        "какие были события, желания, планы. Это необязательно, но поможет точнее интерпретировать "
        "соляр.\nЕсли не хочешь — жми «Пропустить».",
        reply_markup=kb,
    )
    await state.set_state(SolarStates.waiting_context)


@router.callback_query(SolarStates.waiting_context, F.data == "context:skip")
async def process_context_skip(callback: CallbackQuery, state: FSMContext):
    await state.update_data(user_context=None)
    data = await state.get_data()
    _log_report_event(callback.from_user.id, data, "context_done")
    await callback.message.edit_text("Хорошо, без контекста.")
    await callback.answer()
    await show_confirmation(callback.message, state)


@router.message(SolarStates.waiting_context)
async def process_context_text(message: Message, state: FSMContext):
    await state.update_data(user_context=(message.text or "").strip())
    data = await state.get_data()
    _log_report_event(message.from_user.id, data, "context_done")
    await message.answer("Записала контекст.")
    await show_confirmation(message, state)


# ---------------------------------------------------------------------------
# Подтверждение и редактирование перед расчётом
# ---------------------------------------------------------------------------


async def show_confirmation(answer_target, state: FSMContext) -> None:
    data = await state.get_data()
    if data.get("report_type") == "synastry":
        await show_synastry_confirmation(answer_target, state)
        return
    _log_report_event(answer_target.chat.id, data, "confirmation_shown")

    birth_time = data.get("birth_time") or "неизвестно"
    cycle_year = data["solar_cycle_year"]
    user_context = data.get("user_context")
    context_line = f"\nКонтекст: {user_context}" if user_context else "\nКонтекст: (не указан)"

    text = (
        "Проверь данные перед расчётом:\n\n"
        f"Имя: {data.get('person_name', '')}\n"
        f"Дата рождения: {data['birth_date']}\n"
        f"Время рождения: {birth_time}\n"
        f"Место рождения: {data['birth_place']['label']}\n"
        f"Место соляра: {data['solar_place']['label']}\n"
        f"Год расчёта: {cycle_year} → {cycle_year + 1}"
        f"{context_line}"
    )

    buttons = [
        [InlineKeyboardButton(text="✅ Всё верно, считать!", callback_data="confirm:go")],
        [InlineKeyboardButton(text="✏️ Поправить данные", callback_data="confirm:edit")],
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await answer_target.answer(text, reply_markup=kb)
    await state.set_state(SolarStates.confirmation)


async def show_synastry_confirmation(answer_target, state: FSMContext) -> None:
    data = await state.get_data()
    _log_report_event(answer_target.chat.id, data, "confirmation_shown")
    birth_time = data.get("birth_time") or "неизвестно"
    partner_birth_time = data.get("partner_birth_time") or "неизвестно"

    text = (
        "Проверь данные перед расчётом синастрии:\n\n"
        f"Ты: {data.get('person_name', '')}\n"
        f"Дата рождения: {data['birth_date']}\n"
        f"Время рождения: {birth_time}\n"
        f"Место рождения: {data['birth_place']['label']}\n\n"
        f"Партнёр: {data.get('partner_name', '')}\n"
        f"Дата рождения партнёра: {data['partner_birth_date']}\n"
        f"Время рождения партнёра: {partner_birth_time}\n"
        f"Место рождения партнёра: {data['partner_birth_place']['label']}"
    )

    buttons = [
        [InlineKeyboardButton(text="✅ Всё верно, считать!", callback_data="confirm:go")],
        [InlineKeyboardButton(text="✏️ Поправить данные", callback_data="confirm:edit")],
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await answer_target.answer(text, reply_markup=kb)
    await state.set_state(SolarStates.confirmation)


@router.callback_query(SolarStates.confirmation, F.data == "confirm:edit")
async def process_confirm_edit(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    if data.get("report_type") == "synastry":
        await show_synastry_edit_options(callback.message)
    else:
        await show_solar_edit_options(callback.message)


@router.callback_query(SolarStates.confirmation, F.data == "confirm:back")
async def process_confirm_back(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.delete()
    await show_confirmation(callback.message, state)


async def show_solar_edit_options(message: Message) -> None:
    buttons = [
        [InlineKeyboardButton(text="✏️ Имя", callback_data="edit:name")],
        [InlineKeyboardButton(text="✏️ Дата рождения", callback_data="edit:birth_date")],
        [InlineKeyboardButton(text="✏️ Время рождения", callback_data="edit:birth_time")],
        [InlineKeyboardButton(text="✏️ Место рождения", callback_data="edit:birth_place")],
        [InlineKeyboardButton(text="✏️ Место соляра", callback_data="edit:solar_place")],
        [InlineKeyboardButton(text="✏️ Год расчёта", callback_data="edit:year")],
        [InlineKeyboardButton(text="✏️ Контекст года", callback_data="edit:context")],
        [InlineKeyboardButton(text="⬅️ Назад к проверке", callback_data="confirm:back")],
    ]
    await message.edit_text(
        "Что поправить в данных для соляра?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


async def show_synastry_edit_options(message: Message) -> None:
    buttons = [
        [InlineKeyboardButton(text="✏️ Твоё имя", callback_data="edit:name")],
        [InlineKeyboardButton(text="✏️ Твоя дата рождения", callback_data="edit:birth_date")],
        [InlineKeyboardButton(text="✏️ Твоё время рождения", callback_data="edit:birth_time")],
        [InlineKeyboardButton(text="✏️ Твоё место рождения", callback_data="edit:birth_place")],
        [InlineKeyboardButton(text="✏️ Имя партнёра", callback_data="edit:partner_name")],
        [InlineKeyboardButton(text="✏️ Дата рождения партнёра", callback_data="edit:partner_birth_date")],
        [InlineKeyboardButton(text="✏️ Время рождения партнёра", callback_data="edit:partner_birth_time")],
        [InlineKeyboardButton(text="✏️ Место рождения партнёра", callback_data="edit:partner_birth_place")],
        [InlineKeyboardButton(text="⬅️ Назад к проверке", callback_data="confirm:back")],
    ]
    await message.edit_text(
        "Что поправить в данных для синастрии?",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons),
    )


@router.callback_query(SolarStates.confirmation, F.data.startswith("edit:"))
async def process_edit_choice(callback: CallbackQuery, state: FSMContext):
    target = callback.data.split(":")[1]
    await callback.answer()
    await state.update_data(return_to_confirmation=True)

    if target == "name":
        await callback.message.edit_text("Напиши новое имя:")
        await state.set_state(SolarStates.waiting_name)
    elif target == "birth_date":
        await callback.message.edit_text("Пришли новую дату рождения в формате ДД.ММ.ГГГГ:")
        await state.set_state(SolarStates.waiting_birth_date)
    elif target == "birth_time":
        await callback.message.edit_text(
            "Пришли новое время рождения в формате ЧЧ:ММ (или «не знаю»):"
        )
        await state.set_state(SolarStates.waiting_birth_time)
    elif target == "birth_place":
        await callback.message.edit_text("Напиши город рождения заново:")
        await state.set_state(SolarStates.waiting_birth_place)
    elif target == "solar_place":
        await callback.message.edit_text("Хорошо, обновим место соляра.")
        await _ask_solar_place(callback.message, state)
    elif target == "year":
        await _ask_cycle_year(callback.message, state)
    elif target == "context":
        await _ask_context(callback.message, state)
    elif target == "partner_name":
        await callback.message.edit_text("Напиши новое имя партнёра:")
        await state.set_state(SolarStates.waiting_partner_name)
    elif target == "partner_birth_date":
        await callback.message.edit_text(
            "Пришли новую дату рождения партнёра в формате ДД.ММ.ГГГГ:"
        )
        await state.set_state(SolarStates.waiting_partner_birth_date)
    elif target == "partner_birth_time":
        await callback.message.edit_text(
            "Пришли новое время рождения партнёра в формате ЧЧ:ММ (или «не знаю»):"
        )
        await state.set_state(SolarStates.waiting_partner_birth_time)
    elif target == "partner_birth_place":
        await callback.message.edit_text("Напиши город рождения партнёра заново:")
        await state.set_state(SolarStates.waiting_partner_birth_place)


@router.callback_query(SolarStates.confirmation, F.data == "confirm:go")
async def process_confirm_go(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    data = await state.get_data()
    report_type = data.get("report_type", "solar")

    if not PAYMENTS_ENABLED:
        await state.update_data(payment_confirmed=False)
        await callback.message.edit_text("Запускаю расчёт...")
        if report_type == "synastry":
            await _run_synastry_analysis(callback.message, callback.from_user, state)
        else:
            await _run_solar_analysis(callback.message, callback.from_user, state)
        return

    log_event(callback.from_user.id, "payment_started")
    log_event(callback.from_user.id, f"{report_type}_payment_started")
    try:
        pre_payment_pitch = _build_pre_payment_pitch(data, report_type)
    except Exception as e:
        await callback.message.answer(f"Не удалось подготовить описание разбора: {e}")
        return

    try:
        await callback.message.delete()
    except Exception:
        try:
            await callback.message.edit_text("Данные приняты. Показываю пример готового отчёта...")
        except Exception:
            pass
    await asyncio.sleep(0.5)

    await _send_pre_payment_preview(callback.message, report_type, pre_payment_pitch)

    if report_type == "synastry":
        title = "Синастрия / совместимость"
        description = f"Разбор совместимости по двум натальным картам — {SYNASTRY_STARS_PRICE} ⭐"
        payload = "synastry_analysis"
        prices = [LabeledPrice(label="Синастрия", amount=SYNASTRY_STARS_PRICE)]
        pay_button_text = f"Рассчитать синастрию — {SYNASTRY_STARS_PRICE} ⭐"
    else:
        title = "Разбор соляра на год"
        description = f"Полный астрологический разбор соляра — {SOLAR_STARS_PRICE} ⭐"
        payload = "solar_chart_analysis"
        prices = [LabeledPrice(label="Разбор соляра", amount=SOLAR_STARS_PRICE)]
        pay_button_text = f"Рассчитать мой соляр — {SOLAR_STARS_PRICE} ⭐"

    await callback.message.answer_invoice(
        title=title,
        description=description,
        payload=payload,
        currency="XTR",
        prices=prices,
        provider_token="",
        reply_markup=InlineKeyboardMarkup(
            inline_keyboard=[[InlineKeyboardButton(text=pay_button_text, pay=True)]]
        ),
    )
    log_event(callback.from_user.id, "payment_invoice_sent")
    log_event(callback.from_user.id, f"{report_type}_payment_invoice_sent")


def _build_pre_payment_pitch(data: dict, report_type: str) -> str:
    if report_type == "synastry":
        return _build_synastry_pre_payment_pitch(data)
    return _build_solar_pre_payment_pitch(data)


def _format_russian_date(value: date) -> str:
    return f"{value.day} {MONTH_NAMES[value.month]} {value.year}"


def _solar_period_text(data: dict) -> str:
    day, month, _ = (int(x) for x in data["birth_date"].split("."))
    cycle_year = int(data["solar_cycle_year"])
    try:
        start = date(cycle_year, month, day)
    except ValueError:
        start = date(cycle_year, 2, 28)
    try:
        end = date(cycle_year + 1, month, day)
    except ValueError:
        end = date(cycle_year + 1, 2, 28)
    return f"от {_format_russian_date(start)} до {_format_russian_date(end)}"


async def _send_pre_payment_preview(message: Message, report_type: str, caption: str) -> None:
    previews = [
        (path, preview_caption)
        for path, preview_caption in PREVIEW_PATHS.get(report_type, [])
        if os.path.exists(path)
    ]
    if not previews:
        await message.answer(caption)
        return
    media = [
        InputMediaPhoto(media=FSInputFile(path), caption=caption if index == 0 else None)
        for index, (path, _) in enumerate(previews[:10])
    ]
    try:
        await message.answer_media_group(media)
    except Exception:
        await message.answer(caption)
        for path, _ in previews:
            try:
                await message.answer_photo(FSInputFile(path))
            except Exception:
                continue


def _build_solar_pre_payment_pitch(data: dict) -> str:
    period = _solar_period_text(data)

    return (
        "Данные приняты.\n\n"
        f"По ним можно построить персональный соляр на период {period}: "
        "PDF-прогноз по сферам жизни, а не общий гороскоп по знаку.\n\n"
        "Внутри: карта года с баллами, главная тема периода, разбор ключевых сфер "
        "(карьера, деньги, отношения, дом, здоровье, внутреннее состояние), риски, "
        "возможности и практический план.\n\n"
        "На скринах — пример готового PDF. В твоём отчёте значения и трактовки будут "
        "рассчитаны индивидуально.\n\n"
        f"Полный разбор — {SOLAR_STARS_PRICE} ⭐."
    )


def _build_synastry_pre_payment_pitch(data: dict) -> str:
    first_name = data.get("person_name") or "ты"
    partner_name = data.get("partner_name") or "партнёр"

    return (
        "Данные приняты.\n\n"
        f"По ним можно построить синастрию пары {first_name} + {partner_name}: "
        "PDF-разбор совместимости по двум натальным картам.\n\n"
        "Внутри: общая динамика пары, эмоциональная связь, химия, коммуникация, быт, "
        "долгосрочность, зоны напряжения и практические рекомендации.\n\n"
        "На скринах — пример готового PDF. В твоём отчёте значения и трактовки будут "
        "рассчитаны индивидуально.\n\n"
        f"Полный разбор — {SYNASTRY_STARS_PRICE} ⭐."
    )


@router.pre_checkout_query()
async def process_pre_checkout(query: PreCheckoutQuery):
    await query.answer(ok=True)


@router.message(F.successful_payment)
async def process_successful_payment(message: Message, state: FSMContext):
    log_event(message.from_user.id, "payment_success")
    data = await state.get_data()
    report_type = data.get("report_type", "solar")
    log_event(message.from_user.id, f"{report_type}_payment_success")
    await state.update_data(payment_confirmed=True)
    if report_type == "synastry":
        await message.answer("Оплата получена ⭐ Готовлю полную расшифровку синастрии...")
        await _run_synastry_analysis(message, message.from_user, state)
    else:
        await message.answer("Оплата получена ⭐ Готовлю полную расшифровку соляра...")
        await _run_solar_analysis(message, message.from_user, state)


@router.message(Command("paysupport"))
async def cmd_paysupport(message: Message):
    await message.answer(
        "Если оплата прошла, а разбор не пришёл — напиши мне здесь, что произошло, "
        "и я разберусь и верну звёзды, если нужно."
    )


@router.message(Command("stats", "stat"))
async def cmd_stats(message: Message):
    """Видна только владельцу бота (ADMIN_USER_ID в .env) — показывает воронку и источники."""
    if not _is_admin(message.from_user.id if message.from_user else None):
        return

    summary = funnel_summary()
    selected_events = ("solar_selected", "synastry_selected")
    sources = list_sources_for_any_event(selected_events)

    def count(event: str) -> int:
        return summary.get(event, 0)

    def count_step(event: str | tuple[str, ...]) -> int:
        if isinstance(event, tuple):
            return max(summary.get(item, 0) for item in event)
        return count(event)

    def paid_generated(report_type: str) -> int:
        return count_users_with_events(
            (f"{report_type}_payment_success", f"{report_type}_generated")
        )

    def pct(part: int, total: int) -> str:
        if total <= 0:
            return "—"
        return f"{part / total * 100:.0f}%"

    def funnel_block(title: str, steps: list[tuple[str, str | tuple[str, ...]]]) -> list[str]:
        lines = [f"\n{title}:"]
        previous_value: Optional[int] = None
        for label, event in steps:
            value = count_step(event)
            if previous_value is None:
                lines.append(f"{label}: {value}")
            else:
                lines.append(f"{label}: {value} ({pct(value, previous_value)} от прошлого шага)")
            previous_value = value
        return lines

    solar_steps = [
        ("выбрали соляр", "solar_selected"),
        ("ввели имя", "solar_name_entered"),
        ("ввели дату рождения", "solar_birth_date_entered"),
        ("ввели время рождения", "solar_birth_time_entered"),
        ("выбрали город рождения", "solar_birth_place_entered"),
        ("выбрали год соляра", "solar_cycle_year_entered"),
        ("выбрали место соляра", "solar_place_entered"),
        ("добавили/пропустили контекст", "solar_context_done"),
        ("увидели подтверждение", "solar_confirmation_shown"),
        ("нажали «Всё верно»", "solar_payment_started"),
        ("увидели кнопку оплаты", ("solar_payment_invoice_sent", "solar_payment_started")),
        ("успешно оплатили", "solar_payment_success"),
    ]
    synastry_steps = [
        ("выбрали синастрию", "synastry_selected"),
        ("ввели своё имя", "synastry_name_entered"),
        ("ввели свою дату рождения", "synastry_birth_date_entered"),
        ("ввели своё время рождения", "synastry_birth_time_entered"),
        ("выбрали свой город рождения", "synastry_birth_place_entered"),
        ("ввели имя партнёра", "synastry_partner_name_entered"),
        ("ввели дату рождения партнёра", "synastry_partner_birth_date_entered"),
        ("ввели время рождения партнёра", "synastry_partner_birth_time_entered"),
        ("выбрали город рождения партнёра", "synastry_partner_birth_place_entered"),
        ("увидели подтверждение", "synastry_confirmation_shown"),
        ("нажали «Всё верно»", "synastry_payment_started"),
        ("увидели кнопку оплаты", ("synastry_payment_invoice_sent", "synastry_payment_started")),
        ("успешно оплатили", "synastry_payment_success"),
    ]

    lines = ["📊 Воронка (уникальные пользователи):"]
    lines.append(f"\nОбщий старт: {count('start')}")
    selected_total = count_users_with_any_event(selected_events)
    lines.append(f"Выбрали тип разбора: {selected_total} ({pct(selected_total, count('start'))} от старта)")
    lines.append(f"Не выбрали тип разбора: {max(count('start') - selected_total, 0)}")
    lines.extend(funnel_block("🌞 Соляр", solar_steps))
    lines.extend(funnel_block("💞 Синастрия", synastry_steps))

    solar_generated = count("solar_generated")
    solar_paid_generated = max(
        count("solar_generated_after_payment"),
        paid_generated("solar"),
    )
    synastry_generated = count("synastry_generated")
    synastry_paid_generated = max(
        count("synastry_generated_after_payment"),
        paid_generated("synastry"),
    )
    lines.append("\n📄 Файлы / выдачи:")
    lines.append(
        f"соляр — всего файлов: {solar_generated}; после оплаты: {solar_paid_generated}; "
        f"бесплатно/тест/старый режим: {max(solar_generated - solar_paid_generated, 0)}"
    )
    lines.append(
        f"синастрия — всего файлов: {synastry_generated}; после оплаты: {synastry_paid_generated}; "
        f"бесплатно/тест/старый режим: {max(synastry_generated - synastry_paid_generated, 0)}"
    )

    lines.append("\n📍 Источники среди выбравших разбор (?start=...):")
    if sources:
        for src, cnt in sources:
            lines.append(f"{src}: {cnt}")
    else:
        lines.append("(пока нет данных)")

    await message.answer("\n".join(lines))


# ---------------------------------------------------------------------------
# Сам расчёт + потоковая генерация разбора + pdf-файл
# ---------------------------------------------------------------------------


async def _run_solar_analysis(answer_target, from_user: User, state: FSMContext) -> None:
    data = await state.get_data()
    birth_place = data["birth_place"]
    solar_place = data["solar_place"]
    cycle_year = data["solar_cycle_year"]
    user_context: Optional[str] = data.get("user_context")

    day, month, year = (int(x) for x in data["birth_date"].split("."))

    birth_time = data.get("birth_time")
    if birth_time:
        hour, minute = (int(x) for x in birth_time.split(":"))
        time_note = ""
    else:
        hour, minute = 12, 0
        time_note = (
            "\n\n(Точное время рождения неизвестно — считаю на условный полдень, "
            "положения домов могут быть не совсем точны.)"
        )

    progress_msg = await answer_target.answer(
        "⏳ Карта соляра уже построена. Готовлю полную расшифровку — это может занять пару минут..."
        + time_note
    )

    birth_tz = get_timezone(birth_place["lat"], birth_place["lon"])
    solar_tz = get_timezone(solar_place["lat"], solar_place["lon"])

    try:
        chart_data = compute_solar_return(
            birth_year=year,
            birth_month=month,
            birth_day=day,
            birth_hour=hour,
            birth_minute=minute,
            birth_tz=birth_tz,
            birth_lat=birth_place["lat"],
            birth_lon=birth_place["lon"],
            birth_place_label=birth_place["label"],
            solar_lat=solar_place["lat"],
            solar_lon=solar_place["lon"],
            solar_place_label=solar_place["label"],
            solar_tz=solar_tz,
            solar_cycle_year=cycle_year,
        )
    except Exception as e:
        await progress_msg.edit_text(f"Не удалось рассчитать соляр: {e}")
        await state.clear()
        return

    prompt = build_solar_json_prompt(
        chart_data,
        person_name=data.get("person_name", ""),
        user_context=user_context,
    )

    report_json = None
    try:
        buffer, stop_reason = await interpret_solar_chart(prompt)
    except Exception as e:
        await progress_msg.edit_text(f"Клод не ответил: {e}")
        await state.clear()
        return

    try:
        report_json = normalize_solar_report(parse_report_json(buffer))
    except Exception:
        # Аварийный путь: если Claude вернул невалидный JSON, не ломаем выдачу
        # пользователю, а собираем старый текстовый PDF.
        fallback_prompt = build_solar_prompt(
            chart_data,
            person_name=data.get("person_name", ""),
            user_context=user_context,
        )
        try:
            await progress_msg.edit_text(
                "✍️ Собираю текстовую версию разбора, визуальный шаблон не принял данные..."
                + time_note
            )
        except Exception:
            pass
        try:
            buffer, stop_reason = await interpret_solar_chart(fallback_prompt)
        except Exception as e:
            await progress_msg.edit_text(f"Не удалось собрать отчёт: {e}")
            await state.clear()
            return

    cut_off_note = (
        "\n\n⚠️ Ответ получился длиннее лимита и мог быть обрезан."
        if stop_reason == "max_tokens"
        else ""
    )

    if report_json:
        teaser = structured_report_to_teaser(report_json)
    else:
        teaser = extract_main_theme(buffer)
        if not teaser.strip():
            teaser = "Разбор готов — основной текст смотри в приложенном файле ниже."
    teaser += cut_off_note
    try:
        await progress_msg.edit_text(teaser)
    except Exception:
        await answer_target.answer(teaser)

    file_status = await answer_target.answer("📄 Формирую PDF-файл с полной расшифровкой...")

    output_path = f"/tmp/solar_{from_user.id}_{int(time.time())}.pdf"
    title = f"Соляр {data.get('person_name', '')}".strip()
    if report_json:
        await structured_solar_to_pdf(report_json, output_path)
    else:
        visual_profile = build_solar_profile(
            chart_data,
            person_name=data.get("person_name", ""),
            cycle_year=cycle_year,
        )
        await markdown_to_pdf(title, buffer, output_path, visual_profile=visual_profile)

    name_part = re.sub(r'[\\/:*?"<>|]', "", data.get("person_name", "")).strip()
    display_name = f"{name_part} {data['birth_date']} {cycle_year}-{cycle_year + 1}".strip()
    display_name = re.sub(r"\s+", " ", display_name)
    display_filename = f"{display_name}.pdf"

    _log_generated_event(from_user.id, data, "solar")

    try:
        await answer_target.answer_document(FSInputFile(output_path, filename=display_filename))
        await file_status.delete()
    except Exception:
        await file_status.edit_text("Готово ✅ (файл выше)")
    finally:
        if os.path.exists(output_path):
            os.remove(output_path)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="🔄 Рассчитать другой соляр", callback_data="restart:solar")],
            [InlineKeyboardButton(text="💞 Рассчитать синастрию", callback_data="restart:synastry")],
        ]
    )
    await answer_target.answer("Готово! Если нужен ещё один разбор:", reply_markup=kb)

    await state.clear()


async def _run_synastry_analysis(answer_target, from_user: User, state: FSMContext) -> None:
    data = await state.get_data()
    birth_place = data["birth_place"]
    partner_birth_place = data["partner_birth_place"]

    day, month, year = (int(x) for x in data["birth_date"].split("."))
    p_day, p_month, p_year = (int(x) for x in data["partner_birth_date"].split("."))

    birth_time = data.get("birth_time")
    if birth_time:
        hour, minute = (int(x) for x in birth_time.split(":"))
        first_time_note = ""
    else:
        hour, minute = 12, 0
        first_time_note = "\n\n(Твоё точное время рождения неизвестно — считаю на условный полдень.)"

    partner_birth_time = data.get("partner_birth_time")
    if partner_birth_time:
        p_hour, p_minute = (int(x) for x in partner_birth_time.split(":"))
        partner_time_note = ""
    else:
        p_hour, p_minute = 12, 0
        partner_time_note = (
            "\n\n(Точное время рождения партнёра неизвестно — считаю на условный полдень.)"
        )

    progress_msg = await answer_target.answer(
        "⏳ Синастрия уже построена. Готовлю полную расшифровку — это может занять пару минут..."
        + first_time_note
        + partner_time_note
    )

    birth_tz = get_timezone(birth_place["lat"], birth_place["lon"])
    partner_tz = get_timezone(partner_birth_place["lat"], partner_birth_place["lon"])

    try:
        chart_data = compute_synastry(
            first_name=data.get("person_name", ""),
            first_year=year,
            first_month=month,
            first_day=day,
            first_hour=hour,
            first_minute=minute,
            first_tz=birth_tz,
            first_lat=birth_place["lat"],
            first_lon=birth_place["lon"],
            first_place_label=birth_place["label"],
            partner_name=data.get("partner_name", ""),
            partner_year=p_year,
            partner_month=p_month,
            partner_day=p_day,
            partner_hour=p_hour,
            partner_minute=p_minute,
            partner_tz=partner_tz,
            partner_lat=partner_birth_place["lat"],
            partner_lon=partner_birth_place["lon"],
            partner_place_label=partner_birth_place["label"],
        )
    except Exception as e:
        await progress_msg.edit_text(f"Не удалось рассчитать синастрию: {e}")
        await state.clear()
        return

    first_name = data.get("person_name", "")
    partner_name = data.get("partner_name", "")
    prompt = build_synastry_json_prompt(chart_data, first_name=first_name, partner_name=partner_name)

    report_json = None
    try:
        buffer, stop_reason = await interpret_solar_chart(prompt)
    except Exception as e:
        await progress_msg.edit_text(f"Клод не ответил: {e}")
        await state.clear()
        return

    try:
        report_json = normalize_synastry_report(
            parse_report_json(buffer),
            first_name=first_name,
            partner_name=partner_name,
        )
    except Exception:
        fallback_prompt = build_synastry_prompt(
            chart_data,
            first_name=first_name,
            partner_name=partner_name,
        )
        try:
            await progress_msg.edit_text(
                "✍️ Собираю текстовую версию синастрии, визуальный шаблон не принял данные..."
            )
        except Exception:
            pass
        try:
            buffer, stop_reason = await interpret_solar_chart(fallback_prompt)
        except Exception as e:
            await progress_msg.edit_text(f"Не удалось собрать отчёт: {e}")
            await state.clear()
            return

    cut_off_note = (
        "\n\n⚠️ Ответ получился длиннее лимита и мог быть обрезан."
        if stop_reason == "max_tokens"
        else ""
    )

    if report_json:
        teaser = structured_report_to_teaser(
            {
                "main_theme": {
                    "title": (report_json.get("formula") or {}).get("phrase", ""),
                    "text": (report_json.get("formula") or {}).get("text", ""),
                },
                "final_formula": (report_json.get("final") or {}).get("text", ""),
            }
        )
    else:
        teaser = extract_main_theme(buffer)
        if not teaser.strip():
            teaser = "Разбор совместимости готов — основной текст смотри в приложенном файле ниже."
    teaser += cut_off_note
    try:
        await progress_msg.edit_text(teaser)
    except Exception:
        await answer_target.answer(teaser)

    file_status = await answer_target.answer("📄 Формирую PDF-файл с полной расшифровкой...")

    output_path = f"/tmp/synastry_{from_user.id}_{int(time.time())}.pdf"
    title = f"Синастрия {first_name} и {partner_name}".strip()
    if report_json:
        await structured_synastry_to_pdf(report_json, output_path)
    else:
        visual_profile = build_synastry_profile(
            chart_data,
            first_name=first_name,
            partner_name=partner_name,
        )
        await markdown_to_pdf(title, buffer, output_path, visual_profile=visual_profile)

    safe_first = re.sub(r'[\\/:*?"<>|]', "", first_name).strip()
    safe_partner = re.sub(r'[\\/:*?"<>|]', "", partner_name).strip()
    display_name = f"Синастрия {safe_first} и {safe_partner}".strip()
    display_name = re.sub(r"\s+", " ", display_name)
    display_filename = f"{display_name}.pdf"

    _log_generated_event(from_user.id, data, "synastry")

    try:
        await answer_target.answer_document(FSInputFile(output_path, filename=display_filename))
        await file_status.delete()
    except Exception:
        await file_status.edit_text("Готово ✅ (файл выше)")
    finally:
        if os.path.exists(output_path):
            os.remove(output_path)

    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💞 Рассчитать ещё одну синастрию", callback_data="restart:synastry")],
            [InlineKeyboardButton(text="🌞 Рассчитать соляр", callback_data="restart:solar")],
        ]
    )
    await answer_target.answer("Готово! Если нужен ещё один разбор:", reply_markup=kb)

    await state.clear()


@router.callback_query(F.data == "restart:new")
async def process_restart(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await start_flow(callback.message, state)


@router.callback_query(F.data.startswith("restart:"))
async def process_restart_report_type(callback: CallbackQuery, state: FSMContext):
    report_type = callback.data.split(":", 1)[1]
    if report_type == "new":
        await process_restart(callback, state)
        return
    await callback.answer()
    await state.clear()
    await _begin_report_type(callback.message, state, callback.from_user.id, report_type)
