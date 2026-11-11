"""ЛР14 · Результат 2: entity resolution реєстру сутностей Hub (ЛР8 RDF + ЛР9 граф + ЛР13 витяг).

Конвеєр: нормалізація → blocking → порівняння (рядки + векторне подання + атрибути) → рішення за порогом
(підібраним на dev) → [LLM-суддя для пар у «сірій зоні», PC] → злиття в кластери з provenance і unmerge.

  python quality/dedup.py candidates   # кандидати й ознаки → results/dedup_candidates.csv
  python quality/dedup.py eval         # поріг на dev, P/R/F1 на test → results/dedup_eval.json
  python quality/dedup.py merge        # кластери + журнал злиттів → data/clean/entity_registry.json, демонстрація unmerge
"""
from __future__ import annotations

import collections
import itertools
import json
import re
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kb  # noqa: E402

LAB = kb.LAB
RES = LAB / "results"
GOLD = LAB / "quality" / "pairs_gold.csv"
STOP = {"україни", "україна", "у", "в", "і", "й", "та", "з", "на", "для", "від", "до", "по", "the", "of"}
MAX_BLOCK = 40                         # ключі з більшими блоками («аналітик», «бот-акаунт») — стоп-ключі
GROUPS = {"ORG": "agent", "PLATFORM": "agent", "ACCOUNT": "agent", "PERSON": "person", "ANALYST": "person",
          "METHOD": "concept", "PHENOMENON": "concept", "NARRATIVE": "narrative", "RULE": "rule"}


# ------------------------------------------------------------------ 1. нормалізація
def norm(s: str) -> str:
    s = (s or "").lower().replace("’", "'").replace("ʼ", "'").replace("ё", "е")
    s = re.sub(r"[«»\"“”#]", " ", s)
    s = re.sub(r"[^\w\s'\-\.]", " ", s)
    return " ".join(s.replace(".", " ").split())


def stems(s: str) -> set[str]:
    return {t[:5] for t in re.split(r"[\s\-]+", norm(s)) if len(t) >= 3 and t not in STOP and not t.isdigit()}


CODE_RES = [(re.compile(r"\b(?:fch-|ф-)0?(\d+)\b", re.I), "FCH-{:02d}"),
            (re.compile(r"\b(?:rule-|r)(\d)\b", re.I), "RULE-{}"),
            (re.compile(r"\b(acc|off|org|nar|tool)-0*(\d+)\b", re.I), None)]


def codes(r) -> set[str]:
    txt = " ".join([r["name"], r.get("code") or ""])
    out = set()
    for rx, fmt in CODE_RES:
        for m in rx.finditer(txt):
            if fmt:
                out.add(fmt.format(int(m.group(1))))
            else:
                w = 3 if m.group(1).lower() == "acc" else 2
                out.add(f"{m.group(1).upper()}-{int(m.group(2)):0{w}d}")
    m = re.search(r"анонімний telegram-канал #?(\d+)", r["name"].lower())
    if m:                                   # псевдонім анонімного каналу = ACC-00N (правило ЛР13)
        out.add(f"ACC-{int(m.group(1)):03d}")
    return out


def numbers(r) -> set[str]:
    return set(re.findall(r"(?:#|\b[a-zа-я])(\d+)\b", r["name"].lower()))


def acronym(s: str) -> str:
    toks = [t for t in re.split(r"[\s\-]+", norm(re.sub(r"\(.*?\)", " ", s))) if len(t) >= 3 and t not in STOP]
    return "".join(t[0] for t in toks) if len(toks) >= 3 else ""


def aliases(r) -> list[str]:
    al = [r["name"]] + list(r["attrs"].get("variants", []))
    al += re.findall(r"\(([^)]+)\)", r["name"])
    return [a for a in al if a]


def prep(R):
    for r in R:
        r["norm"] = norm(re.sub(r"\(.*?\)", " ", r["name"])) or norm(r["name"])
        r["stems"] = stems(r["name"])
        r["codes"] = codes(r)
        r["nums"] = numbers(r)
        r["acr"] = acronym(r["name"])
        r["alias_norm"] = {norm(a) for a in aliases(r)}
    return R


