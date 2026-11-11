"""ЛР16 · Р5 — whitepaper Domain Knowledge Hub: HTML → PDF (Chromium/Playwright). Числа ЛР16 беруться з results/*.json.
  python whitepaper/build_whitepaper.py  → docs/whitepaper.html, docs/whitepaper.pdf
"""
from __future__ import annotations

import base64
import csv
import html
import json
import subprocess
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
RES, IMG, DOCS = LAB / "results", LAB / "docs" / "img", LAB / "docs"


def J(name):
    p = RES / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def n(x, d=3):
    return f"{x:.{d}f}".replace(".", ",")


def img(name, width="100%"):
    b = base64.b64encode((IMG / name).read_bytes()).decode()
    return f'<img src="data:image/png;base64,{b}" style="width:{width}">'


UI_IMG = 'ui_demo.png' if (IMG / 'ui_demo.png').exists() else 'ui_reco.png'
EV = J("reco_eval_e5.json") or J("reco_eval_lsa.json")
EMB = EV["emb"]
S = EV["summary"]
CS = J(f"cold_start_{EMB}.json") or J("cold_start_lsa.json")
EX = J("explanations.json")
PA = J(f"paired_{EMB}.json")
W_BEST = ", ".join("(" + "; ".join(n(abs(x), 1) for x in r["w_best"]) + ")" for r in EV["runs"])
DR = J("docker_run.json") or {}
DEMO = None
if (LAB / "demo" / "demo_run.json").exists():
    DEMO = json.loads((LAB / "demo" / "demo_run.json").read_text(encoding="utf-8"))

import sys  # noqa: E402
sys.path.insert(0, str(Path(__file__).parent))
import lab_metrics  # noqa: E402
lab_metrics.make(S["popularity"]["ndcg10"]["mean"], S["hybrid_rrf"]["ndcg10"]["mean"])

ex_s = EX["summary"]
llm_ok = ex_s.get("llm_correct")
A, B = CS["new_user"]["summary"], CS["new_doc"]["summary"]
rrf, pop, gr, em, hw = (S[c] for c in ("hybrid_rrf", "popularity", "graph", "embeddings", "hybrid_weighted"))
demo_line = (f"Автоматичний прогін сценарію демонстрації пройшов {DEMO['passed']} кроків" if DEMO else "Сценарій демонстрації прогнано автоматично")
build_line = ""
if DR.get("build_s") is not None:
    build_line = (f"Запуск з нуля на ПК студента (Docker {DR.get('docker_server', '?')}): збірка образу {n(DR['build_s'] / 60, 1)} хв, "
                  f"підйом трьох сервісів до стану healthy — {n(DR.get('up_s', 0) + DR.get('health_wait_s', 0), 0)} с; образ {DR.get('image', '').split(' ')[-1]}.")

CLAIMS = list(csv.DictReader(open(LAB / "claims" / "claims.csv", encoding="utf-8")))

