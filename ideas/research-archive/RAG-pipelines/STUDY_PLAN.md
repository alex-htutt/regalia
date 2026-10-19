# RAG Pipelines — Study Plan

Started: 2026-06-10. One session ≈ 1 chapter + 30–60 min building in `basic_execution/`.
Chapters live in `resources/ai-system-design-guide-main/06-retrieval-systems/` unless noted.

## Phase 1 — Foundations (days 1–2)

- [ ] **Day 1**: `01-foundations/01-llm-internals.md` (skim — just enough to know why embeddings work). Build: `pip install -r requirements.txt`, run `pipeline.py ingest` and `ask` once, read through each file.
- [ ] **Day 2**: `06-retrieval-systems/01-rag-fundamentals.md`. Build: trace one question end-to-end; read the assembled prompt `ask` prints and understand every piece.

## Phase 2 — Core pipeline (days 3–8)

- [ ] **Day 3**: `02-chunking-strategies.md`. Build: compare `chunk_text` vs `chunk_by_paragraph` — reset, re-ingest, run `evaluate.py` for both.
- [ ] **Day 4**: `03-embedding-models.md`. Build: swap MiniLM for `BAAI/bge-small-en-v1.5` in `embedder.py`; compare recall@k.
- [ ] **Day 5**: `04-vector-databases.md`. Build: read what Chroma does under the hood (HNSW); try `l2` vs `cosine` in `store.py`.
- [ ] **Day 6**: `05-hybrid-search.md`. Build: add BM25 (`pip install rank_bm25`) and RRF fusion to `retriever.py`.
- [ ] **Day 7**: `06-reranking-strategies.md`. Build: retrieve top-20, rerank to top-5 with a sentence-transformers CrossEncoder.
- [ ] **Day 8**: `13-rag-evaluation-patterns.md`. Build: grow `EVAL_SET` to 15 questions; add MRR alongside recall@k.

## Phase 3 — Generation + advanced (days 9–14)

- [ ] **Day 9**: re-read `01-rag-fundamentals.md` generation sections. Build: wire a real LLM into `generator.py` (or keep stubbed and write faithfulness checks by hand).
- [ ] **Day 10**: `10-contextual-retrieval.md`. Build: prepend chapter-title context to each chunk before embedding; measure.
- [ ] **Day 11**: `09-advanced-retrieval-patterns.md` (query rewriting, HyDE). Build: try one pattern.
- [ ] **Day 12**: `07-graph-rag.md` *or* `08-agentic-rag.md` — pick what's relevant to the internship. Read only.
- [ ] **Day 13**: `14-production-rag-at-scale.md`. Read; note what your toy pipeline ignores (caching, freshness, multi-tenancy).
- [ ] **Day 14**: Review. Re-run full eval, write a half-page summary of what moved the metrics and why.

Defer until needed: `11-late-interaction-colbert.md`, `12-multimodal-rag.md`, chapters 00/02/07/11/12 of the main guide.

## Daily log

| Date | Chapter | What I built / learned | recall@5 |
|------|---------|------------------------|----------|
| | | | |
