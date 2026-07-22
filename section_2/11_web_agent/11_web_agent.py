# Step 12: web agent. fetch_url with trust boundaries — same agent loop, untrusted network.
# Builds on section_2/10_file_agent/10_file_agent.py (harness patterns only — web-only tools here).
#
# NEW in this lesson:
#   fetch_url — GET a public https URL, return plain text for the model to summarize
#   is_url_allowed() — allowlist + block private/localhost targets (SSRF basics)
#   html_to_text() — strip HTML before stuffing content into history
#
# Note: file tools stay in lesson 10. A later recap lesson combines file + web + more.
import json          # LM Studio request body
import re            # parse TOOL lines; strip template noise
import socket        # resolve hostname — check for private IPs after DNS
import urllib.error  # HTTP errors, timeouts, connection failures
import urllib.request  # fetch_url GET requests — stdlib only
from html.parser import HTMLParser  # HTML → plain text without third-party packages
from urllib.parse import urlparse

URL = "http://localhost:1234/v1/chat/completions"  # LM Studio OpenAI-compatible endpoint
MODEL = "gemma-4-12b-it-mlx"  # must match a model loaded in LM Studio
MODEL_CONTEXT = 8192  # LM Studio hard ceiling
MAX_HISTORY_TOKENS = 4000  # soft budget — from 08b
MAX_TOOL_ROUNDS = 6  # fetch → maybe retry URL → summarize
MAX_FETCH_BYTES = 50_000  # cap downloaded body before it fills history
MAX_FETCH_CHARS = 8000  # cap text returned to the model after HTML stripping
FETCH_TIMEOUT = 10  # seconds — hung requests must not block the agent forever
MAX_EMPTY_RETRIES = 2  # nudge when reply is template noise only

# Teaching allowlist — only these hosts (lesson 11). Production agents use broader policy.
ALLOWED_HOSTS = frozenset({
    "example.com",
    "www.example.com",
    "example.org",
    "www.example.org",
})

# Gemma chat template tags — runtime layer (see README §5)
CHANNEL_TAG_RE = re.compile(r"<\|[^|>]*\|>?|<\|[^|>]*>", re.IGNORECASE)

TOOLS = {}  # name -> function


