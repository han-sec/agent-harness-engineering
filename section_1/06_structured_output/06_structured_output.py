# Step 7: structured output. Get reliable JSON from a messy model.
# Appendix A/B test: run section_1/06_appendix_bad_prompt/06_appendix_bad_prompt.py — same parser, vague prompt.
import json          # parse model replies and build HTTP request bodies
import re            # strip markdown code fences from model output
import urllib.request  # make HTTP calls without extra libraries

URL = "http://localhost:1234/v1/chat/completions"  # LM Studio OpenAI-compatible endpoint
MODEL = "gemma-4-12b-it-mlx"  # must match a model loaded in LM Studio
MAX_JSON_RETRIES = 3  # how many times to re-ask before giving up

JSON_SYSTEM = """You extract a city name from the user's weather question.
Reply with ONLY valid JSON — no markdown, no explanation, no other text.
Format: {"city": "CityName"}
Example: {"city": "Tokyo"}"""  # teaches the model the exact JSON shape we expect

RETRY_MESSAGE = 'Invalid JSON. Reply with ONLY: {"city": "..."}'  # fed back when parsing fails


def get_weather(city: str) -> str:
    """Fake weather — same stub as earlier lessons."""
    return f"Sunny, 28°C in {city}"  # pretend result; proves parsed JSON can drive real code


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


def strip_json(text: str) -> str:
    """Pull a JSON object out of common model wrappers."""
    text = text.strip()  # remove leading/trailing whitespace
    if text.startswith("```"):  # model wrapped JSON in a markdown code block
        text = re.sub(r"^```(?:json)?\s*", "", text)  # drop opening ``` or ```json
        text = re.sub(r"\s*```$", "", text)  # drop closing ```
    start = text.find("{")  # find first { in case of extra chatter
    end = text.rfind("}")  # find last }
    if start != -1 and end != -1:  # both braces found
        text = text[start : end + 1]  # keep only the JSON object slice
    return text.strip()  # return cleaned text ready for json.loads


def parse_city(reply: str) -> str | None:
    """Parse {"city": "..."} from model text. Returns None on any failure."""
    try:
        data = json.loads(strip_json(reply))  # str -> Python dict (may raise JSONDecodeError)
    except json.JSONDecodeError:
        return None  # syntax error — caller will retry
    if not isinstance(data, dict):
        return None  # expected an object, got a list or string
    city = data.get("city")  # safe lookup; returns None if key missing
    if not isinstance(city, str) or not city.strip():
        return None  # reject null, numbers, or empty strings
    return city.strip()  # success — normalized city name


def extract_city(user_message: str) -> str | None:
    """Ask the model for JSON, retry when parsing fails."""
    history = [
        {"role": "system", "content": JSON_SYSTEM},  # JSON-only instructions
        {"role": "user", "content": user_message},  # the weather question to extract from
    ]
    for attempt in range(1, MAX_JSON_RETRIES + 1):  # try up to MAX_JSON_RETRIES times
        print(f"\n[json attempt {attempt}]")  # show which attempt we're on
        reply = stream_chat(history)  # ask the LLM; prints and returns full reply
        city = parse_city(reply)  # try to pull {"city": "..."} from the reply
        if city:
            print(f"[parsed] {city!r}")  # show what we successfully extracted
            return city  # done — valid JSON with a city string
        history.append({"role": "assistant", "content": reply})  # remember the bad reply
        history.append({"role": "user", "content": RETRY_MESSAGE})  # tell model to fix format
    return None  # all retries failed


print(f"Structured output with {MODEL} — empty line or Ctrl+C to quit.")
print('Try: "What\'s the weather in Tokyo?"')  # example prompt for the learner
while True:  # one user turn at a time
    try:
        user = input("\n> ").strip()  # read what you typed
    except (EOFError, KeyboardInterrupt):
        break  # Ctrl+C or Ctrl+D to quit
    if not user:
        break  # empty line to quit

    city = extract_city(user)  # step 1: get {"city": "..."} from the model
    if not city:
        print("[error] Could not get valid JSON after retries.")  # parsing never succeeded
        continue  # skip to next input — don't call get_weather with bad data

    weather = get_weather(city)  # step 2: use parsed city in Python code
    print(f"\n[result] {weather}")  # step 3: show the final answer
