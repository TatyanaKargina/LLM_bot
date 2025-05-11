# config.py
import os
import logging
from dotenv import load_dotenv

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger(__name__)

# Загрузка переменных окружения
load_dotenv()
logger.info("✅ Загружены переменные окружения")

# Telegram API (Telethon)
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_NAME = os.getenv("SESSION_NAME", "session_name")

# Каналы для парсинга
SOURCE_CHANNELS = os.getenv("SOURCE_CHANNELS", "").split(",")

# Telegram Bot
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TARGET_CHANNEL_ID = os.getenv("TARGET_CHANNEL_ID")

# Проверка наличия токена
if not TELEGRAM_BOT_TOKEN:
    logger.error("❌ Не задан TELEGRAM_BOT_TOKEN в .env файле!")

# Проверка наличия целевого канала
if not TARGET_CHANNEL_ID:
    logger.error("❌ Не задан TARGET_CHANNEL_ID в .env файле!")

# Администраторы (массив, даже если один)
try:
    ADMIN_CHAT_IDS = [int(i) for i in os.getenv("ADMIN_CHAT_ID", "0").split(",")]
    if not ADMIN_CHAT_IDS or ADMIN_CHAT_IDS == [0]:
        logger.warning("⚠️ Не заданы ADMIN_CHAT_IDS в .env файле!")
except ValueError:
    logger.error("❌ Неверный формат ADMIN_CHAT_ID в .env файле!")
    ADMIN_CHAT_IDS = []

# Gemini / GPT
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
if not GEMINI_API_KEY:
    logger.warning("⚠️ Не задан GEMINI_API_KEY в .env файле!")