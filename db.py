import sqlite3
import json
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DB_PATH = "news.db"

# Подключение к SQLite
conn = sqlite3.connect(DB_PATH, check_same_thread=False)
cursor = conn.cursor()

# --- Таблица с новостями ---
cursor.execute("""
CREATE TABLE IF NOT EXISTS news (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_id TEXT,
    raw_text TEXT,
    styled_text TEXT,
    status TEXT,
    notified INTEGER DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)
""")

# --- Таблица сессий модерации ---
cursor.execute("""
CREATE TABLE IF NOT EXISTS moderation_session (
    admin_id INTEGER PRIMARY KEY,
    post_ids TEXT,
    current_index INTEGER
)
""")

conn.commit()

# --- Функции для работы с новостями ---

def add_post(source_id, raw_text):
    cursor.execute("""
        INSERT INTO news (source_id, raw_text, styled_text, status)
        VALUES (?, ?, ?, ?)
    """, (source_id, raw_text, raw_text, "new"))
    conn.commit()
    post_id = cursor.lastrowid
    logger.info(f"🆕 Пост {post_id} добавлен из канала {source_id}")
    return post_id


def get_new_posts():
    """Возвращает список ID новых постов"""
    cursor.execute("SELECT id FROM news WHERE status IN ('new', 'pending', 'skipped')")
    return [row[0] for row in cursor.fetchall()]

def set_post_status(post_id, status):
    """Обновляет статус поста"""
    cursor.execute("UPDATE news SET status = ? WHERE id = ?", (status, post_id))
    conn.commit()
    logger.info(f"🔄 Статус поста {post_id} изменен на {status}")

def get_post(post_id):
    """Возвращает пост по ID"""
    cursor.execute("SELECT * FROM news WHERE id = ?", (post_id,))
    post = cursor.fetchone()
    if not post:
        logger.warning(f"⚠️ Пост с ID {post_id} не найден")
    return post

# --- Функции для модерационной сессии ---

def create_session(admin_id, post_ids):
    """Создает или обновляет сессию модерации для админа"""
    post_ids_json = json.dumps(post_ids)
    cursor.execute("""
        INSERT OR REPLACE INTO moderation_session (admin_id, post_ids, current_index)
        VALUES (?, ?, ?)
    """, (admin_id, post_ids_json, 0))
    conn.commit()
    logger.info(f"✅ Создана сессия модерации для админа {admin_id} с {len(post_ids)} постами")

def get_current_post_for_admin(admin_id):
    """Возвращает ID текущего поста из сессии"""
    cursor.execute("SELECT post_ids, current_index FROM moderation_session WHERE admin_id = ?", (admin_id,))
    row = cursor.fetchone()
    if not row:
        return None
    post_ids, index = json.loads(row[0]), row[1]
    if index >= len(post_ids):
        return None
    return post_ids[index]

def advance_session(admin_id):
    """Переходит к следующему посту"""
    cursor.execute("UPDATE moderation_session SET current_index = current_index + 1 WHERE admin_id = ?", (admin_id,))
    conn.commit()
    logger.info(f"➡️ Сессия админа {admin_id} перешла к следующему посту")

def end_session(admin_id):
    """Завершает сессию"""
    cursor.execute("DELETE FROM moderation_session WHERE admin_id = ?", (admin_id,))
    conn.commit()
    logger.info(f"🏁 Сессия модерации админа {admin_id} завершена")

def get_session_index(admin_id):
    """Возвращает текущий индекс поста в сессии"""
    cursor.execute("SELECT current_index FROM moderation_session WHERE admin_id = ?", (admin_id,))
    row = cursor.fetchone()
    return row[0] if row else 0

def get_session_total(admin_id):
    """Возвращает общее количество постов в сессии"""
    cursor.execute("SELECT post_ids FROM moderation_session WHERE admin_id = ?", (admin_id,))
    row = cursor.fetchone()
    return len(json.loads(row[0])) if row else 0

def get_unnotified_posts():
    cursor.execute("SELECT id FROM news WHERE notified = 0 AND status = 'new'")
    posts = [row[0] for row in cursor.fetchall()]
    if posts:
        logger.info(f"🔔 Найдено {len(posts)} непрочитанных постов")
    return posts

def mark_posts_notified(post_ids):
    if post_ids:
        cursor.executemany("UPDATE news SET notified = 1 WHERE id = ?", [(pid,) for pid in post_ids])
        conn.commit()
        logger.info(f"✅ Отмечено {len(post_ids)} постов как прочитанные")