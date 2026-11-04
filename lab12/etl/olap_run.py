"""ЛР12 · виконання OLAP-запитів sql/olap/*.sql, незалежна перевірка двох результатів у pandas
(лише з Parquet, без SQL) і формування docs/olap_results.md."""
import json, re
from pathlib import Path
import duckdb
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results" / "olap"; OUT.mkdir(parents=True, exist_ok=True)
con = duckdb.connect(str(ROOT / "data" / "lab12.duckdb"), read_only=True)

META = {  # бізнес-питання, конструкція, інтерпретація (після аналізу результату)
 "01": ("BQ1. Які класи й підкласи ознак найчастіше приводять до вердикту «фейк»/«маніпуляція»?", "ROLLUP + GROUPING()",
        "Найнадійніші ознаки — S1.4 «Терміновий збір коштів» (89 % хибних) і S3.3 «Дипфейк або монтаж» (86,5 %), далі S2.2 «Бот-мережа» (80 %). На рівні класів «За автором» дає 70 %, «За змістом» — 68 %, «За медіа» — 60 %. Найслабша ознака — «Невідповідність геолокації» (39 %): її варто доповнювати іншими. Рядки з grouping_id = 1/3 — підсумки ROLLUP за класом і загалом (2138 перевірок, 67 % хибних)."),
 "02a": ("Drill-down, крок 1: як змінювалась частка хибних вердиктів за класами ознак по місяцях?", "drill-down (рівень класу) × час",
        "На рівні класів видно зростання частки хибних вердиктів для ознак «За автором» із 58 % у липні до 72–74 % у серпні–жовтні, а для «За змістом» — стрибок у вересні (75 %). Щоб зрозуміти, яке саме поняття дає зростання, спускаємося на рівень нижче (Q02b)."),
 "02b": ("Drill-down, крок 2: які конкретні ознаки класу «За автором» (IRI …#Oznaky_ZaAvtorom) дають хибні вердикти й охоплення?", "drill-down (клас → поняття), фільтр за class_iri",
        "Усередині класу найбільший внесок — «Масові репости бот-мережі» (80 % хибних) і «Новий неверифікований акаунт» (68 %, найбільше охоплення 209 тис.). Фільтр за IRI класу, а не за назвою, робить запит стійким до перейменування поняття в таксономії."),
 "03": ("BQ3. Які типи платформ і акаунтів дають найбільше охоплення хибних публікацій?", "CUBE + GROUPING()",
        "Усі комбінації виміру отримано одним запитом. Найбільше охоплення хибних публікацій — анонімні канали в месенджерах (486 тис. із 1,18 млн, 41 %). Загалом месенджери дають 60 % охоплення, а анонімні канали — 64 %. Боти мають багато хибних перевірок (526), але менше охоплення (285 тис.), тобто вони підсилюють, а не створюють поширення. Медіа — лише 20 хибних перевірок."),
 "04": ("BQ2. Скільки триває перевірка залежно від класу методу й пріоритету; чи виконується SLA?", "GROUPING SETS, quantile_cont",
        "Звірка з базами — найшвидша (у середньому 4,6 год, SLA 100 %), експертна перевірка — найповільніша (12,8 год). Слабке місце — експертна перевірка з високим пріоритетом: SLA 12 год виконано лише в 87 % (p90 = 12,7 год). Для таких справ варто одразу паралельно запускати звірку з базами."),
 "05": ("Slice: які наративи домінували в серпні 2026 р.?", "slice (одне значення виміру часу)",
        "Зріз за серпнем показує сплеск NAR-03 «Отруєна питна вода»: 238 перевірок, із них 159 хибних, охоплення 227 тис. — більше, ніж усі інші наративи разом. Це відповідає події, що спричинила хвилю (10–25.08)."),
 "06": ("Dice: якими методами перевіряють медіафейки високого пріоритету в Telegram і TikTok (III–IV кв.)?", "dice (фільтр за 4 вимірами)",
        "У підкубі домінує технічна верифікація: реверсивний пошук і EXIF дають вердикт у середньому за 1,5 год, геолокація — за 4,6 год, а запит до експерта — 10,9 год. Отже, для медіа з високим пріоритетом експертний запит варто залишати як останній крок."),
 "07": ("Як розподіляються вердикти між фактчекінговими організаціями?", "PIVOT",
        "StopFake виносить найбільше вердиктів (643), найбільше з них — «фейк». Частка «неможливо перевірити» найвища в «Детектор медіа» (11,5 %) і EUvsDisinfo (11,3 %) — тема для обміну методиками. PIVOT перетворює значення категорії на стовпці без ручного CASE."),
 "08": ("BQ5. Які наративи зростають: накопичена кількість фейків і 7-денне ковзне середнє?", "вікна SUM … ROWS UNBOUNDED, AVG … ROWS 6 PRECEDING",
        "Ковзне середнє чітко показує три хвилі, що не перетинаються: NAR-03 — пік 18.08 (7,7 фейка/день), NAR-05 — пік 05.10 (7,9/день), NAR-02 — пік 22.10 (8,0/день). Накопичена сума: NAR-05 має найбільше фейків за період (209), а NAR-02 — найбільший приріст у жовтні (із 54 до 195). Для моніторингу кампаній ковзне середнє корисніше за денні значення, бо згладжує ефект вихідних."),
 "09": ("BQ4. Як навантаження розподілене між аналітиками в межах організацій?", "вікна RANK() і SUM() OVER (PARTITION BY); напівадитивна міра",
        "В EUvsDisinfo і «Детектор медіа» один аналітик (соцмережі й боти) виконує 50–57 % перевірок організації і має найдовший час (9–10 год) — ризик вузького місця. backlog_open усереднено (AVG), бо це знімок черги: сума за весь період не має змісту."),
 "10": ("BQ6. Чи вища частка хибних вердиктів у менш довірених авторів (довіра на момент перевірки, SCD2)?", "SCD тип 2: з'єднання з версією виміру",
        "Частка хибних вердиктів спадає від 73 % для «низького» рівня до 42 % для «середнього» та «високого». 193 перевірки (9 %) прив'язані до старих версій акаунтів: після спростувань ці автори вже понижені (стовпець now_downgraded_to). Без SCD2 ці перевірки потрапили б до нижчого рівня довіри і спотворили б залежність."),
}
results = {}
for f in sorted((ROOT / "sql" / "olap").glob("*.sql")):
    key = f.name.split("_")[0]
    sql = f.read_text(encoding="utf-8")
    df = con.execute(sql).df()
    df.to_csv(OUT / f"{f.stem}.csv", index=False)
    results[key] = (f, sql, df)

