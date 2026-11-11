"""ЛР16 · холодний старт: два сценарії з метриками (5 seed генератора, бутстреп-інтервали).

A. Новий користувач. Користувачів тестового періоду «обнуляємо»: їхню історію з train прибрано (вона лишається для
   популярності й інших користувачів). На онбордингу користувач обирає теми інтересу (у синтетичних даних — заявлені
   теми з users.csv). Порівнюємо:
     • pop_global — загальна популярність;
     • pop_topic  — популярність у межах обраних тем;
     • onboard_hybrid — сіди = фрагменти документів обраних тем (вага 1/кількість) → гібрид RRF (граф + ембединги + популярність);
     • warm3 — після перших 3 взаємодій у test: гібрид RRF на цих 3 сідах (оцінка на решті test-взаємодій).
B. Новий документ. Обираємо 6 публічних документів; усі взаємодії з ними видаляємо з train (так, ніби документ щойно
   додано — популярності немає). Метрики: hit@10 нових фрагментів для користувачів, які їх відкрили в test, і
   exposure — частка нових фрагментів, що потрапили хоча б в один топ-10. Популярність їх не бачить за побудовою;
   графовий (сутності/документ) і ембединговий методи — бачать за змістом. Гібрид RRF «топить» їх через нульову
   популярність, тому додано варіант new_slot2: дві останні позиції топ-10 віддано найкращим за змістом новим фрагментам.
  python reco/cold_start.py [--emb lsa|e5] → results/cold_start_{emb}.json
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime

import numpy as np

import data_gen as DG
import eval as EV
import items as IT
import models as M

NEW_DOCS = ["W09", "W19", "W06", "W13", "W18", "W02"]


def topic_seeds(items, topics):
    seeds = {}
    for t in topics:
        ds = IT.TOPICS.get(t, [])
        its = [it for it in items if it["doc"] in ds]
        for it in its:
            seeds[it["id"]] = 1.0 / max(1, len(its))
    return seeds


def new_user(seed, emb):
    users, rows = DG.generate(seed)
    tr_all, te = EV.split(rows, DG.T_TEST, datetime(2100, 1, 1))
    test_users = {r["user_id"] for r in te}
    utop = {u["user_id"]: u["topics"].split("|") for u in users}
    role = {u["user_id"]: u["role"] for u in users}
    tr = [r for r in tr_all if r["user_id"] not in test_users]          # нові користувачі: без власної історії
    ctx = M.Context(IT.load_items(), tr, DG.T_TEST, emb=emb)
    by_u = defaultdict(list)
    for r in te:
        by_u[r["user_id"]].append(r)
    res = {c: {} for c in ("pop_global", "pop_topic", "onboard_hybrid", "warm3")}
    recs_all = {c: [] for c in res}
    for u, evs in sorted(by_u.items()):
        rel = {r["item_id"] for r in evs}
        nu = "NEW-" + u
        seeds = topic_seeds(ctx.items, utop[u])
        pg = [i for i, _ in M.popularity(ctx, nu, role[u], EV.K_N)]
        cand = [it for it in ctx.candidates(nu, role[u]) if it["topic"] in utop[u]]
        pt = [it["id"] for it in sorted(cand, key=lambda it: (-ctx.pop.get(it["id"], 0), it["id"]))[:EV.K_N]]
        oh = [i for i, _ in M.hybrid_rec(ctx, nu, role[u], EV.K_N, "rrf", seeds=seeds)[0]]
        for c, rec in (("pop_global", pg), ("pop_topic", pt), ("onboard_hybrid", oh)):
            res[c][u] = EV.per_user(rec, rel)
            recs_all[c].append(rec)
        first = []
        for r in evs:
            if r["item_id"] not in first:
                first.append(r["item_id"])
            if len(first) == 3:
                break
        rest = rel - set(first)
        if len(first) == 3 and rest:
            ctx.hist[nu] = {i: 1.0 for i in first}
            w3 = [i for i, _ in M.hybrid_rec(ctx, nu, role[u], EV.K_N, "rrf")[0]]
            del ctx.hist[nu]
            res["warm3"][u] = EV.per_user(w3, rest)
            recs_all["warm3"].append(w3)
    cat = len([it for it in ctx.items if IT.allowed(it, "admin")])
    out = {}
    for c, per in res.items():
        agg = {m: float(np.mean([p[m] for p in per.values()])) for m in ("p5", "r5", "ndcg10")}
        agg["coverage10"] = len({i for rec in recs_all[c] for i in rec}) / cat
        out[c] = {"agg": agg, "ci95": EV.bootstrap(per), "users": len(per)}
    return out


def new_doc(seed, emb):
    users, rows = DG.generate(seed)
    role = {u["user_id"]: u["role"] for u in users}
    items = IT.load_items()
    newset = {it["id"] for it in items if it["doc"] in NEW_DOCS}
    tr_all, te = EV.split(rows, DG.T_TEST, datetime(2100, 1, 1))
    tr = [r for r in tr_all if r["item_id"] not in newset]                 # документи «щойно додані»
    ctx = M.Context(items, tr, DG.T_TEST, emb=emb)
    ctx.new_items = set(newset)
    tg = defaultdict(set)
    for r in te:
        if r["item_id"] in newset:
            tg[r["user_id"]].add(r["item_id"])
    cfgs = {"popularity": lambda u: M.popularity(ctx, u, role[u], EV.K_N),
            "graph": lambda u: M.graph_rec(ctx, u, role[u], EV.K_N)[0],
            "embeddings": lambda u: M.emb_rec(ctx, u, role[u], EV.K_N),
            "hybrid_rrf": lambda u: M.hybrid_rec(ctx, u, role[u], EV.K_N, "rrf")[0],
            "hybrid_rrf+new_slot2": lambda u: M.hybrid_rec(ctx, u, role[u], EV.K_N, "rrf", new_slots=2)[0]}
    out = {}
    all_users = sorted({r["user_id"] for r in te} | set(ctx.hist))
    for c, f in cfgs.items():
        hits = []
        exposed = set()
        for u in all_users:
            rec = [i for i, _ in f(u)]
            exposed |= set(rec) & newset
            if u in tg:
                hits.append(len(set(rec) & tg[u]) / min(len(tg[u]), EV.K_N))
        out[c] = {"hit10_new": float(np.mean(hits)) if hits else 0.0, "exposure_new": len(exposed) / len(newset),
                  "users_with_new": len(tg)}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--emb", default="lsa")
    ap.add_argument("--seeds", type=int, nargs="+", default=[16, 17, 18, 19, 20])
    a = ap.parse_args()
    A, B = [], []
    for s in a.seeds:
        A.append(new_user(s, a.emb))
        B.append(new_doc(s, a.emb))
        print(s, {c: round(v["agg"]["ndcg10"], 3) for c, v in A[-1].items()}, {c: round(v["hit10_new"], 3) for c, v in B[-1].items()}, flush=True)
    sA = {c: {m: {"mean": float(np.mean([r[c]["agg"][m] for r in A])), "sd": float(np.std([r[c]["agg"][m] for r in A], ddof=1)) if len(A) > 1 else 0.0}
              for m in ("p5", "r5", "ndcg10", "coverage10")} for c in A[0]}
    sB = {c: {m: {"mean": float(np.mean([r[c][m] for r in B])), "sd": float(np.std([r[c][m] for r in B], ddof=1)) if len(B) > 1 else 0.0}
              for m in ("hit10_new", "exposure_new")} for c in B[0]}
    res = {"emb": a.emb, "seeds": a.seeds, "new_docs": NEW_DOCS, "new_user": {"runs": A, "summary": sA}, "new_doc": {"runs": B, "summary": sB}}
    (IT.LAB / "results" / f"cold_start_{a.emb}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    for c, v in sA.items():
        print("A", f"{c:15s}", "  ".join(f"{m}={v[m]['mean']:.3f}±{v[m]['sd']:.3f}" for m in v))
    for c, v in sB.items():
        print("B", f"{c:15s}", "  ".join(f"{m}={v[m]['mean']:.3f}±{v[m]['sd']:.3f}" for m in v))


if __name__ == "__main__":
    main()
