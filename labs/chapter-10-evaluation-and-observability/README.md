# Chapter 10 — Agent Evaluation and Observability

Notebook: `Aegis_Chapter10_Lab.ipynb`. Most of this lab is inline; the tracing section
imports the modules below from this folder.

| File | What it is |
|---|---|
| `common/soc.py` | The SOC world (same fixture as Chapter 8) |
| `capstone/aegis/system.py` | `AegisV12` — the assembled agent, recording structured stages and an authorization audit |
| `interface/observability.py` | `build_tracer` (in-memory OpenTelemetry), `export_findings`, `langfuse_otlp_env`, `otlp_tracer_from_env` |
| `demo.py` | Smoke test: RAGAS offline metrics, AegisV12, real OTel spans, Langfuse env; CI runs it |

Run from the repo root: `python labs/chapter-10-evaluation-and-observability/demo.py`

Notes that cost people time:
- RAGAS 0.4 metrics are async-first. In a notebook use `await metric.ascore(...)`; `score()` refuses inside a running event loop.
- `ragas.metrics.collections` metrics need `llm_factory(model, client=AsyncOpenAI(...))` and `ragas.embeddings.OpenAIEmbeddings(client=...)`. The legacy `LangchainLLMWrapper` is rejected.
