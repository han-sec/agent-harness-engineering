# Step 02b (section 4): index — chunk this repo's markdown, embed every chunk, store in SQLite.
#
# NEW in this lesson:
#   split_sections() — cut a markdown file on ## headings, keeping line numbers
#   pack_sections()  — merge chunks that are too small, split ones that are too big
#   embed_batch()    — one POST for many strings (02a made one call per string)
#   dedupe()         — drop byte-identical chunks before they split the ranking
#   build_index()    — write {source, heading, text, vector} rows to SQLite
#
# Chunking is the whole lesson. Retrieval quality is decided HERE, not in the search:
# a chunk that cannot answer a question standalone will never answer one, no matter
# how good your ranking is.
#
# Next: 02c_search embeds a query and ranks these rows with cosine().
import json            # request bodies, and vector storage in SQLite
import re              # find markdown headings
import sqlite3         # same store you built in lesson 15
import urllib.error    # catch "model offline"
import urllib.request  # stdlib HTTP, as always
from pathlib import Path

URL = "http://localhost:1234/v1/embeddings"
EMBED_MODEL = "text-embedding-nomic-embed-text-v1.5"
DOC_PREFIX = "search_document: "  # asymmetric prefix from 02a — documents, not queries

REPO_ROOT = Path(__file__).resolve().parents[2]  # section_4/02b_index -> repo root
DB_PATH = Path(__file__).resolve().parent / "data" / "index.db"

# Size targets, in characters. The corpus decides these numbers, not a blog post:
# this repo's ## sections run from 18 to 6089 chars, median 188 — far too spiky to
# embed as-is. MIN merges the runts, MAX splits the monsters.
MIN_CHARS = 400   # below this, a chunk is a fragment — merge it with the next one
MAX_CHARS = 2000  # above this, one vector has to represent too many ideas — split it
BATCH_SIZE = 32   # strings per embeddings request — 32 takes ~1s, 1 takes ~0.02s

HEADING_RE = re.compile(r"(?m)^(#{1,3})\s+(.+)$")  # h1-h3 only; deeper is usually noise


