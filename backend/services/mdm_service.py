import logging

logger = logging.getLogger(__name__)


def apply_mdm_dictionary(cursor, original_code: str, original_name: str, task_id: str = None) -> dict:
    """
    Проверяет субъекта по эталонному справочнику CompanyReference.
    Если субъект не найден, добавляет его в очередь CompanyStaging для ручной обработки в UI.

    Возвращает словарь с финальным кодом, названием и статусом нормализации.
    """
    code = str(original_code).strip() if original_code else ""
    name = str(original_name).strip() if original_name else ""

    # Определяем, является ли код "нулевым" (частая проблема в реестрах)
    is_zero_code = 1 if not code or code.lower() in ("0", "00000000", "null", "none", "") else 0

    # ==========================================
    # 1. ПОИСК В ЭТАЛОННОМ СЛОВАРЕ (MDM)
    # ==========================================
    if not is_zero_code:
        cursor.execute(
            """
            SELECT StandardName
            FROM CompanyReference
            WHERE Edrpou = ?
            """,
            (code,),
        )
        row = cursor.fetchone()

        if row:
            # Бинго! Нашли компанию в словаре.
            return {
                "is_normalized": True,
                "code": code,
                "name": row[0],  # Возвращаем чистое эталонное имя
            }

    # ==========================================
    # 2. РЕГИСТРАЦИЯ НЕИЗВЕСТНОЙ КОМПАНИИ (STAGING)
    # ==========================================
    # Если мы дошли сюда, значит компании нет в эталоне или код нулевой.
    try:
        # Проверяем, нет ли уже такого мусора в Staging, чтобы не плодить дубликаты
        cursor.execute(
            """
            SELECT 1
            FROM CompanyStaging
            WHERE OriginalCode = ? AND OriginalName = ?
            """,
            (code, name),
        )
        if not cursor.fetchone():
            # Записываем в очередь для страницы "Словарь" в Streamlit
            cursor.execute(
                """
                INSERT INTO CompanyStaging (TaskId, OriginalCode, OriginalName, IsZeroCode)
                VALUES (?, ?, ?, ?)
                """,
                (task_id, code, name, is_zero_code),
            )
    except Exception as e:
        logger.error(f"Ошибка записи в CompanyStaging для {code} - {name}: {e}")
        # Не кидаем raise (ошибку), чтобы не останавливать парсинг всего файла из-за одной компании очереди

    # Возвращаем сырые данные
    return {"is_normalized": False, "code": code, "name": name}
