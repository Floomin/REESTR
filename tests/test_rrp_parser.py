from unittest.mock import MagicMock

import pytest

from backend.services.parser_service import process_rrp_advanced


# 1. Создаем мок курсора, который не ходит в БД, а просто запоминает вызовы
@pytest.fixture
def mock_cursor():
    return MagicMock()


def test_process_rrp_advanced_with_mock(mock_cursor):
    # Загружаем твой "максимально наполненный" JSON
    import json

    with open("tests/mock_data.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    # Запускаем оркестратор
    # task_id передаем фиктивный
    process_rrp_advanced(mock_cursor, check_id=999, rrp_advanced_data=data, task_id="TEST_001")

    # 2. Проверяем, что курсор реально вызвал INSERT
    # Например, проверим, что вставка в RrpRealtySnapshot была вызвана
    assert mock_cursor.execute.called

    # Можно проверить конкретные вызовы:
    # insert_calls = [call for call in mock_cursor.execute.call_args_list if "INSERT INTO RrpRealtySnapshot" in call[0][0]]
    # assert len(insert_calls) > 0

    print("\nТест прошел успешно: все репозитории отработали без исключений!")
