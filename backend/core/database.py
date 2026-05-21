import pyodbc
from loguru import logger

from backend.core.config import settings


def get_db_connection():
    conn = None
    try:
        # Используем наш новый генератор строки подключения
        conn = pyodbc.connect(settings.connection_string)
        yield conn
    except Exception as e:
        logger.error(f"Помилка підключення до БД: {e}")
        raise
    finally:
        if conn:
            conn.close()
