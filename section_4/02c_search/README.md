# Lesson 02c (section 4) — Search

## What this lesson is

Embed a query, score it against every chunk from 02b, print the top 5 — next to `grep` on the same query.

Still no agent. You're looking at retrieval alone, because a bad retriever hidden behind an agent loop is miserable to debug.

## New concept

**Query → vector → rank → top k.**

```
"how do I trim history?"  →  search_query: prefix  →  cosine vs 165 chunks  →  sort  →  top 5
```

## Prerequisites

- [Lesson 02b — Index](../02b_index/README.md) — **run it first**, this reads its `data/index.db`
- [Lesson 10 — File agent](../../section_2/10_file_agent/README.md) — the `grep` we're comparing against

## Run

```bash
python3 section_4/02b_index/02b_index.py    # once, if you haven't
python3 section_4/02c_search/02c_search.py
```

Three fixed demo queries run first, then it drops into a prompt for your own.

## The three results that matter

### 1. Paraphrase — vectors win, grep scores zero

```
[query] 'how do I stop the prompt getting too big over many turns?'
[vector] 0.6571  section_2/08a_token_estimate/README.md:32   [Why measure first?]
         0.6526  section_2/08b_context_management/README.md:1 [Lesson 08b]
[grep]   0 matches — no chunk contains that string
```

Your READMEs say `trim_history` and "soft budget". They never say "too big". Grep has nothing to match; cosine puts both correct lessons at the top.

### 2. Exact symbol — **grep wins, vectors fail**

```
[query] 'MAX_TOOL_ROUNDS'
[vector] 0.6324  section_2/07_error_handling/README.md:36  [What to watch for]  ← does NOT contain the symbol
[grep]   5 exact matches, including 07_error_handling/README.md:15 (the definition)
```

Read that carefully. The top vector hit **does not contain `MAX_TOOL_ROUNDS` at all** — it's a chunk that's merely *about* error handling. Embeddings encode meaning, and a rare identifier has almost no meaning to encode; it gets tokenized into fragments and smeared toward whatever topic surrounds it.

This is the single most common production RAG failure: someone searches for an exact error code, function name, or ticket ID, and semantic search confidently returns a topically-related chunk that doesn't contain it.

**Never delete your keyword search.** 02d measures the split; hybrid retrieval is the fix.

### 3. Every spread is tight

```
[spread] rank1 0.6571 - rank5 0.6315 = 0.0256
[spread] rank1 0.7054 - rank5 0.6782 = 0.0272
[spread] rank1 0.6324 - rank5 0.6004 = 0.0321
```

All three queries: ~0.03 between best and fifth-best. **Rank 1 is not meaningfully better than rank 5** — and on query 1 the genuinely better answer (08b) sits at rank 2.

Two consequences you should carry into every RAG system you build:

- **Pass all k to the model, not just the best hit.** Retrieval picks a neighborhood; the model picks the answer.
- **Never show a user a raw cosine score.** 0.65 vs 0.63 is noise. It looks like precision and isn't.

## What the script adds

| Function | Job |
|---|---|
| `load_index()` | Read 165 rows once, `json.loads` vectors back to `list[float]` |
| `search()` | Embed query with `search_query:`, cosine all chunks, sort, slice k |
| `grep_search()` | `re.escape` + `IGNORECASE` substring — lesson 10's tool, on the same corpus |
| `show()` | Print both, plus the spread, plus the winning chunk's actual text |

## Why a full scan is fine

165 chunks × 768 floats, scanned in pure Python, is instant. A vector database is this loop plus an approximate index that avoids the scan — necessary at a million rows, and at this size it would only hide the mechanic you're learning.

Rough guide: **full scan to ~10k chunks. numpy to ~1M. A real vector DB past that.**

## Checkpoint

Find one query where grep wins and one where vectors win, and explain *why* each fails — in terms of what an embedding actually encodes.

## Try this

1. **Hunt more vector failures.** Try `TOOL:get_weather:Tokyo`, `08b`, `zoneinfo`. Anything rare and literal.
2. **Ask a question the corpus can't answer** — "how do I fine-tune a model?" It still returns 5 chunks with confident-looking scores. Nothing in cosine says "I don't know." That's the `no-answer` case 02d has to score.
3. **Drop `QUERY_PREFIX`** and re-run all three. Watch the ranking shift.
4. **Rebuild 02b with `MIN_CHARS = 50`**, then re-run this. Fragmented chunks, visibly worse results — the 02b checkpoint, now with evidence.

## Key code

```python
scored = [(cosine(query_vec, chunk["vector"]), chunk) for chunk in chunks]
scored.sort(key=lambda pair: pair[0], reverse=True)  # sort on score only — dicts don't compare
return scored[:k]
```

## Next

**Lesson 02d — Eval**: 15–20 `{query, expected_source}` pairs scored as recall@5, reusing [lesson 16](../../section_2/16_evaluation/README.md)'s runner. Everything above is anecdote until it's a number — and you now have two specific hypotheses worth measuring: *does the doc/query prefix matter?* and *how much does hybrid recover on exact-symbol queries?*
