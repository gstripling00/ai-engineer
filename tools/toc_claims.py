"""
The TOC claims registry — every promise the table of contents makes, per chapter,
with the concrete token that proves a lab actually covers it.

This exists because of a real defect found in this book: lab descriptions drifted
from lab code, and nobody could tell, because "the lab teaches X" was checked by
reading prose rather than by grepping the artifact. Here, a claim is only
"covered" if the notebook contains the token that can only exist if the code is
really there.

Each claim:
    id           — stable key
    toc          — the TOC section it comes from
    claim        — the promise, in the TOC's own words
    must_contain — token(s) that MUST appear in the chapter's lab notebook.
                   Pick tokens that cannot be faked by prose: a function name, a
                   class, a library import, a printed metric name.

tools/check_toc_coverage.py fails the build if any claim is uncovered.
"""

CLAIMS = {
 1: [
  dict(id="1.1", toc="§1.1", claim="The four universal components: model, tools, memory, orchestrator",
       must_contain=["TOOL_REGISTRY", "new_memory", "ModelResponse", "max_steps"],
       expect_output=["COMPONENT 1", "COMPONENT 2", "COMPONENT 3", "COMPONENT 4"]),
  dict(id="1.3", toc="§1.3", claim="Tool registry: registering capabilities, schemas, descriptions",
       must_contain=["TOOL_SCHEMAS", "call_tool"],
       expect_output=["search_logs", "ip_reputation", "required args"]),
  dict(id="1.5", toc="§1.5", claim="Orchestration loop: evaluate state, act, observe",
       must_contain=["is_final", "tool_calls"],
       expect_output=["step 0:", "step 1:", "FINAL"]),
  dict(id="1.6", toc="§1.6.3", claim="Termination: goal completion vs. max iterations",
       must_contain=["max_steps", "halt"],
       expect_output=["halt", "max_steps reached", "termination reason"]),
 ],
 2: [
  dict(id="2.1", toc="§2.1", claim="Three layers: identity, context, constraints",
       must_contain=["IDENTITY", "CONTEXT", "CONSTRAINTS", "build_system_prompt"],
       expect_output=["identity", "context", "constraints", "chars"]),
  dict(id="2.3", toc="§2.3.3", claim="Delimiters: separating instructions from data",
       must_contain=["build_system_prompt", "print(prompt)"],
       expect_output=["# Identity", "# Context", "# Constraints", "# Output"]),
  dict(id="2.5", toc="§2.5.3", claim="The limits of prose: a rule that must always hold belongs in code",
       must_contain=["hostile", "preference"],
       expect_output=["constraints OFF", "constraints ON", "ESCALATE"]),
  dict(id="2.6", toc="§2.6", claim="Few-shot prompting: examples guide behavior and output format",
       must_contain=["FEW_SHOT", "example"],
       expect_output=["without examples", "with examples", "VERDICT:"]),
 ],
 3: [
  dict(id="3.2", toc="§3.2", claim="Function calling mechanics: request-response lifecycle",
       must_contain=["IP_REPUTATION_SCHEMA", "fc_dispatch"],
       expect_output=["function calling", "malicious"]),
  dict(id="3.3", toc="§3.3", claim="Structured output: enforcing AND validating before execution",
       must_contain=["validate_tool_call", "json.loads"],
       expect_output=["valid call", "unknown_tool", "bad_arguments"]),
  dict(id="3.5.2", toc="§3.5.2", claim="Automating the tool registry from an OpenAPI specification",
       must_contain=["SOC_OPENAPI", "openapi_to_schemas"],
       expect_output=["schemas before", "schemas after", "hand-written"]),
  dict(id="3.5.3", toc="§3.5.3", claim="Model Context Protocol: runtime tool discovery",
       must_contain=["list_tools", "discovered"],
       expect_output=["discovered at runtime", "ip_reputation", "search_logs"]),
  dict(id="3.5.4", toc="§3.5.4", claim="Choosing the right integration strategy",
       must_contain=["TRADEOFFS"],
       expect_output=["effort per tool", "runtime discovery", "identical"]),
 ],
 4: [
  dict(id="4.2", toc="§4.2", claim="Intent recognition, incl. ambiguous / multi-intent input",
       must_contain=["classify_intent", "multi_intent"],
       expect_output=["multi_intent", "report_phishing", "hand_off"]),
  dict(id="4.3", toc="§4.3", claim="Entity extraction and normalization",
       must_contain=["extract_slots", "clean"],
       expect_output=["sender", "malicious_url", "8:40am"]),
  dict(id="4.3.3", toc="§4.3.3", claim="Grounded extraction: a model may propose, only the text may confirm",
       must_contain=["grounded_extract", "rejected"],
       expect_output=["accepted", "rejected", "ceo@"]),
  dict(id="4.4", toc="§4.4", claim="Slot filling: proactively elicit what is missing",
       must_contain=["REQUIRED_SLOTS", "next_question", "missing"],
       expect_output=["questions asked", "complete"]),
  dict(id="4.5", toc="§4.5.3", claim="Interruptions and clarification",
       must_contain=["is_interruption", "handle_turn"],
       expect_output=["interruption", "resumed"]),
 ],
 5: [
  dict(id="5.2", toc="§5.2.2", claim="Working memory + token optimization (truncate/window/summarize)",
       must_contain=["count_tokens", "truncate", "sliding_window", "summarize_middle"],
       expect_output=["truncate", "sliding_window", "summarize_middle", "keeps system prompt"]),
  dict(id="5.3", toc="§5.3", claim="Episodic memory: recall past episodes by similarity",
       must_contain=["EpisodicMemory", "recall"],
       expect_output=["CAMPAIGN", "recalled"]),
  dict(id="5.3.4", toc="§5.3.4", claim="The similarity threshold is a measured decision",
       must_contain=["threshold"],
       expect_output=["threshold", "recalled"]),
  dict(id="5.4", toc="§5.4", claim="Semantic memory: durable enterprise facts",
       must_contain=["SEMANTIC_FACTS", "is_known_bad_sender"],
       expect_output=["known bad"]),
  dict(id="5.5", toc="§5.5", claim="Procedural memory: learned playbooks, only successes reinforce",
       must_contain=["ProceduralMemory", "succeeded"],
       expect_output=["after a FAILED run", "playbook"]),
 ],
 6: [
  dict(id="6.1", toc="§6.1", claim="Two-phase pipeline: indexing then retrieval",
       must_contain=["chunk", "retrieve"],
       expect_output=["chunks", "retrieved"]),
  dict(id="6.2", toc="§6.2", claim="Vector embeddings and similarity",
       must_contain=["embed", "cosine"],
       expect_output=["similarity"]),
  dict(id="6.3", toc="§6.3.2", claim="Four strategies: fixed, sentence-window, semantic, hierarchical",
       must_contain=["chunk_fixed", "chunk_sentence_window", "chunk_semantic", "chunk_hierarchical"],
       expect_output=["fixed", "sentence-window", "semantic", "hierarchical"]),
  dict(id="6.4", toc="§6.4.2", claim="Query transformation",
       must_contain=["rewrite_query"],
       expect_output=["before:", "after:"]),
  dict(id="6.5", toc="§6.5.2", claim="Hybrid retrieval: dense + sparse (BM25)",
       must_contain=["HybridRetriever", "BM25"],
       expect_output=["dense only", "sparse only", "hybrid"]),
 ],
 7: [
  dict(id="7.2", toc="§7.2", claim="Chain-of-thought: reasoning as an inspectable artifact",
       must_contain=["chain_of_thought"],
       expect_output=["thought:", "conclusion:"]),
  dict(id="7.3", toc="§7.3", claim="The ReAct loop: thought, action, observation",
       must_contain=["trajectory"],
       expect_output=["action", "observation"]),
  dict(id="7.4", toc="§7.4", claim="Plan-and-solve + dynamic replanning",
       must_contain=["make_plan", "execute_plan", "replanned"],
       expect_output=["replanned", "correlate auth failures"]),
  dict(id="7.5", toc="§7.5", claim="Tool selection logic under ambiguity",
       must_contain=["select_tool", "margin"],
       expect_output=["margin", "REFUSED"]),
  dict(id="7.6", toc="§7.6", claim="Self-reflection: catch a conclusion the evidence doesn't support",
       must_contain=["reflect", "revised"],
       expect_output=["revised", "inconclusive"]),
 ],
 8: [
  dict(id="8.1", toc="§8.1.4", claim="The security case: the reader is not the actor",
       must_contain=["TRIAGE_TOOLS", "REPORT_TOOLS"],
       expect_output=["may create_ticket", "denied"]),
  dict(id="8.2", toc="§8.2", claim="Orchestrator-worker topology",
       must_contain=["triage", "investigate", "report"],
       expect_output=["triage", "investigation", "reporting"]),
  dict(id="8.3", toc="§8.3", claim="A2A handoffs carrying structured state",
       must_contain=["trace_id", "handoff"],
       expect_output=["trace", "handoff"]),
  dict(id="8.3.3", toc="§8.3.3", claim="Boundaries preventing infinite delegation loops",
       must_contain=["max_handoffs", "Delegation"],
       expect_output=["REFUSED", "max_handoffs exceeded"]),
  dict(id="8.4", toc="§8.4", claim="Parallel execution: scatter-gather and merge",
       must_contain=["fan_out", "ThreadPoolExecutor"],
       expect_output=["branches", "single trace", "dissent"]),
 ],
 9: [
  dict(id="9.2", toc="§9.2", claim="Semantic routing by meaning",
       must_contain=["semantic_route", "ROUTE_DESCRIPTIONS"],
       expect_output=["phishing_handler", "auth_handler"]),
  dict(id="9.2.3", toc="§9.2.3", claim="Confidence and margin: a router that can say 'I don't know'",
       must_contain=["route_with_confidence", "margin"],
       expect_output=["margin", "would_have_routed_to", "human_analyst"]),
  dict(id="9.3.4", toc="§9.3.4", claim="Severity as policy: never a model",
       must_contain=["severity_route"],
       expect_output=["distinct outcomes", "human_analyst"]),
  dict(id="9.4", toc="§9.4", claim="Fallback and graceful degradation, flagged",
       must_contain=["route_with_fallback", "degraded"],
       expect_output=["degraded", "generalist"]),
  dict(id="9.5", toc="§9.5.2", claim="Escalation with full state",
       must_contain=["build_escalation"],
       expect_output=["verdict", "state"]),
  dict(id="9.6", toc="§9.6", claim="MCP context discovery: routes discovered at runtime",
       must_contain=["discover_routes"],
       expect_output=["discovered", "device_handler"]),
 ],
 11: [
  dict(id="11.1.2", toc="§11.1.2", claim="The five attack surfaces",
       must_contain=["attack surface"],
       expect_output=["injection", "exfiltration", "accountability"]),
  dict(id="11.2", toc="§11.2", claim="Indirect prompt injection, defeated",
       must_contain=["scan_for_injection", "safe_ingest"],
       expect_output=["injection_detected", "escalat"]),
  dict(id="11.3", toc="§11.3", claim="Bi-directional safety filters, explainable blocks",
       must_contain=["safety_filter", "guarded_model_call"],
       expect_output=["blocked_at", "input", "output"]),
  dict(id="11.4", toc="§11.4", claim="PII masking",
       must_contain=["mask_pii"],
       expect_output=["REDACTED", "203.0.113.42"]),
  dict(id="11.5", toc="§11.5", claim="Least-privilege IAM per agent + audit",
       must_contain=["authorize", "AuditLog"],
       expect_output=["allowed", "DENIED"]),
  dict(id="11.6", toc="§11.6", claim="MCP hardening: poisoned descriptions, rug pulls",
       must_contain=["screen_tool_definition", "detect_rug_pull"],
       expect_output=["rejected", "changed"]),
  dict(id="11.7", toc="§11.7", claim="Defense in depth: a regex is a speed bump",
       must_contain=["base64"],
       expect_output=["base64", "blocked: False"]),
 ],
 10: [
  dict(id="10.1.3", toc="§10.1.3", claim="Silent failure: a wrong answer throws no exception",
       must_contain=["silent"],
       expect_output=["200 OK", "no exception", "fabricated"]),
  dict(id="10.2", toc="§10.2", claim="Golden dataset incl. adversarial + benign traps",
       must_contain=["GOLDEN", "trap"],
       expect_output=["benign trap", "attack"]),
  dict(id="10.3", toc="§10.3", claim="Faithfulness and answer relevance (the measure)",
       must_contain=["faithfulness"],
       expect_output=["faithfulness", "supporting context", "unrelated context"]),
  dict(id="10.3.4b", toc="§10.3.4", claim="RAGAS LLM-judged metrics (Faithfulness, AnswerRelevancy)",
       must_contain=["AnswerRelevancy", "LangchainLLMWrapper"],
       documented_not_demonstrated=(
           "These metrics judge with an LLM by design, so they require a paid OpenAI key; "
           "the offline verifier cannot run them without billing a real account. The cell "
           "ships ready to run and is tagged needs_api_key.")),
  dict(id="10.3.4", toc="§10.3.4", claim="REAL RAGAS - reference-free metrics",
       must_contain=["ragas.metrics.collections", "BleuScore"],
       expect_output=["ragas version"]),
  dict(id="10.3.5", toc="§10.3.5", claim="Never average precision and recall",
       must_contain=["precision", "recall"],
       expect_output=["precision", "recall", "false negative"]),
  dict(id="10.4", toc="§10.4", claim="LLM-as-a-judge with a rubric + bias mitigation",
       must_contain=["judge", "RUBRIC"],
       expect_output=["grounded", "complete", "actionable"]),
  dict(id="10.4.4", toc="§10.4.4", claim="Calibrating the judge: false pass vs false fail",
       must_contain=["false_pass", "false_fail"],
       expect_output=["false_pass", "false_fail", "agreement"]),
  dict(id="10.5", toc="§10.5", claim="Tracing: spans across the whole investigation",
       must_contain=["Tracer", "span"],
       expect_output=["trace for", "received"]),
 ],
 12: [
  dict(id="12.2.3", toc="§12.2.3", claim="The evaluation gate: arithmetic, not judgment",
       must_contain=["eval_gate"],
       expect_output=["BLOCKED", "recall"]),
  dict(id="12.3", toc="§12.3", claim="Canary deployments and rollback",
       must_contain=["canary_decision"],
       expect_output=["promote", "rollback"]),
  dict(id="12.4.2", toc="§12.4.2", claim="Latency is a ceiling, quality is a floor",
       must_contain=["check_slos"],
       expect_output=["ALERT", "escalation_accuracy"]),
  dict(id="12.5.2", toc="§12.5.2", claim="Dynamic model routing",
       must_contain=["stage_model", "incident_cost"],
       expect_output=["routed", "all-strong", "saved"]),
  dict(id="12.5.3", toc="§12.5.3", claim="Model retirements and stale prices: date every number",
       must_contain=["PRICES_VERIFIED", "retirement_warnings"],
       expect_output=["verified", "retires"]),
  dict(id="12.6", toc="§12.6", claim="The release policy: which gates block, which only warn",
       must_contain=["cost_gate", "release"],
       expect_output=["cost_regression", "released"]),
 ],
 13: [
  dict(id="13.1", toc="§13.1", claim="Capstone assembly: every chapter's component in one pipeline",
       must_contain=["AegisV12", "trace"],
       expect_output=["guarded_ingest", "routed", "memory_recall", "triage",
                      "investigation", "reported"]),
  dict(id="13.2", toc="§13.2", claim="One incident, one trace id, end to end",
       must_contain=["trace_id"],
       expect_output=["trace_id", "single trace"]),
  dict(id="13.3", toc="§13.3", claim="Defense in depth holds in the assembled system",
       must_contain=["injection_detected"],
       expect_output=["injection_detected", "escalated"]),
  dict(id="13.4", toc="§13.4", claim="Least privilege survives assembly: one agent writes",
       must_contain=["audit"],
       expect_output=["create_ticket", "who touched the world"]),
  dict(id="13.5", toc="§13.5", claim="The analyst interface renders from the real run",
       must_contain=["render_ticket_comment", "interface_contract"],
       expect_output=["AEGIS", "Verdict", "contract satisfied"]),
  dict(id="13.6", toc="§13.6", claim="Enterprise graduation: a real vector store (ChromaDB), persisted",
       must_contain=["chromadb", "PersistentClient"],
       expect_output=["persisted", "reopened"]),
  dict(id="13.6b", toc="§13.6b", claim="Enterprise graduation: real SOC data formats (Wazuh, Sigma, MISP)",
       must_contain=["from_wazuh", "parse_sigma", "from_misp"],
       expect_output=["rule.level", "UNMODIFIED capstone", "false positives", "actionable"]),
  dict(id="13.7", toc="§13.7", claim="Enterprise graduation: a live model tier",
       must_contain=["AEGIS_MODEL", "openai"],
       documented_not_demonstrated=(
           "Running the assembled system against a live model requires a paid OpenAI key; "
           "the offline verifier cannot exercise it without billing a real account. The "
           "cell ships ready to run and is tagged needs_api_key.")),
 ],
}


def claim_count() -> int:
    return sum(len(v) for v in CLAIMS.values())


# --------------------------------------------------------------------------- #
# Duplicate-key guard.
#
# A dict literal silently accepts a repeated key and keeps the LAST one. That bit
# twice while building this registry: a corrected claims block was overwritten by
# a stale one further down, and the validator then reported claims as unverifiable
# for reasons that had nothing to do with the notebooks.
# --------------------------------------------------------------------------- #
import re as _re
_source = open(__file__).read()
_keys = _re.findall(r"^\s(\d+): \[", _source, _re.M)
if len(_keys) != len(set(_keys)):
    _dupes = sorted({k for k in _keys if _keys.count(k) > 1})
    raise RuntimeError(f"duplicate chapter keys in CLAIMS: {_dupes} - "
                       "a later block is silently overwriting an earlier one")