def load_registry():
    R = kb.registry()
    keep = re.compile(r"^(ACC|OFF|ORG|NAR|FCH|TOOL|RULE)-|^Ф-")
    R = [r for r in R if r["type"] != "CASE_ID" or keep.match(r["name"])]
    return prep(R)


# ------------------------------------------------------------------ 2. blocking
def block(R):
    keys = collections.defaultdict(set)
    for i, r in enumerate(R):
        for s in r["stems"]:
            keys["s:" + s].add(i)
        for c in r["codes"]:
            keys["c:" + c].add(i)
        if r["acr"]:
            keys["a:" + r["acr"]].add(i)
        for a in r["alias_norm"]:                                 # абревіатура як окремий токен
            if len(a) <= 6 and " " not in a and len(a) >= 3:
                keys["a:" + a].add(i)
    pairs, stop = set(), []
    for k, ids in keys.items():
        if len(ids) > MAX_BLOCK:
            stop.append((k, len(ids)))
            continue
        pairs.update(itertools.combinations(sorted(ids), 2))
    n = len(R)
    return sorted(pairs), {"records": n, "all_pairs": n * (n - 1) // 2, "candidate_pairs": len(pairs),
                           "reduction_ratio": round(1 - len(pairs) / (n * (n - 1) / 2), 4),
                           "stop_keys": sorted(stop, key=lambda x: -x[1])[:10]}


# ------------------------------------------------------------------ 3. порівняння
def compat(a, b):
    ta, tb = a["type"], b["type"]
    if "CASE_ID" in (ta, tb):
        return True
    return GROUPS.get(ta) == GROUPS.get(tb)


def features(R, pairs):
    from rapidfuzz import fuzz
    from rapidfuzz.distance import JaroWinkler
    docs = [" ".join(sorted(r["alias_norm"])) for r in R]
    vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(2, 4)).fit(docs)
    X = vec.transform(docs)
    rows = []
    for i, j in pairs:
        a, b = R[i], R[j]
        cos = float((X[i] @ X[j].T).toarray()[0, 0])
        jw = JaroWinkler.similarity(a["norm"], b["norm"])
        tset = fuzz.token_set_ratio(a["norm"], b["norm"]) / 100
        sj = len(a["stems"] & b["stems"]) / max(1, len(a["stems"] | b["stems"]))
        code = 1 if a["codes"] & b["codes"] else (-1 if a["codes"] and b["codes"] else 0)
        numc = int(bool(a["nums"] and b["nums"] and not (a["nums"] & b["nums"])))
        acr = int(bool((a["acr"] and a["acr"] in b["alias_norm"]) or (b["acr"] and b["acr"] in a["alias_norm"])
                       or (a["alias_norm"] & b["alias_norm"])))
        rows.append(dict(a=a["rid"], b=b["rid"], name_a=a["name"], name_b=b["name"], type_a=a["type"],
                         type_b=b["type"], src_a=a["source"], src_b=b["source"], cos=round(cos, 3), jw=round(jw, 3),
                         tset=round(tset, 3), stem_jacc=round(sj, 3), code=code, num_conflict=numc, alias=acr,
                         type_compat=int(compat(a, b))))
    return pd.DataFrame(rows)


def score(df):
    s = 0.35 * df.cos + 0.25 * df.tset + 0.2 * df.jw + 0.2 * df.stem_jacc
    s = np.where(df.alias == 1, np.maximum(s, 0.9), s)
    s = np.where(df.code == 1, np.maximum(s, 0.95), s)
    s = np.where((df.code == -1) | (df.num_conflict == 1), np.minimum(s, 0.1), s)
    s = np.where(df.type_compat == 0, s * 0.5, s)
    return np.round(s, 3)


def candidates():
    R = load_registry()
    pairs, stats = block(R)
    df = features(R, pairs)
    df["score"] = score(df)
    df.sort_values("score", ascending=False).to_csv(RES / "dedup_candidates.csv", index=False)
    (RES / "dedup_blocking.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8")
    print(stats)
    return R, df


