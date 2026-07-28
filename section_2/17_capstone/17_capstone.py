# Step 17: capstone — Internal Docs Q&A. Combines lessons 09–16 into one production-style agent.
#
# This file is the ENTRY POINT only — it does not contain the agent loop.
#   sub_agents.py     → planner + researcher + writer + run_manager()
#   harness_routes.py → Python answers help/meta without LLM
#   agent_log.py      → JSONL evidence (lesson 13)
#   human_confirm.py  → HITL gate (lesson 14)
#   session_store.py  → SQLite memory (lesson 15)
#   eval_scoring.py   → pass/fail checks (lesson 16)
#
# Pipeline (Python manager, not the model):
#   plan → research (file + web tools) → write → HITL save → session persist
#
# Usage:
#   python3 section_2/17_capstone/17_capstone.py              # interactive Q&A
#   python3 section_2/17_capstone/17_capstone.py --self-test  # scorer meta-eval (no LLM)
#   python3 section_2/17_capstone/17_capstone.py --eval       # run test_cases.json (needs LM Studio)
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
from harness_routes import builtin_answer, print_welcome
from sub_agents import MODEL, WORKSPACE, run_manager

ROOT = Path(__file__).resolve().parent
TEST_CASES = ROOT / "test_cases.json"
SCORING_FIXTURES = ROOT / "scoring_fixtures.json"
REPORT_FILE = ROOT / "reports" / "eval_report.json"


def run_interactive() -> int:
    """Chat loop — delegates every question to run_manager(eval_mode=False)."""
    session.init_db()  # SQLite ready before first turn (lesson 15)
    print_welcome()
    print(f"Model: {MODEL}")
    print(f"Logs: {LOG_FILE}")
    print("Type quit to exit.\n")

    while True:
        try:
            user_msg = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nBye.")
            return 0
        if not user_msg:
            continue
        if user_msg.lower() in ("quit", "exit", "q"):
            print("Bye.")
            return 0
        # Local help — no run_id, no save (same text as harness builtin route)
        if user_msg.lower() in ("help", "?", "h"):
            print(f"\n{builtin_answer(user_msg)}\n")
            continue
        print()
        # eval_mode=False → HITL prompts + SQLite save inside run_manager
        run_manager(user_msg, eval_mode=False)
        print()


def run_agent_eval() -> int:
    """Run each test case against live LM Studio; score answer + JSONL logs."""
    cases = load_test_cases(TEST_CASES)
    session.init_db()  # eval skips save_turn, but init is harmless
    results = []
    passed = 0

    print(f"Capstone eval with {MODEL} — {len(cases)} case(s)")
    print(f"Sandbox: {WORKSPACE}")
    print(f"Log file: {LOG_FILE}\n")

    for i, case in enumerate(cases, 1):
        print(f"=== [{i}/{len(cases)}] {case['id']} ===")
        print(f"prompt: {case['prompt']!r}\n")
        # eval_mode=True → auto-approve writes, skip SQLite (lesson 16)
        outcome = run_manager(case["prompt"], eval_mode=True)
        # Each turn gets a run_id — filter JSONL to score this run only
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

    return 0 if passed == len(cases) else 1  # exit code for CI


def run_self_test() -> int:
    """Meta-eval: verify scorers against fixtures — no model required."""
    ok, total, lines = run_scoring_self_test(SCORING_FIXTURES)
    for line in lines:
        print(line)
    print(f"\n=== scorer self-test: {ok}/{total} passed ===")
    return 0 if ok == total else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Lesson 17 — Internal Docs Q&A capstone")
    parser.add_argument("--self-test", action="store_true", help="Meta-eval scorers (no LLM)")
    parser.add_argument("--eval", action="store_true", help="Run agent eval against test_cases.json")
    args = parser.parse_args()
    if args.self_test:
        return run_self_test()
    if args.eval:
        return run_agent_eval()
    return run_interactive()


if __name__ == "__main__":
    sys.exit(main())
