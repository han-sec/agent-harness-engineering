# Step 6: multiple tools. Same agent loop as 04 — model picks from a menu.
import json
import re
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

URL = "http://localhost:1234/v1/chat/completions"
MODEL = "gemma-4-12b-it-mlx"

TOOLS = {}  # name -> function; the menu Python can actually run


def get_weather(city: str) -> str:
    """Fake weather — real agents would call an API here."""
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
    try:
        now = datetime.now(ZoneInfo(timezone))
    except ZoneInfoNotFoundError:
        return f"Error: unknown timezone {timezone!r}. Try UTC or America/New_York."
    return now.strftime(f"The time in {timezone} is %H:%M %Z")


TOOLS["get_weather"] = get_weather
TOOLS["calculate"] = calculate
TOOLS["get_time"] = get_time

# The menu the model reads — keep in sync with TOOLS above.
TOOL_MENU = """\
- get_weather(city) — weather for a city. Example: TOOL:get_weather:Tokyo
- calculate(expr) — math expression. Example: TOOL:calculate:15*7
- get_time(timezone) — current time. Example: TOOL:get_time:UTC"""

SYSTEM = f"""You are a helpful assistant with access to tools.

When you need a tool, include this line in your reply:
TOOL:tool_name:argument
(Do not wrap it in thinking tags or other markup.)
Pick the best tool for the job. Call one tool per reply.

Available tools:
{TOOL_MENU}

After you receive an Observation, answer the user in plain language."""


def stream_chat(messages):
    """POST the history, print tokens as they arrive, return the full reply."""
    req = urllib.request.Request(
        URL,
        data=json.dumps({"model": MODEL, "messages": messages, "stream": True}).encode(),
        headers={"Content-Type": "application/json"},
    )
    parts = []
    with urllib.request.urlopen(req) as resp:
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
    """Find `TOOL:name:arg` in the reply and run it. Returns None if not found."""
    match = re.search(r"TOOL:(\w+):(.+)", line.strip())
    if not match:
        return None
    name, arg = match.group(1), match.group(2).strip()
    fn = TOOLS.get(name)
    if not fn:
        return f"Unknown tool: {name}"
    print(f"\n[tool] {name}({arg!r})")
    return fn(arg)


history = [{"role": "system", "content": SYSTEM}]
print(f"Chatting with {MODEL} — empty line or Ctrl+C to quit.")
print("Tools:", ", ".join(TOOLS))
while True:
    try:
        user = input("\n> ").strip()
    except (EOFError, KeyboardInterrupt):
        break
    if not user:
        break
    history.append({"role": "user", "content": user})

    while True:
        reply = stream_chat(history)
        history.append({"role": "assistant", "content": reply})
        result = run_tool(reply)
        if result is None:
            break
        history.append({"role": "user", "content": f"Observation: {result}"})
