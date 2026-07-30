# Lesson 18 — Internal Docs MCP Server

Build a **Model Context Protocol (MCP)** server that exposes employee handbook markdown as tools any AI host (Cursor, Claude Desktop, your capstone) can call.

## One new idea

Lessons 01–17: tools are **Python functions in the same process** (`TOOLS` dict + `run_tool()`).

Lesson 18: tools live in a **separate MCP server process**. The host talks JSON-RPC over **stdio** — same think → act → observe loop, standardized plug.

## Yes — the MCP contains the markdown files

```
section_3/18_mcp/
  docs_mcp_server.py   ← MCP server (this is "the MCP")
  docs/                ← employee .md files live HERE
    onboarding.md
    refunds-policy.md
    deploy-runbook.md
    api-auth.md
    index.md
    team-faq.md
  18_mcp.py            ← smoke test client
```

The server reads only from `docs/`. When you deploy, you can:

- Keep md files in the repo (this lesson)
- Sync `docs/` from Notion/S3 on deploy (production)
- Point `DOCS_ROOT` at another path via env var (easy extension)

The **MCP server is the docs bundle + tool handlers** — not the LLM, not the planner.

## Prerequisites

```bash
cd section_3/18_mcp
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Verify it works (CLI)

```bash
python3 18_mcp.py
```

Expected:

```
PASS initialize
PASS tools/list (3): list_docs, read_doc, grep_docs
PASS list_docs — 6 file(s): [...]
PASS read_doc — refunds-policy.md starts: ...
PASS grep_docs — N match(es)

=== ALL CHECKS PASSED ===
```

Print Cursor config:

```bash
python3 18_mcp.py --cursor-config
```

## Connect to Cursor

1. Run `python3 18_mcp.py --cursor-config` and copy the JSON
2. Cursor → Settings → MCP → add server `internal-docs`
3. Restart MCP
4. Ask: *"Use internal-docs list_docs"* or *"Read refunds-policy.md via internal-docs"*

## Architecture

```
Cursor (host)
  → spawns docs_mcp_server.py (stdio)
  → initialize handshake
  → tools/list → list_docs, read_doc, grep_docs
  → tools/call read_doc { "path": "onboarding.md" }
  → JSON result → model uses as context
```

Compare to lesson 17 capstone:

| Lesson 17 | Lesson 18 |
|-----------|-----------|
| `read_file` in `sub_agents.py` | `read_doc` in MCP server |
| Same Python process | Child process over stdin/stdout |
| `TOOL:read_file:path` prompt parsing | Host uses native MCP / tool UI |

## The three tools

| Tool | Same as lesson… | Args |
|------|-----------------|------|
| `list_docs` | `list_dir` | (none) |
| `read_doc` | `read_file` | `path`: e.g. `onboarding.md` |
| `grep_docs` | `grep` | `query`: e.g. `refund` or `refund:refunds-policy.md` |

## How to create your own MCP (checklist)

Copy this lesson folder and change four things:

1. **`docs/`** — put your markdown (or change `DOCS_ROOT` to your data path)
2. **`@server.list_tools()`** — advertise tool names + JSON Schema for args
3. **`@server.call_tool()`** — dispatch `name` → your Python function
4. **Host config** — command + args pointing at your server script

Minimal server skeleton:

```python
from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

server = Server("my-server")

@server.list_tools()
async def list_tools():
    return [Tool(name="hello", description="...", inputSchema={"type": "object", "properties": {}})]

@server.call_tool()
async def call_tool(name: str, arguments: dict):
    return [TextContent(type="text", text="Hello from MCP")]

async def main():
    async with stdio_server() as (read, write):
        await server.run(read, write, server.create_initialization_options())
```

Rules:

- **stdout** = JSON-RPC only (never `print()` debug to stdout — use stderr)
- **Tools return** `list[TextContent]` with `type="text"`
- **Sandbox paths** — keep `safe_doc_path()` pattern for anything on disk
- **Smoke test** — copy `18_mcp.py` client pattern to verify without Cursor

## Map to your finding-database MCP

Your security findings server (`finding-database/scripts/mcp_server.py`) is the same pattern at larger scale:

| internal-docs (lesson 18) | finding-database (yours) |
|---------------------------|---------------------------|
| 3 tools, md on disk | 5 tools, Qdrant + embeddings |
| `docs/*.md` | `data/findings/*.json` + vector index |
| No extra deps beyond `mcp` | `qdrant-client`, `sentence-transformers` |

Verify yours: `python scripts/smoke_test_mcp.py --fast`

## What's next (lesson 19+)

- **19_mcp_client** — call this MCP from capstone `run_researcher()` instead of in-process `read_file`
- **20_deploy** — run MCP + harness on VPS, cloud LLM API

## Break it on purpose

1. Delete `docs/refunds-policy.md` → `read_doc` returns JSON error (not a crash)
2. Ask for `../etc/passwd` → `safe_doc_path` blocks it
3. Run `python3 docs_mcp_server.py` alone — it waits silently (stdio has no host); use `18_mcp.py` instead

## Checkpoint

- [ ] Explain why md files sit inside the MCP project folder
- [ ] Run `18_mcp.py` and get ALL CHECKS PASSED
- [ ] Connect to Cursor and call `list_docs` successfully
- [ ] Name the three MCP primitives used here (initialize, tools/list, tools/call)