# ---------------- незалежна перевірка в pandas (з Parquet, без SQL) ----------------
P = lambda t: pd.read_parquet(ROOT / "data" / f"{t}.parquet")
fact, tax, ver, dd, nar = P("fact_check"), P("dim_taxonomy"), P("dim_verdict"), P("dim_date"), P("dim_narrative")
x = fact.merge(tax.add_prefix("s_"), left_on="signal_key", right_on="s_taxonomy_key").merge(ver, on="verdict_key")
pd_q01 = x.groupby("s_class_label").agg(checks=("check_id", "size"), false_pct=("is_false", "mean"))
pd_q01["false_pct"] = (pd_q01.false_pct * 100).round(1)
sql_q01 = results["01"][2].query("grouping_id == 1").set_index("class")[["checks", "false_pct"]]
v1 = bool(((pd_q01.checks.values == sql_q01.loc[pd_q01.index].checks.values) &
           np.isclose(pd_q01.false_pct.values, sql_q01.loc[pd_q01.index].false_pct.values)).all())
y = fact.merge(ver, on="verdict_key").merge(nar, on="narrative_key").merge(dd[["date_key", "full_date"]], on="date_key")
y = y[(y.narrative_id == "NAR-05") & (y.category == "фейк")].groupby("full_date").size()
days = pd.date_range("2026-07-01", "2026-10-31").date
y = y.reindex(days, fill_value=0)
pd_q08 = pd.DataFrame({"fakes": y.values, "cum": y.cumsum().values, "ma7": y.rolling(7, min_periods=1).mean().round(2).values}, index=days)
s8 = results["08"][2].query("narrative_id == 'NAR-05'").set_index("full_date")
v2 = bool((pd_q08.cum.values == s8.cum_fakes.values).all() and np.allclose(pd_q08.ma7.values, s8.ma7_fakes.values))
verif = {"Q01_class_totals": {"match": v1, "pandas": pd_q01.reset_index().to_dict("records")},
         "Q08_NAR05_cum_ma7": {"match": v2, "days": len(days), "pandas_last": pd_q08.iloc[-1].to_dict(), "pandas_peak_ma7": float(pd_q08.ma7.max()),
                               "peak_date": str(pd_q08.ma7.idxmax())}}
(ROOT / "results" / "olap_verification.json").write_text(json.dumps(verif, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
print("pandas verification:", v1, v2)

# ---------------- docs/olap_results.md ----------------
def md_table(df, n=20):
    df = df.head(n)
    cols = [c for c in df.columns if c != "concept_iri"]
    fmt = lambda v: "—" if v is None or (isinstance(v, float) and np.isnan(v)) else (f"{v:g}" if isinstance(v, float) else str(v))
    return "\n".join(["| " + " | ".join(cols) + " |", "|" + "---|" * len(cols)] + ["| " + " | ".join(fmt(r[c]) for c in cols) + " |" for _, r in df.iterrows()])

md = ["# ЛР12 · Результати OLAP-запитів", "", "Сховище: DuckDB `data/lab12.duckdb` (версія набору даних — `data/VERSION.json`). Повні результати — `results/olap/*.csv`.", ""]
for key, (f, sql, df) in results.items():
    q, constr, interp = META[key]
    body = re.sub(r"^--.*\n", "", sql, flags=re.M).strip()
    show = df[df.full_date.astype(str).isin(["2026-08-17", "2026-08-25", "2026-09-30", "2026-10-31"])] if key == "08" else df
    md += [f"## Q{key} · {f.stem[len(key) + 1:].replace('_', ' ')}", "", f"**Бізнес-питання.** {q}", "", f"**Конструкція:** {constr}.", "",
           "```sql", body, "```", "", f"**Результат** ({len(df)} рядків{'; показано вибрані дати' if key == '08' else ''}):", "", md_table(show), "",
           f"**Інтерпретація.** {interp}", ""]
md += ["## Незалежна перевірка (pandas)", "",
       f"1. **Q01, підсумки за класами ознак:** pandas `groupby` по Parquet дав ті самі кількості й частки хибних — **{'збіг' if v1 else 'розбіжність'}**.",
       f"2. **Q08, NAR-05:** накопичена сума `cumsum()` і `rolling(7).mean()` по {len(days)} днях збіглися з віконними функціями SQL — **{'збіг' if v2 else 'розбіжність'}**; пік ковзного середнього {verif['Q08_NAR05_cum_ma7']['pandas_peak_ma7']} — {verif['Q08_NAR05_cum_ma7']['peak_date']}.", ""]
(ROOT / "docs" / "olap_results.md").write_text("\n".join(md), encoding="utf-8")
print("written docs/olap_results.md")
