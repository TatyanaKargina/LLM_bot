import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties
from config import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_IDS
from menu_router import menu_router
from moderation_router import moderation_router
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram import Dispatcher
from aiogram.fsm.storage.memory import MemoryStorage
from dotenv import load_dotenv

load_dotenv()

# Настройка логов
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

# Инициализация бота и диспетчера
bot = Bot(token=TELEGRAM_BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher(storage=MemoryStorage())  # ⬅️ Без этого текстовые сообщения не обрабатываются

# Подключение роутеров
dp.include_router(moderation_router)
dp.include_router(menu_router)

# Храним последние уведомления для админов
last_notification = {}  # admin_id: message_id


# Фоновая проверка новых постов
async def background_check_for_news():
    await asyncio.sleep(3)  # Пауза перед стартом

    while True:
        from db import get_unnotified_posts, mark_posts_notified, get_current_post_for_admin

        post_ids = get_unnotified_posts()
        if post_ids:
            keyboard = InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🚀 Начать модерацию", callback_data="start_moderation")]
            ])

            for admin_id in ADMIN_CHAT_IDS:
                # Пропускаем админов, которые уже в сессии модерации
                if get_current_post_for_admin(admin_id) is not None:
                    logging.info(f"Админ {admin_id} уже в сессии модерации, пропускаем уведомление")
                    continue

                text = f"📬 Получено <b>{len(post_ids)}</b> новых постов."
                try:
                    if admin_id in last_notification:
                        # Проверяем, существует ли сообщение
                        try:
                            await bot.edit_message_text(
                                chat_id=admin_id,
                                message_id=last_notification[admin_id],
                                text=text,
                                reply_markup=keyboard
                            )
                            logging.info(f"🔁 Обновлено уведомление для {admin_id}")
                        except Exception:
                            # Если сообщение не найдено, отправляем новое
                            sent = await bot.send_message(
                                chat_id=admin_id,
                                text=text,
                                reply_markup=keyboard
                            )
                            last_notification[admin_id] = sent.message_id
                            logging.info(f"📤 Отправлено новое уведомление администратору {admin_id}")
                    else:
                        sent = await bot.send_message(
                            chat_id=admin_id,
                            text=text,
                            reply_markup=keyboard
                        )
                        last_notification[admin_id] = sent.message_id
                        logging.info(f"📤 Отправлено первое уведомление администратору {admin_id}")

                except Exception as e:
                    logging.warning(f"⚠️ Не удалось обновить/отправить сообщение для {admin_id}: {e}")
                    try:
                        sent = await bot.send_message(
                            chat_id=admin_id,
                            text=text,
                            reply_markup=keyboard
                        )
                        last_notification[admin_id] = sent.message_id
                        logging.info(f"📤 Повторно отправлено уведомление администратору {admin_id}")
                    except Exception as inner_e:
                        logging.error(f"❌ Не удалось вообще отправить уведомление: {inner_e}")

            mark_posts_notified(post_ids)

        await asyncio.sleep(30)  # Проверка каждые 30 секунд


# Точка входа
async def main():
    asyncio.create_task(background_check_for_news())
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())