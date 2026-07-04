import asyncio
import os
import re
import time
from datetime import datetime
from typing import Optional

from aiogram import F, Router
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    LabeledPrice,
    Message,
    PreCheckoutQuery,
    User,
)

from handlers.start import start_flow
from services.analytics import funnel_summary, list_sources, log_event
from services.claude_client import interpret_solar_chart
from services.geocoding import search_city
from services.prompt_builder import (
    build_review_prompt,
    build_solar_prompt,
    build_synastry_prompt,
    build_synastry_review_prompt,
)
from services.report_file import extract_main_theme
from services.report_pdf import markdown_to_pdf
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
SYNASTRY_STARS_PRICE = int(os.getenv("SYNASTRY_STARS_PRICE", "300"))
PAYMENTS_ENABLED = os.getenv("PAYMENTS_ENABLED", "true").strip().lower() == "true"


# ---------------------------------------------------------------------------
# Выбор типа разбора
# ---------------------------------------------------------------------------


@router.callback_query(SolarStates.choosing_report_type, F.data.startswith("report:"))
async def process_report_type(callback: CallbackQuery, state: FSMContext):
    report_type = callback.data.split(":")[1]
    await callback.answer()

    if report_type not in {"solar", "synastry"}:
        await callback.message.answer("Не поняла тип расчёта. Нажми /start и выбери ещё раз.")
        return

    log_event(callback.from_user.id, f"{report_type}_selected")
    await state.update_data(report_type=report_type)
    if report_type == "synastry":
        await callback.message.edit_text(
            "Считаем синастрию / совместимость 💞\n\n"
            "Сначала соберём твои данные. Как тебя зовут?"
        )
    else:
        await callback.message.edit_text(
            "Считаем соляр 🌞\n\n"
            "Как зовут человека, для которого считаем?"
        )
    await state.set_state(SolarStates.waiting_name)


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

    log_event(message.from_user.id, "name_entered")

    data = await state.get_data()
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
    await callback.message.edit_text("Хорошо, без контекста.")
    await callback.answer()
    await show_confirmation(callback.message, state)


@router.message(SolarStates.waiting_context)
async def process_context_text(message: Message, state: FSMContext):
    await state.update_data(user_context=(message.text or "").strip())
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
        [InlineKeyboardButton(text="✏️ Имя", callback_data="edit:name")],
        [InlineKeyboardButton(text="✏️ Дата рождения", callback_data="edit:birth_date")],
        [InlineKeyboardButton(text="✏️ Время рождения", callback_data="edit:birth_time")],
        [InlineKeyboardButton(text="✏️ Место рождения", callback_data="edit:birth_place")],
        [InlineKeyboardButton(text="✏️ Место соляра", callback_data="edit:solar_place")],
        [InlineKeyboardButton(text="✏️ Год расчёта", callback_data="edit:year")],
        [InlineKeyboardButton(text="✏️ Контекст года", callback_data="edit:context")],
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await answer_target.answer(text, reply_markup=kb)
    await state.set_state(SolarStates.confirmation)


async def show_synastry_confirmation(answer_target, state: FSMContext) -> None:
    data = await state.get_data()
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
        [InlineKeyboardButton(text="✏️ Твоё имя", callback_data="edit:name")],
        [InlineKeyboardButton(text="✏️ Твоя дата рождения", callback_data="edit:birth_date")],
        [InlineKeyboardButton(text="✏️ Твоё время рождения", callback_data="edit:birth_time")],
        [InlineKeyboardButton(text="✏️ Твоё место рождения", callback_data="edit:birth_place")],
        [InlineKeyboardButton(text="✏️ Имя партнёра", callback_data="edit:partner_name")],
        [InlineKeyboardButton(text="✏️ Дата рождения партнёра", callback_data="edit:partner_birth_date")],
        [InlineKeyboardButton(text="✏️ Время рождения партнёра", callback_data="edit:partner_birth_time")],
        [InlineKeyboardButton(text="✏️ Место рождения партнёра", callback_data="edit:partner_birth_place")],
    ]
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await answer_target.answer(text, reply_markup=kb)
    await state.set_state(SolarStates.confirmation)


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
        await callback.message.edit_text("Запускаю расчёт...")
        if report_type == "synastry":
            await _run_synastry_analysis(callback.message, callback.from_user, state)
        else:
            await _run_solar_analysis(callback.message, callback.from_user, state)
        return

    log_event(callback.from_user.id, "payment_started")
    log_event(callback.from_user.id, f"{report_type}_payment_started")
    try:
        await callback.message.edit_text("Секунду, считаю короткий акцент по карте...")
    except Exception:
        pass
    await asyncio.sleep(1.4)

    try:
        pre_payment_pitch = _build_pre_payment_pitch(data, report_type)
    except Exception as e:
        await callback.message.answer(f"Не удалось подготовить предрасчёт: {e}")
        return

    try:
        await callback.message.edit_text("Акцент найден. Перепроверяю формулировку...")
    except Exception:
        pass
    await asyncio.sleep(0.8)

    await callback.message.answer(pre_payment_pitch)

    if report_type == "synastry":
        title = "Синастрия / совместимость"
        description = f"Разбор совместимости по двум натальным картам — {SYNASTRY_STARS_PRICE} ⭐"
        payload = "synastry_analysis"
        prices = [LabeledPrice(label="Синастрия", amount=SYNASTRY_STARS_PRICE)]
    else:
        title = "Разбор соляра на год"
        description = f"Полный астрологический разбор соляра — {SOLAR_STARS_PRICE} ⭐"
        payload = "solar_chart_analysis"
        prices = [LabeledPrice(label="Разбор соляра", amount=SOLAR_STARS_PRICE)]

    await callback.message.answer_invoice(
        title=title,
        description=description,
        payload=payload,
        currency="XTR",
        prices=prices,
        provider_token="",
    )


