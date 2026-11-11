"""ЛР13 · гібрид A+Б: для кожного типу сутності й відношення обирається метод із вищим F1 на DEV (test не використовується).
Вихід: results/hybrid_routing.json, results/hybrid_test.jsonl, results/hybrid_all.jsonl (dev+test, для графа)."""
import json, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from evaluate import evaluate  # noqa: E402
from schema import ENTITY_TYPES, RELATIONS  # noqa: E402

sel = json.loads((ROOT / "results" / "llm_selection.json").read_text(encoding="utf-8"))["selected"]
ra, rb = evaluate(ROOT / "results" / "rules_dev.jsonl", "dev"), evaluate(ROOT / "results" / f"{sel}_dev.jsonl", "dev")
route = {}
for kind, names in (("ENT", ENTITY_TYPES), ("REL", RELATIONS)):
    for t in names:
        fa, fb = ra.get(f"{kind}:{t}", {}).get("F1", 0), rb.get(f"{kind}:{t}", {}).get("F1", 0)
        route[f"{kind}:{t}"] = dict(A=fa, B=fb, use="B" if fb > fa else "A")   # нічия → правила (дешевші й детерміновані)
(ROOT / "results" / "hybrid_routing.json").write_text(json.dumps(dict(llm_version=sel, routing=route), ensure_ascii=False, indent=1), encoding="utf-8")


def combine(a_path, b_paths, out_path):
    A = {r["doc_id"]: r for r in map(json.loads, open(a_path, encoding="utf-8"))}
    B = {r["doc_id"]: r for p in b_paths for r in map(json.loads, open(p, encoding="utf-8"))}
    with open(out_path, "w", encoding="utf-8") as f:
        for d, ra_ in A.items():
            rb_ = B.get(d, {"entities": [], "relations": [], "model": "", "version": ""})
            ents = [e | {"method": "A"} for e in ra_["entities"] if route[f"ENT:{e['type']}"]["use"] == "A"] + \
                   [e | {"method": "B"} for e in rb_["entities"] if route[f"ENT:{e['type']}"]["use"] == "B"]
            rels = [r | {"method": ra_["method"], "model": ra_["model"], "version": ra_["version"]} for r in ra_["relations"] if route[f"REL:{r['relation']}"]["use"] == "A"] + \
                   [r | {"method": rb_.get("method", "B"), "model": rb_.get("model", ""), "version": rb_.get("version", "")} for r in rb_["relations"] if route[f"REL:{r['relation']}"]["use"] == "B"]
            cost = {k: (ra_.get("cost", {}).get(k, 0) or 0) + (rb_.get("cost", {}).get(k, 0) or 0) for k in ("prompt_tokens", "completion_tokens", "latency_s", "calls", "retries")}
            f.write(json.dumps(dict(doc_id=d, method="A+B hybrid", model=f"{ra_['model']} + {rb_.get('model', '')}", version=f"{ra_['version']}+{sel}",
                                    ts=ra_["ts"], entities=ents, relations=rels, cost=cost), ensure_ascii=False) + "\n")


combine(ROOT / "results" / "rules_test.jsonl", [ROOT / "results" / "llm_test.jsonl"], ROOT / "results" / "hybrid_test.jsonl")
combine(ROOT / "results" / "rules_all.jsonl", [ROOT / "results" / f"{sel}_dev.jsonl", ROOT / "results" / "llm_test.jsonl"], ROOT / "results" / "hybrid_all.jsonl")
print(json.dumps(route, ensure_ascii=False, indent=0)[:2000])
