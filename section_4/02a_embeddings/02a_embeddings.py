# Step 02a (section 4): embeddings — turn text into vectors you can compare with math.
#
# NEW in this lesson:
#   embed(text)  — POST /v1/embeddings, get a 768-float vector back
#   cosine(a, b) — similarity between two vectors (angle, not distance)
#
# No chunking, no storage, no agent loop. One idea: text -> vector -> compare.
# Next: 02b_index chunks this repo's *.md files and stores their vectors in SQLite.
import json            # serialize the request body, parse the response
import math            # sqrt for the cosine denominator
import urllib.error    # catch "model offline" connection errors
import urllib.request  # same stdlib HTTP as every other lesson

# Same LM Studio server as always — different door. Chat lives at /v1/chat/completions,
# embeddings live at /v1/embeddings. Both are OpenAI-compatible.
URL = "http://localhost:1234/v1/embeddings"
EMBED_MODEL = "text-embedding-nomic-embed-text-v1.5"  # must be loaded in LM Studio (lms ps)

# nomic-embed is an ASYMMETRIC model: it wants to know whether the text is a stored
# document or a search query, and it encodes them into slightly different regions.
# Skip these prefixes and you still get plausible-looking vectors with quietly worse
# recall — the worst kind of bug, because nothing errors. Lesson 02d measures the gap.
DOC_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "


def embed(text: str, prefix: str = "") -> list[float] | None:
    """POST one string, get back the model's vector for it. None if LM Studio is down."""
    req = urllib.request.Request(
        URL,
        data=json.dumps({"model": EMBED_MODEL, "input": prefix + text}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.load(resp)  # not streamed — one JSON blob, unlike chat
    except urllib.error.URLError as exc:
        print(f"\n[error] Cannot reach LM Studio — is the server running? ({exc.reason})")
        return None
    # Shape mirrors chat: a "data" list, one entry per input string.
    return payload["data"][0]["embedding"]


def cosine(a: list[float], b: list[float]) -> float:
    """Similarity of two vectors: 1.0 = same direction, 0.0 = unrelated."""
    dot = sum(x * y for x, y in zip(a, b))          # how much they point the same way
    norm_a = math.sqrt(sum(x * x for x in a))       # length of a
    norm_b = math.sqrt(sum(y * y for y in b))       # length of b
    if not norm_a or not norm_b:
        return 0.0                                   # guard against a zero vector
    return dot / (norm_a * norm_b)                   # divide out length -> pure angle


def keyword_overlap(query: str, doc: str) -> float:
    """Naive 'grep-like' score: fraction of query words that literally appear in doc.

    Not part of a real retriever — it's here so you can watch it fail on paraphrase.
    """
    q_words = set(query.lower().split())
    d_words = set(doc.lower().split())
    if not q_words:
        return 0.0
    return len(q_words & d_words) / len(q_words)


# A tiny corpus: one-line summaries of lessons you already built.
# Deliberately worded the way YOU wrote them — not the way you'd ask about them.
DOCS = {
    "08b_context_management": "trim_history drops old turns once the prompt exceeds MAX_HISTORY_TOKENS, a soft budget below the 8192 ceiling.",
    "11_web_agent": "fetch_url retrieves a page through an allowlist with timeouts, then converts HTML to plain text.",
    "14_human_in_loop": "confirm_action gates write_file behind a yes/no approval prompt before the agent touches disk.",
    "16_evaluation": "test_cases.json drives fixed prompts through the agent and scores the answers pass or fail.",
}

# Note there is no word overlap with any doc above: no "prompt", no "trim", no "history".
QUERY = "how do I stop things getting too big over many turns?"


print(f"Embedding demo with {EMBED_MODEL}")
print("Start LM Studio first: lms server start && lms ps\n")

# --- Part 1: what does a vector actually look like? -------------------------
sample = embed("hello world", DOC_PREFIX)
if sample is None:
    raise SystemExit(1)  # server down — the error was already printed
print(f"[vector] 'hello world' -> {len(sample)} floats")
print(f"[vector] first 5: {[round(x, 4) for x in sample[:5]]}")
print("[vector] that list IS the meaning, as coordinates. Nothing else is stored.\n")

# --- Part 2: rank the corpus against a paraphrased query --------------------
print(f"[query] {QUERY!r}\n")
query_vec = embed(QUERY, QUERY_PREFIX)  # query prefix, not document prefix
if query_vec is None:
    raise SystemExit(1)

scores = []
for name, text in DOCS.items():
    doc_vec = embed(text, DOC_PREFIX)  # one HTTP call per doc — 02b will batch these
    if doc_vec is None:
        raise SystemExit(1)
    scores.append((cosine(query_vec, doc_vec), keyword_overlap(QUERY, text), name))

print(f"{'cosine':>8}  {'keyword':>8}  lesson")
for cos_score, kw_score, name in sorted(scores, reverse=True):  # best match first
    print(f"{cos_score:>8.4f}  {kw_score:>8.2f}  {name}")

top = max(scores)
print(f"\n[result] cosine picked {top[2]} — with {top[1]:.0%} of query words appearing in it.")
print("[result] Keyword scoring cannot rank these at all. That gap is why RAG exists.")

# --- Part 3: does the prefix actually matter? -------------------------------
# Same query, same doc, embedded WITHOUT the asymmetric prefixes.
target = DOCS["08b_context_management"]
with_prefix = cosine(query_vec, embed(target, DOC_PREFIX))
without_prefix = cosine(embed(QUERY), embed(target))
print(f"\n[prefix] with search_query/search_document: {with_prefix:.4f}")
print(f"[prefix] without any prefix:                {without_prefix:.4f}")
print("[prefix] Both 'work'. Only one is what the model was trained for.")
