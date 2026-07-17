# Step 10: planning. Plan-then-execute — two phases, two system prompts, Python-owned plan.
# Builds on section_2/08b_context_management/08b_context_management.py (tools, errors, trim)
# + section_1/06_structured_output/06_structured_output.py (JSON parse + retry).
#
# NEW in this lesson:
#   Phase 1 — model writes a JSON plan; Python never calls run_tool() (guard rail)
#   Phase 2 — model executes one step at a time with the normal tool loop
#   current_plan lives outside history so trimming cannot drop your control state
import json          # serialize HTTP bodies; parse plan JSON from the model
import re            # parse TOOL:name:arg; strip markdown fences from JSON
import urllib.error  # catch "model offline" connection errors
import urllib.request  # make HTTP calls without extra libraries
from datetime import datetime  # get_time tool
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError  # timezone lookup for get_time

URL = "http://localhost:1234/v1/chat/completions"  # LM Studio OpenAI-compatible endpoint
MODEL = "gemma-4-12b-it-mlx"  # must match a model loaded in LM Studio
MODEL_CONTEXT = 8192  # LM Studio hard ceiling — input + output in one request
MAX_HISTORY_TOKENS = 4000  # soft budget per execute step — from 08b
MAX_TOOL_ROUNDS = 5  # cap inner tool loop per step — from 07
MAX_PLAN_RETRIES = 3  # how many times to re-ask for valid plan JSON — from 06

TOOLS = {}  # name -> function; the menu Python can actually run


def get_weather(city: str) -> str:
    """Fake weather — rejects empty city so the model can recover from bad args."""
    if not city.strip():
        return "Error: city cannot be empty"
    return f"Sunny, 28°C in {city}"


def calculate(expr: str) -> str:
    """Evaluate a basic math expression. Numbers and + - * / ( ) only."""
    allowed = set("0123456789+-*/(). ")
    if not expr or not all(c in allowed for c in expr):
        return f"Error: only basic math allowed, got {expr!r}"
    try:
        return str(eval(expr, {"__builtins__": {}}, {}))  # noqa: S307 — lesson demo only
    except Exception as exc:
        return f"Error: {exc}"


def get_time(timezone: str) -> str:
    """Current time in an IANA timezone, e.g. UTC or America/New_York."""
    if not timezone.strip():
        return "Error: timezone cannot be empty"
    try:
        now = datetime.now(ZoneInfo(timezone))
    except ZoneInfoNotFoundError:
        return f"Error: unknown timezone {timezone!r}. Try UTC or America/New_York."
    return now.strftime(f"The time in {timezone} is %H:%M %Z")


TOOLS["get_weather"] = get_weather
TOOLS["calculate"] = calculate
TOOLS["get_time"] = get_time

TOOL_MENU = """\
- get_weather(city) — weather for a city. Example: TOOL:get_weather:Tokyo
- calculate(expr) — math expression. Example: TOOL:calculate:15*7
- get_time(timezone) — current time. Example: TOOL:get_time:UTC"""

# Phase 1 prompt — planning only. Tools are listed so steps can name them, but the
# model must NOT emit TOOL: lines yet. Python enforces that by never calling run_tool().
PLAN_SYSTEM = f"""You are a planner. The user will ask a multi-step question.

Available tools (for planning only — do NOT call them in this phase):
{TOOL_MENU}

Reply with ONLY valid JSON — no markdown, no TOOL lines, no explanation.
Format:
{{"goal": "short summary", "steps": [{{"description": "what to do", "tool": "tool_name or null", "arg": "argument or null"}}]}}
Example:
{{"goal": "Compare weather in two cities", "steps": [
  {{"description": "Get weather for Tokyo", "tool": "get_weather", "arg": "Tokyo"}},
  {{"description": "Get weather for London", "tool": "get_weather", "arg": "London"}},
  {{"description": "Compare both and answer the user", "tool": null, "arg": null}}
]}}
Do NOT call tools. Do NOT answer the user yet. Plan only."""

PLAN_RETRY = (
    "Invalid plan JSON. Reply with ONLY the JSON object in the format above. "
    "No TOOL lines. No markdown fences."
)

# Phase 2 uses build_execute_system() — built per step with the stored plan injected.


