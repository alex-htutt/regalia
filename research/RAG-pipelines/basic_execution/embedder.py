"""Stage 3: Embeddings. Pairs with 06-retrieval-systems/03-embedding-models.md

all-MiniLM-L6-v2: 384 dims, fast, runs on CPU, downloads ~90MB on first use.
As you read the chapter, try swapping in a stronger model (e.g. bge-small-en-v1.5)
and see if retrieval improves on your eval set.
"""

from sentence_transformers import SentenceTransformer

_model = None


def get_model(name: str = "all-MiniLM-L6-v2") -> SentenceTransformer:
    global _model
    if _model is None:
        _model = SentenceTransformer(name)
    return _model


def embed(texts: list[str]) -> list[list[float]]:
    return get_model().encode(texts, show_progress_bar=False).tolist()
