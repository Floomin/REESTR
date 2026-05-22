def get_or_create_plot(cursor, cadastral_number):
    cursor.execute(
        """
        SELECT PlotId
        FROM LandPlot
        WHERE CadastralNumber = ?
    """,
        cadastral_number,
    )

    row = cursor.fetchone()

    if row:
        return row[0]

    cursor.execute(
        """
        INSERT INTO LandPlot (CadastralNumber)
        OUTPUT INSERTED.PlotId
        VALUES (?)
    """,
        cadastral_number,
    )

    return cursor.fetchone()[0]

def get_latest_source_version(cursor, plot_id: int) -> str | None:
    """
    Отримує SourceVersion (hashCode) останньої перевірки для вказаної ділянки.
    """
    cursor.execute("""
        SELECT TOP 1 SourceVersion
        FROM PlotCheck
        WHERE PlotId = ?
        ORDER BY CheckedAt DESC
    """, (plot_id,))
    row = cursor.fetchone()
    return row[0] if row else None

def create_plot_check(cursor, plot_id, task_id, source_version=None, update_date=None):
    """
    Створює запис перевірки (історичний зріз).
    Приймає опціональні source_version (hashCode) та update_date (дата з реєстру).
    """
    cursor.execute("""
        INSERT INTO PlotCheck (PlotId, TaskId, CheckedAt, SourceVersion)
        OUTPUT INSERTED.CheckId
        VALUES (?, ?, COALESCE(TRY_CAST(? AS DATETIME2), GETDATE()), ?)
    """, (plot_id, task_id, update_date, source_version))

    return cursor.fetchone()[0]


def insert_plot_snapshot(cursor, check_id, plot):
    cursor.execute(
        """
        INSERT INTO PlotSnapshot (
            CheckId, Area, Purpose, Category, OwnershipType,
            Region, District, Koatuu, SoilType, SurfaceAngle,
            AvgTemperature, Percipitation, IsInPZFArea, IsGeomValid, ComplexNumber
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """,
        check_id,
        plot.get("area"),
        plot.get("purpose"),
        plot.get("category"),
        plot.get("ownershipType"),
        plot.get("region"),
        plot.get("district"),
        plot.get("koatuu"),
        plot.get("soilType"),
        plot.get("surfaceAngle"),
        plot.get("avgTemperature"),
        plot.get("percipitation"),
        plot.get("isInPZFArea"),
        plot.get("isGeomValid"),
        plot.get("complexNumber"),
    )


def insert_ngo_snapshot(cursor, check_id, ngo_data):
    if not ngo_data:
        return

    cursor.execute(
        """
        INSERT INTO PlotNgoSnapshot (
            CheckId, ValuationAmount, ValuationDate, PricePerGekt
        )
        VALUES (?, ?, ?, ?)
    """,
        check_id,
        ngo_data.get("price"),
        ngo_data.get("dateModify"),
        ngo_data.get("pricePerGekt"),
    )
def create_api_task(cursor, task_id: str, task_name: str, state: int = 3):
    """
    Створює запис про нове завдання в базі даних (State: 3 - в процесі).
    """
    cursor.execute("""
        INSERT INTO ApiTask (TaskId, TaskName, State, CreatedAt)
        VALUES (?, ?, ?, GETDATE())
    """, (task_id, task_name, state))

def finish_api_task(cursor, task_id: str, state: int):
    """
    Оновлює статус завдання при завершенні або помилці.
    """
    cursor.execute("""
        UPDATE ApiTask
        SET State = ?, FinishedAt = GETDATE()
        WHERE TaskId = ?
    """, (state, task_id))
