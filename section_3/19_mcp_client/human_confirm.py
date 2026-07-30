# Lesson 14 — human-in-the-loop. Python input(), not the LLM, decides destructive actions.
# Eval mode (lesson 16) sets _eval_auto_approve so batch runs never block on stdin.
_eval_auto_approve = False


def set_eval_mode(enabled: bool) -> None:
    """When True, confirm_action() returns True without input()."""
    global _eval_auto_approve
    _eval_auto_approve = enabled


def confirm_action(description: str) -> bool:
    """Ask the human before write_file runs. Returns False on reject or Ctrl+C."""
    if _eval_auto_approve:
        print(f"[hitl] auto-approved (eval mode): {description}")
        return True
    print(f"\n[hitl] {description}")
    try:
        reply = input("[hitl] Approve? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n[hitl] treated as rejected")
        return False
    approved = reply in ("y", "yes")
    print(f"[hitl] {'approved' if approved else 'rejected'}")
    return approved
