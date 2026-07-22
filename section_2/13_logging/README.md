# Lesson 13 — Logging

## What this lesson is

**Observability:** same sub-agent pipeline as lesson 12, but every important step is also written to a **log file** with timestamps.

Terminal `print()` = live monitoring while you watch.
`agent_log.py` = durable trace you can grep, share, and replay later.

## New concept

**Structured logging in a separate module** — `agent_log.py` appends one JSON line per event to `logs/agent.jsonl`.

Each user question gets a `run_id` so you can filter one full trace:

```json
{"ts": "2026-07-14T05:40:01+00:00", "run_id": "a1b2c3d4", "event": "turn_start", "question": "..."}
{"ts": "...", "run_id": "a1b2c3d4", "event": "handoff", "from_agent": "manager", "to_agent": "researcher"}
{"ts": "...", "run_id": "a1b2c3d4", "event": "tool_call", "agent": "researcher", "tool": "read_file", "arg": "notes/todo.md"}
{"ts": "...", "run_id": "a1b2c3d4", "event": "turn_end", "answer_chars": 412}
```

## File layout

| File | Role |
|------|------|
| `13_logging.py` | Entry script + input loop (**run this**) |
| `sub_agents.py` | Researcher / writer pipeline (lesson 12) |
| `agent_log.py` | Logging helpers — the one new idea in this lesson |

The harness imports `agent_log as log` and calls `log.handoff(...)`, `log.tool_call(...)` at hook points. Logging logic stays in one place.

## Prerequisites

- [Lesson 12 — Sub-agents](../12_sub_agents/README.md)

## Run

```bash
python3 section_2/13_logging/13_logging.py
```

Try: *What does notes/todo.md say about agents?*

Then inspect the log:

```bash
cat section_2/13_logging/logs/agent.jsonl
# or filter one run:
grep a1b2c3d4 section_2/13_logging/logs/agent.jsonl
```

## Prints vs logs

| | Terminal print | `agent_log.py` |
|---|----------------|----------------|
| **When** | Live, as it happens | Same moments, appended to file |
| **Purpose** | Human watching the run | Replay, debug, eval prep |
| **Survives** | Scrollback only | Stays on disk |
| **Format** | `[researcher] tool read_file(...)` | JSON with `ts`, `run_id`, `event` |

Lesson 12 already had prints. Lesson 13 adds the **log module** — not just more prints.

## Events logged

| Event | When |
|-------|------|
| `turn_start` | User submits a question |
| `handoff` | Manager → researcher, researcher → manager, manager → writer |
| `llm_start` / `llm_reply` | Each sub-agent API call |
| `tool_call` / `observation` | Researcher tool loop |
| `researcher_done` / `writer_done` | Sub-agent finished |
| `turn_end` | Final answer ready |

## Checkpoint

Ask one question, then reproduce the full agent trace from `logs/agent.jsonl` without re-running the model.

## Next

Lesson 14 — Human-in-the-loop: [14_human_in_loop](../14_human_in_loop/README.md).
