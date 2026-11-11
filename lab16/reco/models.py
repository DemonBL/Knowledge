"""ЛР16 · рекомендаційні підходи: популярність (baseline), графовий (шляхи), ембединги (kNN), гібрид (зважений / RRF).

Усі моделі навчаються ЛИШЕ на взаємодіях до межі часу (train) і рекомендують ще не бачені фрагменти, дозволені фільтрами
(RBAC, перевіреність, чинність, опц. свіжість). Графовий метод повертає для кожної рекомендації найкращий шлях — основу пояснення.
"""
from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import numpy as np

import items as IT

HALF_LIFE_DAYS = 21.0                 # згасання ваги старих взаємодій


def decay(ts: str, now: datetime):
    return 0.5 ** ((now - datetime.fromisoformat(ts)).total_seconds() / 86400 / HALF_LIFE_DAYS)


class Context:
    """Спільні дані: каталог, граф, вектори, профілі користувачів на train."""

    def __init__(self, items, train, now, emb="lsa", adj=None, labels=None, vec_path=None):
        self.items = items
        self.by_id = {it["id"]: it for it in items}
        self.idx = {it["id"]: i for i, it in enumerate(items)}
        self.now = now
        self.adj, self.labels = (adj, labels) if adj is not None else IT.build_graph(items)
        self.hist = defaultdict(dict)          # user → item → вага (згасання × тип події)
        self.pop = defaultdict(float)
        self.users = {}
        for r in train:
            w = decay(r["ts"], now) * float(r["weight"])
            self.hist[r["user_id"]][r["item_id"]] = self.hist[r["user_id"]].get(r["item_id"], 0) + w
            self.pop[r["item_id"]] += w
            self.users[r["user_id"]] = r["role"]
        self.n_users = max(1, len(self.hist))
        self.raw_pop = defaultdict(int)
        for r in train:
            self.raw_pop[r["item_id"]] += 1
        # «нові» фрагменти: документ доданий ≤ 30 днів тому і ще жодної взаємодії (можна перевизначити для експерименту)
        self.new_items = {it["id"] for it in items if self.raw_pop.get(it["id"], 0) == 0
                          and (now - datetime.fromisoformat(it["date"])).days <= 30}
        self.vecs = self._vectors(emb, vec_path)
        self.emb = emb

    def _vectors(self, emb, vec_path):
        if emb == "e5":
            p = vec_path or IT.LAB / "data" / "item_vecs_e5.npy"
            # splitlines + strip: файл, записаний на Windows, має \r\n — у Linux-контейнері split("\n") лишав \r і ламав порівняння
            ids = [x.strip() for x in (IT.LAB / "data" / "item_vecs_e5.ids").read_text(encoding="utf-8").splitlines() if x.strip()]
            v = np.load(p)
            assert ids == [it["id"] for it in self.items], "порядок фрагментів у векторах не збігається з каталогом"
            return v
        from sklearn.decomposition import TruncatedSVD
        from sklearn.feature_extraction.text import TfidfVectorizer
        X = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, sublinear_tf=True).fit_transform([it["embed_text"] for it in self.items])
        v = TruncatedSVD(128, random_state=16).fit_transform(X)
        return (v / (np.linalg.norm(v, axis=1, keepdims=True) + 1e-9)).astype("float32")

    def candidates(self, user, role, **flt):
        seen = self.hist.get(user, {})
        return [it for it in self.items if it["id"] not in seen and IT.allowed(it, role, **flt)]


# ------------------------------------------------------------------ baseline
def popularity(ctx: Context, user, role, k=10, **flt):
    c = ctx.candidates(user, role, **flt)
    return sorted(((it["id"], ctx.pop.get(it["id"], 0.0)) for it in c), key=lambda x: (-x[1], x[0]))[:k]


# ------------------------------------------------------------------ графовий: шляхи I→E→I, I→D→I, I→G→G→I
W_PATH = {"MENTIONS": 1.0, "IN_DOC": 0.6, "KG": 0.5, "NEXT_SECTION": 0.8}


