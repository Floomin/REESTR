import streamlit as st

if "role" not in st.session_state:
    st.warning("⛔ Будь ласка, авторизуйтесь на головній сторінці.")
    st.stop() # Зупиняє подальше виконання коду на сторінці

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
            if st.button("Опрацювати файл", type="primary", key="upload_btn"):
                st.success("Файл відправлено на сервер! (Тут буде реальний прогрес-бар)")
    else:
        st.error("⛔ Доступ заборонено. Завантаження файлів вручну доступне лише користувачам з роллю Адміністратора.")
