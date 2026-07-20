# Lesson 10 — File agent

## What this lesson is

Same agent loop as lessons 07–08, but tools now **read real files** from a sandbox folder. The model must use tools to ground answers — not guess from memory.

## New concept

**File tools + path sandbox:** `read_file`, `list_dir`, `grep` under `workspace/` only, with `safe_path()` blocking traversal.

## Prerequisites

[Lesson 08b — Context management](../08b_context_management/README.md)

## Run

```bash
python3 section_2/10_file_agent/10_file_agent.py
```

## Sample workspace

```
workspace/
  readme.md
  notes/
    todo.md
    agents.md
```

The agent can only read inside `workspace/`. Paths like `../../etc/passwd` are rejected.

## Try this

| Prompt | Expected workflow |
|--------|-------------------|
| What does `notes/todo.md` say about agents? | `read_file` → answer from file |
| What's in the notes folder? | `list_dir:notes` |
| Find "harness" in notes | `grep:harness:notes` |

## The three tools

| Tool | Arg format | Example |
|------|------------|---------|
| `list_dir` | path (`.` for root) | `TOOL:list_dir:notes` |
| `grep` | `pattern:path` | `TOOL:grep:agents:notes` |
| `read_file` | path | `TOOL:read_file:notes/todo.md` |

## Troubleshooting Gemma / LM Studio

If you see `<|channel>thought` spam:

1. **Runtime layer** — Gemma's chat template adds channel tags (README §5). Your harness strips them with `strip_template_noise()`.
2. **Empty reply nudge** — if the model emits noise but no tool and no answer, Python sends a retry nudge instead of stopping.
3. **Path confusion** — use `.` or `notes/`, not `workspace/`. The system prompt includes a live directory listing.

## Guard rails (not optional)

| Risk | Harness fix |
|------|-------------|
| Path traversal (`../`) | `safe_path()` + `relative_to(WORKSPACE)` |
| Huge file fills context | `MAX_READ_CHARS` truncation |
| Too many grep hits | `MAX_GREP_MATCHES` cap |
| Binary / non-UTF-8 | Error string, not crash |
| Writes / deletes | **Not in this lesson** — read-only only |

## What to watch for

```
[tool] list_dir('notes')
[observation] 'notes/agents.md\nnotes/todo.md'
[tool] read_file('notes/todo.md')
[observation] '# Todo\n\n- Learn agent harness...'
```

Large observations print truncated in the terminal preview; full text still goes to the model in history.

## Checkpoint

Ask *"What does notes/todo.md say about agents?"* — answer must come from file content, not hallucination.

## Key code

- `WORKSPACE` — sandbox root next to the script
- `safe_path()` / `normalize_path_arg()` — sandbox + path aliases
- `strip_template_noise()` — cope with Gemma channel tags
- `is_empty_reply()` + nudge — don't accept noise as a final answer
- `read_file` / `list_dir` / `grep` — read-only tools

## Memory note

File content enters **conversation history** as Observations (lesson 03). It is not a separate cache. `trim_history` (08b) may drop old reads on long chats.

## Next

[Lesson 11 — Web agent](../../section_2/11_web_agent/README.md)
