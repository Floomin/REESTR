import logging

from backend.core.utils import clean_datetime, safe_bool, safe_float

logger = logging.getLogger(__name__)


def insert_plot_rrp_summary(cursor, check_id: int, rrp_data: dict) -> None:
    """
    Сохраняет сводные (контрольные) данные из Реестра вещных прав (Plot.rrpLandInfo)
    и связанного объекта аренды (Plot.rrpLandInfo.rent).
    """
    if not rrp_data:
        return

    # Безопасно извлекаем объект rent (если его нет, будет пустой словарь)
    rent_data = rrp_data.get("rent") or {}

    query = """
        INSERT INTO PlotRrpSummary (
            CheckId, Purpose, Area,
            IrpsRegDate, LimitationRegDate, MortgageRegDate,
            IrpsEndDate, LimitationEndDate, MortgageEndDate,
            RentStartDate, RentEndDate, RentActTermText,
            RentIsWithPermanent, RentIsWithSubRent, RentSum
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """

    params = (
        check_id,
        rrp_data.get("purpose"),
        safe_float(rrp_data.get("area")),
        # Даты регистрации
        clean_datetime(rrp_data.get("irpsRegDate")),
        clean_datetime(rrp_data.get("limitationRegDate")),
        clean_datetime(rrp_data.get("mortgageRegDate")),
        # Даты окончания
        clean_datetime(rrp_data.get("irpsEndDate")),
        clean_datetime(rrp_data.get("limitationEndDate")),
        clean_datetime(rrp_data.get("mortgageEndDate")),
        # Блок Rent (Оренда)
        clean_datetime(rent_data.get("startDate")),
        clean_datetime(rent_data.get("endDate")),
        rent_data.get("actTermText"),
        safe_bool(rent_data.get("isWithPermanent")),
        safe_bool(rent_data.get("isWithSubRent")),
        safe_float(rent_data.get("sumRent")),
    )

    try:
        cursor.execute(query, params)
    except Exception as e:
        logger.error(f"Ошибка при сохранении PlotRrpSummary (CheckId: {check_id}): {e}")
        raise
