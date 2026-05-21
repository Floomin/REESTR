import streamlit as st

# Налаштування сторінки
st.set_page_config(page_title="Державні реєстри | Вхід", layout="centered")

# Нова назва системи
st.title("Державні реєстри")
st.markdown("---")

st.subheader("Авторизація")
with st.form("login_form"):
    login = st.text_input("Логін", placeholder="Введіть ваш логін (введіть 'admin' для тесту)")
    password = st.text_input("Пароль", type="password", placeholder="Введіть пароль")

    submitted = st.form_submit_button("Увійти", type="primary")

    if submitted:
        # Тимчасова логіка для тестування інтерфейсу
        if login.lower() == "admin":
            st.session_state["role"] = "Admin"
            st.success("Ви увійшли як Адміністратор! Перейдіть до меню зліва.")
        else:
            st.session_state["role"] = "User"
            st.success("Ви увійшли як Користувач! Перейдіть до меню зліва.")
