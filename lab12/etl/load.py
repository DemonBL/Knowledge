"""ЛР12 · ELT: сирі CSV + SKOS-таксономія → staging → зірка в DuckDB → перевірки якості → Parquet.
Запуск: python etl/load.py   (результат: data/lab12.duckdb, data/*.parquet, data/VERSION.json, results/dq_report.*)"""
import hashlib, json, sys
from datetime import datetime
from pathlib import Path
import duckdb
import pandas as pd
from rdflib import Graph, RDF
from rdflib.namespace import SKOS

ROOT = Path(__file__).resolve().parents[1]
DATA, RAW, RES = ROOT / "data", ROOT / "data" / "raw", ROOT / "results"
RES.mkdir(exist_ok=True)
DB = DATA / "lab12.duckdb"
VERSION = "1.0.0"
SLA_HOURS = {"високий": 12, "середній": 24, "низький": 48}   # регламент v2.0 (високий пріоритет — 12 год)

if DB.exists(): DB.unlink()
con = duckdb.connect(str(DB))
con.execute((ROOT / "sql" / "ddl.sql").read_text(encoding="utf-8"))

# ---------------- 1. Extract + Load у staging ----------------
for t in ["checks", "accounts", "account_trust_history", "analysts", "narratives"]:
    con.execute(f"CREATE TABLE stg_{t} AS SELECT * FROM read_csv('{(RAW / (t + '.csv')).as_posix()}', header=true, all_varchar=true)")
g = Graph().parse(ROOT / "taxonomy" / "taxonomy.ttl")
tax = []
for c in g.subjects(RDF.type, SKOS.Concept):
    chain = [c]
    while (p := g.value(chain[-1], SKOS.broader)) is not None: chain.append(p)
    chain = chain[::-1]                       # [гілка, клас, поняття]
    lab = lambda x: str(g.value(x, SKOS.prefLabel))
    tax.append(dict(concept_iri=str(c), notation=str(g.value(c, SKOS.notation)), label=lab(c), level=len(chain),
                    parent_iri=str(chain[-2]) if len(chain) > 1 else None, branch_iri=str(chain[0]), branch_label=lab(chain[0]),
                    class_iri=str(chain[1]) if len(chain) > 1 else None, class_label=lab(chain[1]) if len(chain) > 1 else None,
                    scheme_iri=str(g.value(c, SKOS.inScheme))))
stg_tax = pd.DataFrame(sorted(tax, key=lambda r: r["notation"]))
con.register("stg_tax_df", stg_tax)

# ---------------- 2. Очищення staging (журнал рішень) ----------------
log = {}
log["raw_rows"] = con.execute("SELECT count(*) FROM stg_checks").fetchone()[0]
log["duplicates_removed"] = con.execute("SELECT count(*) - count(DISTINCT check_id) FROM stg_checks").fetchone()[0]
con.execute("CREATE TABLE stg_checks_dedup AS SELECT * FROM stg_checks QUALIFY row_number() OVER (PARTITION BY check_id ORDER BY verdict_at) = 1")
con.execute("""CREATE TABLE quarantine AS SELECT c.*, 'невідомий account_id' AS reason FROM stg_checks_dedup c
               WHERE c.account_id NOT IN (SELECT account_id FROM stg_accounts)""")
log["quarantined_orphans"] = con.execute("SELECT count(*) FROM quarantine").fetchone()[0]
con.execute("DELETE FROM stg_checks_dedup WHERE check_id IN (SELECT check_id FROM quarantine)")

