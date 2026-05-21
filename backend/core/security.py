import bcrypt


def get_password_hash(password: str) -> str:
    """Генерує bcrypt хеш із сіллю для заданого пароля."""
    # Кодуємо пароль у байти
    pwd_bytes = password.encode('utf-8')
    # Генеруємо сіль та хешуємо
    salt = bcrypt.gensalt()
    hashed_password = bcrypt.hashpw(pwd_bytes, salt)
    # Повертаємо як рядок для збереження в БД
    return hashed_password.decode('utf-8')

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Перевіряє, чи співпадає введений пароль з хешем із БД."""
    try:
        password_byte_enc = plain_password.encode('utf-8')
        hashed_password_byte_enc = hashed_password.encode('utf-8')
        return bcrypt.checkpw(password_byte_enc, hashed_password_byte_enc)
    except ValueError:
        # Відловлюємо помилку, якщо в БД лежить невалідний хеш (наприклад, старий текст 'hashed_pwd_here')
        return False
