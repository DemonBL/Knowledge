"""ЛР14 · Результат 5: quality/after_report.md і рисунки docs/img/*.png.

Вхід:
  - quality/metrics.json (baseline / after);
  - lab11/results/lab11_results.json (RAG «до»: opt_k3, k = 3);
  - results/rag_after.json (RAG «після», з ПК);
  - results/neo4j_invariants.json;
  - results/dedup_eval.json;
  - quality/reports/trend.csv.
"""
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

LAB = Path(__file__).resolve().parents[1]
HUB = LAB.parent
IMG = LAB / "docs" / "img"
IMG.mkdir(parents=True, exist_ok=True)
C_B, C_A = "#9aa0a6", "#2a78d6"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False})

M = json.loads((LAB / "quality" / "metrics.json").read_text(encoding="utf-8"))
B, A = M["baseline"]["metrics"], M["after"]["metrics"]
R11 = json.loads((HUB / "lab11" / "results" / "lab11_results.json").read_text(encoding="utf-8"))["eval"]["opt_k3"]
RA = json.loads((LAB / "results" / "rag_after.json").read_text(encoding="utf-8"))
NI = json.loads((LAB / "results" / "neo4j_invariants.json").read_text(encoding="utf-8")) if (LAB / "results" / "neo4j_invariants.json").exists() else None
DE = json.loads((LAB / "results" / "dedup_eval.json").read_text(encoding="utf-8"))
before, after = R11["agg"], RA["agg"]
rb = {r["id"]: r for r in R11["rows"]}
ra = {r["id"]: r for r in RA["rows"]}

# ---------------- рисунок 1: профіль якості до/після (частка пройдених порогів за вимірами)
dims = list(dict.fromkeys(r["dimension"] for r in B))
pb = [sum(r["passed"] for r in B if r["dimension"] == d) / sum(1 for r in B if r["dimension"] == d) for d in dims]
pa = [sum(r["passed"] for r in A if r["dimension"] == d) / sum(1 for r in A if r["dimension"] == d) for d in dims]
fig, ax = plt.subplots(figsize=(7.2, 3.2), dpi=200)
x = range(len(dims))
nb = [sum(r["passed"] for r in B if r["dimension"] == d) for d in dims]
na = [sum(r["passed"] for r in A if r["dimension"] == d) for d in dims]
nt = [sum(1 for r in B if r["dimension"] == d) for d in dims]
ax.bar([i - 0.19 for i in x], pb, 0.36, color=C_B, label="baseline (v0)")
ax.bar([i + 0.19 for i in x], pa, 0.36, color=C_A, label="після (v1)")
for i in x:
    ax.text(i - 0.19, pb[i] + 0.02, f"{nb[i]}/{nt[i]}", ha="center", fontsize=7, color="#555")
    ax.text(i + 0.19, pa[i] + 0.02, f"{na[i]}/{nt[i]}", ha="center", fontsize=7, color="#555")
ax.set_xticks(list(x), dims, rotation=20, ha="right")
ax.set_ylabel("частка метрик у межах порогу")
ax.set_ylim(0, 1.15)
ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncols=2)
ax.grid(axis="y", color="#e5e5e5", linewidth=0.6)
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(IMG / "profile_before_after.png")
plt.close(fig)

# ---------------- рисунок 2: метрики RAG до/після
keys = [("faithfulness", "faithfulness"), ("context_recall", "context recall"), ("citation_accuracy", "citation accuracy"),
        ("answer_correct", "правильність"), ("abstention_noanswer", "abstention (без відповіді)"), ("pass_rate", "pass rate")]
fig, ax = plt.subplots(figsize=(7.2, 3.0), dpi=200)
x = range(len(keys))
vb = [before[k] or 0 for k, _ in keys]
va = [after[k] or 0 for k, _ in keys]
ax.bar([i - 0.19 for i in x], vb, 0.36, color=C_B, label="до (ЛР11, k = 3)")
ax.bar([i + 0.19 for i in x], va, 0.36, color=C_A, label="після очищення (k = 3)")
for i, (b, a) in enumerate(zip(vb, va)):
    ax.text(i - 0.19, b + 0.01, f"{b:.2f}", ha="center", fontsize=7, color="#444")
    ax.text(i + 0.19, a + 0.01, f"{a:.2f}", ha="center", fontsize=7, color="#444")
ax.set_xticks(list(x), [l for _, l in keys], fontsize=8)
ax.set_ylim(0, 1.12)
ax.legend(frameon=False, loc="lower center", bbox_to_anchor=(0.5, 1.0), ncols=2)
ax.grid(axis="y", color="#e5e5e5", linewidth=0.6)
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(IMG / "rag_before_after.png")
plt.close(fig)

# ---------------- рисунок 3: тренд gate
T = list(csv.DictReader(open(LAB / "quality" / "reports" / "trend.csv", encoding="utf-8")))
fig, ax = plt.subplots(figsize=(7.2, 2.6), dpi=200)
xs = [int(t["run"]) for t in T]
ax.plot(xs, [int(t["failed_critical"]) for t in T], marker="o", color="#d03b3b", linewidth=2, label="critical-порушення")
ax.plot(xs, [int(t["failed_warning"]) for t in T], marker="s", color="#e3a008", linewidth=2, label="попередження")
for t in T:
    ax.annotate(t["version"].replace("data/", ""), (int(t["run"]), int(t["failed_critical"])), textcoords="offset points",
                xytext=(0, 8), ha="center", fontsize=7)