def strip_template_noise(text: str) -> str:
    """Remove LM Studio / Gemma channel tags so we can detect empty vs real replies."""
    cleaned = CHANNEL_TAG_RE.sub("", text)
    cleaned = re.sub(r"\bthought\b", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


class _TextExtractor(HTMLParser):
    """Collect visible text nodes — minimal HTML stripping for lesson 11."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self._parts.append(text)


def html_to_text(html: str) -> str:
    """Convert HTML to plain text — good enough for summarization, not a browser."""
    parser = _TextExtractor()
    try:
        parser.feed(html)
    except Exception:
        return html  # fallback: return raw if parser chokes on malformed HTML
    return re.sub(r"\n{3,}", "\n\n", "\n".join(parser._parts))


def _is_private_ip(ip: str) -> bool:
    """True for localhost and RFC1918-style addresses — block SSRF to internal services."""
    if ip.startswith("127.") or ip == "::1" or ip == "0.0.0.0":
        return True
    if ip.startswith("10.") or ip.startswith("192.168."):
        return True
    if ip.startswith("169.254."):
        return True
    if ip.startswith("172."):
        second = ip.split(".")[1] if ip.count(".") >= 3 else ""
        if second.isdigit() and 16 <= int(second) <= 31:
            return True
    return False


def is_url_allowed(url: str) -> tuple[bool, str]:
    """URL policy — harness decides before any network call. Model only proposes URLs."""
    parsed = urlparse(url.strip())
    if parsed.scheme != "https":
        return False, "only https:// URLs are allowed"
    host = (parsed.hostname or "").lower()
    if not host:
        return False, "missing hostname"
    if host in ("localhost", "0.0.0.0") or host.endswith(".local"):
        return False, "localhost and .local hosts are blocked"
    if host not in ALLOWED_HOSTS:
        allowed = ", ".join(sorted(ALLOWED_HOSTS))
        return False, f"host {host!r} not on allowlist ({allowed})"
    try:
        for info in socket.getaddrinfo(host, None):
            ip = info[4][0]
            if _is_private_ip(ip):
                return False, f"host {host!r} resolves to blocked address {ip}"
    except socket.gaierror as exc:
        return False, f"cannot resolve host {host!r}: {exc}"
    return True, ""


def fetch_url(url_arg: str) -> str:
    """GET a URL and return plain text. Errors are strings — never raise to the loop."""
    url = url_arg.strip()
    if not url:
        return "Error: URL cannot be empty"
    ok, reason = is_url_allowed(url)
    if not ok:
        return f"Error: URL blocked — {reason}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "agent-harness-course/1.0 (lesson-11)"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            raw = resp.read(MAX_FETCH_BYTES + 1)
    except urllib.error.HTTPError as exc:
        return f"Error: HTTP {exc.code} for {url}"
    except urllib.error.URLError as exc:
        return f"Error: cannot fetch {url}: {exc.reason}"
    except TimeoutError:
        return f"Error: timed out after {FETCH_TIMEOUT}s fetching {url}"
    if len(raw) > MAX_FETCH_BYTES:
        raw = raw[:MAX_FETCH_BYTES]
        truncated = True
    else:
        truncated = False
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return f"Error: response from {url} is not UTF-8 text"
    text = html_to_text(text)
    if not text.strip():
        return f"Error: no readable text extracted from {url}"
    if len(text) > MAX_FETCH_CHARS:
        text = text[:MAX_FETCH_CHARS] + f"\n\n[truncated — showing first {MAX_FETCH_CHARS} chars]"
    elif truncated:
        text += f"\n\n[truncated — download exceeded {MAX_FETCH_BYTES} bytes]"
    return text


TOOLS["fetch_url"] = fetch_url

ALLOWED_LIST = ", ".join(f"https://{h}" for h in sorted(ALLOWED_HOSTS))

SYSTEM = f"""You are a web research agent. Answer using ONLY content returned by fetch_url — do not guess.

When you need a tool, include this line in your reply:
TOOL:fetch_url:https://example.com
No thinking tags. No markdown. One tool per reply, on its own line.

Allowed hosts (https only):
{ALLOWED_LIST}

Workflow: fetch_url → read the Observation → summarize in plain English for the user.

Observations may contain errors (blocked URL, timeout, HTTP 404). Explain the error or try an allowed URL.

When you have page content, stop calling tools and write the final summary."""

EMPTY_REPLY_NUDGE = (
    "Your last reply had no TOOL line and no plain-language answer — only template noise. "
    "Either call fetch_url on an allowed https URL or summarize what you already fetched."
)
GIVE_UP_NUDGE = (
    "You hit the tool round limit. Tell the user plainly what you tried, "
    "what failed, and that you could not complete the request."
)


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def estimate_messages_tokens(messages: list) -> int:
    total = 0
    for msg in messages:
        total += estimate_tokens(msg.get("content", ""))
        total += 4
    return total


def trim_history(history: list) -> None:
    if len(history) <= 1:
        return
    dropped = 0
    while len(history) > 1 and estimate_messages_tokens(history) > MAX_HISTORY_TOKENS:
        history.pop(1)
        dropped += 1
    if dropped:
        remaining = estimate_messages_tokens(history)
        print(f"[context] dropped {dropped} old message(s), ~{remaining} tokens remain")


def stream_chat(messages) -> str | None:
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


def find_tool_call(line: str) -> tuple[str, str] | None:
    for text in (line, strip_template_noise(line)):
        match = re.search(r"TOOL:(\w+):(.+)", text)
        if match:
            return match.group(1), match.group(2).strip()
    return None


def run_tool(line: str) -> str | None:
    found = find_tool_call(line)
    if not found:
        return None
    name, arg = found
    fn = TOOLS.get(name)
    if not fn:
        return f"Error: unknown tool: {name}"
    print(f"\n[tool] {name}({arg!r})")
    try:
        return fn(arg)
    except Exception as exc:
        return f"Error: tool {name} crashed: {exc}"


def is_empty_reply(reply: str) -> bool:
    return len(strip_template_noise(reply)) < 15


history = [{"role": "system", "content": SYSTEM}]
print(f"Web agent with {MODEL} — empty line or Ctrl+C to quit.")
print(f"Allowed: {ALLOWED_LIST}")
print('Try: "Summarize https://example.com"')
print('Or: "Fetch http://127.0.0.1" (should be blocked)')
while True:
    try:
        user = input("\n> ").strip()
    except (EOFError, KeyboardInterrupt):
        break
    if not user:
        break
    history.append({"role": "user", "content": user})

    empty_retries = 0
    hit_round_limit = False
    for _ in range(1, MAX_TOOL_ROUNDS + 1):
        trim_history(history)
        prompt_tokens = estimate_messages_tokens(history)
        print(f"[tokens] ~{prompt_tokens} / {MAX_HISTORY_TOKENS} budget ({MODEL_CONTEXT} max)")
        reply = stream_chat(history)
        if reply is None:
            break
        history.append({"role": "assistant", "content": reply})
        result = run_tool(reply)
        if result is None:
            if is_empty_reply(reply) and empty_retries < MAX_EMPTY_RETRIES:
                empty_retries += 1
                print(f"\n[warn] template noise only — nudging model ({empty_retries}/{MAX_EMPTY_RETRIES})")
                history.append({"role": "user", "content": EMPTY_REPLY_NUDGE})
                continue
            break
        empty_retries = 0
        preview = result if len(result) <= 120 else result[:120] + "..."
        print(f"[observation] {preview!r}")
        history.append({"role": "user", "content": f"Observation: {result}"})
    else:
        hit_round_limit = True
        print(f"\n[error] Gave up after {MAX_TOOL_ROUNDS} tool rounds.")
        history.append({"role": "user", "content": GIVE_UP_NUDGE})
        stream_chat(history)  # one final turn — model explains failure to user
