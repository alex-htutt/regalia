"""Stage 2: Chunking. Pairs with 06-retrieval-systems/02-chunking-strategies.md

Start with fixed-size + overlap. As you read the chapter, try adding:
- paragraph/heading-aware splitting
- sentence-boundary snapping
- semantic chunking
Then compare retrieval quality with evaluate.py.
"""


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> list[str]:
    """Fixed-size character chunks with overlap."""
    if chunk_size <= overlap:
        raise ValueError("chunk_size must be > overlap")
    chunks = []
    start = 0
    while start < len(text):
        chunks.append(text[start : start + chunk_size])
        start += chunk_size - overlap
    return [c.strip() for c in chunks if c.strip()]


def chunk_by_paragraph(text: str, max_size: int = 800) -> list[str]:
    """Paragraph-aware: merge paragraphs until max_size. A better default for markdown."""
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    chunks, current = [], ""
    for p in paragraphs:
        if len(current) + len(p) > max_size and current:
            chunks.append(current)
            current = p
        else:
            current = f"{current}\n\n{p}" if current else p
    if current:
        chunks.append(current)
    return chunks
