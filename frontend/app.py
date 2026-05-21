import requests
import streamlit as st

st.set_page_config(page_title="Державні реєстри | Вхід", layout="centered")

# Перевіряємо, чи користувач вже авторизований
if "role" not in st.session_state:
    st.title("Державні реєстри")
    st.markdown("---")
    st.subheader("Авторизація")

    with st.form("login_form"):
        # Використовуємо логіни з нашого SQL-скрипта: 'admin_main', 'pavlenko_v', 'user_test'
        login = st.text_input("Логін", placeholder="Наприклад: admin_main")
        password = st.text_input("Пароль", type="password", placeholder="Введіть 12345 для тесту")

        submitted = st.form_submit_button("Увійти", type="primary")

        if submitted:
            try:
                # Відправляємо запит на FastAPI
                response = requests.post(
                    "http://127.0.0.1:8000/api/auth/login",
                    json={"login": login, "password": password}
                )

                if response.status_code == 200:
                    data = response.json()
                    # Зберігаємо дані в сесію
                    st.session_state["user_id"] = data["user_id"]
                    st.session_state["full_name"] = data["full_name"]
                    st.session_state["role"] = data["role"]

                    # Перезавантажуємо сторінку
                    st.rerun()
                else:
                    # Виводимо помилку від сервера (наприклад, "Невірний логін")
                    st.error(response.json().get("detail", "Помилка авторизації"))
            except requests.exceptions.ConnectionError:
                st.error("Не вдалося підключитися до сервера. Перевірте, чи запущено FastAPI.")
else:
    # Екран після успішного входу
    st.title(f"Вітаємо, {st.session_state['full_name']}!")
    st.info(f"Ваша роль у системі: **{st.session_state['role']}**")
    st.write("👈 Оберіть потрібний розділ меню на бічній панелі зліва.")

    st.markdown("---")
    if st.button("Вийти з системи"):
        st.session_state.clear()
        st.rerun()
