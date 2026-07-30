#!/usr/bin/env python3
# Step 18: Internal Docs MCP server — stdio transport, tools backed by local .md files.
#
# NEW in this lesson:
#   MCP server using the official Python SDK (mcp package)
#   stdio transport — host spawns this script, talks over stdin/stdout
#   tools/list + tools/call — same idea as lesson 04 TOOLS dict, standard wire format
#
# The markdown files live in docs/ next to this script — the MCP server IS the docs bundle.
# Production: docs/ might be synced from Notion/S3; locally it's just a folder.
#
# Run (host spawns this — don't run interactively unless testing):
#   python3 section_3/18_mcp/docs_mcp_server.py
import json
import re
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

# All employee docs must stay under this folder — same sandbox idea as lesson 10
DOCS_ROOT = Path(__file__).resolve().parent / "docs"
MAX_READ_CHARS = 8000
MAX_GREP_MATCHES = 25

server = Server("internal-docs-mcp")


def safe_doc_path(raw: str) -> Path | None:
    """Resolve a doc path and reject anything outside docs/."""
    rel = raw.strip().replace("\\", "/").lstrip("/")
    if rel.startswith("..") or "/../" in f"/{rel}/":
        return None
    if rel.startswith("docs/"):
        rel = rel[len("docs/"):]
    if not rel:
        return None
    root = DOCS_ROOT.resolve()
    try:
        resolved = (root / rel).resolve()
        resolved.relative_to(root)
    except ValueError:
        return None
    return resolved


def list_docs() -> str:
    if not DOCS_ROOT.is_dir():
        return json.dumps({"error": "docs/ folder missing"})
    names = sorted(p.name for p in DOCS_ROOT.glob("*.md"))
    return json.dumps({"docs": names, "count": len(names)}, indent=2)


def read_doc(path_arg: str) -> str:
    target = safe_doc_path(path_arg)
    if target is None:
        return json.dumps({"error": f"invalid path {path_arg!r} — use e.g. onboarding.md"})
    if not target.exists():
        return json.dumps({"error": f"not found: {path_arg}"})
    if not target.is_file():
        return json.dumps({"error": f"{path_arg!r} is not a file"})
    try:
        text = target.read_text(encoding="utf-8")
    except OSError as exc:
        return json.dumps({"error": str(exc)})
    if len(text) > MAX_READ_CHARS:
        text = text[:MAX_READ_CHARS] + f"\n\n[truncated — {MAX_READ_CHARS} chars]"
    return json.dumps({"path": target.name, "content": text}, indent=2)


def grep_docs(arg: str) -> str:
    """Arg format: pattern or pattern:filename — search one file or all docs."""
    if ":" in arg:
        pattern, _, file_part = arg.partition(":")
        pattern = pattern.strip()
        file_part = file_part.strip()
    else:
        pattern, file_part = arg.strip(), ""
    if not pattern:
        return json.dumps({"error": "pattern required — e.g. refund or refund:refunds-policy.md"})
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        return json.dumps({"error": f"invalid regex: {exc}"})

    if file_part:
        files = [safe_doc_path(file_part)]
        if files[0] is None:
            return json.dumps({"error": f"invalid file {file_part!r}"})
    else:
        files = sorted(DOCS_ROOT.glob("*.md"))

    hits: list[str] = []
    for file_path in files:
        if not file_path or not file_path.is_file():
            continue
        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except OSError:
            continue
        for num, line in enumerate(lines, 1):
            if regex.search(line):
                hits.append(f"{file_path.name}:{num}: {line}")
                if len(hits) >= MAX_GREP_MATCHES:
                    break
        if len(hits) >= MAX_GREP_MATCHES:
            break

    return json.dumps(
        {"pattern": pattern, "matches": hits, "count": len(hits)},
        indent=2,
    )


@server.list_tools()
async def list_tools() -> list[Tool]:
    """Advertise tools — host calls this after initialize (like TOOL_MENU in lesson 04)."""
    return [
        Tool(
            name="list_docs",
            description="List all internal employee markdown docs available in this MCP server.",
            inputSchema={"type": "object", "properties": {}},
        ),
        Tool(
            name="read_doc",
            description="Read one markdown doc by filename (e.g. onboarding.md, refunds-policy.md).",
            inputSchema={
                "type": "object",
                "properties": {
                    "path": {
                        "type": "string",
                        "description": "Filename under docs/, e.g. onboarding.md",
                    }
                },
                "required": ["path"],
            },
        ),
        Tool(
            name="grep_docs",
            description="Search docs for a regex pattern. Optional :filename to search one file.",
            inputSchema={
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "pattern or pattern:filename — e.g. refund:refunds-policy.md",
                    }
                },
                "required": ["query"],
            },
        ),
    ]


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    """Dispatch tool by name — same role as run_tool() in lesson 04."""
    if name == "list_docs":
        text = list_docs()
    elif name == "read_doc":
        text = read_doc(arguments.get("path", ""))
    elif name == "grep_docs":
        text = grep_docs(arguments.get("query", ""))
    else:
        text = json.dumps({"error": f"unknown tool: {name}"})
    return [TextContent(type="text", text=text)]


async def main() -> None:
    # stdio: read JSON-RPC from stdin, write responses to stdout — logs must go to stderr only
    async with stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            server.create_initialization_options(),
        )


if __name__ == "__main__":
    import asyncio

    asyncio.run(main())