ARCH = """<svg viewBox="0 0 760 300" xmlns="http://www.w3.org/2000/svg" font-family="Liberation Sans" font-size="11">
<defs><marker id="a" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#555"/></marker></defs>
<g fill="#f3f6fb" stroke="#2a78d6" stroke-width="1.2">
<rect x="10" y="20" width="170" height="260" rx="6"/><rect x="215" y="20" width="250" height="260" rx="6"/><rect x="500" y="20" width="250" height="260" rx="6"/></g>
<g font-weight="bold" fill="#1f3f73"><text x="20" y="40">Джерела й обробка (ЛР3–14)</text><text x="225" y="40">Сховище знань (гібридне)</text><text x="510" y="40">Доступ і застосування (ЛР11–16)</text></g>
<g fill="#fff" stroke="#999"><rect x="22" y="55" width="146" height="40" rx="4"/><rect x="22" y="105" width="146" height="40" rx="4"/><rect x="22" y="155" width="146" height="40" rx="4"/><rect x="22" y="205" width="146" height="58" rx="4"/>
<rect x="228" y="55" width="224" height="40" rx="4"/><rect x="228" y="105" width="224" height="40" rx="4"/><rect x="228" y="155" width="224" height="40" rx="4"/><rect x="228" y="205" width="224" height="58" rx="4"/>
<rect x="512" y="55" width="226" height="40" rx="4"/><rect x="512" y="105" width="226" height="40" rx="4"/><rect x="512" y="155" width="226" height="40" rx="4"/><rect x="512" y="205" width="226" height="58" rx="4"/></g>
<g fill="#222"><text x="30" y="72">Онтологія, таксономія</text><text x="30" y="87" fill="#666">ЛР3–8: OWL, SKOS, SHACL</text>
<text x="30" y="122">Корпус 36 док., 529 фрагм.</text><text x="30" y="137" fill="#666">ЛР10: очищення, chunking</text>
<text x="30" y="172">Витяг знань (IE)</text><text x="30" y="187" fill="#666">ЛР13: правила + LLM</text>
<text x="30" y="222">Якість і ER</text><text x="30" y="237" fill="#666">ЛР14: 19 перевірок gate,</text><text x="30" y="252" fill="#666">реєстр сутностей, провенанс</text>
<text x="236" y="72">Граф розслідувань (LPG/RDF)</text><text x="236" y="87" fill="#666">ЛР9/14: Neo4j · 8322 трійки RDF</text>
<text x="236" y="122">Індекс документів</text><text x="236" y="137" fill="#666">ЛР10: BM25 + e5 + RRF, RBAC</text>
<text x="236" y="172">OLAP-куб і семантичний шар</text><text x="236" y="187" fill="#666">ЛР12: DuckDB, 7 метрик</text>
<text x="236" y="222">Граф рекомендацій</text><text x="236" y="237" fill="#666">ЛР16: фрагмент–сутність–документ,</text><text x="236" y="252" fill="#666">1 899 ребер + журнали взаємодій</text>
<text x="520" y="72">RAG-чат з цитуванням</text><text x="520" y="87" fill="#666">ЛР11: «не знаю», API з ключами</text>
<text x="520" y="122">Агент LangGraph + MCP</text><text x="520" y="137" fill="#666">ЛР15: 3 інструменти read-only, HITL</text>
<text x="520" y="172">Рекомендації з поясненнями</text><text x="520" y="187" fill="#666">ЛР16: граф + e5 + популярність, RRF</text>
<text x="520" y="222">Демонстратор (Docker Compose)</text><text x="520" y="237" fill="#666">graph · api (FastAPI) · ui (Streamlit)</text><text x="520" y="252" fill="#666">LLM qwen2.5:7b локально (Ollama)</text></g>
<g stroke="#555" stroke-width="1.2" marker-end="url(#a)"><line x1="168" y1="150" x2="226" y2="150"/><line x1="452" y1="150" x2="510" y2="150"/></g>
</svg>"""


def table(head, rows, cls=""):
    h = "".join(f"<th>{x}</th>" for x in head)
    b = "".join("<tr>" + "".join(f"<td>{x}</td>" for x in r) + "</tr>" for r in rows)
    return f'<table class="{cls}"><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table>'


reco_tab = table(["Конфігурація", "P@5", "R@5", "nDCG@10", "coverage@10", "novelty@10"],
                 [[nm] + [f"{n(S[c][m]['mean'])} ± {n(S[c][m]['sd'])}" for m in ("p5", "r5", "ndcg10", "coverage10")] + [n(S[c]["novelty10"]["mean"], 2)]
                  for c, nm in (("popularity", "популярність"), ("graph", "графовий"), ("embeddings", f"ембединги ({EMB})"),
                                ("hybrid_weighted", "гібрид зважений"), ("hybrid_rrf", "<b>гібрид RRF</b>"))])

risk_tab = table(["Ризик", "AI Act / NIST AI RMF", "Як зменшуємо в Hub", "Залишковий"], [
    ["Вигадані факти у відповіді агента", "NIST: Valid & Reliable, Measure 2.5; GenAI-профіль: confabulation", "цитування [id], верифікатор чисел у доказах, «не знаю»; успішність 0,75, але 3/12 сценаріїв хибні", "середній"],
    ["Ін'єкція промпту, підвищення ролі", "NIST: Secure & Resilient; GenAI-профіль: information security", "фільтр входу, роль із сесії, RBAC до ранжування, read-only граф, закріплені маніфести; атаки 13/13 відбито", "низький"],
    ["Витік restricted-досьє", "AI Act ст. 10 (дані), GDPR; NIST: Privacy-Enhanced", "фільтр доступу до кандидатів у пошуку й рекомендаціях, порти лише 127.0.0.1, локальна LLM", "низький"],
    ["Непрозорість рекомендацій", "AI Act ст. 13, 50 (прозорість); NIST: Explainable & Interpretable", "пояснення лише зі шляху графа, перевірка сутностей; відповіді агента позначено як згенеровані ШІ", "низький"],
    ["Бульбашка, упередження популярності", "NIST: Fair (managed bias), Map 5.1", "RRF з графом і ембедингами (coverage 0,39 проти 0,04), слоти нових; план — MMR", "середній"],
    ["Застарілі / замінені регламенти", "AI Act ст. 15 (точність); NIST: Manage 4.1 (моніторинг)", "фільтр чинності, свіжості; gate якості ЛР14; версії сховища", "низький"],
    ["Надмірна довіра аналітика до системи", "AI Act ст. 14 (людський нагляд), ст. 4 (AI-грамотність); NIST: Govern 3.2", "HITL для запису знань (propose_fact), рекомендації — підказка, не вердикт; навчання користувачів", "середній"],
    ["Синтетичні дані оцінки ≠ реальна поведінка", "NIST: Measure 2.1, 4.2 (валідність оцінки)", "чесно позначено; план A/B-тесту й збору журналів зі згодою", "високий"],
])

