# Basic RAG Pipeline

Minimal, fully-local RAG pipeline. Each file maps to a chapter in
`../resources/ai-system-design-guide-main/06-retrieval-systems/`.
The default corpus is the study guide itself — you query what you're learning.

## Setup

```bash
pip install -r requirements.txt
```

## Run

```bash
python pipeline.py ingest                          # index chapter 06 (first run downloads ~90MB model)
python pipeline.py ask "What is hybrid search?"    # retrieve + show assembled prompt
python evaluate.py                                 # recall@k on the built-in eval set
python pipeline.py reset                           # wipe the index
```

Generation is stubbed — `ask` shows the exact prompt an LLM would receive.
Plug in an API key via `generator.py::call_llm()` when ready.

## File ↔ chapter map

| File | Chapter | Extension to try after reading |
|------|---------|-------------------------------|
| `pipeline.py` | 01 fundamentals | — |
| `chunker.py` | 02 chunking | sentence-aware / semantic chunking |
| `embedder.py` | 03 embeddings | swap model, compare recall@k |
| `store.py` | 04 vector DBs | try a different distance metric |
| `retriever.py` | 05 hybrid, 06 reranking | add BM25 + RRF, then a cross-encoder |
| `generator.py` | 01 (the G) | wire up a real LLM |
| `evaluate.py` | 13 evaluation | add faithfulness checks, grow the eval set |

Run `evaluate.py` before and after every change — that's the whole point.
