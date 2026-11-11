"""ЛР15 · консоль людини в циклі: перегляд черги data/pending.jsonl, рішення approve/reject з коментарем.
Схвалене записується лише з provenance (propose_fact.apply_fact); кожне рішення — у журнал аудиту.
  python agent/hitl_review.py                      # інтерактивно (на ПК)
  python agent/hitl_review.py --script a,r         # неінтерактивно (лише для перевірки коду)
"""
import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import propose_fact as PF  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--script", default="")
    ap.add_argument("--reviewer", default="")
    a = ap.parse_args()
    if not PF.PENDING.exists():
        print("Черга порожня.")
        return
    items = [json.loads(l) for l in open(PF.PENDING, encoding="utf-8") if l.strip()]
    decided = {json.loads(l)["proposal_id"] for l in open(PF.AUDIT, encoding="utf-8") if '"human_decision"' in l}
    items = [i for i in items if i["id"] not in decided]
    script = [x.strip() for x in a.script.split(",") if x.strip()]
    reviewer = a.reviewer or (input("Ваше ім'я (рецензент): ").strip() if not script else "scripted-test")
    for n, it in enumerate(items):
        print("\n" + "=" * 70)
        print(f"Пропозиція {it['id']}  ризик: {it['risk'].upper()}   рекомендація системи: {it['recommendation']}")
        print(f"  Факт:    {it['subject']} —{it['predicate']}→ {it['object']}")
        print(f"  Джерело: {it['source_id']}: «{it['quote']}»")
        print(f"  Чому такий ризик: {'; '.join(it['why'])}")
        print("  Перевірки: " + "; ".join(("✓ " if c['ok'] else "✗ ") + c['name'] for c in it['checks']))
        if script:
            d, comment = ("approve" if script[n].startswith("a") else "reject"), "scripted"
        else:
            ans = ""
            while ans not in ("y", "n", "т", "н"):
                ans = input("Схвалити запис у сховище? [y/n]: ").strip().lower()
            d = "approve" if ans in ("y", "т") else "reject"
            comment = input("Коментар (чому): ").strip()
        PF.audit("human_decision", it["id"], reviewer=reviewer, decision=d, comment=comment, risk=it["risk"])
        if d == "approve":
            PF.apply_fact(it, approved_by=f"людина: {reviewer}")
            print("  → записано з provenance")
        else:
            print("  → відхилено, у сховище не записано")
    PF.metrics()


if __name__ == "__main__":
    main()
