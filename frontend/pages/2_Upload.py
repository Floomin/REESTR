import requests
import streamlit as st

if "role" not in st.session_state:
    st.warning("⛔ Будь ласка, авторизуйтесь на головній сторінці.")
    st.stop()  # Зупиняє подальше виконання коду на сторінці

st.set_page_config(page_title="Оновлення даних", layout="wide")

# Отримуємо роль поточного користувача (за замовчуванням 'User')
role = st.session_state.get("role", "User")

st.title("Оновлення даних")
st.markdown("---")

tab_api, tab_file = st.tabs(["Запит до API", "Завантаження з файлу (JSON)"])

# Вкладка 1: Доступна всім (або відповідно до ваших майбутніх правил)
with tab_api:
    st.subheader("Синхронізація через API Vkursi")
    st.write("Оновлення даних безпосередньо з державних реєстрів.")
    api_cadastrals = st.text_area("Введіть кадастрові номери (через кому або з нового рядка):", height=150)

    if st.button("Відправити запит", type="primary"):
        st.info("Тут буде логіка відправки масиву кадастрових номерів на наш FastAPI.")

# Вкладка 2: Суворий контроль доступу (тільки Адмін)
with tab_file:
    st.subheader("Імпорт вигрузок")

    if role == "Admin":
        uploaded_file = st.file_uploader("Оберіть JSON файл", type=["json"])
        if uploaded_file is not None:
            # Використовуємо width="stretch" згідно з оновленими стандартами Streamlit
            if st.button("🚀 Розпочати імпорт", type="primary", width="stretch"):
                with st.spinner("Триває імпорт та обробка даних... Це може зайняти певний час для великих файлів."):
                    try:
                        # URL вашого бекенду (з upload.py)
                        API_URL = "http://127.0.0.1:8000/api/upload/json"
                        files = {"file": (uploaded_file.name, uploaded_file, "application/json")}

                        # Відправляємо файл на сервер
                        res = requests.post(API_URL, files=files)

                        if res.status_code == 200:
                            data = res.json()
                            st.success("✅ Файл успішно оброблено!")

                            # Красиво виводимо статистику з нашого parser_service
                            col1, col2, col3 = st.columns(3)
                            col1.metric("Оброблено ділянок", data.get("processed", 0))
                            col2.metric("Пропущено (дублікати)", data.get("skipped", 0))
                            col3.metric("Помилки", len(data.get("errors", [])))

                            # Якщо були помилки, ховаємо їх під спойлер, щоб не засмічувати екран
                            if data.get("errors"):
                                with st.expander("Деталі помилок"):
                                    for err in data["errors"]:
                                        st.error(err)
                        else:
                            st.error(f"Помилка сервера: {res.text}")

                    except Exception as e:
                        st.error(f"Помилка підключення до сервера: {e}")
    else:
        st.error("⛔ Доступ заборонено. Завантаження файлів вручну доступне лише користувачам з роллю Адміністратора.")
