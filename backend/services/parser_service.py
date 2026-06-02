import json
import logging

from backend.repositories.plot_dzk_repository import insert_plot_dzk_info
from backend.repositories.plot_intersection_repository import insert_plot_intersections
from backend.repositories.plot_main_repository import insert_plot_main_snapshot
from backend.repositories.plot_ngo_repository import insert_plot_ngo

# Импортируем наши "детали конструктора" для блока Plot
from backend.repositories.plot_repository import create_plot_check, get_or_create_plot, update_api_task_state
from backend.repositories.plot_rrp_summary_repository import insert_plot_rrp_summary
from backend.repositories.rrp_common_repository import process_cause_documents_and_links
from backend.repositories.rrp_encumbrances_repository import process_limitations, process_mortgages
from backend.repositories.rrp_realty_repository import RrpRealtyRepository
from backend.repositories.rrp_rights_repository import process_other_property_rights, process_property_rights

# TODO: Импорты для RRP и MDM (добавим позже)
# from backend.repositories.rrp_advanced_repository import process_rrp_advanced
# from backend.repositories.mdm_repository import process_subjects

logger = logging.getLogger(__name__)


def process_rrp_advanced(cursor, check_id: int, rrp_advanced_data: dict, task_id: str) -> None:
    """
    Оркестратор для блока RrpAdvanced.
    Обрабатывает массив недвижимости и все связанные права/обременения.
    """
    if not rrp_advanced_data:
        return

    realty_list = rrp_advanced_data.get("realty")
    if not realty_list:
        return

    # Предохранитель: API иногда отдает объект вместо массива
    if isinstance(realty_list, dict):
        realty_list = [realty_list]

    if not isinstance(realty_list, list):
        return

    for realty in realty_list:
        if not isinstance(realty, dict):
            continue

        # 1. Сохраняем базовый объект недвижимости (Snapshot)
        realty_id = RrpRealtyRepository.save_realty_snapshot(cursor, check_id, realty)
        if not realty_id:
            logger.warning(f"Не удалось сохранить RealtySnapshot для CheckId {check_id}")
            continue

        # 2. Сохраняем адреса
        addresses = realty.get("realtyAddress")
        if isinstance(addresses, dict):
            addresses = [addresses]
        if isinstance(addresses, list):
            for addr in addresses:
                if isinstance(addr, dict):
                    RrpRealtyRepository.save_realty_address(cursor, realty_id, addr)

        # 3. Сохраняем земельные участки (GroundAreas)
        RrpRealtyRepository.process_realty_ground_areas(cursor, realty_id, realty.get("groundArea"))

        # 4. Обрабатываем права и обременения, собирая "хвосты" (документы и линки)
        all_documents_and_links = []

        # -- Права собственности (prp) --
        prp_docs = process_property_rights(cursor, realty_id, realty.get("prp"), task_id)
        if prp_docs:
            all_documents_and_links.extend(prp_docs)

        # -- Иные вещные права (irp) --
        irp_docs = process_other_property_rights(cursor, realty_id, realty.get("irp"), task_id)
        if irp_docs:
            all_documents_and_links.extend(irp_docs)

        # -- Обременения (limitation) --
        lm_docs = process_limitations(cursor, realty_id, realty.get("limitation"), task_id)
        if lm_docs:
            all_documents_and_links.extend(lm_docs)

        # -- Ипотеки (mortgage) --
        mg_docs = process_mortgages(cursor, realty_id, realty.get("mortgage"), task_id)
        if mg_docs:
            all_documents_and_links.extend(mg_docs)

        # 5. Финал: сохраняем все собранные документы и связи в полиморфные таблицы
        if all_documents_and_links:
            process_cause_documents_and_links(cursor, all_documents_and_links)


def process_registry_json(db_connection, task_id: str, json_file_path: str):
    """
    Оркестратор парсинга. Открывает файл, читает JSON и прогоняет каждый участок
    через конвейер репозиториев в рамках единой транзакции.
    """
    logger.info(f"Начало обработки задачи {task_id}. Файл: {json_file_path}")
    cursor = db_connection.cursor()

    try:
        # Читаем JSON файл
        with open(json_file_path, "r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, list):
            raise ValueError("Ожидался массив участков в корне JSON.")

        total_plots = len(data)
        logger.info(f"Найдено участков для обработки: {total_plots}")

        # Проходимся по каждому участку
        for index, item in enumerate(data):
            cadastral_number = item.get("CadastrNumber")

            # Пропускаем записи без кадастрового номера (если такие бывают)
            if not cadastral_number:
                logger.warning(f"Пропущен элемент на индексе {index} (нет CadastrNumber)")
                continue

            plot_data = item.get("Plot") or {}
            hash_code = plot_data.get("hashCode")

            # =================================================================
            # БЛОК 1: ИДЕНТИФИКАЦИЯ И ИСТОРИЧНОСТЬ (plot_repository)
            # =================================================================
            plot_id = get_or_create_plot(cursor, cadastral_number)

            # Создаем новый "снимок" проверки (Check)
            check_id = create_plot_check(
                cursor=cursor,
                plot_id=plot_id,
                task_id=task_id,
                source_version=hash_code,
                source="JSON_UPLOAD",
                is_successful=1,
            )

            # =================================================================
            # БЛОК 2: ДЕТАЛИ УЧАСТКА (Plot)
            # =================================================================
            if plot_data:
                # 2.1 Плоские характеристики и климат
                insert_plot_main_snapshot(cursor, check_id, plot_data)

                # 2.2 Деньги и оценка (НГО)
                insert_plot_ngo(cursor, check_id, plot_data.get("ngo"))

                # 2.3 Пересечения границ
                insert_plot_intersections(cursor, check_id, plot_data.get("plotPlotIntersect"))

                # 2.4 Государственный земельный кадастр (ДЗК)
                insert_plot_dzk_info(cursor, check_id, plot_data.get("dzkLandInfo"))

                # 2.5 Контрольные сводные данные из Реестра прав
                insert_plot_rrp_summary(cursor, check_id, plot_data.get("rrpLandInfo"))

            # =================================================================
            # БЛОК 3: ЮРИДИЧЕСКИЕ ПРАВА И СУБЪЕКТЫ (RrpAdvanced)
            # =================================================================
            rrp_advanced_data = item.get("RrpAdvanced")
            if rrp_advanced_data:
                # Вызываем наш новый оркестратор RRP
                process_rrp_advanced(cursor, check_id, rrp_advanced_data, task_id)

        # Если цикл прошел без ошибок — сохраняем ВСЕ изменения в БД!
        db_connection.commit()

        # Обновляем статус задачи на "Выполнено" (например, 1)
        update_api_task_state(cursor, task_id, state=1)
        db_connection.commit()

        logger.info(f"Успешно обработано {total_plots} участков.")

    except Exception as e:
        # Если хоть где-то упала ошибка (например, неверный тип данных) — отменяем ВСЁ
        db_connection.rollback()
        logger.error(f"Критическая ошибка при обработке файла {json_file_path}: {e}")

        # Обновляем статус задачи на "Ошибка" (например, 2)
        try:
            update_api_task_state(cursor, task_id, state=2)
            db_connection.commit()
        except Exception as db_err:
            logger.error(f"Не удалось обновить статус задачи на ошибку: {db_err}")

        raise e  # Пробрасываем ошибку дальше, чтобы Streamlit мог ее показать

    finally:
        cursor.close()
