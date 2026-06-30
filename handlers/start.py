from aiogram import Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.types import Message

from services.analytics import log_event, register_user_source
from states import SolarStates

router = Router()


async def start_flow(answer_target, state: FSMContext) -> None:
    """Общая точка входа в диалог — используется и из /start, и из кнопки
    "Рассчитать другой соляр"."""
    await state.clear()
    await answer_target.answer(
        "Привет! Я Orbitia 🌞\n\n"
        "Я считаю соляр — карту твоего персонального года, который начинается "
        "в день рождения. Это не шаблонный гороскоп, а точный астрономический расчёт: "
        "по нему видно, какие сферы жизни будут активнее всего в этом году, где ждать "
        "роста, а где — напряжения, и почему. Поможет понять логику года и спланировать "
        "его осознанно, а не наугад.\n\n"
        "Считаю по реальным эфемеридам и даю развёрнутый разбор — по домам, "
        "планетам и аспектам: карьера, отношения, деньги, здоровье и многое другое.\n\n"
        "Для начала: как зовут человека, для которого считаем?"
    )
    await state.set_state(SolarStates.waiting_name)


@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext, command: CommandObject):
    source = command.args
    register_user_source(message.from_user.id, source)
    log_event(message.from_user.id, "start")
    await start_flow(message, state)
