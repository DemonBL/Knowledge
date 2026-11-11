"""ЛР14 · Результат 1/5: профіль якості сховища (15 метрик, 8 вимірів) для версії baseline або clean.

  python quality/profile.py baseline   → results/metrics_baseline.json
  python quality/profile.py clean      → results/metrics_clean.json
  python quality/profile.py report     → quality/metrics.json (обидві версії) + quality/profile_baseline.md + docs/img/profile.png
"""
from __future__ import annotations

import collections
import json
import re
import sys
from datetime import date
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kb  # noqa: E402
import conflicts  # noqa: E402

LAB = kb.LAB
RES = LAB / "results"
VERSION_TAG = {"baseline": "kb-2026.11-v0 (ЛР9 CSV + корпус ЛР10, стан на 2026-10-28)", "clean": "kb-2026.11-v1 (після ЛР14)"}

# id, вимір, назва, напрям (≥ або ≤), поріг, критичність (блокує CI?)
METRICS = [
    ("M01", "повнота", "Частка тверджень зі статусом перевірки (вердикт або явне «не перевірено»)", ">=", 1.0, "critical"),
    ("M02", "повнота", "Частка наративів з агрегатами (кількість тверджень і публікацій)", ">=", 1.0, "major"),
    ("M03", "узгодженість", "Порушення логічних правил регламенту (reasoner, SPARQL)", "<=", 0, "critical"),
    ("M04", "узгодженість", "Непозначені часові суперечності (вердикт раніше за публікацію)", "<=", 0, "major"),
    ("M05", "узгодженість", "Термінологічні розбіжності (варіанти назв без канонічного id)", "<=", 0, "minor"),
    ("M06", "точність", "Точність на експертній вибірці (36 записів)", ">=", 0.9, "major"),
    ("M07", "актуальність", "Нечинні документи без позначки чинності", "<=", 0, "critical"),
    ("M08", "актуальність", "Частка документів, оновлених за останні 24 міс.", ">=", 0.9, "minor"),
    ("M09", "унікальність", "Частка дублікатів фрагментів корпусу", "<=", 0.01, "major"),
    ("M10", "унікальність", "Частка нерозв'язаних дублікатів сутностей (на розмічених парах)", "<=", 0.1, "major"),
    ("M11", "походження", "Частка ребер графа з source + confidence + validFrom", ">=", 1.0, "critical"),
    ("M12", "походження", "Частка фрагментів з джерелом (URL) і ліцензією", ">=", 1.0, "major"),
    ("M13", "валідність", "Порушення SHACL рівня Violation", "<=", 0, "critical"),
    ("M14", "доступність", "Частка запланованих джерел, які вдалося отримати", ">=", 0.95, "minor"),
    ("M15", "доступність", "Частка фрагментів з коректною міткою доступу (RBAC)", ">=", 1.0, "critical"),
]


def shacl_counts(version):
    import pyshacl
    from rdflib import Graph, Namespace
    SH = Namespace("http://www.w3.org/ns/shacl#")
    g = kb.to_rdf(version)
    conf, rg, _ = pyshacl.validate(g, shacl_graph=Graph().parse(LAB / "quality" / "shapes.ttl"), inference="none")
    c = collections.Counter(str(rg.value(r, SH.resultSeverity)).split("#")[1] for r in rg.subjects(SH.resultSeverity, None))
    by = collections.Counter(str(rg.value(r, SH.resultMessage)) for r in rg.subjects(SH.resultSeverity, None))
    return c.get("Violation", 0), c.get("Warning", 0), dict(by)


def chunk_dups(ch):
    from sklearn.feature_extraction.text import TfidfVectorizer
    X = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5)).fit_transform([c["text"] for c in ch])
    S = (X @ X.T).toarray()
    num = [tuple(re.findall(r"\d+", c["text"])) for c in ch]
    dup = set()
    for i in range(len(ch)):
        for j in range(i + 1, len(ch)):
            if S[i, j] >= 0.95 and num[i] == num[j]:
                dup.add(j)
    return len(dup)


