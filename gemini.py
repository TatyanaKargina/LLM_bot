# gemini.py

import logging
import google.generativeai as genai
import config

# Настройка логирования с выводом в консоль
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)

logger = logging.getLogger("gemini")

genai.configure(api_key=config.GEMINI_API_KEY)


def revise_text_with_chatgpt(raw_text, comment="", source=""):
    prompt = (
        "Внеси корректировку в текст на основании комментария. CashTaxi заменяй на Таксопарк СВОИ!. Номер телефона всегда заменяй на +7 929 515 80 66. Остальное оставь неизменным.\n\n"
        f"Текст: {raw_text}\n\n"
        f"Комментарий администратора: {comment}\n\n"
        "Выдай итоговый вариант."
    )

    logger.info("📤 Отправляем запрос в Gemini")
    logger.debug(f"🔸 PROMPT:\n{prompt}")

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        response = model.generate_content(prompt)
        logger.info("✅ Ответ получен от Gemini")
        logger.debug(f"🔹 Ответ Gemini:\n{response.text.strip()}")
        return response.text.strip()
    except Exception as e:
        logger.exception("❌ Ошибка при обращении к Gemini API")
        # В случае ошибки возвращаем исходный текст и добавляем информацию об ошибке в лог
        logger.error(f"Детали ошибки: {str(e)}")
        return raw_text