def estimate_tokens(text: str) -> int:
    """Rough token count — ~4 chars per token. From 08a."""
    return max(1, len(text) // 4)


def estimate_messages_tokens(messages: list) -> int:
    """Estimate tokens for a full messages list (system + history)."""
    total = 0
    for msg in messages:
        total += estimate_tokens(msg.get("content", ""))
        total += 4  # rough overhead per message (role tags, chat template)
    return total


def trim_history(history: list) -> None:
    """Drop oldest messages after system until under MAX_HISTORY_TOKENS."""
    if len(history) <= 1:
        return  # only system prompt — nothing to trim
    dropped = 0
    while len(history) > 1 and estimate_messages_tokens(history) > MAX_HISTORY_TOKENS:
        history.pop(1)  # drop oldest non-system message; index 0 is always system
        dropped += 1
    if dropped:
        remaining = estimate_messages_tokens(history)
        print(f"[context] dropped {dropped} old message(s), ~{remaining} tokens remain")


def stream_chat(messages) -> str | None:
    """POST the history, print tokens as they arrive, return the full reply (or None if offline)."""
    req = urllib.request.Request(
        URL,
        data=json.dumps({"model": MODEL, "messages": messages, "stream": True}).encode(),
        headers={"Content-Type": "application/json"},
    )
    parts = []
    try:
        resp = urllib.request.urlopen(req)
    except urllib.error.URLError as exc:
        print(f"\n[error] Cannot reach LM Studio — is the server running? ({exc.reason})")
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


def run_tool(line: str) -> str | None:
    """Find TOOL:name:arg, run it safely. Returns None if no tool call in the reply."""
    match = re.search(r"TOOL:(\w+):(.+)", line.strip())
    if not match:
        return None
    name, arg = match.group(1), match.group(2).strip()
    fn = TOOLS.get(name)
    if not fn:
        return f"Error: unknown tool: {name}"
    print(f"\n[tool] {name}({arg!r})")
    try:
        return fn(arg)
    except Exception as exc:
        return f"Error: tool {name} crashed: {exc}"


def strip_json(text: str) -> str:
    """Pull a JSON object out of common model wrappers — same idea as lesson 06."""
    text = text.strip()
    if text.startswith("```"):  # model wrapped JSON in a markdown code block
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")  # find first { in case of extra chatter before JSON
    end = text.rfind("}")  # find last } in case of trailing text
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return text.strip()


def parse_plan(reply: str) -> dict | None:
    """Parse and validate plan JSON. Returns None on any failure — caller retries."""
    try:
        data = json.loads(strip_json(reply))
    except json.JSONDecodeError:
        return None  # bad syntax — harness will retry, not execute
    if not isinstance(data, dict):
        return None
    goal = data.get("goal")
    steps = data.get("steps")
    if not isinstance(goal, str) or not goal.strip():
        return None  # need a non-empty goal string
    if not isinstance(steps, list) or not steps:
        return None  # need at least one step
    cleaned_steps = []
    for step in steps:
        if not isinstance(step, dict):
            return None
        desc = step.get("description")
        if not isinstance(desc, str) or not desc.strip():
            return None  # every step needs a human-readable description
        tool = step.get("tool")  # optional — null means "answer/summarize" step
        arg = step.get("arg")  # optional — paired with tool when present
        if tool is not None and not isinstance(tool, str):
            return None
        if arg is not None and not isinstance(arg, str):
            return None
        if tool is not None and tool not in TOOLS:
            return None  # plan references a tool Python cannot run — reject early
        cleaned_steps.append(
            {
                "description": desc.strip(),
                "tool": tool.strip() if isinstance(tool, str) and tool.strip() else None,
                "arg": arg.strip() if isinstance(arg, str) and arg.strip() else None,
            }
        )
    return {"goal": goal.strip(), "steps": cleaned_steps}


def print_plan(plan: dict) -> None:
    """Show the parsed plan before execution — learner should see plan before [tool] lines."""
    print(f"\n[plan] goal: {plan['goal']}")
    for i, step in enumerate(plan["steps"], 1):
        hint = ""
        if step["tool"]:
            hint = f" (suggested: {step['tool']}({step['arg']!r}))"
        print(f"[plan]   {i}. {step['description']}{hint}")


def request_plan(user_message: str) -> dict | None:
    """Phase 1 — ask the model for a JSON plan. Guard rail: never run tools here."""
    history = [
        {"role": "system", "content": PLAN_SYSTEM},
        {"role": "user", "content": user_message},
    ]
    for attempt in range(1, MAX_PLAN_RETRIES + 1):
        print(f"\n[plan phase] asking model for plan (attempt {attempt})")
        reply = stream_chat(history)
        if reply is None:
            return None  # LM Studio offline — abort this turn
        if re.search(r"TOOL:\w+:", reply):
            # Model tried to act during planning — prompt said not to, but we enforce in code too.
            print("[guard] model emitted TOOL: during planning — ignoring (no tool will run)")
        plan = parse_plan(reply)
        if plan:
            print_plan(plan)
            return plan  # valid plan — hand off to execute phase
        history.append({"role": "assistant", "content": reply})
        history.append({"role": "user", "content": PLAN_RETRY})
    print(f"[error] Could not get valid plan JSON after {MAX_PLAN_RETRIES} attempts.")
    return None


def build_execute_system(plan: dict, step_num: int) -> str:
    """Phase 2 system prompt — inject the full plan and highlight the current step."""
    lines = [
        "You are executing a plan step by step.",
        f"Goal: {plan['goal']}",
        "",
        "Plan:",
    ]
    for i, step in enumerate(plan["steps"], 1):
        marker = "  ← current step" if i == step_num else ""
        lines.append(f"  {i}. {step['description']}{marker}")
    lines.extend(
        [
            "",
            "When you need a tool for the current step, include this line in your reply:",
            "TOOL:tool_name:argument",
            "(Do not wrap it in thinking tags or other markup.)",
            "Call one tool per reply.",
            "",
            "Available tools:",
            TOOL_MENU,
            "",
            "Observations may contain errors. Read them, fix your args, and retry.",
            "When the current step is done, reply in plain language (no TOOL line).",
        ]
    )
    return "\n".join(lines)


def execute_step(plan: dict, step_num: int, prior_observations: list[str]) -> list[str]:
    """Phase 2 — run the tool loop for one plan step. Returns new observations to carry forward."""
    step = plan["steps"][step_num - 1]
    print(f"\n[execute] step {step_num}/{len(plan['steps'])}: {step['description']}")

    # Fresh history per step — system prompt includes the plan + "you are on step N".
    history = [{"role": "system", "content": build_execute_system(plan, step_num)}]

    # Give the model context from earlier steps so step 3 can compare step 1+2 results.
    if prior_observations:
        summary = "Results from earlier steps:\n" + "\n".join(f"- {obs}" for obs in prior_observations)
        history.append({"role": "user", "content": summary})

    history.append(
        {
            "role": "user",
            "content": f"Execute step {step_num} now: {step['description']}",
        }
    )

    step_observations = []  # tool results from this step only
    for _ in range(1, MAX_TOOL_ROUNDS + 1):  # cap tool rounds per step; _ = index unused
        trim_history(history)
        prompt_tokens = estimate_messages_tokens(history)
        print(f"[tokens] ~{prompt_tokens} / {MAX_HISTORY_TOKENS} budget")
        reply = stream_chat(history)
        if reply is None:
            break
        history.append({"role": "assistant", "content": reply})
        result = run_tool(reply)  # guard rail lifted — tools allowed in execute phase
        if result is None:
            break  # step finished — model gave a plain-language answer
        print(f"[observation] {result!r}")
        step_observations.append(result)
        history.append({"role": "user", "content": f"Observation: {result}"})
    else:
        print(f"\n[error] Step {step_num} hit {MAX_TOOL_ROUNDS} tool rounds without finishing.")

    return step_observations


def confirm_execute() -> bool:
    """Human gate — user decides whether to leave planning and run tools (preview of lesson 14)."""
    while True:
        try:
            answer = input("\nRun this plan? [y/n] ").strip().lower()
        except (EOFError, KeyboardInterrupt):
            print("\n[plan] cancelled")
            return False
        if answer in ("y", "yes"):
            return True  # user approved — harness may enter execute phase
        if answer in ("n", "no", ""):
            print("[plan] cancelled — not executing (still in planning mode)")
            return False
        print("Please answer y or n.")


def execute_plan(plan: dict) -> None:
    """Walk the plan steps in order. Python drives the loop; model executes each step."""
    prior_observations: list[str] = []  # accumulate results across steps for later steps
    for step_num in range(1, len(plan["steps"]) + 1):
        step_results = execute_step(plan, step_num, prior_observations)
        prior_observations.extend(step_results)


print(f"Planning agent with {MODEL} — empty line or Ctrl+C to quit.")
print("Try: Compare weather in Tokyo and London, then say which is warmer.")
print("After the plan prints, approve with y to enter execute phase (tools enabled).")
while True:  # outer loop: one user question at a time
    try:
        user = input("\n> ").strip()
    except (EOFError, KeyboardInterrupt):
        break
    if not user:
        break

    current_plan = request_plan(user)  # Phase 1 — plan only; Python stores result here
    if current_plan is None:
        continue  # planning failed — do not enter execute phase

    if not confirm_execute():
        continue  # user declined — skip execute phase; no tools run

    print("\n[execute phase] starting — tools enabled")
    execute_plan(current_plan)  # Phase 2 — step-by-step execution with tools enabled
