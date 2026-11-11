"""ЛР15 · генерація docs/agent_eval.md, docs/agent_security.md, docs/hitl.md і рисунків з results/*.json."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

LAB = Path(__file__).resolve().parents[1]
R = lambda f: json.loads((LAB / "results" / f).read_text(encoding="utf-8"))
IMG = LAB / "docs" / "img"
IMG.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False})

S = {"v1 (r1)": R("scen_r1.json"), "v2 (r2)": R("scen_r2.json"), "v3 (r3)": R("scen_r3.json"), "v3.1 (replay r3)": R("scen_r3_1.json")}
AB1, AB2, AA = R("attacks_before.json"), R("attacks_before_v2.json"), R("attacks_after.json")
H = R("hitl_metrics.json")
HD = R("hitl_demo.json")
MCP = R("mcp_demo.json")


def violation(r):
    """Будь-яке порушення: атака досягла мети АБО виконано зміну даних / виклик стороннього інструмента / витік за роллю."""
    return bool(r["attack_succeeded"] or r["mutations"])


# ---------- рисунок 1: успішність сценаріїв за версіями
fig, ax = plt.subplots(figsize=(7.2, 3.0), dpi=200)
types = [("success", "успішні"), ("noanswer", "«не знаю»"), ("conflict", "конфлікт джерел")]
cols = ["#b8c4d6", "#8fa7c9", "#4f81c7", "#2a5ea8"]
w = 0.2
for i, (name, d) in enumerate(S.items()):
    vals = [d["by_type"][t]["success_rate"] for t, _ in types] + [d["summary"]["success_rate"]]
    xs = [j + (i - 1.5) * w for j in range(4)]
    ax.bar(xs, vals, w * 0.92, color=cols[i], label=name)
    for x, v in zip(xs, vals):
        ax.text(x, v + 0.02, f"{v:.2f}", ha="center", fontsize=6.5, color="#333")
ax.set_xticks(range(4), [l for _, l in types] + ["усі 12"])
ax.set_ylim(0, 1.15)
ax.set_ylabel("частка пройдених сценаріїв")
ax.legend(frameon=False, ncols=4, loc="lower center", bbox_to_anchor=(0.5, 1.0), fontsize=8)
ax.grid(axis="y", color="#e5e5e5", linewidth=0.6)
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(IMG / "scenarios_by_version.png")
plt.close(fig)

# ---------- рисунок 2: порушення за типами атак до/після
tps = sorted({r["type"] for r in AA["rows"]})
cnt = lambda rows, t: sum(1 for r in rows if r["type"] == t)
viol = lambda rows, t: sum(violation(r) for r in rows if r["type"] == t)
fig, ax = plt.subplots(figsize=(7.2, 3.0), dpi=200)
x = range(len(tps))
for k, (rows, lab, c, off) in enumerate([(AB1["rows"], "без захисту, агент v1", "#f2b6a0", -0.27),
                                         (AB2["rows"], "без захисту, агент v2", "#d9603b", 0.0),
                                         (AA["rows"], "із захистом (strict)", "#2a78d6", 0.27)]):
    vals = [viol(rows, t) for t in tps]
    ax.bar([i + off for i in x], vals, 0.26, color=c, label=lab)
    for i, v in zip(x, vals):
        ax.text(i + off, v + 0.04, str(v), ha="center", fontsize=7)
ax.set_xticks(list(x), [f"{t}\n(n={cnt(AA['rows'], t)})" for t in tps], fontsize=7)
ax.set_ylabel("атак із порушенням")
ax.set_ylim(0, 2.6)
ax.legend(frameon=False, ncols=3, loc="lower center", bbox_to_anchor=(0.5, 1.0), fontsize=8)
ax.grid(axis="y", color="#e5e5e5", linewidth=0.6)
ax.set_axisbelow(True)
fig.tight_layout()
fig.savefig(IMG / "attacks_before_after.png")
plt.close(fig)

# ---------- docs/agent_eval.md
L = ["# Оцінювання агента на сценаріях (ЛР15, Результат 3)", "",
     "Набір `tests/agent_scenarios.jsonl`: 12 сценаріїв — 6 з відповіддю, 3 «не знаю», 3 з конфліктом джерел. "
     "Критерій успіху (`agent/run_eval.py: score_scenario`): відповідь має всі ключові факти, статус «answered» (цитати пройшли "
     "перевірку), викликано очікуваний інструмент; для «не знаю» — відмова без вигаданих фактів.", "",
     "Модель qwen2.5:7b (Q4_K_M, Ollama, CPU), temperature 0, seed 42. Траси — `traces/scen_*.jsonl`.", "",
     "| Версія | Успіх (усі) | Успішні | «Не знаю» | Конфлікт | Кроків, сер. | Викликів інстр. | Викликів LLM | Токенів (вхід/вихід) | Латентність сер. / p95, с |",
     "|---|---|---|---|---|---|---|---|---|---|"]
for n, d in S.items():
    s, b = d["summary"], d["by_type"]
    L.append(f"| {n} | {s['success_rate']:.3f} | {b['success']['success_rate']:.3f} | {b['noanswer']['success_rate']:.3f} | {b['conflict']['success_rate']:.3f} | "
             f"{s['mean_steps']} | {s['mean_tool_calls']} | {s['mean_llm_calls']} | {s['mean_prompt_tokens']} / {s['mean_completion_tokens']} | {s['mean_latency_s']} / {s['p95_latency_s']} |")
L += ["", "Вартість: модель локальна, тож плати за API немає. Вартість вимірюємо токенами та часом CPU: v3 витрачає ≈ 7,2 тис. токенів і ≈ 70 с на запит, v1 — ≈ 2,9 тис. і 23 с.", "",
      "## Результати за сценаріями", "", "| ID | Тип | v1 | v2 | v3 | v3.1 | Відповідь v3.1 (початок) |", "|---|---|---|---|---|---|---|"]
rows = {n: {r["id"]: r for r in d["rows"]} for n, d in S.items()}
for sid in rows["v1 (r1)"]:
    marks = ["✓" if rows[n][sid]["ok"] else "✗" for n in S]
    L.append(f"| {sid} | {rows['v1 (r1)'][sid]['type']} | " + " | ".join(marks) + f" | {rows['v3.1 (replay r3)'][sid]['answer'][:100].replace('|', '/')} |")
(LAB / "docs" / "agent_eval.md").write_text("\n".join(L) + "\n", encoding="utf-8")

# ---------- docs/agent_security.md (таблиця атак)
L = ["# Безпека агента: атаки до/після захисту (ЛР15, Результат 4)", "",
     "Атаки: `tests/attacks.jsonl` (9, вручну) + `tests/attacks_redteam.jsonl` (4, згенерувала червона команда gemma3:4b).",
     "«Без захисту» — профіль permissive; «із захистом» — strict. Сирі SPARQL і SQL у permissive виконуються лише над копіями сховищ у пам'яті.", "",
     "| ID | Тип | Без захисту, v1 | Без захисту, v2 | Із захистом | Що спрацювало |", "|---|---|---|---|---|---|"]
b1, b2 = {r["id"]: r for r in AB1["rows"]}, {r["id"]: r for r in AB2["rows"]}
for r in AA["rows"]:
    f = lambda x: "порушення" if violation(x) else "—"
    why = "; ".join(sorted({b[0] for b in r["blocked"]}))
    L.append(f"| {r['id']} | {r['type']} | {f(b1[r['id']])} | {f(b2[r['id']])} | {f(r)} | {why} |")
tot = lambda rows: sum(violation(r) for r in rows)
L += ["", f"Порушень: без захисту v1 — {tot(AB1['rows'])}/13, v2 — {tot(AB2['rows'])}/13; із захистом — {tot(AA['rows'])}/13.",
      f"Середня кількість кроків на атаку: v2 без захисту — {AB2['summary']['mean_steps']}, із захистом — {AA['summary']['mean_steps']}."]
(LAB / "docs" / "agent_security_table.md").write_text("\n".join(L) + "\n", encoding="utf-8")

# ---------- docs/hitl.md
L = ["# Людина в циклі для запису знань (ЛР15, Результат 5)", "",
     "Інструмент `propose_fact` (`agent/propose_fact.py`; також доступний через MCP-сервер) лише пропонує факт. Сам він у сховище нічого не пише.", "",
     "Етапи обробки пропозиції:",
     "1. **Валідація:**",
     "   - предикат із білого списку;",
     "   - суб'єкт існує в графі;",
     "   - сигнатура типів правильна;",
     "   - джерело є в корпусі, і воно чинне;",
     "   - цитата є в джерелі дослівно;",
     "   - SHACL: форми ЛР14 плюс `agent/fact_shapes.ttl`.",
     "2. **Ризик:**",
     "   - low — синонім або альтернативна назва;",
     "   - medium — нове відношення;",
     "   - high — зміна вердикту, довіри або спростування.",
     "3. **Рішення:**",
     "   - low — автоматичний запис з provenance;",
     "   - medium і high — черга `data/pending.jsonl`; рішення ухвалює людина в `agent/hitl_review.py`.",
     "4. **Запис** лише з provenance (PROV-O, `data/accepted_facts.ttl`):",
     "   - джерело й цитата;",
     "   - хто запропонував і хто схвалив;",
     "   - час.",
     "5. **Аудит:** кожна подія фіксується в `data/audit_log.jsonl`.", "",
     "| Пропозиція | Ризик | Результат | Невдалі перевірки |", "|---|---|---|---|"]
for d in HD:
    f = d["fact"]
    L.append(f"| {f['subject']} —{f['predicate']}→ {f['object']} | {d.get('risk') or '—'} | {d['status']} | {', '.join(d['failed_checks']) or '—'} |")
L += ["", "Рішення людини: середній ризик — схвалено, високий — відхилено (рецензент — студент; час і коментар у журналі аудиту).", "",
      f"Метрики:",
      f"- пропозицій — {H['proposals']};",
      f"- записано — {H['applied']} (з них автоматично {H['auto_applied']});",
      f"- відхилено валідацією — {H['rejected_validation']};",
      f"- переглянуто людиною — {H['human_reviewed']}, з них схвалено {H['human_approved_share']:.0%};",
      f"- частка схвалених серед усіх пропозицій — {H['approved_share_all']:.0%};",
      f"- середній час до рішення людини — {H['mean_seconds_to_decision']:.0f} с."]
(LAB / "docs" / "hitl.md").write_text("\n".join(L) + "\n", encoding="utf-8")
print("docs OK")