cost_tab = table(["Операція", "Виміряно", "Ресурс"], [
    ["Рекомендація (top-5, гібрид RRF + пояснення)", f"{DEMO['steps'][0]['seconds'] * 1000:.0f} мс" if DEMO else "≈ 20–40 мс", "CPU, 1 процес; без LLM"],
    ["Відповідь агента ЛР15 (v3, 12 сценаріїв)", "70,2 с у середньому, p95 134,1 с", "qwen2.5:7b Q4 на CPU; 6 786 вхідних + 391 вихідних токенів на питання"],
    ["RAG ЛР11 (k = 3)", "p50 23,3 с, p95 41,4 с", "те саме"],
    ["Пошук із reranker ЛР10", "≈ 4,6 с на запит", "cross-encoder на CPU"],
    ["Перефразування пояснення (ЛР16)", f"{n(sum(r.get('llm_latency_s', 0) for r in EX['rows']) / max(1, len(EX['rows'])), 1)} с" if llm_ok is not None else "—", "qwen2.5:7b"],
    ["Збірка демонстратора з нуля", f"{n(DR['build_s'] / 60, 1)} хв" if DR.get("build_s") is not None else "—", f"образ {DR.get('image', '—').split(' ')[-1]}, python:3.12-slim без torch"],
])

claims_tab = table(["id", "Твердження", "Рівень", "Статус", "Джерело"],
                   [[c["id"], html.escape(c["claim"]), c["verification_level"], c["status"], html.escape(c["source"])] for c in CLAIMS[:20]], "small")

