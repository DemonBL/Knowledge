"""ЛР14 · навмисні дефекти для демонстрації CI: копія версії clean → data/defects з трьома дефектами.

  D-1: публікація PUB-010 отримує другого автора (рядок у rels_PUBLISHED)       → SHACL S2 (T01)
  D-2: ребро MAKES_CLAIM з confidence 1.7 і посиланням на неіснуючий CLM-99    → T13 цілісність, T14 діапазон, T01
  D-3: у корпус повторно вставлено фрагмент W14:s001 під новим id і без ліцензії → T09 дублікат, T10 походження, T17 схема
  python quality/defects.py && python quality/gate.py --kb-dir data/defects --label "3 навмисні дефекти"
"""
import json
import shutil
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kb  # noqa: E402

D = kb.LAB / "data" / "defects"
if D.exists():
    shutil.rmtree(D)
shutil.copytree(kb.CLEAN / "graph", D / "graph")
shutil.copy(kb.CLEAN / "docs.jsonl", D / "docs.jsonl")
p = D / "graph" / "rels_PUBLISHED.csv"
df = pd.read_csv(p, dtype=str)
df = pd.concat([df, pd.DataFrame([dict(start="ACC-027", end="PUB-010", source="manual_edit", confidence="1.0", validFrom="2026-11-06")])])
df.to_csv(p, index=False)
p = D / "graph" / "rels_MAKES_CLAIM.csv"
df = pd.read_csv(p, dtype=str)
df = pd.concat([df, pd.DataFrame([dict(start="PUB-012", end="CLM-99", source="nlp_claim_extraction", confidence="1.7", validFrom="2026-11-06")])])
df.to_csv(p, index=False)
ch = kb.load_jsonl(kb.CLEAN / "corpus.jsonl")
dup = dict(next(c for c in ch if c["chunk_id"] == "W14:s001"))
dup.update(chunk_id="W14:s099", license=None)
ch.append(dup)
with open(D / "corpus.jsonl", "w", encoding="utf-8") as f:
    for c in ch:
        f.write(json.dumps(c, ensure_ascii=False) + "\n")
print("дефекти внесено в", D)
