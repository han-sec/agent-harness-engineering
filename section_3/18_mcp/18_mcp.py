# Step 18: MCP — verify the internal-docs MCP server and print Cursor config.
#
# Usage:
#   cd section_3/18_mcp && python3 -m venv .venv && source .venv/bin/activate
#   pip install -r requirements.txt
#   python3 section_3/18_mcp/18_mcp.py              # smoke test (default)
#   python3 section_3/18_mcp/18_mcp.py --cursor-config  # print MCP config snippet
import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PYTHON = ROOT / ".venv/bin/python"
SERVER = ROOT / "docs_mcp_server.py"


def print_cursor_config() -> None:
    """Show what to paste into Cursor MCP settings."""
    py = PYTHON if PYTHON.is_file() else Path(sys.executable)
    cfg = {
        "mcpServers": {
            "internal-docs": {
                "command": str(py.resolve()),
                "args": [str(SERVER.resolve())],
            }
        }
    }
    print("Add to Cursor → Settings → MCP (adjust python path if no .venv):\n")
    print(json.dumps(cfg, indent=2))
    print("\nThen restart MCP and ask: 'Use list_docs on internal-docs'")


async def smoke_test() -> int:
    """Spawn server over stdio, run initialize + tools/list + one read."""
    try:
        from mcp import ClientSession, StdioServerParameters
        from mcp.client.stdio import stdio_client
    except ImportError:
        print("FAIL: pip install -r requirements.txt (needs mcp package)", file=sys.stderr)
        return 1

    if not SERVER.is_file():
        print(f"FAIL: server not found: {SERVER}", file=sys.stderr)
        return 1

    py = str(PYTHON if PYTHON.is_file() else sys.executable)
    params = StdioServerParameters(command=py, args=[str(SERVER)])

    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            print("PASS initialize")

            tools = await session.list_tools()
            names = [t.name for t in tools.tools]
            print(f"PASS tools/list ({len(names)}): {', '.join(names)}")

            listing = await session.call_tool("list_docs", {})
            data = json.loads(listing.content[0].text)
            print(f"PASS list_docs — {data.get('count')} file(s): {data.get('docs')}")

            read_result = await session.call_tool(
                "read_doc", {"path": "refunds-policy.md"}
            )
            doc = json.loads(read_result.content[0].text)
            preview = (doc.get("content") or "")[:80].replace("\n", " ")
            print(f"PASS read_doc — refunds-policy.md starts: {preview!r}...")

            grep_result = await session.call_tool(
                "grep_docs", {"query": "14 days"}
            )
            grep_data = json.loads(grep_result.content[0].text)
            print(f"PASS grep_docs — {grep_data.get('count')} match(es)")

    print("\n=== ALL CHECKS PASSED ===")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Lesson 18 — internal docs MCP")
    parser.add_argument(
        "--cursor-config",
        action="store_true",
        help="Print Cursor mcpServers JSON snippet",
    )
    args = parser.parse_args()
    if args.cursor_config:
        print_cursor_config()
        return 0
    return asyncio.run(smoke_test())


if __name__ == "__main__":
    sys.exit(main())
