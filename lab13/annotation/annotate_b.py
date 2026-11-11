"""ЛР13 · розмітник B — незалежна локальна модель gemma3:4b (Ollama) за тією самою інструкцією; не бачить міток розмітника A.
Вихід: results/kappa_B.jsonl; журнал: llm_log/annotator_B.jsonl. Запуск на ПК: run_lab13.bat"""
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src")); sys.path.insert(0, str(ROOT.parent / "common"))
from schema import RELATIONS  # noqa: E402
from hub_common import LLM  # noqa: E402

LABELS = list(RELATIONS) + ["NONE"]
SCHEMA = {"type": "object", "properties": {"label": {"enum": LABELS}}, "required": ["label"]}
DEFS = "\n".join(f"- {k}: {d} (голова {'|'.join(sorted(h))} → хвіст {'|'.join(sorted(t))})" for k, (h, t, d) in RELATIONS.items())
SYSTEM = ("Ти — розмітник бази знань фактчекінгу. Тобі дано абзац і дві сутності (ГОЛОВА, ХВІСТ). Визнач, яке відношення ГОЛОВА → ХВІСТ "
          "прямо стверджує абзац. Якщо жодне — NONE. Відношення:\n" + DEFS + "\n- NONE: абзац не стверджує жодного з відношень між цими сутностями.\n"
          "COOPERATES_WITH симетричне. Сутності подано в канонічній формі (у тексті можуть бути інші відмінки або синоніми). Поверни JSON {\"label\": ...}.")
llm = LLM("gemma3:4b", ROOT / "llm_log" / "annotator_B.jsonl", temperature=0.0, seed=7, num_ctx=4096, prompt_version="annot_B_v1")
(ROOT / "results").mkdir(exist_ok=True)
items = [json.loads(l) for l in open(ROOT / "data" / "kappa_items.jsonl", encoding="utf-8")]
with open(ROOT / "results" / "kappa_B.jsonl", "w", encoding="utf-8") as f:
    for it in items:
        msg = [{"role": "system", "content": SYSTEM},
               {"role": "user", "content": f"АБЗАЦ:\n{it['context']}\n\nГОЛОВА: {it['head']}\nХВІСТ: {it['tail']}"}]
        out = llm.chat(msg, task=f"annot_B {it['id']}", fmt=SCHEMA, max_tokens=40)
        try:
            lab = json.loads(out["text"])["label"]
        except Exception:  # noqa
            lab = "NONE"
        f.write(json.dumps(dict(id=it["id"], label_B=lab, raw=out["text"]), ensure_ascii=False) + "\n"); f.flush()
        print(it["id"], lab, flush=True)
print("annotator B done")
