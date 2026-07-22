# Step 13: sub-agents. Python manager delegates to researcher + writer — separate histories, same model.
# Builds on section_2/10_file_agent/10_file_agent.py (file tools live in researcher only).
#
# NEW in this lesson:
#   run_researcher() / run_writer() — each is its own API loop with isolated history
#   Python manager — orchestrates handoff (facts string); user only sees final writer output
#   Eval (lesson 16) later makes this pattern measurable at scale
import json          # serialize each sub-agent's messages list to JSON
import re            # parse TOOL lines; strip template noise; grep in file tools
import urllib.error  # catch "model offline" connection errors
import urllib.request  # POST to LM Studio — one call per sub-agent turn
from pathlib import Path  # sandbox file tools — copied from lesson 10

URL = "http://localhost:1234/v1/chat/completions"  # LM Studio OpenAI-compatible endpoint
MODEL = "gemma-4-12b-it-mlx"  # must match a model loaded in LM Studio
MODEL_CONTEXT = 8192  # LM Studio hard ceiling — input + output in one request
MAX_HISTORY_TOKENS = 4000  # soft budget per sub-agent — from 08b
MAX_RESEARCHER_ROUNDS = 8  # researcher may list → grep → read before returning facts
MAX_READ_CHARS = 8000  # cap read_file output so one file doesn't fill researcher history
MAX_GREP_MATCHES = 25  # cap grep hits returned to the model
MAX_EMPTY_RETRIES = 2  # nudge when reply is template noise only (no tool, no facts)

# Gemma chat template tags — runtime layer, not your prompt (see README §5)
CHANNEL_TAG_RE = re.compile(r"<\|[^|>]*\|>?|<\|[^|>]*>", re.IGNORECASE)

# Sandbox root — only the researcher sub-agent touches files (writer has no tools)
WORKSPACE = Path(__file__).resolve().parent / "workspace"

# Researcher-only tools — writer has no tools (lesson 12 boundary: gather vs synthesize)
RESEARCHER_TOOLS = {}


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
        return f"Error: {path_arg!r} is not UTF-8 text"
    except OSError as exc:
        return f"Error: cannot read {path_arg!r}: {exc}"
    if len(text) > MAX_READ_CHARS:
        return text[:MAX_READ_CHARS] + f"\n\n[truncated — {MAX_READ_CHARS} chars shown]"
    return text


def list_dir(path_arg: str) -> str:
    """List names in a workspace directory. Use '.' or '' for workspace root."""
    raw = normalize_path_arg(path_arg) if path_arg.strip() else "."
    target = safe_path(raw)
    if target is None:
        return f"Error: invalid path {path_arg!r}"
    if not target.exists():
        return f"Error: directory not found: {raw}"
    if not target.is_dir():
        return f"Error: {raw!r} is a file — use read_file"
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
        return f"Error: invalid path {path_arg!r}"
    if not target.exists():
        return f"Error: path not found: {path_arg}"
    try:
        regex = re.compile(pattern, re.IGNORECASE)
    except re.error as exc:
        return f"Error: invalid regex {pattern!r}: {exc}"
    files = [target] if target.is_file() else [p for p in target.rglob("*") if p.is_file()]
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
                    return "\n".join(hits) + f"\n[truncated — {MAX_GREP_MATCHES} matches]"
    if not hits:
        return f"(no matches for {pattern!r} under {path_arg})"
    return "\n".join(hits)


RESEARCHER_TOOLS["read_file"] = read_file
RESEARCHER_TOOLS["list_dir"] = list_dir
RESEARCHER_TOOLS["grep"] = grep

# Snapshot at startup — researcher system prompt shows real files so it skips bad path guesses
WORKSPACE_SNAPSHOT = list_dir(".")

RESEARCHER_TOOL_MENU = """\
- list_dir(path) — Example: TOOL:list_dir:notes
- grep(pattern:path) — Example: TOOL:grep:agents:notes
- read_file(path) — Example: TOOL:read_file:notes/todo.md"""

# Sub-agent 1 system prompt — file tools only; output is bullet facts, not user-facing prose
RESEARCHER_SYSTEM = f"""You are the RESEARCHER sub-agent. You do not talk to the user.

Your job: use file tools to gather facts for the manager. Workspace listing:
{WORKSPACE_SNAPSHOT}

When you need a tool:
TOOL:tool_name:argument
One tool per reply. No thinking tags.

Tools:
{RESEARCHER_TOOL_MENU}

When you have enough facts, stop calling tools. Reply with bullet facts only — cite file paths.
Do not write the final user-facing essay (the writer sub-agent does that)."""

# Sub-agent 2 system prompt — no tools; must stay faithful to the facts string from Python
WRITER_SYSTEM = """You are the WRITER sub-agent. You do not talk to the manager — your reply goes to the user.

Use ONLY the researcher facts provided. Do not invent file content. Do not call tools.
Write a clear, short answer in plain language. Cite file paths when relevant."""

