"""Whitepaper · рисунок метрик якості ЛР9–ЛР15 «до → після» (значення — зі звітів і results/ відповідних ЛР; джерела в підписах)."""
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

OUT = Path(__file__).resolve().parents[1] / "docs" / "img" / "wp_labs.png"
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 8.5, "axes.spines.top": False, "axes.spines.right": False})

# (метрика, ЛР, «до», «після», підпис до, підпис після)
ROWS = [
    ("recall@5 пошуку", "ЛР10", 0.722, 0.847, "BM25", "гібрид+reranker"),
    ("F1 відношень (test)", "ЛР13", 0.163, 0.811, "LLM 7B", "правила spaCy"),
    ("пороги якості (з 15)", "ЛР14", 3 / 15, 11 / 15, "baseline", "після очищення"),
    ("ER: F1 на test", "ЛР14", 0.780, 0.884, "поріг", "+LLM-суддя"),
    ("успішність агента", "ЛР15", 0.417, 0.75, "v1", "v3.1"),
    ("атаки без успіху", "ЛР15", 11 / 13, 13 / 13, "без захисту", "6 шарів"),
    ("правильні SQL (Text-to-SQL)", "ЛР12", 0.667, 0.75, "автоматична оцінка", "ручна оцінка"),
    ("nDCG@10 рекомендацій", "ЛР16", None, None, "популярність", "гібрид RRF"),
]


def make(nd_before, nd_after):
    rows = [r if r[2] is not None else (r[0], r[1], nd_before, nd_after, r[4], r[5]) for r in ROWS]
    fig, ax = plt.subplots(figsize=(7.4, 3.6), dpi=200)
    for i, (m, lab, a, b, la, lb) in enumerate(rows):
        y = len(rows) - 1 - i
        ax.plot([a, b], [y, y], color="#c9c8c2", lw=2.2, zorder=1)
        ax.scatter([a], [y], s=36, color="#a3a29c", zorder=2)
        ax.scatter([b], [y], s=36, color="#2a78d6", zorder=3)
        ax.annotate(f"{la} " + f"{a:.2f}".replace(".", ","), (a, y), xytext=(0, 6), textcoords="offset points", ha="center", fontsize=6.5, color="#52514e")
        ax.annotate(f"{lb} " + f"{b:.2f}".replace(".", ","), (b, y), xytext=(0, -11), textcoords="offset points", ha="center", fontsize=6.5, color="#1f5fae")
    ax.set_yticks(range(len(rows)), [f"{r[1]} · {r[0]}" for r in reversed(rows)])
    ax.set_xlim(0, 1.05)
    ax.set_ylim(-0.7, len(rows) - 0.4)
    ax.set_xlabel("значення метрики (частка)")
    ax.grid(axis="x", color="#eeeeee", lw=0.6)
    ax.set_title("Якість Hub по етапах: сірим — базовий варіант, синім — обраний", fontsize=9)
    fig.tight_layout()
    fig.savefig(OUT)
    plt.close(fig)


if __name__ == "__main__":
    make(0.054, 0.165)
