"""ЛР14 · експертна вибірка для виміру точності (36 записів, seed 14) → quality/accuracy_sample.csv.

Три частини сховища по 12 записів:
  A. факти графа ЛР9 (наратив, вердикт, першоджерело твердження) — звірка з текстом аналітичних звітів INT-NAR;
  B. відношення, витягнуті в ЛР13 (метод А, прийняті в граф) — звірка з цитатою-доказом (експерт);
  C. типи сутностей реєстру з ЛР13 — перевірка за схемою ЛР13 (експерт); після очищення беремо канонічний тип кластера.
Експертні оцінки B і C — LLM-експерт (Claude, рівень V3); студент переглядає й може змінити колонку verdict."""
import json
import random
import re
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kb  # noqa: E402
import dedup  # noqa: E402

LAB = kb.LAB
rows = []
# A. граф ↔ звіти
nodes, rels = kb.graph("baseline")
ch, _ = kb.corpus("baseline")
rep = {}
for c in ch:
    if c["doc_id"].startswith("INT-NAR"):
        rep[c["doc_id"]] = rep.get(c["doc_id"], "") + c["text"] + "\n"
part = rels["PART_OF"].set_index("start").end
ab = rels["ABOUT"].set_index("end").start
cat = nodes["Verdict"].set_index("id").category
der = set(rels["DERIVED_FROM"].start)
mk, pb = rels["MAKES_CLAIM"], rels["PUBLISHED"].set_index("end").start
random.seed(14)
for c in random.sample([f"CLM-{i:02d}" for i in range(1, 33)], 12):
    nar = part[c]
    t = rep[f"INT-NAR-{nar[-2:]}"]
    root = [p for p in mk[mk.end == c].start if p not in der][0]
    v = cat.get(ab.get(c, ""), "немає")
    fact = f"{c} ∈ {nar}; вердикт: {v}; першоджерело {root} від {pb[root]}"
    m = re.search(re.escape(c) + r":.*?(?=CLM-\d\d:|$)", t, re.S)
    seg = m.group(0) if m else ""
    ok = (f"{root} від {pb[root]}" in seg) and ((v == "немає" and "не завершено" in seg) or f"«{v}»" in seg)
    rows.append(dict(record_id=c, part="A граф ЛР9", record=fact, reference=f"INT-NAR-{nar[-2:]} (звіт групи моніторингу)",
                     verdict_baseline=int(ok), verdict_after=int(ok), checker="автоматична звірка з текстом звіту",
                     reason="збігається" if ok else "розбіжність"))
# B. відношення ЛР13 (оцінки експерта)
B = {0: (1, "«співпрацювати з Facebook (разом з VoxCheck)»"), 1: (1, "збігається з графом ЛР9"), 2: (1, "збігається з графом ЛР9"),
     3: (0, "1967 — рік матеріалу Ф. Мейера, а не заснування газети"), 4: (1, "команда Януковича поширювала дезінформацію"),
     5: (1, "окупаційна влада (ДНР) поширювала дезінформацію"), 6: (1, "співпраця з ВООЗ у боротьбі з дезінформацією"),
     7: (1, "факт правильний (фінансування); мітка голови «# StopFake ##» — дефект форми"), 8: (1, "збігається з графом ЛР9"),
     9: (1, "співпраця з ВООЗ"), 10: (1, "першоджерело PUB-071 від ACC-002"), 11: (1, "збігається з графом ЛР9")}
R13 = [json.loads(l) for l in open(kb.HUB / "lab13" / "results" / "rules_all.jsonl", encoding="utf-8")]
rel = [(r["doc_id"], x) for r in R13 for x in r["relations"]]
random.seed(14)
for i, (d, x) in enumerate(random.sample(rel, 12)):
    head = " ".join(x["head"].split())
    rows.append(dict(record_id=f"{d}#{i}", part="B відношення ЛР13", record=f"{head} —{x['relation']}→ {x['tail']}",
                     reference=f"{d}: «{x['evidence'][:140]}»", verdict_baseline=B[i][0], verdict_after=B[i][0],
                     checker="LLM-експерт (Claude), V3", reason=B[i][1]))
# C. типи сутностей ЛР13
C = {"Twitter": (1, ""), "Офісу генерального прокурора України": (1, "тип вірний; назва у непрямому відмінку"),
     "Флоренс Найтінгейл": (1, ""), "посольство Великої Британії в Україні": (1, ""),
     "Упереджене викладення фактів": (1, "прийом дезінформації"), "Гіперболізовані боти": (1, "вид ботів (W22)"),
     "Google": (0, "компанія з платформою → PLATFORM (правило схеми ЛР13)"), "LinkedIn": (1, ""),
     "кіберзлочинці": (0, "загальна група, не організація — не сутність"), "Google Usenet": (0, "сервіс/платформа, не ORG"),
     "NAR-02": (1, ""), "зневажливий термін": (0, "не сутність (фрагмент визначення)")}
RIGHT = {"Google": "PLATFORM", "Google Usenet": "PLATFORM"}
reg = json.loads((kb.CLEAN / "entity_registry.json").read_text(encoding="utf-8"))
canon = {m["rid"]: e["type"] for e in reg["entities"] for m in e["members"]}
recs = [r for r in dedup.load_registry() if r["source"] == "ЛР13 витяг"]
random.seed(14)
for r in random.sample(recs, 12):
    vb, why = C[r["name"]]
    ct = canon.get(r["rid"], r["type"])
    va = int(vb == 1 or RIGHT.get(r["name"]) == ct)
    rows.append(dict(record_id=r["rid"], part="C тип сутності ЛР13", record=f"{r['name']} : {r['type']}" + (f" → {ct}" if ct != r["type"] else ""),
                     reference="схема ЛР13 (docs/extraction_schema.md) + документ " + ",".join(r["attrs"]["docs"]),
                     verdict_baseline=vb, verdict_after=va, checker="LLM-експерт (Claude), V3", reason=why))
df = pd.DataFrame(rows)
df.to_csv(LAB / "quality" / "accuracy_sample.csv", index=False)
print(len(df), df.verdict_baseline.mean().round(3), df.verdict_after.mean().round(3))
print(df.groupby("part")[["verdict_baseline", "verdict_after"]].mean())
