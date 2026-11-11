# ЛР 10 · Векторне сховище та семантичний пошук

    run_lab10.bat   # корпус (Вікіпедія + kb_internal) → gold → chunking → embeddings → upsert/delete → гібрид + оцінювання
    run_kappa.bat   # другий розмітник (gemma3:4b) і Cohen's κ

Артефакти: data/corpus.jsonl, data/docs.jsonl, src/chunking.py, src/search_core.py (індекс, BM25, RRF, reranker, пре-фільтр),
eval/gold.jsonl, eval/annot_*.jsonl, results/lab10_results.json, results/kappa.json, docs/*.md, claims/claims.csv.
