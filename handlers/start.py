from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, Message

from services.analytics import log_event, register_user_source
from states import SolarStates

router = Router()


async def start_flow(answer_target, state: FSMContext) -> None:
    """Общая точка входа в диалог — используется и из /start, и из кнопки
    "Рассчитать другой соляр"."""
    await state.clear()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💞 Синастрия / совместимость — 300 ⭐", callback_data="report:synastry")],
            [InlineKeyboardButton(text="🌞 Соляр — 100 ⭐", callback_data="report:solar")],
        ]
    )
    await answer_target.answer(
        "Привет! Я Orbitia 🌞\n\n"
        "Я считаю соляр на персональный год и синастрию совместимости по данным "
        "двух людей. Расчёт идёт по реальным эфемеридам, с развёрнутым разбором "
        "планет, домов и аспектов.\n\n"
        "Что хочешь рассчитать?",
        reply_markup=kb,
    )
    await state.set_state(SolarStates.choosing_report_type)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, command: CommandObject):
    source = command.args
    register_user_source(message.from_user.id, source)
    log_event(message.from_user.id, "start")
    await start_flow(message, state)
