# Step 8: errors. Tool failures become Observations — never crash, never loop forever.
import json          # serialize the request body to JSON
import re            # parse TOOL:name:arg from the model's reply
import urllib.error  # catch "model offline" connection errors
import urllib.request  # make HTTP calls without extra libraries
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

URL = "http://localhost:1234/v1/chat/completions"  # LM Studio OpenAI-compatible endpoint
MODEL = "gemma-4-12b-it-mlx"  # must match a model loaded in LM Studio
MAX_TOOL_ROUNDS = 5  # cap inner loop — model can't spin on tools forever

TOOLS = {}  # name -> function; the menu Python can actually run


def get_weather(city: str) -> str:
    """Fake weather — rejects empty city so the model can recover from bad args."""
    if not city.strip():
        return "Error: city cannot be empty"  # error string, not an exception — still an Observation
    return f"Sunny, 28°C in {city}"  # pretend result


def calculate(expr: str) -> str:
    """Evaluate a basic math expression. Numbers and + - * / ( ) only."""
    allowed = set("0123456789+-*/(). ")  # whitelist safe characters
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
        now = datetime.now(ZoneInfo(timezone))  # look up timezone
    except ZoneInfoNotFoundError:
        return f"Error: unknown timezone {timezone!r}. Try UTC or America/New_York."
    return now.strftime(f"The time in {timezone} is %H:%M %Z")


TOOLS["get_weather"] = get_weather  # register tools by name
TOOLS["calculate"] = calculate
TOOLS["get_time"] = get_time

TOOL_MENU = """\
- get_weather(city) — weather for a city. Example: TOOL:get_weather:Tokyo
- calculate(expr) — math expression. Example: TOOL:calculate:15*7
- get_time(timezone) — current time. Example: TOOL:get_time:UTC"""  # model reads this menu

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


def stream_chat(messages) -> str | None:
    """POST the history, print tokens as they arrive, return the full reply (or None if offline)."""
    req = urllib.request.Request(
        URL,
        data=json.dumps({"model": MODEL, "messages": messages, "stream": True}).encode(),  # body as bytes
        headers={"Content-Type": "application/json"},
    )
    parts = []  # collect streamed tokens into one reply string
    try:
        resp = urllib.request.urlopen(req)  # may raise URLError if LM Studio is down
    except urllib.error.URLError as exc:
        print(f"\n[error] Cannot reach LM Studio — is the server running? ({exc.reason})")
        return None  # caller stops this turn without crashing
    with resp:
        for raw in resp:  # read SSE lines as they arrive
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
        return None  # no tool call — caller treats reply as a normal answer
    name, arg = match.group(1), match.group(2).strip()
    fn = TOOLS.get(name)
    if not fn:
        return f"Error: unknown tool: {name}"  # model picked a tool we don't have
    print(f"\n[tool] {name}({arg!r})")
    try:
        return fn(arg)  # may return "Error: ..." or raise — both handled by caller
    except Exception as exc:
        return f"Error: tool {name} crashed: {exc}"  # unexpected crash → Observation, not traceback


history = [{"role": "system", "content": SYSTEM}]  # system prompt always first
print(f"Chatting with {MODEL} — empty line or Ctrl+C to quit.")
print("Tools:", ", ".join(TOOLS))
print(f"Max tool rounds per turn: {MAX_TOOL_ROUNDS}")
print('Try: "Weather in Tokyo" or provoke an error with an empty city arg.')
while True:  # outer loop: one user turn at a time
    try:
        user = input("\n> ").strip()
    except (EOFError, KeyboardInterrupt):
        break
    if not user:
        break
    history.append({"role": "user", "content": user})  # remember your message

    for round_num in range(1, MAX_TOOL_ROUNDS + 1):  # inner loop with a hard cap
        reply = stream_chat(history)
        if reply is None:
            break  # server unreachable — stop this turn gracefully
        history.append({"role": "assistant", "content": reply})  # remember what it said
        result = run_tool(reply)
        if result is None:
            break  # final answer for this turn — back to input()
        print(f"[observation] {result!r}")  # show what the model will read next
        history.append({"role": "user", "content": f"Observation: {result}"})  # feed result back to LLM
    else:
        # for/else: runs only if loop did NOT break — we hit the round cap
        print(f"\n[error] Gave up after {MAX_TOOL_ROUNDS} tool rounds.")
