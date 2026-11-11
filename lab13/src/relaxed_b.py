"""ЛР13 · діагностика (після оцінювання, не для налаштування): скільки відношень методу Б відкинула сувора валідація лише
через відсутні head_type/tail_type. Тип відновлюється з власного списку сутностей моделі (збіг за ключем нормалізації);
якщо сигнатура відношення допускає один тип — береться він. Цитата й наявність у тексті перевіряються так само суворо."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from extract_llm import validate  # noqa: E402
from normalize import lemma_key  # noqa: E402
from schema import RELATIONS  # noqa: E402

corpus = {d["doc_id"]: d for d in map(json.loads, open(ROOT / "data" / "corpus.jsonl", encoding="utf-8"))}
best = {}
for l in open(ROOT / "llm_log" / "extract_llm_log.jsonl", encoding="utf-8"):
    g = json.loads(l); v, doc, tr = g["task"].split()
    if v != "llm_v1" or corpus[doc]["split"] != "test": continue
    try: obj = json.loads(g["raw_output"])
    except Exception: continue
    tmap = {lemma_key(e["text"]): e["type"] for e in obj.get("entities", []) if isinstance(e, dict) and "text" in e and "type" in e}
    fixed = 0
    for r in obj.get("relations", []):
        if not isinstance(r, dict) or r.get("relation") not in RELATIONS: continue
        H, T, _ = RELATIONS[r["relation"]]
        for side, allowed in (("head", H), ("tail", T)):
            if not r.get(side + "_type"):
                t = tmap.get(lemma_key(r.get(side, "")))
                if t is None and len(allowed) == 1: t = next(iter(allowed))
                if t: r[side + "_type"] = t; fixed += 1
    e, rels, errs = validate(obj, corpus[doc]["text"])
    if doc not in best or len(rels) > len(best[doc]["relations"]):
        best[doc] = dict(doc_id=doc, method="B:LLM+schema (relaxed types)", model=g["model"], version="llm_v1-relaxed", ts=g["ts"],
                         entities=e, relations=rels, cost={}, fixed_types=fixed)
with open(ROOT / "results" / "llm_test_relaxed.jsonl", "w", encoding="utf-8") as f:
    for d in corpus:
        if corpus[d]["split"] == "test":
            f.write(json.dumps(best.get(d, dict(doc_id=d, entities=[], relations=[], method="B", model="", version="", ts="")), ensure_ascii=False) + "\n")
print("ok")
