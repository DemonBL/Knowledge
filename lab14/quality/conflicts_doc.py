"""Генерує quality/conflicts.md з results/conflicts_baseline.json, quality/decisions.csv і data/clean/alternatives.jsonl."""
import csv
import json
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
K = json.loads((LAB / "results" / "conflicts_baseline.json").read_text(encoding="utf-8"))
KC = json.loads((LAB / "results" / "conflicts_clean.json").read_text(encoding="utf-8"))
D = {r["id"]: r for r in csv.DictReader(open(LAB / "quality" / "decisions.csv", encoding="utf-8"))}
A = [json.loads(l) for l in open(LAB / "data" / "clean" / "alternatives.jsonl", encoding="utf-8")]
MAP = {"K1": "D3", "K2": "D4", "K3": "D5", "K4": "D6", "K5": "D7", "K6": "D9"}
TYPE = {"logical": "логічна", "value": "значення (різні джерела)", "temporal": "часова", "terminological": "термінологічна"}
L = ["# Суперечності та їх розв'язання (ЛР14, Результат 3)", "",
     "Детектор: `python quality/conflicts.py baseline|clean`.",
     "Логічні правила — SPARQL-«reasoner» над RDF-знімком; ті самі запити працюють як CI-перевірки T03–T06.", "",
     f"Знайдено **{len(K)} суперечностей** 4 типів. Після очищення детектор не знаходить жодної неврахованої: {len(KC)}.", "",
     "| ID | Тип | Суперечність | Випадків | Стратегія | Виправлення | Рішення |", "|---|---|---|---|---|---|---|"]
for c in K:
    d = D[MAP[c["id"]]]
    L.append(f"| {c['id']} | {TYPE[c['type']]} | {c['title']} | {len(c['items'])} | {d['strategy']} | {d['decision']} | {d['id']} |")
L += ["", "## Деталі", ""]
for c in K:
    d = D[MAP[c["id"]]]
    L += [f"### {c['id']} · {c['title']}", "",
          f"- **Тип:** {TYPE[c['type']]}.",
          f"- **Як знайдено:** {c['detector']}.",
          f"- **Випадки:** {'; '.join(c['items'][:10])}{' …' if len(c['items']) > 10 else ''}.",
          f"- **Стратегія:** {d['strategy']}.",
          f"- **Виправлення:** {d['decision']}; зміна: {d['change']}.",
          f"- **Чому:** {d['why']}.",
          f"- **Ризик:** {d['risk']}. **Запропонував:** {d['proposed_by']}. **Схвалив:** {d['approved_by']}, {d['date']}.", ""]
L += ["## Збережені альтернативи з походженням", "",
      f"Файл `data/clean/alternatives.jsonl` містить {len(A)} записів. Значення не перезаписуються, а зберігаються поряд:",
      "- `current` — значення, що використовується;",
      "- `current-provisional` — тимчасово чинне;",
      "- `alternative` — конкурентне значення.", "",
      "Кожен запис має джерело, правило, дату й посилання на рішення. У графі Neo4j альтернативи видно як властивості:",
      "- `complianceStatus`;",
      "- `firstSeenAt` і `temporalFlag`;",
      "- `altCondition`.", "",
      "| Об'єкт | Властивість | Значення | Статус | Джерело | Рішення |", "|---|---|---|---|---|---|"]
for a in [x for x in A if x["subject"] in ("VRD-27", "VRD-01", "RULE-2")]:
    L.append(f"| {a['subject']} | {a['property']} | {a['value']} | {a['status']} | {a['source']} | {a['decision']} |")
L += ["", "Випадки з альтернативами:",
      "- **K1** — 6 вердиктів × 2 значення категорії;",
      "- **K2** — 10 вердиктів × 2 дати;",
      "- **K4** — 2 формулювання умови RULE-2.", "",
      "## Журнал рішень", "",
      "Повний журнал — `quality/decisions.csv`. У ньому 12 рішень, для кожного вказано, хто запропонував, хто схвалив, дату, ризик і причину.", "",
      "| ID | Проблема | Рішення | Ризик | Запропонував | Схвалив | Дата |", "|---|---|---|---|---|---|---|"]
for d in D.values():
    L.append(f"| {d['id']} | {d['conflict_or_issue']} | {d['decision']} | {d['risk']} | {d['proposed_by']} | {d['approved_by']} | {d['date']} |")
L += ["", "Правило схвалення за ризиком:",
      "- **низький** — власник схвалює пакетом;",
      "- **середній** — власник переглядає кожен випадок, оригінальне значення лишається альтернативою;",
      "- **високий** (злиття сутностей) — автоматично лише вище порогу з dev; сіра зона — LLM-суддя плюс перегляд людиною; будь-яке злиття можна скасувати (unmerge)."]
(LAB / "quality" / "conflicts.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("ok", len(L))
