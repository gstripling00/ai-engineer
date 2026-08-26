"""
Real OpenTelemetry, and the Langfuse handoff.

build_tracer() returns a tracer backed by an in-memory exporter: offline, no
server, every span inspectable. export_findings() maps a Run onto spans - one
root per incident, one child per stage, one child per authorization decision,
and the evaluation scores ON the same trace so 'what did it do' and 'was it any
good' can be joined.

langfuse_otlp_env() builds the three environment variables that point any OTLP
exporter at a Langfuse instance. Langfuse v4 is OTel-native, so we depend on the
stable layer (OpenTelemetry) rather than a vendor SDK; otlp_tracer_from_env()
is the production tracer, configured entirely from the environment.
"""
import base64
import os

from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter

SERVICE = "aegis"


def build_tracer():
    """In-memory tracer for the lab and CI. Returns (tracer, exporter)."""
    exporter = InMemorySpanExporter()
    provider = TracerProvider(resource=Resource.create({"service.name": SERVICE}))
    provider.add_span_processor(SimpleSpanProcessor(exporter))
    return provider.get_tracer(SERVICE), exporter


def _clean(value):
    """OTel attributes must be str/bool/int/float (or sequences of them)."""
    if isinstance(value, (str, bool, int, float)):
        return value
    return str(value)


def export_findings(run, tracer, scores: dict | None = None) -> None:
    """One trace per incident. Stages, authorization decisions, and evaluation
    scores are all children of the same root span."""
    with tracer.start_as_current_span("aegis.incident",
                                      attributes={"aegis.trace_id": run.trace_id,
                                                  "aegis.alert_id": run.alert.get("id", ""),
                                                  "aegis.injection_detected": run.injection_detected,
                                                  "aegis.escalated": run.escalated}):
        for name, attributes in run.stages:
            with tracer.start_as_current_span(f"aegis.{name}",
                                              attributes={k: _clean(v) for k, v in attributes.items()}):
                pass
        for agent, tool, allowed in run.audit:
            with tracer.start_as_current_span("aegis.authorization",
                                              attributes={"aegis.agent": agent, "aegis.tool": tool,
                                                          "aegis.allowed": allowed, "aegis.chapter": "8"}):
                pass
        if scores:
            with tracer.start_as_current_span("aegis.evaluation",
                                              attributes={**{f"aegis.score.{k}": float(v) for k, v in scores.items()},
                                                          "aegis.chapter": "10"}):
                pass


def langfuse_otlp_env(public_key: str, secret_key: str, host: str = "http://localhost:3000") -> dict:
    """The three variables that point ANY OTLP/HTTP exporter at Langfuse."""
    token = base64.b64encode(f"{public_key}:{secret_key}".encode()).decode()
    return {
        "OTEL_EXPORTER_OTLP_ENDPOINT": f"{host.rstrip('/')}/api/public/otel",
        "OTEL_EXPORTER_OTLP_HEADERS": f"Authorization=Basic {token}",
        "OTEL_EXPORTER_OTLP_PROTOCOL": "http/protobuf",
    }


def otlp_tracer_from_env():
    """Production tracer: reads OTEL_EXPORTER_OTLP_* from the environment.
    Swap Langfuse for Cloud Trace or Jaeger by changing the variables, not the code."""
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
    if not endpoint:
        raise RuntimeError("OTEL_EXPORTER_OTLP_ENDPOINT is not set - see langfuse_otlp_env()")
    provider = TracerProvider(resource=Resource.create({"service.name": SERVICE}))
    provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))   # endpoint/headers from env
    trace.set_tracer_provider(provider)
    return provider.get_tracer(SERVICE)
