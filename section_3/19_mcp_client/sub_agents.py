# Step 19: harness + MCP client — researcher tools call lesson 18 server over stdio.
#
# NEW in this lesson:
#   mcp_client.docs_mcp_session — spawn docs_mcp_server.py, tools/call, close
#   run_researcher() inner loop uses MCP instead of in-process read_file/grep
#
# Unchanged from 17: run_manager, planner, writer, logging, HITL, session
import asyncio
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

import agent_log as log
import session_store as session
from harness_routes import builtin_answer, is_meta_question
from human_confirm import confirm_action, set_eval_mode
from mcp_client import (
    DOCS_MCP_ROOT,
    MCP_TOOL_NAMES,
    docs_mcp_session,
    mcp_arg_preview,
    mcp_call,
    tool_line_to_mcp_args,
)

URL = "http://localhost:1234/v1/chat/completions"
MODEL = "gemma-4-12b-it-mlx"
MAX_HISTORY_TOKENS = 4000
MAX_PLAN_RETRIES = 3
MAX_RESEARCHER_ROUNDS = 10
MAX_EMPTY_RETRIES = 2
DEFAULT_OUTPUT_PATH = "output/answer.md"

CHANNEL_TAG_RE = re.compile(r"<\|[^|>]*\|>?|<\|[^|>]*>", re.IGNORECASE)
OUTPUT_DIR = Path(__file__).resolve().parent / "output"
DOCS_DIR = DOCS_MCP_ROOT / "docs"

PLANNER_TOOL_NAMES = MCP_TOOL_NAMES


def _docs_listing() -> str:
    if not DOCS_DIR.is_dir():
        return "(docs folder not found — run lesson 18)"
    names = sorted(p.name for p in DOCS_DIR.glob("*.md"))
    return ", ".join(names) if names else "(empty)"


DOCS_SNAPSHOT = _docs_listing()

RESEARCHER_TOOL_MENU = """\
- list_docs — Example: TOOL:list_docs:_
- grep_docs(query) — Example: TOOL:grep_docs:refund or TOOL:grep_docs:refund:refunds-policy.md
- read_doc(path) — Example: TOOL:read_doc:refunds-policy.md

Tools run via MCP (lesson 18 docs_mcp_server.py) — not local Python file functions."""

PLAN_SYSTEM = f"""You are the PLANNER sub-agent for an internal docs Q&A assistant.

Docs are served by the internal-docs MCP server. Available files:
{DOCS_SNAPSHOT}

Tools (planning only — do NOT call them in this phase):
{RESEARCHER_TOOL_MENU}

Reply with ONLY valid JSON — no markdown, no TOOL lines.
Format:
{{"goal": "short summary", "steps": [{{"description": "what to do", "tool": "tool_name or null", "arg": "argument or null"}}]}}
Example:
{{"goal": "Find refund window", "steps": [
  {{"description": "Search for refund", "tool": "grep_docs", "arg": "refund"}},
  {{"description": "Read refunds-policy.md", "tool": "read_doc", "arg": "refunds-policy.md"}},
  {{"description": "Hand facts to writer", "tool": null, "arg": null}}
]}}
Do NOT call tools. Plan only."""

PLAN_RETRY = (
    "Invalid plan JSON. Reply with ONLY the JSON object. No TOOL lines. No markdown fences."
)

RESEARCHER_SYSTEM = f"""You are the RESEARCHER sub-agent. You do not talk to the user.

Gather facts using MCP doc tools (stdio server — Python harness calls them for you).
Docs available: {DOCS_SNAPSHOT}

When you need a tool, emit one line:
TOOL:tool_name:argument
One tool per reply. No thinking tags.

Tools:
{RESEARCHER_TOOL_MENU}

After grep_docs hits, read_doc the full source file. Cite filenames in facts (e.g. refunds-policy.md).
When done, stop calling tools and return bullet facts only."""

WRITER_SYSTEM = """You are the WRITER sub-agent. Use ONLY researcher facts. No tools.
Write a clear answer. Cite doc filenames when relevant."""

EMPTY_REPLY_NUDGE = "No TOOL line and no facts yet. Call an MCP doc tool or return bullet facts."


