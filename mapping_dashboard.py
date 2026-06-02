import json

import pandas as pd
import streamlit as st

st.set_page_config(layout="wide", page_title="Data Mapping Architect")

st.title("Архитектура маппинга: JSON -> MS SQL")
st.markdown("Интерфейс для визуального анализа структур данных и проектирования репозиториев.")

# Сайдбар для загрузки файлов или выбора готовых
st.sidebar.header("Исходные данные")
uploaded_csv = st.sidebar.file_uploader("Загрузи json_schema_analysis1.csv", type=["csv"])
uploaded_txt = st.sidebar.file_uploader("Загрузи структура БД MS SQL.txt", type=["txt"])
uploaded_json = st.sidebar.file_uploader("Загрузи пример реального JSON (опционально)", type=["json"])

col1, col2 = st.columns(2)

with col1:
    st.subheader("📦 Структура JSON")
    if uploaded_csv is not None:
        # Читаем CSV со схемой JSON
        df_json = pd.read_csv(uploaded_csv)

        # Добавляем фильтр по пути для удобства (например, чтобы смотреть только RrpAdvanced)
        search_path = st.text_input("Поиск по пути (path):", value="RrpAdvanced")
        if search_path:
            df_json = df_json[df_json['path'].str.contains(search_path, case=False, na=False)]

        st.dataframe(df_json, use_container_width=True, height=600)
    else:
        st.info("Загрузи файл json_schema_analysis1.csv в панели слева.")

    if uploaded_json is not None:
        st.markdown("---")
        st.subheader("📄 Пример сырого JSON")
        raw_data = json.load(uploaded_json)
        st.json(raw_data, expanded=False)

with col2:
    st.subheader("🗄 Структура БД (MS SQL)")
    if uploaded_txt is not None:
        # Читаем TXT файл. Предполагаем, что он разделен табуляцией (судя по твоему формату)
        try:
            df_sql = pd.read_csv(uploaded_txt, sep="\t")

            # Фильтр по названию таблицы
            search_table = st.text_input("Поиск по таблице (TableName):", value="Rrp")
            if search_table and 'TableName' in df_sql.columns:
                df_sql = df_sql[df_sql['TableName'].str.contains(search_table, case=False, na=False)]

            st.dataframe(df_sql, use_container_width=True, height=600)
        except Exception as e:
            st.error(f"Ошибка чтения файла БД: {e}. Проверь формат разделителей (ожидается Tab).")
            # Если файл не читается как таблица, выводим как текст
            uploaded_txt.seek(0)
            st.text_area("Сырой текст схемы БД", uploaded_txt.read().decode('utf-8'), height=600)
    else:
        st.info("Загрузи файл структура БД MS SQL.txt в панели слева.")
