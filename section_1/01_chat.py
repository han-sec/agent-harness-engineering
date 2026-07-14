# Step 2: a chat completion is just an HTTP POST with JSON. Stdlib only.
import json          # serialize the request body and parse the response
import urllib.request  # make HTTP calls without extra libraries

req = urllib.request.Request(
    "http://localhost:1234/v1/chat/completions",  # LM Studio OpenAI-compatible endpoint
    data=json.dumps({
        "model": "gemma-4-12b-it-mlx",  # must match a model loaded in LM Studio
        "messages": [
            {"role": "system", "content": "You are a concise assistant."},  # sets behavior
            {"role": "user", "content": "Explain what a token is in one sentence."},  # your question
        ],
        "temperature": 0.7,  # 0 = deterministic, higher = more random
    }).encode(),  # HTTP body must be bytes
    headers={"Content-Type": "application/json"},  # tell the server we're sending JSON
)

with urllib.request.urlopen(req) as resp:  # send POST and wait for the full response
    body = json.load(resp)  # parse JSON body into a Python dict

print(body["choices"][0]["message"]["content"])  # the assistant's reply text
print("---")
print("tokens used:", body["usage"])  # prompt/completion token counts from the API
