#!/usr/bin/env python3
"""
Generate a free-Colab notebook for each Aegis chapter from a metadata table.

One generator keeps all twelve notebooks consistent: same three-tier model story
(mock -> Ollama -> Gemini), same run-the-demo / run-the-tests structure, chapter-
specific narrative and commands. Run from the repo root:

    python tools/make_notebooks.py
"""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
from nb_visuals import step_banner, pill, progress_bar, callout, expected_output

# Real captured demo output (per chapter) to embed as 'you should see this' panels.
_DEMO = {}
_demo_path = "/tmp/demo_out.json"
if os.path.exists(_demo_path):
    with open(_demo_path) as _f:
        _DEMO = {int(k): v for k, v in json.load(_f).items()}


# Per-chapter metadata: folder, title, one-line hook, the primary demo module,
# and the specific "what just happened" note.
CHAPTERS = [
    dict(dir="ch01", title="Anatomy of an Agent",
         hook="Aegis is born: a bare ReAct loop that triages one alert, exposing the four "
              "components every agent has — model, tools, memory, orchestrator.",
         demo="scratch/triage_agent.py",
         extra=[("The same agent, three ways",
                 "Run the LangGraph and ADK versions and notice the four components "
                 "reappear in each — proof they're concepts, not framework features.",
                 ["langgraph_track/triage_graph.py", "adk_track/triage_adk.py"])],
         note="You just built an agent with no framework, then recognized its parts inside two."),
    dict(dir="ch02", title="System Prompts",
         hook="A system prompt is three layers — identity, context, constraints. Watch the "
              "constraint layer flip a confident wrong verdict into a correct escalation.",
         demo="langgraph_track/demo_constraints.py",
         extra=[],
         note="Same privileged-account alert: constraints OFF -> verdict; constraints ON -> escalate."),
    dict(dir="ch03", title="Giving Agents Tools",
         hook="The same SOC tools wired three ways — function calling, OpenAPI, and a real MCP "
              "server/client — so you can feel the tradeoffs in reuse and discovery.",
         demo="compare.py",
         extra=[("Each mechanism on its own",
                 "Run them individually to see the schema effort, the one-spec-to-many-tools "
                 "payoff, and MCP runtime discovery.",
                 ["function_calling/tools_fc.py", "openapi/tools_openapi.py", "mcp_track/tools_mcp.py"])],
         note="Same verdict every way — the mechanism changes reuse and coupling, not the answer."),
    dict(dir="ch04", title="Conversational Agents (Slot Filling)",
         hook="Aegis interviews an employee about a suspicious email, filling an incident form "
              "one question at a time until it can hand off a structured record.",
         demo="langgraph_track/intake_graph.py",
         extra=[],
         note="Free text in, structured incident out — the intake that feeds triage."),
    dict(dir="ch05", title="Memory",
         hook="Give Aegis memory and the third phishing report from the same sender this week "
              "is recognized as a campaign, not an isolated one-off.",
         demo="langgraph_track/memory_demo.py",
         extra=[],
         note="isolated -> isolated -> CAMPAIGN: episodic recall is the whole difference."),
    dict(dir="ch06", title="RAG",
         hook="Ground Aegis in incident-response runbooks and CVE advisories, and compare how "
              "three chunking strategies affect retrieval.",
         demo="langgraph_track/rag_demo.py",
         extra=[],
         note="All strategies retrieve the right runbook here; note the confidence spread — "
              "that gap becomes hit-vs-miss at production scale."),
    dict(dir="ch07", title="Planning",
         hook="Aegis plans a multi-signal investigation up front, then replans when a log "
              "source goes down — reaching a verdict instead of dead-ending.",
         demo="langgraph_track/plan_demo.py",
         extra=[],
         note="With the 1-hour log window down, step 1 falls back to a broader search and the "
              "investigation still completes."),
    dict(dir="ch08", title="Multi-Agent Systems",
         hook="Aegis becomes a team: one agent splits into Triage, Investigation, and Reporting "
              "workers coordinated by the A2A handoff pattern.",
         demo="langgraph_track/multi_agent.py",
         extra=[("The Google Cloud track",
                 "The same pipeline on ADK 2.x's Workflow graph with native A2A.",
                 ["adk_track/multi_agent_adk.py"])],
         note="Three specialists, escalating privilege — only Reporting can open a ticket."),
    dict(dir="ch09", title="Routing and Coordination",
         hook="Route each alert to the right handler by meaning and severity, fall back when a "
              "handler is down, and escalate to a human with full state.",
         demo="langgraph_track/routing_demo.py",
         extra=[],
         note="Semantic routing by type, deterministic routing by severity, graceful fallback, "
              "stateful escalation."),
    dict(dir="ch10", title="Evaluation and Observability",
         hook="Grade Aegis against a golden dataset of labeled alerts, score the RAG component "
              "with RAGAS-style metrics, and trace an investigation.",
         demo="langgraph_track/eval_demo.py",
         extra=[],
         note="The demo deliberately surfaces a recall gap — evaluation catching a real bug is "
              "the point."),
    dict(dir="ch11", title="Security: Securing the Agent That Secures You",
         hook="Red-team Aegis: an indirect prompt injection hidden in a log line. Watch the "
              "unguarded agent obey it and the guarded agent defeat it.",
         demo="langgraph_track/redteam_demo.py",
         extra=[],
         note="Unguarded -> attacker flips the verdict to benign. Guarded -> neutralized and "
              "escalated. Plus PII masking and least-privilege IAM."),
    dict(dir="ch12", title="Deployment",
         hook="Take the three-agent Aegis to production: a CI/CD eval gate, canary rollout, "
              "SLO alerting, and dynamic model routing for cost control.",
         demo="langgraph_track/deploy_demo.py",
         extra=[],
         note="Eval gate blocks regressions, canary promotes within tolerance, SLO breach alerts, "
              "and routing saves ~73% by sending triage to a fast model."),
]

