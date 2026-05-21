import requests
import streamlit as st

# Налаштування сторінки
st.set_page_config(page_title="Державні Реєстри", page_icon="🚜", layout="wide")

st.title("🚜 Управління земельним банком")
st.markdown("---")

st.subheader("Завантаження даних (JSON)")
uploaded_file = st.file_uploader("Оберіть файл вигрузки з реєстрів", type=["json"])

if uploaded_file is not None:
    if st.button("Опрацювати файл", type="primary"):
        with st.spinner("Відправка файлу на сервер та парсинг даних..."):
            try:
                # Підготовка файлу для відправки через HTTP POST запит
                files = {"file": (uploaded_file.name, uploaded_file.getvalue(), "application/json")}

                # Звертаємось до нашого FastAPI сервера
                response = requests.post("http://127.0.0.1:8000/api/upload/json", files=files)

                if response.status_code == 200:
                    result = response.json()
                    st.success("Файл успішно оброблено сервером!")

                    # Виведення статистики
                    col1, col2 = st.columns(2)
                    col1.metric("✅ Додано / Оновлено", result.get("processed", 0))
                    col2.metric("⏭️ Пропущено (дублікати)", result.get("skipped", 0))

                    # Виведення помилок, якщо вони є
                    if result.get("errors"):
                        st.error("⚠️ Під час обробки деяких ділянок виникли помилки:")
                        for err in result.get("errors"):
                            st.write(f"- {err}")
                else:
                    st.error(f"Помилка сервера: {response.status_code} - {response.text}")

            except requests.exceptions.ConnectionError:
                st.error("🚨 Не вдалося підключитися до Backend сервера. Переконайтеся, що FastAPI (uvicorn) запущено на порту 8000.")
            except Exception as e:
                st.error(f"Неочікувана помилка: {e}")
