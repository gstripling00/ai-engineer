# Optional Lab 12B — Ship It

Notebook: `Aegis_Chapter12B_Lab.ipynb`. The capstone behind an HTTP endpoint, in a
container, with tracing pointed wherever the environment says.

| File | What it is |
|---|---|
| `service/app.py` | FastAPI service: `POST /triage`, `GET /healthz`, `GET /metrics`; timeout, rate limit, input bounds, OTel export |
| `service/config.py` | `Settings` from environment variables, with documented defaults |
| `Dockerfile` | Builds from the repo root with the one `requirements.txt`; non-root; health check |
| `docker-compose.yml` | Runs the service; commented variables point spans at Langfuse or any OTLP collector |
| `demo.py` | In-process test of every endpoint and every guard via `TestClient`; CI runs it |

Run locally from the repo root:

    cd labs/chapter-12b-ship-it && uvicorn service.app:app --reload
    curl -s localhost:8000/healthz
    curl -s -X POST localhost:8000/triage -H 'content-type: application/json' \
      -d '{"alert":{"id":"A-1","rule":"Multiple failed logins followed by success","user":"j.okafor","src_ip":"203.0.113.42","severity_hint":"high"},"raw_log":""}'

Or in a container: `docker compose -f labs/chapter-12b-ship-it/docker-compose.yml up --build`