HTML = f"""<!doctype html><html lang="uk"><head><meta charset="utf-8"><title>Domain Knowledge Hub — whitepaper</title>
<style>
@page {{ size: A4; }}
body {{ font-family: 'Liberation Serif', serif; font-size: 10.6pt; line-height: 1.38; color: #111; }}
h1 {{ font-family: 'Liberation Sans'; font-size: 19pt; margin: 0 0 4pt; color: #1f3f73; }}
h2 {{ break-after: avoid; font-family: 'Liberation Sans'; font-size: 12.5pt; color: #1f3f73; margin: 14pt 0 4pt; border-bottom: 1px solid #c8d4e6; padding-bottom: 2pt; }}
h3 {{ break-after: avoid; font-family: 'Liberation Sans'; font-size: 10.6pt; margin: 9pt 0 2pt; }}
p {{ margin: 0 0 5pt; text-align: justify; }}
ul {{ margin: 0 0 5pt 0; padding-left: 15pt; }} li {{ margin-bottom: 1.5pt; }}
table {{ border-collapse: collapse; width: 100%; font-size: 8.8pt; margin: 4pt 0 3pt; page-break-inside: avoid; }}
table.small {{ font-size: 7.6pt; }}
th, td {{ border: 1px solid #b9c2cf; padding: 2.5pt 4pt; vertical-align: top; text-align: left; }}
th {{ background: #e9eef6; font-family: 'Liberation Sans'; }}
.cap {{ font-size: 8.8pt; color: #444; margin: 1pt 0 8pt; text-align: center; }}
.fig {{ page-break-inside: avoid; margin: 4pt 0; text-align: center; }}
.lead {{ font-size: 11pt; color: #333; }}
.meta {{ font-family: 'Liberation Sans'; font-size: 9pt; color: #555; margin-bottom: 8pt; }}
.box {{ background: #f3f6fb; border-left: 3px solid #2a78d6; padding: 5pt 8pt; margin: 5pt 0; }}
.pb {{ page-break-before: always; }}
</style></head><body>
<h1>Domain Knowledge Hub: сховище знань для аналізу достовірності інформації</h1>
<div class="meta">Whitepaper фінального проєкту курсу «Сховища знань та управління знаннями» · Хоптій Дмитро, ФЕІ-42, ЛНУ імені Івана Франка · листопад 2026 · версія сховища kb-2026.11-v1</div>
<p class="lead"><b>Коротко.</b> Hub зводить в одне сховище онтологію, граф розслідувань, корпус довідкових і внутрішніх документів, OLAP-куб перевірок і журнали роботи аналітиків. Поверх нього працюють RAG-чат з цитуванням, LLM-агент з інструментами лише для читання і рекомендаційний модуль, що пояснює кожну підказку шляхом у графі знань. Усе запускається однією командою Docker Compose і працює на звичайному ПК з локальною моделлю 7B, без передавання даних зовнішнім сервісам. Гібридні рекомендації дають nDCG@10 = {n(rrf['ndcg10']['mean'])} проти {n(pop['ndcg10']['mean'])} у популярності. Агент відбиває 13 з 13 атак. Головне обмеження — оцінка рекомендацій на синтетичних журналах.</p>

<h2>1. Проблема і користувачі</h2>
<p>Фактчекер працює з потоком тверджень: перевіряє першоджерело, шукає спростування, застосовує регламент вердиктів і пояснює рішення. Знання для цього розпорошені:</p>
<ul><li>енциклопедичні статті про пропаганду й методи перевірки;</li><li>внутрішні регламенти, що змінюються (регламент 2025 замінено регламентом 2026);</li><li>досьє наративів з обмеженим доступом;</li><li>історія попередніх вердиктів;</li><li>мережі акаунтів-поширювачів.</li></ul>
<p>Типові збої такі: застосування застарілого правила, пропущене спростування, вигадана моделлю цифра, витік закритого досьє.</p>
<p><b>Користувачі:</b></p>
<ul><li><b>аналітик-фактчекер</b> (основний; роль analyst) — пошук доказів, відповіді з цитатами, рекомендації «що прочитати далі»;</li>
<li><b>керівник групи / адміністратор знань</b> (admin) — досьє наративів, контроль якості, схвалення нових фактів;</li>
<li><b>гість / стажер</b> (guest) — лише публічні матеріали, навчання.</li></ul>
<p><b>Компетентнісні питання</b> (ЛР7, ЛР9):</p>
<ul><li>«хто першоджерело твердження?»;</li><li>«які офіційні джерела його спростовують?»;</li><li>«чи відповідає вердикт чинному регламенту?»;</li><li>«яка частка хибних вердиктів на платформі?»;</li><li>«що ще варто прочитати аналітику, який вивчає дипфейки?».</li></ul>

<h2>2. Архітектура</h2>
<div class="fig">{ARCH}</div><div class="cap">Рисунок 1 – Архітектура Hub: три шари й лабораторні, у яких їх побудовано</div>
<p><b>Гібридне сховище.</b> Кожен тип питань обслуговує своя модель даних:</p>
<ul><li><b>граф</b> (Neo4j LPG у ЛР9; RDF-знімок 8322 трійки для SPARQL у ЛР8/14) — зв'язки «акаунт → публікація → твердження → наратив → вердикт»;</li>
<li><b>індекс документів</b> (ЛР10) — 36 документів, 529 фрагментів, гібридний пошук BM25 + e5 + RRF з фільтром доступу до ранжування;</li>
<li><b>OLAP-куб</b> (ЛР12, зірка з 7 вимірами в DuckDB) — агреговані показники через семантичний шар із 7 метрик.</li></ul>
<p><b>Шар застосувань:</b></p>
<ul><li>RAG-чат (ЛР11);</li><li>агент LangGraph із трьома інструментами й MCP-сервером (ЛР15);</li><li>рекомендаційний модуль (ЛР16).</li></ul>
<p><b>Демонстратор</b> — три контейнери з одного образу python:3.12-slim:</p>
<ul><li><code>graph</code> — SPARQL лише для читання на pyoxigraph;</li><li><code>api</code> — FastAPI: рекомендації, пояснення, пошук, агент, проксі SPARQL;</li><li><code>ui</code> — Streamlit.</li></ul>
<p>LLM qwen2.5:7b працює на хості через Ollama. Порти відкриті лише на 127.0.0.1, контейнери працюють від непривілейованого користувача, секретів немає. {build_line} {demo_line} (рекомендації з поясненнями, відповідь з доказом, «не знаю», три атаки, холодний старт).</p>
<div class="fig">{img(UI_IMG, '80%')}</div><div class="cap">Рисунок 2 – Інтерфейс демонстратора: рекомендації аналітику з поясненнями зі шляхів графа</div>

<h2>3. Знання і походження (provenance)</h2>
<p><b>Онтологія.</b> Вона пройшла шлях від таксономії й семантичної мережі (ЛР4–5) до OWL у Protégé (ЛР6) і має 18 класів, 13 object і 16 data properties. Узгодженість перевірено HermiT. RDF-сховище ЛР8 додало SHACL-форми й RDFS-виведення: той самий запит повертає 5 результатів замість 0.</p>
<p><b>Походження фактів.</b> Кожне ребро графа несе <code>source</code>, <code>confidence</code>, <code>validFrom</code>; після ЛР14 жодного ребра без провенансу. Злиття сутностей (ER) зберігає вихідні записи і має операцію unmerge — хибне злиття YouTube ~ YouTuber скасовано. Суперечності розв'язуються за явними стратегіями («дата», «рішення власника», «канонічний термін»). 34 альтернативні значення збережено з походженням, а не стерто.</p>
<p><b>Нові факти</b> агент лише <i>пропонує</i> (<code>propose_fact</code>, ЛР15). Пропозиція проходить SHACL-валідацію, оцінку ризику і схвалення людиною з записом PROV-O та журналом аудиту.</p>
<p><b>Витяг знань.</b> На test правила spaCy дали F1 відношень 0,811 проти 0,163 у локальної LLM (ЛР13). Тому основний метод — правила, а LLM лише генерує кандидатів, яких фільтрує валідатор цитат.</p>

<h2>4. Метрики якості (ЛР3–ЛР16)</h2>
<div class="fig">{img('wp_labs.png', '92%')}</div><div class="cap">Рисунок 3 – Ключові метрики етапів: базовий і обраний варіант (дані звітів ЛР10–ЛР16)</div>
{table(["ЛР", "Що вимірювали", "Результат"], [
    ["3–7", "модель предметної області", "глосарій, таксономія SKOS, семантична мережа; онтологія 18 класів, узгоджена (HermiT, 0 суперечливих класів)"],
    ["8", "RDF-сховище", "SHACL: 3 форми; RDFS-виведення додало 499 трійок, запит класу 0 → 5 результатів"],
    ["9", "граф Neo4j", "297 вузлів, 808 ребер; PageRank знайшов 8/8 першоджерел; Louvain модулярність 0,57; індекс −45 % db hits; Text-to-Cypher 50–58 %"],
    ["10", "пошук", "recall@5: BM25 0,722 → гібрид+reranker 0,847; 0 порушень прав доступу"],
    ["11", "RAG", "13/15 правильних, усі запити без відповіді відхилено; citation validity 1,0, context recall 0,875, citation accuracy 0,662; суддя завищує faithfulness (κ = 0,488)"],
    ["12", "OLAP і Text-to-SQL", "2138 фактів без сиріт, 8 перевірок; Text-to-SQL 66,7 % (75 % вручну), атаки 3/3 заблоковано"],
    ["13", "витяг знань", "F1 відношень: правила 0,811, LLM 0,163; прийнято 54/254 пропозицій LLM; κ розмітки 0,375"],
    ["14", "якість даних", "пороги: 3/15 → 11/15; ER test P/R 0,889/0,696 → з LLM-суддею 0,950/0,826; gate із 19 перевірок блокує 3/3 дефекти"],
    ["15", "агент", "успішність 0,417 → 0,75 (12 сценаріїв); атаки без захисту 2/13 успішні, із захистом 0/13"],
    ["16", "рекомендації", f"nDCG@10: популярність {n(pop['ndcg10']['mean'])} → гібрид RRF {n(rrf['ndcg10']['mean'])}; coverage@10 {n(pop['coverage10']['mean'])} → {n(rrf['coverage10']['mean'])}; пояснень, що пройшли перевірку: шаблон {n(ex_s['template_correct'], 2)}, перефразування LLM {n(llm_ok, 2)} (строга перевірка {n(ex_s['llm_correct_strict'], 2)}); вставлені сторонні сутності виявлено {ex_s['negative_control']['caught']}/{ex_s['negative_control']['injected']}"],
])}
<div class="cap">Таблиця 1 – Метрики якості за етапами</div>

<h3>Рекомендації: офлайн-оцінка</h3>
<p><b>Дані.</b> Синтетичні журнали 60 користувачів за три місяці. Часове розбиття: train &lt; 2026-10-06 ≤ validation &lt; 2026-10-20 ≤ test. Ваги гібриду підбиралися лише на validation. Популярність і профілі рахуються від моменту межі, тож витоку з майбутнього немає.</p>
<p><b>Повтори.</b> 5 seed генератора, у кожному бутстреп за користувачами (1000 вибірок). Ембединги: {EMB}.</p>
{reco_tab}<div class="cap">Таблиця 2 – Офлайн-оцінка рекомендацій на test (середнє ± sd за 5 seed)</div>
<div class="fig">{img('reco_accuracy.png', '78%')}</div><div class="cap">Рисунок 4 – P@5, R@5, nDCG@10 за конфігураціями</div>
<div class="fig">{img('reco_tradeoff.png', '62%')}</div><div class="cap">Рисунок 5 – Компроміс точності (nDCG@10) і покриття каталогу</div>
<p><b>Висновок.</b> Обидва гібриди втричі кращі за популярність і кращі за кожен окремий метод. Зважений гібрид має трохи вищий середній nDCG@10 ({n(hw['ndcg10']['mean'])} проти {n(rrf['ndcg10']['mean'])}). Але парний тест на тих самих {PA['n_user_pairs']} користувачах дає різницю {n(PA['mean_diff_a_minus_b'])}, 95 % CI [{n(PA['ci95'][0])}; {n(PA['ci95'][1])}], тобто різниця незначуща. Для продукту обрано <b>RRF</b>:</p>
<ul><li>точність у межах похибки така сама, а розкид між seed менший (sd {n(rrf['ndcg10']['sd'])} проти {n(hw['ndcg10']['sd'])});</li><li>він не потребує навчуваних ваг — у зваженого гібриду оптимальні ваги стрибають між seed ({W_BEST}), тобто їх підбір переналаштовується на validation;</li><li>покриття каталогу стабільніше (sd {n(rrf['coverage10']['sd'])} проти {n(hw['coverage10']['sd'])}).</li></ul>
<div class="fig">{img('cold_start.png', '86%')}</div><div class="cap">Рисунок 6 – Холодний старт: новий користувач (nDCG@10) і новий документ (exposure, hit@10)</div>
<p><b>Холодний старт:</b></p>
<ul><li><b>новий користувач</b> обирає теми: гібрид від тем дає nDCG@10 = {n(A['onboard_hybrid']['ndcg10']['mean'])} проти {n(A['pop_global']['ndcg10']['mean'])} у загальної популярності; після трьох взаємодій — {n(A['warm3']['ndcg10']['mean'])};</li>
<li><b>новий документ</b>: без примусових слотів RRF майже не показує нові фрагменти (exposure {n(B['hybrid_rrf']['exposure_new']['mean'])}); з двома слотами — {n(B['hybrid_rrf+new_slot2']['exposure_new']['mean'])}.</li></ul>

<h2>5. Ризики за AI Act і NIST AI RMF</h2>
<p><b>Класифікація за AI Act.</b> Регламент (ЄС) 2024/1689 зі змінами Digital Omnibus — Регламент (ЄС) 2026/1744. Hub — допоміжний інструмент аналітика для пошуку, рекомендацій і чернеток відповідей. Він не належить до заборонених практик (ст. 5) і не входить до переліку високоризикових систем Додатка III: не ухвалює рішень щодо осіб, не впливає на вибори, не використовується правоохоронними органами.</p>
<p><b>Обов'язки, що діють:</b></p>
<ul><li><b>прозорість (ст. 50, з 2 серпня 2026)</b> — користувач знає, що працює з ШІ, а згенерований текст позначено: відповіді агента в UI мають позначку моделі; пояснення рекомендацій у демонстраторі — детерміновані шаблони зі шляху графа;</li>
<li><b>AI-грамотність персоналу (ст. 4)</b>.</li></ul>
<p>Якщо систему почне застосовувати державний орган для рішень щодо громадян, класифікацію треба переглянути. Обов'язки для Додатка III після Omnibus діють з 2 грудня 2027 року. Обов'язки постачальника GPAI-моделі (ст. 53) лежать на розробнику qwen, а не на Hub.</p>
<p><b>NIST AI RMF 1.0.</b> Функції Govern / Map / Measure / Manage і профіль генеративного ШІ NIST AI 600-1 зведено в реєстр ризиків:</p>
{risk_tab}<div class="cap">Таблиця 3 – Реєстр ризиків і заходів</div>
<p><b>Govern.</b> Ролі власника знань і рецензента; журнали рішень (ЛР14); правила запису знань лише через HITL (ЛР15).</p>
<p><b>Measure.</b> Gate якості з 19 перевірок, набори тестів RAG і агента, red teaming, офлайн-оцінка рекомендацій.</p>
<p><b>Manage.</b> Регресійні прогони після змін корпусу. Регресію RAG на T13 у ЛР14 виявлено саме так.</p>

<h2>6. Економіка і вартість</h2>
<p><b>Інфраструктура.</b> Уся система працює на одному ПК студента (CPU, модель 7B у квантуванні Q4). Плата за API відсутня, дані не залишають машину. Головна «вартість» — затримка LLM на CPU.</p>
{cost_tab}<div class="cap">Таблиця 4 – Виміряні витрати ресурсів</div>
<p><b>Масштабування.</b> Порівняймо з хмарним API за формулою <i>вартість = N·(T<sub>in</sub>·p<sub>in</sub> + T<sub>out</sub>·p<sub>out</sub>)</i>. На одне питання агента T<sub>in</sub> ≈ 6 786, T<sub>out</sub> ≈ 391 токен. Для 1 000 питань на день це ≈ 6,8 млн вхідних і 0,4 млн вихідних токенів. За умовних цін 1 і 5 доларів за мільйон токенів виходить ≈ 8,7 долара на день. Реальні тарифи треба перевіряти на момент рішення. При цьому внутрішні документи довелося б передавати зовнішньому постачальнику, що для restricted-досьє неприйнятно.</p>
<p><b>Висновок про вартість.</b> Для групи з кількох аналітиків локальний варіант дешевший і безпечніший. Вузьке місце — пропускна здатність: ≈ 70 с на питання на CPU. Підвищити її можна так:</p>
<ul><li>GPU;</li><li>кешування відповідей;</li><li>маршрутизація простих питань без LLM — рекомендації й пошук уже працюють за десятки мілісекунд.</li></ul>
<p><b>Трудовитрати.</b> Найдорожчим ресурсом була людська розмітка й перевірка: золоті набори ЛР10–13, ручна перевірка суддів (ЛР11, ЛР14), рішення HITL (ЛР15).</p>

<h2>7. Використання генеративного ШІ в проєкті</h2>
<p><b>Два класи генеративного ШІ:</b></p>
<ul><li><b>LLM-експерт (Claude, Anthropic)</b> — проєктування, код, тексти документації, аналіз результатів;</li>
<li><b>локальні моделі як компоненти системи</b> — qwen2.5:7b: Text-to-Cypher/SQL, витяг знань, судді, агент, перефразування пояснень; gemma3:4b: незалежний суддя і червона команда.</li></ul>
<p>Протокол кожної ЛР — <code>llm_log/</code> (запит, пропозиція, рішення людини) і <code>claims/claims.csv</code> (твердження з рівнем перевірки V1–V4).</p>
<p><b>Найбільший виграш.</b> LLM-експерт найбільше допоміг зі швидкістю побудови інфраструктури: конвеєри, тестові набори, Docker, документація. Також він знайшов неочевидні причини збоїв — затінення стандартного модуля <code>profile</code>, через яке e5 не працювала (ЛР15).</p>
<p><b>Помилки експерта, виявлені вимірюванням:</b></p>
<ul><li>виправлення v2 агента погіршили результат (0,417 → 0,25);</li><li>первинний графовий рекомендатор мав nDCG 0,05 — нормалізація за ступенем «вбивала» сигнал;</li><li>оцінки LLM-суддів були завищені (κ = 0,488);</li><li>LLM гірше за правила витягувала відношення;</li><li>перша (строга) перевірка пояснень відкидала третину правильних перефразувань через відмінкові форми назв — знайдено розбором відмов і виправлено з негативним контролем.</li></ul>
<p><b>Висновок.</b> Кожну пропозицію LLM перевіряли прогоном, кожне твердження звіту має джерело в <code>results/</code>. Усі моделі в продукті локальні, ключів API немає, персональні дані не передавалися.</p>

<h2>8. Обмеження</h2>
<ul>
<li><b>Синтетичні журнали взаємодій.</b> Генератор читає розділи послідовно й обирає документи за темами, тож підіграє ребру NEXT_SECTION і онбордингу за темами. Абсолютні значення метрик не переносяться на реальних користувачів.</li>
<li><b>Малі вибірки:</b> 12 сценаріїв агента, 31 тест RAG, 50–53 користувачів у test рекомендацій. Інтервали широкі, а різниця між двома гібридами незначуща.</li>
<li><b>Мала LLM на CPU.</b> Часто обирає не той інструмент, повільна (p95 до 134 с). У 3 з 12 сценаріїв агент дає хибну або неповну відповідь.</li>
<li><b>Покриття графа:</b> 37 % фрагментів без жодної сутності; газетир чутливий до відмінків.</li>
<li><b>Перевіреність документа</b> — грубий фільтр. Пороги точності, свіжості й доступності джерел (ЛР14) ще не досягнуто.</li>
</ul>

<h2>9. Наступні кроки</h2>
<ul>
<li>Пілот із реальними аналітиками: збір журналів зі згодою, онлайн A/B-тест RRF проти популярності, метрика «використано в вердикті».</li>
<li>Диверсифікація (MMR) і контроль новизни; навчуваний ранжувальник на реальних кліках з тими самими фільтрами.</li>
<li>Перевіреність на рівні тверджень (вердикти ЛР9) замість документів; автоматичне оновлення джерел для порогів свіжості.</li>
<li>GPU або менша спеціалізована модель для агента; кеш; маршрутизація питань «граф / OLAP / документи» без LLM.</li>
<li>CI: gate якості ЛР14, регресія RAG і агента, офлайн-оцінка рекомендацій на кожну зміну корпусу; моніторинг дрейфу.</li>
</ul>

<h2>Джерела</h2>
<ol style="font-size:9.4pt">
<li>Лекція 16 «Рекомендаційні системи, етика та майбутнє систем знань». Курс «Сховища знань та управління знаннями», ЛНУ, 2026.</li>
<li>Ricci F., Rokach L., Shapira B. (eds.) Recommender Systems Handbook. 2nd ed. Springer, 2015.</li>
<li>Aggarwal C. C. Recommender Systems: The Textbook. Springer, 2016.</li>
<li>Регламент (ЄС) 2024/1689 Європейського Парламенту і Ради (Artificial Intelligence Act). OJ L, 12.07.2024.</li>
<li>Регламент (ЄС) 2026/1744 (Digital Omnibus on AI) — зміни строків застосування AI Act; огляд: Goodwin, «Not Delayed, Not Deferred: EU AI Act Transparency Obligations Are Now in Force», 08.2026.</li>
<li>NIST AI 100-1. Artificial Intelligence Risk Management Framework (AI RMF 1.0). NIST, 2023.</li>
<li>NIST AI 600-1. AI RMF: Generative Artificial Intelligence Profile. NIST, 2024.</li>
<li>Cormack G. V., Clarke C. L. A., Büttcher S. Reciprocal Rank Fusion Outperforms Condorcet and Individual Rank Learning Methods // SIGIR 2009.</li>
<li>Järvelin K., Kekäläinen J. Cumulated Gain-Based Evaluation of IR Techniques // ACM TOIS. 2002. Vol. 20(4).</li>
<li>Wang L. et al. Text Embeddings by Weakly-Supervised Contrastive Pre-training (E5). arXiv:2212.03533, 2022.</li>
<li>Lewis P. et al. Retrieval-Augmented Generation for Knowledge-Intensive NLP Tasks // NeurIPS 2020.</li>
<li>Yao S. et al. ReAct: Synergizing Reasoning and Acting in Language Models // ICLR 2023.</li>
<li>W3C. PROV-O: The PROV Ontology. W3C Recommendation, 2013; W3C. Shapes Constraint Language (SHACL), 2017.</li>
</ol>

<h2 class="pb">Додаток А. Топ-20 тверджень проєкту</h2>
<p style="font-size:9pt">Рівні перевірки: V1 — думка/джерело без перевірки; V2 — перевірено вручну на прикладах; V3 — перевірено на тестовому наборі; V4 — відтворюваний прогін з артефактом у <code>results/</code>. Повна таблиця — <code>claims/claims.csv</code>.</p>
{claims_tab}
</body></html>"""

(DOCS / "whitepaper.html").write_text(HTML, encoding="utf-8")
js = f"""const {{ chromium }} = require('playwright');
(async () => {{ const b = await chromium.launch(); const p = await b.newPage();
 await p.goto('file://{(DOCS / "whitepaper.html").as_posix()}'); await p.waitForTimeout(500);
 await p.pdf({{ path: '{(DOCS / "whitepaper.pdf").as_posix()}', format: 'A4', printBackground: true,
   margin: {{ top: '16mm', bottom: '16mm', left: '16mm', right: '16mm' }}, displayHeaderFooter: true,
   headerTemplate: '<span></span>', footerTemplate: '<div style="font-size:8px;width:100%;text-align:center;color:#666">Domain Knowledge Hub · whitepaper · <span class="pageNumber"></span>/<span class="totalPages"></span></div>' }});
 await b.close(); }})();"""
(Path(__file__).parent / "_pdf.js").write_text(js, encoding="utf-8")
subprocess.run(["node", str(Path(__file__).parent / "_pdf.js")], check=True)
print("whitepaper.pdf")
