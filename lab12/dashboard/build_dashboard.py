"""ЛР12 · аналітична панель: 5 візуалізацій за 5 бізнес-питаннями.
Дані беруться через семантичний шар (ті самі метрики, що в metrics.yml).
Вихід: dashboard/dashboard.html (plotly, інтерактивна) і dashboard/v1..v5.png (для звіту)."""
import sys
from pathlib import Path
import duckdb
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from plotly.subplots import make_subplots

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from semantic.semantic import SemanticLayer  # noqa: E402

OUT = ROOT / "dashboard"
sl = SemanticLayer()
con = duckdb.connect(str(ROOT / "data" / "lab12.duckdb"), read_only=True)
C = ["#2a78d6", "#eb6834", "#1baf7a"]          # категоріальні слоти 1–3 (провалідована палітра)
INK, MUTED, GRID = "#0b0b0b", "#52514e", "#e6e5e1"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.edgecolor": MUTED, "axes.labelcolor": INK,
                     "xtick.color": MUTED, "ytick.color": MUTED, "axes.spines.top": False, "axes.spines.right": False})

# ---- дані
v1 = sl.query(["false_verdict_rate", "checks_count"], ["signal_class", "signal"]).sort_values(["signal_class", "false_verdict_rate"])
v1c = sl.query(["false_verdict_rate"], ["signal_class"]).set_index("signal_class").false_verdict_rate
v2 = con.execute((ROOT / "sql/olap/08_window_narratives.sql").read_text(encoding="utf-8")).df()
nar = dict(con.execute("SELECT narrative_id, name FROM dim_narrative").fetchall())
v3 = sl.query(["false_reach"], ["platform_type", "account_kind"]).pivot(index="account_kind", columns="platform_type", values="false_reach").fillna(0)
v3 = v3.loc[["анонімний канал", "бот", "користувач", "медіа"], ["месенджер", "соцмережа", "відеоплатформа"]]
v4 = sl.query(["avg_hours_to_verdict", "sla_compliance_rate", "checks_count"], ["method_class", "priority"])
v5 = sl.query(["false_verdict_rate", "checks_count"], ["trust_at_check"])
order = ["низький", "знижений", "середній", "високий"]
v5 = v5.set_index("trust_at_check").loc[order].reset_index()

TXT = {
 "v1": ("BQ1. Частка хибних вердиктів за ознаками таксономії (клас → ознака)",
        "Найсильніші ознаки: терміновий збір коштів (89 %) і дипфейк/монтаж (86,5 %). Найслабша — невідповідність геолокації (39 %). Клас «За автором» загалом найінформативніший (70 %)."),
 "v2": ("BQ5. Фейки за наративами: 7-денне ковзне середнє",
        "Три хвилі не перетинаються: «Отруєна питна вода» — середина серпня, «Фейкові збори коштів» — кінець вересня, «Колапс інфраструктури» — пік 22.10, наприкінці жовтня спадає. Сплеск видно за 2–3 дні до піку, тож можна заздалегідь підсилити чергу."),
 "v3": ("BQ3. Охоплення хибних публікацій: тип акаунта × тип платформи",
        "Анонімні канали в месенджерах дають 41 % охоплення хибних публікацій (486 тис.). Боти численні, але їхнє охоплення втричі менше: вони підсилюють поширення, а не створюють аудиторію."),
 "v4": ("BQ2. Середній час до вердикту за методом і пріоритетом (год)",
        "Звірка з базами найшвидша при будь-якому пріоритеті. Експертна перевірка з високим пріоритетом у середньому триває 7,3 год, але лише 87 % встигають у SLA 12 год. Таким справам потрібна паралельна звірка з базами."),
 "v5": ("BQ6. Частка хибних вердиктів за рівнем довіри автора на момент перевірки",
        "Частка хибних вердиктів спадає з 73 % («низький») до 42 % («середній»/«високий»). Отже, індекс довіри — корисна ознака пріоритизації. Рівень «високий» має лише 36 перевірок, тому оцінка для нього ненадійна."),
}

# ---- PNG для звіту (matplotlib)
def save(fig, name):
    fig.tight_layout(); fig.savefig(OUT / f"{name}.png", dpi=200); plt.close(fig)

fig, ax = plt.subplots(figsize=(7.2, 4.2))
classes = list(dict.fromkeys(v1.signal_class))
y, labels, colors = [], [], []
pos = 0
for i, cl in enumerate(classes):
    part = v1[v1.signal_class == cl]
    for _, r in part.iterrows():
        y.append(pos); labels.append(r.signal); colors.append(C[i]); pos += 1
    pos += 0.6
