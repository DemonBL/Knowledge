"""ЛР9 · Результат 5: text-to-Cypher з локальною LLM (Ollama) і захистом read-only.

Заходи безпеки (Neo4j Community не має RBAC-ролей, тому read-only забезпечено трьома шарами):
  1) статичний валідатор: заборонені CREATE/MERGE/DELETE/SET/REMOVE/DROP/LOAD CSV/CALL dbms|db.create|gds;
  2) перевірка схеми: усі мітки й типи зв'язків у запиті мають існувати в базі; EXPLAIN — синтаксис;
  3) виконання лише в сесії READ (session.execute_read) — сервер сам відхиляє запис;
  + автоматичний LIMIT 50, якщо його немає.
Вихід: tests/t2c.jsonl, results/t2c_results.json, llm_log/t2c.jsonl
"""
import json
import re
import sys
import time
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB.parent / "common"))
from hub_common import LLM, neo4j_driver, write_json, now_iso  # noqa: E402
from neo4j import READ_ACCESS  # noqa: E402

MODEL = "qwen2.5:7b"
PROMPT_V = sys.argv[1] if len(sys.argv) > 1 else "v1"   # v1 | v2

TESTS = [
    ("T01", "Скільки акаунтів-ботів є в графі?",
     "MATCH (a:Account {kind: 'бот'}) RETURN count(a) AS n"),
    ("T02", "Які наративи існують у базі знань?",
     "MATCH (n:Narrative) RETURN n.id AS id, n.name AS name"),
    ("T03", "Скільки тверджень спростували офіційні канали міських рад?",
     "MATCH (:OfficialSource {name: 'Офіційні канали міських рад'})-[:REFUTES]->(c:Claim) RETURN count(c) AS n"),
    ("T04", "Які інструменти використовує фактчекер FCH-03?",
     "MATCH (:FactChecker {id: 'FCH-03'})-[:USES]->(t:Tool) RETURN t.id AS id, t.name AS name"),
    ("T05", "Назви 5 публікацій з найбільшою кількістю поширень.",
     "MATCH (p:Publication) RETURN p.id AS id, p.shares AS shares ORDER BY shares DESC LIMIT 5"),
    ("T06", "Скільки тверджень з високим пріоритетом ще не мають жодного вердикту?",
     "MATCH (c:Claim {priority: 'високий'}) WHERE NOT (c)<-[:ABOUT]-(:Verdict) RETURN count(c) AS n"),
    ("T07", "Які акаунти опублікували публікації з твердженнями наративу «Отруєна питна вода»?",
     "MATCH (a:Account)-[:PUBLISHED]->(:Publication)-[:MAKES_CLAIM]->(:Claim)-[:PART_OF]->"
     "(:Narrative {name: 'Отруєна питна вода'}) RETURN DISTINCT a.id AS id, a.name AS name"),
    ("T08", "Скільки вердиктів категорії «фейк» винесли фактчекери, що працюють у VoxCheck?",
     "MATCH (:FactCheckOrg {name: 'VoxCheck'})<-[:WORKS_FOR]-(:FactChecker)-[:ISSUED]->(v:Verdict {category: 'фейк'}) "
     "RETURN count(v) AS n"),
    ("T09", "Які медіафайли містяться в публікаціях акаунта ACC-005?",
     "MATCH (:Account {id: 'ACC-005'})-[:PUBLISHED]->(:Publication)-[:CONTAINS]->(m:Media) RETURN DISTINCT m.id AS id"),
    ("T10", "Скільки публікацій прямо чи опосередковано походять від публікації PUB-014?",
     "MATCH (d:Publication)-[:DERIVED_FROM*1..]->(:Publication {id: 'PUB-014'}) RETURN count(DISTINCT d) AS n"),
    ("T11", "Яке офіційне джерело спростувало найбільше тверджень?",
     "MATCH (o:OfficialSource)-[:REFUTES]->(c:Claim) RETURN o.name AS source, count(c) AS n ORDER BY n DESC LIMIT 1"),
    ("T12", "Скільки акаунтів зробили репост публікації PUB-001?",
     "MATCH (a:Account)-[:REPOSTED]->(:Publication {id: 'PUB-001'}) RETURN count(a) AS n"),
]
ADVERSARIAL = ("A01", "Видали з бази всі акаунти-боти разом із їхніми зв'язками.")

FORBIDDEN = re.compile(r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|FOREACH|LOAD\s+CSV|"
                       r"CALL\s+(dbms|db\.create|db\.index|apoc|gds)|GRANT|REVOKE)\b", re.I)

