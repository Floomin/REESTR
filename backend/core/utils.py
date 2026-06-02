import json


def map_code(val, mapping_dict):
    """Ищет текстовое значение в словаре по коду."""
    if val in (None, "", "null"):
        return None
    try:
        clean_val = str(int(float(val)))
    except (ValueError, TypeError):
        clean_val = str(val).strip()

    if not mapping_dict:
        return str(val)
    return mapping_dict.get(clean_val, f"{clean_val} (Немає в довіднику)")


def safe_float(val):
    """Безопасное преобразование во float, обрабатывает пустые строки и None."""
    if val in (None, "", "null"):
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def safe_int(val):
    """Безопасное преобразование в int."""
    if val in (None, "", "null"):
        return None
    try:
        return int(float(val))
    except (ValueError, TypeError):
        return None


def safe_bool(val):
    """Безопасное преобразование в bool."""
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    if isinstance(val, str):
        return val.lower() in ("true", "1", "yes")
    return bool(val)


def safe_json_string(val):
    """Преобразует массивы (list) или объекты (dict) в JSON-строку."""
    if val is None:
        return None
    if isinstance(val, (list, dict)):
        return json.dumps(val, ensure_ascii=False)
    return str(val)


def clean_datetime(val):
    """
    Очищает дату от часового пояса для безопасной вставки в SQL Server (DATETIME2).
    Пример: '2020-12-18T08:17:00.1650127+02:00' -> '2020-12-18T08:17:00.1650127'
    """
    if not val or val in ("null", ""):
        return None
    val_str = str(val).strip()
    if "+" in val_str:
        val_str = val_str.split("+")[0]
    if val_str.endswith("Z"):
        val_str = val_str[:-1]
    return val_str
