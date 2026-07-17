# Lesson 08a — Token estimate

## What this lesson is

Before you trim conversation history, you need to **measure** it. This lesson adds a rough token counter and logs prompt size against the model's 8192 context window.

No trimming yet — just visibility.

## New concept

**`estimate_tokens()`** — ~4 characters per token, good enough for budgeting.

## Prerequisites

[Lesson 07 — Error handling](../07_error_handling/README.md)

## Run

```bash
python3 section_2/08a_token_estimate/08a_token_estimate.py
```

Chat normally — watch the `[tokens]` line before each model call.

## What the script adds

- `MODEL_CONTEXT = 8192` — hard ceiling from LM Studio
- `estimate_tokens(text)` — `len(text) // 4`
- `estimate_messages_tokens(messages)` — sum content + ~4 overhead per message
- Prints `[tokens] ~N / 8192 max` before each LLM call

## Why measure first?

You can't trim intelligently if you don't know how big the prompt is. Lesson 08b uses these same functions to drop old turns.

## Try this

Have a long conversation (10+ turns) and watch the token count climb.

## Checkpoint

Explain why you measure prompt size *before* trimming, and why `// 4` is "good enough" for this course.

## Key code

```python
def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)
```

## Next

[Lesson 08b — Context management](../08b_context_management/README.md)
