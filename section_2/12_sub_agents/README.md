# Lesson 12 — Sub-agents

## What this lesson is

**Delegation:** one Python manager runs two sub-agents — each with **its own history** and **its own API calls** to the same Gemma model.

You only chat with the manager. Researcher and writer work in isolated boxes; the manager passes a **facts string** between them.

## New concept

**Sub-agents = separate `history` + separate `stream_chat` calls + handoff via Python.**

Not a second LM Studio process — same model, different context per role.

## Prerequisites

- [Lesson 10 — File agent](../10_file_agent/README.md) (researcher reuses file tools)

## Run

```bash
python3 section_2/12_sub_agents/12_sub_agents.py
```

Try: *What does notes/todo.md say about agents?*

## Watch the pipeline

```
[manager] received user question
[manager] → delegating to researcher
[researcher] calling model...
[researcher] tool list_dir('.')
[researcher] tool read_file('notes/todo.md')
[researcher] returning facts (...)
[manager] ← researcher done
[manager] → delegating to writer
[writer] calling model...
[manager] ← writer done
--- answer ---
...
```

## The three roles

| Role | Talks to user? | Tools | Output |
|------|----------------|-------|--------|
| **Manager** | Yes (via final print) | None (Python only) | Orchestrates |
| **Researcher** | No | `list_dir`, `grep`, `read_file` | Bullet facts |
| **Writer** | No (reply shown to user) | None | Plain-language answer |

## Same model, different boxes

```
You → run_manager()
        → run_researcher()  →  history A  →  POST Gemma
        → run_writer(facts) →  history B  →  POST Gemma
      → print answer
```

Researcher history **does not** appear in writer history — only the `facts` string is copied across.

## Why eval matters (lesson 16)

This lesson is a **minimal** sub-agent system — enough to feel the pattern.

It becomes **useful at scale** when you can **measure** each box:

| Eval question | Lesson 16 |
|---------------|-----------|
| Did researcher find the right file? | Pass/fail test cases |
| Did writer stay faithful to facts? | Compare output vs researcher Observations |
| Did the pipeline beat one monolithic agent? | Score both designs on same prompts |

Sub-agents + eval = tune researcher prompts/tools separately from writer — without guessing.

## Checkpoint

One user question → see `[researcher]` tool calls → see `[writer]` final answer grounded in file content.

## Key code

- `run_researcher()` — isolated history + tool loop
- `run_writer()` — isolated history, facts injected, no tools
- `run_manager()` — Python handoff

## Next

[Lesson 13 — Logging](../13_logging/README.md): log every sub-agent call for replay and eval prep.
