# Порівняння embeddings (20 запитів, HNSW M=32, efC=200, efS=64)

| модель | dim | побудова, с | recall@5 | MRR | пошук мед., мс | p95, мс |
|---|---|---|---|---|---|---|
| intfloat/multilingual-e5-small | 384 | 31.31 | 0.8 | 0.758 | 33.6 | 81.5 |
| sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 | 384 | 29.46 | 0.85 | 0.68 | 46.7 | 123.0 |