CH_NUM = {c["dir"]: str(i + 1) for i, c in enumerate([c for c in CHAPTERS])}
# fix numbering: ch08 is chapter 8 etc. — derive from the dir digits instead.
def num(d): return str(int(d[2:]))


def md(*lines):
    return {"cell_type": "markdown", "metadata": {}, "source": [l + "\n" for l in lines]}


def code(*lines):
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [],
            "source": [l + "\n" for l in lines]}


def build_notebook(ch: dict) -> dict:
    n = num(ch["dir"])
    ci = int(n)
    demo_lines = _DEMO.get(ci, {}).get("lines", [])
    TOTAL_STEPS = 5

    cells = [
        # ---- Title ----
        md(f"# 🛡️ Aegis · Chapter {n} — {ch['title']}",
           "",
           f"{ch['hook']}",
           "",
           f"{pill('BEGINNER-FRIENDLY', '#2FA84F')} &nbsp; {pill('FREE COLAB', '#3D7EDB')} "
           f"&nbsp; {pill('NO API KEY', '#8A4FCF')}",
           "",
           "This is a **paint-by-numbers** lab. Do the steps in order, top to bottom. "
           "Every code cell has a ▶️ button on its left — click it and wait for the "
           "spinner to stop before moving on. You do **not** need to understand or "
           "type any code; you run it and read what comes back.",
           "",
           progress_bar(0, TOTAL_STEPS, "0 of 5 steps done — start below")),

        # ---- What you'll see (the flow diagram) ----
        md(f"![What this lab does](./Aegis_Chapter{n}_flow.svg)",
           "",
           "*Above: the whole lab at a glance. Each box is something you'll watch happen.*",
           "",
           *callout("why", ch["note"])),

        # ---- STEP 1: Setup ----
        md(step_banner(1, "Set up the lab", "run these two cells once — about 30 seconds"),
           "",
           "Click ▶️ on the next cell to download the book's code into this Colab. "
           "A long list of lines will scroll by — that's normal.",
           "",
           *callout("tip", "First time in Colab? A cell is **running** when you see a "
                    "spinning circle to its left, and **done** when that circle "
                    "becomes a number in brackets like `[1]`.")),
        code("# \u25b6\ufe0f Click the play button on the LEFT of this cell.",
             "# Set this to the book's companion repository:",
             'REPO_URL = "https://github.com/<your-org>/<your-repo>.git"',
             "",
             "import os, sys, subprocess",
             "",
             'if not os.path.isdir("aegis"):',
             '    r = subprocess.run(["git", "clone", REPO_URL, "aegis"],',
             "                       capture_output=True, text=True)",
             "    if r.returncode != 0:",
             '        raise RuntimeError("git clone failed - check REPO_URL above.\\n" + r.stderr)',
             "",
             'os.chdir("aegis")',
             'sys.path.insert(0, os.path.abspath("."))',
             "print('Repo ready at:', os.getcwd())"),
        md("Now install the exact tested versions of the libraries the labs use. "
           "Click ▶️ and wait for **Done** to print at the bottom."),
        code("# ▶️ Installs pinned dependencies (tested versions — no surprises).",
             "!pip -q install langgraph==1.2.9 langchain-core==1.4.9 mcp==1.28.1 google-adk==2.4.0 pytest",
             "print('Done — dependencies installed.')"),
        md(*callout("check", "Both cells above finished without a red error box? "
                    "You're set up. If you saw a red box, re-run the cell once — "
                    "Colab occasionally hiccups on the first try."),
           "",
           progress_bar(1, TOTAL_STEPS, "1 of 5 — setup complete")),

        # ---- STEP 2: Look at the picture ----
        md(step_banner(2, "Look before you run", "10 seconds — no clicking", accent="#3D7EDB"),
           "",
           "Scroll back up to the diagram for a moment. In this lab you'll watch "
           "Aegis do exactly what those boxes show. You don't need to memorize it — "
           "just know the shape of what's coming.",
           "",
           *callout("watch", ch["note"]),
           "",
           progress_bar(2, TOTAL_STEPS, "2 of 5 — oriented")),

        # ---- STEP 3: Run it (mock) ----
        md(step_banner(3, "Run the lab (mock model)", "instant, offline, deterministic", accent="#2FA84F"),
           "",
           f"{pill('TIER 1: MOCK', '#2FA84F')}",
           "",
           "Click ▶️ on the next cell. The **mock** model gives scripted answers, so "
           "the lab runs instantly and the same way every time — perfect for seeing "
           "the control flow clearly before a real model's randomness enters."),
        code("import os",
             "os.environ['AEGIS_MODEL'] = 'mock'",
             f"!cd {ch['dir']} && AEGIS_MODEL=mock python {ch['demo']}"),
    ]

    if demo_lines:
        cells.append(md(*expected_output(demo_lines),
                        "",
                        *callout("watch", ch["note"])))
    cells.append(md(*callout("check", "Your output matches the panel above (the wording "
                             "is identical on the mock tier)? Then the lab worked. ✅"),
                    "",
                    progress_bar(3, TOTAL_STEPS, "3 of 5 — you ran it")))

    # ---- optional extras become part of step 3 ----
    for title, blurb, mods in ch["extra"]:
        cells.append(md(f"#### 🔎 Bonus: {title}", blurb,
                        "", *callout("tip", "Optional — click ▶️ if you're curious; skip to Step 4 if not.")))
        cells.append(code(*[f"!cd {ch['dir']} && AEGIS_MODEL=mock python {m}" for m in mods]))

    # ---- STEP 4: real model (Ollama) ----
    cells += [
        md(step_banner(4, "See a REAL model do it", "optional — adds ~3 minutes", accent="#8A4FCF"),
           "",
           f"{pill('TIER 2: OLLAMA — FREE', '#8A4FCF')}",
           "",
           "Want to watch a genuine language model instead of the mock? This installs "
           "**Ollama** (a free, local model runner) right inside Colab and points the "
           "lab at it. Totally optional — the lab already worked in Step 3.",
           "",
           *callout("tip", "Faster with a free GPU: **Runtime ▸ Change runtime type ▸ T4 GPU** "
                    "before running these. Not required, just quicker.")),
        code("# ▶️ Installs Ollama and starts it (takes a minute).",
             "!curl -fsSL https://ollama.com/install.sh | sh",
             "import subprocess, time",
             "subprocess.Popen(['ollama','serve']); time.sleep(5)",
             "print('Pulling a small model — one-time, ~2 min...')",
             "!ollama pull gemma3:4b",
             "!pip -q install ollama==0.4.7",
             "print('Done — real model ready.')"),
        code("# ▶️ Runs the SAME lab, now on a real model.",
             "os.environ['AEGIS_MODEL'] = 'ollama'",
             "os.environ['OLLAMA_MODEL'] = 'gemma3:4b'",
             f"!cd {ch['dir']} && AEGIS_MODEL=ollama OLLAMA_MODEL=gemma3:4b python {ch['demo']}"),
        md(*callout("watch", "A real model isn't scripted, so the wording will differ from "
                    "the mock panel — and may vary run to run. The **shape** of the "
                    "result should still match. That difference is the whole lesson of "
                    "the mock tier: it lets you learn the flow first."),
           "",
           progress_bar(4, TOTAL_STEPS, "4 of 5 — real model (optional)")),

        # ---- STEP 5: tests ----
        md(step_banner(5, "Prove it works", "the same checks the authors run", accent="#F2A900"),
           "",
           "Click ▶️ to run this chapter's automated tests. Green `passed` means every "
           "piece of this lab behaves exactly as the book promises."),
        code(f"!cd {ch['dir']} && AEGIS_MODEL=mock python -m pytest tests/ -q"),
        md(*callout("check", "See `passed` in green? 🎉 You've completed the chapter lab — "
                    "run it, seen it, and verified it."),
           "",
           *callout("help", "Red `failed` or an error? Re-run **Step 1** (setup) first — "
                    "most problems are a half-finished install. Still stuck? The "
                    "chapter's `LAB_GUIDE.md` has a troubleshooting section for this "
                    "exact lab."),
           "",
           progress_bar(5, TOTAL_STEPS, "5 of 5 — done! 🛡️")),
        md("---",
           f"**What next?** Chapter {n} in the book explains *why* everything you just "
           "watched works the way it does. When you're ready, open the next chapter's "
           "notebook and keep building Aegis.",
           "",
           f"*Certification alignment: see the table at the end of Chapter {n} for how "
           "this maps to associate-level AI-engineering exam domains.*"),
    ]

    return {"cells": cells,
            "metadata": {"colab": {"provenance": []},
                         "kernelspec": {"name": "python3", "display_name": "Python 3"},
                         "language_info": {"name": "python"}},
            "nbformat": 4, "nbformat_minor": 0}



