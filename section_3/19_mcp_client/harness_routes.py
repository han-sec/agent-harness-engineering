# Harness routes — Python handles meta/help before the LLM pipeline (lesson 12 pattern).
import re
from pathlib import Path

from mcp_client import DOCS_MCP_ROOT

DOCS_DIR = DOCS_MCP_ROOT / "docs"

_META_PATTERNS = (
    re.compile(r"^(help|\?|h)$", re.I),
    re.compile(r"what (can|do) you (do|help)", re.I),
    re.compile(r"what tools? (do you )?(have|available)", re.I),
    re.compile(r"list (your )?tools", re.I),
    re.compile(r"how (do i|to) (use|ask)", re.I),
    re.compile(r"^capabilities?$", re.I),
)


def is_meta_question(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False
    return any(p.search(stripped) for p in _META_PATTERNS)


def _doc_listing() -> str:
    if not DOCS_DIR.is_dir():
        return "(no docs/ — run lesson 18)"
    names = sorted(p.name for p in DOCS_DIR.glob("*.md"))
    return ", ".join(names) if names else "(empty)"


def builtin_answer(text: str) -> str:
    docs = _doc_listing()
    return f"""I'm an **Internal Docs Q&A** assistant (lesson 19 — MCP client).

**What I can do**
- Answer from employee handbook markdown via the **internal-docs MCP server** (lesson 18)
- Tools: `list_docs`, `read_doc`, `grep_docs` — researcher calls them over stdio
- Plan → research → write pipeline (same as capstone 17)
- Remember recent turns (SQLite); save answers to `output/answer.md` after HITL approval

**Docs available:** {docs}

**Example questions**
- "What is the refund window?"
- "Give me an overview of internal docs"
- "Walk me through a staging deploy"

**Commands:** `help`, `quit`

**Loops (important)**
- **Outer:** your Python `while True` in `19_mcp_client.py` — one user turn per iteration
- **Middle:** `run_manager_async()` — sequential planner → researcher → writer (no tool loop)
- **Inner:** only inside `run_researcher()` — LLM ↔ MCP tools until facts are ready

**MCP lifecycle**
- Harness **starts** MCP when you launch `19_mcp_client.py` (`[mcp] session started`)
- Same subprocess serves every question in the chat (no respawn per turn)
- Harness **closes** MCP when you type `quit` or Ctrl+C (`[mcp] session closed`)

Logs: `logs/agent.jsonl`"""


def print_welcome() -> None:
    print(f"Docs (MCP data): {DOCS_DIR}")
    print(f"Available: {_doc_listing()}")
    print()
    print("Type help for capabilities, or ask a docs question.")
    print('Example: "What is the refund window?"')
    print()
