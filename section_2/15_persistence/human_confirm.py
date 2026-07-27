# Lesson 14 — human-in-the-loop. Python asks the human before destructive actions.
# NOT an LLM prompt — your code blocks until input() returns y/yes.


def confirm_action(description: str) -> bool:
    """Pause and ask the human. Returns True only for y/yes."""
    print(f"\n[hitl] {description}")
    try:
        reply = input("[hitl] Approve? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n[hitl] treated as rejected")
        return False
    approved = reply in ("y", "yes")
    print(f"[hitl] {'approved' if approved else 'rejected'}")
    return approved
