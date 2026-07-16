# Step 3: streaming. Same endpoint, "stream": true. The response is
# Server-Sent Events: lines of `data: {json}`, ending with `data: [DONE]`.
import json          # serialize request and parse each streamed JSON chunk
import urllib.request  # make HTTP calls without extra libraries

req = urllib.request.Request(
    "http://localhost:1234/v1/chat/completions",  # same endpoint as 01_chat.py
    data=json.dumps({
        "model": "gemma-4-12b-it-mlx",  # must match a model loaded in LM Studio
        "messages": [{"role": "user", "content": "Write a haiku about local LLMs."}],
        "stream": True,  # ask for tokens as they're generated, not one big response
    }).encode(),  # HTTP body must be bytes
    headers={"Content-Type": "application/json"},  # tell the server we're sending JSON
)

with urllib.request.urlopen(req) as resp:  # connection stays open while tokens arrive
    for raw in resp:  # read SSE lines one at a time
        line = raw.decode().strip()  # bytes -> str, trim whitespace
        if not line.startswith("data: "):  # skip non-SSE lines (blank, comments)
            continue
        payload = line[len("data: "):]  # strip the "data: " prefix
        if payload == "[DONE]":  # stream finished
            break
        delta = json.loads(payload)["choices"][0]["delta"]  # one incremental update
        print(delta.get("content", ""), end="", flush=True)  # print token immediately
print()  # newline after streaming ends
