import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class RrpRealtyRepository:
    @staticmethod
    def save_realty_snapshot(cursor, check_id: int, realty_data: Dict[str, Any]) -> Optional[int]:
        """
        Сохраняет базовую информацию об объекте недвижимости (RrpRealtySnapshot).
        Возвращает сгенерированный RealtyId.
        """
        if not realty_data:
            return None

        # Предохранители: API может вернуть числа как строки или наоборот
        area_sq_m = float(realty_data.get("AreaSqM")) if realty_data.get("AreaSqM") else None
        living_area_sq_m = float(realty_data.get("LivingAreaSqM")) if realty_data.get("LivingAreaSqM") else None
        readiness_percent = float(realty_data.get("ReadinessPercent")) if realty_data.get("ReadinessPercent") else None

        query = """
            INSERT INTO RrpRealtySnapshot (
                CheckId, RegistrationNumber, RegistrationDate, ReType, ReTypeExtension,
                ReSubType, ReSubTypeExtension, IsResidentialBuilding, ReState, SectionType,
                Region, TechDescription, AreaSqM, LivingAreaSqM, ReadinessPercent,
                EdessbIdentifier, AdditionalInfo, RootSbjName, RootSbjRegDate, RootSbjCode,
                EntityLinkRpvnReID, EntityLinkRegDate, EntityLinkRegistryType, RealtyPartsRaw
            )
            OUTPUT INSERTED.RealtyId
            VALUES (
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?, ?,
                ?, ?, ?, ?
            )
        """

        params = (
            check_id,
            realty_data.get("RegistrationNumber"),
            realty_data.get("RegistrationDate"),  # Убедись, что дата в формате, понятном SQL Server (YYYY-MM-DD)
            realty_data.get("ReType"),
            realty_data.get("ReTypeExtension"),
            realty_data.get("ReSubType"),
            realty_data.get("ReSubTypeExtension"),
            bool(realty_data.get("IsResidentialBuilding")),
            realty_data.get("ReState"),
            realty_data.get("SectionType"),
            realty_data.get("Region"),
            realty_data.get("TechDescription"),
            area_sq_m,
            living_area_sq_m,
            readiness_percent,
            realty_data.get("EdessbIdentifier"),
            realty_data.get("AdditionalInfo"),
            realty_data.get("RootSbjName"),
            realty_data.get("RootSbjRegDate"),
            realty_data.get("RootSbjCode"),
            realty_data.get("EntityLinkRpvnReID"),
            realty_data.get("EntityLinkRegDate"),
            realty_data.get("EntityLinkRegistryType"),
            # Если RealtyPartsRaw - это вложенный JSON, сериализуем его в строку
            str(realty_data.get("RealtyPartsRaw")) if realty_data.get("RealtyPartsRaw") else None,
        )

        try:
            cursor.execute(query, params)
            result = cursor.fetchone()
            return result[0] if result else None
        except Exception as e:
            logger.error(f"Ошибка при сохранении RrpRealtySnapshot: {e}. Data: {realty_data.get('RegistrationNumber')}")
            raise

    @staticmethod
    def save_realty_address(cursor, realty_id: int, address_data: Dict[str, Any]) -> None:
        """Сохраняет детализированный адрес объекта."""
        if not address_data:
            return

        query = """
            INSERT INTO RrpRealtyAddress (
                RealtyId, AddressDetail, RegionName, RegionId, DistrictName, DistrictId,
                CityName, CityId, ObjectName, ObjectId, StreetName, StreetId,
                DcHouseType, House, DcBuildingType, Building, DcObjectNumType,
                ObjectNum, DcRoomType, Room, Koatuu
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        params = (
            realty_id,
            address_data.get("AddressDetail"),
            address_data.get("RegionName"),
            address_data.get("RegionId"),
            address_data.get("DistrictName"),
            address_data.get("DistrictId"),
            address_data.get("CityName"),
            address_data.get("CityId"),
            address_data.get("ObjectName"),
            address_data.get("ObjectId"),
            address_data.get("StreetName"),
            address_data.get("StreetId"),
            address_data.get("DcHouseType"),
            address_data.get("House"),
            address_data.get("DcBuildingType"),
            address_data.get("Building"),
            address_data.get("DcObjectNumType"),
            address_data.get("ObjectNum"),
            address_data.get("DcRoomType"),
            address_data.get("Room"),
            address_data.get("Koatuu"),
        )
        cursor.execute(query, params)

    @staticmethod
    def process_realty_ground_areas(cursor, realty_id: int, ground_areas: Any) -> None:
        """
        Обрабатывает земельные участки, привязанные к объекту недвижимости.
        Учитывает, что API может вернуть один объект вместо списка.
        """
        if not ground_areas:
            return

        # Предохранитель: если прилетел dict вместо list
        if isinstance(ground_areas, dict):
            ground_areas = [ground_areas]
        elif not isinstance(ground_areas, list):
            logger.warning(f"Неожиданный тип данных для ground_areas: {type(ground_areas)}. RealtyId: {realty_id}")
            return

        query = """
            INSERT INTO RrpRealtyGroundArea (
                RealtyId, CadastralNumber, MelNetworkNum, Area, AreaUM,
                RegDateSlc, TargetPurpose, RegOrganization, RegNums, HoldingsRaw
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        for ga in ground_areas:
            if not isinstance(ga, dict):
                continue

            area_val = float(ga.get("Area")) if ga.get("Area") else None

            params = (
                realty_id,
                ga.get("CadastralNumber"),
                ga.get("MelNetworkNum"),
                area_val,
                ga.get("AreaUM"),
                ga.get("RegDateSlc"),
                ga.get("TargetPurpose"),
                ga.get("RegOrganization"),
                ga.get("RegNums"),
                str(ga.get("HoldingsRaw")) if ga.get("HoldingsRaw") else None,
            )
            cursor.execute(query, params)
