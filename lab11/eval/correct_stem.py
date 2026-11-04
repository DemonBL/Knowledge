"""ЛР11 · виправлена метрика правильності: основи слів (5 літер) + число як окремий токен (не частина CLM-17)."""
import json, re
from pathlib import Path
LAB = Path(__file__).resolve().parents[1]
R = json.load(open(LAB / 'results' / 'lab11_results.json', encoding='utf-8'))
E = {json.loads(l)['id']: json.loads(l) for l in open(LAB / 'eval' / 'rag_eval.jsonl', encoding='utf-8')}
def toks(s): return re.findall(r"[\w'’-]+", s.lower().replace('’', "'"))
def fact_in(f, ans):
    if re.fullmatch(r"\d+", f):   # число: окремий токен, не частина CLM-17
        return re.search(rf"(?<![\w-]){f}(?![\w-])", ans) is not None
    ft, at = toks(f), toks(ans)
    st = lambda w: w[:5] if len(w) > 5 else w
    return all(any(a.startswith(st(w)) for a in at) for w in ft)
out = {}
for tag in ('baseline_k5', 'opt_k3'):
    rows = R['eval'][tag]['rows']
    A = [r for r in rows if r['category'] == 'answerable']
    stem = {r['id']: all(fact_in(f, r['answer']) for f in E[r['id']]['key_facts']) for r in A}
    out[tag] = {'answer_correct_stem': round(sum(stem.values()) / len(A), 3),
                'changed': {k: [bool(next(x for x in A if x['id'] == k).get('correct')), v] for k, v in stem.items()
                            if v != bool(next(x for x in A if x['id'] == k).get('correct'))}}
print(json.dumps(out, ensure_ascii=False))
json.dump(out, open(LAB / 'results' / 'correct_stem.json', 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
