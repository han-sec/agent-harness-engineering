# Step 11: file agent. Read-only file tools in a sandbox — same agent loop, real grounding.
# Builds on section_2/08b_context_management/08b_context_management.py.
#
# NEW in this lesson:
#   read_file, list_dir, grep — tools that touch the real filesystem
#   safe_path() — every path must stay inside workspace/ (no ../ escapes)
#   Output caps — large files don't blow the context window
#   strip_template_noise() — Gemma/LM Studio may emit <|channel> tags (runtime layer)
import json          # serialize the request body to JSON
import re            # parse TOOL:name:arg; search file contents in grep
import urllib.error  # catch "model offline" connection errors
import urllib.request  # make HTTP calls without extra libraries
from pathlib import Path  # safe paths and file reads — stdlib only

URL = "http://localhost:1234/v1/chat/completions"  # LM Studio OpenAI-compatible endpoint
MODEL = "gemma-4-12b-it-mlx"  # must match a model loaded in LM Studio
MODEL_CONTEXT = 8192  # LM Studio hard ceiling — input + output in one request
MAX_HISTORY_TOKENS = 4000  # soft budget — from 08b
MAX_TOOL_ROUNDS = 8  # file tasks may need list_dir → grep → read_file
MAX_READ_CHARS = 8000  # cap read_file output so one file doesn't fill history
MAX_GREP_MATCHES = 25  # cap grep hits returned to the model
MAX_EMPTY_RETRIES = 2  # nudge when reply is only template noise, no tool, no answer

# Gemma chat template tags — runtime layer, not your prompt (see README §5)
CHANNEL_TAG_RE = re.compile(r"<\|[^|>]*\|>?|<\|[^|>]*>", re.IGNORECASE)

# Sandbox root — all file tools resolve paths under here only
WORKSPACE = Path(__file__).resolve().parent / "workspace"

TOOLS = {}  # name -> function; the menu Python can actually run


