# LLM Agents — repo guide

Learn AI agent workflows from scratch by building them in plain Python. No frameworks until you understand the loop underneath.

## What this repo is

A hands-on course: one concept per script, run → read → break → fix.

| | |
|---|---|
| **Stack** | Python stdlib + [LM Studio](https://lmstudio.ai/) on `localhost:1234` |
| **Model** | `gemma-4-12b-it-mlx` (or any loaded OpenAI-compatible model) |
| **Syllabus** | See [README.md](README.md) for the full outline |

### The arc

```
Chatbot (01–03)  →  Tool agent (04–06)  →  Reliable agent (07–12)  →  Production (13–17)
```

Every lesson is the same pipeline: **your Python** sends messages over HTTP → **LM Studio** runs inference → **your Python** parses the reply (and maybe runs a tool).

### Folder layout

```
section_1/          # Lessons 01–06 — LLM mechanics + agent loop
  01_chat.py
  02_stream.py
  03_conversation.py
  04_tools.py
  05_multi_tools.py
  06_structured_output.py
  06_appendix_bad_prompt.py   # optional — same lesson, vague prompt (compare parse success)

section_2/          # Lessons 07+ — errors, context, files, production (as you add them)
  07_error_handling.py
  08a_token_estimate.py
  08b_context_management.py
```

Work through `section_1` in order. Each file builds on the previous one.

---

## Guidance for writing lesson code

These rules keep the course consistent and easy for learners to follow.

### 1. One concept per file

Each script adds **exactly one new idea**. Copy the previous lesson and extend it — don't rewrite from scratch.

| Lesson | New idea only |
|--------|----------------|
| `04_tools` | Agent inner loop + `TOOL:name:arg` |
| `05_multi_tools` | Multiple tools in `TOOLS` + menu in system prompt |
| `06_structured_output` | JSON parsing + retry on failure |
| `07_errors` | Tool errors → Observation, `try/except`, `MAX_TOOL_ROUNDS` |
| `08a_token_estimate` | `estimate_tokens`, log prompt size vs 8192 context |
| `08b_context_management` | `trim_history`, `MAX_HISTORY_TOKENS` soft budget |

### 2. Keep the flow simple

Prefer a straight top-to-bottom read:

1. Imports and constants (`URL`, `MODEL`)
2. Small helper functions (`get_weather`, `stream_chat`)
3. The **one new function** the lesson teaches
4. Main loop at the bottom

Avoid abstractions learners haven't seen yet: no classes, no async, no third-party packages.

### 3. Keep comments — but make them teach

Match the style in `04_tools.py` and `06_structured_output.py`:

- **Line comments** on non-obvious lines (HTTP, SSE, parsing, loop logic)
- **Short docstrings** on functions (`"""POST the history..."""`)
- **Step header** at top (`# Step 7: structured output...`)
- **No comment walls** on obvious lines like `import json  # import json`

Comments should answer: *"What is this line doing in the agent pipeline?"*

### 4. Stdlib only

Use `urllib.request`, `json`, `re`, `sqlite3`, etc. If a lesson needs HTTP, streaming, or JSON — stdlib already does it. Frameworks come **after** lesson 17.

### 5. Reuse patterns from earlier lessons

**`stream_chat(messages)`** — copy as-is across lessons unless the lesson specifically changes it.

**Agent inner loop** (from `04` onward):

```python
while True:
    reply = stream_chat(history)
    history.append({"role": "assistant", "content": reply})
    result = run_tool(reply)  # or parse JSON, etc.
    if result is None:
        break
    history.append({"role": "user", "content": f"Observation: {result}"})
```

**Defensive parsing** — models are messy; your code is deterministic:

- Tools: `re.search`, not `re.fullmatch`
- JSON: `try/except json.JSONDecodeError`, validate types, retry on failure

### 6. Local models force honest engineering

Gemma may emit thinking tags, markdown fences, or ignore format instructions. Write parsers that **cope**, not prompts that **hope**.

When something breaks, check three layers (see README §5):

1. **Model** — instruction-following
2. **Runtime** — LM Studio chat template
3. **Your code** — prompt, parsing, loop logic

### 7. Print what matters

Use prefixed prints so learners see the pipeline:

```python
print(f"\n[tool] {name}({arg!r})")
print(f"[parsed] {city!r}")
print(f"[json attempt {attempt}]")
```

### 8. Fake tools are fine

`get_weather` returning a hardcoded string is intentional. The lesson is the **loop**, not the API integration. Real APIs come later.

### 9. Naming and files

- Files: `NN_short_name.py` (e.g. `07_errors.py`)
- Match README lesson numbers
- `section_1` = through lesson 06; `section_2` starts at 07

### 10. Before adding a new lesson

- [ ] Read the previous lesson — extend, don't reinvent
- [ ] One new concept only
- [ ] Line comments on teaching moments
- [ ] Runnable with `python3 section_X/NN_lesson.py` after `lms server start`
- [ ] Update README status when the learner completes it

---

## Quick start (for humans and agents)

```bash
lms server status    # server running?
lms ps               # model loaded?
python3 section_1/06_structured_output.py
```

## Key terms

| Term | Meaning |
|------|---------|
| **Inference** | Running the model to generate text (all we do here) |
| **History** | `messages` list sent every request — this is short-term memory |
| **Agent loop** | Inner `while`: LLM → maybe tool/parse → observation → LLM again |
| **Observation** | Tool result fed back as a user message so the model can answer |
| **Structured output** | Model replies with JSON; Python parses with `json.loads` + retry |

---

*When in doubt: simpler code, more comments on the tricky lines, one idea per file.*