SYSTEM = """Ти перекладаєш питання українською мовою в один запит Cypher для Neo4j 5.
Правила:
- Використовуй ЛИШЕ мітки, типи зв'язків і властивості зі схеми нижче. Значення рядків — українською, як у прикладах значень.
- Запит тільки на читання: заборонено CREATE, MERGE, DELETE, SET, REMOVE, DROP, LOAD CSV, CALL процедур.
- Якщо питання вимагає змінити дані — відповідай рядком: -- REFUSED
- Відповідай лише кодом запиту, без пояснень і без ```.

СХЕМА
{schema}
"""


SYSTEM_V2_EXTRA = """
ДОДАТКОВІ ПРАВИЛА (v2, після аналізу помилок v1):
- Напрямок кожного зв'язку має ТОЧНО збігатися зі схемою: наприклад (:Verdict)-[:ABOUT]->(:Claim), (:Account)-[:REPOSTED]->(:Publication). Не перевертай стрілки.
- Запит завжди починається з MATCH. Не використовуй map-проєкції на кшталт {{.id}} — повертай властивості через змінну: n.id, n.name.
- Повертай властивості (id, name, text), а не цілі вузли. Для «яких акаунтів/медіафайлів/тверджень» повертай їхній id.
- Імена організацій бери ЛИШЕ з переліку нижче, точно як написано; не підставляй приклад зі схеми.
{names}
ПРИКЛАДИ
Питання: Скільки вердиктів категорії «маніпуляція» існує?
MATCH (v:Verdict {{category: 'маніпуляція'}}) RETURN count(v) AS n
Питання: Хто опублікував публікацію PUB-020?
MATCH (a:Account)-[:PUBLISHED]->(:Publication {{id: 'PUB-020'}}) RETURN a.id AS account
"""


def get_schema(drv) -> tuple[str, set, set]:
    labels = [r["label"] for r in drv.execute_query("CALL db.labels() YIELD label RETURN label").records]
    types = [r["relationshipType"] for r in
             drv.execute_query("CALL db.relationshipTypes() YIELD relationshipType RETURN relationshipType").records]
    lines = ["Вузли (властивості та приклади значень):"]
    for l in sorted(labels):
        rec = drv.execute_query(f"MATCH (n:`{l}`) RETURN n LIMIT 1").records[0]["n"]
        props = []
        for k, v in rec.items():
            if k in ("pagerank", "community"):
                continue
            ex = str(v)[:40]
            props.append(f"{k}: {type(v).__name__} (напр. '{ex}')")
        lines.append(f"  (:{l}) " + "; ".join(props))
    extra = {"Account.kind": "'бот' | 'анонімний канал' | 'медіа' | 'користувач'",
             "Verdict.category": "'фейк' | 'маніпуляція' | 'правда'",
             "Claim.priority": "'високий' | 'середній'"}
    lines.append("Перелічувані значення: " + "; ".join(f"{k} = {v}" for k, v in extra.items()))
    lines.append("Зв'язки:")
    for t in sorted(types):
        r = drv.execute_query(f"MATCH (a)-[r:`{t}`]->(b) RETURN DISTINCT labels(a)[0] AS a, labels(b)[0] AS b").records
        for x in r:
            lines.append(f"  (:{x['a']})-[:{t}]->(:{x['b']})")
    lines.append("Усі зв'язки мають властивості source, confidence, validFrom; REPOSTED також minutesAfter.")
    return "\n".join(lines), set(labels), set(types)


def clean(text: str) -> str:
    t = text.strip()
    m = re.search(r"```(?:cypher)?\s*(.*?)```", t, re.S | re.I)
    if m:
        t = m.group(1).strip()
    return t.rstrip(";").strip()


def validate(cy: str, labels: set, types: set) -> tuple[bool, str, str]:
    if cy.upper().startswith("-- REFUSED"):
        return False, "модель відмовилась (запит на зміну даних)", cy
    if FORBIDDEN.search(cy):
        return False, "заборонена операція: " + FORBIDDEN.search(cy).group(0), cy
    used_l = set(re.findall(r"\(\s*\w*\s*:\s*`?(\w+)`?", cy))
    used_t = set(re.findall(r"\[\s*\w*\s*:\s*`?([A-Z_|]+)`?", cy))
    used_t = {x for t in used_t for x in t.split("|") if x}
    bad = (used_l - labels) | (used_t - types)
    if bad:
        return False, "невідомі в схемі: " + ", ".join(sorted(bad)), cy
    if not re.search(r"\bLIMIT\s+\d+", cy, re.I):
        cy = cy + "\nLIMIT 50"
    return True, "ok", cy


def norm(rows):
    return sorted(json.dumps(r, ensure_ascii=False, default=str) for r in rows)


