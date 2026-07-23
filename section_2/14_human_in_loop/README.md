# Lesson 14 — Human-in-the-loop

## What this lesson is

**Safety gate:** before the agent writes a file, **Python pauses and asks you** — not the LLM.

This is **not** the model adding “please approve” to its reply. Your harness calls `input()` and blocks until you type `y` or `n`.

## New concept

**Human-in-the-loop = `confirm_action()` in Python before destructive tools.**

```python
if not confirm_action("Write 412 chars to output/summary.md?"):
    return "Error: write rejected by human"
target.write_text(content)
```

Read tools (`read_file`, `grep`) run freely. **Write** tools wait for you.

## Who asks whom?

| | Who prompts? | Mechanism |
|---|------------|-----------|
| **Wrong mental model** | LLM asks user in chat | Model might skip it or hallucinate approval |
| **This lesson** | Python asks user in terminal | Deterministic — no write without `y` |

## Prerequisites

- [Lesson 13 — Logging](../13_logging/README.md)

## Run

```bash
python3 section_2/14_human_in_loop/14_human_in_loop.py
```

Try: *What does notes/todo.md say about agents?*

After the answer, you'll see:

```
[hitl] Write 412 chars to output/summary.md?
[hitl] Approve? [y/N]:
```

- Type **`y`** → file written to `workspace/output/summary.md`
- Type **`n`** or Enter → write skipped, logged as `approval_denied`

## File layout

| File | Role |
|------|------|
| `14_human_in_loop.py` | Entry script |
| `human_confirm.py` | `confirm_action()` — **lesson 14** |
| `sub_agents.py` | `write_file()` calls confirm before disk write |
| `agent_log.py` | Logs `approval_requested`, `approval_granted`, `approval_denied` |

## Watch the pipeline

```
[manager] ← writer done
[manager] offer to save answer → output/summary.md
[hitl] Write 412 chars to output/summary.md?
[hitl] Approve? [y/N]: y
[hitl] approved
[manager] Wrote 412 chars to output/summary.md
```

## Checkpoint

Run once, reject the save (`n`) — confirm no file appears and log shows `approval_denied`. Run again, approve (`y`) — confirm `workspace/output/summary.md` exists.

## Next

Lesson 15 — Persistence: [15_persistence](../15_persistence/README.md).
