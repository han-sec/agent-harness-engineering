# Lesson 16 — Evaluation

## What this lesson is

**Measure the agent** with fixed test cases and pass/fail scoring — not gut feel.

Logging (13) records evidence. Evaluation (16) judges it.

## New concept

**Test cases + scorers + runner**

```
test_cases.json  →  run_manager(eval_mode=True)  →  score answer + logs  →  report
```

## Prerequisites

- [Lesson 13 — Logging](../13_logging/README.md) (JSONL evidence)
- [Lesson 15 — Persistence](../15_persistence/README.md) (eval skips SQLite)

## Run

**1. Meta-eval — test the scorers (no LM Studio):**

```bash
python3 section_2/16_evaluation/16_evaluation.py --self-test
```

**2. Agent eval — live model (LM Studio required):**

```bash
python3 section_2/16_evaluation/16_evaluation.py
```

Checkpoint: 5 prompts → printed pass rate → `reports/eval_report.json`.

## What we evaluate

| Check | Source |
|-------|--------|
| Right tools used? | JSONL `tool_call` events |
| Answer grounded? | Substrings in final answer |
| Bad phrases absent? | `expect_answer_not_contains` |

Example case:

```json
{
  "id": "todo_harness",
  "prompt": "What does notes/todo.md say about agents?",
  "expect_tools": [{"tool": "read_file", "arg_contains": "todo.md"}],
  "expect_answer_contains": ["harness", "todo.md"]
}
```

## Eval mode

`run_manager(..., eval_mode=True)`:

- Auto-approves HITL writes
- Skips SQLite save/load
- Returns `{run_id, answer, facts}` for scoring

## File layout

| File | Role |
|------|------|
| `16_evaluation.py` | Runner + `--self-test` |
| `test_cases.json` | Agent test prompts |
| `eval_scoring.py` | Scorers — **lesson 16** |
| `scoring_fixtures.json` | Meta-eval fixtures for scorers |
| `sub_agents.py` | Pipeline with `eval_mode` |

---

## Evaluating your eval (meta-eval)

**Yes — production teams validate eval suites too.** A bad test gives false confidence.

| Production practice | Lesson 16 equivalent |
|---------------------|----------------------|
| **Golden labels** | Human marks 20 runs pass/fail; compare to scorers |
| **Scorer unit tests** | `scoring_fixtures.json` + `--self-test` |
| **Holdout set** | Don't tune prompts on the same cases you score |
| **Regression on eval** | Changing scorers must not break fixtures |
| **Human audit sample** | Weekly review random FAIL/PASS traces |
| **LLM-judge calibration** | Compare model grader vs human (we skip LLM judge here) |

`--self-test` checks: *if I feed known mock logs/answers, does the scorer pass/fail correctly?*

It does **not** prove your agent is good — it proves your **tests work**.

### Limits of our meta-eval

- Fixtures use **mock** data — not live agent runs
- 5 agent cases is tiny — production uses hundreds+
- Substring checks miss nuance — production adds human review + richer metrics

**Rule:** Trust eval trends after you trust the scorers (`--self-test`) and spot-check logs.

## Next

Lesson 17 — Capstone (planned): file + web + planning + full production stack.
