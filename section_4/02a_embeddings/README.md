# Lesson 02a (section 4) — Embeddings

## What this lesson is

Turn text into a **vector** — a list of numbers you can compare with math instead of string matching.

This is the first half of retrieval. No chunking, no database, no agent. One idea: `text -> vector -> compare`.

## New concept

**`embed()` + `cosine()`** — the same LM Studio server, a different endpoint.

```
"how do I trim history?"  →  POST /v1/embeddings  →  [0.059, 0.019, -0.145, ...]  (768 floats)
```

Two vectors that point the same way mean the same thing — even with zero words in common.

## Prerequisites

- [Lesson 01 — Chat](../../section_1/01_chat/README.md) (you already know `urllib` + JSON POST)
- An **embedding model** loaded in LM Studio alongside your chat model:

```bash
lms get text-embedding-nomic-embed-text-v1.5   # once
lms server start && lms ps                     # both models should be listed
```

Stdlib only — no venv needed for this lesson.

## Run

```bash
python3 section_4/02a_embeddings/02a_embeddings.py
```

## What the script adds

- `URL = ".../v1/embeddings"` — the embeddings door on the server you already use
- `embed(text, prefix)` — one POST, returns 768 floats (not streamed — one JSON blob)
- `cosine(a, b)` — dot product ÷ both lengths = pure angle, ignoring magnitude
- `keyword_overlap()` — a deliberately naive "grep-like" score, here only to watch it fail
- `DOC_PREFIX` / `QUERY_PREFIX` — nomic's asymmetric task prefixes

## Why cosine, not `==`?

Two sentences never match exactly, and vector *length* varies with text length — a long doc isn't "more" relevant for being long. Cosine throws length away and keeps only direction: **what the text is about**, not how much of it there is.

## The result to look at

```
  cosine   keyword  lesson
  0.6130      0.00  08b_context_management   ← correct
  0.4950      0.00  14_human_in_loop
  0.4897      0.00  16_evaluation
  0.4889      0.00  11_web_agent
```

The query — *"how do I stop things getting too big over many turns?"* — shares **zero words** with the right answer (your README says `trim_history` and "soft budget"). Keyword scoring is 0.00 across the board and cannot rank at all. Cosine puts the right lesson on top.

That gap is the entire reason RAG exists.

## The prefix gotcha

`nomic-embed` is **asymmetric** — it expects `search_document: ` on stored text and `search_query: ` on queries. Skip them and you still get plausible-looking vectors with quietly worse recall, and nothing errors:

```
[prefix] with search_query/search_document: 0.6130
[prefix] without any prefix:                0.5842
```

Both "work". Only one is what the model was trained for. Lesson 02d turns this into a measured recall@k difference instead of a single number.

## Try this

1. **Break the ranking.** Rewrite `QUERY` until the wrong lesson wins. How far off do you have to go?
2. **Add a near-duplicate** doc to `DOCS` and watch two scores land within 0.01 — this is why lesson 02c reranks the top-k instead of trusting rank 1.
3. **Embed one word vs a paragraph** and print `len()` of each vector. Same 768 either way — this is why chunk *size* is your decision, not the model's (lesson 02b).
4. Compare `"cat"` / `"kitten"` / `"database migration"` and see where the numbers land.

## Checkpoint

Explain why cosine similarity is used instead of `==`, and why a 768-float list is a *better* search key than the words it came from.

## Key code

```python
def cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0
```

## Next

**Lesson 02b — Index**: chunk this repo's 64 markdown files by heading, embed each chunk, store them in SQLite next to your [session_store](../../section_2/15_persistence/README.md) tables. That's when you stop hand-writing `DOCS` and start retrieving over something real.
