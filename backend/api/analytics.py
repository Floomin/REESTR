from typing import Annotated, Optional

import pyodbc
from fastapi import APIRouter, Depends, HTTPException
from loguru import logger

from backend.core.database import get_db_connection

router = APIRouter(prefix="/api/analytics", tags=["Analytics"])
DbSession = Annotated[pyodbc.Connection, Depends(get_db_connection)]


@router.get("/koatuu")
def get_koatuu_analytics(db: DbSession, koatuu: Optional[str] = None, company: Optional[str] = None):
    """Отримує детальну аналітику для вкладки Сільських рад (КОАТУУ) з перехресними фільтрами."""
    cursor = db.cursor()

    # 1. Формуємо параметри для уникнення SQL-ін'єкцій
    k_param = f"{koatuu}%" if koatuu else None
    c_param = f"%{company}%" if company else None

    try:
        # --- ЗАПИТ 1: Головні KPI та Метрики ---
        kpi_query = """
            WITH LatestChecks AS (
                SELECT PlotId, CheckId
                FROM (
                    SELECT PlotId, CheckId, ROW_NUMBER() OVER (PARTITION BY PlotId ORDER BY CheckedAt DESC) as rn
                    FROM dbo.PlotCheck
                ) t WHERE rn = 1
            ),
            PlotStats AS (
                SELECT
                    lp.PlotId,
                    CAST(ps.Area AS FLOAT) AS Area,
                    CAST(ngo.ValuationAmount AS FLOAT) AS TotalNgo,
                    -- Перевіряємо наявність власності
                    (SELECT TOP 1 1 FROM RrpRealtySnapshot rrp JOIN RrpPropertyRights pr ON rrp.RealtyId = pr.RealtyId WHERE rrp.CheckId = lc.CheckId) AS HasProperty,
                    -- Перевіряємо наявність оренди
                    (SELECT TOP 1 1 FROM RrpRealtySnapshot rrp JOIN PlotRightSnapshot irp ON rrp.RealtyId = irp.RealtyId WHERE rrp.CheckId = lc.CheckId AND irp.RightType LIKE '%оренд%') AS HasLease,
                    -- Рік завершення оренди
                    (SELECT TOP 1 YEAR(irp.EndDate) FROM RrpRealtySnapshot rrp JOIN PlotRightSnapshot irp ON rrp.RealtyId = irp.RealtyId WHERE rrp.CheckId = lc.CheckId AND irp.RightType LIKE '%оренд%' ORDER BY irp.EndDate DESC) AS LeaseEndYear,
                    -- Автопролонгація
                    (SELECT TOP 1 irp.IsAutomaticProlongation FROM RrpRealtySnapshot rrp JOIN PlotRightSnapshot irp ON rrp.RealtyId = irp.RealtyId WHERE rrp.CheckId = lc.CheckId AND irp.RightType LIKE '%оренд%') AS IsAutoProlong,
                    -- Обтяження / Арешти
                    (SELECT TOP 1 1 FROM RrpRealtySnapshot rrp JOIN RrpLimitations lim ON rrp.RealtyId = lim.RealtyId WHERE rrp.CheckId = lc.CheckId) AS HasLimitation
                FROM dbo.LandPlot lp
                JOIN LatestChecks lc ON lp.PlotId = lc.PlotId
                LEFT JOIN dbo.PlotSnapshot ps ON lc.CheckId = ps.CheckId
                LEFT JOIN dbo.PlotNgoSnapshot ngo ON lc.CheckId = ngo.CheckId
                WHERE (? IS NULL OR ps.Koatuu LIKE ?) -- ВИПРАВЛЕНО ТУТ
                  AND (? IS NULL OR EXISTS (
                      SELECT 1 FROM RrpRealtySnapshot rrp
                      JOIN PlotRightSnapshot irp ON rrp.RealtyId = irp.RealtyId
                      JOIN Subject s ON irp.SubjectId = s.SubjectId
                      WHERE rrp.CheckId = lc.CheckId AND (s.SubjectCode = ? OR s.SubjectName LIKE ?)
                  ))
            )
            SELECT
                COUNT(PlotId) AS TotalPlots,
                SUM(Area) AS TotalArea,
                SUM(CASE WHEN HasLease = 1 THEN Area ELSE 0 END) AS LeasedArea,
                SUM(CASE WHEN HasProperty = 1 AND HasLease IS NULL THEN Area ELSE 0 END) AS OwnedNotLeasedArea,
                SUM(TotalNgo) / NULLIF(SUM(CASE WHEN TotalNgo > 0 THEN Area ELSE 0 END), 0) AS AvgNgoPerHa,
                AVG(LeaseEndYear) AS AvgEndYear,
                SUM(CASE WHEN IsAutoProlong = 1 THEN Area ELSE 0 END) AS AutoProlongArea,
                SUM(CASE WHEN HasLimitation = 1 THEN Area ELSE 0 END) AS ArrestedArea
            FROM PlotStats;
        """
        cursor.execute(kpi_query, (koatuu, k_param, company, company, c_param))
        k_row = cursor.fetchone()

        kpi_data = {
            "total_plots": k_row[0] or 0,
            "total_area": round(k_row[1] or 0.0, 2),
            "leased_area": round(k_row[2] or 0.0, 2),
            "owned_not_leased": round(k_row[3] or 0.0, 2),
            "avg_ngo_per_ha": round(k_row[4] or 0.0, 2),
            "avg_end_year": int(k_row[5]) if k_row[5] else None,
            "auto_prolong_area": round(k_row[6] or 0.0, 2),
            "arrested_area": round(k_row[7] or 0.0, 2),
        }

        # --- ЗАПИТ 2: Топ користувачі (Орендарі) ---
        top_query = """
            WITH LatestChecks AS (
                SELECT PlotId, CheckId
                FROM (SELECT PlotId, CheckId, ROW_NUMBER() OVER (PARTITION BY PlotId ORDER BY CheckedAt DESC) as rn FROM dbo.PlotCheck) t WHERE rn = 1
            )
            SELECT TOP 15
                ISNULL(s.SubjectName, 'Невідомо') AS CompanyName,
                ISNULL(s.SubjectCode, '00000000') AS CompanyCode,
                SUM(CAST(ps.Area AS FLOAT)) AS TotalArea,
                COUNT(DISTINCT lp.PlotId) AS PlotCount
            FROM dbo.LandPlot lp
            JOIN LatestChecks lc ON lp.PlotId = lc.PlotId
            JOIN dbo.PlotSnapshot ps ON lc.CheckId = ps.CheckId
            JOIN dbo.RrpRealtySnapshot rrp ON lc.CheckId = rrp.CheckId
            JOIN dbo.PlotRightSnapshot irp ON rrp.RealtyId = irp.RealtyId AND irp.RightType LIKE '%оренд%'
            JOIN dbo.Subject s ON irp.SubjectId = s.SubjectId
            WHERE (? IS NULL OR ps.Koatuu LIKE ?) -- ВИПРАВЛЕНО ТУТ
            GROUP BY s.SubjectName, s.SubjectCode
            ORDER BY TotalArea DESC;
        """
        cursor.execute(top_query, (koatuu, k_param))
        top_lessees = [
            {"company": r[0], "code": r[1], "area": round(r[2] or 0.0, 2), "plots": r[3]} for r in cursor.fetchall()
        ]

        # --- ЗАПИТ 3: Розподіл по роках завершення ---
        years_query = """
            WITH LatestChecks AS (
                SELECT PlotId, CheckId
                FROM (SELECT PlotId, CheckId, ROW_NUMBER() OVER (PARTITION BY PlotId ORDER BY CheckedAt DESC) as rn FROM dbo.PlotCheck) t WHERE rn = 1
            )
            SELECT
                YEAR(irp.EndDate) AS EndYear,
                SUM(CAST(ps.Area AS FLOAT)) AS TotalArea,
                COUNT(DISTINCT lp.PlotId) AS PlotCount
            FROM dbo.LandPlot lp
            JOIN LatestChecks lc ON lp.PlotId = lc.PlotId
            JOIN dbo.PlotSnapshot ps ON lc.CheckId = ps.CheckId
            JOIN dbo.RrpRealtySnapshot rrp ON lc.CheckId = rrp.CheckId
            JOIN dbo.PlotRightSnapshot irp ON rrp.RealtyId = irp.RealtyId
            WHERE (? IS NULL OR ps.Koatuu LIKE ?) -- ВИПРАВЛЕНО ТУТ
              AND irp.EndDate IS NOT NULL
              AND YEAR(irp.EndDate) BETWEEN 2024 AND 2050
              AND (? IS NULL OR EXISTS (SELECT 1 FROM dbo.Subject s WHERE s.SubjectId = irp.SubjectId AND (s.SubjectCode = ? OR s.SubjectName LIKE ?)))
            GROUP BY YEAR(irp.EndDate)
            ORDER BY EndYear;
        """
        cursor.execute(years_query, (koatuu, k_param, company, company, c_param))
        lease_years = [
            {"year": str(int(r[0])), "area": round(r[1] or 0.0, 2), "plots": r[2]} for r in cursor.fetchall()
        ]

        return {"status": "success", "kpi": kpi_data, "top_lessees": top_lessees, "lease_years": lease_years}

    except Exception as e:
        logger.error(f"Помилка аналітики КОАТУУ: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
