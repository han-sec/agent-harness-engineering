# Step 9b: context management. Trim history when over budget — uses 08a token estimate.
# Builds on 08a_token_estimate.py.
import json          # serialize the request body to JSON
import re            # parse TOOL:name:arg from the model's reply
import urllib.error  # catch "model offline" connection errors
import urllib.request  # make HTTP calls without extra libraries
from datetime import datetime  # get_time tool
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError  # timezone lookup for get_time

URL = "http://localhost:1234/v1/chat/completions"  # LM Studio OpenAI-compatible endpoint
MODEL = "gemma-4-12b-it-mlx"  # must match a model loaded in LM Studio
MODEL_CONTEXT = 8192  # LM Studio hard ceiling — input + output in one request
MAX_HISTORY_TOKENS = 4000  # soft budget — well below 8192; leaves room for reply
MAX_TOOL_ROUNDS = 5  # cap inner loop — model can't spin on tools forever

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

SYSTEM = f"""You are a helpful assistant with access to tools.

When you need a tool, include this line in your reply:
TOOL:tool_name:argument
(Do not wrap it in thinking tags or other markup.)
Pick the best tool for the job. Call one tool per reply.

Available tools:
{TOOL_MENU}

Observations may contain errors (e.g. "Error: city cannot be empty").
Read the error, fix your tool argument, and try again — or explain the problem to the user.

After you receive a successful Observation, answer the user in plain language."""


def estimate_tokens(text: str) -> int:
    """Rough token count — ~4 chars per token. From 08a; used for eval and trimming."""
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
        remaining = estimate_messages_tokens(history)  # show size after trim
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


history = [{"role": "system", "content": SYSTEM}]  # system prompt — never trimmed
print(f"Context management with {MODEL} — empty line or Ctrl+C to quit.")
print(f"Model context: {MODEL_CONTEXT} | history budget: {MAX_HISTORY_TOKENS} tokens")
print("Chat a lot — watch [context] drop old turns while system prompt stays.")
while True:  # outer loop: one user turn at a time
    try:
        user = input("\n> ").strip()
    except (EOFError, KeyboardInterrupt):
        break
    if not user:
        break
    history.append({"role": "user", "content": user})

    for round_num in range(1, MAX_TOOL_ROUNDS + 1):  # inner loop: tool rounds
        trim_history(history)  # NEW: drop old turns before sending to model
        prompt_tokens = estimate_messages_tokens(history)  # size after trim
        print(f"[tokens] ~{prompt_tokens} / {MAX_HISTORY_TOKENS} budget ({MODEL_CONTEXT} max)")
        reply = stream_chat(history)  # only the trimmed history goes over the wire
        if reply is None:
            break
        history.append({"role": "assistant", "content": reply})
        result = run_tool(reply)
        if result is None:
            break
        print(f"[observation] {result!r}")
        history.append({"role": "user", "content": f"Observation: {result}"})
    else:
        print(f"\n[error] Gave up after {MAX_TOOL_ROUNDS} tool rounds.")
