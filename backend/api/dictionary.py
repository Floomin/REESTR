import json
import os
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from loguru import logger
from pydantic import BaseModel
from pyodbc import Connection

from backend.core.database import get_db_connection

router = APIRouter(prefix="/dictionary", tags=["Dictionary MDM"])

# Папка для тимчасових файлів
UPLOAD_DIR = "temp_uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)


def is_zero_code(code):
    """Перевіряє, чи є код саме '00000000' (або серією нулів)."""
    clean_code = str(code).strip()
    return clean_code in ["00000000", "0000000000", "0"]


def extract_subjects_from_json(json_data):
    """Шукає всі компанії у всіх вузлах JSON."""
    subjects = set()  # Використовуємо set для унікальності (Code, Name)

    for item in json_data:
        plot = item.get("Plot") or {}

        # 1. ДЗК (Власність та Оренда)
        dzk = plot.get("dzkLandInfo") or {}
        for own in dzk.get("OwnershipInfo") or []:
            if isinstance(own, dict) and (own.get("NameUo") or own.get("Edrpou")):
                subjects.add((str(own.get("Edrpou", "")).strip(), str(own.get("NameUo") or own.get("NameFo", "")).strip()))

        for right in dzk.get("SubjectRealRightLand") or []:
            if isinstance(right, dict) and (right.get("NameUo") or right.get("Edrpou")):
                subjects.add((str(right.get("Edrpou", "")).strip(), str(right.get("NameUo") or right.get("NameFo", "")).strip()))

        # 2. ДРРП (Зведена інформація)
        rrp_sum = plot.get("rrpLandInfo") or {}
        for sbj in rrp_sum.get("subject") or []:
            if isinstance(sbj, dict) and (sbj.get("name") or sbj.get("code")):
                subjects.add((str(sbj.get("code", "")).strip(), str(sbj.get("name") or sbj.get("sbjRlName", "")).strip()))

        # 3. ДРРП (Розширена інформація)
        adv = plot.get("RrpAdvanced") or {}
        for realty in adv.get("realty") or []:
            if not isinstance(realty, dict):
                continue

            # Власність, Оренда, Іпотека, Обмеження
            for key in ["properties", "irps", "mortgage", "limitation"]:
                for node in realty.get(key) or []:
                    if not isinstance(node, dict):
                        continue
                    for sbj in node.get("subjects") or []:
                        if isinstance(sbj, dict) and (sbj.get("sbjName") or sbj.get("sbjCode")):
                            subjects.add((str(sbj.get("sbjCode", "")).strip(), str(sbj.get("sbjName") or sbj.get("sbjRlName", "")).strip()))

    return subjects


@router.post("/upload")
async def upload_and_scan(
    file: Annotated[UploadFile, File(...)],
    db: Annotated[Connection, Depends(get_db_connection)]
):
    """Завантажує файл і сканує компанії в тимчасове сховище."""
    task_id = str(uuid.uuid4())
    file_path = os.path.join(UPLOAD_DIR, f"{task_id}.json")

    # 1. Зберігаємо файл на диск
    try:
        content = await file.read()
        with open(file_path, "wb") as f:
            f.write(content)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Помилка збереження файлу: {e}") from e

    cursor = db.cursor()
    try:
        # 2. Читаємо JSON і витягуємо компанії
        with open(file_path, "r", encoding="utf-8") as f:
            json_data = json.load(f)

        all_subjects = extract_subjects_from_json(json_data)

        # 3. Записуємо в Staging, перевіряючи з Reference
        new_count = 0
        for code, name in all_subjects:
            if not name:
                continue

            clean_code = str(code).strip()

            # ІГНОРУЄМО повністю порожні коди (не заносимо їх у словник взагалі)
            if not clean_code or clean_code.lower() in ["none", "null"]:
                continue

            zero_code = 1 if is_zero_code(clean_code) else 0

            # Якщо код нормальний, перевіряємо, чи є він вже в довіднику
            if zero_code == 0:
                cursor.execute("SELECT 1 FROM CompanyReference WHERE Edrpou = ?", (clean_code,))
                if cursor.fetchone():
                    continue  # Пропускаємо, бо вже є в еталонному довіднику

            # Якщо компанії немає в довіднику або це нульовий код - додаємо в чергу
            cursor.execute("""
                INSERT INTO CompanyStaging (TaskId, OriginalCode, OriginalName, IsZeroCode)
                VALUES (?, ?, ?, ?)
            """, (task_id, code, name, zero_code))
            new_count += 1

        db.commit()
        return {"status": "success", "task_id": task_id, "found_new_subjects": new_count}

    except Exception as e:
        db.rollback()
        logger.error(f"Помилка сканування: {e}")
        raise HTTPException(status_code=500, detail="Помилка при скануванні файлу") from e


# --- Моделі для запитів ---

class StandardResolution(BaseModel):
    task_id: str
    original_code: str
    standard_name: str

class ZeroResolution(BaseModel):
    task_id: str
    original_name: str
    new_code: str
    standard_name: str


# --- 1. Черга для стандартних кодів ---

