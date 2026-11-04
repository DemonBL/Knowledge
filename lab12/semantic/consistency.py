"""ЛР12 · перевірка узгодженості: те саме питання трьома шляхами —
(1) семантичний шар, (2) ручний OLAP-запит із sql/olap, (3) pandas по Parquet. Вихід: results/semantic_consistency.json, docs/semantic_layer.md"""
import json, sys
from pathlib import Path
import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from semantic.semantic import SemanticLayer  # noqa: E402

sl = SemanticLayer()
con = duckdb.connect(str(ROOT / "data" / "lab12.duckdb"), read_only=True)
olap = lambda f: con.execute((ROOT / "sql" / "olap" / f).read_text(encoding="utf-8")).df()
P = lambda t: pd.read_parquet(ROOT / "data" / f"{t}.parquet")
fact, ver, tax, plat = P("fact_check"), P("dim_verdict"), P("dim_taxonomy"), P("dim_platform")
fv = fact.merge(ver, on="verdict_key")

cases = []
# --- питання 1: частка хибних вердиктів за класом ознаки
a = sl.query(["false_verdict_rate", "checks_count"], ["signal_class"]).set_index("signal_class")
b = olap("01_rollup_signals.sql").query("grouping_id == 1").set_index("class")[["false_pct", "checks"]]
x = fv.merge(tax.add_prefix("s_"), left_on="signal_key", right_on="s_taxonomy_key")
c = x.groupby("s_class_label").agg(r=("is_false", "mean"), n=("check_id", "size")); c["r"] = (c.r * 100).round(1)
ok = np.allclose(a.false_verdict_rate, b.loc[a.index].false_pct) and np.allclose(a.false_verdict_rate, c.loc[a.index].r) \
     and (a.checks_count.values == b.loc[a.index].checks.values).all()
cases.append(dict(question="Яка частка хибних вердиктів за класами ознак?", metric="false_verdict_rate × signal_class",
                  paths=["semantic layer", "Q01 ROLLUP (grouping_id = 1)", "pandas"], values=a.false_verdict_rate.to_dict(), match=bool(ok),
                  sql=sl.metric_sql(["false_verdict_rate", "checks_count"], ["signal_class"])))
# --- питання 2: середній час і SLA за класом методу
a = sl.query(["avg_hours_to_verdict", "sla_compliance_rate"], ["method_class"]).set_index("method_class")
b = olap("04_grouping_sets_sla.sql").query("priority == '—' and method_class != '—'").set_index("method_class")
x = fact.merge(tax.add_prefix("m_"), left_on="method_key", right_on="m_taxonomy_key")
c = x.groupby("m_class_label").agg(h=("hours_to_verdict", lambda s: s.astype(float).mean()), sla=("sla_met", "mean"))
ok = np.allclose(a.avg_hours_to_verdict, b.loc[a.index].avg_hours) and np.allclose(a.sla_compliance_rate, b.loc[a.index].sla_pct) \
     and np.allclose(a.avg_hours_to_verdict, c.loc[a.index].h.round(1)) and np.allclose(a.sla_compliance_rate, (c.loc[a.index].sla * 100).round(1))
cases.append(dict(question="Скільки в середньому триває перевірка і яка частка SLA за класами методів?", metric="avg_hours_to_verdict, sla_compliance_rate × method_class",
                  paths=["semantic layer", "Q04 GROUPING SETS (method_class)", "pandas"], values=a.to_dict("index"), match=bool(ok),
                  sql=sl.metric_sql(["avg_hours_to_verdict", "sla_compliance_rate"], ["method_class"])))
# --- питання 3: охоплення хибних публікацій за типом платформи
a = sl.query(["false_reach"], ["platform_type"]).set_index("platform_type")
b = olap("03_cube_reach.sql").query("grouping_id == 1").set_index("platform_type")
c = fv[fv.is_false].merge(plat, on="platform_key").groupby("platform_type").shares_at_check.sum()
ok = (a.false_reach.values == b.loc[a.index].reach.values).all() and (a.false_reach.values == c.loc[a.index].values).all()
cases.append(dict(question="Яке охоплення хибних публікацій за типами платформ?", metric="false_reach × platform_type",
                  paths=["semantic layer", "Q03 CUBE (grouping_id = 1)", "pandas"], values=a.false_reach.to_dict(), match=bool(ok),
                  sql=sl.metric_sql(["false_reach"], ["platform_type"])))
(ROOT / "results" / "semantic_consistency.json").write_text(json.dumps(cases, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
for cs in cases: print(cs["match"], cs["question"], cs["values"])

# --- docs/semantic_layer.md
md = ["# ЛР12 · Семантичний шар", "", "Файл метрик: `semantic/metrics.yml` (версія " + sl.spec["version"] + "); генератор SQL: `semantic/semantic.py` (клас `SemanticLayer`, метод `metric_sql`).", "",
      "## Метрики", "", "| Назва | Визначення | Формула | Одиниця | Адитивність | Власник | Джерела | Обмеження | Перегляд | Статус |", "|---|---|---|---|---|---|---|---|---|---|"]
for m in sl.metrics.values():
    md.append(f"| `{m['name']}` | {m['definition']} | `{m['formula']}` | {m['unit']} | {m['additivity']} | {m['owner']} | {', '.join(m['sources'])} | {m['constraints']} | {m['review_date']} | {m['status']} |")
md += ["", "## Як працює генерація SQL", "",
       "1. Метрика має формулу та список потрібних з'єднань; вимір — колонку і з'єднання.",
       "2. `metric_sql(metrics, dimensions, filters)` перевіряє, що всі назви є в каталозі (білий список). Потім додає лише потрібні JOIN, будує SELECT / WHERE / GROUP BY і екранує літерали фільтрів.",
       "3. Та сама функція формує текстовий каталог для підказки text-to-SQL (`catalog_text()`), тож LLM бачить ті самі визначення, що й аналітик.", "",
       "Приклад: `metric_sql(['false_verdict_rate', 'checks_count'], ['signal_class'], {'month': [8, 9]})` →", "", "```sql",
       sl.metric_sql(["false_verdict_rate", "checks_count"], ["signal_class"], {"month": [8, 9]}), "```", "", "## Перевірка узгодженості", ""]
for cs in cases:
    md += [f"**{cs['question']}** ({cs['metric']}). Шляхи: {'; '.join(cs['paths'])}. Результат: **{'збіг' if cs['match'] else 'розбіжність'}**.", "",
           "```sql", cs["sql"], "```", "", f"Значення: `{json.dumps(cs['values'], ensure_ascii=False)}`", ""]
md += ["Без семантичного шару «частку хибних» можна порахувати по-різному: усереднити частки підгруп, рахувати «неможливо перевірити» як хибний, брати поточну довіру замість історичної. Тоді різні звіти дають різні числа. Єдина формула в `metrics.yml` усуває цю неоднозначність.", ""]
(ROOT / "docs" / "semantic_layer.md").write_text("\n".join(md), encoding="utf-8")
