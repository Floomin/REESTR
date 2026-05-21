import streamlit as st

if "role" not in st.session_state:
    st.warning("⛔ Будь ласка, авторизуйтесь на головній сторінці.")
    st.stop() # Зупиняє подальше виконання коду на сторінці
