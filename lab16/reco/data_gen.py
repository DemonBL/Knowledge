"""ЛР16 · синтетичні дані взаємодій (задокументовано в docs/reco_design.md, розділ «Дані»).

Чому синтетичні: реальних журналів користувачів Hub немає; персональні дані не використовуються.
Модель генерації (seed фіксований, повтори — інші seed):
  • 60 користувачів: 4 admin, 42 analyst, 14 guest; кожен має 1–3 теми інтересу (ваги Діріхле, α = 0,6);
  • період 2026-08-01 … 2026-11-07; кількість сесій ~ Пуассон(λ = 9…22) — різна активність;
  • сесія: тема за вагами → документ теми (∝ √довжини) → 1–4 послідовні фрагменти, старт зміщений до початку документа;
    15 % сесій — «дослідження»: будь-який доступний документ за популярністю (Zipf);
  • доступні лише фрагменти, дозволені роллю, і документи, дата яких ≤ часу події (нові документи з'являються пізніше);
  • подія: view (вага 1) або cite (вага 3, імовірність 0,15).
Генератор НЕ використовує граф сутностей і ембединги — лише теми документів, щоб не підігравати жодному методу.
  python reco/data_gen.py --seed 16   → data/interactions.csv, data/users.csv
"""
from __future__ import annotations

import argparse
import csv
import math
from datetime import date, datetime, timedelta
from pathlib import Path

import numpy as np

import items as IT

START, END = datetime(2026, 8, 1), datetime(2026, 11, 7, 23, 0)
T_VAL, T_TEST = datetime(2026, 10, 6), datetime(2026, 10, 20)   # межі часового розбиття


def generate(seed=16, n_users=60):
    rng = np.random.default_rng(seed)
    items = IT.load_items()
    by_doc = {}
    for it in items:
        by_doc.setdefault(it["doc"], []).append(it)
    docs = sorted(by_doc)
    doc_date = {d: datetime.fromisoformat(by_doc[d][0]["date"]) for d in docs}
    zipf = {d: 1 / (r + 1) ** 0.8 for r, d in enumerate(rng.permutation(docs))}
    roles = ["admin"] * 4 + ["analyst"] * 42 + ["guest"] * 14
    topics = list(IT.TOPICS)
    users, rows = [], []
    for u in range(n_users):
        uid, role = f"U{u + 1:03d}", roles[u]
        acc = IT.ROLE_ACCESS[role]
        ok_topics = [t for t in topics if any(by_doc[d][0]["sensitivity"] in acc for d in IT.TOPICS[t] if d in by_doc)]
        k = int(rng.integers(1, 4))
        tsel = list(rng.choice(ok_topics, size=min(k, len(ok_topics)), replace=False))
        w = rng.dirichlet([0.6] * len(tsel))
        users.append(dict(user_id=uid, role=role, topics="|".join(tsel), weights="|".join(f"{x:.2f}" for x in w)))
        n_sess = rng.poisson(rng.uniform(9, 22))
        times = sorted(START + timedelta(seconds=float(s)) for s in rng.uniform(0, (END - START).total_seconds(), n_sess))
        for t0 in times:
            avail = [d for d in docs if doc_date[d] <= t0 and by_doc[d][0]["sensitivity"] in acc]
            if not avail:
                continue
            if rng.random() < 0.15:
                p = np.array([zipf[d] for d in avail])
                doc = avail[rng.choice(len(avail), p=p / p.sum())]
            else:
                t = tsel[rng.choice(len(tsel), p=w)]
                cand = [d for d in IT.TOPICS[t] if d in avail]
                if not cand:
                    continue
                p = np.array([math.sqrt(len(by_doc[d])) for d in cand])
                doc = cand[rng.choice(len(cand), p=p / p.sum())]
            chunks = by_doc[doc]
            start = min(int(rng.exponential(len(chunks) / 4)), len(chunks) - 1)
            n = int(rng.integers(1, 5))
            ts = t0
            for c in chunks[start:start + n]:
                ev = "cite" if rng.random() < 0.15 else "view"
                rows.append(dict(user_id=uid, role=role, item_id=c["id"], ts=ts.isoformat(timespec="seconds"), event=ev,
                                 weight=3 if ev == "cite" else 1))
                ts += timedelta(seconds=float(rng.integers(30, 400)))
    rows.sort(key=lambda r: r["ts"])
    return users, rows


def save(users, rows, out=IT.LAB / "data"):
    out.mkdir(exist_ok=True)
    with open(out / "users.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(users[0]))
        w.writeheader()
        w.writerows(users)
    with open(out / "interactions.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed", type=int, default=16)
    a = ap.parse_args()
    u, r = generate(a.seed)
    save(u, r)
    tr = sum(x["ts"] < T_TEST.isoformat() for x in r)
    print(f"користувачів {len(u)}, взаємодій {len(r)}, train {tr}, test {len(r) - tr}, унікальних фрагментів {len({x['item_id'] for x in r})}")
