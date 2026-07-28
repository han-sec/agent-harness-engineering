# Sub-agent harness — lessons 12–15 + eval_mode for lesson 16.
import json
import re
import urllib.error
import urllib.request
from pathlib import Path

import agent_log as log
import session_store as session
from human_confirm import confirm_action, set_eval_mode

URL = "http://localhost:1234/v1/chat/completions"
MODEL = "gemma-4-12b-it-mlx"
MODEL_CONTEXT = 8192
MAX_HISTORY_TOKENS = 4000
MAX_RESEARCHER_ROUNDS = 8
MAX_READ_CHARS = 8000
MAX_GREP_MATCHES = 25
MAX_EMPTY_RETRIES = 2
DEFAULT_OUTPUT_PATH = "output/summary.md"

CHANNEL_TAG_RE = re.compile(r"<\|[^|>]*\|>?|<\|[^|>]*>", re.IGNORECASE)
WORKSPACE = Path(__file__).resolve().parent / "workspace"
RESEARCHER_TOOLS = {}


def strip_template_noise(text: str) -> str:
    cleaned = CHANNEL_TAG_RE.sub("", text)
    cleaned = re.sub(r"\bthought\b", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def normalize_path_arg(raw: str) -> str:
    rel = raw.strip().replace("\\", "/").lstrip("/")
    if rel in ("workspace", "workspace/"):
        return "."
    return rel


def safe_path(raw: str) -> Path | None:
    rel = normalize_path_arg(raw)
    if not rel:
        return None
    if rel.startswith("..") or "/../" in f"/{rel}/":
        return None
    root = WORKSPACE.resolve()
    try:
        resolved = (root / rel).resolve()
        resolved.relative_to(root)
    except ValueError:
        return None
    return resolved


def read_file(path_arg: str) -> str:
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
            continue
        rel = file_path.relative_to(WORKSPACE.resolve()).as_posix()
        for line_num, line in enumerate(lines, 1):
            if regex.search(line):
                hits.append(f"{rel}:{line_num}: {line}")
                if len(hits) >= MAX_GREP_MATCHES:
                    return "\n".join(hits) + f"\n[truncated — {MAX_GREP_MATCHES} matches]"
    if not hits:
        return f"(no matches for {pattern!r} under {path_arg})"
    return "\n".join(hits)


def write_file(path_arg: str, content: str) -> str:
    target = safe_path(path_arg)
    if target is None:
        return f"Error: invalid path {path_arg!r} — must stay inside workspace/"
    preview = content[:200] + ("..." if len(content) > 200 else "")
    log.approval_requested("write_file", path_arg, preview)
    if not confirm_action(f"Write {len(content)} chars to {path_arg}?"):
        log.approval_denied("write_file", path_arg)
        return "Error: write rejected by human"
    log.approval_granted("write_file", path_arg)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    except OSError as exc:
        return f"Error: cannot write {path_arg!r}: {exc}"
    log.file_written(path_arg, len(content))
    return f"Wrote {len(content)} chars to {path_arg}"


RESEARCHER_TOOLS["read_file"] = read_file
RESEARCHER_TOOLS["list_dir"] = list_dir
RESEARCHER_TOOLS["grep"] = grep

WORKSPACE_SNAPSHOT = list_dir(".")

RESEARCHER_TOOL_MENU = """\
- list_dir(path) — Example: TOOL:list_dir:notes
- grep(pattern:path) — Example: TOOL:grep:agents:notes
- read_file(path) — Example: TOOL:read_file:notes/todo.md"""

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

WRITER_SYSTEM = """You are the WRITER sub-agent. You do not talk to the manager — your reply goes to the user.

Use ONLY the researcher facts provided. Do not invent file content. Do not call tools.
If previous conversation is included, use it for continuity — but ground factual claims in researcher facts.
Write a clear, short answer in plain language. Cite file paths when relevant."""

EMPTY_REPLY_NUDGE = (
    "No TOOL line and no facts yet. Call a file tool or return bullet facts now."
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
    while len(history) > 1 and estimate_messages_tokens(history) > MAX_HISTORY_TOKENS:
        history.pop(1)


def stream_chat(messages, label: str) -> str | None:
    log.llm_start(label, estimate_messages_tokens(messages))
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
        log.llm_error(label, str(exc.reason))
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
    reply = "".join(parts)
    log.llm_reply(label, reply, strip_template_noise(reply))
    return reply


def find_tool_call(line: str, tools: dict) -> tuple[str, str] | None:
    for text in (line, strip_template_noise(line)):
        match = re.search(r"TOOL:(\w+):(.+)", text)
        if match:
            name, arg = match.group(1), match.group(2).strip()
            if name in tools:
                return name, arg
    return None


def run_tool(line: str, tools: dict, label: str) -> str | None:
    found = find_tool_call(line, tools)
    if not found:
        return None
    name, arg = found
    print(f"\n[{label}] tool {name}({arg!r})")
    try:
        result = tools[name](arg)
    except Exception as exc:
        result = f"Error: tool {name} crashed: {exc}"
    log.tool_call(label, name, arg, result)
    return result


def is_empty_reply(reply: str) -> bool:
    return len(strip_template_noise(reply)) < 15


def run_researcher(task: str) -> str:
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
            log.agent_offline("researcher")
            return "[researcher offline — LM Studio unreachable]"
        last_reply = reply
        history.append({"role": "assistant", "content": reply})
        result = run_tool(reply, RESEARCHER_TOOLS, "researcher")
        if result is None:
            if is_empty_reply(reply) and empty_retries < MAX_EMPTY_RETRIES:
                empty_retries += 1
                print(f"[researcher] noise only — nudge ({empty_retries}/{MAX_EMPTY_RETRIES})")
                log.nudge("researcher", empty_retries)
                history.append({"role": "user", "content": EMPTY_REPLY_NUDGE})
                continue
            facts = strip_template_noise(reply)
            print(f"[researcher] returning facts ({len(facts)} chars)")
            log.researcher_done(facts)
            return facts or "[researcher returned no facts]"
        empty_retries = 0
        preview = result if len(result) <= 100 else result[:100] + "..."
        print(f"[researcher] observation {preview!r}")
        history.append({"role": "user", "content": f"Observation: {result}"})

    print("[researcher] hit round limit — returning last state")
    log.researcher_round_limit()
    return strip_template_noise(last_reply) or "[researcher hit tool round limit]"


def run_writer(task: str, facts: str, prior_context: str = "") -> str:
    parts = []
    if prior_context:
        parts.append(prior_context)
    parts.append(f"User question: {task}")
    parts.append(f"Researcher facts (use only these):\n{facts}")
    parts.append("Write the final answer for the user.")

    history = [
        {"role": "system", "content": WRITER_SYSTEM},
        {"role": "user", "content": "\n\n".join(parts)},
    ]
    reply = stream_chat(history, "writer")
    if reply is None:
        log.agent_offline("writer")
        return "[writer offline — LM Studio unreachable]"
    answer = strip_template_noise(reply) or "[writer returned empty reply]"
    log.writer_done(answer)
    return answer


def run_manager(user_question: str, *, eval_mode: bool = False) -> dict:
    """Run full pipeline. Returns {run_id, answer, facts} for eval scoring."""
    if eval_mode:
        set_eval_mode(True)
    try:
        run_id = log.begin_turn(user_question)

        prior_context = ""
        if not eval_mode:
            prior_turns = session.load_recent_turns()
            prior_context = session.format_prior_context(prior_turns)
            if prior_turns:
                print(f"[session] loaded {len(prior_turns)} prior turn(s) into writer context")

        print("[manager] received user question")
        print("[manager] → delegating to researcher")
        log.handoff("manager", "researcher")
        facts = run_researcher(user_question)

        print(f"[manager] ← researcher done ({len(facts)} chars)")
        log.handoff("researcher", "manager", facts_chars=len(facts))

        print("[manager] → delegating to writer")
        log.handoff("manager", "writer", facts_chars=len(facts))
        answer = run_writer(user_question, facts, prior_context)

        print("[manager] ← writer done")
        if not eval_mode:
            print(f"\n[manager] offer to save answer → {DEFAULT_OUTPUT_PATH}")
            result = write_file(DEFAULT_OUTPUT_PATH, answer)
            print(f"[manager] {result}")
            turn_id = session.save_turn(user_question, answer)
            print(f"[session] saved turn #{turn_id}")

        log.end_turn(len(answer))
        return {"run_id": run_id, "answer": answer, "facts": facts}
    finally:
        if eval_mode:
            set_eval_mode(False)
