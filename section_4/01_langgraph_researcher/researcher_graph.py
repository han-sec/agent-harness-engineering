# LangGraph — researcher inner loop (mirrors lesson 19 while-loop).
import re
from typing import Annotated, Literal

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict

from mcp_client import (
    DOCS_MCP_ROOT,
    MCP_TOOL_NAMES,
    mcp_arg_preview,
    mcp_call,
    tool_line_to_mcp_args,
)

URL = "http://localhost:1234/v1"
MODEL = "gemma-4-12b-it-mlx"
MAX_HISTORY_TOKENS = 4000
MAX_TOOL_ROUNDS = 10
MAX_EMPTY_RETRIES = 2

CHANNEL_TAG_RE = re.compile(r"<\|[^|>]*\|>?|<\|[^|>]*>", re.IGNORECASE)
DOCS_DIR = DOCS_MCP_ROOT / "docs"
EMPTY_REPLY_NUDGE = "No TOOL line and no facts yet. Call an MCP doc tool or return bullet facts."

RESEARCHER_TOOL_MENU = """\
- list_docs — Example: TOOL:list_docs:_
- grep_docs(query) — Example: TOOL:grep_docs:refund
- read_doc(path) — Example: TOOL:read_doc:refunds-policy.md"""


def _docs_listing() -> str:
    if not DOCS_DIR.is_dir():
        return "(docs folder not found — run lesson 18)"
    names = sorted(p.name for p in DOCS_DIR.glob("*.md"))
    return ", ".join(names) if names else "(empty)"


DOCS_SNAPSHOT = _docs_listing()

RESEARCHER_SYSTEM = f"""You are the RESEARCHER sub-agent. You do not talk to the user.

Gather facts using MCP doc tools. Docs available: {DOCS_SNAPSHOT}

When you need a tool, emit one line:
TOOL:tool_name:argument
One tool per reply. No thinking tags.

Tools:
{RESEARCHER_TOOL_MENU}

After grep_docs hits, read_doc the full source file. Cite filenames in facts.
When done, stop calling tools and return bullet facts only."""

def strip_template_noise(text: str) -> str:
    cleaned = CHANNEL_TAG_RE.sub("", text)
    cleaned = re.sub(r"\bthought\b", "", cleaned, flags=re.IGNORECASE)
    return cleaned.strip()


def find_mcp_tool_call(text: str) -> tuple[str, str] | None:
    for raw in (text, strip_template_noise(text)):
        match = re.search(r"TOOL:(\w+)(?::(.*))?", raw)
        if not match:
            continue
        name = match.group(1)
        arg = (match.group(2) or "").strip()
        if name in MCP_TOOL_NAMES:
            return name, arg
    return None


def estimate_tokens(text: str) -> int:
    return max(1, len(text) // 4)


def trim_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
    trimmed = list(messages)
    while len(trimmed) > 1:
        total = sum(estimate_tokens(m.content) + 4 for m in trimmed)
        if total <= MAX_HISTORY_TOKENS:
            break
        trimmed.pop(1)
    return trimmed


def make_llm() -> ChatOpenAI:
    """LM Studio = OpenAI-compatible HTTP. LangChain client replaces urllib here."""
    return ChatOpenAI(
        base_url=URL,
        api_key="lm-studio",
        model=MODEL,
        temperature=0,
    )

class ResearchState(TypedDict):
    """Shared memory — every node reads this and returns partial updates."""

    messages: Annotated[list[BaseMessage], add_messages]
    facts: str
    empty_retries: int
    tool_rounds: int

def build_researcher_graph(mcp):
    """Compile graph once per chat. `mcp` is injected into the tools node."""

    llm = make_llm()

    async def call_model(state: ResearchState) -> dict:
        """NODE: one LLM turn (lesson 19: top of while loop)."""
        messages = trim_messages(state["messages"])
        print("\n[graph:researcher] calling model...")
        reply = await llm.ainvoke(messages)
        text = reply.content if isinstance(reply.content, str) else str(reply.content)
        print(text)
        return {"messages": [AIMessage(content=text)]}

    async def mcp_tools(state: ResearchState) -> dict:
        """NODE: TOOL line → MCP call → Observation (lesson 19: run_mcp_tool)."""
        last = state["messages"][-1]
        text = last.content if isinstance(last.content, str) else str(last.content)
        found = find_mcp_tool_call(text)
        if not found:
            return {"tool_rounds": state["tool_rounds"] + 1}

        name, arg = found
        arguments = tool_line_to_mcp_args(name, arg)
        preview = mcp_arg_preview(name, arguments)
        print(f"\n[graph:mcp] {name}({preview!r})")
        try:
            result = await mcp_call(mcp, name, arguments)
        except Exception as exc:
            result = f"Error: MCP tool {name} crashed: {exc}"

        obs = result if len(result) <= 100 else result[:100] + "..."
        print(f"[graph:mcp] observation {obs!r}")
        return {
            "messages": [HumanMessage(content=f"Observation: {result}")],
            "tool_rounds": state["tool_rounds"] + 1,
            "empty_retries": 0,
        }

    async def nudge(state: ResearchState) -> dict:
        """NODE: empty model reply → nudge (lesson 19: EMPTY_REPLY_NUDGE)."""
        attempt = state["empty_retries"] + 1
        print(f"[graph:researcher] noise only — nudge ({attempt}/{MAX_EMPTY_RETRIES})")
        return {
            "messages": [HumanMessage(content=EMPTY_REPLY_NUDGE)],
            "empty_retries": attempt,
        }

    def finalize(state: ResearchState) -> dict:
        """NODE: copy last AI message into facts before END."""
        last_ai = None
        for msg in reversed(state["messages"]):
            if isinstance(msg, AIMessage):
                last_ai = msg
                break
        text = ""
        if last_ai is not None:
            text = last_ai.content if isinstance(last_ai.content, str) else str(last_ai.content)
        facts = strip_template_noise(text) or "[researcher returned no facts]"
        print(f"[graph:researcher] facts ready ({len(facts)} chars)")
        return {"facts": facts}

    def route_after_model(state: ResearchState) -> Literal["mcp_tools", "nudge", "__end__"]:
        """CONDITIONAL EDGE after call_model."""
        last = state["messages"][-1]
        text = last.content if isinstance(last.content, str) else str(last.content)
        if find_mcp_tool_call(text):
            return "mcp_tools"
        if len(strip_template_noise(text)) < 15 and state["empty_retries"] < MAX_EMPTY_RETRIES:
            return "nudge"
        return "__end__"

    def route_after_tools(state: ResearchState) -> Literal["call_model", "__end__"]:
        """CONDITIONAL EDGE after mcp_tools — round limit guard."""
        if state["tool_rounds"] >= MAX_TOOL_ROUNDS:
            print("[graph:researcher] hit round limit")
            return "__end__"
        return "call_model"
    
    graph = StateGraph(ResearchState)
    graph.add_node("call_model", call_model)
    graph.add_node("mcp_tools", mcp_tools)
    graph.add_node("nudge", nudge)
    graph.add_node("finalize", finalize)

    graph.add_edge(START, "call_model")
    graph.add_conditional_edges(
        "call_model",
        route_after_model,
        {"mcp_tools": "mcp_tools", "nudge": "nudge", "__end__": "finalize"},
    )
    graph.add_edge("nudge", "call_model")
    graph.add_conditional_edges(
        "mcp_tools",
        route_after_tools,
        {"call_model": "call_model", "__end__": "finalize"},
    )
    graph.add_edge("finalize", END)

    return graph.compile()