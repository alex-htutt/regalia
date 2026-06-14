"""End-to-end RAG pipeline CLI.

Usage:
    python pipeline.py ingest [path]   # index .md/.txt files (default: chapter 06 of the guide)
    python pipeline.py ask "question"  # retrieve + assemble prompt
    python pipeline.py reset           # wipe the vector store

First run downloads the embedding model (~90MB).
"""

import sys
from pathlib import Path

from chunker import chunk_by_paragraph
from embedder import embed
from generator import answer
from retriever import retrieve
from store import add_chunks, reset

DEFAULT_CORPUS = Path(__file__).parent.parent / "resources" / "ai-system-design-guide-main" / "06-retrieval-systems"


def ingest(path: Path):
    files = sorted(path.glob("**/*.md")) + sorted(path.glob("**/*.txt"))
    if not files:
        sys.exit(f"No .md or .txt files found in {path}")
    for f in files:
        chunks = chunk_by_paragraph(f.read_text(encoding="utf-8", errors="ignore"))
        add_chunks(chunks, embed(chunks), source=f.name)
        print(f"  {f.name}: {len(chunks)} chunks")
    print(f"Ingested {len(files)} files.")


def ask(question: str):
    retrieved = retrieve(question, k=5)
    print(answer(question, retrieved))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "ingest":
        ingest(Path(sys.argv[2]) if len(sys.argv) > 2 else DEFAULT_CORPUS)
    elif cmd == "ask" and len(sys.argv) > 2:
        ask(sys.argv[2])
    elif cmd == "reset":
        reset()
        print("Store wiped.")
    else:
        print(__doc__)
