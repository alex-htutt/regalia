"""Stage 7: Evaluation. Pairs with 06-retrieval-systems/13-rag-evaluation-patterns.md

Measures recall@k: does the chunk from the right source file show up in the top k?
Add questions to EVAL_SET as you read chapters — 10-15 questions is enough to
tell whether a chunking/embedding/retrieval change helped or hurt.
"""

from retriever import retrieve

# question -> source file that should contain the answer
EVAL_SET = {
    "What is retrieval augmented generation?": "01-rag-fundamentals.md",
    "What chunk size should I use?": "02-chunking-strategies.md",
    "How do I choose an embedding model?": "03-embedding-models.md",
    "What is HNSW?": "04-vector-databases.md",
    "How does BM25 combine with vector search?": "05-hybrid-search.md",
    "When should I use a cross-encoder reranker?": "06-reranking-strategies.md",
}


def recall_at_k(k: int = 5) -> float:
    hits = 0
    for question, expected_source in EVAL_SET.items():
        results = retrieve(question, k=k)
        sources = [r["source"] for r in results]
        hit = expected_source in sources
        hits += hit
        print(f"{'HIT ' if hit else 'MISS'} {question}  -> {sources[0]}")
    score = hits / len(EVAL_SET)
    print(f"\nrecall@{k}: {score:.0%} ({hits}/{len(EVAL_SET)})")
    return score


if __name__ == "__main__":
    recall_at_k()
