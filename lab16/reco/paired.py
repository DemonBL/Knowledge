"""ЛР16 · парне порівняння двох конфігурацій: різниця nDCG@10 на тих самих користувачах, об'єднано за 5 seed,
бутстреп 2000 повторів; плюс кількість seed, де перемагає кожна.  python reco/paired.py --emb e5 → results/paired_{emb}.json"""
from __future__ import annotations

import argparse
import json
from datetime import datetime

import numpy as np

import data_gen as DG
import eval as EV
import items as IT
import models as M


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emb", default="lsa")
    ap.add_argument("--a", default="hybrid_weighted")
    ap.add_argument("--b", default="hybrid_rrf")
    a = ap.parse_args()
    prev = json.loads((IT.LAB / "results" / f"reco_eval_{a.emb}.json").read_text(encoding="utf-8"))
    wbest = {r["seed"]: tuple(r["w_best"]) for r in prev["runs"]}
    diffs, wins = [], {a.a: 0, a.b: 0}
    pairs = {}
    for s in prev["seeds"]:
        users, rows = DG.generate(s)
        tr, te = EV.split(rows, DG.T_TEST, datetime(2100, 1, 1))
        ctx = M.Context(IT.load_items(), tr, DG.T_TEST, emb=a.emb)
        tg, role = EV.targets(tr, te)
        _, pa, _ = EV.evaluate(ctx, tg, role, a.a, w=wbest[s])
        _, pb, _ = EV.evaluate(ctx, tg, role, a.b, w=wbest[s])
        d = [pa[u]["ndcg10"] - pb[u]["ndcg10"] for u in sorted(pa)]
        diffs += d
        wins[a.a if np.mean(d) > 0 else a.b] += 1
        pairs[s] = {"mean_diff": float(np.mean(d)), "users": len(d), "ties": int(sum(x == 0 for x in d))}
    x = np.array(diffs)
    rng = np.random.default_rng(0)
    bs = [x[rng.integers(0, len(x), len(x))].mean() for _ in range(2000)]
    out = {"emb": a.emb, "a": a.a, "b": a.b, "metric": "ndcg10", "mean_diff_a_minus_b": float(x.mean()),
           "ci95": [float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5))], "n_user_pairs": len(x),
           "share_ties": float(np.mean(x == 0)), "seed_wins": wins, "per_seed": pairs}
    (IT.LAB / "results" / f"paired_{a.emb}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(out, ensure_ascii=False))


if __name__ == "__main__":
    main()
