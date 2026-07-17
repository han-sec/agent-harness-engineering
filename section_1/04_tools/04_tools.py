# Step 5: tools. Same chat loop as 03, but the model can trigger Python functions.
import json          # serialize the request body to JSON
import re            # parse TOOL:name:arg from the model's reply
import urllib.request  # make HTTP calls without extra libraries

URL = "http://localhost:1234/v1/chat/completions"  # LM Studio OpenAI-compatible endpoint
MODEL = "gemma-4-12b-it-mlx"  # must match a model loaded in LM Studio

TOOLS = {}  # name -> function; populated after tool functions are defined


def get_weather(city: str) -> str:
    """Fake weather — real agents would call an API here."""
    return f"Sunny, 28°C in {city}"  # pretend result; replace with a real API later


TOOLS["get_weather"] = get_weather  # register so run_tool() can look it up by name


def stream_chat(messages):
    """POST the history, print tokens as they arrive, return the full reply."""
    req = urllib.request.Request(
        URL,
        data=json.dumps({"model": MODEL, "messages": messages, "stream": True}).encode(),  # body as bytes
        headers={"Content-Type": "application/json"},  # tell the server we're sending JSON
    )
    parts = []  # collect streamed tokens to return the full reply string
    with urllib.request.urlopen(req) as resp:  # open the HTTP connection
        for raw in resp:  # read SSE lines as they arrive
            line = raw.decode().strip()  # bytes -> str, trim whitespace
            if not line.startswith("data: "):  # skip non-SSE lines (blank, comments)
                continue
            payload = line[len("data: "):]  # strip the "data: " prefix
            if payload == "[DONE]":  # stream finished
                break
            token = json.loads(payload)["choices"][0]["delta"].get("content", "")  # one text chunk
            parts.append(token)  # save for the final reply
            print(token, end="", flush=True)  # show token immediately in the terminal
    print()  # newline after streaming ends
    return "".join(parts)  # full assistant reply as one string


def run_tool(line: str) -> str | None:
    """Find `TOOL:name:arg` in the reply and run it. Returns None if not found."""
    # search, not fullmatch — models often wrap tool calls in extra text (e.g. thinking tags)
    match = re.search(r"TOOL:(\w+):(.+)", line.strip())
    if not match:
        return None  # no tool call — caller treats reply as a normal answer
    name, arg = match.group(1), match.group(2).strip()  # e.g. get_weather, Kuala Lumpur
    fn = TOOLS.get(name)  # look up the Python function by name
    if not fn:
        return f"Unknown tool: {name}"  # model asked for a tool we don't have
    print(f"\n[tool] {name}({arg!r})")  # show you Python is running, not the model
    return fn(arg)  # call the tool and return its result


SYSTEM = """You are a helpful assistant with access to tools.

When you need a tool, include this line in your reply:
TOOL:tool_name:argument
(Do not wrap it in thinking tags or other markup.)

Available tools:
- get_weather(city) — get weather for a city. Example: TOOL:get_weather:Tokyo

After you receive an Observation, answer the user in plain language."""


history = [{"role": "system", "content": SYSTEM}]  # system prompt teaches tool format + when to use it
print(f"Chatting with {MODEL} — empty line or Ctrl+C to quit.")
while True:  # outer loop: one user turn at a time
    try:
        user = input("\n> ").strip()  # read what you typed
    except (EOFError, KeyboardInterrupt):
        break  # Ctrl+C or Ctrl+D to quit
    if not user:
        break  # empty line to quit
    history.append({"role": "user", "content": user})  # remember your message

    # inner loop: model may call a tool, get an Observation, then answer
    while True:
        reply = stream_chat(history)  # ask the LLM; prints and returns full reply
        history.append({"role": "assistant", "content": reply})  # remember what it said
        result = run_tool(reply)  # None = normal text; str = tool ran, here's the result
        if result is None:
            break  # final answer for this turn — back to input()
        history.append({"role": "user", "content": f"Observation: {result}"})  # feed result back to LLM
