"""ЛР16 · демонстрація фільтрів якості й доступу: як кожен фільтр змінює допустимий каталог і топ-5 рекомендацій.
  python reco/filters_demo.py → results/filters_demo.json
"""
from __future__ import annotations

import json
from datetime import datetime

import data_gen as DG
import items as IT
import models as M

CASES = [
    ("guest, усі фільтри (за замовчуванням)", "guest", {}),
    ("analyst, усі фільтри", "analyst", {}),
    ("admin, усі фільтри", "admin", {}),
    ("admin, без фільтра перевіреності", "admin", {"require_verified": False}),
    ("admin, включно із заміненими (superseded)", "admin", {"current_only": False}),
    ("analyst, свіжість ≤ 60 днів", "analyst", {"fresh_days": 60}),
]


def main():
    users, rows = DG.generate(16)
    items = IT.load_items()
    ctx = M.Context(items, rows, datetime(2026, 11, 8))
    seeds = {it["id"]: 1.0 for it in items if it["doc"] in ("INT-RULES", "INT-REG-2026", "W19")}   # інтерес: регламенти перевірки
    out = []
    for name, role, flt in CASES:
        cat = [it for it in items if IT.allowed(it, role, **flt)]
        ranked, _ = M.hybrid_rec(ctx, "DEMO", role, 5, "rrf", seeds=seeds, **flt)
        top = [ctx.by_id[i] for i, _ in ranked]
        out.append({"case": name, "role": role, "filters": flt, "catalog": len(cat),
                    "by_sensitivity": {s: sum(it["sensitivity"] == s for it in cat) for s in ("public", "internal", "restricted")},
                    "unverified_in_catalog": sum(not it["verified"] for it in cat),
                    "superseded_in_catalog": sum(it["status"] == "superseded" for it in cat),
                    "top5": [f"{it['id']} ({it['sensitivity']}, {it['date']}, {it['status']}{'' if it['verified'] else ', НЕПЕРЕВІРЕНЕ'})" for it in top]})
        print(name, out[-1]["catalog"], out[-1]["top5"])
    (IT.LAB / "results" / "filters_demo.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
