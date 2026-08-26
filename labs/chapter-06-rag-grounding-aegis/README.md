# Chapter 6 — RAG: Grounding Aegis in Your Runbooks

Notebook: `Aegis_Chapter6_Lab.ipynb` — it adds this folder to `sys.path` and imports
the modules below. The notebook is a guidebook: RAG from first principles through
the advanced techniques, all offline and deterministic.

| File | What it is |
|---|---|
| `data/corpus.py` | Three runbooks, two CVE advisories, `METADATA`, and a `GOLDEN_SET` |
| `rag/pipeline.py` | Chunkers (`fixed`, `sentence-window`, `semantic`, `hierarchical`, `chunk_by_step`), `embed`/`cosine`, `VectorIndex` with metadata filtering, `evaluate_strategies` |
| `rag/hybrid.py` | `rewrite_query`, `multi_query`, `make_semantic_embed`, `HybridRetriever` (dense + BM25, alpha fusion and RRF) |
| `rag/advanced.py` | `rerank` (cross-encoder stand-in), `ParentChildIndex`, `grounded_answer` + `grounding_check`, `hit_rate` / `mrr` |
| `rag/vectorstore.py` | Real Chroma: persistent collection, explicit vectors, metadata `where` filters |
| `demo.py` | Smoke test across every section; CI runs it |

Run from the repo root: `python labs/chapter-06-rag-grounding-aegis/demo.py`
