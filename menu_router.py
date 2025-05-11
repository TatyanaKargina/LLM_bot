from aiogram import Router, types, F
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.filters import CommandStart
import json
import os
import asyncio
import logging

from config import ADMIN_CHAT_IDS
from aiogram.filters import Command
from aiogram.types import Message
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup


# Состояния для FSM
class ChannelManagement(StatesGroup):
    adding_channels = State()
    deleting_channels = State()


menu_router = Router()
monitoring_active = set()
CHANNELS_FILE = "channels.json"
logger = logging.getLogger(__name__)


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

    # Удаляем сообщение с командой
    try:
        await message.delete()
    except Exception as e:
        pass

    # Ограничиваем количество удаляемых сообщений
    MAX_MESSAGES_TO_DELETE = 200

    deleted = 0
    try:
        async for msg in message.bot.get_chat_history(message.chat.id, limit=MAX_MESSAGES_TO_DELETE):
            try:
                await message.bot.delete_message(message.chat.id, msg.message_id)
                deleted += 1
                # Небольшие задержки между пакетами запросов
                if deleted % 10 == 0:
                    await asyncio.sleep(0.3)
            except Exception:
                continue
    except Exception as e:
        pass

    # Отправляем главное меню, которое будет единственным сообщением
    await message.answer("👋 Главное меню:", reply_markup=get_main_menu())


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
async def prompt_add_channel(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(ChannelManagement.adding_channels)
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Отмена", callback_data="cancel_channel_operation")]
    ])
    await callback.message.edit_text(
        "Введите каналы через запятую или пробел:",
        reply_markup=keyboard
    )


@menu_router.callback_query(F.data == "delete_channel")
async def show_delete_channel_menu(callback: types.CallbackQuery):
    channels = load_channels()
    if not channels:
        await callback.message.edit_text(
            "Список каналов пуст.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Назад", callback_data="manage_channels")]
            ])
        )
        return

    # Создаем кнопки для каждого канала
    keyboard = []
    for channel in channels:
        keyboard.append([
            InlineKeyboardButton(
                text=f"❌ {channel}",
                callback_data=f"remove_channel_{channel}"
            )
        ])

    # Добавляем кнопку назад
    keyboard.append([InlineKeyboardButton(text="🔙 Назад", callback_data="manage_channels")])

    await callback.message.edit_text(
        "Выберите канал для удаления:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard)
    )


@menu_router.callback_query(F.data.startswith("remove_channel_"))
async def remove_channel(callback: types.CallbackQuery):
    channel_to_remove = callback.data.replace("remove_channel_", "")
    channels = load_channels()

    if channel_to_remove in channels:
        channels.remove(channel_to_remove)
        save_channels(channels)

        # Показываем временное сообщение об успехе
        temp_message = await callback.message.edit_text(f"Канал {channel_to_remove} удален.")

        # Небольшая задержка и возврат к списку каналов
        await asyncio.sleep(1)
        await show_delete_channel_menu(callback)
    else:
        await callback.answer("Канал не найден в списке")


@menu_router.callback_query(F.data == "cancel_channel_operation")
async def cancel_channel_operation(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()
    await callback.message.edit_text("👋 Главное меню:", reply_markup=get_main_menu())


@menu_router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()  # Очищаем состояние при возврате в главное меню
    await callback.message.edit_text("👋 Главное меню:", reply_markup=get_main_menu())


@menu_router.message(ChannelManagement.adding_channels)
async def handle_add_channels(message: types.Message, state: FSMContext):
    # Удаляем сообщение пользователя
    try:
        await message.delete()
    except Exception:
        pass

    # Остальной код обработки
    # ...

    # Получаем предыдущее сообщение с инструкцией и удаляем его
    data = await state.get_data()
    instruction_message_id = data.get('instruction_message_id')
    if instruction_message_id:
        try:
            await message.bot.delete_message(chat_id=message.chat.id, message_id=instruction_message_id)
        except Exception:
            pass

    # Отправляем временное сообщение об успехе и затем удаляем его
    status_message = await message.answer(f"✅ Каналы добавлены.")
    await asyncio.sleep(1)
    try:
        await status_message.delete()
    except Exception:
        pass

    # Показываем главное меню
    await message.answer("👋 Главное меню:", reply_markup=get_main_menu())
    await state.clear()


@menu_router.message(ChannelManagement.deleting_channels)
async def handle_delete_channels(message: types.Message, state: FSMContext):
    input_text = message.text.strip()
    channels = load_channels()

    input_channels = [c.strip().lstrip("@") for c in input_text.replace(",", " ").split()]
    removed = [f"@{c}" for c in input_channels if f"@{c}" in channels]
    channels = [c for c in channels if c not in removed]
    save_channels(channels)

    # Удаляем сообщение пользователя
    try:
        await message.delete()
    except Exception as e:
        logger.error(f"Не удалось удалить сообщение пользователя: {e}")

    # Отправляем статусное сообщение и затем удаляем его
    status_msg = await message.answer(f"🗑️ Удалено каналов: {len(removed)}")
    await state.clear()

    main_menu_msg = await message.answer("👋 Главное меню:", reply_markup=get_main_menu())

    # Удаляем статусное сообщение после задержки
    await asyncio.sleep(2)
    try:
        await status_msg.delete()
    except Exception as e:
        logger.error(f"Не удалось удалить статусное сообщение: {e}")


@menu_router.callback_query(F.data == "start_monitoring")
async def start_monitoring(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if user_id in monitoring_active:
        text = "📡 Мониторинг уже запущен."
    else:
        monitoring_active.add(user_id)
        text = "✅ Мониторинг запущен."

    keyboard = [
        [InlineKeyboardButton(text="🛑 Завершить мониторинг", callback_data="stop_monitoring")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=keyboard))


@menu_router.callback_query(F.data == "stop_monitoring")
async def stop_monitoring(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    monitoring_active.discard(user_id)
    await callback.message.edit_text(
        "🛑 Мониторинг остановлен.",
        reply_markup=get_main_menu()
    )