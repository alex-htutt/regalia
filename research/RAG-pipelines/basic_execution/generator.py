"""Stage 6: Generation. Pairs with 06-retrieval-systems/01-rag-fundamentals.md (the G in RAG)

Stubbed by default: prints the assembled prompt so you can inspect exactly what
an LLM would receive. To go live, set ANTHROPIC_API_KEY or OPENAI_API_KEY and
fill in call_llm() — the prompt assembly (the part that matters for RAG) is done.
"""

PROMPT_TEMPLATE = """Answer the question using ONLY the context below.
If the context doesn't contain the answer, say so.

Context:
{context}

Question: {question}

Answer:"""


def build_prompt(question: str, retrieved: list[dict]) -> str:
    context = "\n\n---\n\n".join(
        f"[{r['source']}]\n{r['text']}" for r in retrieved
    )
    return PROMPT_TEMPLATE.format(context=context, question=question)


def call_llm(prompt: str) -> str:
    """Stub. Replace with an API call when ready, e.g.:

    import anthropic
    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY
    msg = client.messages.create(
        model="claude-haiku-4-5",
        max_tokens=500,
        messages=[{"role": "user", "content": prompt}],
    )
    return msg.content[0].text
    """
    return "(generation stubbed — prompt above is what the LLM would receive)"


def answer(question: str, retrieved: list[dict], show_prompt: bool = True) -> str:
    prompt = build_prompt(question, retrieved)
    if show_prompt:
        print("=" * 60)
        print(prompt)
        print("=" * 60)
    return call_llm(prompt)
