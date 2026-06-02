import logging

from backend.core.utils import clean_datetime, safe_float, safe_int

logger = logging.getLogger(__name__)


def insert_plot_ngo(cursor, check_id: int, ngo_data: dict) -> int | None:
    """
    Сохраняет данные Нормативной денежной оценки (НГО) в таблицу PlotNgo.
    """
    if not ngo_data:
        return None

    query = """
        INSERT INTO PlotNgo (
            CheckId, Area, DateModify, OwnershipType, Price, PricePerGektar, Purpose, PurposeInt
        )
        OUTPUT INSERTED.NgoId
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    """

    params = (
        check_id,
        safe_float(ngo_data.get("area")),
        clean_datetime(ngo_data.get("dateModify")),
        ngo_data.get("ownershipType"),
        safe_float(ngo_data.get("price")),
        safe_float(ngo_data.get("pricePerGekt")),
        ngo_data.get("purpose"),
        safe_int(ngo_data.get("purposeInt")),
    )

    try:
        cursor.execute(query, params)
        row = cursor.fetchone()
        return row[0] if row else None
    except Exception as e:
        logger.error(f"Ошибка при сохранении PlotNgo (CheckId: {check_id}): {e}")
        raise