HOUSE_ACCENTS = {
    "1": "личность, внешний образ, самостоятельные решения и новый старт",
    "2": "деньги, самоценность, ресурсы и ощущение опоры",
    "3": "общение, обучение, документы, поездки и важные разговоры",
    "4": "дом, семья, переезд, внутреннее состояние и личная база",
    "5": "любовь, творчество, дети, удовольствие и желание проявляться",
    "6": "работа, режим, здоровье, привычки и ежедневная нагрузка",
    "7": "отношения, партнёрства, договорённости и важные союзы",
    "8": "глубокие перемены, общие деньги, близость и психологическая честность",
    "9": "расширение горизонтов, обучение, путешествия и новые смыслы",
    "10": "карьера, статус, цели, признание и движение вверх",
    "11": "друзья, команда, аудитория, планы на будущее и новые круги",
    "12": "завершение старого, тишина, восстановление и скрытые процессы",
}

PERSONAL_PLANETS = {"Солнце", "Луна", "Меркурий", "Венера", "Марс"}


def _build_pre_payment_pitch(data: dict, report_type: str) -> str:
    if report_type == "synastry":
        return _build_synastry_pre_payment_pitch(data)
    return _build_solar_pre_payment_pitch(data)


def _table_row(table: list[list[str]], name: str) -> Optional[list[str]]:
    for row in table[1:]:
        if row and row[0] == name:
            return row
    return None


def _top_house_from_planets(planets_table: list[list[str]]) -> Optional[str]:
    counts: dict[str, int] = {}
    for row in planets_table[1:]:
        if len(row) < 3:
            continue
        counts[row[2]] = counts.get(row[2], 0) + 1
    if not counts:
        return None
    return max(counts, key=counts.get)


def _closest_aspect(aspects_table: list[list[str]], personal_only: bool = False) -> Optional[list[str]]:
    rows = []
    for row in aspects_table[1:]:
        if len(row) < 4:
            continue
        if personal_only and row[0] not in PERSONAL_PLANETS and row[2] not in PERSONAL_PLANETS:
            continue
        try:
            orb = float(row[3])
        except ValueError:
            continue
        rows.append((orb, row))
    if not rows:
        return None
    return sorted(rows, key=lambda item: item[0])[0][1]


def _aspect_phrase(row: list[str]) -> str:
    return f"{row[0]} в аспекте «{row[1].lower()}» с {row[2].lower()} (орб {row[3]})"


def _build_solar_pre_payment_pitch(data: dict) -> str:
    birth_place = data["birth_place"]
    solar_place = data["solar_place"]
    cycle_year = data["solar_cycle_year"]
    day, month, year = (int(x) for x in data["birth_date"].split("."))

    birth_time = data.get("birth_time")
    if birth_time:
        hour, minute = (int(x) for x in birth_time.split(":"))
    else:
        hour, minute = 12, 0

    birth_tz = get_timezone(birth_place["lat"], birth_place["lon"])
    solar_tz = get_timezone(solar_place["lat"], solar_place["lon"])
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

    name = data.get("person_name") or "тебя"
    planets = chart_data.get("planets") or []
    sun_row = _table_row(planets, "Солнце")
    moon_row = _table_row(planets, "Луна")
    sun_house = sun_row[2] if sun_row and len(sun_row) > 2 else None
    moon_house = moon_row[2] if moon_row and len(moon_row) > 2 else None
    top_house = _top_house_from_planets(planets)
    focus_house = sun_house or top_house or moon_house
    focus = HOUSE_ACCENTS.get(focus_house or "", "главные события, выборы и внутренние перемены")
    closest = _closest_aspect(chart_data.get("aspects") or [])
    aspect_text = ""
    if closest:
        aspect_text = (
            f" Самый точный акцент в аспектах: {_aspect_phrase(closest)} — "
            "это добавляет году сильную тему, которую стоит раскрыть в полном разборе."
        )
    if moon_house and moon_house != focus_house:
        aspect_text += (
            f" Луна дополнительно подсвечивает {HOUSE_ACCENTS.get(moon_house, moon_house + ' дом')}."
        )

    return (
        f"🌞 Мы уже рассчитали соляр для {name} на {cycle_year}–{cycle_year + 1}.\n\n"
        "Год выглядит насыщенным и полным событий: карта показывает, что основной акцент "
        f"пойдёт через {focus}. Это не общий гороскоп — расчёт уже построен по твоей дате, "
        f"времени и месту соляра.{aspect_text}\n\n"
        f"Полная расшифровка покажет главную тему года, точки роста, зоны напряжения и "
        f"практичный фокус по сферам жизни. Стоимость полного разбора — {SOLAR_STARS_PRICE} ⭐."
    )


