# Capstone harness — lessons 09–16 combined.
#
# Architecture (lesson 12): Python MANAGER orchestrates; model never picks sub-agents.
#   run_manager()  → fixed pipeline
#   run_planner()  → JSON plan, NO tools (lesson 09 guard rail)
#   run_researcher() → tool loop: file + web (lessons 10 + 11)
#   run_writer()   → cited answer, no tools (lesson 12)
#   write_file()   → HITL gate before disk write (lesson 14)
#
# Supporting modules (imported, not duplicated here):
#   agent_log, session_store, human_confirm
import json
import re
import socket
import urllib.error
import urllib.request
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

import agent_log as log
import session_store as session
from harness_routes import builtin_answer, is_meta_question
from human_confirm import confirm_action, set_eval_mode

# --- LM Studio + budgets (from 08a/08b) ---
URL = "http://localhost:1234/v1/chat/completions"
MODEL = "gemma-4-12b-it-mlx"
MODEL_CONTEXT = 8192  # hard ceiling — logged for awareness, not enforced here
MAX_HISTORY_TOKENS = 4000  # soft trim inside researcher loop
MAX_PLAN_RETRIES = 3  # retry bad plan JSON before aborting turn
MAX_RESEARCHER_ROUNDS = 10  # tool loop safety cap
MAX_READ_CHARS = 8000  # file tool output cap (lesson 10)
MAX_GREP_MATCHES = 25
MAX_FETCH_BYTES = 50_000  # web download cap (lesson 11)
MAX_FETCH_CHARS = 8000
FETCH_TIMEOUT = 10
MAX_EMPTY_RETRIES = 2  # nudge when model returns template noise only
DEFAULT_OUTPUT_PATH = "output/answer.md"  # saved after HITL approval

# Teaching allowlist — production would use config, not a hardcoded set
ALLOWED_HOSTS = frozenset({
    "example.com",
    "www.example.com",
    "example.org",
    "www.example.org",
})

# Gemma/LM Studio may emit <|channel|> tags — strip before parsing (README §5)
CHANNEL_TAG_RE = re.compile(r"<\|[^|>]*\|>?|<\|[^|>]*>", re.IGNORECASE)
WORKSPACE = Path(__file__).resolve().parent / "workspace"  # sandbox root (lesson 10)
RESEARCHER_TOOLS = {}  # populated below — only these names can run


# ---------------------------------------------------------------------------
# Helpers — template noise + path sandbox (lesson 10)
# ---------------------------------------------------------------------------

