"""
Configuration from the environment, and nowhere else.

Every knob a deployment turns is an environment variable with a documented
default. No literal in code, no config file that drifts from the container.
"""
import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    model_tier: str = os.environ.get("AEGIS_MODEL", "mock")
    timeout_s: float = float(os.environ.get("AEGIS_TIMEOUT_S", "10"))
    rate_limit_per_min: int = int(os.environ.get("AEGIS_RATE_LIMIT_PER_MIN", "120"))
    max_raw_log_chars: int = int(os.environ.get("AEGIS_MAX_RAW_LOG_CHARS", "8000"))
    otlp_endpoint: str = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "")
    service_version: str = os.environ.get("AEGIS_VERSION", "dev")

    def as_public_dict(self) -> dict:
        """What /healthz may reveal. Never a key, never a header."""
        return {"model_tier": self.model_tier, "timeout_s": self.timeout_s,
                "rate_limit_per_min": self.rate_limit_per_min, "version": self.service_version,
                "tracing": "otlp" if self.otlp_endpoint else "in-memory"}


def load_settings() -> Settings:
    return Settings()
