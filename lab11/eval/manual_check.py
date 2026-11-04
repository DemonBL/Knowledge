"""ЛР11 · ручна перевірка ≥10 вердиктів судді (faithfulness) і Cohen's κ."""
import json
from pathlib import Path
LAB = Path(__file__).resolve().parents[1]
from sklearn.metrics import cohen_kappa_score
R = json.load(open(LAB / 'results' / 'lab11_results.json', encoding='utf-8'))
J = {('b', r['id']): r for r in R['eval']['baseline_k5']['rows'] if 'judge_faithful' in r}
J.update({('o', r['id']): r for r in R['eval']['opt_k3']['rows'] if r['id'] in ('T15', 'T27')})
H = {  # ручна оцінка: 1 — усі твердження відповіді підтверджені контекстом
 ('b','T01'):(1,'дата є у W14:s001'), ('b','T02'):(1,'вірно; суддя додав твердження з контексту, а не з відповіді'),
 ('b','T03'):(1,'TensorFlow є у W06:s004'), ('b','T04'):(1,'дослівно W26:s001; 2-ге «твердження» судді взято з контексту'),
 ('b','T05'):(1,'перефраз W13:s001/s009/s010'), ('b','T06'):(1,'W05:s002'), ('b','T07'):(1,'W07:s000'),
 ('b','T08'):(1,'W15:s001'), ('b','T09'):(1,'перефраз W10:s000, стилістично неточно'), ('b','T10'):(1,'W14:s005, W19:s000'),
 ('b','T11'):(0,'«психологічні тактики, соціальна інформація» в контексті немає; суддя розклав контекст замість відповіді'),
 ('b','T12'):(1,'зміст є в графі; але цитата [G:OFF-03] не про першоджерело'), ('b','T13'):(1,'вердикт і Ф-04 є в рядку [G:VRD-10]'),
 ('b','T14'):(0,'правило названо «R1–R4» (це назва каталогу); дію «позначити як повторно використаний» спотворено'),
 ('b','T15'):(0,'«14 публікацій» — немає в контексті (4+3+6=13, а насправді 17)'),
 ('b','T24'):(1,'INT-REG-2026:s001'), ('b','T25'):(1,'INT-REG-2026:s002'), ('b','T26'):(1,'INT-REG-2026:s001'),
 ('b','T27'):(1,'обидві версії регламенту в контексті'),
 ('o','T15'):(0,'«13 публікацій» — арифметика з 3 тверджень, правильне число 17 не в контексті'),
 ('o','T27'):(1,'«один доказ» є в INT-REG-2025:s001 — суддя помилився'),
}
items = []
for k, (h, c) in H.items():
    items.append({'id': ('baseline ' if k[0]=='b' else 'k=3 ') + k[1], 'judge': int(J[k]['judge_faithful']), 'human': h, 'comment': c})
j = [x['judge'] for x in items]; h = [x['human'] for x in items]
mc = {'n': len(items), 'agreement': sum(a == b for a, b in zip(j, h)) / len(items), 'kappa': cohen_kappa_score(j, h),
      'judge_pos': sum(j), 'human_pos': sum(h),
      'human_faithful_share_baseline': sum(x['human'] for x in items if x['id'].startswith('baseline')) / sum(1 for x in items if x['id'].startswith('baseline')),
      'judge_decomposed_context': ['T02','T04','T11','T24','T26'],
      'reviewer': 'LLM-експерт Claude (claude-opus-5-5) за контекстом із logs/rag_log.jsonl; потребує підтвердження студентом',
      'items': items}
json.dump(mc, open(LAB / 'eval' / 'manual_check.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
print({k: v for k, v in mc.items() if k != 'items'})
