# Entry — planner (plain Python) + researcher (LangGraph).
import asyncio
import json
import re
import sys
import urllib.error
import urllib.request

from mcp_client import DOCS_MCP_SERVER, docs_mcp_session
from researcher_graph import DOCS_SNAPSHOT, MODEL, run_researcher_graph

URL = "http://localhost:1234/v1/chat/completions"

PLAN_SYSTEM = f"""You are the PLANNER. Reply with ONLY JSON — no TOOL lines.
Docs: {DOCS_SNAPSHOT}
Format: {{"goal": "...", "steps": [{{"description": "...", "tool": "grep_docs or null", "arg": "..."}}]}}"""


def stream_chat(messages: list[dict], label: str) -> str | None:
    print(f"\n[{label}] calling model...")
    req = urllib.request.Request(
        URL,
        data=json.dumps({"model": MODEL, "messages": messages, "stream": True}).encode(),
        headers={"Content-Type": "application/json"},
    )
    parts = []
    try:
        resp = urllib.request.urlopen(req)
    except urllib.error.URLError as exc:
        print(f"[error] Cannot reach LM Studio ({exc.reason})")
        return None
    with resp:
        for raw in resp:
            line = raw.decode().strip()
            if not line.startswith("data: "):
                continue
            payload = line[len("data: "):]
            if payload == "[DONE]":
                break
            token = json.loads(payload)["choices"][0]["delta"].get("content", "")
            parts.append(token)
            print(token, end="", flush=True)
    print()
    return "".join(parts)


def strip_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return text.strip()


def parse_plan(reply: str) -> dict | None:
    try:
        data = json.loads(strip_json(reply))
    except json.JSONDecodeError:
        return None
    if not isinstance(data.get("goal"), str) or not isinstance(data.get("steps"), list):
        return None
    return data


def format_plan(plan: dict) -> str:
    lines = [f"Goal: {plan['goal']}", "Steps:"]
    for i, step in enumerate(plan["steps"], 1):
        desc = step.get("description", "")
        tool = step.get("tool")
        arg = step.get("arg")
        hint = f" (suggested: {tool}({arg!r}))" if tool else ""
        lines.append(f"  {i}. {desc}{hint}")
    return "\n".join(lines)


async def run_interactive() -> int:
    print("Section 4 — LangGraph researcher (compare to lesson 19)")
    print(f"Model: {MODEL}")
    print("Type quit to exit.\n")

    async with docs_mcp_session() as mcp:
        while True:
            try:
                question = (await asyncio.to_thread(input, "You: ")).strip()
            except (EOFError, KeyboardInterrupt):
                print("\nBye.")
                return 0
            if not question or question.lower() in ("quit", "exit", "q"):
                print("Bye.")
                return 0

            print("\n[manager] → planner (plain Python)")
            reply = stream_chat(
                [{"role": "system", "content": PLAN_SYSTEM}, {"role": "user", "content": question}],
                "planner",
            )
            plan = parse_plan(reply or "")
            if not plan:
                print("[planner] failed")
                continue
            print(f"[plan] goal: {plan['goal']}")

            print("[manager] → researcher (LangGraph)")
            facts = await run_researcher_graph(question, format_plan(plan), mcp)
            print(f"\n--- Facts ---\n{facts}\n")


def main() -> int:
    if not DOCS_MCP_SERVER.is_file():
        print(f"FAIL: lesson 18 server missing: {DOCS_MCP_SERVER}", file=sys.stderr)
        return 1
    return asyncio.run(run_interactive())


if __name__ == "__main__":
    sys.exit(main())