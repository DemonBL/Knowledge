"""ЛР16 · веб-інтерфейс демонстратора (Streamlit): рекомендації з поясненнями, холодний старт, пошук, агент, SPARQL.
  streamlit run lab16/ui/app.py   (API_URL — адреса API, за замовчуванням http://127.0.0.1:8000)
"""
import json
import os

import requests
import streamlit as st

API = os.environ.get("API_URL", "http://127.0.0.1:8000")
st.set_page_config(page_title="Domain Knowledge Hub · ЛР16", layout="wide")
st.title("Domain Knowledge Hub — аналіз достовірності інформації")
st.caption("ЛР16 · рекомендації з поясненнями зі шляхів графа, агент ЛР15, граф знань. Дані користувачів — синтетичні.")

try:
    h = requests.get(API + "/health", timeout=5).json()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Фрагментів", h["items"])
    c2.metric("Взаємодій", h["interactions"])
    c3.metric("Граф (трійок)", h.get("graph", {}).get("triples", "—"))
    c4.metric("LLM", h.get("llm", {}).get("status", "—"))
except Exception as e:  # noqa
    st.error(f"API недоступне за {API}: {e}")
    st.stop()

tab1, tab2, tab3, tab4 = st.tabs(["Рекомендації", "Холодний старт", "Запитати агента", "Пошук і SPARQL"])


def show_items(res):
    st.caption(f"роль: **{res['role']}** · сценарій: {res['scenario']} · ембединги: {res['embeddings']} · {res['latency_ms']} мс"
               + (" · ⚠ заявлену роль проігноровано" if res.get("role_claim_ignored") else ""))
    for n, it in enumerate(res["items"], 1):
        with st.container(border=True):
            st.markdown(f"**{n}. {it['title']}** — {it['section']}  \n`{it['item_id']}` · {it['date']} · {it['sensitivity']}")
            e = it["explanation"]
            st.write(e["text"])
            if e["path"]:
                st.caption("шлях: " + " → ".join(e["path"]) + ("  ✓ перевірено" if e["check_ok"] else "  ✗ не пройшло перевірку"))


with tab1:
    c1, c2, c3 = st.columns(3)
    uid = c1.text_input("ID користувача", "U010")
    role = c2.selectbox("Заявлена роль", ["analyst", "guest", "admin"])
    k = c3.slider("Кількість", 3, 10, 5)
    c4, c5 = st.columns(2)
    fresh = c4.number_input("Свіжість, днів (0 — без обмеження)", 0, 2000, 0)
    ver = c5.checkbox("Лише перевірені", True)
    if st.button("Рекомендувати"):
        r = requests.post(API + "/recommend", json={"user_id": uid, "role": role, "k": k, "fresh_days": fresh or None,
                                                    "require_verified": ver}, timeout=30).json()
        show_items(r)

with tab2:
    topics = list(requests.get(API + "/topics", timeout=5).json())
    sel = st.multiselect("Оберіть теми інтересу", topics, default=["фото й метадані"])
    if st.button("Рекомендувати новому користувачу"):
        show_items(requests.post(API + "/recommend", json={"interests": sel, "role": "guest", "k": 5}, timeout=30).json())

with tab3:
    q = st.text_area("Питання", "Коли засновано StopFake?")
    r2 = st.selectbox("Роль", ["analyst", "guest", "admin"], key="ask_role")
    if st.button("Запитати"):
        with st.spinner("агент працює (локальна LLM)…"):
            resp = requests.post(API + "/ask", json={"question": q, "role": r2}, timeout=600)
        if resp.ok:
            d = resp.json()
            st.info("Відповідь згенеровано ШІ (локальна модель через Ollama) і перевірено верифікатором цитат; перевіряйте джерела [id].")
            st.markdown(d["answer"])
            st.caption(f"статус: {d['status']} · інструменти: {d['tools_used']} · {d['latency_s']} с")
            if d.get("blocked"):
                st.warning("Заблоковано політиками: " + json.dumps(d["blocked"], ensure_ascii=False))
        else:
            st.error(resp.json().get("detail"))

with tab4:
    q = st.text_input("Пошук документів", "дипфейк перевірка")
    if st.button("Шукати"):
        st.json(requests.post(API + "/search", json={"query": q, "role": "guest"}, timeout=30).json())
    sp = st.text_area("SPARQL (лише SELECT)", "PREFIX hub: <http://www.lnu.edu.ua/kb/hub#>\nSELECT ?n ?name WHERE { ?n hub:name ?name } LIMIT 10")
    if st.button("Виконати SPARQL"):
        resp = requests.post(API + "/sparql", data=sp.encode("utf-8"), timeout=30)
        st.json(resp.json())
