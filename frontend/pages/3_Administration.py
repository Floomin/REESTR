import streamlit as st

if "role" not in st.session_state:
    st.warning("⛔ Будь ласка, авторизуйтесь на головній сторінці.")
    st.stop()  # Зупиняє подальше виконання коду на сторінці

st.set_page_config(page_title="Адміністрування", layout="wide")

st.title("Адміністрування системи")
st.markdown("---")

tab_users, tab_logs = st.tabs(["Управління користувачами", "Журнал дій (Аудит)"])

with tab_users:
    col1, col2 = st.columns([1, 2])
    with col1:
        st.subheader("Створити користувача")
        with st.form("new_user"):
            st.text_input("Логін")
            st.text_input("ПІБ")
            st.selectbox("Роль", ["User", "Admin"])
            st.text_input("Тимчасовий пароль")
            st.form_submit_button("Додати", type="primary")

    with col2:
        st.subheader("Активні користувачі")
        st.write("Тут буде таблиця (Dataframe) зі списком користувачів, кнопками блокування та скидання пароля.")

with tab_logs:
    st.subheader("Аналітика дій")
    st.write("Тут буде таблиця (UserActionLog) з історією пошукових запитів та входів у систему.")