def embed_batch(texts: list[str]) -> list[list[float]] | None:
    """POST many strings at once. The response 'data' list comes back in input order."""
    req = urllib.request.Request(
        URL,
        # NEW vs 02a: "input" takes a list, not just a string. Same endpoint.
        data=json.dumps({"model": EMBED_MODEL, "input": texts}).encode(),
        headers={"Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=300) as resp:
            payload = json.load(resp)
    except urllib.error.URLError as exc:
        print(f"\n[error] Cannot reach LM Studio — is the server running? ({exc.reason})")
        return None
    return [row["embedding"] for row in payload["data"]]


def split_sections(text: str) -> list[dict]:
    """Cut a markdown file at each heading. Returns {heading, line_start, body} sections."""
    sections = []
    matches = list(HEADING_RE.finditer(text))
    if not matches:  # a file with no headings is one section
        return [{"heading": "", "line_start": 1, "body": text}]
    # Anything before the first heading (frontmatter, intro paragraph) is its own section.
    if matches[0].start() > 0:
        sections.append({"heading": "", "line_start": 1, "body": text[: matches[0].start()]})
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        sections.append({
            "heading": match.group(2).strip(),
            # count newlines before this point — cheap way to get a citable line number
            "line_start": text.count("\n", 0, match.start()) + 1,
            "body": text[match.start():end],
        })
    return sections


def split_long_body(body: str) -> list[str]:
    """Break an oversized section on blank lines, never mid-paragraph."""
    paragraphs = body.split("\n\n")
    pieces, current = [], ""
    for para in paragraphs:
        # +2 accounts for the "\n\n" we will rejoin with
        if current and len(current) + len(para) + 2 > MAX_CHARS:
            pieces.append(current)
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current:
        pieces.append(current)
    return pieces


def pack_sections(sections: list[dict]) -> list[dict]:
    """Normalize section sizes: merge the runts, split the monsters."""
    packed, buffer = [], None
    for section in sections:
        if not section["body"].strip():
            continue  # a heading with nothing under it carries no meaning
        if len(section["body"]) > MAX_CHARS:
            if buffer:  # flush whatever was accumulating before this big one
                packed.append(buffer)
                buffer = None
            for piece in split_long_body(section["body"]):
                packed.append({**section, "body": piece})
            continue
        if buffer is None:
            buffer = dict(section)
        else:
            # Merge: keep the FIRST heading as the label, since it's the broader one.
            buffer["body"] += "\n\n" + section["body"]
        if len(buffer["body"]) >= MIN_CHARS:
            packed.append(buffer)
            buffer = None
    if buffer:  # trailing runt — keep it rather than silently dropping content
        packed.append(buffer)
    return packed


def chunk_file(path: Path) -> list[dict]:
    """One markdown file -> ready-to-embed chunks with a source breadcrumb."""
    text = path.read_text(encoding="utf-8", errors="replace")
    source = str(path.relative_to(REPO_ROOT))
    chunks = []
    for section in pack_sections(split_sections(text)):
        # THE BREADCRUMB TRICK: prepend where this text came from before embedding.
        # A chunk reading "- get_weather(city) — Example: TOOL:get_weather:Tokyo" is
        # meaningless alone. With "section_1/04_tools/README.md > Key code" in front,
        # the vector also encodes WHICH LESSON it belongs to — so a query mentioning
        # tools or lesson 04 can find it. Cheap, and it fixes most tiny-chunk misses.
        breadcrumb = f"{source} > {section['heading']}" if section["heading"] else source
        chunks.append({
            "source": source,
            "heading": section["heading"],
            "line_start": section["line_start"],
            "text": section["body"].strip(),
            "embed_text": f"{breadcrumb}\n\n{section['body'].strip()}",
        })
    return chunks


def collect_chunks() -> list[dict]:
    """Walk the repo's markdown, skipping virtualenvs, output, and lesson fixtures."""
    # "workspace" and "notes" hold the sample files lessons 10-17 read at runtime —
    # test fixtures, not documentation. Indexing them means a search for "agents"
    # returns eleven identical todo.md files instead of the lesson that explains them.
    skip = {".venv", "__pycache__", "node_modules", ".git", "logs", "output",
            "workspace", "notes", "data", "reports"}
    chunks = []
    for path in sorted(REPO_ROOT.rglob("*.md")):
        if skip & set(path.parts):  # any skipped directory anywhere in the path
            continue
        chunks.append(chunk_file(path))
    return [chunk for file_chunks in chunks for chunk in file_chunks]


def dedupe(chunks: list[dict]) -> list[dict]:
    """Drop chunks whose text is byte-identical to one already kept.

    Every real corpus has duplicates — copied templates, vendored docs, a README
    pasted into three folders. Near-identical vectors split the ranking between
    themselves and push genuinely different results off the top-k. Cheap fix,
    measurable payoff; do it before you reach for anything cleverer.
    """
    seen, unique = set(), []
    for chunk in chunks:
        if chunk["text"] in seen:
            continue
        seen.add(chunk["text"])
        unique.append(chunk)
    return unique


def build_index(chunks: list[dict]) -> bool:
    """Embed every chunk in batches and replace the chunks table. Full rebuild each run."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(DB_PATH) as conn:
        conn.execute("DROP TABLE IF EXISTS chunks")  # rebuild — 340 chunks costs ~12s
        conn.execute(
            """
            CREATE TABLE chunks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source TEXT NOT NULL,
                heading TEXT NOT NULL,
                line_start INTEGER NOT NULL,
                text TEXT NOT NULL,
                vector TEXT NOT NULL
            )
            """
        )
        for start in range(0, len(chunks), BATCH_SIZE):
            batch = chunks[start:start + BATCH_SIZE]
            vectors = embed_batch([DOC_PREFIX + c["embed_text"] for c in batch])
            if vectors is None:
                return False  # server died mid-index; error already printed
            conn.executemany(
                "INSERT INTO chunks (source, heading, line_start, text, vector) "
                "VALUES (?, ?, ?, ?, ?)",
                [
                    # Vectors stored as JSON text: readable with the sqlite3 CLI and
                    # trivial to json.loads back. ~10KB per row — fine at this scale,
                    # wrong at a million rows (that's what real vector stores are for).
                    (c["source"], c["heading"], c["line_start"], c["text"], json.dumps(v))
                    for c, v in zip(batch, vectors)
                ],
            )
            print(f"[embed] {min(start + BATCH_SIZE, len(chunks))}/{len(chunks)} chunks")
    return True


def print_stats(chunks: list[dict]) -> None:
    """Show the size distribution — this is how you tell good chunking from bad."""
    sizes = sorted(len(c["text"]) for c in chunks)
    sources = {c["source"] for c in chunks}
    print(f"\n[stats] {len(chunks)} chunks from {len(sources)} files")
    print(f"[stats] chars  min {sizes[0]}  median {sizes[len(sizes) // 2]}  max {sizes[-1]}")
    print(f"[stats] under MIN_CHARS ({MIN_CHARS}): {sum(1 for s in sizes if s < MIN_CHARS)}")
    print(f"[stats] over  MAX_CHARS ({MAX_CHARS}): {sum(1 for s in sizes if s > MAX_CHARS)}")


print("Building the retrieval index over this repo's markdown.")
print("Start LM Studio first: lms server start && lms ps\n")

raw_chunks = collect_chunks()
all_chunks = dedupe(raw_chunks)
print(f"[dedupe] {len(raw_chunks)} chunks -> {len(all_chunks)} "
      f"({len(raw_chunks) - len(all_chunks)} exact duplicates dropped)")
print_stats(all_chunks)

# THE CHECKPOINT: read these before trusting any search built on top of them.
print("\n[sample] three chunks, spread across the corpus — read them:")
for pick in (0, len(all_chunks) // 2, len(all_chunks) - 1):
    chunk = all_chunks[pick]
    preview = chunk["text"][:220].replace("\n", " ")
    print(f"\n  --- chunk {pick}: {chunk['source']}:{chunk['line_start']} "
          f"[{chunk['heading'] or 'no heading'}] ({len(chunk['text'])} chars)")
    print(f"  {preview}{'...' if len(chunk['text']) > 220 else ''}")
print("\n  Ask of each: could this answer a question on its own? If not, fix the")
print("  chunker before moving on — 02c cannot rank context that isn't there.\n")

if build_index(all_chunks):
    print(f"\n[done] index written to {DB_PATH.relative_to(REPO_ROOT)}")
    print("[done] inspect it: sqlite3 " + str(DB_PATH.relative_to(REPO_ROOT))
          + " 'SELECT source, heading FROM chunks LIMIT 10;'")
    print("[next] 02c_search embeds a query and ranks these rows.")
