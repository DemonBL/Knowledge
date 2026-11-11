"""ЛР15 · v3.1 — повторна перевірка (replay) відповідей прогону r3 виправленим верифікатором, без нових викликів LLM.

Чому це коректно: у графі агента чернетка (draft) генерується ДО перевірки (verify), тому виправлення верифікатора
не змінює ні вибору інструментів, ні тексту першої чернетки. Інструменти детерміновані (BM25, SPARQL, DuckDB) —
їхні виклики повторюються з аргументами з трас, докази відтворюються. Порядок як в агенті: перша чернетка → перевірка →
(якщо не пройшла) друга чернетка → перевірка → інакше «не знаю».
  python agent/replay_verify.py  → results/scen_r3_1.json
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import policies as P  # noqa: E402
import run_eval as E  # noqa: E402
import tools as T  # noqa: E402

LAB = T.LAB
drafts = {}
for l in open(LAB / "llm_log" / "agent_llm.jsonl", encoding="utf-8"):
    r = json.loads(l)
    if r.get("task") == "draft" and r.get("version") == "v3":
        drafts.setdefault(r["request_id"], []).append(r["raw_output"].strip())
items = {json.loads(l)["id"]: json.loads(l) for l in open(LAB / "tests" / "agent_scenarios.jsonl", encoding="utf-8")}
old = {r["id"]: r for r in json.loads((LAB / "results" / "scen_r3.json").read_text(encoding="utf-8"))["rows"]}
rows = []
for l in open(LAB / "traces" / "scen_r3.jsonl", encoding="utf-8"):
    tr = json.loads(l)
    sess = T.Session(role=tr["role"], profile="strict")
    for t in tr["trace"]:
        if t.get("node") == "tool" and not t.get("error"):
            T.call_tool(sess, t["tool"], t["args"], {"kb_graph", "search_docs", "olap_metrics"})
    for eid, txt in list(sess.evidence.items()):                  # санітизація, як в агенті
        sess.evidence[eid], _ = P.sanitize(txt)
    ds = drafts.get(tr["request_id"], [])
    ans, status, used = "Не знаю: не вдалося підтвердити відповідь цитатами з джерел Hub.", "abstained", None
    for i, d in enumerate(ds[:2]):
        ok, probs, _ = P.verify_answer(d, sess.evidence, "strict")
        if ok:
            ans, used = d, i + 1
            status = "abstained" if P.ABSTAIN.search(d) else "answered"
            if status == "abstained":
                ans = P.CIT.sub("", ans).strip()
            break
    r = dict(old[tr["id"]])
    r.update(answer=ans, status=status, version="v3.1 (replay)", replay_draft_used=used, replay_drafts=len(ds))
    r["ok"], r["why"] = E.score_scenario(items[tr["id"]], r)
    rows.append(r)
    print(tr["id"], "OK" if r["ok"] else "FAIL", status, used, "|", ans[:110].replace("\n", " "))
res = {"version": "v3.1 (replay r3)", "model": "qwen2.5:7b", "rows": rows, "summary": E.summarize(rows),
       "by_type": {t: E.summarize([r for r in rows if r["type"] == t]) for t in ("success", "noanswer", "conflict")},
       "note": "кроки, токени й латентність — з прогону r3 (нових викликів LLM немає)"}
(LAB / "results" / "scen_r3_1.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print(json.dumps({k: res["summary"][k] for k in ("success_rate", "mean_steps")}, ensure_ascii=False),
      {t: v["success_rate"] for t, v in res["by_type"].items()})
