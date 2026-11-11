"""ЛР13 · оцінювання витягу: P/R/F1 для сутностей і відношень (загалом і за типами), частка без підтвердженої цитати,
частка вигаданих, вартість/документ. Порівняння на рівні документа за канонічними ключами (src/normalize.py).
Запуск: python src/evaluate.py --split dev|test --pred results/rules_test.jsonl [--pred results/llm_test.jsonl ...]"""
import argparse, json, re, sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from normalize import canon, rel_tail_key, same_entity, lemma_key  # noqa: E402
from schema import SYMMETRIC, RELATIONS  # noqa: E402

CORPUS = {d["doc_id"]: d for d in map(json.loads, open(ROOT / "data" / "corpus.jsonl", encoding="utf-8"))}
GOLD = {g["doc_id"]: g for g in map(json.loads, open(ROOT / "data" / "gold.jsonl", encoding="utf-8"))}


def gold_sets(doc_id):
    g, text = GOLD[doc_id], CORPUS[doc_id]["text"]
    ents = {(m["norm"] if m["type"] == "DATE" else canon(m["norm"], m["type"], text), m["type"]) for m in g["entities"]}
    rels = set()
    for r in g["relations"]:
        ht = next((m["type"] for m in g["entities"] if m["norm"] == r["head"]), "ORG")
        tt = next((m["type"] for m in g["entities"] if m["norm"] == r["tail"]), "ORG")
        h = r["head"] if ht == "DATE" else canon(r["head"], ht, text)
        t = r["tail"] if tt == "DATE" else canon(r["tail"], tt, text)
        rels.add(key3(h, r["relation"], rel_tail_key(t, tt)))
    return ents, rels


def key3(h, r, t):
    return (r, *sorted((h, t))) if r in SYMMETRIC else (r, h, t)


def pred_sets(rec):
    text = CORPUS[rec["doc_id"]]["text"]
    ents = {(canon(e["text"], e["type"], text), e["type"]) for e in rec.get("entities", [])}
    rels = set()
    for r in rec.get("relations", []):
        ht, tt = r.get("head_type") or "ORG", r.get("tail_type") or "ORG"
        h, t = canon(r["head"], ht, text), canon(r["tail"], tt, text)
        rels.add(key3(h, r["relation"], rel_tail_key(t, tt)))
    return ents, rels


def match_count(pred, gold, ent_mode):
    """Кількість збігів з урахуванням м'якого збігу PERSON."""
    used, tp = set(), 0
    for p in pred:
        for g in gold:
            if g in used: continue
            ok = (p[1] == g[1] and same_entity(p[0], g[0], p[1])) if ent_mode else (
                p[0] == g[0] and all(a == b or (" " in a and " " in b and same_entity(a, b, "PERSON")) for a, b in zip(p[1:], g[1:])))
            if ok:
                used.add(g); tp += 1; break
    return tp


def prf(tp, np_, ng):
    p = tp / np_ if np_ else 0.0; r = tp / ng if ng else 0.0
    return dict(P=round(p, 3), R=round(r, 3), F1=round(2 * p * r / (p + r), 3) if p + r else 0.0, tp=tp, pred=np_, gold=ng)


def evaluate(pred_path, split):
    preds = {r["doc_id"]: r for r in map(json.loads, open(pred_path, encoding="utf-8"))}
    docs = [d for d, g in GOLD.items() if g["split"] == split]
    agg = defaultdict(lambda: [0, 0, 0])
    no_ev = fabricated = nrel = 0
    cost = defaultdict(float)
    errors = []
    for d in docs:
        ge, gr = gold_sets(d)
        rec = preds.get(d, {"doc_id": d, "entities": [], "relations": []})
        pe, pr_ = pred_sets(rec)
        text = CORPUS[d]["text"]
        for t in set(x[1] for x in ge | pe):
            P_, G_ = {x for x in pe if x[1] == t}, {x for x in ge if x[1] == t}
            tp = match_count(P_, G_, True)
            for k in (("ENT", "ALL"), ("ENT", t)):
                agg[k][0] += tp; agg[k][1] += len(P_); agg[k][2] += len(G_)
        for rt in set(x[0] for x in gr | pr_):
            P_, G_ = {x for x in pr_ if x[0] == rt}, {x for x in gr if x[0] == rt}
            tp = match_count(P_, G_, False)
            for k in (("REL", "ALL"), ("REL", rt)):
                agg[k][0] += tp; agg[k][1] += len(P_); agg[k][2] += len(G_)
            for x in P_:
                if match_count({x}, G_, False) == 0: errors.append(dict(doc=d, kind="FP", rel=x))
            for x in G_:
                if match_count(P_, {x}, False) == 0: errors.append(dict(doc=d, kind="FN", rel=x))
        for r in rec.get("relations", []):
            nrel += 1
            ev = r.get("evidence", "")
            if not ev or ev not in text: no_ev += 1
            if any(lemma_key(x)[:4] not in lemma_key(text) for x in (r["head"], r["tail"]) if x and not re.match(r"\d", x)):
                fabricated += 1
        for k in ("prompt_tokens", "completion_tokens", "latency_s", "calls", "retries"):
            cost[k] += rec.get("cost", {}).get(k, 0) or 0
    res = {f"{a}:{b}": prf(*v) for (a, b), v in sorted(agg.items())}
    res["_quality"] = dict(relations_pred=nrel, without_verified_evidence=no_ev, without_evidence_share=round(no_ev / nrel, 3) if nrel else 0.0,
                           fabricated=fabricated, fabricated_share=round(fabricated / nrel, 3) if nrel else 0.0)
    res["_cost_per_doc"] = {k: round(v / len(docs), 2) for k, v in cost.items()}
    res["_errors"] = errors
    return res


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--split", default="dev"); ap.add_argument("--pred", action="append", required=True)
    a = ap.parse_args()
    for p in a.pred:
        r = evaluate(ROOT / p, a.split)
        print(f"== {p} [{a.split}]")
        for k, v in r.items():
            if not k.startswith("_"): print(f"  {k:28} P={v['P']:.3f} R={v['R']:.3f} F1={v['F1']:.3f}  ({v['tp']}/{v['pred']}/{v['gold']})")
        print("  ", r["_quality"], r["_cost_per_doc"])
