def apply_mdm_dictionary(cursor, code, name):
    """Проганяє код і назву через еталонні довідники та повертає очищені значення."""
    clean_code = str(code).strip() if code and str(code).strip() not in ["None", "null"] else None
    safe_name = str(name).strip() if name and str(name).strip() not in ["None", "null"] else "Не вказано"

    # 1. Шукаємо в Журналі виправлень (для нульових або відсутніх кодів)
    if not clean_code or clean_code in ["0", "00000000", "0000000000"]:
        cursor.execute(
            """
            SELECT TOP 1 NewCode, NewName
            FROM JsonCorrections
            WHERE OriginalName = ?
            ORDER BY CorrectionId DESC
        """,
            (safe_name,),
        )
        correction = cursor.fetchone()
        if correction:
            clean_code = correction[0]
            safe_name = correction[1]

    # 2. Шукаємо еталонну назву в CompanyReference (якщо код є і він валідний)
    if clean_code and clean_code not in ["0", "00000000", "0000000000"]:
        cursor.execute(
            """
            SELECT StandardName
            FROM CompanyReference
            WHERE Edrpou = ?
        """,
            (clean_code,),
        )
        reference = cursor.fetchone()
        if reference:
            safe_name = reference[0]

    return clean_code, safe_name


def get_or_create_subject(cursor, code, name, subject_type):
    # Очищаємо дані перед будь-якими діями
    clean_code, safe_name = apply_mdm_dictionary(cursor, code, name)

    if clean_code:
        # Ищем по коду (самый надежный вариант)
        cursor.execute(
            """
            SELECT SubjectId FROM Subject WHERE SubjectCode = ?
        """,
            (clean_code,),
        )
    else:
        # Если кода нет, пытаемся найти по точному совпадению имени
        cursor.execute(
            """
            SELECT SubjectId FROM Subject WHERE SubjectName = ? AND SubjectCode IS NULL
        """,
            (safe_name,),
        )

    row = cursor.fetchone()

    # Если субъект найден — возвращаем его ID
    if row:
        return row[0]

    # Если не найден — создаем нового с еталонними даними
    cursor.execute(
        """
        INSERT INTO Subject (SubjectCode, SubjectName, SubjectType)
        OUTPUT INSERTED.SubjectId
        VALUES (?, ?, ?)
    """,
        (clean_code, safe_name, subject_type),
    )

    return cursor.fetchone()[0]
