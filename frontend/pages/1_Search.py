import pandas as pd
import streamlit as st

if "role" not in st.session_state:
    st.warning("⛔ Будь ласка, авторизуйтесь на головній сторінці.")
    st.stop() # Зупиняє подальше виконання коду на сторінці

st.set_page_config(page_title="Пошук", layout="wide")

st.title("Пошук по реєстрах")
st.markdown("---")

st.subheader("Параметри пошуку")

# Розбиваємо на 2 колонки для зручної сітки 2x2
col1, col2 = st.columns(2)

with col1:
    cadastral = st.text_input("Кадастровий номер", placeholder="Наприклад: 0520885200:01:005:0813")
    edrpou = st.text_input("ЄДРПОУ / ІПН", placeholder="Тільки цифри (8 або 10 символів)")

with col2:
    koatuu = st.text_input("КОАТУУ", placeholder="Наприклад: 0520885200")
    subject_name = st.text_input("ПІБ / Назва компанії", placeholder="Наприклад: ТОВ 'Зоря Поділля' або Коберник")

# Кнопка пошуку під блоком фільтрів
st.write("") # Невеликий відступ
search_btn = st.button("Знайти", type="primary")

st.markdown("---")

if search_btn:
    # Логіка для пошуку масиву ділянок (ЄДРПОУ, КОАТУУ або Назва)
    if edrpou or subject_name or koatuu:
        st.subheader("Знайдені ділянки")

        # Тимчасова таблиця-заглушка для демонстрації
        df = pd.DataFrame({
            "Кадастровий номер": ["0520885200:01:005:0813", "0520885200:01:005:0814"],
            "Площа (га)": [5.9457, 2.1234],
            "Цільове призначення": ["01.01", "01.01"],
            "Орендар / Власник": ["ТОВ 'Зоря Поділля'", "ТОВ 'Зоря Поділля'"]
        })

        # Відображення зручної таблиці
        st.dataframe(df, use_container_width=True, hide_index=True)

        st.info("Оберіть кадастровий номер зі списку нижче для перегляду детального досьє.")
        # Випадаючий список для вибору конкретної ділянки з результатів
        selected_cadastral = st.selectbox("Детальна інформація по ділянці:", df["Кадастровий номер"])
    else:
        # Якщо шукали конкретно один номер (і інші поля порожні)
        selected_cadastral = cadastral

    # Відображення досьє (ДЗК та ДРРП)
    if selected_cadastral:
        st.subheader(f"Досьє ділянки: {selected_cadastral}")
        tab_dzk, tab_drrp = st.tabs(["ДЗК (Державний земельний кадастр)", "ДРРП (Реєстр речових прав)"])

        with tab_dzk:
            st.write("Тут буде таблиця з площею, цільовим призначенням та експлікацією угідь.")
            st.write("Тут буде таблиця суб'єктів права з ДЗК.")

        with tab_drrp:
            st.write("Тут буде інформація про РНМ та стан реєстрації.")
            st.write("Тут буде таблиця з договорами оренди, строками дії та документами-підставами.")
