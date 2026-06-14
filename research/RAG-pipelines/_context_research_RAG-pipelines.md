---
date: 2026-06-10
tags: [area/research, type/reference]
status: active
topic: "Retrieval-augmented generation — chunking, embeddings, vector DBs, eval"
deadline:
related: []
---

# RAG Pipelines — Context

Self-directed study on retrieval-augmented generation. Primary resource: `resources/ai-system-design-guide-main/06-retrieval-systems/`. Structured as learning → basic execution → deep execution (deep execution project will live in `projects/`).

## Current state
- `basic_execution/` has a complete minimal pipeline (8 files):
  - `pipeline.py` — ingest / ask / reset CLI
  - `chunker.py`, `embedder.py`, `store.py` (Chroma + HNSW), `retriever.py`
  - `generator.py` — stubbed; outputs the assembled prompt
  - `evaluate.py` — recall@k on built-in eval set
  - `requirements.txt`, `README.md`
- `STUDY_PLAN.md` — 14-day phased plan (foundations → core pipeline → generation + advanced); no days logged yet
- `AI_JARGON_STUDY_GUIDE.md` — decoder ring for LLM/training terms in the study guide chapters

## Active deliverable(s)
- Work through `STUDY_PLAN.md` one session per day; log results in its daily-log table.
- Run `evaluate.py` before/after each build step to track recall@k.

## Open questions
- When to wire a real LLM into `generator.py` (Day 9 per plan, or earlier if useful for internship).
- Whether to extend into a deep-execution project (full multi-tenant RAG app) once Phase 3 is done.

## Key resources
- `resources/ai-system-design-guide-main/` — primary reading
- `AI_JARGON_STUDY_GUIDE.md` — reference for unfamiliar terms
- `STUDY_PLAN.md` — day-by-day agenda

## Next deadline
- Self-paced; aim for ~1 chapter + build per day

---
↑ [[research/_context_research|Research]]
