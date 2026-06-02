import logging
from typing import Any, Dict, List

from backend.core.utils import clean_datetime

logger = logging.getLogger(__name__)


def process_cause_documents_and_links(cursor, items_to_process: List[Dict[str, Any]]) -> None:
    """
    Универсальный обработчик документов-оснований (cd) и связей сущностей (entityLinks).
    Принимает список словарей формата:
    [{"ParentId": 123, "ParentType": "PropertyRight", "Documents": [...], "EntityLinks": [...]}]
    """
    if not items_to_process:
        return

    # Запросы подготовлены строго по структуре таблиц из файла БД
    query_cd = """
        INSERT INTO RrpCauseDocument (
            ParentType, ParentId, CdType, CdTypeExtension,
            DocNumber, DocDate, Publisher, ExpirationDate, AdditionalInfo
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    query_link = """
        INSERT INTO RrpEntityLink (
            ParentType, ParentId, RegistryType, RegistryTypeExt,
            RpvnReId, OtherRegNum, LinkPrRnNum, OldRegDate, LinkRegDate
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    for item in items_to_process:
        parent_id = item.get("ParentId")
        parent_type = item.get("ParentType")

        if not parent_id or not parent_type:
            continue

        # ==========================================
        # 1. Обработка документов-оснований (Cause Documents)
        # ==========================================
        documents = item.get("Documents")

        # Предохранитель на случай, если реестр отдаст объект вместо массива
        if isinstance(documents, dict):
            documents = [documents]

        if isinstance(documents, list):
            for doc in documents:
                if not isinstance(doc, dict):
                    continue

                # В реестрах номер документа бывает раскидан по разным ключам
                # Чаще всего это 'enum', 'docNum' или 'cdID'. Собираем безопасный fallback.
                doc_number = doc.get("enum") or doc.get("docNum") or doc.get("cdID")

                params_cd = (
                    parent_type,
                    parent_id,
                    doc.get("cdType"),
                    doc.get("cdTypeExtension"),
                    str(doc_number) if doc_number else None,
                    clean_datetime(doc.get("docDate")),
                    doc.get("publisher"),
                    clean_datetime(doc.get("expirationDate")),
                    str(doc.get("additional")) if doc.get("additional") else None,
                )

                try:
                    cursor.execute(query_cd, params_cd)
                except Exception as e:
                    logger.error(f"Ошибка при сохранении RrpCauseDocument для {parent_type} ID {parent_id}: {e}")
                    raise

        # ==========================================
        # 2. Обработка связей сущностей (Entity Links)
        # ==========================================
        links = item.get("EntityLinks")

        if isinstance(links, dict):
            links = [links]

        if isinstance(links, list):
            for link in links:
                if not isinstance(link, dict):
                    continue

                params_link = (
                    parent_type,
                    parent_id,
                    link.get("registryType"),
                    link.get("registryTypeExt"),
                    str(link.get("rpvnReId")) if link.get("rpvnReId") else None,
                    str(link.get("otherRegNum")) if link.get("otherRegNum") else None,
                    str(link.get("linkPrRnNum")) if link.get("linkPrRnNum") else None,
                    clean_datetime(link.get("oldRegDate")),
                    clean_datetime(link.get("linkRegDate")),
                )

                try:
                    cursor.execute(query_link, params_link)
                except Exception as e:
                    logger.error(f"Ошибка при сохранении RrpEntityLink для {parent_type} ID {parent_id}: {e}")
                    raise
