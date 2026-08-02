# Lesson 19 — MCP client

Wire the capstone harness to **lesson 18's docs MCP server** instead of in-process file tools. One new idea: **spawn MCP over stdio and call `tools/call` from Python**.

## Prerequisite

Complete [lesson 18](../18_mcp/README.md). The harness spawns `section_3/18_mcp/docs_mcp_server.py` — you do not start it manually.

```bash
python3 section_3/18_mcp/18_mcp.py          # smoke test server
```

## Setup

On macOS Homebrew Python, `pip` may not be on your PATH — use `python3 -m pip` instead.

```bash
cd section_3/19_mcp_client
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt   # installs mcp>=1.0.0
lms server start && lms ps                   # LM Studio + loaded model
python3 19_mcp_client.py
```

Lesson 18's MCP server also needs its venv (one-time):

```bash
cd section_3/18_mcp
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 18_mcp.py                            # smoke test
```

## The three loops (read this first)

People often confuse "inner loop" with sub-agent handoffs. There are **three** layers:

```
┌─────────────────────────────────────────────────────────────┐
│ OUTER — 19_mcp_client.py                                    │
│   while True: input → run_manager() → print answer          │
│   Python only. No LLM tool loop here.                       │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│ MIDDLE — run_manager() in sub_agents.py                     │
│   planner  →  researcher  →  writer                         │
│   Sequential handoffs. Still no tool loop at manager level. │
└─────────────────────────────────────────────────────────────┘
                              │
              researcher only ▼
┌─────────────────────────────────────────────────────────────┐
│ INNER — run_researcher()                                    │
│   while rounds:                                             │
│     LLM reply → TOOL:grep_docs:… → MCP tools/call           │
│     Observation → LLM again … until facts (no TOOL line)    │
│   DocsMcpSession wraps the whole researcher run.            │
└─────────────────────────────────────────────────────────────┘
```

**Answer to the common question:** The inner loop is **not** between planner and researcher, or researcher and writer. Sub-agents do not call each other — **Python manager** calls them one after another. Only **researcher** has the LLM ↔ tool cycle.

Planner has a **retry loop** for JSON (lesson 06/09), not tools. Writer is a **single** LLM call.

## What changed from lesson 17

| Piece | Lesson 17 | Lesson 19 |
|-------|-----------|-----------|
| Researcher tools | `read_file`, `list_dir`, `grep` in Python | `list_docs`, `read_doc`, `grep_docs` via MCP |
| Tool execution | `run_tool(reply, RESEARCHER_TOOLS)` | `run_mcp_tool(reply, mcp)` |
| Docs location | `workspace/docs/` | `18_mcp/docs/` (server process) |
| Manager / writer / session / HITL | Same | Same |

## File-by-file walkthrough

Read in this order.

### 1. `requirements.txt`

First third-party dependency for the **client** side (server was lesson 18). Same `mcp` package — host and server both speak MCP JSON-RPC.

### 2. `mcp_client.py` — **the one new module**

This is the lesson's core.

- `docs_mcp_session()` — async context manager (same pattern as `18_mcp.py` smoke test)
  - `async with` in `19_mcp_client.py`: spawn server at chat start, close on quit
  - Prints `[mcp] session started` / `[mcp] session closed`
  - `mcp_call(session, name, args)`: `tools/call`, return text

**Why one session per chat?** Spawning stdio MCP has process overhead. Reuse one subprocess for all questions in a session; shut it down when the user exits so no zombie processes linger.

### 3. `sub_agents.py` — capstone pipeline, MCP researcher

Copied from `17_capstone/sub_agents.py` with surgical edits:

| Function | Role |
|----------|------|
| `run_manager_async()` | Outer orchestration — handoffs only |
| `run_planner()` | JSON plan, guard rail (no tools) |
| `_run_researcher_async()` | **Inner loop** — reuses chat-level MCP session |
| `run_mcp_tool()` | Replaces `run_tool()` for researcher |
| `run_writer()` | Single LLM call on facts |
| `write_file()` | HITL save to `output/` (still local Python, not MCP) |

Prompts now list MCP tool names. `DOCS_SNAPSHOT` reads `18_mcp/docs/*.md` at import (for planner context) without spawning MCP.

### 4. `19_mcp_client.py` — entry point

Same pattern as `17_capstone.py`:

- `asyncio.run(run_interactive())` — MCP session wraps the whole `while True` loop
- `session.init_db()`
- `while True`: read user input → `run_manager()` → print
- `help` / `quit` shortcuts

Checks that `docs_mcp_server.py` exists before starting.

### 5. Support files (unchanged from 17)

| File | Purpose |
|------|------|
| `agent_log.py` | JSONL trace — now logs `mcp read_doc` style tool lines |
| `human_confirm.py` | Approve `write_file` |
| `session_store.py` | SQLite prior turns → writer context |
| `harness_routes.py` | `help` without LLM; docs listing from `18_mcp/docs` |

## Tool line mapping

Model still emits lesson-04 style lines; Python translates to MCP:

| Model emits | MCP call |
|-------------|----------|
| `TOOL:list_docs:_` | `list_docs` `{}` |
| `TOOL:read_doc:refunds-policy.md` | `read_doc` `{"path": "refunds-policy.md"}` |
| `TOOL:grep_docs:refund` | `grep_docs` `{"query": "refund"}` |
| `TOOL:grep_docs:refund:refunds-policy.md` | `grep_docs` `{"query": "refund:refunds-policy.md"}` |

## What to watch in the terminal

A normal doc question should show:

```
[mcp] session started → docs_mcp_server.py (stdio)
[manager] → planner
...
[manager] → researcher (inner MCP loop runs inside)
[researcher] mcp grep_docs('refund')
...
Bye.
[mcp] session closed
```

If you see `[researcher] mcp ...`, lesson 19 is working — tools left the harness process and hit lesson 18.

## Try it

```
What is the refund window?
Give me an overview of internal documentation
help
```

## Checkpoint

- [ ] `18_mcp.py` smoke test passes
- [ ] `19_mcp_client.py` starts and shows MCP server path
- [ ] Doc question prints `[researcher] mcp ...` lines
- [ ] Answer cites real doc filenames
- [ ] `logs/agent.jsonl` has `tool_call` events with MCP tool names

## Next

Lesson 20 — deploy harness + MCP to a VPS with env-based config.
