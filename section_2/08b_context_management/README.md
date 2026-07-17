# Lesson 08b — Context management

## What this lesson is

When history grows too large, **drop the oldest turns** (never the system prompt) so the agent keeps working on long conversations.

Uses the token estimators from 08a with a soft budget well below the 8192 hard limit.

## New concept

**`trim_history()` + `MAX_HISTORY_TOKENS`** — soft budget leaves room for the model's reply.

## Prerequisites

[Lesson 08a — Token estimate](../08a_token_estimate/README.md)

## Run

```bash
python3 section_2/08b_context_management/08b_context_management.py
```

Chat a lot — watch for `[context] dropped N old message(s)`.

## What the script adds

- `MAX_HISTORY_TOKENS = 4000` — soft budget (8192 is the hard ceiling)
- `trim_history(history)` — pops index `1` (oldest non-system message) until under budget
- System prompt at index `0` is **never** trimmed

## What to watch for

```
[tokens] ~4200 / 4000 budget (8192 max)
[context] dropped 2 old message(s), ~3800 tokens remain
```

The model may "forget" very old turns — that's intentional.

## Checkpoint

Agent still works after 30+ turns without hitting context errors.

## Key code

```python
while len(history) > 1 and estimate_messages_tokens(history) > MAX_HISTORY_TOKENS:
    history.pop(1)  # keep system at index 0
```

## Next

[Lesson 09 — Planning](../09_planning/README.md)
