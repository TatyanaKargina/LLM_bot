import sqlite3
import logging
import asyncio
from aiogram import Router, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup
from config import ADMIN_CHAT_IDS, TARGET_CHANNEL_ID
from db import (
    get_new_posts, create_session, get_post,
    get_current_post_for_admin, set_post_status,
    get_session_index, get_session_total,
    advance_session, end_session
)
from gemini import revise_text_with_chatgpt
from menu_router import get_main_menu  # Для кнопки "Назад"
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup


class GeminiProcessing(StatesGroup):
    waiting_for_comment = State()


logger = logging.getLogger(__name__)

moderation_router = Router()


@moderation_router.callback_query(F.data == "go_to_moderation")
async def show_moderation_button(callback: types.CallbackQuery):
    new_posts = get_new_posts()
    if not new_posts:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
        ])
        await callback.message.edit_text(
            "Нет новых постов для модерации.",
            reply_markup=keyboard
        )
        return

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🚀 Начать модерацию", callback_data="start_moderation")],
        [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
    ])
    await callback.message.edit_text(
        f"📬 Получено <b>{len(new_posts)}</b> новых постов.",
        reply_markup=keyboard
    )


@moderation_router.callback_query(F.data == "back_to_main")
async def back_to_main(callback: types.CallbackQuery, state: FSMContext):
    await state.clear()  # Очищаем состояние при возврате в главное меню
    await callback.message.edit_text("👋 Главное меню:", reply_markup=get_main_menu())


@moderation_router.callback_query(F.data == "start_moderation")
async def start_moderation(callback: types.CallbackQuery):
    admin_id = callback.from_user.id

    # Проверяем, есть ли уже активная сессия
    current_post = get_current_post_for_admin(admin_id)
    if current_post is not None:
        # Сессия существует - предлагаем продолжить или перезапустить
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="▶️ Продолжить текущую сессию", callback_data="continue_session")],
            [InlineKeyboardButton(text="🔄 Начать заново", callback_data="restart_session")],
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
        ])
        await callback.message.edit_text(
            "У вас уже есть активная сессия модерации.",
            reply_markup=keyboard
        )
        return

    # Нет активной сессии, создаем новую
    new_posts = get_new_posts()

    logger.info(f"🔎 Модерация запущена. Найдено постов: {len(new_posts)}")
    logger.info(f"📝 ID новых постов: {new_posts}")

    if not new_posts:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
        ])
        await callback.message.edit_text(
            "Нет новых постов для модерации.",
            reply_markup=keyboard
        )
        return

    create_session(admin_id, new_posts)
    logger.info(f"📦 Создана сессия модерации для {admin_id} с постами: {new_posts}")

    # Отправляем и сразу сохраняем сообщение о начале модерации
    start_message = await callback.message.edit_text("Модерация началась ✅")

    # Отправляем первый пост для модерации
    await send_current_post(admin_id, callback.bot, callback.message.chat.id)

    # Удаляем сообщение "Модерация началась" через небольшую задержку
    await asyncio.sleep(1)
    try:
        await start_message.delete()
    except Exception as e:
        logger.error(f"Не удалось удалить сообщение о начале модерации: {e}")


@moderation_router.callback_query(F.data == "continue_session")
async def continue_moderation_session(callback: types.CallbackQuery):
    admin_id = callback.from_user.id
    start_message = await callback.message.edit_text("Продолжаем модерацию ✅")
    await send_current_post(admin_id, callback.bot, callback.message.chat.id)
    await asyncio.sleep(1)
    try:
        await start_message.delete()
    except Exception as e:
        logger.error(f"Не удалось удалить сообщение: {e}")


@moderation_router.callback_query(F.data == "restart_session")
async def restart_moderation_session(callback: types.CallbackQuery):
    admin_id = callback.from_user.id
    # Завершаем текущую сессию
    end_session(admin_id)
    # Перенаправляем на start_moderation
    await start_moderation(callback)