@router.get("/queue/standard/{task_id}")
def get_next_standard(task_id: str, db: Annotated[Connection, Depends(get_db_connection)]):
    """Повертає наступний код з черги разом із усіма варіантами його назв."""
    cursor = db.cursor()

    # Рахуємо скільки унікальних кодів залишилося
    cursor.execute("""
        SELECT COUNT(DISTINCT OriginalCode)
        FROM CompanyStaging
        WHERE TaskId = ? AND IsZeroCode = 0
    """, (task_id,))
    remaining_count = cursor.fetchone()[0]

    # Беремо один унікальний код з черги
    cursor.execute("""
        SELECT TOP 1 OriginalCode
        FROM CompanyStaging
        WHERE TaskId = ? AND IsZeroCode = 0
    """, (task_id,))
    row = cursor.fetchone()

    if not row:
        return {"status": "empty"}

    code = row[0]

    # Збираємо всі криві назви, які були в JSON під цим кодом
    cursor.execute("""
        SELECT DISTINCT OriginalName
        FROM CompanyStaging
        WHERE TaskId = ? AND OriginalCode = ? AND IsZeroCode = 0
    """, (task_id, code))

    variants = [r[0] for r in cursor.fetchall() if r[0]]

    return {
        "status": "ok",
        "code": code,
        "variants": variants,
        "remaining": remaining_count
    }

@router.post("/resolve/standard")
def resolve_standard(data: StandardResolution, db: Annotated[Connection, Depends(get_db_connection)]):
    """Зберігає еталонну назву в довідник і видаляє оброблені записи зі Staging."""
    cursor = db.cursor()
    try:
        # 1. Записуємо в довідник (якщо хтось не додав його паралельно)
        cursor.execute("""
            IF NOT EXISTS (SELECT 1 FROM CompanyReference WHERE Edrpou = ?)
            BEGIN
                INSERT INTO CompanyReference (Edrpou, StandardName)
                VALUES (?, ?)
            END
        """, (data.original_code, data.original_code, data.standard_name))

        # 2. Видаляємо з черги всі записи з цим кодом для цього завдання
        cursor.execute("""
            DELETE FROM CompanyStaging
            WHERE TaskId = ? AND OriginalCode = ? AND IsZeroCode = 0
        """, (data.task_id, data.original_code))

        db.commit()
        return {"status": "success"}
    except Exception as e:
        db.rollback()
        logger.error(f"Помилка збереження стандартного коду: {e}")
        raise HTTPException(status_code=500, detail="Не вдалося зберегти запис") from e


# --- 2. Черга для проблемних кодів (00000000) ---

@router.get("/queue/zero/{task_id}")
def get_next_zero(task_id: str, db: Annotated[Connection, Depends(get_db_connection)]):
    """Повертає наступну назву компанії без коду."""
    cursor = db.cursor()

    # Рахуємо скільки унікальних назв залишилося
    cursor.execute("""
        SELECT COUNT(DISTINCT OriginalName)
        FROM CompanyStaging
        WHERE TaskId = ? AND IsZeroCode = 1
    """, (task_id,))
    remaining_count = cursor.fetchone()[0]

    cursor.execute("""
        SELECT TOP 1 OriginalName
        FROM CompanyStaging
        WHERE TaskId = ? AND IsZeroCode = 1
    """, (task_id,))
    row = cursor.fetchone()

    if not row:
        return {"status": "empty"}

    return {
        "status": "ok",
        "original_name": row[0],
        "remaining": remaining_count
    }

@router.post("/resolve/zero")
def resolve_zero(data: ZeroResolution, db: Annotated[Connection, Depends(get_db_connection)]):
    """
    Зберігає компанію в довідник (якщо коду ще немає),
    пише лог у JsonCorrections для подальшої заміни в файлі,
    і видаляє запис зі Staging.
    """
    cursor = db.cursor()
    try:
        # 1. Перевіряємо, чи є вже такий введений код у довіднику
        cursor.execute("""
            IF NOT EXISTS (SELECT 1 FROM CompanyReference WHERE Edrpou = ?)
            BEGIN
                INSERT INTO CompanyReference (Edrpou, StandardName)
                VALUES (?, ?)
            END
        """, (data.new_code, data.new_code, data.standard_name))

        # 2. Записуємо правило в Журнал виправлень JSON
        cursor.execute("""
            INSERT INTO JsonCorrections (TaskId, OriginalName, NewCode, NewName)
            VALUES (?, ?, ?, ?)
        """, (data.task_id, data.original_name, data.new_code, data.standard_name))

        # 3. Видаляємо оброблений запис з черги
        cursor.execute("""
            DELETE FROM CompanyStaging
            WHERE TaskId = ? AND OriginalName = ? AND IsZeroCode = 1
        """, (data.task_id, data.original_name))

        db.commit()
        return {"status": "success"}
    except Exception as e:
        db.rollback()
        logger.error(f"Помилка збереження нульового коду: {e}")
        raise HTTPException(status_code=500, detail="Не вдалося зберегти запис") from e
