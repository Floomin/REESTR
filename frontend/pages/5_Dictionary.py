import requests
import streamlit as st

st.set_page_config(page_title="MDM Словник", page_icon="📖", layout="wide")

st.title("📖 MDM Словник: Нормалізація контрагентів")
st.markdown("Цей модуль сканує файли вивантажень, знаходить нові компанії та дозволяє додати їх до еталонного довідника перед імпортом у базу.")

API_URL = "http://127.0.0.1:8000/api/dictionary"

# Ініціалізація стану сесії
if "mdm_task_id" not in st.session_state:
    st.session_state["mdm_task_id"] = None
if "mdm_queue_type" not in st.session_state:
    st.session_state["mdm_queue_type"] = "standard"  # Може бути: 'standard', 'zero', 'done'

# --- ЕТАП 1: ЗАВАНТАЖЕННЯ ---
if not st.session_state["mdm_task_id"]:
    st.info("Завантажте JSON-файл для сканування нових контрагентів.")
    uploaded_file = st.file_uploader("Оберіть JSON файл", type=["json"])

    if uploaded_file is not None:
        if st.button("🚀 Почати сканування файлу", type="primary", width="stretch"):
            with st.spinner("Сканування файлу (це може зайняти кілька хвилин для файлів ~400 Мб)..."):
                try:
                    files = {"file": (uploaded_file.name, uploaded_file, "application/json")}
                    res = requests.post(f"{API_URL}/upload", files=files)

                    if res.status_code == 200:
                        data = res.json()
                        st.session_state["mdm_task_id"] = data["task_id"]
                        st.session_state["mdm_queue_type"] = "standard"
                        st.success(f"Сканування завершено! Знайдено нових суб'єктів для обробки: {data['found_new_subjects']}")
                        st.rerun()
                    else:
                        st.error(f"Помилка сканування: {res.text}")
                except Exception as e:
                    st.error(f"Помилка підключення до сервера: {e}")

# --- ЕТАП 2: WIZARD (ІНТЕРФЕЙС ПЕРЕВІРКИ) ---
if st.session_state["mdm_task_id"] and st.session_state["mdm_queue_type"] != "done":
    task_id = st.session_state["mdm_task_id"]

    # Кнопка аварійного скидання
    col_empty, col_reset = st.columns([4, 1])
    with col_reset:
        if st.button("🛑 Перервати сесію", width="stretch"):
            st.session_state["mdm_task_id"] = None
            st.rerun()

    st.markdown("---")

    # ЧЕРГА 1: СТАНДАРТНІ КОДИ
    if st.session_state["mdm_queue_type"] == "standard":
        # Запитуємо наступний запис
        res = requests.get(f"{API_URL}/queue/standard/{task_id}")
        if res.status_code == 200:
            data = res.json()
            if data.get("status") == "empty":
                st.success("🎉 Всі стандартні компанії успішно оброблено! Переходимо до проблемних кодів.")
                st.session_state["mdm_queue_type"] = "zero"
                st.rerun()
            else:
                code = data["code"]
                variants = data["variants"]
                remaining = data.get("remaining", 0)

                st.subheader(f"Крок 1/2: Компанії з існуючим кодом ЄДРПОУ ⏳ Залишилось: {remaining}")

                # Візуалізація картки
                st.info(f"**ЄДРПОУ / ІПН:** `{code}`")
                st.write("**Варіанти назв, знайдені у цьому файлі:**")
                for v in variants:
                    st.markdown(f"- {v}")

                # Форма для заповнення
                with st.form("standard_form", clear_on_submit=True):
                    default_name = variants[0] if variants else ""
                    std_name = st.text_input("Введіть або відредагуйте еталонну назву компанії:", value=default_name)

                    submit = st.form_submit_button("✅ Зберегти в довідник")

                    if submit:
                        if not std_name.strip():
                            st.error("Назва не може бути порожньою.")
                        else:
                            payload = {
                                "task_id": task_id,
                                "original_code": code,
                                "standard_name": std_name.strip()
                            }
                            post_res = requests.post(f"{API_URL}/resolve/standard", json=payload)
                            if post_res.status_code == 200:
                                st.rerun()
                            else:
                                st.error("Помилка при збереженні.")

    # ЧЕРГА 2: ПРОБЛЕМНІ КОДИ (00000000)
    elif st.session_state["mdm_queue_type"] == "zero":
        res = requests.get(f"{API_URL}/queue/zero/{task_id}")
        if res.status_code == 200:
            data = res.json()
            if data.get("status") == "empty":
                st.session_state["mdm_queue_type"] = "done"
                st.rerun()
            else:
                orig_name = data["original_name"]
                remaining = data.get("remaining", 0)

                st.subheader(f"Крок 2/2: Проблемні записи ⏳ Залишилось: {remaining}")

                # Візуалізація картки
                st.warning("⚠️ Запис без валідного коду ЄДРПОУ. Необхідно ідентифікувати компанію.")
                st.write(f"**Назва в реєстрі:** `{orig_name}`")

                with st.form("zero_form", clear_on_submit=True):
                    new_code = st.text_input("1. Введіть справжній код ЄДРПОУ / ІПН:")
                    std_name = st.text_input("2. Введіть еталонну назву компанії:", value=orig_name)

                    submit = st.form_submit_button("✅ Зберегти та створити правило заміни")

                    if submit:
                        if not new_code.strip() or not std_name.strip():
                            st.error("Обидва поля (Код і Назва) є обов'язковими для заповнення.")
                        else:
                            payload = {
                                "task_id": task_id,
                                "original_name": orig_name,
                                "new_code": new_code.strip(),
                                "standard_name": std_name.strip()
                            }
                            post_res = requests.post(f"{API_URL}/resolve/zero", json=payload)
                            if post_res.status_code == 200:
                                st.rerun()
                            else:
                                st.error("Помилка при збереженні.")

# --- ЕТАП 3: ФІНАЛ ---
if st.session_state["mdm_queue_type"] == "done":
    st.success("✅ Словник оновлено! Усі нові суб'єкти додані до еталонної бази, а правила заміни сформовані.")
    st.balloons()

    if st.button("Завершити та підготувати новий файл", type="primary", width="stretch"):
        st.session_state["mdm_task_id"] = None
        st.session_state["mdm_queue_type"] = "standard"
        st.rerun()
