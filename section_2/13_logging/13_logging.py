# Step 14: logging. Entry script — wires sub-agent harness + log module.
# Builds on section_2/12_sub_agents/12_sub_agents.py.
#
# NEW in this lesson (see agent_log.py):
#   Structured JSONL logs with timestamps and run_id — replayable traces for eval
#
# Files in this folder:
#   13_logging.py  — entry + input loop (you run this)
#   sub_agents.py  — researcher / writer pipeline (lesson 12)
#   agent_log.py   — log_event helpers (lesson 13 — the one new idea)
from agent_log import LOG_FILE
from sub_agents import MODEL, WORKSPACE, run_manager

print(f"Sub-agents + logging with {MODEL} — empty line or Ctrl+C to quit.")
print(f"Sandbox: {WORKSPACE}")
print(f"Log file: {LOG_FILE}  (JSONL — one event per line)")
print("Terminal prints = live view. Log file = replay after the run.")
print('Try: "What does notes/todo.md say about agents?"')
while True:
    try:
        user = input("\n> ").strip()
    except (EOFError, KeyboardInterrupt):
        break
    if not user:
        break
    final = run_manager(user)
    print(f"\n--- answer ---\n{final}")
    print(f"[log] run saved — grep run_id in {LOG_FILE}")
