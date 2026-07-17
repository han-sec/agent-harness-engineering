# Lesson 09 — Planning (plan-then-execute)

## What this lesson is

**Two-phase agent control flow.** Phase 1: model writes a JSON plan (no tools). Phase 2: model executes step-by-step with the normal tool loop.

Same idea as Plan mode in Cursor or Claude Code — but you build the mode switch in Python.

## New concept

**Plan-then-execute:** different system prompts per phase + guard rails so tools never run during planning.

## Prerequisites

- [Lesson 06 — Structured output](../../section_1/06_structured_output/README.md) (JSON parse + retry)
- [Lesson 08b — Context management](../08b_context_management/README.md) (full agent loop)

## Run

```bash
python3 section_2/09_planning/09_planning.py
```

Try: *Compare weather in Tokyo and London, then say which is warmer.*

## The two phases

### Phase 1 — Plan

- `PLAN_SYSTEM` — reply with JSON only, list tools but do NOT call them
- `request_plan()` — calls LLM, **never** calls `run_tool()`
- If model emits `TOOL:` anyway → `[guard]` warning, ignored
- `parse_plan()` validates JSON shape + tool names
- Plan stored in `current_plan` (Python-owned, outside history)
- **`confirm_execute()`** — you approve with `y` before any tools run (preview of lesson 14)

### Phase 2 — Execute (after you approve)

- `build_execute_system()` — injects full plan, marks current step
- `execute_step()` — inner tool loop per step (from lessons 07–08)
- Prior step observations passed forward for compare/s summarize steps

## What to watch for

You should see **`[plan phase]` and numbered steps before any `[tool]` lines**:

```
[plan phase] asking model for plan (attempt 1)
[plan] goal: Compare weather in two cities
[plan]   1. Get weather for Tokyo (suggested: get_weather('Tokyo'))
[plan]   2. Get weather for London ...
Run this plan? [y/n] y

[execute phase] starting — tools enabled
[execute] step 1/3: Get weather for Tokyo
[tool] get_weather('Tokyo')
```

## Harness vs prompt

| Layer | Role |
|-------|------|
| **Prompt** | Asks model to plan first |
| **Python** | Refuses to run tools in phase 1; **waits for your y/n**; drives step loop in phase 2 |

You don't trust the model to respect mode boundaries — you enforce them in code.

## Checkpoint

Ask a multi-step question → visible plan appears before tool execution.

## Key code

- `confirm_execute()` — human gate before execute (lesson 14 preview)
- `request_plan()` — phase 1 guard rail
- `parse_plan()` / `strip_json()` — from lesson 06
- `build_execute_system()` — phase 2 context
- `execute_plan()` — step driver loop

## Next

[Lesson 10 — File agent](../10_file_agent/README.md)
