def get_or_create_subject(cursor, code, name, subject_type):
    # Если имя не передано, ставим заглушку, чтобы SQL не ругался на NOT NULL
    safe_name = name if name else "Не вказано"

    if code:
        # Ищем по коду (самый надежный вариант)
        cursor.execute(
            """
            SELECT SubjectId
            FROM Subject
            WHERE SubjectCode = ?
        """,
            code,
        )
    else:
        # Если кода нет, пытаемся найти по точному совпадению имени
        cursor.execute(
            """
            SELECT SubjectId
            FROM Subject
            WHERE SubjectName = ? AND SubjectCode IS NULL
        """,
            safe_name,
        )

    row = cursor.fetchone()

    # Если субъект найден — возвращаем его ID
    if row:
        return row[0]

    # Если не найден — создаем нового
    cursor.execute(
        """
        INSERT INTO Subject (
            SubjectCode,
            SubjectName,
            SubjectType
        )
        OUTPUT INSERTED.SubjectId
        VALUES (?, ?, ?)
    """,
        code,
        safe_name,
        subject_type,
    )

    return cursor.fetchone()[0]
