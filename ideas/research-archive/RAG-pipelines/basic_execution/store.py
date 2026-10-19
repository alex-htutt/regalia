"""Stage 4: Vector store. Pairs with 06-retrieval-systems/04-vector-databases.md

Chroma persists locally to ./chroma_db — no server needed.
The chapter covers what's happening underneath (HNSW indexes, distance metrics).
"""

import chromadb

DB_PATH = "chroma_db"
COLLECTION = "study_guide"


def get_collection():
    client = chromadb.PersistentClient(path=DB_PATH)
    return client.get_or_create_collection(COLLECTION, metadata={"hnsw:space": "cosine"})


def add_chunks(chunks: list[str], embeddings: list[list[float]], source: str):
    col = get_collection()
    col.add(
        ids=[f"{source}::{i}" for i in range(len(chunks))],
        documents=chunks,
        embeddings=embeddings,
        metadatas=[{"source": source, "chunk": i} for i in range(len(chunks))],
    )


def reset():
    client = chromadb.PersistentClient(path=DB_PATH)
    try:
        client.delete_collection(COLLECTION)
    except Exception:
        pass
