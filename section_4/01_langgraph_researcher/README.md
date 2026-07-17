# Lesson 01 (section 4) — LangGraph researcher

Build this lesson **block by block** — see the step-by-step guide in your chat.

Port lesson 19's researcher inner loop to a LangGraph `StateGraph`.

## Files to create

```
section_4/01_langgraph_researcher/
  requirements.txt
  mcp_client.py          ← copy from lesson 19 (unchanged)
  researcher_graph.py    ← NEW: graph nodes + edges
  01_langgraph_researcher.py  ← entry point
```

## Run

```bash
cd section_4/01_langgraph_researcher
python3 -m venv .venv && source .venv/bin/activate
python3 -m pip install -r requirements.txt
lms server start && lms ps
python3 01_langgraph_researcher.py
```
