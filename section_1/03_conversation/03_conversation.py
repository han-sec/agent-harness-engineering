# Step 4: turn-based chat = streaming (for display) + history append (for memory).
import json          # serialize request and parse each streamed JSON chunk
import urllib.request  # make HTTP calls without extra libraries

URL = "http://localhost:1234/v1/chat/completions"  # LM Studio OpenAI-compatible endpoint
MODEL = "gemma-4-12b-it-mlx"  # must match a model loaded in LM Studio


def stream_chat(messages):
    """POST the history, print tokens as they arrive, return the full reply."""
    req = urllib.request.Request(
        URL,
        data=json.dumps({"model": MODEL, "messages": messages, "stream": True}).encode(),  # full history each call
        headers={"Content-Type": "application/json"},  # tell the server we're sending JSON
    )
    parts = []  # collect streamed tokens to return the full reply string
    with urllib.request.urlopen(req) as resp:  # connection stays open while tokens arrive
        for raw in resp:  # read SSE lines one at a time
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


history = [{"role": "system", "content": "You are a concise assistant."}]  # starts every conversation
print(f"Chatting with {MODEL} — empty line or Ctrl+C to quit.")
while True:  # keep chatting until you quit
    try:
        user = input("\n> ").strip()  # read what you typed
    except (EOFError, KeyboardInterrupt):
        break  # Ctrl+C or Ctrl+D to quit
    if not user:
        break  # empty line to quit
    history.append({"role": "user", "content": user})  # remember your message
    reply = stream_chat(history)  # send full history; model sees everything so far
    history.append({"role": "assistant", "content": reply})  # remember its answer for next turn