# ---------------- 3. Виміри ----------------
con.execute("""INSERT INTO dim_date
SELECT CAST(strftime(d, '%Y%m%d') AS INTEGER), d, day(d),
       ['пн','вт','ср','чт','пт','сб','нд'][isodow(d)], weekofyear(d), date_trunc('week', d), month(d),
       ['січень','лютий','березень','квітень','травень','червень','липень','серпень','вересень','жовтень','листопад','грудень'][month(d)],
       quarter(d), year(d), isodow(d) >= 6
FROM (SELECT unnest(generate_series(DATE '2026-06-01', DATE '2026-12-31', INTERVAL 1 DAY))::DATE AS d)""")
con.execute("""INSERT INTO dim_taxonomy SELECT row_number() OVER (ORDER BY notation), concept_iri, notation, label, level, parent_iri,
               branch_iri, branch_label, class_iri, class_label, scheme_iri FROM stg_tax_df""")
con.execute("""INSERT INTO dim_account
SELECT row_number() OVER (ORDER BY h.account_id, h.valid_from), h.account_id, a.name, a.kind, CAST(h.trust_level AS TINYINT),
       ['низький','знижений','середній','високий'][CAST(h.trust_level AS INTEGER)],
       CAST(h.valid_from AS DATE),
       COALESCE(CAST(lead(h.valid_from) OVER w AS DATE) - 1, DATE '9999-12-31'),
       lead(h.valid_from) OVER w IS NULL
FROM stg_account_trust_history h JOIN stg_accounts a USING (account_id)
WINDOW w AS (PARTITION BY h.account_id ORDER BY h.valid_from)""")
con.execute("""INSERT INTO dim_platform VALUES (1,'Telegram','месенджер'),(2,'Facebook','соцмережа'),(3,'X','соцмережа'),
               (4,'Instagram','соцмережа'),(5,'TikTok','відеоплатформа'),(6,'YouTube','відеоплатформа')""")
con.execute("""INSERT INTO dim_analyst SELECT row_number() OVER (ORDER BY analyst_id), analyst_id, name, specialization, org_id, org_name
               FROM stg_analysts""")
con.execute("INSERT INTO dim_narrative VALUES (0, 'NAR-00', 'без наративу', '—')")
con.execute("""INSERT INTO dim_narrative SELECT CAST(substr(narrative_id, 5) AS INTEGER), narrative_id, name, theme FROM stg_narratives""")
con.execute("""INSERT INTO dim_verdict VALUES (1,'фейк',true,3),(2,'маніпуляція',true,2),(3,'неможливо перевірити',false,1),(4,'правда',false,0)""")

# ---------------- 4. Факт ----------------
sla = " ".join(f"WHEN '{k}' THEN {v}" for k, v in SLA_HOURS.items())
con.execute(f"""INSERT INTO fact_check
SELECT c.check_id, c.publication_id,
       CAST(strftime(CAST(c.verdict_at AS TIMESTAMP), '%Y%m%d') AS INTEGER),
       CAST(strftime(CAST(c.detected_at AS TIMESTAMP), '%Y%m%d') AS INTEGER),
       a.account_key, p.platform_key, an.analyst_key, COALESCE(n.narrative_key, 0), s.taxonomy_key, m.taxonomy_key, v.verdict_key,
       c.priority, 1, CAST(c.shares_at_check AS INTEGER), CAST(c.evidence_count AS INTEGER), CAST(c.effort_minutes AS INTEGER),
       CAST(c.backlog_open AS INTEGER),
       round(date_diff('minute', CAST(c.detected_at AS TIMESTAMP), CAST(c.verdict_at AS TIMESTAMP)) / 60.0, 2),
       CAST(c.confidence AS DECIMAL(3,2)),
       date_diff('minute', CAST(c.detected_at AS TIMESTAMP), CAST(c.verdict_at AS TIMESTAMP)) / 60.0 <= CASE c.priority {sla} END
FROM stg_checks_dedup c
LEFT JOIN dim_account a  ON a.account_id = c.account_id AND CAST(c.verdict_at AS DATE) BETWEEN a.valid_from AND a.valid_to
LEFT JOIN dim_platform p ON p.platform = c.platform
LEFT JOIN dim_analyst an ON an.analyst_id = c.analyst_id
LEFT JOIN dim_narrative n ON n.narrative_id = c.narrative_id
LEFT JOIN dim_taxonomy s ON s.concept_iri = c.signal_iri
LEFT JOIN dim_taxonomy m ON m.concept_iri = c.method_iri
LEFT JOIN dim_verdict v  ON v.category = c.verdict""")

