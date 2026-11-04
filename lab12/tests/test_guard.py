"""ЛР12 · модульні тести захистів text-to-SQL (AST, read-only, LIMIT, тайм-аут). Запуск: python tests/test_guard.py"""
import json, sys, time
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]; sys.path.insert(0, str(ROOT))
from t2sql.t2sql import guard, Rejected, run_readonly, build_db

CASES = [  # (SQL, очікування)
 ("SELECT count(*) FROM fact_check", "pass"),
 ("WITH x AS (SELECT * FROM fact_check) SELECT count(*) FROM x", "pass"),
 ("SELECT * FROM fact_check LIMIT 5000", "pass"),               # LIMIT буде зменшено до 1000
 ("DELETE FROM fact_check WHERE verdict_key = 4", "block"),
 ("UPDATE dim_account SET trust_level = 4", "block"),
 ("DROP TABLE dim_account", "block"),
 ("SELECT 1; DROP TABLE dim_account", "block"),
 ("ATTACH 'x.db' AS y", "block"),
 ("COPY fact_check TO 'out.csv'", "block"),
 ("INSTALL httpfs", "block"),
 ("PRAGMA database_list", "block"),
 ("SELECT * FROM read_csv('C:/Windows/win.ini')", "block"),
 ("SELECT * FROM read_parquet('a.parquet')", "block"),
 ("SELECT * FROM 'data/fact_check.parquet'", "block"),
 ("SELECT getenv('PATH')", "block"),
 ("SELECT * FROM information_schema.tables", "block"),
]
out = []
for sql, exp_ in CASES:
    try:
        g = guard(sql); got, info = "pass", g
    except Rejected as e:
        got, info = "block", str(e)
    out.append(dict(sql=sql, expected=exp_, got=got, info=info, ok=got == exp_))
db = build_db(ROOT / "data" / "t2sql_test.duckdb")
t0 = time.perf_counter()
try:
    run_readonly(db, guard("SELECT count(*) FROM fact_check a, fact_check b, fact_check c WHERE a.shares_at_check + b.shares_at_check > c.shares_at_check"), timeout=2.0)
    to = dict(sql="3-кратний декартів добуток", expected="timeout", got="finished", ok=False)
except TimeoutError as e:
    to = dict(sql="3-кратний декартів добуток (≈ 9,8 млрд комбінацій)", expected="timeout", got="timeout", info=f"{e}; зупинено за {time.perf_counter() - t0:.2f} с", ok=True)
out.append(to)
try:  # read-only: навіть якщо guard обійдено, з'єднання не дозволяє запис
    import duckdb
    c = duckdb.connect(str(db), read_only=True); c.execute("DELETE FROM fact_check"); ro = dict(ok=False, got="deleted")
except Exception as e:  # noqa
    ro = dict(ok=True, got="error", info=str(e).splitlines()[0][:120])
out.append(dict(sql="DELETE через read-only з'єднання (в обхід guard)", expected="error", **ro))
db.unlink()
(ROOT / "results" / "guard_tests.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
for o in out: print("OK " if o["ok"] else "FAIL", o["expected"], o["got"], "|", o["sql"][:55], "→", o.get("info", "")[:70])
print(f"{sum(o['ok'] for o in out)}/{len(out)} тестів пройдено")
