from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message

from services.analytics import log_event, register_user_source
from services.payment_jobs import cancel_payment_job, get_active_payment_job
from states import SolarStates

router = Router()


async def start_flow(answer_target, state: FSMContext) -> None:
    """Общая точка входа в диалог — используется и из /start, и из кнопки
    "Рассчитать другой соляр"."""
    await state.clear()
    kb = InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="💞 Синастрия / совместимость", callback_data="report:synastry")],
            [InlineKeyboardButton(text="🌞 Соляр", callback_data="report:solar")],
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
    active_job_id = get_active_payment_job(message.from_user.id)
    if active_job_id:
        kb = InlineKeyboardMarkup(
            inline_keyboard=[
                [
                    InlineKeyboardButton(
                        text="⏳ Подождать готовый разбор",
                        callback_data="activecalc:wait",
                    )
                ],
                [
                    InlineKeyboardButton(
                        text="🆕 Отменить и начать заново",
                        callback_data=f"activecalc:restart:{active_job_id}",
                    )
                ],
            ]
        )
        await message.answer(
            "Сейчас уже идёт оплаченный расчёт. Обычно он занимает несколько минут.\n\n"
            "Подождать готовый разбор или отменить его и начать новый расчёт?",
            reply_markup=kb,
        )
        return
    await start_flow(message, state)


@router.callback_query(F.data == "activecalc:wait")
async def wait_for_active_calculation(callback: CallbackQuery):
    await callback.answer("Продолжаю расчёт")
    await callback.message.edit_text(
        "Хорошо, продолжаю готовить разбор ⏳\n"
        "Пришлю результат сюда, как только он будет готов."
    )


@router.callback_query(F.data.startswith("activecalc:restart:"))
async def restart_during_active_calculation(callback: CallbackQuery, state: FSMContext):
    job_id = callback.data.rsplit(":", 1)[1]
    cancelled = cancel_payment_job(job_id, callback.from_user.id)
    if not cancelled:
        await callback.answer("Расчёт уже завершён", show_alert=True)
        return

    await callback.answer("Текущий расчёт отменён")
    await callback.message.edit_text("Текущий расчёт отменён. Начинаем заново.")
    await start_flow(callback.message, state)
