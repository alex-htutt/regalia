# AI Training & LLM Jargon — Study Guide

A decoder ring for the terms in `01-foundations/`. Organized so each section unblocks specific chapter files. Skim once now, then return when a term stalls you.

---

## 1. How a model "learns" (training basics)

**Parameters / weights** — The numbers inside the model that get adjusted during training. "7B model" = 7 billion parameters. They start random; training tunes them. Everything the model "knows" is encoded in these numbers.

**Loss** — A single number measuring how wrong the model's prediction was. Training = repeatedly nudging weights to make loss smaller.

**Gradient descent** — The nudging algorithm. The *gradient* tells you which direction to adjust each weight to reduce loss; you take a small step that way, millions of times.

**Backpropagation** — How gradients are computed: errors at the output are traced backward through the network so every weight learns its share of the blame.

**Learning rate** — Step size for each nudge. Too big: training blows up. Too small: takes forever.

**Epoch / batch** — A *batch* is the group of examples processed before one weight update. An *epoch* is one full pass through the training data. LLMs often train less than one epoch — data is that big.

**Next-token prediction** — The actual task LLMs train on: given text so far, predict the next token. Everything else (reasoning, chat) emerges from doing this at scale.

**Pretraining** — The big expensive phase: next-token prediction on trillions of tokens of internet text. Produces a "base model" that completes text but doesn't follow instructions.

**Fine-tuning** — Continuing training on a smaller, targeted dataset to specialize the model. *SFT (supervised fine-tuning)*: training on example instruction→response pairs so it behaves like an assistant.

**RLHF (Reinforcement Learning from Human Feedback)** — After SFT, humans rank model outputs; a *reward model* learns those preferences; the LLM is tuned to score well on it. This is why models are "helpful" rather than just plausible.

**Scaling laws** — Empirical rules linking model size, data size, and compute to performance. The reason labs build bigger models: loss falls predictably with scale. "Chinchilla-optimal" = the best data-to-parameters ratio for a compute budget.

**Overfitting / generalization** — Overfitting: memorizing training data instead of learning patterns. Generalization: performing well on data never seen.

→ *Unblocks: scaling-laws sections of `01-llm-internals.md`*

## 2. Tokens (the model's alphabet)

**Token** — The unit models read/write. Not words, not characters — subword pieces ("understanding" → "under" + "standing"). ~4 chars or ~¾ of a word in English.

**Tokenizer / vocabulary** — The fixed lookup table (typically 32k–256k entries) mapping text↔token IDs. Decided before training, frozen forever after.

**BPE (Byte Pair Encoding)** — The dominant algorithm for building that table: start from characters, repeatedly merge the most frequent adjacent pair. *WordPiece* and *Unigram/SentencePiece* are variants.

**Context window** — Max tokens the model can attend to at once (e.g., 200k). The hard budget that makes RAG necessary: you can't stuff all your documents in.

→ *Unblocks: `02-tokenization-deep-dive.md`*

## 3. Embeddings (the part RAG is built on)

**Embedding / vector** — A list of numbers (e.g., 384 floats) representing a piece of text such that *similar meaning → nearby vectors*. The foundation of vector search.

**Dimensions (d)** — Length of that list. Your MiniLM model: 384-d. Bigger ≠ always better; it's a capacity/cost tradeoff.

**Cosine similarity** — Standard "how close are two vectors" measure: angle between them, 1 = identical direction. Your Chroma store uses this.

**Embedding model vs. LLM** — An embedding model (BERT-style, *encoder-only*) reads text and outputs one vector. An LLM (*decoder-only*) generates text. Different architectures, different jobs.

**Latent / vector space** — The abstract geometric space where embeddings live. "Semantically similar texts cluster in vector space" = the whole premise of dense retrieval.

→ *Unblocks: `05-embeddings-and-vector-spaces.md` and chapter 06's `03-embedding-models.md`*

