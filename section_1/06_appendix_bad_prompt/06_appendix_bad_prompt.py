# Appendix to 06: BAD prompt on purpose — compare with section_1/06_structured_output/06_structured_output.py
#
# Same parsing code. Only the system prompt is vague (no format line, no example).
# Run both scripts with the same question and count [json attempt N] lines.
#
# You are NOT training the model — you are instructing it at inference time.
# Examples + exact format in the prompt raise the odds of parseable JSON on attempt 1.
import json          # parse model replies and build HTTP request bodies
import re            # strip markdown code fences from model output
import urllib.request  # make HTTP calls without extra libraries

URL = "http://localhost:1234/v1/chat/completions"  # LM Studio OpenAI-compatible endpoint
MODEL = "gemma-4-12b-it-mlx"  # must match a model loaded in LM Studio
MAX_JSON_RETRIES = 3  # same cap as the good version — fair comparison

# FAULTY: vague, no format spec, no example — model guesses shape and adds chatter
BAD_JSON_SYSTEM = "Extract the city from the user's weather question. Reply in JSON."

# Also vague — doesn't show the model what correct looks like
BAD_RETRY_MESSAGE = "That was not valid JSON. Try again."

RETRY_MESSAGE = BAD_RETRY_MESSAGE  # alias so extract_city stays identical to lesson 06


def get_weather(city: str) -> str:
    """Fake weather — same stub as lesson 06."""
    return f"Sunny, 28°C in {city}"


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


def strip_json(text: str) -> str:
    """Pull a JSON object out of common model wrappers — same as lesson 06."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return text.strip()


def parse_city(reply: str) -> str | None:
    """Parse {"city": "..."} from model text. Returns None on any failure."""
    try:
        data = json.loads(strip_json(reply))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    city = data.get("city")
    if not isinstance(city, str) or not city.strip():
        return None
    return city.strip()


def extract_city(user_message: str) -> str | None:
    """Ask the model for JSON, retry when parsing fails."""
    history = [
        {"role": "system", "content": BAD_JSON_SYSTEM},  # <-- only real difference vs 06
        {"role": "user", "content": user_message},
    ]
    for attempt in range(1, MAX_JSON_RETRIES + 1):
        print(f"\n[json attempt {attempt}]")
        reply = stream_chat(history)
        city = parse_city(reply)
        if city:
            print(f"[parsed] {city!r}")
            return city
        print(f"[parse fail] model sent: {reply!r}")  # see the messy reply — key teaching moment
        history.append({"role": "assistant", "content": reply})
        history.append({"role": "user", "content": RETRY_MESSAGE})
    return None


print("APPENDIX — bad prompt demo (compare with 06_structured_output.py)")
print(f"Model: {MODEL} — empty line or Ctrl+C to quit.")
print('Try the same question in both files: "What\'s the weather in Tokyo?"')
print("Watch for: extra prose, markdown fences, wrong keys like location/name.\n")
while True:
    try:
        user = input("\n> ").strip()
    except (EOFError, KeyboardInterrupt):
        break
    if not user:
        break

    city = extract_city(user)
    if not city:
        print("[error] Could not get valid JSON after retries.")
        continue

    weather = get_weather(city)
    print(f"\n[result] {weather}")
