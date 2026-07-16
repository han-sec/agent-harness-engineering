# Lesson 03 — Conversation memory

## What this lesson is

A turn-based chatbot. Each user message appends to a **`history` list** that is sent on every request — that's how the model "remembers" without a database.

Combines lesson 02's streaming with a reusable `stream_chat()` helper.

## New concept

**Memory = your Python list.** The model has no memory of its own; you resend the full conversation every call.

## Prerequisites

[Lesson 02 — Streaming](../02_stream/README.md)

## Run

```bash
python3 section_1/03_conversation/03_conversation.py
```

Type messages at the `>` prompt. Empty line or Ctrl+C to quit.

## Try this

1. "My name is Han."
2. "What's my name?"

The model answers from history — not from any stored state in LM Studio.

## What the script does

```
User types → append to history → stream_chat(history) → append assistant reply → repeat
```

`stream_chat()` returns the full reply string (while also printing tokens live).

## Checkpoint

Explain why the model "remembers" your name even though LM Studio stores nothing between script runs.

## Key code

- `history = [{"role": "system", ...}, ...]` — grows each turn
- `stream_chat(messages)` — copied into every later lesson

## Next

[Lesson 04 — Tools](../04_tools/README.md)