def _build_synastry_pre_payment_pitch(data: dict) -> str:
    birth_place = data["birth_place"]
    partner_birth_place = data["partner_birth_place"]
    day, month, year = (int(x) for x in data["birth_date"].split("."))
    p_day, p_month, p_year = (int(x) for x in data["partner_birth_date"].split("."))

    birth_time = data.get("birth_time")
    if birth_time:
        hour, minute = (int(x) for x in birth_time.split(":"))
    else:
        hour, minute = 12, 0

    partner_birth_time = data.get("partner_birth_time")
    if partner_birth_time:
        p_hour, p_minute = (int(x) for x in partner_birth_time.split(":"))
    else:
        p_hour, p_minute = 12, 0

    chart_data = compute_synastry(
        first_name=data.get("person_name", ""),
        first_year=year,
        first_month=month,
        first_day=day,
        first_hour=hour,
        first_minute=minute,
        first_tz=get_timezone(birth_place["lat"], birth_place["lon"]),
        first_lat=birth_place["lat"],
        first_lon=birth_place["lon"],
        first_place_label=birth_place["label"],
        partner_name=data.get("partner_name", ""),
        partner_year=p_year,
        partner_month=p_month,
        partner_day=p_day,
        partner_hour=p_hour,
        partner_minute=p_minute,
        partner_tz=get_timezone(partner_birth_place["lat"], partner_birth_place["lon"]),
        partner_lat=partner_birth_place["lat"],
        partner_lon=partner_birth_place["lon"],
        partner_place_label=partner_birth_place["label"],
    )

    first_name = data.get("person_name") or "ты"
    partner_name = data.get("partner_name") or "партнёр"
    closest = _closest_aspect(chart_data.get("aspects") or [], personal_only=True)
    aspect_text = ""
    if closest:
        aspect_text = (
            f" Уже видно один из главных крючков связи: {_aspect_phrase(closest)}."
        )

    return (
        f"💞 Мы уже рассчитали синастрию для пары {first_name} + {partner_name}.\n\n"
        "Связь выглядит неслучайной: в карте есть точки притяжения, эмоционального отклика "
        f"и зоны, где вы можете сильно включать друг друга.{aspect_text} Это как раз тот случай, "
        "где важно смотреть не только “подходим/не подходим”, а как именно работает динамика пары.\n\n"
        "Полная расшифровка покажет химию, эмоциональную совместимость, риски, ресурсы и то, "
        f"как вы влияете друг на друга. Стоимость полного разбора — {SYNASTRY_STARS_PRICE} ⭐."
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


@router.message(Command("stats"))
async def cmd_stats(message: Message):
    """Видна только владельцу бота (ADMIN_USER_ID в .env) — показывает воронку и источники."""
    admin_id = os.getenv("ADMIN_USER_ID")
    if admin_id and str(message.from_user.id) != admin_id.strip():
        return

    summary = funnel_summary()
    sources = list_sources()

    def count(event: str) -> int:
        return summary.get(event, 0)

    def pct(part: int, total: int) -> str:
        if total <= 0:
            return "—"
        return f"{part / total * 100:.0f}%"

    def product_block(title: str, prefix: str) -> list[str]:
        selected = count(f"{prefix}_selected")
        payment_started = count(f"{prefix}_payment_started")
        payment_success = count(f"{prefix}_payment_success")
        generated = count(f"{prefix}_generated")
        return [
            f"\n{title}:",
            f"выбрали: {selected}",
            f"дошли до оплаты: {payment_started} ({pct(payment_started, selected)} от выбора)",
            f"оплатили: {payment_success} ({pct(payment_success, payment_started)} от инвойса)",
            f"получили файл: {generated} ({pct(generated, payment_success)} от оплат)",
        ]

    lines = ["📊 Воронка (уникальные пользователи):"]
    lines.append(f"\nВсего стартов: {count('start')}")
    lines.append(f"ввели имя: {count('name_entered')}")
    lines.append(f"ввели дату рождения: {count('birth_date_entered')}")
    lines.extend(product_block("🌞 Соляр", "solar"))
    lines.extend(product_block("💞 Синастрия", "synastry"))

    lines.append("\nОбщие платежи (включая старые события до разделения):")
    lines.append(f"payment_started: {count('payment_started')}")
    lines.append(f"payment_success: {count('payment_success')}")

    lines.append("\n📍 Источники (?start=...):")
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

    prompt = build_solar_prompt(
        chart_data,
        person_name=data.get("person_name", ""),
        user_context=user_context,
    )

    try:
        buffer, stop_reason = await interpret_solar_chart(prompt)
    except Exception as e:
        await progress_msg.edit_text(f"Клод не ответил: {e}")
        await state.clear()
        return

    cut_off_note = ""
    if stop_reason == "max_tokens":
        cut_off_note = "\n\n⚠️ Черновик получился длиннее лимита и обрезался."

    # Второй проход: вычитка и сжатие до жёсткого лимита объёма + проверка
    # черновика на соответствие исходным данным карты.
    try:
        await progress_msg.edit_text(
            "✍️ Раскрываю акценты в полный разбор и проверяю текст..." + time_note
        )
    except Exception:
        pass

    review_prompt = build_review_prompt(
        buffer,
        chart_data,
        person_name=data.get("person_name", ""),
        user_context=user_context,
    )
    try:
        reviewed, review_stop_reason = await interpret_solar_chart(review_prompt)
        if reviewed.strip():
            buffer = reviewed
            cut_off_note = (
                "\n\n⚠️ Ответ получился длиннее лимита и обрезался даже после сокращения."
                if review_stop_reason == "max_tokens"
                else ""
            )
    except Exception:
        pass  # если вычитка не удалась — используем черновик как есть

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
    markdown_to_pdf(title, buffer, output_path)

    name_part = re.sub(r'[\\/:*?"<>|]', "", data.get("person_name", "")).strip()
    display_name = f"{name_part} {data['birth_date']} {cycle_year}-{cycle_year + 1}".strip()
    display_name = re.sub(r"\s+", " ", display_name)
    display_filename = f"{display_name}.pdf"

    log_event(from_user.id, "solar_generated")

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
            [InlineKeyboardButton(text="🔄 Рассчитать другой соляр", callback_data="restart:new")]
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
    prompt = build_synastry_prompt(chart_data, first_name=first_name, partner_name=partner_name)

    try:
        buffer, stop_reason = await interpret_solar_chart(prompt)
    except Exception as e:
        await progress_msg.edit_text(f"Клод не ответил: {e}")
        await state.clear()
        return

    cut_off_note = ""
    if stop_reason == "max_tokens":
        cut_off_note = "\n\n⚠️ Черновик получился длиннее лимита и обрезался."

    try:
        await progress_msg.edit_text("✍️ Раскрываю акценты пары в полный разбор и проверяю текст...")
    except Exception:
        pass

    review_prompt = build_synastry_review_prompt(
        buffer,
        chart_data,
        first_name=first_name,
        partner_name=partner_name,
    )
    try:
        reviewed, review_stop_reason = await interpret_solar_chart(review_prompt)
        if reviewed.strip():
            buffer = reviewed
            cut_off_note = (
                "\n\n⚠️ Ответ получился длиннее лимита и обрезался даже после сокращения."
                if review_stop_reason == "max_tokens"
                else ""
            )
    except Exception:
        pass

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
    markdown_to_pdf(title, buffer, output_path)

    safe_first = re.sub(r'[\\/:*?"<>|]', "", first_name).strip()
    safe_partner = re.sub(r'[\\/:*?"<>|]', "", partner_name).strip()
    display_name = f"Синастрия {safe_first} и {safe_partner}".strip()
    display_name = re.sub(r"\s+", " ", display_name)
    display_filename = f"{display_name}.pdf"

    log_event(from_user.id, "synastry_generated")

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
            [InlineKeyboardButton(text="🔄 Рассчитать ещё", callback_data="restart:new")]
        ]
    )
    await answer_target.answer("Готово! Если нужен ещё один разбор:", reply_markup=kb)

    await state.clear()


@router.callback_query(F.data == "restart:new")
async def process_restart(callback: CallbackQuery, state: FSMContext):
    await callback.answer()
    await start_flow(callback.message, state)
