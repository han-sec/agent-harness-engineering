# Same MCP client as lesson 19 — spawns lesson 18 docs server over stdio.
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

DOCS_MCP_ROOT = Path(__file__).resolve().parent.parent.parent / "section_3" / "18_mcp"
DOCS_MCP_PYTHON = DOCS_MCP_ROOT / ".venv/bin/python"
DOCS_MCP_SERVER = DOCS_MCP_ROOT / "docs_mcp_server.py"

MCP_TOOL_NAMES = frozenset({"list_docs", "read_doc", "grep_docs"})


def _server_params() -> StdioServerParameters:
    if not DOCS_MCP_SERVER.is_file():
        raise FileNotFoundError(f"MCP server not found: {DOCS_MCP_SERVER}")
    python = DOCS_MCP_PYTHON if DOCS_MCP_PYTHON.is_file() else Path("python3")
    return StdioServerParameters(
        command=str(python),
        args=[str(DOCS_MCP_SERVER.resolve())],
    )


@asynccontextmanager
async def docs_mcp_session():
    print("[mcp] session started → docs_mcp_server.py (stdio)")
    try:
        async with stdio_client(_server_params()) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                yield session
    finally:
        print("[mcp] session closed")


async def mcp_call(session: ClientSession, name: str, arguments: dict) -> str:
    result = await session.call_tool(name, arguments)
    if not result.content:
        return "Error: empty MCP result"
    block = result.content[0]
    return block.text if hasattr(block, "text") else str(block)


def tool_line_to_mcp_args(name: str, arg: str) -> dict:
    if name == "list_docs":
        return {}
    if name == "read_doc":
        path = arg.strip()
        if path.startswith("docs/"):
            path = path[len("docs/"):]
        return {"path": path}
    if name == "grep_docs":
        return {"query": arg.strip()}
    return {}


def mcp_arg_preview(name: str, arguments: dict) -> str:
    if name == "list_docs":
        return "_"
    if name == "read_doc":
        return arguments.get("path", "")
    if name == "grep_docs":
        return arguments.get("query", "")
    return str(arguments)