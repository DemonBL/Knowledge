"""ЛР14 · очищення сховища: baseline → clean (версія kb-2026.11-v1).

Кожна зміна має запис у журналі рішень (quality/decisions.csv) і, де значення конкурують,
альтернативу з походженням (data/clean/alternatives.jsonl). Для Neo4j генерується міграція
data/clean/03_quality_fix.cypher і зворотна 03_quality_undo.cypher.
  python quality/clean.py
"""
from __future__ import annotations

import csv
import json
import re
import shutil
import sys
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer

sys.path.insert(0, str(Path(__file__).resolve().parent))
import kb  # noqa: E402

LAB = kb.LAB
OUT = kb.CLEAN
GOUT = OUT / "graph"
TS = "2026-11-06"
OWNER = "Хоптій Д. (власник сховища)"
NEAR_DUP = 0.95


def load_decisions():
    return {r["id"]: r for r in csv.DictReader(open(LAB / "quality" / "decisions.csv", encoding="utf-8"))}


# ------------------------------------------------------------------ граф
def clean_graph(alts, cy, undo):
    nodes, rels = kb.graph("baseline")
    GOUT.mkdir(parents=True, exist_ok=True)
    claim, verd, nar, rule = nodes["Claim"], nodes["Verdict"], nodes["Narrative"], nodes["Rule"]
    about, mk, part, conf, pub = rels["ABOUT"], rels["MAKES_CLAIM"], rels["PART_OF"], rels["CONFIRMS"], nodes["Publication"]

    # повнота: явний статус перевірки для кожного твердження (рішення D1)
    has_v = set(about.end)
    claim["status"] = ["перевірено" if c in has_v else "не перевірено (вердикту немає)" for c in claim.id]
    cy.append("MATCH (c:Claim) WHERE NOT (c)<-[:ABOUT]-(:Verdict) SET c.status = 'не перевірено (вердикту немає)'")
    cy.append("MATCH (c:Claim) WHERE (c)<-[:ABOUT]-(:Verdict) SET c.status = 'перевірено'")
    undo.append("MATCH (c:Claim) REMOVE c.status")

    # повнота: агрегати наративу (рішення D2) — кількість тверджень і публікацій
    pc = mk.merge(part, left_on="end", right_on="start").groupby("end_y").start_x.nunique()
    cc = part.groupby("end").start.nunique()
    nar["claimCount"] = nar.id.map(cc).fillna(0).astype(int).astype(str)
    nar["publicationCount"] = nar.id.map(pc).fillna(0).astype(int).astype(str)
    cy.append("MATCH (n:Narrative) OPTIONAL MATCH (n)<-[:PART_OF]-(c:Claim) OPTIONAL MATCH (c)<-[:MAKES_CLAIM]-(p:Publication) "
              "WITH n, count(DISTINCT c) AS cc, count(DISTINCT p) AS pc SET n.claimCount = cc, n.publicationCount = pc")
    undo.append("MATCH (n:Narrative) REMOVE n.claimCount, n.publicationCount")

    # K1 логічна: «правда» з одним джерелом при регламенті 2.0 → статус відповідності + альтернатива (D3)
    vc = verd.merge(about, left_on="id", right_on="start")
    ncf = conf.groupby("end").start.nunique()
    verd["complianceStatus"] = ""
    for r in vc.itertuples():
        if r.category == "правда" and r.decidedAt >= "2026-09-01" and ncf.get(r.end, 0) < 2:
            verd.loc[verd.id == r.id, "complianceStatus"] = "потребує другого офіційного джерела (INT-REG-2026 §2)"
            alts.append(dict(subject=r.id, property="category", value="правда", status="current-provisional",
                             source="factcheck_registry", rule="INT-REG-2025 §2: достатньо одного офіційного джерела",
                             recorded=TS, decision="D3"))
            alts.append(dict(subject=r.id, property="category", value="неможливо перевірити", status="alternative",
                             source="INT-REG-2026 §2 (reasoner)", rule="за чинним регламентом одного джерела недостатньо",
                             recorded=TS, decision="D3"))
    cy.append("MATCH (v:Verdict {category:'правда'})-[:ABOUT]->(c:Claim) WHERE v.decidedAt >= date('2026-09-01') "
              "AND COUNT { (:OfficialSource)-[:CONFIRMS]->(c) } < 2 "
              "SET v.complianceStatus = 'потребує другого офіційного джерела (INT-REG-2026 §2)'")
    undo.append("MATCH (v:Verdict) REMOVE v.complianceStatus")

    # K2 часова: дата вердикту < першої публікації → обидва значення зберігаються як альтернативи (D4)
    first = mk.merge(pub, left_on="start", right_on="id").groupby("end").publishedAt.min()
    verd["firstSeenAt"], verd["temporalFlag"] = "", ""
    for r in vc.itertuples():
        f = first.get(r.end)
        if f and r.decidedAt < f:
            verd.loc[verd.id == r.id, ["firstSeenAt", "temporalFlag"]] = [f, "вердикт раніше за першу публікацію у графі"]
            alts.append(dict(subject=r.id, property="decidedAt", value=r.decidedAt, status="current", source="factcheck_registry",
                             rule="дата з реєстру фактчекерів (довіра до реєстру; запит на перевірку надіслано)", recorded=TS, decision="D4"))
            alts.append(dict(subject=r.id, property="claimFirstSeenAt", value=f, status="alternative", source="telegram_export / platform_api",
                             rule="найраніша публікація з твердженням у графі", recorded=TS, decision="D4"))
    cy.append("MATCH (v:Verdict)-[:ABOUT]->(c:Claim)<-[:MAKES_CLAIM]-(p:Publication) WITH v, min(p.publishedAt) AS f "
              "WHERE v.decidedAt < f SET v.firstSeenAt = f, v.temporalFlag = 'вердикт раніше за першу публікацію у графі'")
    undo.append("MATCH (v:Verdict) REMOVE v.firstSeenAt, v.temporalFlag")

    # K4 значення + K5 термінологія: правила — канонічний id RULE-n, псевдонім Rn; умова з ЛР8 як альтернатива (D6, D7)
    rule["alias"] = rule.id.str.replace("RULE-", "R", regex=False)
    rule["altCondition"] = ""
    r8 = "автор має спростоване твердження (фейк / маніпуляція) у публікації з ≥ 1000 поширень"
    rule.loc[rule.id == "RULE-2", "altCondition"] = r8 + " [ЛР8 RDF]"
    alts.append(dict(subject="RULE-2", property="condition", value=rule.loc[rule.id == "RULE-2", "condition"].iloc[0],
                     status="current", source="lab07_rules → граф ЛР9", rule="ширше формулювання (будь-яке спростоване твердження)",
                     recorded=TS, decision="D6"))
    alts.append(dict(subject="RULE-2", property="condition", value=r8, status="alternative", source="ЛР8 RDF (data.ttl)",
                     rule="вужче формулювання; узгодити з власником правила Ф-01", recorded=TS, decision="D6"))
    cy.append("MATCH (r:Rule) SET r.alias = replace(r.id, 'RULE-', 'R')")
    cy.append(f"MATCH (r:Rule {{id:'RULE-2'}}) SET r.altCondition = '{r8} [ЛР8 RDF]'")
    undo.append("MATCH (r:Rule) REMOVE r.alias, r.altCondition")

    for lab, df in nodes.items():
        df.to_csv(GOUT / f"nodes_{lab}.csv", index=False)
    for t, df in rels.items():
        df.to_csv(GOUT / f"rels_{t}.csv", index=False)


