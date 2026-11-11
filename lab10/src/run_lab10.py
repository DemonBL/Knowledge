"""ЛР10 · повний прогін Результатів 2–5 (крім другого розмітника — див. kappa.py).

Запуск: F:\\kms_tools\\venv\\Scripts\\python.exe lab10\\src\\run_lab10.py
Вхід:   data/docs.jsonl (build_corpus.py), eval/gold.jsonl
Вихід:  results/lab10_results.json, data/chunks_*.jsonl, eval/kappa_candidates.jsonl, docs/*.md
"""
import json
import random
import statistics
import sys
import time
import traceback
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(LAB / "src"))
sys.path.insert(0, str(LAB.parent / "common"))
import numpy as np  # noqa: E402
from hub_common import write_json, now_iso, md_table  # noqa: E402
import search_core as S  # noqa: E402
import chunking as CH  # noqa: E402

random.seed(42)
np.random.seed(42)
RES = {"started": now_iso()}
OUT = LAB / "results"
OUT.mkdir(exist_ok=True)


def save():
    write_json(OUT / "lab10_results.json", RES)


def step(name):
    def deco(fn):
        def run(*a, **k):
            print(f"\n===== {name}", flush=True)
            t0 = time.time()
            try:
                r = fn(*a, **k)
                RES.setdefault("steps", {})[name] = {"ok": True, "sec": round(time.time() - t0, 1)}
                return r
            except Exception as e:  # noqa
                traceback.print_exc()
                RES.setdefault("steps", {})[name] = {"ok": False, "error": repr(e)}
            finally:
                save()
        return run
    return deco


docs = S.load_jsonl(LAB / "data" / "docs.jsonl")
DOCS = {d["doc_id"]: d for d in docs}
gold = S.load_jsonl(LAB / "eval" / "gold.jsonl")
answerable = [g for g in gold if g["type"] != "noanswer"]
for g in answerable:
    g["located"] = [S.locate(e, DOCS) for e in g["evidence"]]
def _mix(n_kw, n_para, n_multi):
    pick = lambda t, n: [g for g in answerable if g["type"] == t][:n]  # noqa: E731
    return pick("keyword", n_kw) + pick("paraphrase", n_para) + pick("multihop", n_multi)


CHUNK_Q = _mix(4, 4, 2)             # 10 запитів для порівняння chunking (усі типи)
EMB_Q = _mix(8, 8, 4)               # 20 запитів для порівняння embeddings (усі типи)


def eval_set(search_fn, items, chunks):
    rows, lat = [], []
    for it in items:
        t0 = time.perf_counter()
        res = search_fn(it["query"])
        lat.append((time.perf_counter() - t0) * 1000)
        grades = [S.chunk_grade(c, it, it["located"]) for c in chunks]
        m = S.metrics(res, it, it["located"], grades)
        m["qid"] = it["qid"]
        m["first_hit_rank"] = next((r for r, (c, _) in enumerate(res[:10], 1)
                                    if any(S.evidence_hit(c, e) for e in it["evidence"])), None)
        m["top_ids"] = [c["chunk_id"] for c, _ in res[:10]]
        m["top_scores"] = [round(s, 4) for _, s in res[:10]]
        rows.append(m)
    agg = {k: round(statistics.mean(r[k] for r in rows), 3) for k in ("recall@5", "recall@10", "mrr", "ndcg@10")}
    agg["latency_ms_median"] = round(statistics.median(lat), 1)
    agg["latency_ms_p95"] = round(float(np.percentile(lat, 95)), 1)
    return agg, rows