ax.set_xticks(xs, [f"запуск {x}" for x in xs])
ax.set_ylabel("кількість перевірок, що впали")
ax.set_ylim(0, max(int(t["failed_critical"]) for t in T) + 2)
ax.legend(frameon=False)
ax.grid(axis="y", color="#e5e5e5", linewidth=0.6)
fig.tight_layout()
fig.savefig(IMG / "gate_trend.png")
plt.close(fig)

# ---------------- after_report.md
f3 = lambda v: "—" if v is None else (f"{v:.3f}" if isinstance(v, float) else str(v))
L = ["# Після покращення та вплив на RAG (ЛР14, Результат 5)", "",
     f"Версії: baseline — {M['baseline']['tag']}; після — {M['after']['tag']}. Дата виміру: {M['after']['measured_at']}.", "",
     "## 1. Метрики якості «до/після»", "",
     "| ID | Вимір | Метрика | Поріг | До | Після | Статус |", "|---|---|---|---|---|---|---|"]
for b, a in zip(B, A):
    st = ("✅" if a["passed"] else "❌") + (" ↑" if a["passed"] and not b["passed"] else "")
    L.append(f"| {b['id']} | {b['dimension']} | {b['name']} | {b['op']} {b['threshold']} | {f3(b['value'])} | {f3(a['value'])} | {st} |")
L += ["", f"Пройдено порогів: до — {sum(r['passed'] for r in B)}/15, після — {sum(r['passed'] for r in A)}/15. "
      "Не досягнуто: M06 (точність типів сутностей ЛР13), M08 і M14 (застарілі та недоступні джерела — потрібна мережа й рішення власника), "
      "M10 (рештки дублікатів сутностей; recall ER на test < 1).", ""]
if NI:
    L += ["Cypher-інваріанти в Neo4j (ПК, `results/neo4j_invariants.json`):", "",
          "| Інваріант | До міграції | Після |", "|---|---|---|"]
    for k in NI["before"]:
        L.append(f"| {k} | {NI['before'][k]} | {NI['after'][k]} |")
    L.append("")
L += ["## 2. Метрики RAG «до/після» (тестовий набір ЛР11, 31 тест, k = 3, текст + граф)", "",
      "«До» — прогін ЛР11 `opt_k3`: той самий код, генератор qwen2.5:7b (seed 42), суддя gemma3:4b (seed 7), той самий граф ЛР9. "
      "«Після» — очищене сховище: корпус v1 і граф після міграції; шаблони підграфа показують нові поля.", "",
      "| Метрика | До | Після | Δ |", "|---|---|---|---|"]
for k, lab in [("faithfulness", "faithfulness"), ("faithful_share", "частка повністю faithful відповідей"), ("context_recall", "context recall"),
               ("citation_accuracy", "citation accuracy"), ("citation_validity", "citation validity"), ("answer_correct", "правильність (answerable)"),
               ("abstention_noanswer", "abstention на питаннях без відповіді"), ("false_abstention", "хибні відмови"), ("pass_rate", "pass rate"),
               ("latency_p50_s", "латентність p50, с"), ("prompt_tokens_mean", "токенів підказки, сер.")]:
    b, a = before.get(k), after.get(k)
    d = (a - b) if isinstance(a, (int, float)) and isinstance(b, (int, float)) else None
    L.append(f"| {lab} | {f3(b)} | {f3(a)} | {'' if d is None else f'{d:+.3f}'} |")
L += ["", "Зміни за тестами (pass / правильність):", "", "| Тест | Категорія | До | Після | Відповідь після (початок) |", "|---|---|---|---|---|"]
for tid in rb:
    b, a = rb[tid], ra.get(tid, {})
    if bool(b.get("pass")) != bool(a.get("pass")) or tid in ("T12", "T13", "T14", "T15", "T24", "T25", "T26", "T27"):
        L.append(f"| {tid} | {b['category']} | {'pass' if b.get('pass') else 'FAIL'} | {'pass' if a.get('pass') else 'FAIL'} | "
                 f"{(a.get('answer') or '')[:110].replace('|', '/').replace(chr(10), ' ')} |")
L += ["", "## 3. Дедуплікація (Р2), коротко", "",
      f"Поріг з dev — {DE['threshold']}: dev P = {DE['dev']['P']}, R = {DE['dev']['R']}; test P = {DE['test']['P']}, R = {DE['test']['R']}, F1 = {DE['test']['F1']}."
      + (f" З LLM-суддею в сірій зоні ({DE.get('llm_judged_pairs', 0)} пар): test P = {DE['test_with_llm_judge']['P']}, "
         f"R = {DE['test_with_llm_judge']['R']}, F1 = {DE['test_with_llm_judge']['F1']}." if "test_with_llm_judge" in DE else ""), ""]
(LAB / "quality" / "after_report.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("after_report.md OK")