async def send_current_post(admin_id: int, bot, chat_id: int):
    post_id = get_current_post_for_admin(admin_id)

    if post_id is None:
        await bot.send_message(
            chat_id=chat_id,
            text="✅ Все посты из сессии обработаны.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Вернуться в меню", callback_data="back_to_main")]
            ])
        )
        return

    post = get_post(post_id)
    if not post:
        advance_session(admin_id)
        await send_current_post(admin_id, bot, chat_id)
        return

    post_number = get_session_index(admin_id) + 1
    total = get_session_total(admin_id)

    # Используем styled_text (который может быть обработан Gemini), если он доступен
    post_text = post[3] if post[3] else post[2]

    text = f"<b>Пост {post_number} из {total}</b>\n\n{post_text}"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Опубликовать", callback_data=f"publish_{post_id}"),
            InlineKeyboardButton(text="⏳ Отложить", callback_data=f"skip_{post_id}")
        ],
        [InlineKeyboardButton(text="🧠 Обработать (Gemini)", callback_data=f"gemini_{post_id}")],
        [InlineKeyboardButton(text="🗑 Отклонить", callback_data=f"decline_{post_id}")],
        [InlineKeyboardButton(text="🔙 В меню", callback_data="end_moderation")]
    ])

    await bot.send_message(chat_id=chat_id, text=text, reply_markup=keyboard)


@moderation_router.callback_query(F.data == "end_moderation")
async def end_moderation(callback: types.CallbackQuery, state: FSMContext):
    admin_id = callback.from_user.id

    # Удаляем сообщение с постом
    await callback.message.delete()

    # Очищаем сессию
    end_session(admin_id)

    # Возвращаемся в главное меню
    await callback.message.answer("👋 Главное меню:", reply_markup=get_main_menu())


@moderation_router.callback_query(F.data.startswith(("publish_", "gemini_", "skip_", "decline_")))
async def handle_post_action(callback: types.CallbackQuery, state: FSMContext):
    admin_id = callback.from_user.id
    data = callback.data

    if data.startswith("publish_"):
        post_id = int(data.split("_")[1])
        post = get_post(post_id)
        if not post:
            await callback.message.edit_text("⚠️ Пост не найден.")
            return

        # Используем текст с стилем (после Gemini), если он есть
        publish_text = post[3] if post[3] else post[2]

        await callback.bot.send_message(chat_id=TARGET_CHANNEL_ID, text=publish_text)
        set_post_status(post_id, "published")

        # Удаляем сообщение с постом вместо редактирования
        await callback.message.delete()

        # Сохраняем message_id для последующего удаления
        status_message = await callback.bot.send_message(
            chat_id=callback.message.chat.id,
            text="✅ Пост опубликован."
        )

        # Сохраняем ID сообщения для удаления
        await state.update_data(status_message_id=status_message.message_id)

        advance_session(admin_id)
        await send_current_post(admin_id, callback.bot, callback.message.chat.id)

        # Удаляем сообщение о статусе через небольшую задержку
        await asyncio.sleep(1)
        await status_message.delete()

    elif data.startswith("skip_"):
        post_id = int(data.split("_")[1])
        set_post_status(post_id, "skipped")

        # Удаляем сообщение с постом
        await callback.message.delete()

        # Отправляем статус (который будет удален)
        status_message = await callback.bot.send_message(
            chat_id=callback.message.chat.id,
            text="⏳ Пост отложен."
        )

        advance_session(admin_id)
        await send_current_post(admin_id, callback.bot, callback.message.chat.id)

        # Удаляем сообщение о статусе
        await asyncio.sleep(1)
        await status_message.delete()

    elif data.startswith("gemini_"):
        post_id = int(data.split("_")[1])
        await state.update_data(post_id=post_id)
        await state.update_data(post_message_id=callback.message.message_id)  # Сохраняем ID сообщения с постом
        await state.update_data(chat_id=callback.message.chat.id)  # Сохраняем chat_id в state
        await state.set_state(GeminiProcessing.waiting_for_comment)

        # Добавляем кнопку отмены
        keyboard = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🔙 Отмена", callback_data=f"cancel_gemini_{post_id}")]
        ])

        # Сделаем сообщение более явным, чтобы пользователь понимал, что нужно сделать
        instruction_message = await callback.message.answer(
            "💬 Введите комментарий для редактирования поста в Gemini:",
            reply_markup=keyboard
        )

        # Сохраняем ID сообщения с инструкцией для последующего удаления
        await state.update_data(instruction_message_id=instruction_message.message_id)

    elif data.startswith("decline_"):
        post_id = int(data.split("_")[1])
        try:
            conn = sqlite3.connect("news.db", check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute("DELETE FROM news WHERE id = ?", (post_id,))
            conn.commit()
            conn.close()
            await callback.message.delete()

            # Добавляем сообщение о статусе, которое будет удалено
            status_message = await callback.message.answer("🗑 Пост удален.")

            # Переходим к следующему посту
            advance_session(admin_id)
            await send_current_post(admin_id, callback.bot, callback.message.chat.id)

            # Удаляем сообщение о статусе после задержки
            await asyncio.sleep(1)
            await status_message.delete()

        except Exception as e:
            error_msg = await callback.message.edit_text(
                f"❌ Ошибка при удалении поста: {e}",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🔙 Назад", callback_data="back_to_main")]
                ])
            )
            # Удаляем сообщение об ошибке через некоторое время
            await asyncio.sleep(3)
            await error_msg.delete()
            return


