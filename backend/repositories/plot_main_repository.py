import logging

from backend.core.utils import map_code, safe_bool, safe_float, safe_int, safe_json_string

logger = logging.getLogger(__name__)

# =========================================================================
# СЛОВНИКИ ДЛЯ РОЗШИФРОВКИ КОДІВ З JSON
# =========================================================================

DICT_KATEGORIYA = {
    "1": "Землі сільськогосподарського призначення",
    "2": "Землі житлової та громадської забудови",
    "3": "Землі природно-заповідного та іншого природоохоронного призначення",
    "4": "Землі оздоровчого призначення",
    "5": "Землі рекреаційного призначення",
    "6": "Землі історико-культурного призначення",
    "7": "Землі лісогосподарського призначення",
    "8": "Землі водного фонду",
    "9": "Землі промисловості, транспорту, зв'язку, енергетики, оборони",
    "0": "Не визначено / Без категорії",
}

DICT_TSILOVE = {
    "170": "01.01 — Для ведення товарного сільськогосподарського виробництва",
    "171": "01.02 — Для ведення фермерського господарства",
    "172": "01.03 — Для ведення особистого селянського господарства",
    "173": "01.04 — Для ведення підсобного сільського господарства",
    "174": "01.05 — Для індивідуального садівництва",
    "175": "01.06 — Для колективного садівництва",
    "176": "01.07 — Для городництва",
    "177": "01.08 — Для сінокосіння і випасання худоби",
    "178": "01.09 — Для дослідних і навчальних цілей",
    "110": "02.01 — Для будівництва і обслуговування житлового будинку (присадибна ділянка)",
}

DICT_FORMA_VLASNOSTI = {"0": "Приватна", "1": "Державна", "2": "Комунальна"}

DICT_TIP_PRAVA = {"0": "Немає / Не визначено", "1": "Оренда", "2": "Емфітевзис", "3": "Суперфіцій", "4": "Сервітут"}

DICT_SLOPE_EXPOSITION = {
    "1": "Північ (N)",
    "2": "Північний схід (NE)",
    "3": "Схід (E)",
    "4": "Південний схід (SE)",
    "5": "Південь (S)",
    "6": "Південний захід (SW)",
    "7": "Захід (W)",
    "8": "Північний захід (NW)",
    "9": "Рівнина (немає нахилу)",
}


# =========================================================================
# ОСНОВНА ФУНКЦІЯ ІНСЕРТУ
# =========================================================================


def insert_plot_main_snapshot(cursor, check_id: int, plot_data: dict) -> int | None:
    """
    Зберігає основні дані ділянки у таблицю PlotMainSnapshot.
    Коди автоматично розшифровуються у зрозумілий текст.
    """
    if not plot_data:
        return None

    query = """
        INSERT INTO PlotMainSnapshot (
            CheckId,
            Area, AreaPkku, Koatuu, Kategoriya, TsilovePriznachennya, VidUgiddya, FormaVlasnosti,
            VlasnikiDilyanok, KilkistVlasnikiv, TipPravaKoristuvannya, PravoKoristuvannyaOrendariv, TerminDiyiOrendi,
            SudovikhSprav, SudovikhSpravVidkryto, ObmezhennyaObtyazhennya,
            AgroClimateZone, SoilType, SoilFertility, CropType, CropProductivity, SurfaceAngle, SlopeExposition,
            MaxTemperature, MinTemperature, AvgTemperature, Percipitation, SnowDepth, DroughSeverity, SoilMoisture,
            IsArchive, IsGeomIntersect, IsInSettlementArea, IsInPZFArea, IntersectPZFArea,
            NamePZF, PZFType, PZFLevel, DistanceAto, GeomIntersectAreaSummary, HashCode
        )
        OUTPUT INSERTED.SnapshotId
        VALUES (
            ?,
            ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?,
            ?, ?, ?, ?, ?, ?
        )
    """

    params = (
        check_id,
        # Базові кадастрові дані
        safe_float(plot_data.get("area")),
        safe_float(plot_data.get("areaPkku")),
        plot_data.get("koatuu"),
        map_code(plot_data.get("kategoriya"), DICT_KATEGORIYA),  # <-- Застосовано словник
        map_code(plot_data.get("tsilovePriznachennya"), DICT_TSILOVE),  # <-- Застосовано словник
        plot_data.get("vidUgiddya"),
        map_code(plot_data.get("formaVlasnosti"), DICT_FORMA_VLASNOSTI),  # <-- Застосовано словник
        # Аналітика власників та оренди
        safe_json_string(plot_data.get("vlasnikiDilyanok")),
        safe_int(plot_data.get("kilkistVlasnikiv")),
        map_code(plot_data.get("tipPravaKoristuvannya"), DICT_TIP_PRAVA),  # <-- Застосовано словник
        safe_json_string(plot_data.get("pravoKoristuvannyaOrendariv")),
        plot_data.get("terminDiyiOrendi"),
        # Судові справи та Обтяження
        safe_int(plot_data.get("sudovikhSprav")),
        safe_int(plot_data.get("sudovikhSpravVidkryto")),
        safe_json_string(plot_data.get("obmezhennyaObtyazhennya")),
        # Агро та Клімат
        plot_data.get("agroClimateZone"),
        plot_data.get("soilType"),  # <-- Готово для майбутнього словника
        plot_data.get("soilFertility"),
        plot_data.get("cropType"),
        safe_float(plot_data.get("cropProductivity")),
        safe_float(plot_data.get("surfaceAngle")),
        map_code(plot_data.get("slopeExposition"), DICT_SLOPE_EXPOSITION),  # <-- Застосовано словник
        safe_float(plot_data.get("maxTemperature")),
        safe_float(plot_data.get("minTemperature")),
        safe_float(plot_data.get("avgTemperature")),
        safe_float(plot_data.get("percipitation")),
        safe_float(plot_data.get("snowDepth")),
        plot_data.get("droughSeverity"),
        safe_float(plot_data.get("soilMoisture")),
        # Статуси та Зони
        safe_bool(plot_data.get("Archive")),
        safe_bool(plot_data.get("isGeomIntersect")),
        safe_bool(plot_data.get("isInSettlementArea")),
        safe_bool(plot_data.get("isInPZFArea")),
        safe_float(plot_data.get("intersectPZFArea")),
        plot_data.get("namePZF"),
        plot_data.get("pZFType"),
        plot_data.get("pZFLevel"),
        safe_float(plot_data.get("distanceAto")),
        safe_float(plot_data.get("geomIntersectAreaSummary")),
        plot_data.get("hashCode"),
    )

    try:
        cursor.execute(query, params)
        row = cursor.fetchone()
        return row[0] if row else None
    except Exception as e:
        logger.error(f"Помилка при збереженні PlotMainSnapshot (CheckId: {check_id}): {e}")
        raise
