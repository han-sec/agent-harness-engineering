# Lesson 02b (section 4) — Index

## What this lesson is

Chunk this repo's markdown, embed every chunk, store the vectors in SQLite.

**Chunking is the whole lesson.** Retrieval quality is decided here, not in the search. A chunk that can't answer a question standalone will never answer one, no matter how good your ranking gets.

## New concept

**Chunk → embed → store.**

```
64 *.md files  →  split on headings  →  merge runts / split monsters  →  dedupe  →  embed  →  SQLite
```

## Prerequisites

- [Lesson 02a — Embeddings](../02a_embeddings/README.md) (`embed`, `cosine`, doc/query prefixes)
- [Lesson 15 — Persistence](../../section_2/15_persistence/README.md) (SQLite you've already written)

Stdlib only — no venv.

## Run

```bash
python3 section_4/02b_index/02b_index.py
```

Full rebuild every run (~12s for 165 chunks). Output lands in `data/index.db`.

## What the script adds

| Function | Job |
|---|---|
| `split_sections()` | Cut a file at `#`/`##`/`###`, keeping `line_start` so results stay citable |
| `split_long_body()` | Break oversized sections on blank lines — never mid-paragraph |
| `pack_sections()` | Merge sections under `MIN_CHARS`, split those over `MAX_CHARS` |
| `dedupe()` | Drop byte-identical chunks before they split the ranking |
| `embed_batch()` | **NEW vs 02a:** `"input"` takes a *list* — 32 vectors in ~1s |

## Why sizes need normalizing

Split this repo naively on `##` and you get **340 sections: 18 to 6089 chars, median 188**. Both tails are broken:

- **Too small** — `"- get_weather(city) — Example: TOOL:get_weather:Tokyo"` is a true statement about nothing. Its vector matches every tools query and answers none.
- **Too big** — one vector representing 6000 chars of five different ideas is the average of all of them, and therefore close to none of them.

`MIN_CHARS = 400` / `MAX_CHARS = 2000` come from that measured distribution, not from a blog post. After packing: **165 chunks, median 508, none over max.**

## The breadcrumb trick

Before embedding, each chunk gets its origin prepended:

```
section_1/04_tools/README.md > Key code

- `TOOL:name:arg` — the contract the model must emit
```

The stored `text` stays clean; only `embed_text` carries the breadcrumb. Now the vector encodes *which lesson this is*, so a tiny chunk is still findable. This fixes most small-chunk misses for one line of code.

## Your corpus is dirtier than you think

The first build of this index pulled in `workspace/` and `notes/` — the sample files lessons 10–17 read at runtime. Result:

```
199 chunks, 46 of them (23%) exact duplicates
  x11: '# Agents\n\nAn **agent** wraps an LLM in a loop so it can **act**...'
  x11: '# agents need harness engineering — tools, parsing, guard rails...'
```

Eleven identical copies of a test fixture would beat the actual lesson on any query about agents, because near-identical vectors split the ranking between themselves and push genuinely different results out of the top-k. Two fixes, both in the script:

1. **Skip fixture directories** — `workspace`, `notes`, `data`, `reports` are test data, not documentation → 199 chunks becomes 167
2. **`dedupe()` on exact text** — catches the rest → 165

Do both *before* reaching for anything cleverer. Cheap, and measurable in 02d.

## Checkpoint

The script prints three chunks from across the corpus. **Read them.** For each, ask: *could this answer a question on its own?*

If not, fix the chunker before moving on — 02c cannot rank context that isn't there. This is the single highest-leverage check in the whole RAG build, and it takes thirty seconds.

## Try this

1. **Inspect the store** — `sqlite3 section_4/02b_index/data/index.db 'SELECT source, heading, length(text) FROM chunks LIMIT 20;'`
2. **Break it deliberately** — set `MIN_CHARS = 50`, rebuild, read the samples. Watch chunks become fragments.
3. **Drop the breadcrumb** from `embed_text`, rebuild, and see in 02c which queries stop working.
4. **Index the Python too** — `*.py` split on `def`. Different corpus, same pipeline.
5. **Make it incremental** — store a hash per file and only re-embed what changed. Not needed at 165 chunks; essential at 100k.

## Key code

```python
# The breadcrumb: stored text stays clean, embedded text knows where it lives.
breadcrumb = f"{source} > {section['heading']}" if section["heading"] else source
chunks.append({..., "text": body, "embed_text": f"{breadcrumb}\n\n{body}"})
```

## Note on storage

Vectors are stored as JSON text — readable from the `sqlite3` CLI, `json.loads` back in one line. ~10KB/row is fine at 165 rows and wrong at a million. That's the point where a real vector store starts earning its dependency; you are nowhere near it.

## Next

**Lesson 02c — Search**: embed a query, `cosine()` it against all 165 rows, print the top 5 with sources — next to `grep` on the same query. Early result from the index you just built:

```
Q: how do the sub agents keep separate histories?
  0.7456  section_2/12_sub_agents/README.md:1   [Lesson 12 — Sub-agents]
  0.6708  section_3/19_mcp_client/README.md:96  [sub_agents.py — capstone pipeline]
```

Note how tight the scores are — 0.74 vs 0.67 — and that on other queries the *second* hit is the better answer. That compression is what reranking exists to fix, and why 02d measures recall@k instead of trusting rank 1.
