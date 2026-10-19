"""Stage 5: Retrieval. Pairs with 06-retrieval-systems/05-hybrid-search.md and 06-reranking-strategies.md

Currently pure dense (vector) search. Extensions as you read:
- hybrid: add BM25 keyword scores (rank_bm25 package) and fuse with RRF
- reranking: rerank top-20 down to top-5 with a cross-encoder
"""

from embedder import embed
from store import get_collection


def retrieve(query: str, k: int = 5) -> list[dict]:
    col = get_collection()
    res = col.query(query_embeddings=embed([query]), n_results=k)
    return [
        {"text": doc, "source": meta["source"], "distance": dist}
        for doc, meta, dist in zip(
            res["documents"][0], res["metadatas"][0], res["distances"][0]
        )
    ]