vals = list(v1.groupby("signal_class", sort=False).apply(lambda d: list(d.false_verdict_rate)).sum())
ax.barh(y, vals, color=colors, height=0.72)
for yy, vv in zip(y, vals): ax.text(vv + 1, yy, f"{vv:.0f} %", va="center", fontsize=8, color=INK)
ax.set_yticks(y, labels, fontsize=8); ax.set_xlim(0, 100); ax.set_xlabel("частка хибних вердиктів, %")
ax.xaxis.grid(True, color=GRID); ax.set_axisbelow(True)
from matplotlib.patches import Patch
ax.legend([Patch(color=C[i]) for i in range(len(classes))], [f"{c} (разом {v1c[c]:.0f} %)" for c in classes], frameon=False, fontsize=8, loc="lower center", bbox_to_anchor=(0.3, 1.0), ncol=3)
save(fig, "v1")

fig, ax = plt.subplots(figsize=(7.2, 3.3))
for i, n in enumerate(["NAR-03", "NAR-05", "NAR-02"]):
    d = v2[v2.narrative_id == n]
    ax.plot(d.full_date, d.ma7_fakes, color=C[i], lw=2, label=nar[n])
    pk = d.loc[d.ma7_fakes.idxmax()]
    ax.annotate(f"{pk.ma7_fakes:.1f}", (pk.full_date, pk.ma7_fakes), xytext=(0, 5), textcoords="offset points", ha="center", fontsize=8, color=INK)
ax.set_ylabel("фейків на день (ковзне 7 дн.)"); ax.yaxis.grid(True, color=GRID); ax.set_axisbelow(True)
ax.legend(frameon=False, fontsize=8, loc="upper left"); fig.autofmt_xdate()
save(fig, "v2")

fig, ax = plt.subplots(figsize=(6.4, 3.2))
im = ax.imshow(v3.values / 1000, cmap="Blues", aspect="auto")
ax.set_xticks(range(3), v3.columns); ax.set_yticks(range(4), v3.index)
for i in range(v3.shape[0]):
    for j in range(v3.shape[1]):
        val = v3.values[i, j] / 1000
        ax.text(j, i, f"{val:.0f} тис.", ha="center", va="center", fontsize=9, color="white" if val > 250 else INK)
fig.colorbar(im, ax=ax, label="охоплення, тис. поширень")
ax.spines[:].set_visible(False)
save(fig, "v3")

fig, ax = plt.subplots(figsize=(7.2, 3.4))
pr = ["високий", "середній", "низький"]; mc = ["Звірка з базами", "Технічна верифікація", "Експертна перевірка"]
w = 0.26
for i, p in enumerate(pr):
    d = v4[v4.priority == p].set_index("method_class").loc[mc]
    xs = [k + (i - 1) * w for k in range(3)]
    ax.bar(xs, d.avg_hours_to_verdict, w - 0.03, color=C[i], label=f"пріоритет {p}")
    for x, h, s in zip(xs, d.avg_hours_to_verdict, d.sla_compliance_rate):
        ax.text(x, h + 0.3, f"{h:.1f}\nSLA {s:.0f}%", ha="center", fontsize=7, color=INK)
ax.set_xticks(range(3), mc); ax.set_ylabel("середній час, год"); ax.set_ylim(0, 25)
ax.yaxis.grid(True, color=GRID); ax.set_axisbelow(True); ax.legend(frameon=False, fontsize=8, loc="upper left")
save(fig, "v4")

fig, ax = plt.subplots(figsize=(6.4, 3.0))
ax.bar(v5.trust_at_check, v5.false_verdict_rate, color=C[0], width=0.55)
for x, (r, n) in enumerate(zip(v5.false_verdict_rate, v5.checks_count)):
    ax.text(x, r + 1.5, f"{r:.0f} %\n(n = {n:.0f})", ha="center", fontsize=8, color=INK)
ax.set_ylim(0, 90); ax.set_ylabel("частка хибних вердиктів, %"); ax.set_xlabel("рівень довіри автора на момент перевірки (SCD2)")
ax.yaxis.grid(True, color=GRID); ax.set_axisbelow(True)
save(fig, "v5")

# ---- інтерактивна панель (plotly, підказки при наведенні)
kpi = sl.query(["checks_count", "false_verdict_rate", "false_reach", "avg_hours_to_verdict", "sla_compliance_rate"]).iloc[0]
fig = make_subplots(rows=3, cols=2, specs=[[{"type": "sunburst"}, {"type": "xy"}], [{"type": "heatmap"}, {"type": "xy"}], [{"type": "xy", "colspan": 2}, None]],
                    subplot_titles=[TXT[k][0] for k in ["v1", "v2", "v3", "v4", "v5"]], vertical_spacing=0.09, horizontal_spacing=0.08)
