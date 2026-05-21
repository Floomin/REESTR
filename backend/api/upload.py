import json
import uuid
from typing import Annotated

import pyodbc
from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from loguru import logger

from backend.core.database import get_db_connection
from backend.services.parser_service import process_json_payload

router = APIRouter(prefix="/api/upload", tags=["Upload"])
DbSession = Annotated[pyodbc.Connection, Depends(get_db_connection)]

@router.post("/json")
async def upload_json_file(
    # Використовуємо Annotated для уникнення помилки B008
    file: Annotated[UploadFile, File(...)],
    db: DbSession = None
):
    """
    Приймає JSON файл з даними ділянок, парсить його та зберігає у БД.
    """
    if not file.filename.endswith('.json'):
        raise HTTPException(status_code=400, detail="Дозволені лише JSON файли")

    try:
        contents = await file.read()
        json_data = json.loads(contents)

        task_id = str(uuid.uuid4())
        logger.info(f"Початок обробки файлу {file.filename} (Task: {task_id})")

        result = process_json_payload(db, task_id, file.filename, json_data)
        return result

    except json.JSONDecodeError as e:
        # Додаємо "from e" для уникнення помилки B904
        raise HTTPException(status_code=400, detail="Невірний формат JSON") from e
    except Exception as e:
        logger.error(f"Помилка завантаження файлу: {e}")
        # Додаємо "from e" для уникнення помилки B904
        raise HTTPException(status_code=500, detail="Внутрішня помилка сервера") from e
