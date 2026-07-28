# Step 17: evaluation. Run test cases, score answer + logs, report pass rate.
# Builds on section_2/15_persistence/ (pipeline) + section_2/13_logging/ (evidence).
#
# NEW in this lesson:
#   test_cases.json + eval_scoring.py — deterministic pass/fail
#   scoring_fixtures.json + --self-test — meta-eval for the scorers (no LLM)
#
# Usage:
#   python3 section_2/16_evaluation/16_evaluation.py --self-test   # eval the eval
#   python3 section_2/16_evaluation/16_evaluation.py             # run agent eval (needs LM Studio)
import argparse
import json
import sys
from pathlib import Path

import session_store as session
from agent_log import LOG_FILE
from eval_scoring import (
    load_log_events,
    load_test_cases,
    run_scoring_self_test,
    score_case,
)
from sub_agents import MODEL, WORKSPACE, run_manager

ROOT = Path(__file__).resolve().parent
TEST_CASES = ROOT / "test_cases.json"
SCORING_FIXTURES = ROOT / "scoring_fixtures.json"
REPORT_FILE = ROOT / "reports" / "eval_report.json"


def run_agent_eval() -> int:
    """Run each test case against live LM Studio; score from answer + JSONL logs."""
    cases = load_test_cases(TEST_CASES)
    session.init_db()
    results = []
    passed = 0

    print(f"Agent eval with {MODEL} — {len(cases)} case(s)")
    print(f"Sandbox: {WORKSPACE}")
    print(f"Log file: {LOG_FILE}\n")

    for i, case in enumerate(cases, 1):
        print(f"=== [{i}/{len(cases)}] {case['id']} ===")
        print(f"prompt: {case['prompt']!r}\n")
        outcome = run_manager(case["prompt"], eval_mode=True)
        events = load_log_events(outcome["run_id"])
        result = score_case(case, outcome["answer"], events)
        results.append({**result, "run_id": outcome["run_id"]})
        if result["passed"]:
            passed += 1
            print(f"\n[eval] PASS {case['id']}")
        else:
            print(f"\n[eval] FAIL {case['id']}")
        for check in result["checks"]:
            print(f"  {check}")
        print()

    rate = 100.0 * passed / len(cases) if cases else 0.0
    print(f"=== summary: {passed}/{len(cases)} passed ({rate:.0f}%) ===")

    REPORT_FILE.parent.mkdir(exist_ok=True)
    report = {"passed": passed, "total": len(cases), "rate_pct": rate, "results": results}
    REPORT_FILE.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Report: {REPORT_FILE}")

    return 0 if passed == len(cases) else 1


def run_self_test() -> int:
    """Meta-eval: verify scorers against fixtures — no model required."""
    ok, total, lines = run_scoring_self_test(SCORING_FIXTURES)
    for line in lines:
        print(line)
    print(f"\n=== scorer self-test: {ok}/{total} passed ===")
    return 0 if ok == total else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Lesson 16 — agent evaluation")
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="Run meta-eval on scorers (no LM Studio needed)",
    )
    args = parser.parse_args()
    if args.self_test:
        return run_self_test()
    return run_agent_eval()


if __name__ == "__main__":
    sys.exit(main())
