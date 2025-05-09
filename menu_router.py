from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
import json
import os

from config import ADMIN_CHAT_IDS
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest
from config import ADMIN_CHAT_IDS
from aiogram.fsm.context import FSMContext

menu_router = Router()
user_state = {}
CHANNELS_FILE = "channels.json"
monitoring_active = set()


def load_channels():
    if not os.path.exists(CHANNELS_FILE):
        return []
    with open(CHANNELS_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def save_channels(channels):
    with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
        json.dump(channels, f)


def get_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📡 Каналы", callback_data="manage_channels")],
        [InlineKeyboardButton(text="🚀 Запуск мониторинга", callback_data="start_monitoring")],
        [InlineKeyboardButton(text="📝 Модерация постов", callback_data="go_to_moderation")]
    ])


@menu_router.message(CommandStart())
async def start_menu(message: types.Message):
    if message.from_user.id not in ADMIN_CHAT_IDS:
        await message.answer("🚫 У вас нет доступа.")
        return
    await message.answer("👋 Добро пожаловать! Выберите действие:", reply_markup=get_main_menu())


@menu_router.message(Command("clear"))
async def clear_command(message: Message):
    if message.from_user.id not in ADMIN_CHAT_IDS:
        return

    chat_id = message.chat.id
    bot = message.bot

    deleted = 0
    # Пробуем удалить последние 50 сообщений бота
    for i in range(message.message_id - 1, message.message_id - 50, -1):
        try:
            await bot.delete_message(chat_id, i)
            deleted += 1
        except TelegramBadRequest:
            continue  # сообщение не найдено или уже удалено

    await bot.send_message(chat_id, "👋 Главное меню:", reply_markup=get_main_menu())


@menu_router.callback_query(F.data == "manage_channels")
async def show_channels(callback: types.CallbackQuery):
    channels = load_channels()
    channel_list = "\n".join(channels) if channels else "Список пуст."
    keyboard = [
        [InlineKeyboardButton(text="➕ Добавить", callback_data="add_channel")],
        [InlineKeyboardButton(text="➖ Удалить", callback_data="delete_channel")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ]
    await callback.message.edit_text(
        f"📡 Текущие каналы для мониторинга:\n{channel_list}",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )


@menu_router.callback_query(F.data == "add_channel")
async def prompt_add_channel(callback: types.CallbackQuery):
    user_state[callback.from_user.id] = "adding"
    await callback.message.edit_text("Введите каналы через запятую или пробел:")


@menu_router.callback_query(F.data == "delete_channel")
async def prompt_delete_channel(callback: types.CallbackQuery):
    user_state[callback.from_user.id] = "deleting"
    await callback.message.edit_text("Введите канал(ы), которые хотите удалить:")


@menu_router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery):
    await callback.message.edit_text("👋 Главное меню:", reply_markup=get_main_menu())


# Изменяем обработчик текстовых сообщений - добавляем проверку на состояние FSM
@menu_router.message(F.text)
async def handle_channel_input(message: types.Message, state: FSMContext):
    # Получаем текущее состояние FSM
    current_state = await state.get_state()

    # Если пользователь находится в каком-либо состоянии FSM, 
    # не обрабатываем сообщение в этом обработчике
    if current_state is not None:
        return

    user_id = message.from_user.id
    if user_id not in user_state:
        return

    action = user_state.pop(user_id)
    input_text = message.text.strip()
    channels = load_channels()

    input_channels = [c.strip().lstrip("@") for c in input_text.replace(",", " ").split()]
    input_channels = list(set(input_channels))  # Удаляем дубли

    if action == "adding":
        new_channels = [f"@{c}" for c in input_channels if f"@{c}" not in channels]
        channels.extend(new_channels)
        save_channels(channels)
        await message.answer(f"✅ Добавлено каналов: {len(new_channels)}")
    elif action == "deleting":
        removed = [f"@{c}" for c in input_channels if f"@{c}" in channels]
        channels = [c for c in channels if c not in removed]
        save_channels(channels)
        await message.answer(f"🗑️ Удалено каналов: {len(removed)}")

    await message.answer("👋 Главное меню:", reply_markup=get_main_menu())


@menu_router.callback_query(F.data == "start_monitoring")
async def start_monitoring(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id in monitoring_active:
        text = "📡 Мониторинг уже запущен."
    else:
        monitoring_active.add(user_id)
        text = "✅ Мониторинг запущен."

    keyboard = [
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")],
        [InlineKeyboardButton(text="🛑 Завершить мониторинг", callback_data="stop_monitoring")]
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))


@menu_router.callback_query(F.data == "stop_monitoring")
async def stop_monitoring(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    monitoring_active.discard(user_id)
    await callback.message.edit_text("🛑 Мониторинг остановлен.", reply_markup=get_main_menu())