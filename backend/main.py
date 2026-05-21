import pyodbc
from fastapi import Depends, FastAPI
from loguru import logger

from backend.api import upload
from backend.core.database import get_db_connection

# Инициализация приложения
app = FastAPI(
    title="Державні Реєстри API",
    description="API для управління земельним банком",
    version="1.0.0"
)

# Настройка Loguru
logger.add("data/api_errors.log", rotation="10 MB", level="ERROR")

app.include_router(upload.router)

@app.get("/")
def read_root():
    return {"message": "Сервер Державні Реєстри успішно запущено!"}

@app.get("/health")
def health_check(db: pyodbc.Connection = Depends(get_db_connection)):  # noqa: B008
    """Проверка подключения к базе данных"""
    cursor = db.cursor()
    cursor.execute("SELECT 1")
    return {"status": "ok", "database": "connected"}
