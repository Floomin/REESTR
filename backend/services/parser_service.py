import pyodbc
from loguru import logger

from backend.repositories.dzk_repository import process_dzk
from backend.repositories.plot_repository import (
    create_api_task,
    create_plot_check,
    finish_api_task,
    get_latest_source_version,
    get_or_create_plot,
    insert_plot_snapshot,
)
from backend.repositories.rrp_repository import process_rrp


def process_json_payload(db: pyodbc.Connection, task_id: str, file_name: str, json_data: list) -> dict:
    cursor = db.cursor()
    processed_count = 0
    skipped_count = 0 # <-- Новий лічильник для пропущених дублікатів
    errors = []

    try:
        create_api_task(cursor, task_id, file_name, state=3)
        db.commit()

        for item in json_data:
            cadastral = item.get("CadastrNumber")
            plot = item.get("Plot")

            if not cadastral or not plot:
                continue

            try:
                # 1. Отримуємо ID ділянки
                plot_id = get_or_create_plot(cursor, cadastral)

                # 2. ПЕРЕВІРКА НА ДУБЛІКАТИ
                current_hash = plot.get("hashCode")
                latest_hash = get_latest_source_version(cursor, plot_id)

                # Якщо хеш є у файлі і він співпадає з останнім у базі - пропускаємо!
                if current_hash and latest_hash == current_hash:
                    logger.info(f"Ділянка {cadastral} не змінилася (дублікат). Пропуск.")
                    skipped_count += 1
                    continue

                # 3. Якщо дані нові - дістаємо оригінальну дату та зберігаємо
                dzk_info = plot.get("dzkLandInfo") or {}
                registry_date = dzk_info.get("UpdateDate")

                check_id = create_plot_check(
                    cursor,
                    plot_id,
                    task_id,
                    source_version=current_hash,
                    update_date=registry_date
                )

                insert_plot_snapshot(cursor, check_id, plot)
                process_dzk(cursor, check_id, cadastral, plot.get("dzkLandInfo"))
                process_rrp(cursor, check_id, item)

                db.commit()
                processed_count += 1
                logger.info(f"Успішно оброблено: {cadastral}")

            except Exception as e:
                db.rollback()
                error_msg = f"Помилка обробки ділянки {cadastral}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)

        final_state = 1 if len(errors) == 0 else 2
        finish_api_task(cursor, task_id, state=final_state)
        db.commit()

        # Повертаємо інформацію про пропущені файли
        return {
            "status": "success",
            "processed": processed_count,
            "skipped": skipped_count,
            "errors": errors
        }

    except Exception as e:
        db.rollback()
        finish_api_task(cursor, task_id, state=2)
        db.commit()
        logger.critical(f"Глобальна помилка парсингу: {e}")
        raise e
    finally:
        cursor.close()