def strip_template_noise(text: str) -> str:
    cleaned = CHANNEL_TAG_RE.sub("", text)
    cleaned = re.sub(r"\bthought\b", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def strip_json(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return text.strip()


def parse_plan(reply: str) -> dict | None:
    try:
        data = json.loads(strip_json(reply))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    goal = data.get("goal")
    steps = data.get("steps")
    if not isinstance(goal, str) or not goal.strip():
        return None
    if not isinstance(steps, list) or not steps:
        return None
    cleaned_steps = []
    for step in steps:
        if not isinstance(step, dict):
            return None
        desc = step.get("description")
        if not isinstance(desc, str) or not desc.strip():
            return None
        tool = step.get("tool")
        arg = step.get("arg")
        if tool is not None and not isinstance(tool, str):
            return None
        if arg is not None and not isinstance(arg, str):
            return None
        if tool is not None and tool.strip() and tool.strip() not in PLANNER_TOOL_NAMES:
            return None
        cleaned_steps.append(
            {
                "description": desc.strip(),
                "tool": tool.strip() if isinstance(tool, str) and tool.strip() else None,
                "arg": arg.strip() if isinstance(arg, str) and arg.strip() else None,
            }
        )
    return {"goal": goal.strip(), "steps": cleaned_steps}


def format_plan(plan: dict) -> str:
    lines = [f"Goal: {plan['goal']}", "Steps:"]
    for i, step in enumerate(plan["steps"], 1):
        hint = ""
        if step["tool"]:
            hint = f" (suggested: {step['tool']}({step['arg']!r}))"
        lines.append(f"  {i}. {step['description']}{hint}")
    return "\n".join(lines)


def print_plan(plan: dict) -> None:
    print(f"\n[plan] goal: {plan['goal']}")
    for i, step in enumerate(plan["steps"], 1):
        hint = ""
        if step["tool"]:
            hint = f" (suggested: {step['tool']}({step['arg']!r}))"
        print(f"[plan]   {i}. {step['description']}{hint}")


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def estimate_messages_tokens(messages: list) -> int:
    total = 0
    for msg in messages:
        total += estimate_tokens(msg.get("content", ""))
        total += 4
    return total


def trim_history(history: list) -> None:
    if len(history) <= 1:
        return
    while len(history) > 1 and estimate_messages_tokens(history) > MAX_HISTORY_TOKENS:
        history.pop(1)


def stream_chat(messages, label: str) -> str | None:
    log.llm_start(label, estimate_messages_tokens(messages))
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
        print(f"\n[error] Cannot reach LM Studio ({exc.reason})")
        log.llm_error(label, str(exc.reason))
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
    reply = "".join(parts)
    log.llm_reply(label, reply, strip_template_noise(reply))
    return reply


def find_mcp_tool_call(line: str) -> tuple[str, str] | None:
    """Parse TOOL:name:arg for MCP tool names."""
    for text in (line, strip_template_noise(line)):
        match = re.search(r"TOOL:(\w+)(?::(.*))?", text)
        if not match:
            continue
        name = match.group(1)
        arg = (match.group(2) or "").strip()
        if name in MCP_TOOL_NAMES:
            return name, arg
    return None


async def run_mcp_tool(line: str, session, label: str) -> str | None:
    """Parse model reply → MCP tools/call. None = no tool line (end inner loop)."""
    found = find_mcp_tool_call(line)
    if not found:
        return None
    name, arg = found
    arguments = tool_line_to_mcp_args(name, arg)
    preview = mcp_arg_preview(name, arguments)
    print(f"\n[{label}] mcp {name}({preview!r})")
    try:
        result = await mcp_call(session, name, arguments)
    except Exception as exc:
        result = f"Error: MCP tool {name} crashed: {exc}"
    log.tool_call(label, name, preview, result)
    return result


def is_empty_reply(reply: str) -> bool:
    return len(strip_template_noise(reply)) < 15


def write_file(path_arg: str, content: str) -> str:
    """Save writer answer locally (HITL) — not via MCP."""
    rel = path_arg.strip().lstrip("/")
    if rel.startswith(".."):
        return f"Error: invalid path {path_arg!r}"
    target = (OUTPUT_DIR / rel).resolve()
    try:
        target.relative_to(OUTPUT_DIR.resolve())
    except ValueError:
        return f"Error: path must stay under output/"
    preview = content[:200] + ("..." if len(content) > 200 else "")
    log.approval_requested("write_file", path_arg, preview)
    if not confirm_action(f"Write {len(content)} chars to {path_arg}?"):
        log.approval_denied("write_file", path_arg)
        return "Error: write rejected by human"
    log.approval_granted("write_file", path_arg)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        return f"Error: cannot write {path_arg!r}: {exc}"
    log.file_written(path_arg, len(content))
    return f"Wrote {len(content)} chars to {path_arg}"


def run_planner(user_question: str) -> dict | None:
    history = [
        {"role": "system", "content": PLAN_SYSTEM},
        {"role": "user", "content": user_question},
    ]
    for attempt in range(1, MAX_PLAN_RETRIES + 1):
        print(f"\n[planner] asking for plan (attempt {attempt})")
        reply = stream_chat(history, "planner")
        if reply is None:
            log.planner_offline()
            return None
        if re.search(r"TOOL:\w+", reply):
            print("[guard] model emitted TOOL: during planning — ignoring")
        plan = parse_plan(reply)
        if plan:
            print_plan(plan)
            log.plan_done(plan["goal"], len(plan["steps"]))
            return plan
        history.append({"role": "assistant", "content": reply})
        history.append({"role": "user", "content": PLAN_RETRY})
    print(f"[error] Could not get valid plan JSON after {MAX_PLAN_RETRIES} attempts.")
    return None


async def _run_researcher_async(task: str, plan: dict, mcp) -> str:
    """INNER LOOP — LLM ↔ MCP tools. Reuses the chat-level MCP session."""
    plan_text = format_plan(plan)
    history = [
        {"role": "system", "content": RESEARCHER_SYSTEM},
        {
            "role": "user",
            "content": f"Research task: {task}\n\nPlan:\n{plan_text}",
        },
    ]
    empty_retries = 0
    last_reply = ""

    for _ in range(1, MAX_RESEARCHER_ROUNDS + 1):
        trim_history(history)
        reply = stream_chat(history, "researcher")
        if reply is None:
            log.agent_offline("researcher")
            return "[researcher offline — LM Studio unreachable]"
        last_reply = reply
        history.append({"role": "assistant", "content": reply})
        result = await run_mcp_tool(reply, mcp, "researcher")
        if result is None:
            if is_empty_reply(reply) and empty_retries < MAX_EMPTY_RETRIES:
                empty_retries += 1
                print(f"[researcher] noise only — nudge ({empty_retries}/{MAX_EMPTY_RETRIES})")
                log.nudge("researcher", empty_retries)
                history.append({"role": "user", "content": EMPTY_REPLY_NUDGE})
                continue
            facts = strip_template_noise(reply)
            print(f"[researcher] returning facts ({len(facts)} chars)")
            log.researcher_done(facts)
            return facts or "[researcher returned no facts]"
        empty_retries = 0
        preview = result if len(result) <= 100 else result[:100] + "..."
        print(f"[researcher] observation {preview!r}")
        history.append({"role": "user", "content": f"Observation: {result}"})

    print("[researcher] hit round limit")
    log.researcher_round_limit()
    return strip_template_noise(last_reply) or "[researcher hit tool round limit]"


def run_researcher(task: str, plan: dict, mcp=None) -> str:
    """Sync entry for one-off runs — opens and closes its own MCP session."""
    async def _once():
        async with docs_mcp_session() as session:
            return await _run_researcher_async(task, plan, session)

    try:
        return asyncio.run(_once())
    except FileNotFoundError as exc:
        return f"[researcher MCP error — {exc}]"


def run_writer(task: str, facts: str, prior_context: str = "") -> str:
    parts = []
    if prior_context:
        parts.append(prior_context)
    parts.append(f"User question: {task}")
    parts.append(f"Researcher facts:\n{facts}")
    parts.append("Write the final answer.")
    history = [
        {"role": "system", "content": WRITER_SYSTEM},
        {"role": "user", "content": "\n\n".join(parts)},
    ]
    reply = stream_chat(history, "writer")
    if reply is None:
        log.agent_offline("writer")
        return "[writer offline — LM Studio unreachable]"
    answer = strip_template_noise(reply) or "[writer returned empty reply]"
    log.writer_done(answer)
    return answer


async def run_manager_async(user_question: str, mcp, *, eval_mode: bool = False) -> dict:
    """OUTER orchestration — sequential handoffs; researcher reuses chat MCP session."""
    if eval_mode:
        set_eval_mode(True)
    try:
        run_id = log.begin_turn(user_question)
        prior_context = ""
        if not eval_mode:
            prior_turns = session.load_recent_turns()
            prior_context = session.format_prior_context(prior_turns)
            if prior_turns:
                print(f"[session] loaded {len(prior_turns)} prior turn(s)")

        print("[manager] received user question")

        if is_meta_question(user_question):
            answer = builtin_answer(user_question)
            print("[manager] builtin route")
            print(f"\n{answer}\n")
            log.builtin_handled("meta")
            if not eval_mode:
                session.save_turn(user_question, answer)
            log.end_turn(len(answer))
            return {"run_id": run_id, "answer": answer, "facts": "", "plan": None}

        print("[manager] → planner")
        log.handoff("manager", "planner")
        plan = run_planner(user_question)
        if plan is None:
            answer = "[planner failed]"
            log.end_turn(len(answer))
            return {"run_id": run_id, "answer": answer, "facts": "", "plan": None}

        print("[manager] ← planner done")
        log.handoff("planner", "manager", step_count=len(plan["steps"]))

        print("[manager] → researcher (inner MCP loop runs inside)")
        log.handoff("manager", "researcher")
        facts = await _run_researcher_async(user_question, plan, mcp)

        print(f"[manager] ← researcher done ({len(facts)} chars)")
        log.handoff("researcher", "manager", facts_chars=len(facts))

        print("[manager] → writer")
        log.handoff("manager", "writer", facts_chars=len(facts))
        answer = run_writer(user_question, facts, prior_context)

        print("[manager] ← writer done")
        if not eval_mode:
            print(f"\n[manager] offer save → {DEFAULT_OUTPUT_PATH}")
            print(f"[manager] {write_file(DEFAULT_OUTPUT_PATH, answer)}")
            turn_id = session.save_turn(user_question, answer)
            print(f"[session] saved turn #{turn_id}")

        log.end_turn(len(answer))
        return {"run_id": run_id, "answer": answer, "facts": facts, "plan": plan}
    finally:
        if eval_mode:
            set_eval_mode(False)


def run_manager(user_question: str, *, eval_mode: bool = False) -> dict:
    """One-shot sync entry — opens MCP for this question only, then closes."""

    async def _once():
        async with docs_mcp_session() as mcp:
            return await run_manager_async(user_question, mcp, eval_mode=eval_mode)

    return asyncio.run(_once())
