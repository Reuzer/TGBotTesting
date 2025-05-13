import json
import logging
from aiogram import Bot, Dispatcher, F, types
from aiogram.types import Message, CallbackQuery, FSInputFile
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.filters import Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
import asyncio
import os

API_TOKEN = '7697724690:AAGafP4hFJIVL9QJIHpwnsO3t9YHXaABJJ0'

bot = Bot(token=API_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())

USERS_DB = "data/users.json"
MAP_PATH = "data/map.jpg"

def load_users():
    try:
        with open(USERS_DB, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return []

def save_users(users):
    with open(USERS_DB, "w", encoding="utf-8") as f:
        json.dump(users, f, indent=2, ensure_ascii=False)

def get_user(uid):
    for u in load_users():
        if u["user_id"] == uid:
            return u
    return None

def register_user(uid, group_id, role):
    users = load_users()
    for u in users:
        if u["user_id"] == uid:
            u["role"] = role
            u["group_id"] = group_id
            save_users(users)
            return
    users.append({"user_id": uid, "group_id": group_id, "role": role})
    save_users(users)

class InputState(StatesGroup):
    links = State()
    teachers = State()
    starosta = State()
    map = State()
    register_group = State()

@dp.message(Command("start"))
async def cmd_start(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)

    if user:
        if "role" in user and user["role"] in ["student", "leader"]:
            await send_main_menu(message, user["role"])
            return
        else:
            group = user["group_id"]
            kb = InlineKeyboardBuilder()
            kb.button(text="Я студент", callback_data=f"role_student_{group}")
            kb.button(text="Я руководитель", callback_data=f"role_leader_{group}")
            await message.answer("Вы уже указали группу.\nВыберите вашу роль:", reply_markup=kb.as_markup())
            return

    await message.answer("Введите ID вашей группы (например: ИС-301):")
    await state.set_state(InputState.register_group)

@dp.message(InputState.register_group)
async def register_group_handler(message: Message, state: FSMContext):
    group = message.text.strip()
    await state.update_data(group_id=group)
    kb = InlineKeyboardBuilder()
    kb.button(text="Я студент", callback_data=f"role_student_{group}")
    kb.button(text="Я руководитель", callback_data=f"role_leader_{group}")
    await message.answer("Выберите вашу роль:", reply_markup=kb.as_markup())
    await state.clear()

@dp.callback_query(F.data.startswith("role_"))
async def role_callback(callback: CallbackQuery):
    role, group_id = callback.data.split("_")[1], callback.data.split("_")[2]
    register_user(callback.from_user.id, group_id, role)
    group_file = f"data/{group_id}.json"
    if not os.path.exists(group_file):
        with open(group_file, "w", encoding="utf-8") as f:
            json.dump({}, f, ensure_ascii=False, indent=2)
    await send_main_menu(callback.message, role)

async def send_main_menu(message: Message, role: str):
    kb = InlineKeyboardBuilder()
    kb.button(text="📎 Ссылки", callback_data="get_links")
    kb.button(text="👨‍🏫 Преподаватели", callback_data="get_teachers")
    kb.button(text="👤 Староста", callback_data="get_starosta")
    kb.button(text="📍 Схема", callback_data="get_map")

    if role == "leader":
        kb.button(text="➕ Заменить ссылки", callback_data="input_links")
        kb.button(text="➕ Заменить преподавателей", callback_data="input_teachers")
        kb.button(text="➕ Заменить старосту", callback_data="input_starosta")
        kb.button(text="🖼️ Заменить схему", callback_data="input_map")

    kb.adjust(1)  # <=== ВАЖНО: одна кнопка в строке

    await message.answer("Выберите действие:", reply_markup=kb.as_markup())


# --- Получение информации ---

@dp.callback_query(F.data == "get_links")
async def show_links(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    group_data = load_group_data(user["group_id"])
    links = group_data.get("links", "Ссылки не найдены.")
    await callback.message.answer(f"📎 Ссылки:\n{links}")

@dp.callback_query(F.data == "get_teachers")
async def show_teachers(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    group_data = load_group_data(user["group_id"])
    teachers = group_data.get("teachers", "Преподаватели не указаны.")
    await callback.message.answer(f"👨‍🏫 Преподаватели:\n{teachers}")

@dp.callback_query(F.data == "get_starosta")
async def show_starosta(callback: CallbackQuery):
    user = get_user(callback.from_user.id)
    group_data = load_group_data(user["group_id"])
    starosta = group_data.get("starosta", "Староста не указан.")
    await callback.message.answer(f"👤 Староста:\n{starosta}")

@dp.callback_query(F.data == "get_map")
async def show_map(callback: CallbackQuery):
    if os.path.exists(MAP_PATH):
        await callback.message.answer_photo(FSInputFile(MAP_PATH))
    else:
        await callback.message.answer("Схема ещё не загружена.")

# --- Ввод информации суперюзером ---

@dp.callback_query(F.data == "input_links")
async def ask_links(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите новые ссылки (они заменят старые):")
    await state.set_state(InputState.links)

@dp.message(InputState.links)
async def save_links(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    update_group_field(user["group_id"], "links", message.text)
    await message.answer("Ссылки обновлены.")
    await state.clear()

@dp.callback_query(F.data == "input_teachers")
async def ask_teachers(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите новых преподавателей (они заменят старых):")
    await state.set_state(InputState.teachers)

@dp.message(InputState.teachers)
async def save_teachers(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    update_group_field(user["group_id"], "teachers", message.text)
    await message.answer("Преподаватели обновлены.")
    await state.clear()

@dp.callback_query(F.data == "input_starosta")
async def ask_starosta(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Введите данные о старосте:")
    await state.set_state(InputState.starosta)

@dp.message(InputState.starosta)
async def save_starosta(message: Message, state: FSMContext):
    user = get_user(message.from_user.id)
    update_group_field(user["group_id"], "starosta", message.text)
    await message.answer("Староста обновлён.")
    await state.clear()

@dp.callback_query(F.data == "input_map")
async def ask_map(callback: CallbackQuery, state: FSMContext):
    await callback.message.answer("Отправьте изображение схемы (JPG/PNG). Предыдущая будет заменена.")
    await state.set_state(InputState.map)

@dp.message(InputState.map, F.photo)
async def save_map(message: Message, state: FSMContext):
    photo = message.photo[-1]
    await photo.download(destination=MAP_PATH)
    await message.answer("Схема успешно загружена.")
    await state.clear()

# --- Вспомогательные функции ---

def load_group_data(group_id):
    path = f"data/{group_id}.json"
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def update_group_field(group_id, field, value):
    path = f"data/{group_id}.json"
    data = load_group_data(group_id)
    data[field] = value
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# --- Запуск ---

async def main():
    logging.basicConfig(level=logging.INFO)
    os.makedirs("data", exist_ok=True)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
