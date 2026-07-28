# Harness routes — Python handles some inputs BEFORE the LLM pipeline (lesson 12 pattern).
# Meta questions (help, tools, capabilities) don't need plan → research → write.
import re
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parent / "workspace"
DOCS_DIR = WORKSPACE / "docs"

# Patterns for questions Python can answer deterministically — no model call
_META_PATTERNS = (
    re.compile(r"^(help|\?|h)$", re.I),
    re.compile(r"what (can|do) you (do|help)", re.I),
    re.compile(r"what tools? (do you )?(have|available)", re.I),
    re.compile(r"list (your )?tools", re.I),
    re.compile(r"how (do i|to) (use|ask)", re.I),
    re.compile(r"^capabilities?$", re.I),
)


def is_meta_question(text: str) -> bool:
    """True if the harness should answer without calling planner/researcher/writer."""
    stripped = text.strip()
    if not stripped:
        return False
    return any(p.search(stripped) for p in _META_PATTERNS)


def _doc_listing() -> str:
    if not DOCS_DIR.is_dir():
        return "(no docs/ folder found)"
    names = sorted(p.name for p in DOCS_DIR.iterdir() if p.suffix == ".md")
    return ", ".join(names) if names else "(empty)"


def builtin_answer(text: str) -> str:
    """Deterministic reply for meta / help questions."""
    docs = _doc_listing()
    return f"""I'm an **Internal Docs Q&A** assistant. I answer from files in `workspace/docs/` — not from general knowledge.

**What I can do**
- Look up policies, runbooks, and onboarding steps
- Search across docs (`grep`), read full files, list what's available
- Synthesize answers from **multiple docs** (e.g. team-faq.md, index.md)
- Remember recent chat turns (SQLite) for follow-ups
- Save answers to `output/answer.md` after you approve (HITL)

**Docs available:** {docs}

**Example questions**
- Overview: "Give me an overview of our internal documentation"
- Lookup: "What is the refund window?"
- Procedure: "Walk me through a staging deploy"
- Cross-doc: "I'm a new engineer — what must I read before prod?"
- Compare: "What are the differences between staging and prod API limits?"
- Follow-up: "What about Friday deploys?" (after a prior deploy question)

**Commands**
- `help` — this message (Python, no LLM)
- `quit` — exit

**Pipeline** (for real doc questions): plan → research (tools) → write → optional save
Logs: `logs/agent.jsonl`"""


def print_welcome() -> None:
    """Startup banner — teaches what the harness is for."""
    print("Internal Docs Q&A (capstone)")
    print(f"Docs: {DOCS_DIR}")
    print(f"Available: {_doc_listing()}")
    print()
    print("Type help for capabilities, or ask a docs question.")
    print("Examples:")
    print('  "Give me an overview of internal docs"')
    print('  "I\'m new — what do I need before prod deploy?"')
    print('  "Compare refund policy vs API billing support"')
    print('  "What is the refund window?"')
    print()
