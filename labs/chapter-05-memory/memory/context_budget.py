"""
Working memory and the token budget (§5.2.2).

Working memory is a buffer you pay for on every call. When it outgrows the
budget, something has to go — and HOW it goes is a design decision, not a
detail. Three strategies, same interface:

    truncate          keep the most recent messages that fit. Naive, and it
                      will drop the system prompt without telling you.
    sliding_window    pin the system prompt, then keep the most recent messages.
    summarize_middle  pin the system prompt, keep the most recent messages, and
                      replace everything in between with one summary message.

Token counting here is a character heuristic (~4 chars per token) so the lab
runs offline. Swap in tiktoken for a real model; the strategies do not change.
"""


def count_tokens(messages: list) -> int:
    """Approximate token count: ~4 characters per token, plus per-message overhead."""
    return sum(len(m.get("content", "")) // 4 + 3 for m in messages)


def _tokens(message: dict) -> int:
    return count_tokens([message])


def truncate(messages: list, budget: int) -> list:
    """Keep the most recent messages that fit. Treats the system prompt like any
    other message — which is the bug."""
    kept, used = [], 0
    for m in reversed(messages):
        cost = _tokens(m)
        if used + cost > budget:
            break
        kept.insert(0, m)
        used += cost
    return kept


def sliding_window(messages: list, budget: int) -> list:
    """Pin the system prompt; fill the rest of the budget from the most recent end."""
    if not messages:
        return []
    system = [m for m in messages[:1] if m.get("role") == "system"]
    rest = messages[len(system):]
    used = count_tokens(system)
    window = []
    for m in reversed(rest):
        cost = _tokens(m)
        if used + cost > budget:
            break
        window.insert(0, m)
        used += cost
    return system + window


def _summarize(dropped: list) -> str:
    """A deterministic stand-in for a model-written summary."""
    calls = [m["content"] for m in dropped if m.get("content", "").startswith("[call]")]
    tools = sorted({c.split("]")[1].split("(")[0].strip() for c in calls})
    return (f"[summary of {len(dropped)} earlier messages: "
            f"{len(calls)} tool calls to {', '.join(tools) or 'no tools'}]")


def summarize_middle(messages: list, budget: int) -> list:
    """Pin the system prompt, keep the most recent messages, summarize the middle."""
    if not messages:
        return []
    system = [m for m in messages[:1] if m.get("role") == "system"]
    rest = messages[len(system):]
    summary_slot = {"role": "system", "content": _summarize(rest)}   # worst-case size
    used = count_tokens(system) + _tokens(summary_slot)
    recent = []
    for m in reversed(rest):
        cost = _tokens(m)
        if used + cost > budget:
            break
        recent.insert(0, m)
        used += cost
    dropped = rest[:len(rest) - len(recent)]
    if not dropped:
        return system + recent
    return system + [{"role": "system", "content": _summarize(dropped)}] + recent
