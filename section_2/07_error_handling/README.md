# Lesson 07 — Error handling

## What this lesson is

Make the agent **resilient**. Tool failures become Observations (error strings), not crashes. Connection errors to LM Studio are caught. The inner loop is capped with `MAX_TOOL_ROUNDS`.

## New concept

**Errors → Observations + `MAX_TOOL_ROUNDS`.** The agent recovers from bad inputs instead of spinning forever.

## Prerequisites

[Lesson 06 — Structured output](../../section_1/06_structured_output/README.md)

## Run

```bash
python3 section_2/07_error_handling/07_error_handling.py
```

## Try this

| Prompt | What happens |
|--------|--------------|
| Weather in Tokyo | Normal success |
| Weather in *(empty)* or trick empty city | Tool returns error string → model retries or explains |
| Stop LM Studio mid-chat | `[error] Cannot reach LM Studio` — no traceback crash |

## What the script adds

- Tools return `"Error: ..."` strings instead of raising (where appropriate)
- `run_tool()` wrapped in `try/except` for unexpected crashes
- `urllib.error.URLError` caught in `stream_chat()`
- `for round_num in range(1, MAX_TOOL_ROUNDS + 1)` — hard cap on tool rounds

## What to watch for

```
[tool] get_weather('')
[observation] 'Error: city cannot be empty'
```

The model sees the error as a user message and can fix its argument.

## Checkpoint

Agent recovers when `get_weather("")` fails — no Python traceback, no infinite loop.

## Key code

- `MAX_TOOL_ROUNDS = 5`
- Error strings in tool functions (not exceptions)
- `try/except` around `fn(arg)` and `urlopen`

## Next

[Lesson 08a — Token estimate](../08a_token_estimate/README.md)