EMPTY_REPLY_NUDGE = (
    "No TOOL line and no facts yet. Call a file tool or return bullet facts now."
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
    while len(history) > 1 and estimate_messages_tokens(history) > MAX_HISTORY_TOKENS:
        history.pop(1)  # keep system prompt; drop oldest user/assistant turn


def stream_chat(messages, label: str) -> str | None:
    """POST one sub-agent's history, print tokens live, return full reply (or None if offline).

    label — which box is calling (researcher / writer) so the terminal trace is readable.
    Same HTTP code as lesson 04; only the messages list differs per sub-agent.
    """
    print(f"\n[{label}] calling model...")
    req = urllib.request.Request(
        URL,
        data=json.dumps({"model": MODEL, "messages": messages, "stream": True}).encode(),
        headers={"Content-Type": "application/json"},
    )
    parts = []
    try:
        resp = urllib.request.urlopen(req)
    except urllib.error.URLError as exc:
        print(f"\n[error] Cannot reach LM Studio ({exc.reason})")
        return None
    with resp:
        for raw in resp:
            line = raw.decode().strip()
            if not line.startswith("data: "):
                continue  # SSE comment lines — skip
            payload = line[len("data: "):]
            if payload == "[DONE]":
                break  # stream finished
            token = json.loads(payload)["choices"][0]["delta"].get("content", "")
            parts.append(token)
            print(token, end="", flush=True)
    print()
    return "".join(parts)


def find_tool_call(line: str, tools: dict) -> tuple[str, str] | None:
    """Return (name, arg) if a TOOL line exists in raw or cleaned text.

    tools — only the researcher's registry; writer passes an empty dict so tools are ignored.
    """
    for text in (line, strip_template_noise(line)):
        match = re.search(r"TOOL:(\w+):(.+)", text)
        if match:
            name, arg = match.group(1), match.group(2).strip()
            if name in tools:
                return name, arg
    return None


def run_tool(line: str, tools: dict, label: str) -> str | None:
    """Run one tool call from a sub-agent reply. Returns None if no TOOL line found."""
    found = find_tool_call(line, tools)
    if not found:
        return None
    name, arg = found
    fn = tools[name]
    print(f"\n[{label}] tool {name}({arg!r})")
    try:
        return fn(arg)
    except Exception as exc:
        return f"Error: tool {name} crashed: {exc}"


def is_empty_reply(reply: str) -> bool:
    """True when stripped reply has no real answer text (template noise only)."""
    return len(strip_template_noise(reply)) < 15


def run_researcher(task: str) -> str:
    """Sub-agent box 1 — isolated history, file tools, returns fact string for manager.

    This is the same agent inner loop from lesson 04, but:
    - history starts fresh (writer never sees researcher turns)
    - system prompt forbids user-facing prose
    - exit condition is "bullet facts" not "answer the user"
    """
    # Fresh history — this list never merges with writer's history
    history = [
        {"role": "system", "content": RESEARCHER_SYSTEM},
        {"role": "user", "content": f"Research task from manager: {task}"},
    ]
    empty_retries = 0
    last_reply = ""

    for _ in range(1, MAX_RESEARCHER_ROUNDS + 1):
        trim_history(history)
        reply = stream_chat(history, "researcher")
        if reply is None:
            return "[researcher offline — LM Studio unreachable]"
        last_reply = reply
        history.append({"role": "assistant", "content": reply})
        result = run_tool(reply, RESEARCHER_TOOLS, "researcher")
        if result is None:
            # No tool line — model thinks it is done gathering facts
            if is_empty_reply(reply) and empty_retries < MAX_EMPTY_RETRIES:
                empty_retries += 1
                print(f"[researcher] noise only — nudge ({empty_retries}/{MAX_EMPTY_RETRIES})")
                history.append({"role": "user", "content": EMPTY_REPLY_NUDGE})
                continue  # don't treat template noise as finished research
            facts = strip_template_noise(reply)
            print(f"[researcher] returning facts ({len(facts)} chars)")
            return facts or "[researcher returned no facts]"
        empty_retries = 0  # successful tool call resets empty-reply counter
        preview = result if len(result) <= 100 else result[:100] + "..."
        print(f"[researcher] observation {preview!r}")
        history.append({"role": "user", "content": f"Observation: {result}"})

    # Round limit — return best-effort facts so manager can still hand off to writer
    print("[researcher] hit round limit — returning last state")
    return strip_template_noise(last_reply) or "[researcher hit tool round limit]"


def run_writer(task: str, facts: str) -> str:
    """Sub-agent box 2 — isolated history, no tools, user-facing prose only.

    Single LLM call (no inner tool loop). Python injects researcher facts as context —
    the only bridge between the two sub-agent boxes.
    """
    history = [
        {"role": "system", "content": WRITER_SYSTEM},
        {
            "role": "user",
            "content": (
                f"User question: {task}\n\n"
                f"Researcher facts (use only these):\n{facts}\n\n"
                "Write the final answer for the user."
            ),
        },
    ]
    reply = stream_chat(history, "writer")
    if reply is None:
        return "[writer offline — LM Studio unreachable]"
    return strip_template_noise(reply) or "[writer returned empty reply]"


def run_manager(user_question: str) -> str:
    """Python orchestrator — user talks to manager; sub-agents never see input() directly.

    No LLM here — just sequential Python calls and a string handoff (facts).
    Frameworks like CrewAI automate this same manager → worker pattern.
    """
    print("[manager] received user question")
    print("[manager] → delegating to researcher")
    facts = run_researcher(user_question)  # history A — tools, observations, facts
    print(f"[manager] ← researcher done ({len(facts)} chars)")
    print("[manager] → delegating to writer")
    answer = run_writer(user_question, facts)  # history B — facts in, prose out
    print("[manager] ← writer done")
    return answer


print(f"Sub-agents with {MODEL} — empty line or Ctrl+C to quit.")
print(f"Sandbox: {WORKSPACE}")
print("You talk to [manager]. [researcher] has file tools. [writer] has no tools.")
print('Try: "What does notes/todo.md say about agents?"')
while True:
    try:
        user = input("\n> ").strip()
    except (EOFError, KeyboardInterrupt):
        break
    if not user:
        break
    final = run_manager(user)  # one user turn → researcher loop → writer call → print
    print(f"\n--- answer ---\n{final}")