# ---------------- 5. Перевірки якості ----------------
ORPHANS = """SELECT 'account' AS fk, count(*) AS n FROM fact_check f LEFT JOIN dim_account d USING (account_key) WHERE d.account_key IS NULL
UNION ALL SELECT 'platform', count(*) FROM fact_check f LEFT JOIN dim_platform d USING (platform_key) WHERE d.platform_key IS NULL
UNION ALL SELECT 'analyst', count(*) FROM fact_check f LEFT JOIN dim_analyst d USING (analyst_key) WHERE d.analyst_key IS NULL
UNION ALL SELECT 'narrative', count(*) FROM fact_check f LEFT JOIN dim_narrative d USING (narrative_key) WHERE d.narrative_key IS NULL
UNION ALL SELECT 'signal', count(*) FROM fact_check f LEFT JOIN dim_taxonomy d ON d.taxonomy_key = f.signal_key WHERE d.taxonomy_key IS NULL
UNION ALL SELECT 'method', count(*) FROM fact_check f LEFT JOIN dim_taxonomy d ON d.taxonomy_key = f.method_key WHERE d.taxonomy_key IS NULL
UNION ALL SELECT 'verdict', count(*) FROM fact_check f LEFT JOIN dim_verdict d USING (verdict_key) WHERE d.verdict_key IS NULL
UNION ALL SELECT 'date', count(*) FROM fact_check f LEFT JOIN dim_date d USING (date_key) WHERE d.date_key IS NULL"""
(ROOT / "sql" / "checks").mkdir(exist_ok=True)
(ROOT / "sql" / "checks" / "orphans.sql").write_text("-- «Сироти»: рядки факту без відповідного рядка виміру (очікується 0 для кожного FK)\n" + ORPHANS + ";\n", encoding="utf-8")
CHECKS = [
    ("DQ1", "not null", "ключі та міри факту не порожні",
     "SELECT count(*) FROM fact_check WHERE " + " OR ".join(f"{c} IS NULL" for c in
        ["account_key", "platform_key", "analyst_key", "narrative_key", "signal_key", "method_key", "verdict_key", "date_key", "hours_to_verdict", "confidence"]), "error"),
    ("DQ2", "унікальність", "check_id унікальний; одна поточна версія акаунта",
     "SELECT (SELECT count(*) - count(DISTINCT check_id) FROM fact_check) + (SELECT count(*) FROM (SELECT account_id FROM dim_account WHERE is_current GROUP BY 1 HAVING count(*) <> 1))", "error"),
    ("DQ3", "сироти (FK)", "кожен ключ факту знайдено у вимірі", f"SELECT sum(n) FROM ({ORPHANS})", "error"),
    ("DQ4", "діапазони", "confidence ∈ [0;1], hours > 0 і ≤ 168, shares ≥ 0, evidence ∈ [0;10]",
     "SELECT count(*) FROM fact_check WHERE confidence NOT BETWEEN 0 AND 1 OR hours_to_verdict <= 0 OR hours_to_verdict > 168 OR shares_at_check < 0 OR evidence_count NOT BETWEEN 0 AND 10", "error"),
    ("DQ5", "узгодженість дат", "вердикт не раніше виявлення; дата в межах 01.07–31.10.2026 (+1 день)",
     "SELECT count(*) FROM fact_check WHERE date_key < detected_date_key OR date_key NOT BETWEEN 20260701 AND 20261101", "error"),
    ("DQ6", "таксономія", "ознака — листок гілки «Ознаки», метод — листок гілки «Методи»",
     """SELECT count(*) FROM fact_check f JOIN dim_taxonomy s ON s.taxonomy_key = f.signal_key JOIN dim_taxonomy m ON m.taxonomy_key = f.method_key
        WHERE s.level <> 3 OR m.level <> 3 OR s.notation NOT LIKE 'S%' OR m.notation NOT LIKE 'M%'""", "error"),
    ("DQ7", "SCD2", "версії акаунта не перетинаються і без розривів",
     """SELECT count(*) FROM (SELECT valid_from, lag(valid_to) OVER (PARTITION BY account_id ORDER BY valid_from) AS prev_to FROM dim_account)
        WHERE prev_to IS NOT NULL AND prev_to <> valid_from - 1""", "error"),
    ("DQ8", "бізнес-правило", "«фейк»/«маніпуляція» мають ≥ 2 доказів (регламент v2.0)",
     "SELECT count(*) FROM fact_check f JOIN dim_verdict v USING (verdict_key) WHERE v.is_false AND evidence_count < 2", "warning"),
]
dq = []
for cid, kind, desc, sql, sev in CHECKS:
    n = int(con.execute(sql).fetchone()[0] or 0)
    dq.append(dict(id=cid, kind=kind, description=desc, violations=n, severity=sev, status="pass" if n == 0 else ("fail" if sev == "error" else "warn"), sql=" ".join(sql.split())))
