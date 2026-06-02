import logging
from typing import Any, Dict, List

from backend.core.utils import clean_datetime, safe_float
from backend.repositories.mdm_repository import get_or_create_subject

logger = logging.getLogger(__name__)


def process_limitations(cursor, realty_id: int, limitation_data: Any, task_id: str) -> List[Dict[str, Any]]:
    """
    Обрабатывает обременения (аресты, запреты на отчуждение и т.д.).
    Возвращает список документов-оснований для common_repository.
    """
    if not limitation_data:
        return []

    if isinstance(limitation_data, dict):
        limitation_data = [limitation_data]
    if not isinstance(limitation_data, list):
        return []

    documents_to_process = []

    for lm in limitation_data:
        if not isinstance(lm, dict):
            continue

        # Вставляем данные по структуре таблицы RrpLimitation
        query_lm = """
            INSERT INTO RrpLimitation (
                RealtyId, RecordNumber, LmType, LmTypeExtension,
                RegistrationDate, Registrar, LmDescription, ExecTerm,
                ActTermText, ActTerm, ObligationSum, CurrencyType
            )
            OUTPUT INSERTED.LimitationId
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params_lm = (
            realty_id,
            lm.get("rnNum") or lm.get("recordNumber"),
            lm.get("lmType"),
            lm.get("lmTypeExtension"),
            clean_datetime(lm.get("dateRegRight") or lm.get("registrationDate")),
            lm.get("registrar"),
            lm.get("lmDescription") or lm.get("description"),
            lm.get("execTerm"),
            lm.get("actTermText"),
            clean_datetime(lm.get("actTerm")),
            safe_float(lm.get("obligationSum")),
            lm.get("currencyType"),
        )

        try:
            cursor.execute(query_lm, params_lm)
            row = cursor.fetchone()
            if not row:
                continue
            limitation_id = row[0]
        except Exception as e:
            logger.error(f"Ошибка при сохранении RrpLimitation для RealtyId {realty_id}: {e}")
            raise

        # Обрабатываем субъектов (обременитель, лицо, чьи права обременяются)
        sbj_data = lm.get("sbj")
        if isinstance(sbj_data, dict):
            sbj_data = [sbj_data]

        if isinstance(sbj_data, list):
            for sbj in sbj_data:
                if not isinstance(sbj, dict):
                    continue

                subject_id = get_or_create_subject(cursor, sbj, task_id)

                if subject_id:
                    query_link = """
                        INSERT INTO RrpLimitationSubject (LimitationId, SubjectId, SubjectRole)
                        VALUES (?, ?, ?)
                    """
                    cursor.execute(query_link, (limitation_id, subject_id, sbj.get("sbjRole")))

        # Собираем документы
        documents_to_process.append(
            {
                "ParentId": limitation_id,
                "ParentType": "Limitation",
                "Documents": lm.get("cd"),
                "EntityLinks": lm.get("entityLinks"),
            }
        )

    return documents_to_process


def process_mortgages(cursor, realty_id: int, mortgage_data: Any, task_id: str) -> List[Dict[str, Any]]:
    """
    Обрабатывает ипотеки. Ипотека — сложная сущность со своими обязательствами.
    """
    if not mortgage_data:
        return []

    if isinstance(mortgage_data, dict):
        mortgage_data = [mortgage_data]
    if not isinstance(mortgage_data, list):
        return []

    documents_to_process = []

    for mg in mortgage_data:
        if not isinstance(mg, dict):
            continue

        # 1. Инсерт основной записи ипотеки
        query_mg = """
            INSERT INTO RrpMortgage (
                RealtyId, RecordNumber, RegistrationDate, Registrar,
                MgState, ObjectDescription, AdditionalInfo
            )
            OUTPUT INSERTED.MortgageId
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """
        params_mg = (
            realty_id,
            mg.get("rnNum") or mg.get("recordNumber"),
            clean_datetime(mg.get("dateRegRight") or mg.get("registrationDate")),
            mg.get("registrar"),
            mg.get("mgState") or mg.get("prState"),
            mg.get("objectDescription"),
            str(mg.get("additional")) if mg.get("additional") else None,
        )

        try:
            cursor.execute(query_mg, params_mg)
            row = cursor.fetchone()
            if not row:
                continue
            mortgage_id = row[0]
        except Exception as e:
            logger.error(f"Ошибка при сохранении RrpMortgage для RealtyId {realty_id}: {e}")
            raise

        # 2. Обрабатываем субъектов ипотеки (ипотекодатель, ипотекодержатель)
        sbj_data = mg.get("sbj")
        if isinstance(sbj_data, dict):
            sbj_data = [sbj_data]

        if isinstance(sbj_data, list):
            for sbj in sbj_data:
                if not isinstance(sbj, dict):
                    continue

                subject_id = get_or_create_subject(cursor, sbj, task_id)

                if subject_id:
                    query_link = """
                        INSERT INTO RrpMortgageSubject (MortgageId, SubjectId, SubjectRole)
                        VALUES (?, ?, ?)
                    """
                    cursor.execute(query_link, (mortgage_id, subject_id, sbj.get("sbjRole")))

        # 3. Обрабатываем обязательства по ипотеке (RrpMortgageObligation)
        # Обычно это вложенный объект (или массив) 'obligation'
        obl_data = mg.get("obligation")
        if isinstance(obl_data, dict):
            obl_data = [obl_data]

        if isinstance(obl_data, list):
            for obl in obl_data:
                if not isinstance(obl, dict):
                    continue

                query_obl = """
                    INSERT INTO RrpMortgageObligation (
                        MortgageId, ExecTerm, ExecTermText, ObligationSum,
                        ObligationSumText, CurrencyType, CurrencyText
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                """
                cursor.execute(
                    query_obl,
                    (
                        mortgage_id,
                        obl.get("execTerm"),
                        obl.get("execTermText"),
                        str(obl.get("obligationSum")) if obl.get("obligationSum") else None,
                        obl.get("obligationSumText"),
                        obl.get("currencyType"),
                        obl.get("currencyText"),
                    ),
                )

        # 4. Обрабатываем права, на которые распространяется ипотека (RrpMortgagePropertyRight)
        # (Например, в ипотеке находится право аренды, а не само имущество)
        pr_rights_data = mg.get("mortgagePropertyRights") or mg.get("irpRight")
        if isinstance(pr_rights_data, dict):
            pr_rights_data = [pr_rights_data]

        if isinstance(pr_rights_data, list):
            for pr_right in pr_rights_data:
                if not isinstance(pr_right, dict):
                    continue

                query_mpr = """
                    INSERT INTO RrpMortgagePropertyRight (
                        MortgageId, IrpRnNum, IrpSort, PropertyDescription
                    )
                    VALUES (?, ?, ?, ?)
                """
                # Номер права может приходить как int, страхуем через get()
                cursor.execute(
                    query_mpr,
                    (
                        mortgage_id,
                        pr_right.get("irpRnNum") or pr_right.get("rnNum"),
                        pr_right.get("irpSort"),
                        pr_right.get("propertyDescription") or pr_right.get("description"),
                    ),
                )

        # 5. Собираем документы
        documents_to_process.append(
            {
                "ParentId": mortgage_id,
                "ParentType": "Mortgage",
                "Documents": mg.get("cd"),
                "EntityLinks": mg.get("entityLinks"),
            }
        )

    return documents_to_process
