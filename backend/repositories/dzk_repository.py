import json

from backend.repositories.subject_repository import get_or_create_subject


def _safe_str(value):
    """Безопасная конвертация словарей/массивов в строку (на случай аномалий в JSON)"""
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return value


def _safe_date(value):
    """Безопасная обработка дат: фильтрует пустые строки и приводит DD.MM.YYYY к YYYY-MM-DD"""
    if not value:
        return None

    val_str = str(value).strip()

    if not val_str or val_str.lower() in ("null", "none"):
        return None

    # Если дата пришла в формате ДД.ММ.РРРР (например: 24.11.2021)
    if len(val_str) >= 10 and val_str[2] == "." and val_str[5] == ".":
        try:
            return f"{val_str[6:10]}-{val_str[3:5]}-{val_str[0:2]}"
        except Exception:
            pass

    return val_str

def extract_clean_address(address_field):
    """
    Разбирает вложенные структуры адреса из JSON (списки, словари)
    и возвращает чистый склеенный текст.
    """
    if not address_field:
        return None

    # Если из JSON пришла обычная строка — просто отдаем её
    if isinstance(address_field, str):
        return address_field.strip()

    # Если пришел список словарей (наш случай: [{'addressDetail': 'Вінницька обл.'}])
    if isinstance(address_field, list):
        parts = []
        for item in address_field:
            if isinstance(item, dict):
                # Вытаскиваем все текстовые значения (игнорируя пустые)
                for val in item.values():
                    if val and isinstance(val, str):
                        parts.append(val.strip())
            elif isinstance(item, str):
                parts.append(item.strip())

        return ", ".join(parts) if parts else None

    return str(address_field)

def process_dzk(cursor, check_id, cadastral_number, dzk_data):
    """
    Полный парсинг и сохранение данных ДЗК (dzkLandInfo)
    """
    if not dzk_data:
        return

    reg_val_data = dzk_data.get("RegulatoryMonetaryValuation")
    reg_val = None

    if isinstance(reg_val_data, dict):
        reg_val = reg_val_data.get("ValueUah")
    elif not isinstance(reg_val_data, list):
        # Про всяк випадок, якщо колись прийде просто число
        reg_val = reg_val_data
    # ----------------------------------

    # 1. Базовый срез ДЗК
    cursor.execute(
        """
        INSERT INTO PlotDzkSnapshot (
            CheckId, CadastralNumber, RegistrationDate, Area,
            Purpose, Category, Location, KategoriaZemli, RegulatoryMonetaryValuation
        ) OUTPUT INSERTED.DzkSnapshotId
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        (
            check_id,
            cadastral_number,
            _safe_date(dzk_data.get("UpdateDate")),
            dzk_data.get("LandAreaNum"),
            _safe_str(dzk_data.get("Purpose")),
            _safe_str(dzk_data.get("Category")),
            extract_clean_address(dzk_data.get("Location")),
            _safe_str(dzk_data.get("kategoriaZemli")),
            reg_val
        ),
    )
    dzk_snapshot_id = cursor.fetchone()[0]

    # 2. Документи ДЗК
    for doc in dzk_data.get("DocInfoList") or []:
        if not isinstance(doc, dict):
            continue  # Захист від строк
        cursor.execute(
            """
            INSERT INTO PlotDzkDocuments (DzkSnapshotId, DocType, DocNumber, DocDate)
            VALUES (?, ?, ?, ?)
        """,
            (
                dzk_snapshot_id,
                _safe_str(doc.get("DocType")),
                _safe_str(doc.get("DocNumber")),
                _safe_date(doc.get("DocDate")),
            ),
        )

    # 3. Право власності ДЗК
    for own in dzk_data.get("OwnershipInfo") or []:
        if not isinstance(own, dict):
            continue  # Захист
        name = own.get("NameUo") or own.get("NameFo") or "Не вказано"
        code = own.get("Edrpou")
        sbj_type = "2" if own.get("NameUo") else "1"

        subj_id = get_or_create_subject(cursor, code, name, sbj_type)

        cursor.execute(
            """
            INSERT INTO PlotDzkOwnership (
                DzkSnapshotId, SubjectId, OwnershipType, NameFo, NameUo,
                Edrpou, DateRegRight, EntryRecordNumber, RegAuthority, Description
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                dzk_snapshot_id,
                subj_id,
                _safe_str(own.get("OwnershipType")),
                _safe_str(own.get("NameFo")),
                _safe_str(own.get("NameUo")),
                _safe_str(own.get("Edrpou")),
                _safe_date(own.get("DateRegRight")),
                _safe_str(own.get("EntryRecordNumber")),
                _safe_str(own.get("RegAuthority")),
                _safe_str(own.get("Description")),
            ),
        )

    # 4. Речові права / Оренда ДЗК
    for right in dzk_data.get("SubjectRealRightLand") or []:
        if not isinstance(right, dict):
            continue  # Захист
        name = right.get("NameUo") or right.get("NameFo") or "Не вказано"
        code = right.get("Edrpou")
        sbj_type = "2" if right.get("NameUo") else "1"

        subj_id = get_or_create_subject(cursor, code, name, sbj_type)

        cursor.execute(
            """
            INSERT INTO PlotDzkSubjectRealRights (
                DzkSnapshotId, SubjectId, PropertyRight, NameFo, NameUo,
                Edrpou, DateRegRight, EntryRecordNumber, RegAuthority
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                dzk_snapshot_id,
                subj_id,
                _safe_str(right.get("PropertyRight")),
                _safe_str(right.get("NameFo")),
                _safe_str(right.get("NameUo")),
                _safe_str(right.get("Edrpou")),
                _safe_date(right.get("DateRegRight")),
                _safe_str(right.get("EntryRecordNumber")),
                _safe_str(right.get("RegAuthority")),
            ),
        )

    # 5. Обмеження ДЗК (Гнучка обробка)
    restriction_data = dzk_data.get("RestrictionInfo")

    if isinstance(restriction_data, str):
        # Якщо прийшла просто строка
        cursor.execute(
            """
            INSERT INTO PlotDzkRestrictions (DzkSnapshotId, Description) VALUES (?, ?)
        """,
            (dzk_snapshot_id, _safe_str(restriction_data)),
        )

    elif isinstance(restriction_data, list):
        # Якщо прийшов нормальний масив
        for rest in restriction_data:
            if not isinstance(rest, dict):
                continue
            cursor.execute(
                """
                INSERT INTO PlotDzkRestrictions (
                    DzkSnapshotId, RestrictionType, RestrictionCode, RegistrationDate, Description
                ) VALUES (?, ?, ?, ?, ?)
            """,
                (
                    dzk_snapshot_id,
                    _safe_str(rest.get("RestrictionType")),
                    _safe_str(rest.get("RestrictionCode")),
                    _safe_date(rest.get("RegistrationDate")),
                    _safe_str(rest.get("Description")),
                ),
            )