def strip_template_noise(text: str) -> str:
    """Remove runtime tags so is_empty_reply() and tool parsing see real content."""
    cleaned = CHANNEL_TAG_RE.sub("", text)
    cleaned = re.sub(r"\bthought\b", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def normalize_path_arg(raw: str) -> str:
    """Map model mistakes like 'workspace/docs' → 'docs' (sandbox-relative)."""
    rel = raw.strip().replace("\\", "/").lstrip("/")
    if rel in ("workspace", "workspace/"):
        return "."
    return rel


def safe_path(raw: str) -> Path | None:
    """Reject paths outside WORKSPACE — every file tool calls this first."""
    rel = normalize_path_arg(raw)
    if not rel:
        return None
    if rel.startswith("..") or "/../" in f"/{rel}/":
        return None  # block ../ escapes
    root = WORKSPACE.resolve()
    try:
        resolved = (root / rel).resolve()
        resolved.relative_to(root)  # raises if outside sandbox
    except ValueError:
        return None
    return resolved


# ---------------------------------------------------------------------------
# File tools (lesson 10) — return error strings, never raise to the loop
# ---------------------------------------------------------------------------

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
    """Arg format pattern:path — e.g. refund:docs searches all files under docs/."""
    if ":" not in arg:
        return "Error: grep arg must be pattern:path — example: refund:docs"
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


# ---------------------------------------------------------------------------
# Web tool (lesson 11) — harness checks URL before any network call
# ---------------------------------------------------------------------------

class _TextExtractor(HTMLParser):
    """Collect visible text nodes — minimal HTML stripping."""

    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self._parts.append(text)


def html_to_text(html: str) -> str:
    parser = _TextExtractor()
    try:
        parser.feed(html)
    except Exception:
        return html  # malformed HTML — return raw rather than crash
    return re.sub(r"\n{3,}", "\n\n", "\n".join(parser._parts))


def _is_private_ip(ip: str) -> bool:
    """Block SSRF to localhost / RFC1918 after DNS resolution."""
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
    """URL policy — model proposes URLs; Python decides before fetch_url runs."""
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
    ok, reason = is_url_allowed(url_arg.strip())
    if not ok:
        return f"Error: URL blocked — {reason}"
    req = urllib.request.Request(
        url_arg.strip(),
        headers={"User-Agent": "agent-harness-course/1.0 (lesson-17-capstone)"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=FETCH_TIMEOUT) as resp:
            raw = resp.read(MAX_FETCH_BYTES + 1)
    except urllib.error.HTTPError as exc:
        return f"Error: HTTP {exc.code} for {url_arg}"
    except urllib.error.URLError as exc:
        return f"Error: cannot fetch {url_arg}: {exc.reason}"
    except TimeoutError:
        return f"Error: timed out after {FETCH_TIMEOUT}s fetching {url_arg}"
    truncated = len(raw) > MAX_FETCH_BYTES
    if truncated:
        raw = raw[:MAX_FETCH_BYTES]
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        return f"Error: response from {url_arg} is not UTF-8 text"
    text = html_to_text(text)
    if not text.strip():
        return f"Error: no readable text extracted from {url_arg}"
    if len(text) > MAX_FETCH_CHARS:
        text = text[:MAX_FETCH_CHARS] + f"\n\n[truncated — first {MAX_FETCH_CHARS} chars]"
    elif truncated:
        text += f"\n\n[truncated — download exceeded {MAX_FETCH_BYTES} bytes]"
    return text


# ---------------------------------------------------------------------------
# Write tool (lesson 14) — manager calls this, not the researcher
# ---------------------------------------------------------------------------

def write_file(path_arg: str, content: str) -> str:
    """Save writer output — gated by human_confirm (or auto-approved in eval mode)."""
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


# Register tools the researcher loop can dispatch
RESEARCHER_TOOLS["read_file"] = read_file
RESEARCHER_TOOLS["list_dir"] = list_dir
RESEARCHER_TOOLS["grep"] = grep
RESEARCHER_TOOLS["fetch_url"] = fetch_url

PLANNER_TOOL_NAMES = frozenset(RESEARCHER_TOOLS.keys())  # validate plan JSON references
WORKSPACE_SNAPSHOT = list_dir("docs")  # baked into prompts at import time
ALLOWED_LIST = ", ".join(f"https://{h}" for h in sorted(ALLOWED_HOSTS))

RESEARCHER_TOOL_MENU = """\
- list_dir(path) — Example: TOOL:list_dir:docs
- grep(pattern:path) — Example: TOOL:grep:refund:docs
- read_file(path) — Example: TOOL:read_file:docs/onboarding.md
- fetch_url(url) — Example: TOOL:fetch_url:https://example.com (https allowlist only)"""

# --- Sub-agent system prompts (each role gets its own isolated history) ---

PLAN_SYSTEM = f"""You are the PLANNER sub-agent for an internal docs Q&A assistant.

Internal docs live under docs/ in the workspace. Listing:
{WORKSPACE_SNAPSHOT}

Start with docs/index.md for overviews, "what docs exist", or broad questions.
Use docs/team-faq.md for cross-doc scenarios (new hire + prod, refund + API, etc.).

Available tools (for planning only — do NOT call them in this phase):
{RESEARCHER_TOOL_MENU}

Plan enough steps to gather thorough facts — typical patterns:
- Lookup: grep to find the doc → read_file the full file
- Overview: read_file index.md → read_file 1–2 relevant docs
- Compare / multi-topic: read_file each doc involved (2–3 steps)
- Procedure: read_file the runbook or FAQ section step-by-step

Reply with ONLY valid JSON — no markdown, no TOOL lines, no explanation.
Format:
{{"goal": "short summary", "steps": [{{"description": "what to do", "tool": "tool_name or null", "arg": "argument or null"}}]}}
Example:
{{"goal": "Find refund window in policy doc", "steps": [
  {{"description": "Search docs for refund", "tool": "grep", "arg": "refund:docs"}},
  {{"description": "Read refunds-policy.md", "tool": "read_file", "arg": "docs/refunds-policy.md"}},
  {{"description": "Hand facts to writer", "tool": null, "arg": null}}
]}}
Do NOT call tools. Do NOT answer the user yet. Plan only."""

PLAN_RETRY = (
    "Invalid plan JSON. Reply with ONLY the JSON object in the format above. "
    "No TOOL lines. No markdown fences."
)

RESEARCHER_SYSTEM = f"""You are the RESEARCHER sub-agent. You do not talk to the user.

Your job: follow the manager's plan and gather thorough facts from internal docs (and optionally the web).
Docs listing:
{WORKSPACE_SNAPSHOT}

Research habits:
- After grep hits, read_file the full source doc — don't stop at snippets alone
- For broad questions, read docs/index.md first, then specific docs
- For "what do I need?" questions, read docs/team-faq.md and any linked docs
- Quote specific numbers, dates, and steps from the files
- Cite every fact as: docs/path.md — "short quote or paraphrase"

When you need a tool:
TOOL:tool_name:argument
One tool per reply. No thinking tags.

Tools:
{RESEARCHER_TOOL_MENU}

Allowed web hosts: {ALLOWED_LIST}

When you have enough facts, stop calling tools. Reply with bullet facts only — one bullet per fact with source path.
Do not write the final user-facing essay (the writer sub-agent does that)."""

WRITER_SYSTEM = """You are the WRITER sub-agent. You do not talk to the manager — your reply goes to the user.

Use ONLY the researcher facts provided. Do not invent doc content. Do not call tools.
If previous conversation is included, use it for continuity — but ground factual claims in researcher facts.

Write a helpful, complete answer using this structure when the facts support it:

**Answer** — direct response in 1–2 sentences

**Details** — bullets with specifics (numbers, steps, rules). Quote or paraphrase from facts.

**Sources** — list doc paths you relied on (e.g. docs/refunds-policy.md)

**Related** — optional: other docs the user might read next (only if mentioned in facts)

For narrow factual questions, a short Answer + Sources is fine. For "overview" or "what do I need?" questions, use all sections."""

EMPTY_REPLY_NUDGE = (
    "No TOOL line and no facts yet. Call a file tool or return bullet facts now."
)


# ---------------------------------------------------------------------------
# Plan parsing (lesson 09) — defensive JSON, same pattern as lesson 06
# ---------------------------------------------------------------------------

def strip_json(text: str) -> str:
    """Pull JSON object out of markdown fences or extra chatter."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1:
        text = text[start : end + 1]
    return text.strip()


def parse_plan(reply: str) -> dict | None:
    """Validate plan shape — reject plans that reference tools Python cannot run."""
    try:
        data = json.loads(strip_json(reply))
    except json.JSONDecodeError:
        return None
    if not isinstance(data, dict):
        return None
    goal = data.get("goal")
    steps = data.get("steps")
    if not isinstance(goal, str) or not goal.strip():
        return None
    if not isinstance(steps, list) or not steps:
        return None
    cleaned_steps = []
    for step in steps:
        if not isinstance(step, dict):
            return None
        desc = step.get("description")
        if not isinstance(desc, str) or not desc.strip():
            return None
        tool = step.get("tool")
        arg = step.get("arg")
        if tool is not None and not isinstance(tool, str):
            return None
        if arg is not None and not isinstance(arg, str):
            return None
        if tool is not None and tool.strip() and tool.strip() not in PLANNER_TOOL_NAMES:
            return None  # plan names a tool not in RESEARCHER_TOOLS — reject early
        cleaned_steps.append(
            {
                "description": desc.strip(),
                "tool": tool.strip() if isinstance(tool, str) and tool.strip() else None,
                "arg": arg.strip() if isinstance(arg, str) and arg.strip() else None,
            }
        )
    return {"goal": goal.strip(), "steps": cleaned_steps}


def format_plan(plan: dict) -> str:
    """Text block injected into researcher user message."""
    lines = [f"Goal: {plan['goal']}", "Steps:"]
    for i, step in enumerate(plan["steps"], 1):
        hint = ""
        if step["tool"]:
            hint = f" (suggested: {step['tool']}({step['arg']!r}))"
        lines.append(f"  {i}. {step['description']}{hint}")
    return "\n".join(lines)


def print_plan(plan: dict) -> None:
    print(f"\n[plan] goal: {plan['goal']}")
    for i, step in enumerate(plan["steps"], 1):
        hint = ""
        if step["tool"]:
            hint = f" (suggested: {step['tool']}({step['arg']!r}))"
        print(f"[plan]   {i}. {step['description']}{hint}")


# ---------------------------------------------------------------------------
# LLM transport + tool loop primitives (lessons 02, 04, 07)
# ---------------------------------------------------------------------------

def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def estimate_messages_tokens(messages: list) -> int:
    total = 0
    for msg in messages:
        total += estimate_tokens(msg.get("content", ""))
        total += 4  # rough per-message template overhead
    return total


def trim_history(history: list) -> None:
    """Drop oldest non-system messages when researcher history exceeds soft budget."""
    if len(history) <= 1:
        return
    while len(history) > 1 and estimate_messages_tokens(history) > MAX_HISTORY_TOKENS:
        history.pop(1)  # index 0 is always system prompt


def stream_chat(messages, label: str) -> str | None:
    """POST history to LM Studio, stream tokens to terminal, return full reply."""
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
    """re.search not fullmatch — model may wrap TOOL line in extra text."""
    for text in (line, strip_template_noise(line)):
        match = re.search(r"TOOL:(\w+):(.+)", text)
        if match:
            name, arg = match.group(1), match.group(2).strip()
            if name in tools:
                return name, arg
    return None


def run_tool(line: str, tools: dict, label: str) -> str | None:
    """Run one tool; return None if reply has no TOOL line (end of inner loop)."""
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


# ---------------------------------------------------------------------------
# Sub-agents — each is an LLM call (+ tool loop for researcher only)
# ---------------------------------------------------------------------------

def run_planner(user_question: str) -> dict | None:
    """Phase 1 — JSON plan only. Guard rail: never call run_tool() here."""
    history = [
        {"role": "system", "content": PLAN_SYSTEM},
        {"role": "user", "content": user_question},
    ]
    for attempt in range(1, MAX_PLAN_RETRIES + 1):
        print(f"\n[planner] asking for plan (attempt {attempt})")
        reply = stream_chat(history, "planner")
        if reply is None:
            log.planner_offline()
            return None
        if re.search(r"TOOL:\w+:", reply):
            # Prompt says no tools — but we enforce in code too (lesson 09 guard rail)
            print("[guard] model emitted TOOL: during planning — ignoring (no tool will run)")
        plan = parse_plan(reply)
        if plan:
            print_plan(plan)
            log.plan_done(plan["goal"], len(plan["steps"]))
            return plan
        # Bad JSON — append failed reply + retry nudge (same pattern as lesson 06)
        history.append({"role": "assistant", "content": reply})
        history.append({"role": "user", "content": PLAN_RETRY})
    print(f"[error] Could not get valid plan JSON after {MAX_PLAN_RETRIES} attempts.")
    return None


def run_researcher(task: str, plan: dict) -> str:
    """Phase 2 — agent inner loop: LLM → maybe tool → Observation → LLM again."""
    plan_text = format_plan(plan)
    history = [
        {"role": "system", "content": RESEARCHER_SYSTEM},
        {
            "role": "user",
            "content": f"Research task from manager: {task}\n\nPlan to follow:\n{plan_text}",
        },
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
            # No TOOL line — treat as final facts unless reply is empty noise
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
    """Phase 3 — single LLM call, no tools. Facts string is the only ground truth."""
    parts = []
    if prior_context:
        parts.append(prior_context)  # from SQLite — continuity, not new facts
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


# ---------------------------------------------------------------------------
# Manager — Python orchestrates the fixed pipeline (lesson 12)
# ---------------------------------------------------------------------------

def run_manager(user_question: str, *, eval_mode: bool = False) -> dict:
    """Full capstone pipeline: plan → research → write → optional HITL save."""
    if eval_mode:
        set_eval_mode(True)  # auto-approve writes; skip session save below
    try:
        run_id = log.begin_turn(user_question)

        prior_context = ""
        if not eval_mode:
            # Persistence (lesson 15) — inject into writer only, not planner/researcher
            prior_turns = session.load_recent_turns()
            prior_context = session.format_prior_context(prior_turns)
            if prior_turns:
                print(f"[session] loaded {len(prior_turns)} prior turn(s) into writer context")

        print("[manager] received user question")

        # Python route — meta/help questions skip the LLM pipeline (harness_routes.py)
        if is_meta_question(user_question):
            answer = builtin_answer(user_question)
            print("[manager] builtin route — skipping planner/researcher/writer")
            print(f"\n{answer}\n")
            log.builtin_handled("meta")
            if not eval_mode:
                turn_id = session.save_turn(user_question, answer)
                print(f"[session] saved turn #{turn_id} (no file write for help)")
            log.end_turn(len(answer))
            return {"run_id": run_id, "answer": answer, "facts": "", "plan": None, "builtin": True}

        # --- Phase 1: plan (no tools) ---
        print("[manager] → delegating to planner")
        log.handoff("manager", "planner")
        plan = run_planner(user_question)
        if plan is None:
            answer = "[planner failed — could not produce a valid plan]"
            log.end_turn(len(answer))
            return {"run_id": run_id, "answer": answer, "facts": "", "plan": None}

        print(f"[manager] ← planner done ({len(plan['steps'])} steps)")
        log.handoff("planner", "manager", step_count=len(plan["steps"]))

        # --- Phase 2: research (tool loop) ---
        print("[manager] → delegating to researcher")
        log.handoff("manager", "researcher")
        facts = run_researcher(user_question, plan)

        print(f"[manager] ← researcher done ({len(facts)} chars)")
        log.handoff("researcher", "manager", facts_chars=len(facts))

        # --- Phase 3: write (no tools) ---
        print("[manager] → delegating to writer")
        log.handoff("manager", "writer", facts_chars=len(facts))
        answer = run_writer(user_question, facts, prior_context)

        print("[manager] ← writer done")
        if not eval_mode:
            # HITL + persistence only in interactive mode
            print(f"\n[manager] offer to save answer → {DEFAULT_OUTPUT_PATH}")
            result = write_file(DEFAULT_OUTPUT_PATH, answer)
            print(f"[manager] {result}")
            turn_id = session.save_turn(user_question, answer)
            print(f"[session] saved turn #{turn_id}")

        log.end_turn(len(answer))
        return {"run_id": run_id, "answer": answer, "facts": facts, "plan": plan}
    finally:
        if eval_mode:
            set_eval_mode(False)