# ------------------------------------------------------------------ 4. оцінка: поріг на dev, P/R на test
def prf(y, p):
    tp = int(((y == 1) & (p == 1)).sum()); fp = int(((y == 0) & (p == 1)).sum()); fn = int(((y == 1) & (p == 0)).sum())
    P = tp / (tp + fp) if tp + fp else 1.0
    Rr = tp / (tp + fn) if tp + fn else 1.0
    return dict(tp=tp, fp=fp, fn=fn, P=round(P, 3), R=round(Rr, 3), F1=round(2 * P * Rr / (P + Rr), 3) if P + Rr else 0)


def evaluate():
    G = pd.read_csv(GOLD)
    C = pd.read_csv(RES / "dedup_candidates.csv")
    key = lambda a, b: "||".join(sorted([a, b]))
    sc = {key(a, b): s for a, b, s in zip(C.a, C.b, C.score)}
    G["score"] = [sc.get(key(a, b), 0.0) for a, b in zip(G.a, G.b)]          # пара поза блоками → 0 (пропуск blocking)
    dev, test = G[G.split == "dev"], G[G.split == "test"]
    grid = [round(x, 2) for x in np.arange(0.3, 0.96, 0.01)]
    curve = [(t, prf(dev.label.values, (dev.score >= t).astype(int).values)) for t in grid]
    best = max(curve, key=lambda x: (x[1]["F1"], x[1]["P"], x[0]))
    t = best[0]
    out = {"threshold": t, "dev": best[1], "test": prf(test.label.values, (test.score >= t).astype(int).values),
           "dev_curve": [{"t": a, **b} for a, b in curve],
           "n_pairs": {"dev": len(dev), "test": len(test), "pos": int(G.label.sum()), "neg": int((G.label == 0).sum())},
           "blocking_recall_gold": round(float((G[G.label == 1].score > 0).mean()), 3)}
    # сіра зона: t − 0.12 ≤ score < 0.95 → LLM-суддя (результати з ПК, якщо є). Пари зі збігом коду
    # (score ≥ 0.95) вирішує детерміноване правило: суддя не бачить відповідності кодів (Ф-01 ≡ FCH-01, псевдонім ≡ ACC)
    J = RES / "dedup_llm_judge.json"
    test = test.copy()
    test["grey"] = (test.score >= t - 0.12) & (test.score < 0.95)
    out["test_grey_pairs"] = int(test.grey.sum())
    if J.exists():
        jd = {key(x["a"], x["b"]): x["same"] for x in json.loads(J.read_text(encoding="utf-8"))["pairs"] if x.get("same") is not None}
        pred = [(int(jd[key(a, b)]) if g and key(a, b) in jd else int(s >= t))
                for a, b, s, g in zip(test.a, test.b, test.score, test.grey)]
        out["test_with_llm_judge"] = prf(test.label.values, np.array(pred))
        out["llm_judged_pairs"] = sum(1 for a, b, g in zip(test.a, test.b, test.grey) if g and key(a, b) in jd)
    errs = test[(test.score >= t) != (test.label == 1)]
    out["test_errors"] = errs[["a", "b", "name_a", "name_b", "label", "score"]].to_dict("records")
    (RES / "dedup_eval.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("threshold", "dev", "test", "n_pairs", "blocking_recall_gold", "test_grey_pairs")}, ensure_ascii=False))
    return out


# ------------------------------------------------------------------ 5. злиття з provenance і unmerge
class Registry:
    """Кластери сутностей. Злиття не видаляє записи: канонічна сутність зберігає members (вихідні записи з
    джерелом) і журнал merge_log; unmerge відновлює кластери до злиття за id операції."""

    def __init__(self, records):
        self.rec = {r["rid"]: r for r in records}
        self.cluster = {rid: rid for rid in self.rec}          # rid → id кластера
        self.log = []

    def members(self, cid):
        return sorted(r for r, c in self.cluster.items() if c == cid)

    def merge(self, a, b, evidence, actor, ts):
        ca, cb = self.cluster[a], self.cluster[b]
        if ca == cb:
            return None
        keep, gone = sorted([ca, cb], key=lambda c: (-len(self.members(c)), not c.startswith("G9:"), c))
        moved = self.members(gone)
        for r in moved:
            self.cluster[r] = keep
        op = {"op": f"M{len(self.log) + 1:04d}", "type": "merge", "into": keep, "from": gone, "moved": moved,
              "pair": [a, b], "evidence": evidence, "actor": actor, "ts": ts, "undone": False}
        self.log.append(op)
        return op

    def unmerge(self, op_id, actor, ts, reason):
        op = next(o for o in self.log if o["op"] == op_id)
        for r in op["moved"]:
            self.cluster[r] = op["from"]
        op["undone"] = True
        self.log.append({"op": f"U{len(self.log) + 1:04d}", "type": "unmerge", "undo": op_id, "actor": actor,
                         "ts": ts, "reason": reason})

    def canonical(self):
        out = []
        pri = {"ЛР9 граф Neo4j": 0, "ЛР8 RDF": 1, "ЛР13 витяг": 2}
        for cid in sorted(set(self.cluster.values())):
            ms = [self.rec[m] for m in self.members(cid)]
            head = min(ms, key=lambda r: (pri[r["source"]], r["type"] == "CASE_ID", len(r["name"])))
            types = {m["type"] for m in ms} - {"CASE_ID"}
            ctype = "PLATFORM" if {"PLATFORM", "ORG"} <= types and head["source"] == "ЛР13 витяг" else head["type"]
            out.append({"id": cid, "label": head["name"], "type": ctype,   # компанія з платформою → PLATFORM (схема ЛР13)
                        "sameAs": [m["rid"] for m in ms if m["rid"] != cid],
                        "members": [{"rid": m["rid"], "name": m["name"], "type": m["type"], "source": m["source"]} for m in ms]})
        return out


def merge():
    R = load_registry()
    C = pd.read_csv(RES / "dedup_candidates.csv")
    t = json.loads((RES / "dedup_eval.json").read_text(encoding="utf-8"))["threshold"]
    G = pd.read_csv(GOLD)
    gold = {"||".join(sorted([a, b])): l for a, b, l in zip(G.a, G.b, G.label)}
    reg = Registry(R)
    ts = kb.REF_DATE + "T12:00:00+02:00"
    n_auto = 0
    for r in C[C.score >= t].itertuples():
        g = gold.get("||".join(sorted([r.a, r.b])))
        if g == 0:                       # експерт/власник уже відхилив цю пару — не зливаємо
            continue
        ev = dict(score=r.score, cos=r.cos, jw=r.jw, tset=r.tset, code=r.code, alias=r.alias, threshold=t,
                  rule="auto score ≥ t" + (" + gold=1" if g == 1 else ""))
        if reg.merge(r.a, r.b, ev, "dedup.py v1 (авто, поріг з dev)", ts):
            n_auto += 1
    # демонстрація unmerge: хибне авто-злиття, яке виявив перегляд кластерів власником реєстру
    demo = None
    for op in reg.log:
        names = {reg.rec[x]["name"] for x in op["pair"]}
        if names == {"YouTube", "YouTuber"}:
            demo = op
            break
    if demo is None:
        demo = reg.log[-1]
    before = reg.members(demo["into"])
    reg.unmerge(demo["op"], "Хоптій Д. (власник реєстру)", kb.REF_DATE + "T13:00:00+02:00",
                "перегляд: платформа YouTube ≠ автор контенту (YouTuber); хибне злиття через спільний префікс назви")
    after = {"into": reg.members(demo["into"]), "restored": reg.members(demo["from"])}
    canon = reg.canonical()
    out = {"threshold": t, "records": len(R), "clusters": len(canon), "merged_clusters": sum(1 for c in canon if c["sameAs"]),
           "merge_ops": n_auto, "unmerge_demo": {"op": demo["op"], "members_before": before, "after": after},
           "entities": canon, "merge_log": reg.log}
    kb.CLEAN.mkdir(parents=True, exist_ok=True)
    (kb.CLEAN / "entity_registry.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print({k: out[k] for k in ("records", "clusters", "merged_clusters", "merge_ops", "unmerge_demo")})
    return out


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "all"
    if cmd in ("candidates", "all"):
        candidates()
    if cmd in ("eval", "all"):
        evaluate()
    if cmd in ("merge", "all"):
        merge()