## 4. Inside the transformer (architecture)

**Transformer** — The architecture behind all modern LLMs: stacked identical *layers*, each containing attention + a feed-forward network.

**Attention / self-attention** — The mechanism letting each token look at every other token and weigh which ones matter for predicting what's next. Why "it" can resolve to "the cat" from 50 tokens back.

**Q, K, V (query, key, value)** — The three vectors each token is projected into for attention. Intuition: each token issues a search *query* against every other token's *key*; matching strength decides how much of each *value* it absorbs.

**Multi-head attention (MHA)** — Running several attention "heads" in parallel, each free to learn a different relationship (syntax, coreference, etc.). *GQA/MQA* = efficiency variants that share keys/values across heads.

**O(n²)** — Attention cost grows with the square of sequence length: every token attends to every other. Why long contexts are expensive.

**Feed-forward network (FFN) / MLP** — The other half of each layer: per-token computation where much of the "knowledge" is stored. *SwiGLU*, *GELU*, *ReLU* = activation-function flavors inside it.

**Layer normalization (LayerNorm / RMSNorm, Pre-LN)** — Plumbing that keeps numbers in a stable range so deep networks train at all. Pre-LN = applying it before attention/FFN (modern default; trains more stably).

**Residual connection** — Each layer's output is *added* to its input rather than replacing it. Lets gradients flow through very deep stacks.

**Position encodings (RoPE, ALiBi)** — Attention is order-blind by default; these inject "token 5 comes before token 6." RoPE is today's standard.

**Decoder-only vs encoder-only vs encoder-decoder** — Decoder-only: generates left-to-right (GPT, Claude, Llama). Encoder-only: reads whole text at once, outputs representations (BERT, your embedding model). Encoder-decoder: reads then generates (T5, translation).

**MoE (Mixture of Experts)** — Instead of one big FFN, many "expert" FFNs with a router activating only a few per token. Big total parameters, small per-token compute (DeepSeek, Mixtral).

→ *Unblocks: `01-llm-internals.md`, `03-attention-mechanisms.md`, `04-transformer-architecture.md`*

## 5. Inference (using a trained model)

**Inference** — Running the model to get output. Training adjusts weights; inference just reads them.

**Logits → softmax → sampling** — The model outputs a raw score (*logit*) per vocabulary token; *softmax* converts scores to probabilities; *sampling* picks the next token from that distribution.

**Temperature** — Sampling knob: 0 ≈ always pick the most likely token (deterministic), higher = more random. *Top-p / top-k* = other ways to trim unlikely tokens before sampling.

**Autoregressive** — Generating one token at a time, feeding each output back as input. Why generation is slow and per-token priced.

**KV cache** — Stores each previous token's keys/values so they aren't recomputed for every new token. THE serving-memory bottleneck; why long contexts cost RAM.

**Prefill vs decode** — Prefill: processing your prompt (parallel, fast per token). Decode: generating output (sequential, slow per token). Explains "time to first token" vs "tokens per second."

**Hallucination** — Fluent, confident, wrong output. The model predicts plausible tokens, not verified facts — the core problem RAG mitigates by grounding answers in retrieved text.

→ *Unblocks: `06-inference-pipeline.md`*

---

## Reading strategy

The repo's `GLOSSARY.md` defines every term in one line — keep it open in a split pane while reading. This guide gives the *why*; the glossary is the quick lookup. When a chapter's math gets heavy (e.g., the √d_k scaling in attention), read the intuition paragraph, skip the derivation, move on — it never blocks the RAG material.

Self-test (you should be able to answer after Phase 1, days 1–2):

1. Why does a model trained only on next-token prediction need RLHF before it's a useful assistant?
2. Why can't you fix a tokenizer problem by fine-tuning?
3. What property of embedding vectors makes vector search work, and which similarity measure does your pipeline use?
4. Why is generation priced per token and slower than processing your prompt?
5. What does the KV cache trade memory for?