# ------------------------------------------------------------------ корпус
def near_dups(ch):
    X = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5)).fit_transform([c["text"] for c in ch])
    S = (X @ X.T).toarray()
    num = [tuple(re.findall(r"\d+", c["text"])) for c in ch]
    drop = {}
    for i in range(len(ch)):
        for j in range(i + 1, len(ch)):
            if ch[i]["doc_id"].startswith("INT-REG") or ch[j]["doc_id"].startswith("INT-REG"):
                continue                     # версії регламенту обробляє правило «нечинна версія» нижче
            if S[i, j] >= NEAR_DUP and num[i] == num[j] and j not in drop and i not in drop:
                drop[j] = (ch[i]["chunk_id"], round(float(S[i, j]), 3))
    return drop


def clean_corpus(log):
    ch, docs = kb.corpus("baseline")
    D = {d["doc_id"]: d for d in docs}
    # провенанс на рівні фрагмента (D8)
    for d in docs:
        d.setdefault("source_url", None)
        if not d.get("source_url"):
            d["source_url"] = f"hub://lab10/kb_internal/{d['doc_id']}.md"
        d["status"] = "чинний"
    # актуальність (D5): регламент 1.0 нечинний
    D["INT-REG-2025"].update(status="superseded", supersededBy="INT-REG-2026", validTo="2026-08-31",
                             title="Регламент перевірки повідомлень, версія 1.0 (НЕЧИННИЙ з 2026-09-01; замінено версією 2.0, INT-REG-2026)")
    D["INT-REG-2026"].update(status="чинний", validFrom="2026-09-01", title="Регламент перевірки повідомлень, версія 2.0 (ЧИННИЙ з 2026-09-01)")
    # термінологія (D7, D9)
    D["INT-RULES"]["title"] = "Каталог правил верифікації RULE-1 – RULE-4 (скорочено R1–R4)"
    D["W06"]["altLabel"] = "Діпфейк"
    # унікальність (D10): точні й майже-дублікати; для версій регламенту — дубль у нечинній версії
    drop = near_dups(ch)
    removed = []
    keep = []
    for i, c in enumerate(ch):
        c = dict(c)
        d = D[c["doc_id"]]
        if i in drop:
            removed.append(dict(chunk_id=c["chunk_id"], reason="дублікат", of=drop[i][0], sim=drop[i][1]))
            continue
        if c["chunk_id"] in ("W16:s071", "W13:s002"):          # валідність (D11): обрізаний / навігаційний фрагмент
            removed.append(dict(chunk_id=c["chunk_id"], reason="невалідний фрагмент (навігація/обрізаний текст)", of="", sim=None))
            continue
        c["title"] = d["title"]
        c["source_url"] = d["source_url"]
        c["license"] = d.get("license")
        c["status"] = d["status"]
        if re.search(r"\bR([1-4])\b", c["text"]):
            c["text"] = re.sub(r"\bправило R([1-4])\b", r"правило RULE-\1 (R\1)", c["text"])
            c["text"] = re.sub(r"(?<!RULE-\d \()\bR([1-4])\b(?!\))", r"RULE-\1 (R\1)", c["text"])
        c["embed_text"] = f"{c['title']}. {c['section']}. {c['text']}"
        keep.append(c)
    # дублікати версій регламенту: однакові розділи лишаються лише в чинній версії
    seen = {}
    final = []
    for c in sorted(keep, key=lambda c: (c["doc_id"] != "INT-REG-2026", c["chunk_id"])):
        k = re.sub(r"\W+", "", c["text"].lower())
        if c["doc_id"].startswith("INT-REG") and k in seen:
            removed.append(dict(chunk_id=c["chunk_id"], reason="розділ нечинної версії, ідентичний чинній", of=seen[k], sim=1.0))
            continue
        seen.setdefault(k, c["chunk_id"])
        final.append(c)
    order = {c["chunk_id"]: i for i, c in enumerate(ch)}
    final.sort(key=lambda c: order[c["chunk_id"]])
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "corpus.jsonl", "w", encoding="utf-8") as f:
        for c in final:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    with open(OUT / "docs.jsonl", "w", encoding="utf-8") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    log["corpus_removed"] = removed
    log["corpus_size"] = {"before": len(ch), "after": len(final)}


def main():
    alts, cy, undo, log = [], [], [], {}
    clean_graph(alts, cy, undo)
    clean_corpus(log)
    with open(OUT / "alternatives.jsonl", "w", encoding="utf-8") as f:
        for a in alts:
            f.write(json.dumps(a, ensure_ascii=False) + "\n")
    hdr = "// ЛР14 · міграція якості kb-2026.11-v0 → v1 (Neo4j 5.26). Зворотна: 03_quality_undo.cypher\n"
    (OUT / "03_quality_fix.cypher").write_text(hdr + ";\n".join(cy) + ";\n", encoding="utf-8")
    (OUT / "03_quality_undo.cypher").write_text("// ЛР14 · відкат міграції якості\n" + ";\n".join(undo) + ";\n", encoding="utf-8")
    log["alternatives"] = len(alts)
    log["version"] = "kb-2026.11-v1"
    (LAB / "results" / "clean_log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in log.items() if k != "corpus_removed"}, ensure_ascii=False), len(log["corpus_removed"]), "фрагментів вилучено")


if __name__ == "__main__":
    main()
