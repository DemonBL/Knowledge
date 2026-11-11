"""ЛР16 · рисунки й таблиці з результатів (results/*.json) → docs/img/*.png, docs/reco_eval.md, docs/cold_start.md.
Береться e5, якщо є results/reco_eval_e5.json (прогін на ПК), інакше LSA; LSA показується як порівняння.
  python reco/make_docs.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

LAB = Path(__file__).resolve().parents[1]
RES, IMG, DOCS = LAB / "results", LAB / "docs" / "img", LAB / "docs"
IMG.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "axes.spines.top": False, "axes.spines.right": False})
GRID = dict(axis="y", color="#e5e5e5", linewidth=0.6)
NAMES = {"popularity": "популярність (baseline)", "graph": "графовий (шляхи)", "embeddings": "ембединги (kNN)",
         "hybrid_weighted": "гібрид зважений", "hybrid_rrf": "гібрид RRF"}
COL = {"popularity": "#a3a29c", "graph": "#2a78d6", "embeddings": "#eb6834", "hybrid_weighted": "#1baf7a", "hybrid_rrf": "#6250d6"}
MET = {"p5": "P@5", "r5": "R@5", "ndcg10": "nDCG@10", "coverage10": "coverage@10", "novelty10": "novelty@10, біт"}


def load(name):
    p = RES / name
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


def f3(x):
    return f"{x:.3f}".replace(".", ",")


def main():
    E5, LSA = load("reco_eval_e5.json"), load("reco_eval_lsa.json")
    main_ = E5 or LSA
    emb = main_["emb"]
    S = main_["summary"]
    cfgs = list(S)
    # --- рис. 1: точність (середнє ± sd за 5 seed)
    fig, ax = plt.subplots(figsize=(7.4, 3.3), dpi=200)
    ms = ["p5", "r5", "ndcg10"]
    w = 0.16
    for j, c in enumerate(cfgs):
        xs = np.arange(len(ms)) + (j - 2) * w
        mu = [S[c][m]["mean"] for m in ms]
        sd = [S[c][m]["sd"] for m in ms]
        ax.bar(xs, mu, w * 0.92, yerr=sd, color=COL[c], label=NAMES[c], error_kw=dict(lw=0.8, capsize=2, ecolor="#555"))
    ax.set_xticks(range(len(ms)), [MET[m] for m in ms])
    ax.grid(**GRID)
    ax.set_axisbelow(True)
    ax.set_ylabel("значення (середнє ± sd, 5 seed)")
    ax.legend(ncol=3, fontsize=7.5, frameon=False, loc="upper left")
    ax.set_title(f"Офлайн-оцінка на test (часове розбиття), ембединги {emb}", fontsize=9.5)
    fig.tight_layout()
    fig.savefig(IMG / "reco_accuracy.png")
    plt.close(fig)
    # --- рис. 2: точність vs покриття
    fig, ax = plt.subplots(figsize=(5.6, 3.4), dpi=200)
    for c in cfgs:
        x, y = S[c]["coverage10"]["mean"], S[c]["ndcg10"]["mean"]
        ax.errorbar(x, y, xerr=S[c]["coverage10"]["sd"], yerr=S[c]["ndcg10"]["sd"], fmt="o", ms=7, color=COL[c], ecolor="#999", lw=0.8, capsize=2)
        off = {"hybrid_weighted": (-70, 8), "hybrid_rrf": (6, -12)}.get(c, (6, 4))
        ax.annotate(NAMES[c], (x, y), xytext=off, textcoords="offset points", fontsize=7.5)
    ax.set_xlabel("coverage@10 (частка доступного каталогу)")
    ax.set_ylabel("nDCG@10")
    ax.grid(color="#eeeeee", linewidth=0.6)
    ax.set_title("Компроміс точності й покриття", fontsize=9.5)
    fig.tight_layout()
    fig.savefig(IMG / "reco_tradeoff.png")
    plt.close(fig)
    # --- рис. 3: nDCG за seed
    fig, ax = plt.subplots(figsize=(5.6, 3.0), dpi=200)
    seeds = [r["seed"] for r in main_["runs"]]
    for c in cfgs:
        ax.plot(seeds, [r["configs"][c]["agg"]["ndcg10"] for r in main_["runs"]], marker="o", ms=4, lw=1.6, color=COL[c], label=NAMES[c])
    ax.set_xticks(seeds)
    ax.set_xlabel("seed генератора взаємодій")
    ax.set_ylabel("nDCG@10")
    ax.grid(**GRID)
    ax.legend(fontsize=7, frameon=False, ncol=2)
    ax.set_title("Стійкість висновку між повторами", fontsize=9.5)
    fig.tight_layout()
    fig.savefig(IMG / "reco_seeds.png")
    plt.close(fig)
    # --- холодний старт
    CS = load(f"cold_start_{emb}.json") or load("cold_start_lsa.json")
    A, B = CS["new_user"]["summary"], CS["new_doc"]["summary"]
    an = {"pop_global": "популярність\nзагальна", "pop_topic": "популярність\nу темах", "onboard_hybrid": "гібрид RRF\nвід тем", "warm3": "гібрид після\n3 взаємодій"}
    bn = {"popularity": "популярність", "graph": "графовий", "embeddings": "ембединги", "hybrid_rrf": "гібрид RRF", "hybrid_rrf+new_slot2": "гібрид RRF\n+2 слоти нових"}
    fig, axs = plt.subplots(1, 2, figsize=(8.2, 3.1), dpi=200)
    xs = np.arange(len(A))
    axs[0].bar(xs, [A[c]["ndcg10"]["mean"] for c in A], 0.6, yerr=[A[c]["ndcg10"]["sd"] for c in A], color="#2a78d6",
               error_kw=dict(lw=0.8, capsize=2, ecolor="#555"))
    axs[0].set_xticks(xs, [an[c] for c in A], fontsize=7)
    axs[0].set_ylabel("nDCG@10")
    axs[0].set_title("A. Новий користувач", fontsize=9)
    xs = np.arange(len(B))
    axs[1].bar(xs - 0.18, [B[c]["exposure_new"]["mean"] for c in B], 0.36, color="#1baf7a", label="exposure нових фрагментів")
    axs[1].bar(xs + 0.18, [B[c]["hit10_new"]["mean"] for c in B], 0.36, color="#eb6834", label="hit@10 нових фрагментів")
    axs[1].set_xticks(xs, [bn[c] for c in B], fontsize=7)
    axs[1].set_title("B. Новий документ", fontsize=9)
    axs[1].legend(fontsize=7, frameon=False)
    for a in axs:
        a.grid(**GRID)
        a.set_axisbelow(True)
    fig.tight_layout()
    fig.savefig(IMG / "cold_start.png")
    plt.close(fig)

    # --- docs/reco_eval.md
    L = [f"# Офлайн-оцінка рекомендацій (ЛР16, Р2)", "",
         "Згенеровано `reco/make_docs.py` з `results/reco_eval_*.json`. Прогін: `python reco/eval.py --emb e5|lsa` (5 seed генератора 16–20).", "",
         "## Протокол", "",
         "- **Дані:** синтетичні журнали 60 користувачів (4 admin, 42 analyst, 14 guest) за 2026-08-01…11-07, події view/cite; генератор (`reco/data_gen.py`) знає лише теми документів, не граф і не ембединги.",
         "- **Часове розбиття без витоку:** `train_fit < 2026-10-06 ≤ validation < 2026-10-20 ≤ test`. Ваги гібриду підбираються на validation моделлю, навченою лише на train_fit; фінальна модель навчається на всьому до 2026-10-20 і оцінюється на test.",
         "- Популярність, профілі і згасання (період напіврозпаду 21 день) рахуються від моменту межі; документи, створені після межі, у train не потрапляють і для генератора недоступні до своєї дати.",
         "- **Релевантні** = фрагменти, які користувач відкрив у test і не відкривав у train; рекомендуються лише не бачені й дозволені роллю (фільтри RBAC, перевіреність, чинність).",
         "- **Метрики:** P@5, R@5, nDCG@10 (середнє за користувачами), coverage@10 (частка доступного каталогу в усіх топ-10), novelty@10 (−log₂ популярності, біти).",
         "- **Невизначеність:** 95 % бутстреп-інтервали (1000 повторів за користувачами) для кожного seed і середнє ± sd за 5 seed.", ""]
    for E in [x for x in (E5, LSA) if x]:
        L += [f"## Результати: ембединги {E['emb']}", "", "| Конфігурація | " + " | ".join(MET.values()) + " |", "|---|" + "---|" * len(MET)]
        for c, v in E["summary"].items():
            L.append(f"| {NAMES[c]} | " + " | ".join(f"{f3(v[m]['mean'])} ± {f3(v[m]['sd'])}" for m in MET) + " |")
        r0 = E["runs"][0]
        L += ["", f"Seed {r0['seed']}: train {r0['train']}, test {r0['test']} взаємодій, користувачів у test {r0['test_users']}; "
              f"95 % бутстреп-інтервали nDCG@10:", ""]
        L += [f"- {NAMES[c]}: {f3(r0['configs'][c]['agg']['ndcg10'])} [{f3(r0['configs'][c]['ci95']['ndcg10'][0])}; {f3(r0['configs'][c]['ci95']['ndcg10'][1])}]"
              for c in r0["configs"]]
        L += ["", "Ваги зваженого гібриду (граф, ембединги, популярність), підібрані на validation: " +
              "; ".join(f"seed {r['seed']}: {tuple(r['w_best'])}" for r in E["runs"]), ""]
    PA = load(f"paired_{emb}.json")
    if PA:
        hw, rr = S["hybrid_weighted"], S["hybrid_rrf"]
        L += ["## Вибір кращої конфігурації", "",
              f"Обидва гібриди кращі за кожен окремий метод і приблизно втричі кращі за популярність. За середнім nDCG@10 зважений гібрид трохи вищий ({f3(hw['ndcg10']['mean'])} проти {f3(rr['ndcg10']['mean'])}).",
              "",
              f"Парний тест на тих самих {PA['n_user_pairs']} парах «користувач × seed» (`results/paired_{emb}.json`, бутстреп 2000) дає різницю {f3(PA['mean_diff_a_minus_b'])}, 95 % CI [{f3(PA['ci95'][0])}; {f3(PA['ci95'][1])}]. Інтервал містить нуль. За seed перемоги: {PA['seed_wins']}.",
              "", "**Обрано гібрид RRF**, бо:",
              "- точність у межах похибки та сама, розкид між seed менший (sd " + f3(rr['ndcg10']['sd']) + " проти " + f3(hw['ndcg10']['sd']) + ");",
              "- немає навчуваних ваг: оптимальні ваги зваженого гібриду нестабільні між seed (див. вище), тож їх підбір на невеликій validation переналаштовується;",
              "- покриття каталогу стабільніше (sd " + f3(rr['coverage10']['sd']) + " проти " + f3(hw['coverage10']['sd']) + ");",
              "- RRF не залежить від шкал балів, тому додавання нового джерела сигналу не потребує перенастроювання.",
              "", "Зважений гібрид лишається варіантом, якщо з'являться реальні журнали й більша validation.", ""]
    L += ["![Точність](img/reco_accuracy.png)", "", "![Компроміс](img/reco_tradeoff.png)", "", "![Seed](img/reco_seeds.png)", ""]
    (DOCS / "reco_eval.md").write_text("\n".join(L), encoding="utf-8")

    # --- docs/cold_start_results.md (таблиці для cold_start.md)
    L = ["| Сценарій A: конфігурація | P@5 | R@5 | nDCG@10 | coverage@10 |", "|---|---|---|---|---|"]
    for c, v in A.items():
        L.append(f"| {an[c].replace(chr(10), ' ')} | " + " | ".join(f"{f3(v[m]['mean'])} ± {f3(v[m]['sd'])}" for m in ("p5", "r5", "ndcg10", "coverage10")) + " |")
    L += ["", "| Сценарій B: конфігурація | hit@10 нових | exposure нових |", "|---|---|---|"]
    for c, v in B.items():
        L.append(f"| {bn[c].replace(chr(10), ' ')} | {f3(v['hit10_new']['mean'])} ± {f3(v['hit10_new']['sd'])} | {f3(v['exposure_new']['mean'])} ± {f3(v['exposure_new']['sd'])} |")
    intro = ["# Холодний старт (ЛР16, Р3)", "", f"Код — `reco/cold_start.py`, результати — `results/cold_start_{emb}.json`. 5 seed генератора, ембединги {emb}.", "",
             "## Сценарій A — новий користувач", "",
             "**Постановка:**",
             "- користувачів тестового періоду «обнуляємо»: їхні події до 2026-10-20 прибрано (популярність рахується за іншими користувачами);",
             "- на онбордингу користувач обирає теми зі списку `GET /topics` (9 тем); у синтетиці — заявлені теми з `data/users.csv`.", "",
             "**Методи:**",
             "- `pop_global` — загальна популярність;",
             "- `pop_topic` — популярність у межах обраних тем;",
             "- `onboard_hybrid` — сіди = фрагменти документів обраних тем з вагою 1/кількість, далі гібрид RRF (граф + ембединги + популярність);",
             "- `warm3` — той самий гібрид після перших 3 взаємодій у test, оцінка на решті.", "",
             "## Сценарій B — новий документ", "",
             "**Постановка:**",
             "- 6 публічних документів (" + ", ".join(CS["new_docs"]) + ") вважаємо «щойно доданими»: усі взаємодії з ними видалено з train, популярність нульова;",
             "- hit@10 — частка нових фрагментів, які користувач відкрив у test і які потрапили в його топ-10;",
             "- exposure — частка нових фрагментів, показаних хоча б одному користувачеві.", "",
             "**Методи:**",
             "- RRF «топить» нові фрагменти, бо в списку популярності вони останні;",
             "- тому додано `new_slots`: до 2 останніх позицій топ-10 віддаються найкращим за змістом (граф + ембединги) фрагментам, доданим ≤ 30 днів тому без жодної взаємодії.", "",
             "## Результати", ""]
    concl = ["", "![Холодний старт](img/cold_start.png)", "", "## Висновки", "",
             f"- Новому користувачеві вибір тем дає nDCG@10 {f3(A['onboard_hybrid']['ndcg10']['mean'])} проти {f3(A['pop_global']['ndcg10']['mean'])} у загальної популярності; після 3 взаємодій — {f3(A['warm3']['ndcg10']['mean'])}.",
             f"- Популярність у межах тем ({f3(A['pop_topic']['ndcg10']['mean'])}) не гірша за гібрид, бо синтетичний генератор обирає документи саме за темами. Гібрид дає більше покриття ({f3(A['onboard_hybrid']['coverage10']['mean'])} проти {f3(A['pop_topic']['coverage10']['mean'])}) і пояснення зі шляху. У продукті для нового користувача доцільно змішувати обидва.",
             f"- Новий документ: популярність його не бачить зовсім, RRF — майже ні (exposure {f3(B['hybrid_rrf']['exposure_new']['mean'])}). Два слоти підвищують exposure до {f3(B['hybrid_rrf+new_slot2']['exposure_new']['mean'])} і hit@10 до {f3(B['hybrid_rrf+new_slot2']['hit10_new']['mean'])} ціною двох позицій топу. Чисті ембединги мають найвищий hit@10 ({f3(B['embeddings']['hit10_new']['mean'])}).",
             "- Обмеження: hit@10 нових фрагментів низький, бо сценарій суворий (нових фрагментів мало серед test-переглядів).", ""]
    (DOCS / "cold_start.md").write_text("\n".join(intro + L + concl), encoding="utf-8")
    # --- docs/explanations.md
    EX = load("explanations.json")
    if EX:
        es = EX["summary"]
        L = ["# Пояснення рекомендацій (ЛР16, Р3)", "", "Код — `reco/explain.py`, результати — `results/explanations.json`, сирі виходи LLM — `llm_log/explain_llm.jsonl`.", "",
             "## Як будується пояснення", "",
             "1. Графовий метод для кожного кандидата зберігає найкращий шлях: переглянутий фрагмент → (сусідній розділ | спільна сутність | документ | ребро графа ЛР9) → рекомендований фрагмент.",
             "2. **Шаблон** формує речення лише з вузлів шляху — це пояснення, яке показує демонстратор.",
             "3. **LLM** (qwen2.5:7b, temperature 0) лише перефразовує шаблон. У підказці — перелік дозволених назв зі шляху й заборона нових фактів, чисел, організацій, дат.",
             "4. **Автоматична перевірка** (`check`) шукає в тексті сутності реєстру ЛР14 (за основами назв), id графа (CLM/NAR/…), id фрагментів і цитати «…». Усе знайдене має належати шляху, і має бути згаданий хоча б один проміжний вузол.", "",
             "## Результати", "",
             f"- рекомендацій: {es['n']} (10 користувачів × топ-3, гібрид RRF, e5);",
             f"- шаблони пройшли перевірку: {f3(es['template_correct'])};"]
        if es.get("llm_correct") is not None:
            L += [f"- перефразування LLM, перевірка v1 (строга, точний підрядок): {f3(es['llm_correct_strict'])};",
                  f"- перефразування LLM, перевірка v2 (цитати за основами слів): {f3(es['llm_correct'])};",
                  f"- негативний контроль: у кожне пояснення вставлено сторонню сутність або назву документа поза шляхом ({es['negative_control']['injected']} текстів) — перевірка v2 виявила {es['negative_control']['caught']} ({f3(es['negative_control']['detection_rate'])});",
                  f"- середня затримка перефразування: {sum(r.get('llm_latency_s', 0) for r in EX['rows']) / len(EX['rows']):.1f} с (CPU).".replace(".", ",", 1), "",
                  "**Розбір.** v1 відхилила 10 з 30 текстів. З них 9 — хибні відмови: LLM відмінює назви («з «Дезінформацією щодо пандемії COVID-19»»), а строга перевірка шукала точний підрядок. Перевірку виправлено (v2) і повторно застосовано до тих самих збережених текстів, без нових викликів моделі. Щоб v2 не стала надто поблажливою, додано негативний контроль.",
                  "", "Залишкова справжня помилка — 1 текст, у якому модель не назвала жодного проміжного вузла: зв'язок «чому» втрачено.",
                  "", "**Мовні вади, які перевірка сутностей не ловить:**",
                  "- звертання «Аналітикі» (неправильний кличний відмінок) у більшості текстів;",
                  "- одне англійське слово посеред речення («від looked at»).",
                  "", "Тому демонстратор показує шаблонне пояснення, а перефразування — лише опція після перевірки.", ""]
        L += ["## П'ять прикладів", "", "| Користувач → фрагмент | Шлях графа | Пояснення (LLM, якщо є) | Перевірка |", "|---|---|---|---|"]
        rows = EX["rows"]
        pick = [r for r in rows if not r.get("llm_ok", True)][:1]
        for ln in (4, 3, 2):
            pick += [r for r in rows if len(r["path"]) == ln and r not in pick][:2]
        for r in pick[:5]:
            t = (r.get("llm_text") or r["template"]).replace("|", "/")
            L.append(f"| {r['user']} → {r['item']} | {' → '.join(r['path_labels'])} | {t} | {'✓' if r.get('llm_ok', r['template_ok']) else '✗ ' + '; '.join(r.get('llm_problems', []))} |")
        (DOCS / "explanations.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("ok", emb)


if __name__ == "__main__":
    main()