# ================================================================== R1: статистика корпусу
@step("corpus stats")
def corpus_stats():
    corpus = S.load_jsonl(LAB / "data" / "corpus.jsonl")
    by_type, by_sens = {}, {}
    for c in corpus:
        by_type[c["type"]] = by_type.get(c["type"], 0) + 1
        by_sens[c["sensitivity"]] = by_sens.get(c["sensitivity"], 0) + 1
    RES["corpus"] = {"docs": len(docs), "chunks": len(corpus), "by_type": by_type, "by_sensitivity": by_sens,
                     "wiki_docs": [[d["doc_id"], d["title"], d["date"], d["source_url"]] for d in docs if d["type"] == "encyclopedia"],
                     "internal_docs": [[d["doc_id"], d["title"], d["type"], d["sensitivity"], d["date"]] for d in docs if d["type"] != "encyclopedia"],
                     "avg_chunk_chars": round(statistics.mean(len(c["text"]) for c in corpus)),
                     "all_have_meta": all(all(c.get(k) for k in ("doc_id", "title", "section", "type", "date", "sensitivity", "source_url")) for c in corpus)}


# ================================================================== R2: chunking
@step("chunking comparison")
def chunking_cmp(enc):
    out = {}
    for name in ("fixed", "structural", "semantic"):
        t0 = time.perf_counter()
        if name == "fixed":
            chunks = [c for d in docs for c in CH.chunk_fixed(d)]
        elif name == "structural":
            chunks = [c for d in docs for c in CH.chunk_structural(d)]
        else:
            chunks = [c for d in docs for c in CH.chunk_semantic(d, enc.passages)]
        t_chunk = time.perf_counter() - t0
        with open(LAB / "data" / f"chunks_{name}.jsonl", "w", encoding="utf-8") as f:
            for c in chunks:
                f.write(json.dumps(c, ensure_ascii=False) + "\n")
        vs = S.VectorStore(enc, chunks)

        def fn(q, vs=vs):
            return vs.search(enc.queries([q])[0], 10)
        agg, rows = eval_set(fn, CHUNK_Q, chunks)
        ctx = [sum(len(c["text"]) for c in chunks if c["chunk_id"] in r["top_ids"][:5]) for r in rows]
        agg.update({"chunks": len(chunks), "avg_chunk_chars": round(statistics.mean(len(c["text"]) for c in chunks)),
                    "avg_context_chars_top5": round(statistics.mean(ctx)), "chunk_s": round(t_chunk, 1),
                    "index_s": vs.build_s})
        out[name] = {"agg": agg, "rows": rows}
        print(name, agg)
    RES["chunking"] = out


# ================================================================== R3: два embeddings
@step("embeddings comparison")
def emb_cmp(encs, chunks):
    out = {}
    for key, enc in encs.items():
        vs = S.VectorStore(enc, chunks)
        lat = []

        def fn(q, vs=vs, enc=enc):
            return vs.search(enc.queries([q])[0], 10)
        agg, rows = eval_set(fn, EMB_Q, chunks)
        out[key] = {"model": S.MODELS[key], "dim": enc.dim, "build_s": vs.build_s, "params": S.HNSW,
                    "agg": agg, "rows": rows}
        print(key, agg, "build", vs.build_s)
    RES["embeddings"] = out


@step("upsert/delete")
def upsert_test(enc, chunks):
    vs = S.VectorStore(enc, chunks)
    live0 = len(vs.live())
    targets = [d for d in docs if d["type"] == "encyclopedia"][:5]
    log = []
    # 3 документи оновлюємо (додаємо унікальний абзац), 2 видаляємо
    for i, d in enumerate(targets[:3]):
        nd = json.loads(json.dumps(d))
        marker = f"Тестове оновлення {i+1}: документ «{d['title']}» доповнено розділом про перевірку оновлень індексу (маркер UPD{i+1}X)."
        nd["sections"] = nd["sections"] + [["Оновлення", [marker]]]
        new_chunks = CH.chunk_structural(nd)
        removed, added = vs.upsert_doc(d["doc_id"], new_chunks)
        hit = vs.search(enc.queries([marker])[0], 3)
        log.append({"op": "upsert", "doc_id": d["doc_id"], "removed": removed, "added": added,
                    "top1_after": hit[0][0]["chunk_id"], "top1_is_new_text": "Тестове оновлення" in hit[0][0]["text"]})
    for d in targets[3:5]:
        probe = d["sections"][0][1][0][:300]
        before = [c["doc_id"] for c, _ in vs.search(enc.queries([probe])[0], 20)]
        n = vs.delete_doc(d["doc_id"])
        after = [c["doc_id"] for c, _ in vs.search(enc.queries([probe])[0], 50)]
        log.append({"op": "delete", "doc_id": d["doc_id"], "deleted_chunks": n,
                    "in_top20_before": d["doc_id"] in before, "in_top50_after": d["doc_id"] in after})
    RES["upsert_delete"] = {"live_before": live0, "live_after": len(vs.live()), "tombstones": len(vs.dead), "compactions": vs.compactions,
                            "ops": log}
    print(RES["upsert_delete"])