sb = v1.copy()
ids = ["Ознаки"] + [f"Ознаки/{c}" for c in classes] + [f"Ознаки/{r.signal_class}/{r.signal}" for r in sb.itertuples()]
par = [""] + ["Ознаки"] * len(classes) + [f"Ознаки/{r.signal_class}" for r in sb.itertuples()]
lab = ["Ознаки дезінформації"] + classes + list(sb.signal)
cnt_c = sb.groupby("signal_class").checks_count.sum()
valsb = [cnt_c.sum()] + [cnt_c[c] for c in classes] + list(sb.checks_count)
rate = [float(kpi.false_verdict_rate)] + [float(v1c[c]) for c in classes] + list(sb.false_verdict_rate)
fig.add_trace(go.Sunburst(ids=ids, parents=par, labels=lab, values=valsb, branchvalues="total", marker=dict(colors=rate, colorscale="Blues", cmin=30, cmax=95),
                          hovertemplate="%{label}<br>перевірок: %{value}<br>хибних: %{color:.1f} %<extra></extra>"), 1, 1)
for i, n in enumerate(["NAR-03", "NAR-05", "NAR-02"]):
    d = v2[v2.narrative_id == n]
    fig.add_trace(go.Scatter(x=d.full_date, y=d.ma7_fakes, name=nar[n], line=dict(color=C[i], width=2),
                             hovertemplate="%{x|%d.%m}: %{y:.1f} фейків/день<extra>" + nar[n] + "</extra>"), 1, 2)
fig.add_trace(go.Heatmap(z=v3.values / 1000, x=list(v3.columns), y=list(v3.index), colorscale="Blues", showscale=False,
                         text=[[f"{v / 1000:.0f} тис." for v in row] for row in v3.values], texttemplate="%{text}",
                         hovertemplate="%{y} · %{x}: %{z:.0f} тис. поширень<extra></extra>"), 2, 1)
for i, p in enumerate(pr):
    d = v4[v4.priority == p].set_index("method_class").loc[mc]
    fig.add_trace(go.Bar(x=mc, y=d.avg_hours_to_verdict, name=f"пріоритет {p}", marker_color=C[i], customdata=d.sla_compliance_rate,
                         hovertemplate="%{x}<br>%{y:.1f} год, SLA %{customdata:.0f} %<extra>" + p + "</extra>"), 2, 2)
fig.add_trace(go.Bar(x=v5.trust_at_check, y=v5.false_verdict_rate, marker_color=C[0], showlegend=False, customdata=v5.checks_count,
                     text=[f"{r:.0f} %" for r in v5.false_verdict_rate], textposition="outside",
                     hovertemplate="довіра %{x}: %{y:.1f} % хибних (n = %{customdata})<extra></extra>"), 3, 1)
fig.update_layout(height=1250, template="plotly_white", font=dict(family="DejaVu Sans, Arial", size=12), barmode="group",
                  legend=dict(orientation="h", y=1.04), margin=dict(t=110, l=40, r=30, b=40),
                  title=dict(text=f"Перевірка публікацій · 01.07–31.10.2026 · перевірок: {kpi.checks_count:.0f} · хибних: {kpi.false_verdict_rate:.1f} % · "
                                  f"охоплення хибних: {kpi.false_reach / 1e6:.2f} млн · середній час: {kpi.avg_hours_to_verdict:.1f} год · SLA: {kpi.sla_compliance_rate:.1f} %", font=dict(size=14)))
html = fig.to_html(include_plotlyjs=True, full_html=False)
notes = "".join(f"<li><b>{TXT[k][0]}</b> — {TXT[k][1]}</li>" for k in TXT)
(OUT / "dashboard.html").write_text(f"""<!doctype html><html lang="uk"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Панель фактчекінгу</title><style>body{{font-family:'DejaVu Sans',Arial,sans-serif;margin:16px;background:#fcfcfb;color:#0b0b0b}}li{{margin:6px 0}}</style></head>
<body><h2>Аналітична панель ЛР12 · куб «Перевірка публікацій»</h2>{html}<h3>Інтерпретації</h3><ol>{notes}</ol>
<p style="color:#52514e">Дані синтетичні (etl/generate.py, seed 12); метрики — semantic/metrics.yml.</p></body></html>""", encoding="utf-8")
print("dashboard written", kpi.to_dict())
