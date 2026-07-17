# Lesson 05 — Multiple tools

## What this lesson is

Same agent loop as lesson 04, but the model **chooses from a menu** of tools: weather, calculator, and clock.

The loop doesn't change — only the `TOOLS` registry and system prompt grow.

## New concept

**Tool menu in the system prompt** + multiple entries in `TOOLS`.

## Prerequisites

[Lesson 04 — Tools](../04_tools/README.md)

## Run

```bash
python3 section_1/05_multi_tools/05_multi_tools.py
```

## Try this

| Prompt | Expected tool |
|--------|---------------|
| Weather in Paris | `get_weather` |
| What is 15 * 7? | `calculate` |
| What time is it in UTC? | `get_time` |

## What the script adds

- `calculate(expr)` — safe-ish `eval` with a character whitelist
- `get_time(timezone)` — real clock via `zoneinfo`
- `TOOL_MENU` block in the system prompt listing all tools with examples

## Checkpoint

Add a fourth tool (e.g. `reverse_text`) without help — register it in `TOOLS` and update the menu.

## Key code

```python
TOOLS["get_weather"] = get_weather
TOOLS["calculate"] = calculate
TOOLS["get_time"] = get_time
```

## Next

[Lesson 06 — Structured output](../06_structured_output/README.md)
