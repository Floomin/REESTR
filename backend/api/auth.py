from typing import Annotated

import pyodbc
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger
from pydantic import BaseModel

from backend.core.database import get_db_connection

# ІМПОРТУЄМО нашу функцію перевірки
from backend.core.security import verify_password

router = APIRouter(prefix="/api/auth", tags=["Auth"])
DbSession = Annotated[pyodbc.Connection, Depends(get_db_connection)]

class LoginRequest(BaseModel):
    login: str
    password: str

@router.post("/login")
def login(req: LoginRequest, db: DbSession):
    cursor = db.cursor()

    cursor.execute("""
        SELECT UserId, PasswordHash, FullName, Role, IsActive
        FROM AppUser
        WHERE Login = ?
    """, (req.login,))

    user = cursor.fetchone()

    if not user:
        raise HTTPException(status_code=401, detail="Невірний логін або пароль")

    user_id, password_hash, full_name, role, is_active = user

    if not is_active:
        raise HTTPException(status_code=403, detail="Ваш акаунт заблоковано")

    # СЬОГОДНІШНЯ МАГІЯ: Справжня перевірка хешу
    if not verify_password(req.password, password_hash):
        # Відповідь завжди однакова для логіну та паролю, щоб зловмисник не знав, де саме помилився
        raise HTTPException(status_code=401, detail="Невірний логін або пароль")

    try:
        cursor.execute("""
            INSERT INTO UserActionLog (UserId, ActionType, ActionDetails)
            VALUES (?, 'LOGIN', 'Успішний вхід в систему')
        """, (user_id,))
        db.commit()
    except Exception as e:
        db.rollback()
        logger.error(f"Помилка логування входу: {e}")

    return {
        "status": "success",
        "user_id": user_id,
        "full_name": full_name,
        "role": role
    }
