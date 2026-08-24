#!/usr/bin/env python3
"""
Environment check — run this first, and any time a lab misbehaves.

Mirrors production practice in three ways the labs should model:

  1. ONE source of truth. Everything installs from requirements.txt. This script
     verifies the installed environment matches it.
  2. FAIL FAST, LOUDLY. A broken environment says so here, with the fix, instead
     of surfacing as a confusing error three cells into a notebook.
  3. SECRETS FROM THE ENVIRONMENT. Keys are read from env vars, never written
     into a notebook cell. This script confirms a key is present WITHOUT ever
     printing it.

    python tools/check_env.py
"""
import importlib
import os
import sys

# (module, import path, why the book needs it)
REQUIRED = [
    ("langgraph", "langgraph.graph", "open-source agent track (StateGraph/END)"),
    ("langchain-core", "langchain_core", "message and tool primitives"),
    ("langchain-community", "langchain_community", "RAGAS dependency — see the pin note"),
    ("google-adk", "google.adk", "Google Cloud agent track (Agent, Workflow)"),
    ("mcp", "mcp", "tool discovery and hardening (Ch 3, 9, 11)"),
    ("openai", "openai", "the default real-model tier"),
    ("langchain-openai", "langchain_openai", "wires OpenAI into RAGAS"),
    ("ragas", "ragas.metrics.collections", "evaluation (Ch 10)"),
    ("sacrebleu", "sacrebleu", "required by RAGAS BleuScore"),
    ("opentelemetry-sdk", "opentelemetry.sdk.trace", "tracing (Ch 10)"),
    ("chromadb", "chromadb", "vector store (Ch 6)"),
    ("rank-bm25", "rank_bm25", "sparse retrieval for hybrid search (Ch 6)"),
    ("pytest", "pytest", "the test suite"),
]

# The pin that pip will happily get wrong. See requirements.txt.
CRITICAL_PIN = ("langchain_community", "0.3.", (
    "ragas 0.4.3 imports langchain_community.chat_models.vertexai, removed in\n"
    "     0.4.x. pip resolves 0.4.x cleanly and then `import ragas` fails at\n"
    "     RUNTIME. Fix:  pip install 'langchain-community==0.3.29'"))


def main() -> int:
    problems = []

    print("dependencies")
    for name, module, why in REQUIRED:
        try:
            importlib.import_module(module)
            print(f"  ok      {name:22} {why}")
        except Exception as exc:
            print(f"  MISSING {name:22} {why}")
            problems.append(f"{name}: {type(exc).__name__} — "
                            f"run  pip install -r requirements.txt")

    # the load-bearing pin
    print("\ncritical pin")
    module, expected_prefix, explanation = CRITICAL_PIN
    try:
        installed = importlib.import_module(module).__version__
        if installed.startswith(expected_prefix):
            print(f"  ok      langchain-community {installed} (compatible with ragas)")
        else:
            print(f"  WRONG   langchain-community {installed} — expected {expected_prefix}x")
            problems.append("langchain-community is on an incompatible major.\n     "
                            + explanation)
    except Exception:
        pass   # already reported above

    # secrets: present or absent, never printed
    print("\nmodel access")
    key = os.environ.get("OPENAI_API_KEY", "")
    if key:
        print(f"  ok      OPENAI_API_KEY is set ({len(key)} chars, value not shown)")
    else:
        print("  absent  OPENAI_API_KEY not set")
        print("          Offline labs still run: AEGIS_MODEL=mock")
        print("          For real-model labs:    export OPENAI_API_KEY=...")
        print("          In Colab: use the key icon (Secrets), never a literal in a cell.")

    tier = os.environ.get("AEGIS_MODEL", "mock")
    print(f"  tier    AEGIS_MODEL={tier}"
          + ("  (deterministic, free, no key)" if tier == "mock" else "  (billable)"))

    if problems:
        print(f"\nFAILED — {len(problems)} problem(s):\n")
        for p in problems:
            print("   -", p)
        return 1

    print("\nOK: environment matches requirements.txt")
    return 0


if __name__ == "__main__":
    sys.exit(main())
