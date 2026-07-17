# Lesson 06 appendix — Bad prompt (optional)

## What this lesson is

**Same parsing code as lesson 06.** Only the system prompt is vague — no format line, no example.

Run both scripts with the same question and compare how many `[json attempt N]` retries you need.

## Why it exists

You are **not training** the model. You are instructing it at inference time. Examples + exact format in the prompt raise the odds of parseable JSON on attempt 1.

This proves the difference between **prompt engineering** and **harness engineering** — you still need the parser either way.

## Prerequisites

[Lesson 06 — Structured output](../06_structured_output/README.md) (read first)

## Run both and compare

```bash
python3 section_1/06_structured_output/06_structured_output.py
python3 section_1/06_appendix_bad_prompt/06_appendix_bad_prompt.py
```

Use the same input each time, e.g. *What's the weather in Tokyo?*

## What differs

| | Good prompt (06) | Bad prompt (appendix) |
|---|------------------|----------------------|
| Format spec | `{"city": "CityName"}` + example | "Reply in JSON" (vague) |
| Retry message | Shows exact shape | "Try again" (vague) |
| Parser | Identical | Identical |

## Checkpoint

Explain why the bad prompt causes more retries even though `parse_city()` never changed.

## Next

Back to the main path: [Lesson 07 — Error handling](../../section_2/07_error_handling/README.md)