def build_capstone() -> dict:
    """The capstone notebook: same beginner scaffolding, one assembled run."""
    import subprocess
    r = subprocess.run(["python", "-m", "capstone.aegis.system"],
                       capture_output=True, text=True,
                       env={**os.environ, "AEGIS_MODEL": "mock"}, cwd=REPO)
    cap = [l for l in r.stdout.strip().split("\n")] if r.returncode == 0 else []
    T = 5
    cells = [
        md("# \U0001F6E1\uFE0F Aegis \u00B7 Capstone \u2014 The Whole System, Assembled", "",
           "Twelve chapters became twelve capabilities. Here they run as **one** security "
           "agent that catches a hidden attack, investigates, escalates, and files a masked ticket.", "",
           f"{pill('BEGINNER-FRIENDLY','#2FA84F')} &nbsp; {pill('FREE COLAB','#3D7EDB')} &nbsp; {pill('NO API KEY','#8A4FCF')}", "",
           "Paint-by-numbers: click \u25B6\uFE0F on each cell in order, top to bottom.", "",
           progress_bar(0, T, "0 of 5 steps done \u2014 start below")),
        md("![Aegis assembled](../diagrams/Aegis_assembled.svg)", "",
           "*Every box is labeled with the chapter that built it \u2014 the whole book, working together.*", "",
           *callout("why", "The first box \u2014 guarded ingest \u2014 is Chapter 11's defense standing guard before anything else runs.")),
        md(step_banner(1, "Set up the lab", "run these two cells once"), "",
           "Click \u25B6\uFE0F to download the code, then again to install the tested libraries.", "",
           *callout("tip", "A cell is done when the spinner becomes a number like `[1]`.")),
        code('REPO_URL = "https://github.com/<your-org>/<your-repo>.git"',
             "import os, sys, subprocess",
             'if not os.path.isdir("aegis"):',
             '    r = subprocess.run(["git", "clone", REPO_URL, "aegis"], capture_output=True, text=True)',
             "    if r.returncode != 0:",
             '        raise RuntimeError("git clone failed - check REPO_URL above.\\n" + r.stderr)',
             'os.chdir("aegis")',
             'sys.path.insert(0, os.path.abspath("."))',
             "print('Repo ready.')"),
        code("!pip -q install langgraph==1.2.9 langchain-core==1.4.9 mcp==1.28.1 google-adk==2.4.0 pytest",
             "print('Done \u2014 dependencies installed.')"),
        md(*callout("check", "No red error box, and you saw `Done`? Setup complete."), "",
           progress_bar(1, T, "1 of 5 \u2014 setup complete")),
        md(step_banner(2, "Look before you run", "10 seconds", accent="#3D7EDB"), "",
           "Scroll up to the diagram. You're about to watch every box happen in a single run.", "",
           *callout("watch", "The trace names each stage \u2014 match each line to a chapter."), "",
           progress_bar(2, T, "2 of 5 \u2014 oriented")),
        md(step_banner(3, "Run the whole system", "instant, offline", accent="#2FA84F"), "",
           f"{pill('TIER 1: MOCK','#2FA84F')}", "", "Click \u25B6\uFE0F. One hostile incident runs through all twelve chapters."),
        code("import os", "os.environ['AEGIS_MODEL']='mock'", "!AEGIS_MODEL=mock python -m capstone.aegis.system"),
    ]
    if cap:
        cells.append(md(*expected_output(cap), "",
                        *callout("watch", "`guarded_ingest` catches the injection FIRST \u2014 the whole book as one system.")))
    cells += [
        md(*callout("check", "Your trace matches the panel? \U0001F389"), "", progress_bar(3, T, "3 of 5 \u2014 you ran it")),
        md(step_banner(4, "See it on a real model", "optional", accent="#8A4FCF"), "",
           f"{pill('TIER 2: OLLAMA \u2014 FREE','#8A4FCF')}", "", "Replay the same incident on a real model, free, in Colab.", "",
           *callout("tip", "Faster with **Runtime \u25B8 Change runtime type \u25B8 T4 GPU** first.")),
        code("!curl -fsSL https://ollama.com/install.sh | sh",
             "import subprocess, time", "subprocess.Popen(['ollama','serve']); time.sleep(5)",
             "!ollama pull gemma3:4b", "!pip -q install ollama==0.4.7", "print('Real model ready.')"),
        code("os.environ['AEGIS_MODEL']='ollama'", "os.environ['OLLAMA_MODEL']='gemma3:4b'",
             "!AEGIS_MODEL=ollama OLLAMA_MODEL=gemma3:4b python -m capstone.aegis.system"),
        md(*callout("watch", "Wording changes on a real model, but the pipeline still catches the injection and reaches the same verdict shape."), "",
           progress_bar(4, T, "4 of 5 \u2014 real model (optional)")),
        md(step_banner(5, "Prove it works", "the authors' own checks", accent="#F2A900"), "",
           "Click \u25B6\uFE0F to run the capstone tests \u2014 trace order, injection defeat, least-privilege writes."),
        code("!AEGIS_MODEL=mock python -m pytest capstone/tests/ -q"),
        md(*callout("check", "Green `passed`? \U0001F389\U0001F6E1\uFE0F You've run the entire assembled system and verified it."), "",
           *callout("help", "Red or error? Re-run Step 1. Still stuck? See `capstone/LAB_GUIDE.md`."), "",
           progress_bar(5, T, "5 of 5 \u2014 done!")),
        md("---", "**What next?** Appendix D walks this same run stage by stage, and the lab guide's "
           "*Go further* section has three ways to extend Aegis."),
    ]
    return {"cells": cells,
            "metadata": {"colab": {"provenance": []},
                         "kernelspec": {"name": "python3", "display_name": "Python 3"},
                         "language_info": {"name": "python"}},
            "nbformat": 4, "nbformat_minor": 0}

def main():
    made = []
    for ch in CHAPTERS:
        nb = build_notebook(ch)
        n = num(ch["dir"])
        path = os.path.join(REPO, ch["dir"], f"Aegis_Chapter{n}_Colab.ipynb")
        with open(path, "w") as f:
            json.dump(nb, f, indent=1)
        made.append(path)
    cap = build_capstone()
    cap_path = os.path.join(REPO, "capstone", "Aegis_Capstone_Colab.ipynb")
    with open(cap_path, "w") as f:
        json.dump(cap, f, indent=1)
    made.append(cap_path)
    print(f"generated {len(made)} notebooks")
    for p in made:
        print("  ", os.path.relpath(p, REPO))


if __name__ == "__main__":
    main()
