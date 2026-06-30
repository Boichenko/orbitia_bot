from aiogram.fsm.state import State, StatesGroup


class SolarStates(StatesGroup):
    waiting_name = State()
    waiting_birth_date = State()
    waiting_birth_time = State()
    waiting_birth_place = State()
    waiting_birth_place_choice = State()
    waiting_solar_place = State()
    waiting_solar_place_choice = State()
    waiting_cycle_year = State()
    waiting_cycle_year_custom = State()
    waiting_context = State()
    confirmation = State()
