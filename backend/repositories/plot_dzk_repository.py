import logging

from backend.core.utils import clean_datetime, safe_float

logger = logging.getLogger(__name__)


def insert_plot_dzk_info(cursor, check_id: int, dzk_data: dict) -> None:
    """
    Сохраняет кадастровую выписку ДЗК (Plot.dzkLandInfo) и связанные массивы субъектов.
    """
    if not dzk_data:
        return

    # 1. Сохраняем "шапку" (основную информацию из ДЗК)
    query_info = """
        INSERT INTO PlotDzkInfo (
            CheckId, UpdateDate, Purpose, LandArea, LandAreaNum,
            Location, KategoriaZemli, VidUgiddya, RegulatoryMonetaryValuation
        )
        OUTPUT INSERTED.DzkInfoId
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    params_info = (
        check_id,
        clean_datetime(dzk_data.get("UpdateDate")),
        dzk_data.get("Purpose") or dzk_data.get("purposeOriginal"),
        dzk_data.get("LandArea"),
        safe_float(dzk_data.get("LandAreaNum")),
        dzk_data.get("Location"),
        dzk_data.get("kategoriaZemli"),
        dzk_data.get("vidUgiddya"),
        safe_float(dzk_data.get("RegulatoryMonetaryValuation")),
    )

    try:
        cursor.execute(query_info, params_info)
        row = cursor.fetchone()

        if not row:
            return  # Если не удалось получить ID, прерываем обработку

        dzk_info_id = row[0]

        # 2. Сохраняем владельцев (OwnershipInfo)
        owners = dzk_data.get("OwnershipInfo")
        if owners:
            _insert_dzk_subjects(cursor, dzk_info_id, owners, "Ownership")

        # 3. Сохраняем арендаторов и прочие вещные права (SubjectRealRightLand)
        renters = dzk_data.get("SubjectRealRightLand")
        if renters:
            _insert_dzk_subjects(cursor, dzk_info_id, renters, "RealRight")

    except Exception as e:
        logger.error(f"Ошибка при сохранении PlotDzkInfo (CheckId: {check_id}): {e}")
        raise


def _insert_dzk_subjects(cursor, dzk_info_id: int, subjects_data: list, right_group: str) -> None:
    """
    Внутренняя функция для сохранения субъектов ДЗК (владельцев или арендаторов).
    """
    # Защита на случай, если подрядчик прислал объект вместо списка
    if isinstance(subjects_data, dict):
        subjects_data = [subjects_data]

    if not isinstance(subjects_data, list):
        return

    query = """
        INSERT INTO PlotDzkSubject (
            DzkInfoId, RightGroup, PropertyRight, NameFo, NameUo,
            Edrpou, DateRegRight, EntryRecordNumber, RegAuthority, AreaCoveredSublease
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    for item in subjects_data:
        if not isinstance(item, dict):
            continue

        params = (
            dzk_info_id,
            right_group,  # Флаг: 'Ownership' или 'RealRight'
            item.get("PropertyRight"),
            item.get("NameFo"),
            item.get("NameUo"),
            item.get("Edrpou"),
            item.get("DateRegRight"),  # Оставляем строкой, так как ДЗК часто шлет "31.07.2017"
            item.get("EntryRecordNumber"),
            item.get("RegAuthority"),
            safe_float(item.get("AreaCoveredSublease")),
        )

        try:
            cursor.execute(query, params)
        except Exception as e:
            logger.error(f"Ошибка при сохранении PlotDzkSubject (DzkInfoId: {dzk_info_id}): {e}")
            raise
