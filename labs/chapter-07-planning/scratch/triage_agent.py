"""
The Chapter 1 ReAct loop, unchanged in shape: model decides, tool acts, the
observation goes back into memory, repeat until the model concludes or the step
budget runs out. Reproduced here so Chapter 7 can contrast it with a plan
without depending on another chapter's folder.
"""
import json
import os
import sys
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from planning.tools import INCIDENT, TOOLS, call_tool  # noqa: E402

ALERT = dict(INCIDENT)

TOOL_SCHEMAS = [
    {"type": "function", "function": {"name": name, "description": fn.__doc__ or name,
                                      "parameters": {"type": "object"}}}
    for name, fn in TOOLS.items()
]


@dataclass
class ToolCall:
    name: str
    args: dict


@dataclass
class ModelResponse:
    text: str = ""
    tool_calls: list = field(default_factory=list)

    @property
    def is_final(self) -> bool:
        return not self.tool_calls


class MockModel:
    """Deterministic: check the IP, then the user, then conclude."""
    name = "mock"

    def chat(self, messages: list, tools: list) -> ModelResponse:
        used = [m["content"] for m in messages if m["role"] == "assistant" and m["content"].startswith("[call]")]
        if not any("ip_reputation" in u for u in used):
            return ModelResponse(tool_calls=[ToolCall("ip_reputation", {"ip": ALERT["src_ip"]})])
        if not any("get_user_context" in u for u in used):
            return ModelResponse(tool_calls=[ToolCall("get_user_context", {"user": ALERT["user"]})])
        return ModelResponse(text="Investigation complete. See structured findings.")


def new_memory(alert: dict) -> list:
    return [{"role": "system", "content": "You are Aegis, a tier-1 SOC triage agent."},
            {"role": "user", "content": f"Triage this alert: {json.dumps(alert)}"}]


def run(alert: dict | None = None, max_steps: int = 5, verbose: bool = True) -> dict:
    alert = alert or ALERT
    model = MockModel()
    memory = new_memory(alert)
    trajectory = []
    for step in range(max_steps):
        response = model.chat(memory, TOOL_SCHEMAS)
        if response.is_final:
            memory.append({"role": "assistant", "content": response.text})
            trajectory.append(("final", response.text))
            if verbose:
                print(f"  step {step}: FINAL - {response.text}")
            break
        for call in response.tool_calls:
            observation = call_tool(call.name, call.args)
            memory.append({"role": "assistant", "content": f"[call] {call.name}({json.dumps(call.args)})"})
            memory.append({"role": "tool", "content": observation})
            trajectory.append((call.name, observation))
            if verbose:
                print(f"  step {step}: {call.name}({call.args}) -> {observation[:60]}")
    else:
        trajectory.append(("halt", "max_steps reached"))
    return {"model": model.name, "trajectory": trajectory, "memory": memory}
