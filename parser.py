import asyncio
import logging
import json
import os
from telethon import TelegramClient, events
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from dotenv import load_dotenv
from config import API_ID, API_HASH, SESSION_NAME, TELEGRAM_BOT_TOKEN, ADMIN_CHAT_IDS
from db import add_post, get_unnotified_posts, mark_posts_notified, get_current_post_for_admin
from dotenv import load_dotenv

load_dotenv()

# 🔧 Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 🌱 Загрузка .env
load_dotenv()

# 🤖 Инициализация Telethon и aiogram
client = TelegramClient(SESSION_NAME, API_ID, API_HASH)
bot = Bot(token=TELEGRAM_BOT_TOKEN)


# 📡 Загрузка списка каналов из channels.json
def load_channels():
    try:
        with open("channels.json", "r", encoding="utf-8") as f:
            channels = json.load(f)
        if not channels:
            raise ValueError("Список каналов пуст")
        return channels
    except Exception as e:
        logger.error(f"❌ Не удалось загрузить список каналов: {e}")
        return []


SOURCE_CHANNELS = load_channels()
logger.info(f"🎯 Каналы для мониторинга: {SOURCE_CHANNELS}")

if not SOURCE_CHANNELS:
    logger.warning("⚠️ Нет каналов для мониторинга. Добавьте их через меню бота.")
    exit()


# 🔁 Обработка новых сообщений
@client.on(events.NewMessage(chats=SOURCE_CHANNELS))
async def handler(event):
    logger.info("🚨 Сработал handler от Telethon!")

    raw_text = event.message.message
    source = event.chat.username or event.chat.title or str(event.chat_id)

    logger.info(f"🆕 Новый пост из {source}")
    post_id = add_post(source, raw_text)
    logger.info(f"📥 Пост #{post_id} сохранён в БД")

    # 🔔 Уведомление администратору только для тех, кто не в сессии модерации
    unnotified = get_unnotified_posts()
    if unnotified:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚀 Начать модерацию", callback_data="start_moderation")]
        ])
        for admin_id in ADMIN_CHAT_IDS:
            # Проверяем, не находится ли админ уже в сессии модерации
            if get_current_post_for_admin(admin_id) is not None:
                logger.info(f"Админ {admin_id} уже в сессии модерации, пропускаем уведомление")
                continue

            try:
                await bot.send_message(
                    chat_id=admin_id,
                    text=f"📥 Получено <b>{len(unnotified)}</b> новых постов.",
                    reply_markup=keyboard
                )
                logger.info(f"🔔 Уведомление отправлено администратору {admin_id}")
            except Exception as e:
                logger.error(f"❌ Ошибка при отправке уведомления: {e}")

        mark_posts_notified(unnotified)


# 🧪 Отладочная функция с ограничением вывода информации
async def debug_session_info():
    await client.start()
    me = await client.get_me()
    logger.info(f"👤 Авторизован как: {me.username or me.id}")

    # Ограничиваем вывод только первыми 5 каналами
    dialogs = await client.get_dialogs(limit=10)
    channel_count = 0

    for dialog in dialogs:
        if dialog.is_channel and channel_count < 5:
            logger.info(f"📡 Канал: {dialog.name} — {dialog.entity.username or dialog.id}")
            channel_count += 1

    if channel_count == 5:
        logger.info("... и другие каналы (показаны только первые 5)")


# 🚀 Запуск парсера
async def main():
    await client.start()
    await debug_session_info()
    logger.info(f"✅ Парсер запущен. Мониторим: {', '.join(SOURCE_CHANNELS)}")
    await client.run_until_disconnected()


if __name__ == "__main__":
    asyncio.run(main())