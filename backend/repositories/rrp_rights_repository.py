import logging
from typing import Any, Dict, List

from backend.core.utils import clean_datetime, safe_bool
from backend.repositories.mdm_repository import get_or_create_subject

logger = logging.getLogger(__name__)


def process_property_rights(cursor, realty_id: int, prp_data: Any, task_id: str) -> List[Dict[str, Any]]:
    """
    Обрабатывает права собственности (prp).
    Возвращает список словарей с документами и линками для последующей обработки в common_repository.
    """
    if not prp_data:
        return []

    if isinstance(prp_data, dict):
        prp_data = [prp_data]
    if not isinstance(prp_data, list):
        return []

    documents_to_process = []

    for pr in prp_data:
        if not isinstance(pr, dict):
            continue

        # Вставляем данные строго по структуре таблицы RrpPropertyRight
        query_pr = """
            INSERT INTO RrpPropertyRight (
                RealtyId, RecordNumber, RightKind, RegistrationDate,
                PrState, Registrar, CommonKind, IsCommonProperty,
                PartSize, PrModeBit, ModeAdditionalInfo, AdditionalInfo
            )
            OUTPUT INSERTED.PropertyRightId
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params_pr = (
            realty_id,
            pr.get("rnNum") or pr.get("recordNumber"),  # В JSON обычно rnNum
            pr.get("prKind"),  # В БД это RightKind
            clean_datetime(pr.get("dateRegRight") or pr.get("registrationDate")),
            pr.get("prState"),
            pr.get("registrar"),
            pr.get("prCommonKind") or pr.get("commonKind"),
            safe_bool(pr.get("isCommonProperty")),
            str(pr.get("partSize")) if pr.get("partSize") else None,
            pr.get("prModeBit"),
            pr.get("modeAdditionalInfo"),
            str(pr.get("additional")) if pr.get("additional") else None,
        )

        try:
            cursor.execute(query_pr, params_pr)
            row = cursor.fetchone()
            if not row:
                continue
            property_right_id = row[0]
        except Exception as e:
            logger.error(f"Ошибка при сохранении RrpPropertyRight для RealtyId {realty_id}: {e}")
            raise

        # Обрабатываем субъектов права (владельцев)
        sbj_data = pr.get("sbj")
        if isinstance(sbj_data, dict):
            sbj_data = [sbj_data]

        if isinstance(sbj_data, list):
            for sbj in sbj_data:
                if not isinstance(sbj, dict):
                    continue

                subject_id = get_or_create_subject(cursor, sbj, task_id)

                if subject_id:
                    # Вставляем связку в RrpPropertyRightSubject
                    query_link = """
                        INSERT INTO RrpPropertyRightSubject (PropertyRightId, SubjectId, SubjectRole)
                        VALUES (?, ?, ?)
                    """
                    cursor.execute(query_link, (property_right_id, subject_id, sbj.get("sbjRole")))

        # Сохраняем "хвосты" (документы и линки) для обработки в common репозитории
        documents_to_process.append(
            {
                "ParentId": property_right_id,
                "ParentType": "PropertyRight",
                "Documents": pr.get("cd"),
                "EntityLinks": pr.get("entityLinks"),
            }
        )

    return documents_to_process


def process_other_property_rights(cursor, realty_id: int, irp_data: Any, task_id: str) -> List[Dict[str, Any]]:
    """
    Обрабатывает иные вещные права (irp - оренда, емфітевзис тощо).
    """
    if not irp_data:
        return []

    if isinstance(irp_data, dict):
        irp_data = [irp_data]
    if not isinstance(irp_data, list):
        return []

    documents_to_process = []

    for irp in irp_data:
        if not isinstance(irp, dict):
            continue

        # Извлекаем блок аренды, если он есть
        rent_data = irp.get("rent") or {}
        if not isinstance(rent_data, dict):
            rent_data = {}

        # Вставляем данные строго по структуре таблицы RrpOtherPropertyRight
        query_irp = """
            INSERT INTO RrpOtherPropertyRight (
                RealtyId, RecordNumber, RegistrationDate, Registrar,
                IrpSort, IrpSortExtension, IrpDescription, ObjectDescription,
                IrpSpread, ActTermText, ActTerm, IsIndefinitely,
                IsAutomaticProlongation, CalculatedStartDate, CalculatedEndDate
            )
            OUTPUT INSERTED.IrpId
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params_irp = (
            realty_id,
            irp.get("rnNum") or irp.get("recordNumber"),
            clean_datetime(irp.get("dateRegRight") or irp.get("registrationDate")),
            irp.get("registrar"),
            irp.get("prKind") or irp.get("irpSort"),  # В БД колонка называется IrpSort
            irp.get("irpSortExtension"),
            irp.get("irpDescription") or irp.get("description"),
            irp.get("objectDescription"),
            irp.get("irpSpread"),
            irp.get("actTermText") or rent_data.get("actTermText"),
            clean_datetime(irp.get("actTerm")),
            safe_bool(irp.get("isIndefinitely")),
            safe_bool(irp.get("isAutomaticProlongation")),
            clean_datetime(rent_data.get("startDate") or irp.get("calculatedStartDate")),  # Маппим даты аренды
            clean_datetime(rent_data.get("endDate") or irp.get("calculatedEndDate")),
        )

        try:
            cursor.execute(query_irp, params_irp)
            row = cursor.fetchone()
            if not row:
                continue
            irp_id = row[0]
        except Exception as e:
            logger.error(f"Ошибка при сохранении RrpOtherPropertyRight для RealtyId {realty_id}: {e}")
            raise

        # Обрабатываем субъектов (арендаторов / орендодавців)
        sbj_data = irp.get("sbj")
        if isinstance(sbj_data, dict):
            sbj_data = [sbj_data]

        if isinstance(sbj_data, list):
            for sbj in sbj_data:
                if not isinstance(sbj, dict):
                    continue

                subject_id = get_or_create_subject(cursor, sbj, task_id)

                if subject_id:
                    # Вставляем связку в RrpOtherPropertyRightSubject
                    query_link = """
                        INSERT INTO RrpOtherPropertyRightSubject (IrpId, SubjectId, SubjectRole)
                        VALUES (?, ?, ?)
                    """
                    cursor.execute(query_link, (irp_id, subject_id, sbj.get("sbjRole")))

        # Собираем документы
        documents_to_process.append(
            {
                "ParentId": irp_id,
                "ParentType": "OtherPropertyRight",
                "Documents": irp.get("cd"),
                "EntityLinks": irp.get("entityLinks"),
            }
        )

    return documents_to_process
