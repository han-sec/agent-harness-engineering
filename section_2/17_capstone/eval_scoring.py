# Lesson 16 — scoring. Deterministic pass/fail from answer text + JSONL log events.
# Humans design test_cases.json; Python scores — no LLM in the grading loop.
import json
from pathlib import Path

from agent_log import LOG_FILE


def load_test_cases(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def load_log_events(run_id: str, log_file: Path = LOG_FILE) -> list[dict]:
    """Return all JSONL records for one run_id — evidence from lesson 13."""
    if not log_file.exists():
        return []
    events = []
    for line in log_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        record = json.loads(line)
        if record.get("run_id") == run_id:
            events.append(record)
    return events


def score_tools(events: list[dict], expect_tools: list[dict]) -> tuple[bool, list[str]]:
    """PASS if each expected tool appears in tool_call events (researcher phase)."""
    if not expect_tools:
        return True, []
    tool_calls = [e for e in events if e.get("event") == "tool_call"]
    reasons: list[str] = []
    all_ok = True
    for expected in expect_tools:
        name = expected["tool"]
        arg_needle = expected.get("arg_contains", "")
        matched = any(
            call.get("tool") == name and arg_needle in call.get("arg", "")
            for call in tool_calls
        )
        if matched:
            reasons.append(f"tools: ok — {name}({arg_needle!r})")
        else:
            all_ok = False
            reasons.append(f"tools: FAIL — missing {name} arg containing {arg_needle!r}")
    return all_ok, reasons


def score_answer(
    answer: str,
    expect_contains: list[str],
    expect_not_contains: list[str],
) -> tuple[bool, list[str]]:
    """PASS if writer output has required substrings and avoids forbidden ones."""
    text = answer.lower()
    reasons: list[str] = []
    all_ok = True
    for needle in expect_contains:
        if needle.lower() in text:
            reasons.append(f"answer: ok — contains {needle!r}")
        else:
            all_ok = False
            reasons.append(f"answer: FAIL — missing {needle!r}")
    for needle in expect_not_contains:
        if needle.lower() in text:
            all_ok = False
            reasons.append(f"answer: FAIL — forbidden {needle!r} present")
        else:
            reasons.append(f"answer: ok — no {needle!r}")
    return all_ok, reasons


def score_case(case: dict, answer: str, events: list[dict]) -> dict:
    """Combine tool + answer checks into one pass/fail result."""
    tools_ok, tool_reasons = score_tools(events, case.get("expect_tools", []))
    answer_ok, answer_reasons = score_answer(
        answer,
        case.get("expect_answer_contains", []),
        case.get("expect_answer_not_contains", []),
    )
    passed = tools_ok and answer_ok
    return {
        "id": case["id"],
        "passed": passed,
        "checks": tool_reasons + answer_reasons,
    }


def run_scoring_self_test(fixtures_path: Path) -> tuple[int, int, list[str]]:
    """Meta-eval: verify scorers against known mock pass/fail fixtures (no LLM)."""
    fixtures = load_test_cases(fixtures_path)
    passed = 0
    lines: list[str] = []
    for fixture in fixtures:
        result = score_case(fixture, fixture["mock_answer"], fixture["mock_events"])
        expected = fixture["expected_pass"]
        ok = result["passed"] == expected
        if ok:
            passed += 1
            lines.append(f"[self-test] PASS {fixture['id']} — scorer behaved as expected")
        else:
            lines.append(
                f"[self-test] FAIL {fixture['id']} — expected pass={expected}, "
                f"got pass={result['passed']}; {result['checks']}"
            )
    return passed, len(fixtures), lines
