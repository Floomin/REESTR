from typing import Annotated, Optional

import pyodbc
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from backend.core.database import get_db_connection

router = APIRouter(prefix="/api/search", tags=["Search"])
DbSession = Annotated[pyodbc.Connection, Depends(get_db_connection)]

@router.get("/list")
def search_plots_list(
    db: DbSession,
    user_id: int,
    cadastral: Optional[str] = None,
    edrpou: Optional[str] = None,
    koatuu: Optional[str] = None,
    subject_name: Optional[str] = None,
    limit: int = 1000,
    offset: int = 0
):
    """Шукає ділянки з підтримкою пагінації. Максимально оптимізований запит."""
    cursor = db.cursor()

    action_details = f"Пошук: Кадастр={cadastral}, ЄДРПОУ={edrpou}, КОАТУУ={koatuu}, Назва={subject_name}"
    try:
        cursor.execute("""
            INSERT INTO UserActionLog (UserId, ActionType, ActionDetails)
            VALUES (?, 'SEARCH', ?)
        """, (user_id, action_details))
        db.commit()
    except Exception as e:
        db.rollback()
        logger.warning(f"Не вдалося записати лог пошуку: {e}")

    # Ультра-швидкий запит: тільки базові дані та підрахунок загальної кількості
    query = """
        WITH RankedChecks AS (
            SELECT PlotId, CheckId, ROW_NUMBER() OVER(PARTITION BY PlotId ORDER BY CheckedAt DESC) as rn
            FROM PlotCheck
        ),
        FilteredPlots AS (
            SELECT
                lp.CadastralNumber,
                ps.Koatuu,
                ps.Area,
                rc.CheckId,
                COUNT(*) OVER() AS TotalCount
            FROM LandPlot lp
            JOIN RankedChecks rc ON lp.PlotId = rc.PlotId AND rc.rn = 1
            LEFT JOIN PlotSnapshot ps ON rc.CheckId = ps.CheckId
            WHERE 1=1
    """
    params = []

    if cadastral:
        query += " AND lp.CadastralNumber LIKE ?"
        params.append(f"%{cadastral}%")

    if koatuu:
        query += " AND ps.Koatuu LIKE ?"
        params.append(f"{koatuu}%")

    if edrpou or subject_name:
        query += """
            AND rc.CheckId IN (
                SELECT rss.CheckId
                FROM PlotRrpSummarySnapshot rss
                JOIN PlotRrpSummarySubjects sub ON rss.SummarySnapshotId = sub.SummarySnapshotId
                WHERE 1=1
        """
        if edrpou:
            query += " AND sub.Code = ?"
            params.append(edrpou)
        if subject_name:
            query += " AND sub.Name LIKE ?"
            params.append(f"%{subject_name}%")
        query += ")"

    # Фінальна вибірка без жодних STUFF / XML PATH
    query += """
        )
        SELECT
            f.CadastralNumber,
            f.Koatuu,
            f.Area,
            f.TotalCount
        FROM FilteredPlots f
        ORDER BY f.CadastralNumber
        OFFSET ? ROWS FETCH NEXT ? ROWS ONLY
    """

    params.extend([offset, limit])

    try:
        cursor.execute(query, params)
        columns = [column[0] for column in cursor.description]
        rows = cursor.fetchall()

        total_count = rows[0].TotalCount if rows else 0

        results = []
        for row in rows:
            row_dict = dict(zip(columns, row, strict=False))
            row_dict.pop("TotalCount", None)
            results.append(row_dict)

        return {"status": "success", "data": results, "total": total_count}
    except Exception as e:
        logger.error(f"Помилка пошуку: {e}")
        raise HTTPException(status_code=500, detail="Помилка бази даних під час пошуку") from e

@router.get("/dossier/{cadastral}")
def get_plot_dossier(cadastral: str, db: DbSession):
    """Повертає повну історичну цепочку зрізів ДЗК для конкретної ділянки."""
    cursor = db.cursor()

    try:
        # 1. Знаходимо ВСІ історичні зрізи (PlotCheck) для цього кадастрового номера
        cursor.execute("""
            SELECT pc.CheckId, pc.CheckedAt, t.TaskName
            FROM LandPlot lp
            JOIN PlotCheck pc ON lp.PlotId = pc.PlotId
            LEFT JOIN ApiTask t ON pc.TaskId = t.TaskId
            WHERE lp.CadastralNumber = ?
            ORDER BY pc.CheckedAt DESC
        """, (cadastral,))

        check_rows = cursor.fetchall()
        if not check_rows:
            raise HTTPException(status_code=404, detail="Ділянку не знайдено")

        history_data = []

        # 2. Для кожної перевірки збираємо повний пакет даних ДЗК за вашими 4 блоками
        for ch_row in check_rows:
            check_id, checked_at, task_name = ch_row

            # Блок 1: Відомості про земельну ділянку (Snapshot)
            cursor.execute("SELECT DzkSnapshotId, CadastralNumber, Purpose, Area, Location FROM PlotDzkSnapshot WHERE CheckId = ?", (check_id,))
            dzk_cols = [col[0] for col in cursor.description] if cursor.description else []
            dzk_row = cursor.fetchone()

            if not dzk_row:
                continue # Якщо в цьому зрізі немає даних ДЗК, пропускаємо

            snapshot_data = dict(zip(dzk_cols, dzk_row, strict=False))
            dzk_snapshot_id = snapshot_data["DzkSnapshotId"]

            # Блок 2: Відомості про суб'єктів права власності
            cursor.execute("""
                SELECT OwnershipType, NameFo, NameUo, Edrpou, DateRegRight, EntryRecordNumber, RegAuthority
                FROM PlotDzkOwnership
                WHERE DzkSnapshotId = ?
            """, (dzk_snapshot_id,))
            own_cols = [col[0] for col in cursor.description]
            ownerships = [dict(zip(own_cols, r, strict=False)) for r in cursor.fetchall()]

            # Блок 3: Відомості про суб'єктів речових прав (Оренда тощо)
            cursor.execute("""
                SELECT PropertyRight, NameFo, NameUo, Edrpou, DateRegRight, EntryRecordNumber, RegAuthority
                FROM PlotDzkSubjectRealRights
                WHERE DzkSnapshotId = ?
            """, (dzk_snapshot_id,))
            right_cols = [col[0] for col in cursor.description]
            real_rights = [dict(zip(right_cols, r, strict=False)) for r in cursor.fetchall()]

            # Блок 4: Відомості про зареєстровані обмеження
            cursor.execute("""
                SELECT RestrictionType, RestrictionCode, RegistrationDate
                FROM PlotDzkRestrictions
                WHERE DzkSnapshotId = ?
            """, (dzk_snapshot_id,))
            rest_cols = [col[0] for col in cursor.description]
            restrictions = [dict(zip(rest_cols, r, strict=False)) for r in cursor.fetchall()]

            # Пакуємо зріз в історію
            history_data.append({
                "check_id": check_id,
                "checked_at": checked_at.strftime("%Y-%m-%d %H:%M") if checked_at else "Невідомо",
                "source": task_name or "API Запит",
                "snapshot": snapshot_data,
                "ownerships": ownerships,
                "real_rights": real_rights,
                "restrictions": restrictions
            })

        return {"status": "success", "history": history_data}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Помилка отримання історії для {cadastral}: {e}")
        raise HTTPException(status_code=500, detail="Помилка при завантаженні історії досьє") from e
