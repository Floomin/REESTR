import logging

from backend.core.utils import safe_bool
from backend.services.mdm_service import apply_mdm_dictionary

logger = logging.getLogger(__name__)


def get_or_create_subject(cursor, subject_data: dict, task_id: str = None) -> int | None:
    """
    Нормализует субъекта через MDM-словарь и сохраняет его в таблицу Subject.
    Если субъект уже существует, возвращает его SubjectId.
    """
    if not subject_data:
        return None

    raw_code = subject_data.get("code")
    raw_name = subject_data.get("name")

    # Пропускаем абсолютно пустые записи, если реестр отдал мусор
    if not raw_code and not raw_name:
        return None

    # 1. Прогоняем через MDM-сервис (ищем в CompanyReference или кидаем в Staging)
    mdm_result = apply_mdm_dictionary(cursor, raw_code, raw_name, task_id)

    final_code = mdm_result["code"]
    final_name = mdm_result["name"]
    is_normalized = 1 if mdm_result["is_normalized"] else 0

    # 2. Проверяем, есть ли уже такой субъект в основной таблице Subject
    # Ищем по коду и имени одновременно, чтобы корректно обрабатывать физлиц (у которых код может быть скрыт/нулевой)
    cursor.execute(
        """
        SELECT SubjectId
        FROM Subject
        WHERE SubjectCode = ? AND SubjectName = ?
    """,
        (final_code, final_name),
    )

    row = cursor.fetchone()
    if row:
        return row[0]  # Субъект уже есть, отдаем его ID

    # 3. Если нет - создаем нового
    query = """
        INSERT INTO Subject (
            SubjectType, SubjectCode, SubjectName, SbjAddType,
            IsLocalGovernment, IsStateAuthority, IsNotResident, Country,
            TaxNumberNonRes, PifName, EdrisiCode, Phone, Email, AddressText, IsNormalized
        )
        OUTPUT INSERTED.SubjectId
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    params = (
        subject_data.get("type"),  # '1' - физлицо, '2' - юрлицо
        final_code,
        final_name,
        subject_data.get("sbjAddType"),
        safe_bool(subject_data.get("isLocalGovernment")),
        safe_bool(subject_data.get("isStateAuthority")),
        safe_bool(subject_data.get("isNotResident")),
        subject_data.get("country"),
        subject_data.get("taxNumberNonRes"),
        subject_data.get("pifName"),
        subject_data.get("edrisiCode"),
        subject_data.get("phone"),
        subject_data.get("email"),
        subject_data.get("address"),
        is_normalized,
    )

    try:
        cursor.execute(query, params)
        new_row = cursor.fetchone()
        return new_row[0] if new_row else None
    except Exception as e:
        logger.error(f"Ошибка при создании субъекта {final_code} - {final_name}: {e}")
        raise
