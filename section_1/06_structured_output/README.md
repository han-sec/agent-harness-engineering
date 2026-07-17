# Lesson 06 — Structured output (JSON)

## What this lesson is

Force the model to reply with **parseable JSON**, then use Python to extract a field and drive real code (`get_weather(city)`).

Models are messy — this lesson teaches **defensive parsing + retry**, not prompt-and-hope.

## New concept

**Structured output:** `json.loads` + validate types + retry on failure.

## Prerequisites

[Lesson 05 — Multiple tools](../05_multi_tools/README.md)

## Run

```bash
python3 section_1/06_structured_output/06_structured_output.py
```

Try: *What's the weather in Tokyo?*

## What the script does

1. Separate JSON extraction step: ask model for `{"city": "..."}` only
2. `strip_json()` — handles markdown fences and extra chatter
3. `parse_city()` — validates dict shape and field types
4. On failure: append bad reply + retry message, up to `MAX_JSON_RETRIES`
5. On success: call `get_weather(city)` in plain Python

## What to watch for

```
[json attempt 1]
[parsed] 'Tokyo'
[result] Sunny, 28°C in Tokyo
```

## Checkpoint

Get reliable `{"city": "Tokyo"}` from a messy local model on attempt 1 most of the time.

## Key code

- `strip_json()` — pull `{...}` from wrappers
- `parse_city()` — return `None` on any failure
- `extract_city()` — retry loop

## Optional comparison

Run the appendix with the **same parser, bad prompt**:

[Lesson 06 appendix — Bad prompt](../06_appendix_bad_prompt/README.md)

Count `[json attempt N]` lines — good prompt usually wins on attempt 1.

## Next

[Lesson 07 — Error handling](../../section_2/07_error_handling/README.md)
