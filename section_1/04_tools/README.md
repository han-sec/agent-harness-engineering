# Lesson 04 — Tool-using agent

## What this lesson is

The moment a chatbot becomes an **agent**. The model can *request* a tool by emitting a special text format; **Python executes it** and feeds the result back as an Observation.

## New concept

**Agent inner loop:** LLM → maybe tool → Observation → LLM again.

```
TOOL:tool_name:argument
```

## Prerequisites

[Lesson 03 — Conversation](../03_conversation/README.md)

## Run

```bash
python3 section_1/04_tools/04_tools.py
```

Try: *What's the weather in Tokyo?*

## What the script does

1. System prompt teaches the `TOOL:name:arg` contract
2. Model reply is scanned with `re.search` (not `re.fullmatch` — models add extra text)
3. If a tool call is found, Python runs `get_weather()` and appends `Observation: ...`
4. Loop continues until the model replies without a tool call

## Who decides to call a tool?

| | Role |
|---|------|
| **Model** | Predicts text that *looks like* a tool call |
| **Python** | Parses it, runs the function, controls the loop |

The model never executes code — it only asks.

## What to watch for

```
[tool] get_weather('Tokyo')
[observation] 'Sunny, 28°C in Tokyo'
```

## Checkpoint

Explain who "decides" to call a tool — the model or your Python code?

## Key code

- `TOOLS` registry — `name → function`
- `run_tool(line)` — defensive parsing with `re.search`
- Inner `while True` inside the outer user-input loop

## Next

[Lesson 05 — Multiple tools](../05_multi_tools/README.md)
