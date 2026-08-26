"""
Aegis as a service: the capstone behind one HTTP endpoint.

    POST /triage     {"alert": {...}, "raw_log": "..."}  ->  findings summary + trace id
    GET  /healthz    liveness, configuration (public parts), dependency check
    GET  /metrics    request counts and latency, plain text

Everything production needs that a notebook never did:
  * a TIMEOUT on every run (a hung model call must not hang the service)
  * a RATE LIMIT (a burst of alerts must not become a bill)
  * INPUT BOUNDS (an oversized raw_log is rejected before it reaches the scanner)
  * tracing to wherever OTEL_EXPORTER_OTLP_ENDPOINT points, in-memory otherwise
  * configuration from the environment, health that says what it is running

The agent itself is imported from Chapter 13. Not one line of it changed.
"""
import asyncio
import os
import sys
import time
from collections import deque

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, Field

_LABS = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# The agent comes from Chapter 13's folder (capstone/, common/). Chapter 10's folder
# has packages with the SAME names, so it must not go on sys.path; its observability
# module is loaded by file path instead. Two chapters, no shadowing.
sys.path.insert(0, os.path.join(_LABS, "chapter-13-assembling-aegis"))
from capstone.aegis.system import AegisV12                    # noqa: E402  Chapter 13
from common import soc                                        # noqa: E402  Chapter 13


def _load_observability():
    import importlib.util
    path = os.path.join(_LABS, "chapter-10-evaluation-and-observability", "interface", "observability.py")
    spec = importlib.util.spec_from_file_location("aegis_observability", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


observability = _load_observability()                          # Chapter 10, by path
build_tracer, export_findings = observability.build_tracer, observability.export_findings

from .config import load_settings                             # noqa: E402

settings = load_settings()
app = FastAPI(title="Aegis", version=settings.service_version)


# ---------------------------------------------------------------- tracing sink
def _tracer():
    if settings.otlp_endpoint:
        return observability.otlp_tracer_from_env(), None
    return build_tracer()


TRACER, EXPORTER = _tracer()
AGENT = AegisV12()

# ---------------------------------------------------------------- rate limit + metrics
_window: deque = deque()
METRICS = {"requests": 0, "ok": 0, "rejected_rate_limit": 0, "rejected_input": 0,
           "timeouts": 0, "latency_ms_total": 0.0}


def _rate_limited(now: float) -> bool:
    while _window and now - _window[0] > 60:
        _window.popleft()
    if len(_window) >= settings.rate_limit_per_min:
        return True
    _window.append(now)
    return False


# ---------------------------------------------------------------- schemas
class TriageRequest(BaseModel):
    alert: dict = Field(..., description="the alert, in the shape every chapter expects")
    raw_log: str = Field("", description="untrusted content; scanned, fenced, never obeyed")


class TriageResponse(BaseModel):
    trace_id: str
    verdict: str
    severity: str
    escalated: bool
    escalation_reasons: list
    injection_detected: bool
    ticket_id: str
    stages: list
    denied_tool_calls: int
    latency_ms: float


# ---------------------------------------------------------------- endpoints
@app.get("/healthz")
def healthz() -> dict:
    return {"status": "ok", "agent": "AegisV12", **settings.as_public_dict(),
            "tools": sorted(soc.TOOLS)}


@app.get("/metrics", response_class=PlainTextResponse)
def metrics() -> str:
    avg = METRICS["latency_ms_total"] / METRICS["ok"] if METRICS["ok"] else 0.0
    lines = [f"aegis_{k} {v}" for k, v in METRICS.items() if k != "latency_ms_total"]
    lines.append(f"aegis_latency_ms_avg {avg:.2f}")
    return "\n".join(lines) + "\n"


@app.post("/triage", response_model=TriageResponse)
async def triage(req: TriageRequest, request: Request) -> TriageResponse:
    METRICS["requests"] += 1
    now = time.time()
    if _rate_limited(now):
        METRICS["rejected_rate_limit"] += 1
        raise HTTPException(status_code=429, detail="rate limit exceeded; retry later")
    if len(req.raw_log) > settings.max_raw_log_chars:
        METRICS["rejected_input"] += 1
        raise HTTPException(status_code=413, detail=f"raw_log exceeds {settings.max_raw_log_chars} chars")
    for key in ("id", "user", "src_ip"):
        if key not in req.alert:
            METRICS["rejected_input"] += 1
            raise HTTPException(status_code=422, detail=f"alert missing required field '{key}'")

    started = time.perf_counter()
    try:
        run = await asyncio.wait_for(asyncio.to_thread(AGENT.handle, req.alert, req.raw_log),
                                     timeout=settings.timeout_s)
    except asyncio.TimeoutError:
        METRICS["timeouts"] += 1
        raise HTTPException(status_code=504, detail=f"triage exceeded {settings.timeout_s}s")
    latency = (time.perf_counter() - started) * 1000

    export_findings(run, TRACER)                       # one trace per incident, wherever it goes
    METRICS["ok"] += 1
    METRICS["latency_ms_total"] += latency
    return TriageResponse(
        trace_id=run["trace_id"], verdict=run["verdict"], severity=run["severity"],
        escalated=run["escalated"], escalation_reasons=run["escalation_reasons"],
        injection_detected=run["injection_detected"], ticket_id=run["ticket"].get("id", ""),
        stages=[s["stage"] for s in run["trace"]],
        denied_tool_calls=sum(1 for e in run["audit"] if not e["allowed"]),
        latency_ms=round(latency, 2))