orph = con.execute(ORPHANS).fetchall()
report = {"generated": datetime.now().isoformat(timespec="seconds"), "dataset_version": VERSION, "staging": log,
          "orphans_by_fk": dict(orph), "checks": dq}
(RES / "dq_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
md = ["# Звіт перевірок якості даних (ЛР12)", "", f"Версія набору: {VERSION}; згенеровано {report['generated']}", "",
      f"Staging: сирих рядків {log['raw_rows']}, вилучено дублікатів {log['duplicates_removed']}, у карантин (сироти) {log['quarantined_orphans']}.", "",
      "| ID | Тип | Перевірка | Порушень | Статус |", "|---|---|---|---|---|"]
md += [f"| {d['id']} | {d['kind']} | {d['description']} | {d['violations']} | {d['status']} |" for d in dq]
(RES / "dq_report.md").write_text("\n".join(md) + "\n", encoding="utf-8")

# ---------------- 6. Parquet + версія ----------------
tables = ["dim_date", "dim_taxonomy", "dim_account", "dim_platform", "dim_analyst", "dim_narrative", "dim_verdict", "fact_check"]
counts = {}
for t in tables:
    con.execute(f"COPY {t} TO '{(DATA / (t + '.parquet')).as_posix()}' (FORMAT parquet, COMPRESSION zstd)")
    counts[t] = con.execute(f"SELECT count(*) FROM {t}").fetchone()[0]
con.execute(f"COPY quarantine TO '{(DATA / 'quarantine.csv').as_posix()}' (HEADER)")
sha = lambda p: hashlib.sha256(p.read_bytes()).hexdigest()[:16]
version = {"dataset": "lab12-factcheck-star", "version": VERSION, "created": datetime.now().isoformat(timespec="seconds"),
           "generator": "etl/generate.py", "seed": 12, "generator_sha256": sha(ROOT / "etl" / "generate.py"),
           "taxonomy": "taxonomy/taxonomy.ttl", "taxonomy_sha256": sha(ROOT / "taxonomy" / "taxonomy.ttl"),
           "duckdb": duckdb.__version__, "pandas": pd.__version__, "python": sys.version.split()[0], "rows": counts,
           "parquet_sha256": {t: sha(DATA / (t + ".parquet")) for t in tables}}
(DATA / "VERSION.json").write_text(json.dumps(version, ensure_ascii=False, indent=1), encoding="utf-8")
con.close()
print("staging:", log); print("rows:", counts)
for d in dq: print(d["id"], d["kind"], d["violations"], d["status"])
