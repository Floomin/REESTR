import pandas as pd
import requests
import streamlit as st

st.set_page_config(page_title="Пошук", layout="wide")

if "role" not in st.session_state:
    st.warning("⛔ Будь ласка, авторизуйтесь на головній сторінці.")
    st.stop()

st.title("Пошук по реєстрах")
st.markdown("---")

st.subheader("Параметри пошуку")

col1, col2 = st.columns(2)

with col1:
    cadastral = st.text_input("Кадастровий номер", placeholder="Наприклад: 0520885200:01:005:0813")
    edrpou = st.text_input("ЄДРПОУ / ІПН", placeholder="Тільки цифри (8 або 10 символів)")

with col2:
    koatuu = st.text_input("КОАТУУ", placeholder="Наприклад: 0520885200")
    subject_name = st.text_input("ПІБ / Назва компанії", placeholder="Наприклад: ТОВ 'Зоря Поділля'")

st.write("")
search_btn = st.button("Знайти", type="primary")

st.markdown("---")

# Функція для відправки запиту на сервер
def fetch_data(page_num):
    limit = 1000
    offset = page_num * limit

    params = st.session_state["search_params"]
    params["limit"] = limit
    params["offset"] = offset

    with st.spinner("Завантаження даних..."):
        try:
            res = requests.get("http://127.0.0.1:8000/api/search/list", params=params)
            if res.status_code == 200:
                data = res.json()
                st.session_state["search_results"] = data.get("data", [])
                st.session_state["total_count"] = data.get("total", 0)
                st.session_state["current_page"] = page_num
            else:
                st.error("Помилка сервера при пошуку.")
        except Exception as e:
            st.error(f"Помилка підключення: {e}")

# 1. Логіка першого пошуку (натискання кнопки Знайти)
if search_btn:
    if not (cadastral or edrpou or koatuu or subject_name):
        st.warning("Будь ласка, введіть хоча б один параметр для пошуку.")
    else:
        # Зберігаємо параметри пошуку в сесію, щоб при перегортанні сторінок вони не губилися
        st.session_state["search_params"] = {
            "user_id": st.session_state["user_id"],
            "cadastral": cadastral,
            "edrpou": edrpou,
            "koatuu": koatuu,
            "subject_name": subject_name
        }
        st.session_state["search_params"] = {k: v for k, v in st.session_state["search_params"].items() if v}
        fetch_data(0) # Завантажуємо першу сторінку

# 2. Відображення результатів та пагінації
selected_cadastral = None

if "search_results" in st.session_state:
    data = st.session_state["search_results"]
    total = st.session_state["total_count"]
    current_page = st.session_state["current_page"]

    if not data:
        st.info("За вашим запитом нічого не знайдено.")
    else:
        # Панель інформації та пагінації
        col_info, col_prev, col_next = st.columns([2, 1, 1])

        start_idx = current_page * 1000 + 1
        end_idx = min((current_page + 1) * 1000, total)

        with col_info:
            st.subheader(f"Знайдено ділянок: {total}")
            st.write(f"Показано записи {start_idx} - {end_idx}")

        with col_prev:
            if current_page > 0:
                if st.button("⬅️ Попередні 1000", width="stretch"):
                    fetch_data(current_page - 1)
                    st.rerun()

        with col_next:
            if end_idx < total:
                if st.button("Наступні 1000 ➡️", width="stretch"):
                    fetch_data(current_page + 1)
                    st.rerun()

        # Виводимо таблицю
        df = pd.DataFrame(data)
        df_display = df.rename(columns={
            "CadastralNumber": "Кадастровий номер",
            "Koatuu": "КОАТУУ",
            "Area": "Площа (га)"
        })
        df_display = df_display.fillna("—")
        st.dataframe(df_display, width="stretch", hide_index=True)

        st.info("Оберіть кадастровий номер зі списку нижче для перегляду детального досьє.")
        selected_cadastral = st.selectbox(
            "Детальна інформація по ділянці:",
            df["CadastralNumber"],
            key="cadastral_selector"
        )

