# Logging module — extends lesson 13 with approval events.
import json
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

LOG_DIR = Path(__file__).resolve().parent / "logs"
LOG_FILE = LOG_DIR / "agent.jsonl"
LOG_PREVIEW_CHARS = 500

_run_id = ""


def begin_turn(question: str) -> str:
    global _run_id
    _run_id = uuid4().hex[:8]
    _write("turn_start", question=question)
    return _run_id


def end_turn(answer_chars: int) -> None:
    _write("turn_end", answer_chars=answer_chars)


def handoff(from_agent: str, to_agent: str, **fields) -> None:
    _write("handoff", from_agent=from_agent, to_agent=to_agent, **fields)


def llm_start(agent: str, prompt_tokens: int) -> None:
    _write("llm_start", agent=agent, prompt_tokens=prompt_tokens)


def llm_reply(agent: str, reply: str, cleaned_reply: str) -> None:
    _write(
        "llm_reply",
        agent=agent,
        reply_chars=len(reply),
        reply_preview=_preview(cleaned_reply, 200),
    )


def llm_error(agent: str, error: str) -> None:
    _write("llm_error", agent=agent, error=error)


def tool_call(agent: str, name: str, arg: str, result: str) -> None:
    _write("tool_call", agent=agent, tool=name, arg=arg)
    _write("observation", agent=agent, tool=name, result=_preview(result))


def nudge(agent: str, attempt: int) -> None:
    _write("nudge", agent=agent, attempt=attempt)


def researcher_done(facts: str) -> None:
    _write("researcher_done", facts_chars=len(facts), facts_preview=_preview(facts))


def writer_done(answer: str) -> None:
    _write("writer_done", answer_chars=len(answer), answer_preview=_preview(answer))


def agent_offline(agent: str) -> None:
    _write(f"{agent}_offline")


def researcher_round_limit() -> None:
    _write("researcher_round_limit")


def approval_requested(action: str, path: str, preview: str) -> None:
    _write("approval_requested", action=action, path=path, preview=_preview(preview, 200))


def approval_granted(action: str, path: str) -> None:
    _write("approval_granted", action=action, path=path)


def approval_denied(action: str, path: str) -> None:
    _write("approval_denied", action=action, path=path)


def file_written(path: str, chars: int) -> None:
    _write("file_written", path=path, chars=chars)


def _preview(text: str, limit: int = LOG_PREVIEW_CHARS) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + f"... [{len(text)} chars total]"


def _write(event: str, **fields) -> None:
    record = {
        "ts": datetime.now(timezone.utc).isoformat(),
        "run_id": _run_id,
        "event": event,
        **fields,
    }
    LOG_DIR.mkdir(exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
