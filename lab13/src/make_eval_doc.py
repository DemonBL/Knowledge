"""ЛР13 · docs/extraction_eval.md і results/eval_summary.json: метрики на test (загалом, за типами, за типом джерела),
частка без цитати й вигаданих (до/після валідації), вартість/документ, аналіз помилок, рекомендація."""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
import evaluate as EV  # noqa: E402
from extract_llm import validate  # noqa: E402
from schema import ENTITY_TYPES, RELATIONS  # noqa: E402

M = {"A (правила + spaCy)": "results/rules_test.jsonl", "Б (qwen2.5:7b + схема)": "results/llm_test.jsonl", "Гібрид (маршрутизація за dev)": "results/hybrid_test.jsonl"}
R = {k: EV.evaluate(ROOT / v, "test") for k, v in M.items()}


def by_source(path, pref):
    gold_keep = {d for d, g in EV.GOLD.items() if g["split"] == "test" and (d.startswith("INT-NAR") == (pref == "INT"))}
    tmp = ROOT / "results" / "_tmp.jsonl"
    with open(tmp, "w", encoding="utf-8") as f:
        for l in open(ROOT / path, encoding="utf-8"):
            if json.loads(l)["doc_id"] in gold_keep: f.write(l)
    saved = dict(EV.GOLD)
    for d in list(EV.GOLD):
        if d not in gold_keep: EV.GOLD.pop(d)
    r = EV.evaluate(tmp, "test"); EV.GOLD.clear(); EV.GOLD.update(saved); tmp.unlink()
    return r
SRC = {k: {"Вікіпедія + інші": by_source(v, "W"), "звіти INT-NAR": by_source(v, "INT")} for k, v in list(M.items())[:2]}
# сирі пропозиції LLM до валідації (усі спроби test)
corpus = EV.CORPUS
raw = dict(calls=0, json_invalid=0, proposed=0, valid=0, no_quote=0, signature=0, absent=0)
for l in open(ROOT / "llm_log" / "extract_llm_log.jsonl", encoding="utf-8"):
    g = json.loads(l); v, doc, tr = g["task"].split()
    if v != "llm_v1" or corpus[doc]["split"] != "test": continue
    raw["calls"] += 1
    try: obj = json.loads(g["raw_output"])
    except Exception: raw["json_invalid"] += 1; continue
    e, r, errs = validate(obj, corpus[doc]["text"])
    raw["proposed"] += len(obj.get("relations", [])); raw["valid"] += len(r)
    for x in errs:
        if "evidence" in x: raw["no_quote"] += 1
        elif "сигнатурі" in x: raw["signature"] += 1
        elif "відсутні" in x and "→" in x: raw["absent"] += 1
summary = {k: {kk: vv for kk, vv in v.items() if kk != "_errors"} for k, v in R.items()}
summary["by_source"] = {k: {s: {"ENT": v["ENT:ALL"], "REL": v["REL:ALL"]} for s, v in d.items()} for k, d in SRC.items()}
summary["llm_raw_before_validation"] = raw
summary["kappa"] = json.loads((ROOT / "results" / "kappa.json").read_text(encoding="utf-8"))
summary["dev"] = {"A": EV.evaluate(ROOT / "results/rules_dev.jsonl", "dev")["REL:ALL"], "B_v1": EV.evaluate(ROOT / "results/llm_v1_dev.jsonl", "dev")["REL:ALL"],
                  "B_v2": EV.evaluate(ROOT / "results/llm_v2_dev.jsonl", "dev")["REL:ALL"],
                  "selection": json.loads((ROOT / "results/llm_selection.json").read_text(encoding="utf-8"))}
