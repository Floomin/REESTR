import logging

from backend.core.utils import safe_float

logger = logging.getLogger(__name__)


def insert_plot_intersections(cursor, check_id: int, intersect_data) -> None:
    """
    Сохраняет данные о пространственных пересечениях участка (plotPlotIntersect)
    в таблицу PlotIntersection.
    """
    if not intersect_data:
        return

    # Если API прислало один объект вместо списка (частый баг подрядчиков), оборачиваем в список
    if isinstance(intersect_data, dict):
        intersect_data = [intersect_data]

    # Защита: если пришел совсем неожиданный тип данных
    if not isinstance(intersect_data, list):
        logger.warning(f"Ожидался список или словарь для пересечений, получено: {type(intersect_data)}")
        return

    query = """
        INSERT INTO PlotIntersection (
            CheckId,
            CadastrIntersect,
            GeomIntersectArea
        )
        VALUES (?, ?, ?)
    """

    for item in intersect_data:
        if not isinstance(item, dict):
            continue

        cadastr_intersect = item.get("cadastrIntersect")
        geom_area = safe_float(item.get("geomIntersectArea"))

        # Пропускаем абсолютно пустые записи, если они вдруг есть
        if not cadastr_intersect and geom_area is None:
            continue

        params = (check_id, cadastr_intersect, geom_area)

        try:
            cursor.execute(query, params)
        except Exception as e:
            logger.error(f"Ошибка при сохранении PlotIntersection (CheckId: {check_id}): {e}")
            raise