def strip_template_noise(text: str) -> str:
    """Remove LM Studio / Gemma channel tags so we can detect empty vs real replies."""
    cleaned = CHANNEL_TAG_RE.sub("", text)
    cleaned = re.sub(r"\bthought\b", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def normalize_path_arg(raw: str) -> str:
    """Map common model mistakes to valid sandbox-relative paths."""
    rel = raw.strip().replace("\\", "/").lstrip("/")
    if rel in ("workspace", "workspace/"):
        return "."  # sandbox root — there is no subfolder named workspace/
    return rel


def safe_path(raw: str) -> Path | None:
    """Resolve a user/model path and reject anything outside WORKSPACE."""
    rel = normalize_path_arg(raw)
    if not rel:
        return None
    if rel.startswith("..") or "/../" in f"/{rel}/":
        return None  # block path traversal
    root = WORKSPACE.resolve()
    try:
        resolved = (root / rel).resolve()
        resolved.relative_to(root)  # raises if outside sandbox
    except ValueError:
        return None
    return resolved


def read_file(path_arg: str) -> str:
    """Read a text file under workspace/. Returns error strings, never raises."""
    target = safe_path(path_arg)
    if target is None:
        return f"Error: invalid path {path_arg!r} — must stay inside workspace/"
    if not target.exists():
        return f"Error: file not found: {path_arg}"
    if target.is_dir():
        return f"Error: {path_arg!r} is a directory — use list_dir instead"
    try:
        text = target.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return f"Error: {path_arg!r} is not UTF-8 text — cannot read as text"
    except OSError as exc:
        return f"Error: cannot read {path_arg!r}: {exc}"
    if len(text) > MAX_READ_CHARS:
        return text[:MAX_READ_CHARS] + f"\n\n[truncated — file is {len(text)} chars; showing first {MAX_READ_CHARS}]"
    return text


def list_dir(path_arg: str) -> str:
    """List names in a workspace directory. Use '.' or '' for workspace root."""
    raw = normalize_path_arg(path_arg) if path_arg.strip() else "."
    target = safe_path(raw)
    if target is None:
        return f"Error: invalid path {path_arg!r} — must stay inside workspace/"
    if not target.exists():
        return f"Error: directory not found: {raw}"
    if not target.is_dir():
        return f"Error: {raw!r} is a file — use read_file instead"
    try:
        names = sorted(target.iterdir(), key=lambda p: p.name.lower())
    except OSError as exc:
        return f"Error: cannot list {raw!r}: {exc}"
    if not names:
        return "(empty directory)"
    lines = []
    for entry in names:
        rel = entry.relative_to(WORKSPACE.resolve())
        suffix = "/" if entry.is_dir() else ""
        lines.append(f"{rel.as_posix()}{suffix}")
    return "\n".join(lines)


def grep(arg: str) -> str:
    """Search for pattern under path. Arg format: pattern:path (e.g. agents:notes)."""
    if ":" not in arg:
        return "Error: grep arg must be pattern:path — example: agents:notes"
    pattern, _, path_arg = arg.partition(":")
    pattern = pattern.strip()
    path_arg = path_arg.strip() or "."
    if not pattern:
        return "Error: grep pattern cannot be empty"
    target = safe_path(path_arg)
    if target is None:
        return f"Error: invalid path {path_arg!r} — must stay inside workspace/"
    if not target.exists():
        return f"Error: path not found: {path_arg}"
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        return f"Error: invalid regex pattern {pattern!r}: {exc}"

    files: list[Path] = []
    if target.is_file():
        files = [target]
    else:
        files = [p for p in target.rglob("*") if p.is_file()]

    hits: list[str] = []
    for file_path in sorted(files):
        try:
            lines = file_path.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue  # skip binary or unreadable files silently
        rel = file_path.relative_to(WORKSPACE.resolve()).as_posix()
        for line_num, line in enumerate(lines, 1):
            if regex.search(line):
                hits.append(f"{rel}:{line_num}: {line}")
                if len(hits) >= MAX_GREP_MATCHES:
                    return "\n".join(hits) + f"\n[truncated — showing first {MAX_GREP_MATCHES} matches]"
    if not hits:
        return f"(no matches for {pattern!r} under {path_arg})"
    return "\n".join(hits)


TOOLS["read_file"] = read_file
TOOLS["list_dir"] = list_dir
TOOLS["grep"] = grep

WORKSPACE_SNAPSHOT = ""  # filled after tools are registered — shown in system prompt


def build_system() -> str:
    """System prompt includes a live directory listing so the model skips bad guesses."""
    global WORKSPACE_SNAPSHOT
    WORKSPACE_SNAPSHOT = list_dir(".")
    tool_menu = """\
- list_dir(path) — list files/dirs. Example: TOOL:list_dir:.  Example: TOOL:list_dir:notes
- grep(pattern:path) — search text files. Example: TOOL:grep:agents:notes
- read_file(path) — read a file. Example: TOOL:read_file:notes/todo.md
Paths are relative to the workspace root below — NOT a folder called workspace/."""
    return f"""You are a file agent. Answer using ONLY file content from tools — do not guess.

When you need a tool, include this line in your reply:
TOOL:tool_name:argument
No thinking tags. No markdown. One tool per reply, on its own line.

Workflow: list_dir → grep or read_file → answer in plain English citing the file.

Workspace root listing (paths are relative to here):
{WORKSPACE_SNAPSHOT}

Available tools:
{tool_menu}

Path rules: use `.` or `notes/` — never `workspace/` (that path does not exist).

Observations may contain errors. Fix your path and retry.

When you have enough file content, stop calling tools and write the final answer."""


SYSTEM = build_system()
EMPTY_REPLY_NUDGE = (
    "Your last reply had no TOOL line and no plain-language answer — only template noise. "
    "Either call read_file on a path from list_dir (e.g. notes/todo.md) or answer the user now."
)


def estimate_tokens(text: str) -> int:
    """Rough token count — ~4 chars per token. From 08a."""
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
        return
    dropped = 0
    while len(history) > 1 and estimate_messages_tokens(history) > MAX_HISTORY_TOKENS:
        history.pop(1)
        dropped += 1
    if dropped:
        remaining = estimate_messages_tokens(history)
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


def find_tool_call(line: str) -> tuple[str, str] | None:
    """Return (name, arg) if a TOOL line exists in raw or cleaned text."""
    for text in (line, strip_template_noise(line)):
        match = re.search(r"TOOL:(\w+):(.+)", text)
        if match:
            return match.group(1), match.group(2).strip()
    return None


def run_tool(line: str) -> str | None:
    """Find TOOL:name:arg in raw or cleaned reply. Returns None if no tool call."""
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
    """True when stripped reply has no real answer text (template noise only)."""
    return len(strip_template_noise(reply)) < 15


history = [{"role": "system", "content": SYSTEM}]
print(f"File agent with {MODEL} — empty line or Ctrl+C to quit.")
print(f"Sandbox: {WORKSPACE}")
print('Try: "What does notes/todo.md say about agents?"')
print("Or: \"Find mentions of harness in notes/\"")
while True:
    try:
        user = input("\n> ").strip()
    except (EOFError, KeyboardInterrupt):
        break
    if not user:
        break
    history.append({"role": "user", "content": user})

    empty_retries = 0
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
                continue  # don't treat noise as a final answer
            break  # plain-language final answer (or gave up on nudges)
        empty_retries = 0  # successful tool call resets empty-reply counter
        preview = result if len(result) <= 120 else result[:120] + "..."
        print(f"[observation] {preview!r}")
        history.append({"role": "user", "content": f"Observation: {result}"})
    else:
        print(f"\n[error] Gave up after {MAX_TOOL_ROUNDS} tool rounds.")