# ================================================================== R4 + R5: гібрид і оцінювання
@step("hybrid + eval")
def hybrid_eval(enc, rr, chunks):
    hs = S.HybridSearcher(chunks, enc, rr)
    configs = {}
    per = {}
    for mode in ("bm25", "dense", "hybrid", "hybrid_rerank"):
        def fn(q, mode=mode):
            return hs.search(q, mode, k=10)
        agg, rows = eval_set(fn, answerable, chunks)
        configs[mode] = agg
        per[mode] = {r["qid"]: r for r in rows}
        print(mode, agg)
    # by query type
    by_type = {}
    for mode in configs:
        for t in sorted({g["type"] for g in answerable}):
            ids = [g["qid"] for g in answerable if g["type"] == t]
            by_type.setdefault(mode, {})[t] = round(statistics.mean(per[mode][i]["mrr"] for i in ids), 3)
    # приклади виграшу / програшу гібриду
    wins, losses = [], []
    for g in answerable:
        rank = {m: per[m][g["qid"]]["first_hit_rank"] or 99 for m in per}
        best_single = min(rank["bm25"], rank["dense"])
        row = {"qid": g["qid"], "query": g["query"], "type": g["type"], **{f"rank_{m}": rank[m] for m in rank}}
        if rank["hybrid_rerank"] < best_single:
            wins.append(row)
        elif rank["hybrid_rerank"] > best_single:
            losses.append(row)
    # чи змінює reranker порядок
    changed = sum(per["hybrid"][g["qid"]]["top_ids"][:5] != per["hybrid_rerank"][g["qid"]]["top_ids"][:5] for g in answerable)
    # запити без відповіді: максимальний бал reranker
    noans = [g for g in gold if g["type"] == "noanswer"]
    na_scores = [hs.search(g["query"], "hybrid_rerank", 1)[0][1] for g in noans]
    ans_scores = [per["hybrid_rerank"][g["qid"]]["top_scores"][0] for g in answerable]
    RES["hybrid"] = {"configs": configs, "by_type_mrr": by_type, "wins": wins, "losses": losses,
                     "rerank_changed_top5": changed, "n_answerable": len(answerable),
                     "noanswer_top1_rerank": [[g["qid"], g["query"], round(s, 3)] for g, s in zip(noans, na_scores)],
                     "answerable_top1_rerank_median": round(statistics.median(ans_scores), 3),
                     "answerable_top1_rerank_p10": round(float(np.percentile(ans_scores, 10)), 3),
                     "per_query": per}
    # пре-фільтр
    pf = []
    probes = [("Хто був першоджерелом публікацій наративу «Колапс критичної інфраструктури»?", {}),
              ("Скільки незалежних доказів потрібно для вердикту «фейк»?", {}),
              ("Скільки незалежних доказів потрібно для вердикту «фейк»?", {"date_from": "2026-01-01"}),
              ("Що таке фактчекінг?", {"types": {"regulation", "rulebook"}})]
    for q, extra in probes:
        for role in ("guest", "analyst", "admin"):
            flt = S.make_filter(role, **extra)
            res = hs.search(q, "hybrid_rerank", 5, flt)
            pf.append({"query": q, "role": role, "filter": {k: (sorted(v) if isinstance(v, set) else v) for k, v in extra.items()},
                       "top": [[c["chunk_id"], c["sensitivity"], c["type"], c["date"]] for c, _ in res],
                       "violations": sum(not flt(c) for c, _ in res)})
    RES["prefilter"] = pf
    # кандидати для розмітки двома розмітниками (κ)
    kq = [g for g in answerable if g["type"] in ("paraphrase", "multihop", "keyword")][:12]
    with open(LAB / "eval" / "kappa_candidates.jsonl", "w", encoding="utf-8") as f:
        for g in kq:
            seen, cands = set(), []
            for m in ("hybrid_rerank", "bm25", "dense"):
                for cid in per[m][g["qid"]]["top_ids"][:4]:
                    if cid not in seen:
                        seen.add(cid)
                        c = next(x for x in chunks if x["chunk_id"] == cid)
                        cands.append({"chunk_id": cid, "title": c["title"], "section": c["section"], "text": c["text"]})
            f.write(json.dumps({"qid": g["qid"], "query": g["query"], "candidates": cands}, ensure_ascii=False) + "\n")
    # реальні вартість/затримка
    RES["cost_note"] = "усі моделі локальні (CPU): грошова вартість запиту 0; наведено затримку."


