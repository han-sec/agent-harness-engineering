# Step 16: persistence. Entry script — conversation survives script restarts (SQLite).
# Builds on section_2/14_human_in_loop/.
#
# NEW in this lesson (see session_store.py):
#   save_turn() / load_recent_turns() — SQLite stores user Q + assistant A across runs
#   NOT the same as 08b trim_history (in-memory, one session only)
#
# Files:
#   15_persistence.py  — entry (run this)
#   session_store.py   — SQLite — lesson 15
#   sub_agents.py      — loads prior turns into writer; saves after each answer
import session_store as session
from agent_log import LOG_FILE
from session_store import DB_PATH
from sub_agents import DEFAULT_OUTPUT_PATH, MODEL, WORKSPACE, run_manager

session.init_db()

print(f"Sub-agents + persistence with {MODEL} — empty line or Ctrl+C to quit.")
print(f"Sandbox: {WORKSPACE}")
print(f"Session DB: {DB_PATH}")
print(f"Log file: {LOG_FILE}")
n = session.turn_count()
if n:
    print(f"[session] resuming — {n} saved turn(s) in database")
    for turn in session.load_recent_turns(3):
        preview = turn["user_msg"][:60] + ("..." if len(turn["user_msg"]) > 60 else "")
        print(f"  • {preview}")
else:
    print("[session] fresh start — no prior turns")
print('Try: ask a question, quit, re-run, ask a follow-up like "what did I ask before?"')
while True:
    try:
        user = input("\n> ").strip()
    except (EOFError, KeyboardInterrupt):
        break
    if not user:
        break
    final = run_manager(user)
    print(f"\n--- answer ---\n{final}")
