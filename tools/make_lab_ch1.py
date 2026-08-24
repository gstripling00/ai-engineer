#!/usr/bin/env python3
"""Build the Chapter 1 canonical lab notebook."""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
from lab_builder import md, code, build      # noqa: E402

OUT = os.path.join(REPO, "ch01", "Aegis_Chapter1_Lab.ipynb")

INTRO = [
    md("# Chapter 1 — Anatomy of an Agent",
       "",
       "Every agent, in every framework, is the same four components:",
       "",
       "| # | Component | What it is, concretely |",
       "|---|---|---|",
       "| 1 | **Model** | the reasoning engine that decides what to do next |",
       "| 2 | **Tools** | a dictionary of callables, plus schemas describing them |",
       "| 3 | **Memory** | a list of messages the model re-reads each turn |",
       "| 4 | **Orchestrator** | the loop that ties them together and decides when to stop |",
       "",
       "This lab builds a working agent from the repository's own code, so what you run here",
       "is what the rest of the book builds on. It triages one security alert: a burst of",
       "failed logins followed by a success.",
       "",
       "**Covered in this lab:** §1.1 four components · §1.3 tool registry and schemas ·",
       "§1.5 the orchestration loop · §1.6.3 termination conditions."),
]

BODY = [
    md("## §1.1 — The four components, named in the code",
       "",
       "Import them from the repository and print what each one actually is. No abstraction:",
       "a dict, a list, a callable, and a `for` loop."),
    code('''import sys
sys.path.insert(0, "ch01")

from scratch.triage_agent import TOOL_REGISTRY, TOOL_SCHEMAS, new_memory, call_tool, run
from common.model import get_model, ModelResponse
from common import soc

print("COMPONENT 1  model        ", type(get_model()).__name__,
      "- returns", ModelResponse.__name__)
print("COMPONENT 2  tools        ", type(TOOL_REGISTRY).__name__,
      "of", len(TOOL_REGISTRY), "callables:", list(TOOL_REGISTRY))
print("COMPONENT 3  memory       ", type(new_memory(soc.SEED_ALERT)).__name__,
      "of", len(new_memory(soc.SEED_ALERT)), "messages")
print("COMPONENT 4  orchestrator  run(alert, max_steps=...) - a bounded loop")'''),

    md("## §1.3 — The tool registry",
       "",
       "A registry is a dict mapping names to callables. The *schemas* are what the model",
       "sees: name, description, and a JSON Schema for the arguments.",
       "",
       "Both tools here are read-only. An agent that can only read can embarrass you; an",
       "agent that can write can hurt you. Chapter 3 does tools properly; Chapter 8 decides",
       "who is allowed to hold the dangerous one."),
    code('''for schema in TOOL_SCHEMAS:
    fn = schema["function"]
    print(f'{fn["name"]:15} required args: {fn["parameters"].get("required", [])}')
    print(f'{"":15} description:   {fn["description"]}')

print()
print("dispatch is a dict lookup:")
print("  ", call_tool("ip_reputation", {"ip": "203.0.113.42"})[:72], "...")'''),

    md("## §1.5 — The orchestration loop",
       "",
       "Each turn the model either requests a tool call or produces a final answer. Tool",
       "results are appended to memory as observations, and the loop runs again. That",
       "think-act-observe cycle is the ReAct pattern.",
       "",
       "Run it and watch the loop decide."),
    code('''# The loop's branch, made visible: a ModelResponse is EITHER a final answer
# OR a set of tool calls. `is_final` is the whole control-flow decision.
model = get_model()
memory = new_memory(soc.SEED_ALERT)

first = model.chat(memory, TOOL_SCHEMAS)
print("turn 1  is_final =", first.is_final,
      " tool_calls =", [c.name for c in first.tool_calls])

# feed the observation back, exactly as the loop does
for call in first.tool_calls:
    memory.append({"role": "tool", "content": call_tool(call.name, call.args)})

second = model.chat(memory, TOOL_SCHEMAS)
print("turn 2  is_final =", second.is_final,
      " tool_calls =", [c.name for c in second.tool_calls])
print()
print("that is the entire orchestration decision: act, or stop.")'''),

    md("Now run the whole loop and watch it do exactly that."),
    code('''result = run(verbose=True)

print()
print("model tier:", result["model"])
print("trajectory:")
for tool, observation in result["trajectory"]:
    print(f'  {tool:16} {observation[:56]}')'''),

    md("## §1.6.3 — Termination: goal completion vs. max iterations",
       "",
       "Two ways to stop, and they are not equivalent. The first is the agent deciding it is",
       "done. The second is the budget running out.",
       "",
       "`max_steps` is a **safety** control, not a performance detail: an agent with tools and",
       "no bound is an unbounded actor. Note that the halt is *recorded in the trajectory* — a",
       "silent truncation would be the bug."),
    code('''starved = run(max_steps=1, verbose=False)

print("with max_steps=1:")
for tool, observation in starved["trajectory"]:
    print(f'  {tool:16} {observation[:56]}')

halted = [(t, o) for t, o in starved["trajectory"] if t == "halt"]
print()
for tool, observation in halted:
    print(f'termination reason recorded: {tool} -> "{observation}"')
print("halt recorded in the trace:", bool(halted))
print("the budget is a safety control, and the truncation is visible - not silent")'''),
]

CLOSING = [
    md("---",
       "",
       "## What you built",
       "",
       "A working agent in about forty lines of the repository's own code: a model behind a",
       "swappable seam, a tool registry, a memory list, and a bounded loop.",
       "",
       "Every framework in this book — and every framework outside it — rearranges these four",
       "parts and gives them new names.",
       "",
       "**Next:** Chapter 2 layers the system prompt and shows a single constraint changing a",
       "verdict into an escalation."),
]


def main():
    nb = build(1, "Anatomy of an Agent", INTRO, BODY, CLOSING)
    with open(OUT, "w") as f:
        json.dump(nb, f, indent=1)
    print("wrote", os.path.relpath(OUT, REPO),
          f"({len(nb['cells'])} cells, {sum(1 for c in nb['cells'] if c['cell_type']=='code')} code)")


if __name__ == "__main__":
    main()
