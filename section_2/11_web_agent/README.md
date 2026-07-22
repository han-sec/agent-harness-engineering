# Lesson 11 — Web agent

## What this lesson is

Same agent loop as lessons 07–10, but the tool reads **the public web** instead of local files. One tool: `fetch_url`.

Lesson 10 = trusted sandbox. Lesson 11 = **untrusted network** with harness policy.

## New concept

**`fetch_url` + `is_url_allowed()`** — the model proposes URLs; Python decides what may be fetched.

## Prerequisites

[Lesson 10 — File agent](../10_file_agent/README.md) (harness patterns: errors, trim, noise handling)

## Not in this lesson

- File tools (`read_file`, `list_dir`, `grep`) — those stay in lesson 10
- Combining file + web in one agent — **section 2 recap / capstone** (lesson 17)

## Run

```bash
python3 section_2/11_web_agent/11_web_agent.py
```

Requires network access for live fetches.

## Try this

| Prompt | Expected |
|--------|----------|
| Summarize https://example.com | fetch → summary from page text |
| Fetch http://127.0.0.1 | Blocked — not https / private |
| Fetch https://google.com | Blocked — not on allowlist |

## The one tool

```
TOOL:fetch_url:https://example.com
```

## Trust boundaries (lesson focus)

| Check | Why |
|-------|-----|
| **https only** | No plain http downgrades |
| **Host allowlist** | Teaching default — `example.com`, `example.org` only |
| **DNS → private IP block** | SSRF basics — no fetching your LM Studio via `localhost` |
| **Timeout** | 10s — don't hang forever |
| **Byte + char caps** | Don't fill context with one page |

Policy runs in **`is_url_allowed()`** before `urlopen` — same idea as lesson 10's `safe_path()`.

## Agent loop

```
User question
  → fetch_url (maybe retry after Error Observation)
  → Observation: page text or Error: ...
  → model summarizes (no TOOL line = done)
```

Errors feed back like lesson 07 — model can try an allowed URL.

If max tool rounds hit, harness sends **`GIVE_UP_NUDGE`** and asks the model to explain failure to the user.

## Checkpoint

Summarize `https://example.com` using only fetch content — no hallucinated page text.

## Key code

- `is_url_allowed()` — URL policy (one new harness idea)
- `fetch_url()` — GET + caps + HTML strip
- `html_to_text()` — `html.parser` from stdlib

## Course arc

```
10  file tools     →  local sandbox
11  fetch_url       →  web (this lesson)
…   12–16          →  sub-agents, logging, approval, persistence, eval
17  capstone       →  combined agent (file + web + planning + …)
```

## Next

[Lesson 12 — Sub-agents](../12_sub_agents/README.md)
