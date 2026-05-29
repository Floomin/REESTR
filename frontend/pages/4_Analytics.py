import pandas as pd
import requests
import streamlit as st

if "role" not in st.session_state:
    st.warning("⛔ Будь ласка, авторизуйтесь на головній сторінці.")
    st.stop()

st.set_page_config(page_title="Аналітика", layout="wide")
st.title("📊 Аналітика земельного банку")

# Створюємо дві головні вкладки
tab_koatuu, tab_company = st.tabs(["📍 По сільських радах (КОАТУУ)", "🏢 По юридичних особах"])

# ==========================================
# ВКЛАДКА 1: ПО СІЛЬСЬКИХ РАДАХ
# ==========================================
with tab_koatuu:
    st.markdown("### Аналіз територій")

    # Фільтри для першої вкладки
    col_f1, col_f2 = st.columns(2)
    with col_f1:
        koatuu_filter = st.text_input("Код КОАТУУ (Сільська рада):", placeholder="Пошук по території...", key="k_filter")
    with col_f2:
        company_filter = st.text_input("ЄДРПОУ / Назва (Перехресний фільтр):", placeholder="Аналіз конкретної компанії в цій раді...", key="c_filter")

    if st.button("🚀 Згенерувати звіт", key="btn_koatuu", type="primary"):
        with st.spinner("Збір та агрегація даних..."):
            try:
                params = {}
                if koatuu_filter:
                    params["koatuu"] = koatuu_filter.strip()
                if company_filter:
                    params["company"] = company_filter.strip()

                res = requests.get("http://127.0.0.1:8000/api/analytics/koatuu", params=params)

                if res.status_code == 200:
                    data = res.json()
                    kpi = data["kpi"]

                    # --- БЛОК 1: Основні KPI ---
                    st.markdown("#### 📈 Ключові показники (KPI)")
                    c1, c2, c3, c4 = st.columns(4)
                    c1.metric("Загальна площа", f"{kpi['total_area']} га", f"{kpi['total_plots']} ділянок")
                    c2.metric("Площа в оренді", f"{kpi['leased_area']} га")

                    # Виділяємо вільний запас кольором (якщо він є)
                    free_area = kpi['owned_not_leased']
                    c3.metric("У власності (НЕ в оренді)", f"{free_area} га", "Вільний запас" if free_area > 0 else None)
                    c4.metric("Середнє НГО", f"{kpi['avg_ngo_per_ha']} грн/га")

                    st.markdown("---")
                    c5, c6, c7 = st.columns(3)
                    c5.metric("Середній рік завершення", kpi['avg_end_year'] or "Немає даних")
                    c6.metric("Площа з автопролонгацією", f"{kpi['auto_prolong_area']} га")

                    # Ризикова зона
                    arrested = kpi['arrested_area']
                    c7.metric("Під обтяженнями / Арештами", f"{arrested} га", "Ризик!" if arrested > 0 else None, delta_color="inverse")

                    st.markdown("---")

                    # --- БЛОК 2: Графік та Топ компаній ---
                    col_chart, col_table = st.columns([3, 2])

                    with col_chart:
                        st.markdown("#### 📅 Розподіл завершення договорів по роках")
                        if data["lease_years"]:
                            df_years = pd.DataFrame(data["lease_years"])
                            df_years.set_index("year", inplace=True)
                            # Малюємо стовпчикову діаграму по площі
                            st.bar_chart(df_years["area"], height=350, use_container_width=True)
                        else:
                            st.info("Немає даних про дати завершення оренди.")

                    with col_table:
                        st.markdown("#### 🏆 Найбільші користувачі в раді")
                        if data["top_lessees"]:
                            df_top = pd.DataFrame(data["top_lessees"])
                            df_top.columns = ["Орендар", "ЄДРПОУ", "Площа (га)", "Ділянок"]
                            st.dataframe(df_top, use_container_width=True, hide_index=True)
                        else:
                            st.info("Орендарів не знайдено.")

                else:
                    st.error(f"Помилка сервера: {res.text}")
            except Exception as e:
                st.error(f"Помилка підключення: {e}")

# ==========================================
# ВКЛАДКА 2: ПО ЮРИДИЧНИХ ОСОБАХ (Заглушка)
# ==========================================
with tab_company:
    st.info("Тут буде реалізована аналітика по компаніях (з фільтром по КОАТУУ).")
