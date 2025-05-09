# config.py
import os
from dotenv import load_dotenv

load_dotenv()

# Telegram API (Telethon)
API_ID = os.getenv("API_ID")
API_HASH = os.getenv("API_HASH")
SESSION_NAME = os.getenv("SESSION_NAME", "session_name")

# Каналы для парсинга
SOURCE_CHANNELS = os.getenv("SOURCE_CHANNELS", "").split(",")

# Telegram Bot
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
TARGET_CHANNEL_ID = os.getenv("TARGET_CHANNEL_ID")

# Администраторы (массив, даже если один)
ADMIN_CHAT_IDS = [int(i) for i in os.getenv("ADMIN_CHAT_ID", "0").split(",")]

# Gemini / GPT
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