def graph_scores(ctx: Context, seeds: dict, allowed_ids: set):
    """Сума вкладів шляхів довжини 2 (через сутність або документ) і 3 (сутність → ребро графа ЛР9 → сутність).
    Вклад = вага сіда × вага типу × 1/ступінь проміжного вузла (рідкісні сутності важливіші). Повертає бали й найкращий шлях."""
    adj = ctx.adj
    score, best = defaultdict(float), {}

    def add(cand, val, path):
        score[cand] += val
        if cand not in best or val > best[cand][0]:
            best[cand] = (val, path)

    for s, ws in seeds.items():
        si = "I:" + s
        for mid, t in adj.get(si, {}).items():
            if t == "NEXT_SECTION":                                    # шлях довжини 1: сусідній розділ
                if mid[2:] in allowed_ids:
                    add(mid[2:], ws * W_PATH["NEXT_SECTION"], [si, mid])
                continue
            deg = max(1, sum(1 for x in adj[mid] if x.startswith("I:")))
            base = ws * (W_PATH["IN_DOC"] if t == "IN_DOC" else W_PATH["MENTIONS"]) / deg
            for c, t2 in adj[mid].items():
                if c.startswith("I:") and c[2:] in allowed_ids and c != si:
                    add(c[2:], base, [si, mid, c])
            if mid.startswith("G:"):                                   # шлях через граф знань ЛР9
                for g2, rel in adj[mid].items():
                    if g2.startswith("G:"):
                        deg2 = max(1, sum(1 for x in adj[g2] if x.startswith("I:")))
                        for c, _ in adj[g2].items():
                            if c.startswith("I:") and c[2:] in allowed_ids and c != si:
                                add(c[2:], ws * W_PATH["KG"] / (deg * deg2), [si, mid, g2, c])
    return score, best


def graph_rec(ctx: Context, user, role, k=10, seeds=None, **flt):
    cand = {it["id"] for it in ctx.candidates(user, role, **flt)}
    seeds = seeds if seeds is not None else ctx.hist.get(user, {})
    sc, best = graph_scores(ctx, seeds, cand)
    ranked = sorted(sc.items(), key=lambda x: (-x[1], x[0]))[:k]
    return ranked, {i: best[i][1] for i, _ in ranked}


# ------------------------------------------------------------------ ембединги: kNN до профілю користувача
def emb_scores(ctx: Context, seeds: dict, cand_ids):
    if not seeds:
        return {}
    v = sum(w * ctx.vecs[ctx.idx[i]] for i, w in seeds.items() if i in ctx.idx)
    v = v / (np.linalg.norm(v) + 1e-9)
    ids = list(cand_ids)
    if not ids:
        return {}
    sims = ctx.vecs[[ctx.idx[i] for i in ids]] @ v
    return dict(zip(ids, map(float, sims)))


def emb_rec(ctx: Context, user, role, k=10, seeds=None, **flt):
    cand = [it["id"] for it in ctx.candidates(user, role, **flt)]
    seeds = seeds if seeds is not None else ctx.hist.get(user, {})
    sc = emb_scores(ctx, seeds, cand)
    return sorted(sc.items(), key=lambda x: (-x[1], x[0]))[:k]


# ------------------------------------------------------------------ гібрид
def _minmax(d):
    if not d:
        return {}
    lo, hi = min(d.values()), max(d.values())
    return {k: (v - lo) / (hi - lo) if hi > lo else 0.0 for k, v in d.items()}


def hybrid_rec(ctx: Context, user, role, k=10, mode="weighted", w=(0.5, 0.4, 0.1), rrf_k=60, seeds=None, new_slots=0, **flt):
    """mode=weighted: w_g·graph + w_e·emb + w_p·pop (бали нормалізовано min-max);
    mode=rrf: Σ 1/(rrf_k + ранг) за трьома списками.
    new_slots=n: гарантує до n позицій (з кінця топу) для фрагментів без жодної взаємодії, ранжованих лише за змістом."""
    cand = {it["id"] for it in ctx.candidates(user, role, **flt)}
    seeds = seeds if seeds is not None else ctx.hist.get(user, {})
    g, best = graph_scores(ctx, seeds, cand)
    e = emb_scores(ctx, seeds, cand)
    p = {i: math.log1p(ctx.pop.get(i, 0.0)) for i in cand}
    if mode == "rrf":
        tot = defaultdict(float)
        for d in (g, e, p):
            for r, (i, _) in enumerate(sorted(d.items(), key=lambda x: (-x[1], x[0])), 1):
                tot[i] += 1.0 / (rrf_k + r)
    else:
        g, e, p = _minmax(g), _minmax(e), _minmax(p)
        tot = {i: w[0] * g.get(i, 0) + w[1] * e.get(i, 0) + w[2] * p.get(i, 0) for i in cand}
    ranked = sorted(tot.items(), key=lambda x: (-x[1], x[0]))[:k]
    if new_slots:                                   # холодний старт документа: слоти для фрагментів без взаємодій
        fresh = [i for i in cand if i in ctx.new_items]
        content = defaultdict(float)
        for d in (g, e):
            for r, (i, _) in enumerate(sorted(((i, d[i]) for i in fresh if i in d), key=lambda x: (-x[1], x[0])), 1):
                content[i] += 1.0 / (rrf_k + r)
        top_new = [i for i, _ in sorted(content.items(), key=lambda x: (-x[1], x[0])) if i not in {j for j, _ in ranked}]
        have = sum(1 for i, _ in ranked if i in ctx.new_items)
        for i in top_new[:max(0, new_slots - have)]:
            ranked = ranked[:-1] + [(i, ranked[-1][1] if ranked else 0.0)]
    return ranked, {i: best[i][1] for i, _ in ranked if i in best}