def measure(version):
    nodes, rels = kb.graph(version)
    ch, docs = kb.corpus(version)
    m, ev = {}, {}
    claim = nodes["Claim"]
    has_v = set(rels["ABOUT"].end)
    st = claim.get("status", pd.Series([""] * len(claim)))
    m["M01"] = round(sum((c in has_v) or bool(s) for c, s in zip(claim.id, st)) / len(claim), 3)
    nar = nodes["Narrative"]
    m["M02"] = round(sum(bool(x) for x in nar.get("publicationCount", pd.Series([""] * len(nar)))) / len(nar), 3)
    K = {c["id"]: c for c in conflicts.detect(version)}
    m["M03"] = len(K.get("K1", {}).get("items", [])) + len(K.get("K0", {}).get("items", []))
    m["M04"] = len(K.get("K2", {}).get("items", []))
    m["M05"] = len(K.get("K5", {}).get("items", [])) + len(K.get("K6", {}).get("items", []))
    acc = pd.read_csv(LAB / "quality" / "accuracy_sample.csv")
    col = "verdict_baseline" if version == "baseline" else "verdict_after"
    m["M06"] = round(float(acc[col].mean()), 3)
    ev["M06"] = {"n": len(acc), "correct": int(acc[col].sum())}
    m["M07"] = len(K.get("K3", {}).get("items", [])) // 2 if "K3" in K else 0
    ref = date.fromisoformat(kb.REF_DATE)
    fresh = [d for d in docs if (ref - date.fromisoformat(d["date"])).days <= 730]
    m["M08"] = round(len(fresh) / len(docs), 3)
    ev["M08"] = {"stale": [d["doc_id"] for d in docs if d not in fresh]}
    nd = chunk_dups(ch)
    m["M09"] = round(nd / len(ch), 4)
    ev["M09"] = {"duplicates": nd, "chunks": len(ch)}
    G = pd.read_csv(LAB / "quality" / "pairs_gold.csv")
    pos = G[G.label == 1]
    if version == "baseline":
        m["M10"] = 1.0
    else:
        reg = json.loads((kb.CLEAN / "entity_registry.json").read_text(encoding="utf-8"))
        cl = {mm["rid"]: e["id"] for e in reg["entities"] for mm in e["members"]}
        m["M10"] = round(float(sum(cl[a] != cl[b] for a, b in zip(pos.a, pos.b)) / len(pos)), 3)
        ev["M10"] = {"entities_before": reg["records"], "entities_after": reg["clusters"]}
    tot = sum(len(df) for df in rels.values())
    okp = sum(((df.source != "") & (df.confidence != "") & (df.validFrom != "")).sum() for df in rels.values())
    m["M11"] = round(okp / tot, 3)
    m["M12"] = round(sum(bool(c.get("source_url")) and bool(c.get("license")) for c in ch) / len(ch), 3)
    v, w, by = shacl_counts(version)
    m["M13"] = v
    ev["M13"] = {"violations": v, "warnings": w, "by_message": by}
    inv = json.loads((LAB / "data" / "source_inventory.json").read_text(encoding="utf-8"))
    m["M14"] = round(sum(s["retrieved"] for s in inv) / len(inv), 3)
    ev["M14"] = {"planned": len(inv), "missing": [s["name"] for s in inv if not s["retrieved"]]}
    m["M15"] = round(sum(c.get("sensitivity") in ("public", "internal", "restricted") for c in ch) / len(ch), 3)
    rows = []
    for mid, dim, name, op, thr, sev in METRICS:
        val = m[mid]
        ok = val >= thr if op == ">=" else val <= thr
        rows.append(dict(id=mid, dimension=dim, name=name, value=val, op=op, threshold=thr, severity=sev, passed=bool(ok)))
    out = {"version": version, "tag": VERSION_TAG[version], "measured_at": kb.REF_DATE, "metrics": rows, "evidence": ev,
           "conflicts": {k: len(c["items"]) for k, c in K.items()}}
    (RES / f"metrics_{version}.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(version, sum(r["passed"] for r in rows), "/", len(rows), "пройдено")
    return out


def report():
    B = json.loads((RES / "metrics_baseline.json").read_text(encoding="utf-8"))
    C = json.loads((RES / "metrics_clean.json").read_text(encoding="utf-8")) if (RES / "metrics_clean.json").exists() else None
    (LAB / "quality" / "metrics.json").write_text(json.dumps({"baseline": B, "after": C}, ensure_ascii=False, indent=1), encoding="utf-8")
    L = [f"# Профіль якості сховища — baseline\n",
         f"**Версія:** {B['tag']}. **Дата виміру:** {B['measured_at']}. Скрипт: `python quality/profile.py baseline`.\n",
         "Сховище: граф розслідувань ЛР9 (297 вузлів, 808 ребер), корпус ЛР10 (36 документів, 540 фрагментів), "
         "реєстр сутностей Hub (ЛР8 RDF + ЛР9 + ЛР13, 295 записів).\n",
         "| ID | Вимір | Метрика | Значення | Поріг | Критичність | Статус |", "|---|---|---|---|---|---|---|"]
    for r in B["metrics"]:
        L.append(f"| {r['id']} | {r['dimension']} | {r['name']} | {r['value']} | {r['op']} {r['threshold']} | {r['severity']} | {'✅' if r['passed'] else '❌'} |")
    L += ["", f"Пройдено {sum(r['passed'] for r in B['metrics'])} з {len(B['metrics'])} метрик.", "",
          "## Пріоритети покращення (за впливом на RAG)", "",
          "1. **Повнота графа (M01, M02).** Без явного статусу «не перевірено» генератор домислював вердикт (R10 у ЛР11), "
          "а без агрегату наративу рахував публікації сам і помилявся (T15). Це прямі помилки відповідей — найвищий вплив.",
          "2. **Актуальність і узгодженість значень (M07, M03).** Два регламенти без позначки чинності дають у контексті "
          "суперечливі числа (1 vs 2 докази, 24 vs 12 год) — 4 тести-конфлікти ЛР11 залежать від того, чи модель знає, яка версія чинна.",
          "3. **Унікальність і термінологія корпусу (M09, M05).** Дублікати займають місця в top-k (k = 3) і витісняють потрібні "
          "фрагменти (context recall); назви «R1–R4» замість RULE-n призвели до помилки T14.", "",
          "Менший вплив на RAG: M10 (дублікати сутностей — RAG працює з графом ЛР9, де їх немає), M12 (провенанс фрагментів — важливий для "
          "аудиту цитат), M08/M14 (оновлення джерел потребує доступу до мережі й рішення власника)."]
    (LAB / "quality" / "profile_baseline.md").write_text("\n".join(L) + "\n", encoding="utf-8")


if __name__ == "__main__":
    a = sys.argv[1] if len(sys.argv) > 1 else "baseline"
    if a == "report":
        report()
    else:
        measure(a)
