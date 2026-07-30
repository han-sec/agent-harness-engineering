# Step 19: MCP client — capstone harness calls lesson 18 docs server over stdio.
#
#   mcp_client.py   → spawn MCP server, tools/call
#   sub_agents.py   → same pipeline as 17; researcher uses MCP inner loop
#   section_3/18_mcp/docs_mcp_server.py  → must exist (lesson 18)
#
# MCP lifecycle: harness starts server when chat opens, closes when user quits.
#
# Usage:
#   cd section_3/19_mcp_client && python3 -m pip install -r requirements.txt
#   python3 section_3/18_mcp/18_mcp.py
#   python3 section_3/19_mcp_client/19_mcp_client.py
import asyncio
import sys
from pathlib import Path

import session_store as session
from agent_log import LOG_FILE
from harness_routes import builtin_answer, print_welcome
from mcp_client import DOCS_MCP_ROOT, DOCS_MCP_SERVER, docs_mcp_session
from sub_agents import MODEL, run_manager_async

ROOT = Path(__file__).resolve().parent


async def run_interactive() -> int:
    session.init_db()
    print("Internal Docs Q&A — MCP client (lesson 19)")
    print(f"Model: {MODEL}")
    print(f"MCP server: {DOCS_MCP_SERVER}")
    print(f"Docs data: {DOCS_MCP_ROOT / 'docs'}")
    print(f"Logs: {LOG_FILE}")
    print_welcome()
    print("Type quit to exit.\n")

    # One MCP subprocess for the whole chat — closed when this block exits
    async with docs_mcp_session() as mcp:
        while True:
            try:
                user_msg = (await asyncio.to_thread(input, "You: ")).strip()
            except (EOFError, KeyboardInterrupt):
                print("\nBye.")
                return 0
            if not user_msg:
                continue
            if user_msg.lower() in ("quit", "exit", "q"):
                print("Bye.")
                return 0
            if user_msg.lower() in ("help", "?", "h"):
                print(f"\n{builtin_answer(user_msg)}\n")
                continue
            print()
            await run_manager_async(user_msg, mcp, eval_mode=False)
            print()

    return 0


def main() -> int:
    if not DOCS_MCP_SERVER.is_file():
        print(f"FAIL: lesson 18 server missing: {DOCS_MCP_SERVER}", file=sys.stderr)
        return 1
    return asyncio.run(run_interactive())


if __name__ == "__main__":
    sys.exit(main())
