# Step 15: human-in-the-loop. Entry script — sub-agents + logging + approval gate.
# Builds on section_2/13_logging/.
#
# NEW in this lesson (see human_confirm.py):
#   confirm_action() — Python input() before destructive tools (write_file)
#   NOT an LLM prompt — your code blocks until the human types y/yes
#
# Files:
#   14_human_in_loop.py  — entry (run this)
#   sub_agents.py        — pipeline + write_file with approval gate
#   human_confirm.py     — confirm_action() — lesson 14
#   agent_log.py         — logs approval_granted / approval_denied events
from agent_log import LOG_FILE
from sub_agents import DEFAULT_OUTPUT_PATH, MODEL, WORKSPACE, run_manager

print(f"Sub-agents + HITL with {MODEL} — empty line or Ctrl+C to quit.")
print(f"Sandbox: {WORKSPACE}")
print(f"Save target: {DEFAULT_OUTPUT_PATH}  (requires your approval)")
print(f"Log file: {LOG_FILE}")
print('Try: "What does notes/todo.md say about agents?" — then approve or reject the save.')
while True:
    try:
        user = input("\n> ").strip()
    except (EOFError, KeyboardInterrupt):
        break
    if not user:
        break
    final = run_manager(user)
    print(f"\n--- answer ---\n{final}")
    print(f"[log] run saved — grep approval in {LOG_FILE}")
