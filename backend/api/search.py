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
    offset: int = 0,
):
    """Шукає ділянки з підтримкою пагінації. Максимально оптимізований запит."""
    cursor = db.cursor()

    action_details = f"Пошук: Кадастр={cadastral}, ЄДРПОУ={edrpou}, КОАТУУ={koatuu}, Назва={subject_name}"
    try:
        cursor.execute(
            """
            INSERT INTO UserActionLog (UserId, ActionType, ActionDetails)
            VALUES (?, 'SEARCH', ?)
        """,
            (user_id, action_details),
        )
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
    """Повертає повну історичну цепочку зрізів ДЗК та ДРРП для конкретної ділянки."""
    cursor = db.cursor()

    try:
        cursor.execute(
            """
            SELECT pc.CheckId, pc.CheckedAt, t.TaskName
            FROM LandPlot lp
            JOIN PlotCheck pc ON lp.PlotId = pc.PlotId
            LEFT JOIN ApiTask t ON pc.TaskId = t.TaskId
            WHERE lp.CadastralNumber = ?
            ORDER BY pc.CheckedAt DESC
        """,
            (cadastral,),
        )

        check_rows = cursor.fetchall()
        if not check_rows:
            raise HTTPException(status_code=404, detail="Ділянку не знайдено")

        history_data = []

        for ch_row in check_rows:
            check_id, checked_at, task_name = ch_row

            # --- БЛОК 1: ДЗК (Залишається без змін) ---
            cursor.execute(
                "SELECT DzkSnapshotId, CadastralNumber, Purpose, Area, Location FROM PlotDzkSnapshot WHERE CheckId = ?",
                (check_id,),
            )
            dzk_cols = [col[0] for col in cursor.description] if cursor.description else []
            dzk_row = cursor.fetchone()

            snapshot_data = dict(zip(dzk_cols, dzk_row, strict=False)) if dzk_row else {}
            dzk_snapshot_id = snapshot_data.get("DzkSnapshotId")

            ownerships, real_rights, restrictions = [], [], []
            if dzk_snapshot_id:
                cursor.execute(
                    "SELECT OwnershipType, NameFo, NameUo, Edrpou, DateRegRight, EntryRecordNumber, RegAuthority FROM PlotDzkOwnership WHERE DzkSnapshotId = ?",
                    (dzk_snapshot_id,),
                )
                ownerships = [dict(zip([c[0] for c in cursor.description], r, strict=False)) for r in cursor.fetchall()]

                cursor.execute(
                    "SELECT PropertyRight, NameFo, NameUo, Edrpou, DateRegRight, EntryRecordNumber, RegAuthority FROM PlotDzkSubjectRealRights WHERE DzkSnapshotId = ?",
                    (dzk_snapshot_id,),
                )
                real_rights = [
                    dict(zip([c[0] for c in cursor.description], r, strict=False)) for r in cursor.fetchall()
                ]

                cursor.execute(
                    "SELECT RestrictionType, RestrictionCode, RegistrationDate FROM PlotDzkRestrictions WHERE DzkSnapshotId = ?",
                    (dzk_snapshot_id,),
                )
                restrictions = [
                    dict(zip([c[0] for c in cursor.description], r, strict=False)) for r in cursor.fetchall()
                ]

            # --- БЛОК 2: ДРРП (НОВЕ) ---
            rrp_data = None
            cursor.execute(
                """
                SELECT RealtyId, RealtyNumber, RegistrationNumber, RegistrationDate, ReType, ReState, RealtyAddress
                FROM RrpRealtySnapshot WHERE CheckId = ?
            """,
                (check_id,),
            )
            realty_cols = [col[0] for col in cursor.description] if cursor.description else []
            realty_row = cursor.fetchone()

            if realty_row:
                rrp_data = dict(zip(realty_cols, realty_row, strict=False))
                realty_id = rrp_data["RealtyId"]

                # Площа об'єкта
                cursor.execute("SELECT Area, AreaUM FROM RrpRealtyGroundArea WHERE RealtyId = ?", (realty_id,))
                area_row = cursor.fetchone()
                rrp_data["FullArea"] = f"{area_row[0]} {area_row[1]}" if area_row else None

                # Права власності
                cursor.execute(
                    """
                    SELECT pr.Id, pr.RegistrationNumber, pr.RightType, pr.RegistrationDate, pr.Registrar, pr.PartSize, pr.PrState,
                           s.SubjectName, s.SubjectCode
                    FROM RrpPropertyRights pr
                    LEFT JOIN Subject s ON pr.SubjectId = s.SubjectId
                    WHERE pr.RealtyId = ?
                """,
                    (realty_id,),
                )
                pr_cols = [c[0] for c in cursor.description] if cursor.description else []
                prop_rights = []
                for r in cursor.fetchall():
                    pr_dict = dict(zip(pr_cols, r, strict=False))
                    # Підтягуємо документи-підстави
                    cursor.execute(
                        "SELECT CdType, DocNumber, DocDate, Publisher FROM RrpCauseDocuments WHERE ParentId = ? AND ParentType = 'PROPERTY'",
                        (pr_dict["Id"],),
                    )
                    pr_dict["documents"] = [
                        dict(zip([c[0] for c in cursor.description], cd_r, strict=False)) for cd_r in cursor.fetchall()
                    ]
                    prop_rights.append(pr_dict)
                rrp_data["property_rights"] = prop_rights

                # Інші речові права (Оренда)
                cursor.execute(
                    """
                    SELECT irp.RightId as Id, irp.RegistrationNumber, irp.RightType, irp.RegistrationDate, irp.StartDate, irp.EndDate, irp.ContractTerm, irp.IsAutomaticProlongation, irp.ObjectDescription, irp.IrpSort,
                           s.SubjectName, s.SubjectCode
                    FROM PlotRightSnapshot irp
                    LEFT JOIN Subject s ON irp.SubjectId = s.SubjectId
                    WHERE irp.RealtyId = ?
                """,
                    (realty_id,),
                )
                or_cols = [c[0] for c in cursor.description] if cursor.description else []
                other_rights = []
                for r in cursor.fetchall():
                    or_dict = dict(zip(or_cols, r, strict=False))
                    cursor.execute(
                        "SELECT CdType, DocNumber, DocDate, Publisher FROM RrpCauseDocuments WHERE ParentId = ? AND ParentType = 'IRP'",
                        (or_dict["Id"],),
                    )
                    or_dict["documents"] = [
                        dict(zip([c[0] for c in cursor.description], cd_r, strict=False)) for cd_r in cursor.fetchall()
                    ]
                    other_rights.append(or_dict)
                rrp_data["other_rights"] = other_rights

                # Іпотеки
                cursor.execute(
                    """
                    SELECT m.MortgageId as Id, m.RegistrationNumber, m.RegistrationDate, m.MortgageType, m.PrState, m.ObjectDescription, m.Registrar,
                           s.SubjectName, s.SubjectCode
                    FROM RrpMortgage m
                    LEFT JOIN Subject s ON m.SubjectId = s.SubjectId
                    WHERE m.RealtyId = ?
                """,
                    (realty_id,),
                )
                mort_cols = [c[0] for c in cursor.description] if cursor.description else []
                mortgages = []
                for r in cursor.fetchall():
                    m_dict = dict(zip(mort_cols, r, strict=False))
                    cursor.execute(
                        "SELECT ObligationType, Amount, Currency FROM RrpMortgageObligations WHERE MortgageId = ?",
                        (m_dict["Id"],),
                    )
                    m_dict["obligations"] = [
                        dict(zip([c[0] for c in cursor.description], obl_r, strict=False))
                        for obl_r in cursor.fetchall()
                    ]
                    mortgages.append(m_dict)
                rrp_data["mortgages"] = mortgages

                # Обтяження (Арешти)
                cursor.execute(
                    """
                    SELECT l.RegistrationNumber, l.RegistrationDate, l.LimitationType, l.LmState, l.ObjectDescription, l.Registrar,
                           s.SubjectName, s.SubjectCode
                    FROM RrpLimitations l
                    LEFT JOIN Subject s ON l.SubjectId = s.SubjectId
                    WHERE l.RealtyId = ?
                """,
                    (realty_id,),
                )
                lim_cols = [c[0] for c in cursor.description] if cursor.description else []
                rrp_data["limitations"] = [dict(zip(lim_cols, r, strict=False)) for r in cursor.fetchall()]

            # Пакуємо все в один зріз
            history_data.append(
                {
                    "check_id": check_id,
                    "checked_at": checked_at.strftime("%Y-%m-%d %H:%M") if checked_at else "Невідомо",
                    "source": task_name or "API Запит",
                    "snapshot": snapshot_data,
                    "ownerships": ownerships,
                    "real_rights": real_rights,
                    "restrictions": restrictions,
                    "rrp": rrp_data,  # НОВИЙ ВУЗОЛ
                }
            )

        return {"status": "success", "history": history_data}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Помилка отримання історії для {cadastral}: {e}")
        raise HTTPException(status_code=500, detail="Помилка при завантаженні історії досьє") from e
