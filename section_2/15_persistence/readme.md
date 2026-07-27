# Lesson 15 — Persistence

## What this lesson is

**Memory across runs:** when you quit and restart the script, your conversation is still in a **SQLite database** — not lost like lesson 03's in-memory `history` list.

## Persistence vs context (08b)

| | Lesson 08b (`trim_history`) | Lesson 15 (`session_store`) |
|---|---------------------------|----------------------------|
| **What** | Drop old messages in RAM | Save Q&A to disk |
| **Survives restart?** | No | **Yes** |
| **Scope** | One sub-agent's `history` list | User ↔ assistant turns at manager level |
| **Tool** | Python list + token budget | SQLite (`stdlib`) |

Both can apply together: trim during a long researcher loop **and** persist finished turns to DB.

## New concept

**`save_turn()` / `load_recent_turns()` → `data/session.db`**

After each answer, Python writes:

```
user question  +  final answer  →  SQLite
```

On the next run, prior turns load into the **writer** sub-agent as context.

## Prerequisites

- [Lesson 14 — Human-in-the-loop](../14_human_in_loop/README.md)

## Run

```bash
python3 section_2/15_persistence/15_persistence.py
```

**Checkpoint:**

1. Ask: *What does notes/todo.md say about agents?*
2. Quit (empty line or Ctrl+C)
3. Re-run the script — see `[session] resuming — 1 saved turn(s)`
4. Ask: *What was my previous question?* — writer should use saved context

Inspect the database:

```bash
sqlite3 section_2/15_persistence/data/session.db "SELECT id, user_msg FROM turns;"
```

## File layout

| File | Role |
|------|------|
| `15_persistence.py` | Entry + resume banner |
| `session_store.py` | SQLite — **lesson 15** |
| `sub_agents.py` | Loads prior turns → writer; saves after answer |

## What is NOT persisted (on purpose)

- Researcher tool traces (too large; use lesson 13 logs for replay)
- Writer/researcher inner `history` lists (fresh each turn)

Only **user question + final answer** — enough to resume a chat.

## Next

Lesson 16 — Evaluation: [16_evaluation](../16_evaluation/README.md).
