# Optional Lab 8C — Real A2A

Notebook: `Aegis_Chapter8C_Lab.ipynb`. Chapter 8's team — imported from its own folder,
unchanged — as three agents speaking Google's Agent2Agent protocol via `a2a-sdk`.

| File | What it is |
|---|---|
| `a2a_team/agents.py` | `WorkerExecutor` (worker inside the task lifecycle), `make_card`, `build_agent_app` (card + JSON-RPC on FastAPI), `discover`, `send_envelope` |
| `a2a_team/orchestrator.py` | `run_incident` (discover by card, follow the envelope's `to_agent`), `MultiAppTransport` (in-process "network"), `run_in_process` |
| `demo.py` | Asserts discovery, three completed tasks on one `context_id`, same verdict and single writer; CI runs it |

Run from the repo root: `python labs/chapter-08c-real-a2a/demo.py`

The whole protocol runs in-process over an httpx ASGI transport, so it is offline and
deterministic. To run the agents as real services: `uvicorn` each `build_agent_app(name, url)`
on its own port and pass those URLs to `run_incident`.
