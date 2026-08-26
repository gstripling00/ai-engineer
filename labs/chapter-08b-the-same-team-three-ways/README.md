# Optional Lab 8B — The Same Team, Three Ways

Notebook: `Aegis_Chapter8B_Lab.ipynb`. Chapter 8's team — imported from its own folder,
unchanged — orchestrated by a for-loop, by LangGraph, and by Google ADK 2.x.

| File | What it is |
|---|---|
| `frameworks/team.py` | Imports Chapter 8's workers/tools/envelope; `Result`, envelope <-> dict helpers |
| `frameworks/scratch_team.py` | `run_scratch` — Chapter 8's loop |
| `frameworks/langgraph_team.py` | `build_graph`, `run_langgraph`, `checkpoint_history` (MemorySaver) |
| `frameworks/adk_team.py` | `build_workflow`, `run_adk`, `fan_out_workflow` (JoinNode) |
| `demo.py` | Asserts all three produce the same verdict, handoffs and audit; CI runs it |

Run from the repo root: `python labs/chapter-08b-the-same-team-three-ways/demo.py`
