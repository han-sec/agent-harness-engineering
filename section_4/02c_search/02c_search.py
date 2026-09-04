# Step 02c (section 4): search — embed a query, rank 02b's chunks, show the top k.
#
# NEW in this lesson:
#   load_index()   — read the chunks table once, parse vectors back from JSON
#   search()       — embed the query, cosine against every chunk, sort, take top k
#   grep_search()  — the same query through plain substring matching, side by side
#
# Still no agent. You are looking at retrieval on its own, because a bad retriever
# hidden behind an agent loop is miserable to debug.
#
# Next: 02d_eval turns "these results look good" into recall@k on fixed test cases.
import json
import math
import re
import sqlite3
import sys
import urllib.error
import urllib.request
from pathlib import Path

URL = "http://localhost:1234/v1/embeddings"
EMBED_MODEL = "text-embedding-nomic-embed-text-v1.5"
QUERY_PREFIX = "search_query: "  # queries get a DIFFERENT prefix than documents (02a)

REPO_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = REPO_ROOT / "section_4" / "02b_index" / "data" / "index.db"  # built by 02b
TOP_K = 5  # how many chunks a real agent would paste into its prompt

DEMO_QUERIES = [
    "how do I stop the prompt getting too big over many turns?",  # paraphrase, no keywords
    "MAX_TOOL_ROUNDS",                                            # exact symbol
    "what stops the agent writing a file without asking me first?",
]


def embed(text: str, prefix: str = "") -> list[float] | None:
    """One string -> one vector. Same helper as 02a."""
    req = urllib.request.Request(
        URL,
        data=json.dumps({"model": EMBED_MODEL, "input": prefix + text}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)["data"][0]["embedding"]
    except urllib.error.URLError as exc:
        print(f"\n[error] Cannot reach LM Studio — is the server running? ({exc.reason})")
        return None


def cosine(a: list[float], b: list[float]) -> float:
    """Copied unchanged from 02a — similarity is the angle between two vectors."""
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    return dot / (norm_a * norm_b) if norm_a and norm_b else 0.0


def load_index() -> list[dict]:
    """Read every chunk into memory once. 165 rows — a scan is instant.

    A "vector database" is this plus an index that avoids the full scan. You need
    that at a million rows. At this size it would only hide the mechanic.
    """
    if not DB_PATH.exists():
        print(f"[error] No index at {DB_PATH.relative_to(REPO_ROOT)}")
        print("[error] Build it first: python3 section_4/02b_index/02b_index.py")
        sys.exit(1)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT source, heading, line_start, text, vector FROM chunks"
    ).fetchall()
    chunks = []
    for row in rows:
        chunk = dict(row)
        chunk["vector"] = json.loads(chunk["vector"])  # JSON text -> list[float]
        chunks.append(chunk)
    return chunks


def search(query: str, chunks: list[dict], k: int = TOP_K) -> list[tuple[float, dict]]:
    """Embed the query, score every chunk, return the k best."""
    query_vec = embed(query, QUERY_PREFIX)  # query prefix — not the document one
    if query_vec is None:
        return []
    scored = [(cosine(query_vec, chunk["vector"]), chunk) for chunk in chunks]
    # sort by score only — dicts don't compare, so never sort the tuple as a whole
    scored.sort(key=lambda pair: pair[0], reverse=True)
    return scored[:k]


def grep_search(query: str, chunks: list[dict], k: int = TOP_K) -> list[dict]:
    """What lesson 10's grep tool would find: literal substring, case-insensitive."""
    pattern = re.compile(re.escape(query), re.IGNORECASE)
    return [chunk for chunk in chunks if pattern.search(chunk["text"])][:k]


def show(query: str, chunks: list[dict]) -> None:
    """Print both retrievers on the same query so the difference is unmissable."""
    print(f"\n{'=' * 72}\n[query] {query!r}\n")

    hits = search(query, chunks)
    if not hits:
        return
    print(f"[vector] top {len(hits)}:")
    for score, chunk in hits:
        location = f"{chunk['source']}:{chunk['line_start']}"
        print(f"  {score:.4f}  {location}  [{chunk['heading'][:44]}]")
    # Preview the winner — the actual text an agent would paste into its prompt.
    best = hits[0][1]
    print(f"\n  best chunk text: {best['text'][:180].replace(chr(10), ' ')}...")

    found = grep_search(query, chunks)
    print(f"\n[grep] literal matches: {len(found)}")
    for chunk in found:
        print(f"          {chunk['source']}:{chunk['line_start']}  [{chunk['heading'][:44]}]")
    if not found:
        print("          (none — no chunk contains that string)")

    # The spread between rank 1 and rank k tells you how much to trust rank 1.
    spread = hits[0][0] - hits[-1][0]
    print(f"\n[spread] rank1 {hits[0][0]:.4f} - rank{len(hits)} {hits[-1][0]:.4f} = {spread:.4f}")
    if spread < 0.05:
        print("[spread] tight — the ranking is nearly a coin flip. Pass all k to the model.")


index = load_index()
sources = {chunk["source"] for chunk in index}
print(f"Loaded {len(index)} chunks from {len(sources)} files ({DB_PATH.name})")

for demo in DEMO_QUERIES:  # fixed queries first, so every run shows the same lesson
    show(demo, index)

print(f"\n{'=' * 72}")
print("Now try your own. Empty line or Ctrl+C to quit.")
while True:
    try:
        user_query = input("\n> ").strip()
    except (EOFError, KeyboardInterrupt):
        break
    if not user_query:
        break
    show(user_query, index)
