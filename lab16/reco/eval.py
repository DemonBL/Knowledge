"""ЛР16 · офлайн-оцінка рекомендацій із часовим розбиттям.

Розбиття (без витоку з майбутнього):
  train_fit < 2026-10-06 ≤ validation < 2026-10-20 ≤ test
  • підбір параметрів гібриду — модель на train_fit, метрики на validation;
  • фінальна оцінка — модель на усіх взаємодіях < 2026-10-20 (train), метрики на test;
  • популярність, профілі, згасання рахуються від моменту межі (now = межа), а не від кінця даних;
  • релевантні = фрагменти, які користувач відкрив у test і НЕ відкривав у train (повторні перегляди не рахуються);
  • фільтри доступу — за роллю користувача (оцінюємо те, що йому дозволено показати).
Метрики: precision@5, recall@5, nDCG@10, coverage@10 (частка доступного каталогу в рекомендаціях), novelty@10
(середня самоінформація −log2 p(i) за популярністю в train). Невизначеність — бутстреп за користувачами (1000) і 5 seed генератора.
  python reco/eval.py [--emb lsa|e5] [--seeds 16 17 18 19 20]  → results/reco_eval.json, docs/img/*.png
"""
from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from datetime import datetime

import numpy as np

import data_gen as DG
import items as IT
import models as M

K_P, K_N = 5, 10


def split(rows, t0, t1):
    return [r for r in rows if r["ts"] < t0.isoformat()], [r for r in rows if t0.isoformat() <= r["ts"] < t1.isoformat()]


def targets(train, test):
    seen = defaultdict(set)
    for r in train:
        seen[r["user_id"]].add(r["item_id"])
    tg, role = defaultdict(set), {}
    for r in test:
        role[r["user_id"]] = r["role"]
        if r["item_id"] not in seen[r["user_id"]]:
            tg[r["user_id"]].add(r["item_id"])
    return {u: s for u, s in tg.items() if s}, role


def dcg(rel):
    return sum(r / math.log2(i + 2) for i, r in enumerate(rel))


def per_user(rec, rel):
    hit5 = sum(1 for i in rec[:K_P] if i in rel)
    ideal = dcg([1] * min(len(rel), K_N))
    return dict(p5=hit5 / K_P, r5=hit5 / len(rel), ndcg10=dcg([1 if i in rel else 0 for i in rec[:K_N]]) / ideal if ideal else 0.0)


CONFIGS = {
    "popularity": lambda ctx, u, r, **kw: M.popularity(ctx, u, r, K_N),
    "graph": lambda ctx, u, r, **kw: M.graph_rec(ctx, u, r, K_N)[0],
    "embeddings": lambda ctx, u, r, **kw: M.emb_rec(ctx, u, r, K_N),
    "hybrid_weighted": lambda ctx, u, r, w=(0.5, 0.4, 0.1), **kw: M.hybrid_rec(ctx, u, r, K_N, "weighted", w)[0],
    "hybrid_rrf": lambda ctx, u, r, **kw: M.hybrid_rec(ctx, u, r, K_N, "rrf")[0],
}


def evaluate(ctx, tg, role, cfg, **kw):
    per, recs = {}, {}
    for u, rel in sorted(tg.items()):
        r = role[u]
        rec = [i for i, _ in CONFIGS[cfg](ctx, u, r, **kw)]
        recs[u] = rec
        per[u] = per_user(rec, rel)
    allowed_cat = {it["id"] for it in ctx.items if any(IT.allowed(it, role[u]) for u in tg)}
    cov = len({i for rec in recs.values() for i in rec[:K_N]}) / len(allowed_cat)
    tot = sum(ctx.raw_pop.values()) or 1
    nov = np.mean([-math.log2((ctx.raw_pop.get(i, 0) + 1) / (tot + len(ctx.items))) for rec in recs.values() for i in rec[:K_N]])
    agg = {m: float(np.mean([p[m] for p in per.values()])) for m in ("p5", "r5", "ndcg10")}
    agg.update(coverage10=cov, novelty10=float(nov), users=len(per))
    return agg, per, recs


def bootstrap(per, B=1000, seed=0):
    rng = np.random.default_rng(seed)
    us = sorted(per)
    out = {}
    for m in ("p5", "r5", "ndcg10"):
        x = np.array([per[u][m] for u in us])
        bs = [x[rng.integers(0, len(x), len(x))].mean() for _ in range(B)]
        out[m] = [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))]
    return out


def tune(rows, emb):
    tr, va = split(rows, DG.T_VAL, DG.T_TEST)
    ctx = M.Context(IT.load_items(), tr, DG.T_VAL, emb=emb)
    tg, role = targets(tr, va)
    grid = [(g, e, round(1 - g - e, 2)) for g in np.arange(0, 1.01, 0.1) for e in np.arange(0, 1.01, 0.1) if g + e <= 1.0001]
    res = []
    for w in grid:
        w = tuple(round(float(x), 2) for x in w)
        a, _, _ = evaluate(ctx, tg, role, "hybrid_weighted", w=w)
        res.append((a["ndcg10"], w, a))
    res.sort(key=lambda x: -x[0])
    return res[0][1], [{"w": list(w), "ndcg10_val": round(n, 4)} for n, w, _ in res[:10]], len(tg)


def run(seed, emb, adj_labels=None):
    users, rows = DG.generate(seed)
    w_best, top, n_val = tune(rows, emb)
    tr, te = split(rows, DG.T_TEST, datetime(2100, 1, 1))
    ctx = M.Context(IT.load_items(), tr, DG.T_TEST, emb=emb)
    tg, role = targets(tr, te)
    out = {"seed": seed, "emb": emb, "w_best": w_best, "val_top": top, "val_users": n_val, "train": len(tr), "test": len(te),
           "test_users": len(tg), "configs": {}}
    for cfg in CONFIGS:
        a, per, recs = evaluate(ctx, tg, role, cfg, w=w_best)
        out["configs"][cfg] = {"agg": a, "ci95": bootstrap(per)}
    return out, ctx, tg, role


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emb", default="lsa")
    ap.add_argument("--seeds", type=int, nargs="+", default=[16, 17, 18, 19, 20])
    a = ap.parse_args()
    runs = []
    for s in a.seeds:
        r, *_ = run(s, a.emb)
        runs.append(r)
        print(s, "w*", r["w_best"], {c: round(v["agg"]["ndcg10"], 3) for c, v in r["configs"].items()}, flush=True)
    summ = {}
    for cfg in CONFIGS:
        summ[cfg] = {}
        for m in ("p5", "r5", "ndcg10", "coverage10", "novelty10"):
            xs = [r["configs"][cfg]["agg"][m] for r in runs]
            summ[cfg][m] = {"mean": float(np.mean(xs)), "sd": float(np.std(xs, ddof=1)) if len(xs) > 1 else 0.0}
    res = {"emb": a.emb, "seeds": a.seeds, "split": {"train_fit_before": DG.T_VAL.isoformat(), "test_from": DG.T_TEST.isoformat()},
           "runs": runs, "summary": summ}
    (IT.LAB / "results" / f"reco_eval_{a.emb}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for cfg, v in summ.items():
        print(f"{cfg:16s}", "  ".join(f"{m}={v[m]['mean']:.3f}±{v[m]['sd']:.3f}" for m in v))


if __name__ == "__main__":
    main()
