# Lesson 15 — persistence. SQLite stores user/assistant turns across script restarts.
# Different from 08b trim_history — that is in-memory for one run; this survives reboot.
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent / "data" / "session.db"
MAX_TURNS_LOADED = 5  # how many past turns to inject into writer context


def _connect() -> sqlite3.Connection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create turns table if this is a fresh database."""
    with _connect() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS turns (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                created_at TEXT NOT NULL,
                user_msg TEXT NOT NULL,
                assistant_msg TEXT NOT NULL
            )
            """
        )


def save_turn(user_msg: str, assistant_msg: str) -> int:
    """Append one Q&A pair — called after each successful manager run (interactive only)."""
    ts = datetime.now(timezone.utc).isoformat()
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO turns (created_at, user_msg, assistant_msg) VALUES (?, ?, ?)",
            (ts, user_msg, assistant_msg),
        )
        return int(cur.lastrowid)


def load_recent_turns(limit: int = MAX_TURNS_LOADED) -> list[dict]:
    """Load newest turns first, return oldest-first for readable context."""
    with _connect() as conn:
        rows = conn.execute(
            "SELECT user_msg, assistant_msg, created_at FROM turns "
            "ORDER BY id DESC LIMIT ?",
            (limit,),
        ).fetchall()
    return [dict(row) for row in reversed(rows)]


def turn_count() -> int:
    with _connect() as conn:
        row = conn.execute("SELECT COUNT(*) AS n FROM turns").fetchone()
    return int(row["n"])


def format_prior_context(turns: list[dict]) -> str:
    """Turn saved rows into text the writer sub-agent can read."""
    if not turns:
        return ""
    lines = ["Previous conversation (context only — answer the latest question):"]
    for turn in turns:
        lines.append(f"User: {turn['user_msg']}")
        lines.append(f"Assistant: {turn['assistant_msg']}")
    return "\n".join(lines)