@moderation_router.callback_query(F.data.startswith("cancel_gemini_"))
async def cancel_gemini_processing(callback: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    instruction_message_id = data.get('instruction_message_id')

    # Удаляем сообщение с инструкцией
    if instruction_message_id:
        try:
            await callback.bot.delete_message(
                chat_id=callback.message.chat.id,
                message_id=instruction_message_id
            )
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение с инструкцией: {e}")

    await state.clear()

    # Показываем кратковременное сообщение об отмене
    cancel_message = await callback.answer("Редактирование отменено")

    # Продолжаем модерацию текущего поста
    admin_id = callback.from_user.id
    await send_current_post(admin_id, callback.bot, callback.message.chat.id)


# Обработчик сообщений при ожидании комментария для Gemini
@moderation_router.message(GeminiProcessing.waiting_for_comment)
async def handle_admin_comment(message: types.Message, state: FSMContext):
    logger.info(f"💬 Комментарий получен от пользователя {message.from_user.id}: {message.text}")
    data = await state.get_data()
    logger.debug(f"FSM Data: {data}")
    post_id = data.get('post_id')
    chat_id = data.get('chat_id', message.chat.id)  # Получаем chat_id из state или используем текущий
    instruction_message_id = data.get('instruction_message_id')  # ID сообщения с инструкцией

    # Сразу удаляем комментарий пользователя
    await message.delete()

    # Удаляем сообщение с инструкцией
    if instruction_message_id:
        try:
            await message.bot.delete_message(chat_id=chat_id, message_id=instruction_message_id)
        except Exception as e:
            logger.error(f"Не удалось удалить сообщение с инструкцией: {e}")

    if not post_id:
        error_message = await message.answer("⚠️ Ошибка состояния: не найден ID поста.")
        await state.clear()
        # Удаляем сообщение об ошибке через некоторое время
        await asyncio.sleep(3)
        await error_message.delete()
        return

    post = get_post(post_id)
    if not post:
        error_message = await message.answer("⚠️ Пост не найден.")
        await state.clear()
        # Удаляем сообщение об ошибке через некоторое время
        await asyncio.sleep(3)
        await error_message.delete()
        return

    raw_text = post[2]

    # Показываем сообщение о процессе обработки
    processing_message = await message.answer("⏳ Обрабатываю пост с помощью Gemini...")

    # Добавляем больше логов для отладки
    logger.info(f"🔍 Начинаем обработку поста {post_id} с комментарием: {message.text}")

    try:
        revised_text = revise_text_with_chatgpt(raw_text, message.text, post[1])
        logger.info(f"📩 Gemini вернул: {revised_text}")

        conn = sqlite3.connect("news.db", check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute("UPDATE news SET styled_text = ?, status = ? WHERE id = ?", (revised_text, "pending", post_id))
        conn.commit()
        conn.close()

        # Удаляем сообщение о процессе обработки
        await processing_message.delete()

        # Сообщаем, что пост был обработан
        success_message = await message.answer("✅ Пост успешно обработан Gemini. Вот результат:")

        # Удаляем старое сообщение поста, если есть
        post_message_id = data.get('post_message_id')
        if post_message_id:
            try:
                await message.bot.delete_message(chat_id=chat_id, message_id=post_message_id)
            except Exception as e:
                logger.error(f"Не удалось удалить сообщение с постом: {e}")

        # Показываем обновленный пост
        await send_current_post(message.from_user.id, message.bot, chat_id)

        # Удаляем сообщение об успешной обработке
        await asyncio.sleep(1)
        await success_message.delete()

    except Exception as e:
        logger.error(f"❌ Ошибка при обработке поста: {e}")

        # Удаляем сообщение о процессе обработки
        await processing_message.delete()

        # Отправляем сообщение об ошибке с кнопками для дальнейших действий
        error_message = await message.answer(
            f"❌ Произошла ошибка при обработке поста: {e}\n"
            "Хотите попробовать еще раз или вернуться к модерации?",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔄 Попробовать снова", callback_data=f"gemini_{post_id}")],
                [InlineKeyboardButton(text="🔙 Вернуться к модерации", callback_data="continue_session")]
            ])
        )

        # Удаляем сообщение об ошибке через некоторое время
        await asyncio.sleep(5)
        try:
            await error_message.delete()
        except Exception:
            pass

    # В любом случае очищаем состояние
    await state.clear()