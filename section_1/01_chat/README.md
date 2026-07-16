# Lesson 01 — Chat completion over HTTP

## What this lesson is

Your first call to a local LLM. No agent loop, no memory — just **one HTTP POST** and a printed reply.

This is the foundation everything else builds on: if you understand this request, every SDK and framework later will feel familiar.

## New concept

**Inference = HTTP POST + JSON.** You send a `messages` list; LM Studio runs the model and returns `choices[0].message.content`.

## Prerequisites

- LM Studio installed with a model loaded (`lms ps`)
- API server running (`lms server start` → `http://localhost:1234`)

## Run

```bash
lms server status
lms ps
python3 section_1/01_chat/01_chat.py
```

## What the script does

1. Builds a Python `dict` with `model`, `messages`, and `temperature`
2. Serializes it with `json.dumps()` → UTF-8 bytes
3. POSTs to `/v1/chat/completions`
4. Parses the JSON response and prints the assistant reply + token usage

## Try this

- Change the user message
- Set `temperature` to `0` vs `1` and compare replies
- Stop the LM Studio server and see what error you get

## Checkpoint

Without looking at the code, explain:

- What each field in the request body does (`model`, `messages`, `temperature`)
- Where the assistant's text lives in the response JSON

## Key terms

| Term | Meaning |
|------|---------|
| **Inference** | Using a trained model to generate text (not training) |
| **Messages** | List of `{role, content}` — system, user, assistant |
| **Temperature** | Randomness: 0 = repeatable, higher = more varied |

## Next

[Lesson 02 — Streaming](../02_stream/README.md)