# 3. Завантаження та відображення досьє
if selected_cadastral:
    st.markdown("---")
    st.subheader(f"Досьє ділянки: {selected_cadastral}")

    with st.spinner("Завантаження досьє..."):
        try:
            dossier_res = requests.get(f"http://127.0.0.1:8000/api/search/dossier/{selected_cadastral}")
            if dossier_res.status_code == 200:
                dossier = dossier_res.json()

                tab_dzk, tab_drrp = st.tabs(["ДЗК (Державний земельний кадастр)", "ДРРП (Реєстр речових прав)"])

                with tab_dzk:
                    history = dossier.get("history", [])

                    if not history:
                        st.info("Дані ДЗК відсутні для цієї ділянки.")
                    else:
                        st.write("### Історія змін за даними ДЗК")

                        import re

                        # Функція для звичайних текстових значень
                        def format_val(val):
                            if val is None or str(val).strip() == "" or str(val).strip().lower() in ["none", "null"]:
                                return "Інформація відсутня"
                            return str(val)

                        # Нова функція спеціально для дат
                        def format_date(val):
                            if val is None or str(val).strip() == "" or str(val).strip().lower() in ["none", "null"]:
                                return "Інформація відсутня"

                            val_str = str(val).strip()
                            # Шукаємо шаблон YYYY-MM-DD (з опціональним часом після нього)
                            match = re.match(r"^(\d{4})-(\d{2})-(\d{2})(.*)$", val_str)
                            if match:
                                year, month, day, rest = match.groups()
                                # Повертаємо у форматі ДД.ММ.РРРР
                                return f"{day}.{month}.{year}{rest}"
                            return val_str

                        # Цикл по всім історичним зрізам
                        for idx, slice_data in enumerate(history):
                            is_expanded = (idx == 0)

                            # Використовуємо format_date для дати запиту (переверне дату і залишить час)
                            title = f"Дата запиту: {format_date(slice_data['checked_at'])}"
                            if idx == 0:
                                title += " (Найсвіжіші дані)"

                            with st.expander(title, expanded=is_expanded):
                                snap = slice_data["snapshot"]

                                # БЛОК 1
                                st.markdown("#### Відомості про земельну ділянку")
                                st.write(f"**Кадастровий номер земельної ділянки:** {format_val(snap.get('CadastralNumber'))}")
                                st.write(f"**Цільове призначення:** {format_val(snap.get('Purpose'))}")

                                area_val = format_val(snap.get('Area'))
                                st.write(f"**Площа земельної ділянки:** {f'{area_val} га' if area_val != 'Інформація відсутня' else area_val}")
                                st.write(f"**Місце розташування:** {format_val(snap.get('Location'))}")

                                st.markdown("---")

                                # БЛОК 2
                                st.markdown("#### Відомості про суб'єктів права власності на земельну ділянку")
                                if slice_data["ownerships"]:
                                    for i, own in enumerate(slice_data["ownerships"]):
                                        subject_name = str(own.get("NameFo") or "") + " " + str(own.get("NameUo") or "")
                                        st.write(f"**Вид речового права:** {format_val(own.get('OwnershipType'))}")
                                        st.write(f"**Прізвище, ім'я та по батькові / Найменування:** {format_val(subject_name)}")
                                        st.write(f"**Код ЄДРПОУ / ІПН:** {format_val(own.get('Edrpou'))}")
                                        # Використовуємо format_date
                                        st.write(f"**Дата державної реєстрації права:** {format_date(own.get('DateRegRight'))}")
                                        st.write(f"**Номер запису про право:** {format_val(own.get('EntryRecordNumber'))}")
                                        st.write(f"**Орган, що здійснив державну реєстрацію права:** {format_val(own.get('RegAuthority'))}")

                                        if i < len(slice_data["ownerships"]) - 1:
                                            st.write("")
                                else:
                                    st.write("Дані про власників відсутні.")

                                st.markdown("---")

                                # БЛОК 3
                                st.markdown("#### Відомості про суб'єкта речового права на земельну ділянку")
                                if slice_data["real_rights"]:
                                    for i, right in enumerate(slice_data["real_rights"]):
                                        subject_name = str(right.get("NameFo") or "") + " " + str(right.get("NameUo") or "")
                                        st.write(f"**Вид речового права:** {format_val(right.get('PropertyRight'))}")
                                        st.write(f"**Прізвище, ім'я та по батькові / Найменування:** {format_val(subject_name)}")
                                        st.write(f"**Код ЄДРПОУ / ІПН:** {format_val(right.get('Edrpou'))}")
                                        # Використовуємо format_date
                                        st.write(f"**Дата державної реєстрації права:** {format_date(right.get('DateRegRight'))}")
                                        st.write(f"**Номер запису про право:** {format_val(right.get('EntryRecordNumber'))}")
                                        st.write(f"**Орган, що здійснив державну реєстрацію права:** {format_val(right.get('RegAuthority'))}")

                                        if i < len(slice_data["real_rights"]) - 1:
                                            st.write("")
                                else:
                                    st.write("Дані про речові права відсутні.")

                                st.markdown("---")

                                # БЛОК 4
                                st.markdown("#### Відомості про зареєстроване обмеження у використанні земельної ділянки")
                                if slice_data["restrictions"]:
                                    for i, rest in enumerate(slice_data["restrictions"]):
                                        r_type = format_val(rest.get('RestrictionType'))
                                        r_code = format_val(rest.get('RestrictionCode'))

                                        if r_code != "Інформація відсутня":
                                            st.write(f"**Вид обмеження:** {r_type} (Код: {r_code})")
                                        else:
                                            st.write(f"**Вид обмеження:** {r_type}")

                                        # Використовуємо format_date
                                        st.write(f"**Дата державної реєстрації обмеження:** {format_date(rest.get('RegistrationDate'))}")

                                        if i < len(slice_data["restrictions"]) - 1:
                                            st.write("")
                                else:
                                    st.write("Зареєстровані обмеження відсутні.")

                with tab_drrp:
                    history = dossier.get("history", [])
                    has_rrp_data = any(slice_data.get("rrp") for slice_data in history)

                    if not has_rrp_data:
                        st.info("Дані ДРРП відсутні для цієї ділянки.")
                    else:
                        st.write("### Історія змін за даними ДРРП")

                        # Допоміжна функція для рендерингу документів-підстав
                        def render_documents(docs):
                            if not docs:
                                return "Інформація відсутня"

                            doc_blocks = []
                            for d in docs:
                                parts = []

                                # Тип документу (головний рівень)
                                cd_type = format_val(d.get('CdType'))
                                main_title = cd_type if cd_type != "Інформація відсутня" else "Документ"

                                # Атрибути документу (вкладений рівень)
                                if d.get('DocNumber') and str(d.get('DocNumber')).strip() not in ["", "None", "null"]:
                                    parts.append(f"серія та номер: {d.get('DocNumber')}")
                                if d.get('DocDate') and str(d.get('DocDate')).strip() not in ["", "None", "null"]:
                                    parts.append(f"виданий {format_date(d.get('DocDate'))}")
                                if d.get('Publisher') and str(d.get('Publisher')).strip() not in ["", "None", "null"]:
                                    parts.append(f"видавник: {d.get('Publisher')}")

                                # Збираємо блок для одного документу
                                if parts:
                                    sub_items = "\n".join([f"    * {p}" for p in parts])
                                    doc_blocks.append(f"- **{main_title}**\n{sub_items}")
                                else:
                                    doc_blocks.append(f"- **{main_title}**")

                            # Streamlit (через Markdown) автоматично відрендерить це як дворівневий список
                            return "\n" + "\n".join(doc_blocks)

                        for idx, slice_data in enumerate(history):
                            rrp = slice_data.get("rrp")
                            if not rrp:
                                continue # Пропускаємо, якщо в цьому зрізі немає ДРРП

                            is_expanded = (idx == 0)

                            title = f"Дата запиту: {format_date(slice_data['checked_at'])}"
                            if idx == 0:
                                title += " (Найсвіжіші дані)"

                            with st.expander(title, expanded=is_expanded):
                                # БЛОК 1: Об'єкт нерухомого майна
                                st.markdown("#### Актуальна інформація про об’єкт нерухомого майна:")
                                st.write(f"**Реєстраційний номер об’єкта нерухомого майна:** {format_val(rrp.get('RegistrationNumber', rrp.get('RealtyNumber')))}")

                                re_type = format_val(rrp.get('ReType'))
                                full_area = format_val(rrp.get('FullArea'))
                                obj_desc = f"{re_type}, площа: {full_area}" if full_area != "Інформація відсутня" else re_type
                                st.write(f"**Об’єкт нерухомого майна:** {obj_desc}")

                                st.write(f"**Дата державної реєстрації:** {format_date(rrp.get('RegistrationDate'))}")
                                st.write(f"**Опис об’єкта / Адреса:** {format_val(rrp.get('RealtyAddress'))}")

                                st.markdown("---")

                                # БЛОК 2: Право власності
                                st.markdown("#### Актуальна інформація про право власності:")
                                if rrp.get("property_rights"):
                                    for i, pr in enumerate(rrp["property_rights"]):
                                        st.write(f"**Номер запису про право власності:** {format_val(pr.get('RegistrationNumber'))}")
                                        st.write(f"**Тип права власності:** {format_val(pr.get('RightType'))}")
                                        st.write(f"**Дата, час державної реєстрації:** {format_date(pr.get('RegistrationDate'))}")
                                        st.write(f"**Державний реєстратор:** {format_val(pr.get('Registrar'))}")
                                        st.write(f"**Підстава виникнення права власності:** {render_documents(pr.get('documents'))}")
                                        st.write(f"**Розмір частки:** {format_val(pr.get('PartSize'))}")

                                        owner_text = f"{format_val(pr.get('SubjectName'))} (ЄДРПОУ/ІПН: {format_val(pr.get('SubjectCode'))})"
                                        st.write(f"**Власники:** {owner_text}")
                                        st.write(f"**Стан:** {format_val(pr.get('PrState'))}")
                                        if i < len(rrp["property_rights"]) - 1:
                                            st.write("")
                                else:
                                    st.write("Відомості про право власності відсутні.")

                                st.markdown("---")

                                # БЛОК 3: Інші речові права
                                st.markdown("#### Відомості про інші речові права:")
                                if rrp.get("other_rights"):
                                    for i, oright in enumerate(rrp["other_rights"]):
                                        st.write(f"**Номер запису про інше речове право:** {format_val(oright.get('RegistrationNumber'))}")
                                        st.write(f"**Вид іншого речового права:** {format_val(oright.get('RightType', oright.get('IrpSort')))}")
                                        st.write(f"**Дата, час державної реєстрації:** {format_date(oright.get('RegistrationDate'))}")
                                        st.write(f"**Державний реєстратор:** {format_val(oright.get('Registrar'))}")
                                        st.write(f"**Підстава для державної реєстрації:** {render_documents(oright.get('documents'))}")

                                        sbj_text = f"{format_val(oright.get('SubjectName'))} (ЄДРПОУ/ІПН: {format_val(oright.get('SubjectCode'))})"
                                        st.write(f"**Відомості про суб’єктів:** {sbj_text}")

                                        # Формуємо строк дії
                                        term_str = f"з {format_date(oright.get('StartDate'))} по {format_date(oright.get('EndDate'))}"
                                        if oright.get('ContractTerm'):
                                            term_str += f" ({oright.get('ContractTerm')})"
                                        st.write(f"**Строк дії:** {term_str}")

                                        prolongation = "Так" if oright.get('IsAutomaticProlongation') else "Ні"
                                        st.write(f"**Ознака «З правом пролонгації»:** {prolongation}")
                                        st.write(f"**Опис предмета іншого речового права:** {format_val(oright.get('ObjectDescription'))}")
                                        if i < len(rrp["other_rights"]) - 1:
                                            st.write("")
                                else:
                                    st.write("Відомості про інші речові права відсутні.")

                                st.markdown("---")

                                # БЛОК 4: Іпотека
                                st.markdown("#### Відомості про державну реєстрацію іпотеки:")
                                if rrp.get("mortgages"):
                                    for i, mort in enumerate(rrp["mortgages"]):
                                        st.write(f"**Номер запису про іпотеку:** {format_val(mort.get('RegistrationNumber'))}")
                                        st.write(f"**Дата державної реєстрації:** {format_date(mort.get('RegistrationDate'))}")
                                        st.write(f"**Вид іпотеки:** {format_val(mort.get('MortgageType'))}")
                                        st.write(f"**Суб’єкт:** {format_val(mort.get('SubjectName'))} (Код: {format_val(mort.get('SubjectCode'))})")
                                        st.write(f"**Опис предмета:** {format_val(mort.get('ObjectDescription'))}")
                                        st.write(f"**Стан:** {format_val(mort.get('PrState'))}")
                                        if i < len(rrp["mortgages"]) - 1:
                                            st.write("")
                                else:
                                    st.write("Відомості про державну реєстрацію іпотеки відсутні.")

                                st.markdown("---")

                                # БЛОК 5: Обтяження
                                st.markdown("#### Відомості про державну реєстрацію обтяжень:")
                                if rrp.get("limitations"):
                                    for i, lim in enumerate(rrp["limitations"]):
                                        st.write(f"**Номер запису про обтяження:** {format_val(lim.get('RegistrationNumber'))}")
                                        st.write(f"**Дата державної реєстрації:** {format_date(lim.get('RegistrationDate'))}")
                                        st.write(f"**Вид обтяження:** {format_val(lim.get('LimitationType'))}")
                                        st.write(f"**Суб’єкт:** {format_val(lim.get('SubjectName'))} (Код: {format_val(lim.get('SubjectCode'))})")
                                        st.write(f"**Опис обтяження:** {format_val(lim.get('ObjectDescription'))}")
                                        st.write(f"**Стан:** {format_val(lim.get('LmState'))}")
                                        if i < len(rrp["limitations"]) - 1:
                                            st.write("")
                                else:
                                    st.write("Відомості про державну реєстрацію обтяжень відсутні.")
            else:
                st.error("Не вдалося завантажити досьє.")
        except Exception as e:
            st.error(f"Помилка підключення: {e}")