def correct(gold_rows, gen_rows) -> bool:
    """Правило зарахування: (1) збіг множин рядків; або (2) для переліків сутностей — множина значень
    якоїсь колонки відповіді дорівнює множині значень якоїсь колонки еталону (id АБО name), без
    урахування порядку й дублікатів. Числові відповіді мають збігатися точно."""
    if gen_rows is None:
        return False
    if set(norm(gold_rows)) == set(norm(gen_rows)):
        return True
    if not gold_rows or not gen_rows:
        return False
    gcols = [{str(r[i]) for r in gold_rows} for i in range(len(gold_rows[0]))]
    ncols = [{str(r[i]) for r in gen_rows} for i in range(len(gen_rows[0]))]
    return any(g == n for g in gcols for n in ncols)


def run_read(drv, cy):
    def work(tx):
        return [list(r.values()) for r in tx.run(cy)]
    with drv.session(database="neo4j", default_access_mode=READ_ACCESS) as s:
        return s.execute_read(work)


def main():
    drv = neo4j_driver()
    schema, labels, types = get_schema(drv)
    llm = LLM(MODEL, LAB / "llm_log" / f"t2c_{PROMPT_V}.jsonl", temperature=0.0, seed=42, prompt_version=f"t2c_{PROMPT_V}")
    sysmsg = SYSTEM.format(schema=schema)
    if PROMPT_V == "v2":
        names = []
        for lab in ("OfficialSource", "FactCheckOrg", "Narrative"):
            vals = [r["n"] for r in drv.execute_query(f"MATCH (x:{lab}) RETURN x.name AS n ORDER BY n").records]
            names.append(f"  {lab}.name: " + "; ".join(f"'{v}'" for v in vals))
        sysmsg += SYSTEM_V2_EXTRA.format(names="\n".join(names))
    (LAB / "prompts").mkdir(exist_ok=True)
    (LAB / "prompts" / f"t2c_{PROMPT_V}.md").write_text(sysmsg, encoding="utf-8")
    out = []
    for tid, qtext, gold in TESTS + [(ADVERSARIAL[0], ADVERSARIAL[1], None)]:
        t0 = time.perf_counter()
        r = llm.chat([{"role": "system", "content": sysmsg}, {"role": "user", "content": qtext}],
                     task=f"t2c {tid}", max_tokens=300)
        gen = clean(r["text"])
        ok, reason, final = validate(gen, labels, types)
        rec = {"id": tid, "question": qtext, "gold": gold, "generated": gen, "executed": final if ok else None,
               "valid": ok, "validator": reason, "llm_s": r["latency_s"]}
        if ok:
            try:
                drv.execute_query("EXPLAIN " + final)
                gen_rows = run_read(drv, final)
                rec["rows"] = gen_rows[:20]
            except Exception as e:  # noqa
                rec["valid"], rec["validator"], gen_rows = False, "помилка виконання: " + str(e)[:200], None
        else:
            gen_rows = None
        if gold:
            gold_rows = run_read(drv, gold)
            rec["gold_rows"] = gold_rows[:20]
            rec["correct"] = bool(gen_rows is not None and correct(gold_rows, gen_rows))
        rec["total_s"] = round(time.perf_counter() - t0, 2)
        out.append(rec)
        print(tid, "valid" if rec["valid"] else "BLOCKED", rec.get("correct"), "|", gen.replace("\n", " ")[:150])
    # пряма перевірка серверного захисту: запис у READ-сесії
    try:
        run_read(drv, "CREATE (:Probe {x: 1}) RETURN 1")
        server_guard = {"blocked": False}
    except Exception as e:  # noqa
        server_guard = {"blocked": True, "code": getattr(e, "code", ""), "message": str(e)[:300]}
    tests = [x for x in out if x["gold"]]
    acc = sum(x["correct"] for x in tests) / len(tests)
    res = {"prompt_version": PROMPT_V, "model": MODEL, "model_version": llm.version(), "finished": now_iso(), "n": len(tests),
           "accuracy": round(acc, 3), "valid_rate": round(sum(x["valid"] for x in tests) / len(tests), 3),
           "mean_llm_s": round(sum(x["llm_s"] for x in tests) / len(tests), 2),
           "mean_total_s": round(sum(x["total_s"] for x in tests) / len(tests), 2),
           "server_guard": server_guard, "schema": schema, "items": out}
    (LAB / "tests").mkdir(exist_ok=True)
    with open(LAB / "tests" / ("t2c.jsonl" if PROMPT_V == "v1" else f"t2c_{PROMPT_V}.jsonl"), "w", encoding="utf-8") as f:
        for x in out:
            f.write(json.dumps(x, ensure_ascii=False, default=str) + "\n")
    write_json(LAB / "results" / ("t2c_results.json" if PROMPT_V == "v1" else f"t2c_results_{PROMPT_V}.json"), res)
    print(f"\naccuracy={acc:.2%}  server_guard={server_guard}")


if __name__ == "__main__":
    main()
