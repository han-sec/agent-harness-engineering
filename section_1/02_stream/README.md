# Lesson 02 — Streaming (SSE)

## What this lesson is

Same endpoint as lesson 01, but with `"stream": true`. Tokens arrive **one at a time** over Server-Sent Events (SSE) instead of in one big JSON blob.

Every chat UI you've used does this — now you see the wire format.

## New concept

**Streaming = open HTTP connection + `data: {json}` lines**, ending with `data: [DONE]`.

## Prerequisites

[Lesson 01 — Chat](../01_chat/README.md)

## Run

```bash
python3 section_1/02_stream/02_stream.py
```

## What the script does

1. Sends the same chat request with `"stream": true`
2. Reads the response line-by-line
3. Strips the `data: ` prefix from each SSE line
4. Parses each chunk's `choices[0].delta.content` and prints immediately

## Try this

- Compare total wait time vs *perceived* speed vs lesson 01
- Add `print(repr(line))` before parsing to see raw SSE bytes

## What to watch for

```
data: {"choices":[{"delta":{"content":"Hello"}}]}
data: [DONE]
```

Non-`data:` lines are skipped (blank lines, comments).

## Checkpoint

Explain why streaming *feels* faster even when total generation time is similar.

## Key terms

| Term | Meaning |
|------|---------|
| **SSE** | Server-Sent Events — one JSON object per line over an open connection |
| **Delta** | Incremental chunk; streaming uses `delta`, non-streaming uses `message` |

## Next

[Lesson 03 — Conversation](../03_conversation/README.md)