def write_docs():
    d = LAB / "docs"
    d.mkdir(exist_ok=True)
    if "chunking" in RES:
        rows = [[k, v["agg"]["chunks"], v["agg"]["avg_chunk_chars"], v["agg"]["recall@5"], v["agg"]["mrr"],
                 v["agg"]["avg_context_chars_top5"], v["agg"]["index_s"]] for k, v in RES["chunking"].items()]
        (d / "chunking_cmp.md").write_text("# Порівняння стратегій chunking (10 запитів, e5-small)\n\n" + md_table(
            ["стратегія", "фрагментів", "сер. символів", "recall@5", "MRR", "контекст top-5, симв.", "індекс, с"], rows), encoding="utf-8")
    if "embeddings" in RES:
        rows = [[v["model"], v["dim"], v["build_s"], v["agg"]["recall@5"], v["agg"]["mrr"], v["agg"]["latency_ms_median"],
                 v["agg"]["latency_ms_p95"]] for v in RES["embeddings"].values()]
        (d / "embeddings_cmp.md").write_text("# Порівняння embeddings (20 запитів, HNSW M=32, efC=200, efS=64)\n\n" + md_table(
            ["модель", "dim", "побудова, с", "recall@5", "MRR", "пошук мед., мс", "p95, мс"], rows), encoding="utf-8")
    if "hybrid" in RES:
        rows = [[k, *[v[m] for m in ("recall@5", "recall@10", "mrr", "ndcg@10", "latency_ms_median", "latency_ms_p95")]]
                for k, v in RES["hybrid"]["configs"].items()]
        (d / "search_eval.md").write_text("# Оцінювання конфігурацій пошуку\n\n" + md_table(
            ["конфігурація", "recall@5", "recall@10", "MRR", "nDCG@10", "мед. мс", "p95 мс"], rows), encoding="utf-8")


if __name__ == "__main__":
    corpus_stats()
    corpus = S.load_jsonl(LAB / "data" / "corpus.jsonl")
    e5 = S.Encoder("e5")
    chunking_cmp(e5)
    minilm = S.Encoder("minilm")
    emb_cmp({"e5": e5, "minilm": minilm}, corpus)
    upsert_test(e5, corpus)
    rr = S.Reranker()
    hybrid_eval(e5, rr, corpus)
    RES["finished"] = now_iso()
    save()
    write_docs()
    print("\nDONE", json.dumps(RES.get("steps"), ensure_ascii=False))