summary["relaxed_B"] = EV.evaluate(ROOT / "results/llm_test_relaxed.jsonl", "test")["REL:ALL"]
(ROOT / "results" / "eval_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1, default=str), encoding="utf-8")

f = lambda x: f"{x:.3f}".replace(".", ",")
md = ["# ЛР13 · Оцінювання витягу та аналіз помилок", "", "Набір: test (15 документів, 102 відношення, 232 унікальні сутності). Порівняння на рівні документа за канонічними ключами (src/normalize.py); COOPERATES_WITH — без напрямку; дата у FOUNDED_ON — за роком.", "",
      "## 1. P / R / F1 загалом", "", "| Метод | Сутності P | R | F1 | Відношення P | R | F1 |", "|---|---|---|---|---|---|---|"]
for k, r in R.items():
    e, rr = r["ENT:ALL"], r["REL:ALL"]
    md.append(f"| {k} | {f(e['P'])} | {f(e['R'])} | {f(e['F1'])} | {f(rr['P'])} | {f(rr['R'])} | {f(rr['F1'])} |")
md += ["", "## 2. F1 за типами", "", "| Тип | A: P / R / F1 | Б: P / R / F1 | золото |", "|---|---|---|---|"]
ka, kb = list(R)[:2]
for kind, names in (("ENT", ENTITY_TYPES), ("REL", RELATIONS)):
    for t in names:
        a, b = R[ka].get(f"{kind}:{t}"), R[kb].get(f"{kind}:{t}")
        if not a and not b: continue
        g = (a or b)["gold"]
        md.append(f"| {kind}:{t} | " + " | ".join(f"{f(x['P'])} / {f(x['R'])} / {f(x['F1'])}" if x else "—" for x in (a, b)) + f" | {g} |")
md += ["", "## 3. За типом джерела (F1 відношень)", "", "| Метод | Вікіпедія + регламенти | Шаблонні звіти INT-NAR |", "|---|---|---|"]
for k, d in SRC.items():
    md.append(f"| {k} | {f(d['Вікіпедія + інші']['REL:ALL']['F1'])} ({d['Вікіпедія + інші']['REL:ALL']['gold']} відн.) | {f(d['звіти INT-NAR']['REL:ALL']['F1'])} ({d['звіти INT-NAR']['REL:ALL']['gold']} відн.) |")
q = R[kb]["_quality"]; ca, cb = R[ka]["_cost_per_doc"], R[kb]["_cost_per_doc"]
md += ["", "## 4. Цитати, вигадані твердження, вартість", "",
       f"- **Після валідації** обидва методи мають 0 % тверджень без підтвердженої цитати: метод А цитує речення-джерело, а метод Б зберігає лише ті пропозиції, де evidence — дослівний фрагмент тексту. Вигаданих (голова/хвіст відсутні в тексті): А — {R[ka]['_quality']['fabricated']} з {R[ka]['_quality']['relations_pred']}, Б — {q['fabricated']} з {q['relations_pred']}.",
       f"- **До валідації (сирий вихід LLM, усі спроби на test):** {raw['calls']} викликів, з них {raw['json_invalid']} з невалідним JSON (обрізаний або зациклений вихід); запропоновано {raw['proposed']} відношень, валідацію пройшли {raw['valid']} ({raw['valid'] / raw['proposed'] * 100:.0f} %). Відкинуто: без дослівної цитати — {raw['no_quote']} ({raw['no_quote'] / raw['proposed'] * 100:.1f} %), порушення сигнатури (типи не зі схеми, текст твердження замість сутності) — {raw['signature']} ({raw['signature'] / raw['proposed'] * 100:.0f} %).",
       f"- **Вартість на документ:** А — {ca['latency_s']} с CPU, 0 токенів; Б — {cb['latency_s']:.0f} с ({cb['latency_s'] / 60:.1f} хв) на CPU, {cb['prompt_tokens']:.0f} токенів підказки + {cb['completion_tokens']:.0f} токенів відповіді, {cb['calls']:.2f} виклику (повторів {cb['retries']:.2f}). Модель локальна, тож грошова вартість 0; за тарифами хмарних API рівня 7–8B це менше $0,01/документ, але час — у ~500 разів більший, ніж у правил.",
       f"- **Діагностика:** якщо відновити пропущені моделлю head_type/tail_type (results/llm_test_relaxed.jsonl), F1 відношень Б = {f(summary['relaxed_B']['F1'])}, тобто типи не головна причина низького recall.",
       f"- **Вибір підказки на dev:** на ПК обрано llm_v1 за спрощеним F1 ({summary['dev']['selection']['dev_quick_rel_f1']}); повна метрика на dev дає v1 = {f(summary['dev']['B_v1']['F1'])}, v2 = {f(summary['dev']['B_v2']['F1'])}. Різниця мала, на висновки не впливає; це обмеження спрощеного відбору.", "",
       "## 5. Аналіз помилок (≥ 10)", "", "| № | Метод | Документ | Тип | Клас помилки | Що | Причина |", "|---|---|---|---|---|---|---|"]
for e in json.loads((ROOT / "docs" / "error_analysis.json").read_text(encoding="utf-8")):
    md.append(f"| {e['n']} | {e['method']} | {e['doc']} | {e['kind']} | {e['cls']} | {e['what']} | {e['why']} |")
md += ["", "Підсумок класів: пропуски (FN) — головна проблема обох методів; для Б — масові, через неправильну структуру відповіді на шаблонних звітах і обрізаний вихід. "
       "Хибні відношення методу А — тригери без синтаксичного зв'язку (близькість ≠ зв'язок). Вигадані методом Б відношення (INT-RULES, INT-SAMPLE-INJ) відкинув валідатор: у граф не потрапило жодне. "
       "Помилки нормалізації («ВООЗ» у дужках) знижують метрику обох методів однаково.", "",
       "## 6. Рекомендація", "",
       f"**Основний метод — А (правила + spaCy)**: F1 відношень {f(R[ka]['REL:ALL']['F1'])} проти {f(R[kb]['REL:ALL']['F1'])} у Б, точність {f(R[ka]['REL:ALL']['P'])}, 0 % без цитати, ~1,5 с на документ. "
       "Маршрутизація за dev (results/hybrid_routing.json) не віддала Б жодного типу — гібрид на test збігається з А. "
       f"На енциклопедичному тексті перевага А менша (F1 {f(SRC[ka]['Вікіпедія + інші']['REL:ALL']['F1'])} проти {f(SRC[kb]['Вікіпедія + інші']['REL:ALL']['F1'])}), а для LEADS і SPREADS_VIA Б на test навіть кращий; тому рекомендовано "
       "**гібрид «А + Б як генератор кандидатів»**: відношення Б, що пройшли валідацію (цитата + сигнатура), додаються в граф зі статусом candidate і перевіряються людиною; "
       "у шаблонних звітах — лише правила. Для Б потрібні: менша порція тексту на виклик (абзац), обов'язкові head_type/tail_type у схемі, ліміт довжини evidence і модель більшого розміру або GPU."]
(ROOT / "docs" / "extraction_eval.md").write_text("\n".join(md) + "\n", encoding="utf-8")
print(json.dumps(summary["by_source"], ensure_ascii=False)[:600]); print(raw)
