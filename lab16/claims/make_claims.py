"""ЛР16 · таблиця тверджень (claims.csv) з числами, взятими з results/*.json (щоб твердження не розходились із прогонами)."""
import csv
import json
from pathlib import Path

LAB = Path(__file__).resolve().parents[1]
R = lambda f: json.loads((LAB / f).read_text(encoding="utf-8")) if (LAB / f).exists() else None  # noqa: E731
n = lambda x, d=3: f"{x:.{d}f}".replace(".", ",")  # noqa: E731

E5, LSA = R("results/reco_eval_e5.json"), R("results/reco_eval_lsa.json")
EV = E5 or LSA
S = EV["summary"]
emb = EV["emb"]
CS = R(f"results/cold_start_{emb}.json")
A, B = CS["new_user"]["summary"], CS["new_doc"]["summary"]
EX = R("results/explanations.json")["summary"]
PA = R(f"results/paired_{emb}.json")
DR = R("results/docker_run.json") or {}
DEMO = R("demo/demo_run.json")
m = lambda c, k: f"{n(S[c][k]['mean'])} ± {n(S[c][k]['sd'])}"  # noqa: E731

rows = [
    ("C01", f"Гібрид RRF підвищує nDCG@10 з {m('popularity', 'ndcg10')} (популярність) до {m('hybrid_rrf', 'ndcg10')} (e5, 5 seed)", "факт", f"results/reco_eval_{emb}.json", "V4", "verified", "часове розбиття; синтетичні журнали"),
    ("C02", f"Зважений гібрид ({m('hybrid_weighted', 'ndcg10')}) і RRF статистично не розрізняються: різниця nDCG@10 {n(PA['mean_diff_a_minus_b'])}, 95 % CI [{n(PA['ci95'][0])}; {n(PA['ci95'][1])}]" if PA else "Зважений гібрид і RRF рівні в межах sd", "факт", f"results/paired_{emb}.json", "V4", "verified", f"перемоги за seed: {PA['seed_wins'] if PA else '—'}"),
    ("C03", "Оптимальні ваги зваженого гібриду нестабільні між seed: " + "; ".join(str(tuple(r['w_best'])) for r in EV["runs"]), "факт", f"results/reco_eval_{emb}.json", "V4", "verified", "аргумент на користь RRF без навчуваних ваг"),
    ("C04", f"Графовий метод сам по собі дає nDCG@10 {m('graph', 'ndcg10')} і найвище покриття {m('graph', 'coverage10')}", "факт", f"results/reco_eval_{emb}.json", "V4", "verified", "частково завдяки NEXT_SECTION, якому підіграє генератор"),
    ("C05", "Додавання ребер NEXT_SECTION підняло nDCG@10 графового методу з 0,050 до 0,095 (seed 16, LSA)", "факт", "llm_log/claude_expert.md (№3), results/reco_eval_lsa.json", "V3", "verified", "до/після на тому самому seed"),
    ("C06", f"Гіпотеза: e5 помітно (≥ 0,02 nDCG@10) краща за LSA як ембединги рекомендацій — ембединги e5 {n(S['embeddings']['ndcg10']['mean'])} проти LSA {n(LSA['summary']['embeddings']['ndcg10']['mean'])}", "гіпотеза", "results/reco_eval_e5.json, reco_eval_lsa.json", "V4", "rejected", "різниця ≈ 0,005, менша за sd; тексти короткі, каталог малий"),
    ("C07", f"Популярність має найнижчу новизну ({n(S['popularity']['novelty10']['mean'], 2)} біт) і покриття ({n(S['popularity']['coverage10']['mean'])})", "факт", f"results/reco_eval_{emb}.json", "V4", "verified", "ризик бульбашки"),
    ("C08", "Оцінка без витоку з майбутнього: ваги підбираються на validation (до 2026-10-20), фінальна модель бачить лише події до межі test", "метод", "reco/eval.py", "V2", "verified", "перевірено кодом split/targets"),
    ("C09", f"Шаблонні пояснення проходять автоматичну перевірку сутностей у {n(EX['template_correct'], 2)} випадків ({EX['n']} рекомендацій)", "факт", "results/explanations.json", "V4", "verified", "перевірка: сутності реєстру, id, цитати ⊆ шлях"),
    ("C10", f"Перефразування qwen2.5:7b проходить перевірку v2 у {n(EX['llm_correct'], 2)} випадків; строга v1 давала {n(EX['llm_correct_strict'], 2)} через хибні відмови на відмінкових формах назв", "факт", "results/explanations.json, llm_log/explain_llm.jsonl", "V4", "verified", "повторна перевірка тих самих текстів, без нових викликів LLM; мовні вади («Аналітикі») перевірка не ловить"),
    ("C11", f"Перевірка v2 виявляє вставлену сторонню сутність або назву документа в {EX['negative_control']['caught']} з {EX['negative_control']['injected']} текстів", "факт", "results/explanations.json (negative_control)", "V4", "verified", "синтетичні ін'єкції; перефразовані хибні зв'язки без нових назв не ловляться"),
    ("C12", f"Новий користувач: онбординг за темами дає nDCG@10 {n(A['onboard_hybrid']['ndcg10']['mean'])} проти {n(A['pop_global']['ndcg10']['mean'])} у загальної популярності", "факт", f"results/cold_start_{emb}.json", "V4", "verified", ""),
    ("C13", f"Гіпотеза: гібрид від обраних тем кращий за популярність у межах тем — {n(A['onboard_hybrid']['ndcg10']['mean'])} проти {n(A['pop_topic']['ndcg10']['mean'])}", "гіпотеза", f"results/cold_start_{emb}.json", "V4", "rejected", "генератор обирає документи за темами — сценарій підіграє популярності в темах; гібрид дає більше покриття"),
    ("C14", f"Після 3 взаємодій nDCG@10 зростає до {n(A['warm3']['ndcg10']['mean'])}", "факт", f"results/cold_start_{emb}.json", "V4", "verified", "оцінка на решті test-взаємодій"),
    ("C15", f"Новий документ: RRF показує нові фрагменти рідко (exposure {n(B['hybrid_rrf']['exposure_new']['mean'])}), 2 слоти підвищують exposure до {n(B['hybrid_rrf+new_slot2']['exposure_new']['mean'])}", "факт", f"results/cold_start_{emb}.json", "V4", "verified", f"hit@10 лишається низьким ({n(B['hybrid_rrf+new_slot2']['hit10_new']['mean'])})"),
    ("C16", "Фільтри доступу застосовуються до ранжування: гість із заявленою роллю admin отримує лише public", "факт", "demo/demo_run.json (крок 4b), results/filters_demo.json", "V4" if DEMO else "V3", "verified", ""),
    ("C17", "Фільтр чинності прибирає замінений регламент INT-REG-2025, який інакше стає першою рекомендацією", "факт", "results/filters_demo.json", "V4", "verified", ""),
    ("C18", (f"Демонстратор запускається з нуля однією командою; збірка {n(DR['build_s'] / 60, 1)} хв, автоматичний сценарій: {DEMO['passed']}" if DR.get("build_s") is not None and DEMO else "Демонстратор запускається однією командою docker compose up"), "факт", "results/docker_run.json, logs/compose.log, demo/demo_run.md", "V4" if DR.get("build_s") is not None else "V2", "verified" if DR.get("build_s") is not None else "pending", ""),
    ("C19", "Hub не є високоризиковою системою за Додатком III AI Act; діють ст. 50 (прозорість) і ст. 4", "оцінка", "Регламент (ЄС) 2024/1689, 2026/1744; docs/whitepaper.pdf §5", "V1", "pending", "юридичну оцінку не проводили; переглянути при використанні органом влади"),
    ("C20", "Синтетичні журнали — головна загроза зовнішній валідності метрик рекомендацій", "оцінка", "docs/reco_design.md, обмеження 1", "V1", "verified", "потрібен пілот і A/B-тест"),
]
with open(LAB / "claims" / "claims.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.writer(f)
    w.writerow(["id", "claim", "type", "source", "verification_level", "status", "comment"])
    w.writerows(rows)
print(len(rows))
