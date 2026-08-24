#!/usr/bin/env python3
"""
Generate the ADVANCED Colab notebook for each chapter.

The contract: a spec and a FAILING acceptance test. You implement until it goes
green. Structure per chapter:

  0  Setup
  1  Where this breaks      — the book's own implementation, criticized honestly
  2  Measure it             — a benchmark that produces numbers to argue with
  3  Build it               — spec, stub, and the acceptance test (run it: it fails)
  4  Reference              — one correct implementation, collapsed
  5  Break it               — adversarial probe against what you just built
  6  Production review      — the analysis a staff engineer is asked for

    python tools/make_advanced_notebooks.py
"""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
sys.path.insert(0, os.path.join(REPO, "instructor"))
from nb_visuals import step_banner, pill, callout       # noqa: E402
from advanced_labs_data import ADVANCED                 # noqa: E402
from chapter_slides_data import CHAPTER_SLIDES, title, failure_modes  # noqa: E402


def md(*lines):
    return {"cell_type": "markdown", "metadata": {}, "source": [l + "\n" for l in lines]}


def code(src: str):
    return {"cell_type": "code", "metadata": {}, "execution_count": None,
            "outputs": [], "source": [l + "\n" for l in src.strip().split("\n")]}


def build(ch: int) -> dict:
    x = ADVANCED[ch]
    fms = failure_modes(ch)

    cells = [
        md(f"# Aegis · Chapter {ch} — {title(ch)}",
           "### Advanced track",
           "",
           f"{pill('ADVANCED', '#E5484D')} &nbsp; {pill('SPEC + TESTS', '#3D7EDB')} "
           f"&nbsp; {pill('YOU IMPLEMENT', '#F2A900')}",
           "",
           "**The contract.** You get a spec and a failing acceptance test. You implement until "
           "it goes green. A reference implementation is provided — collapsed, and it is *one* "
           "answer, not the answer. The test is the contract.",
           "",
           "Every acceptance test in this track is verified in CI to **fail against the stub and "
           "pass against the reference** — so none of them are vacuous. If yours goes green, you "
           "built the thing.",
           "",
           f"*Assumes the Chapter {ch} intermediate notebook, or equivalent fluency with the "
           f"chapter's internals.*"),

        md(step_banner(0, "Setup", "pinned, terse", accent="#6B7885")),
        code('''# Set this to the book's companion repository, then run.
REPO_URL = "https://github.com/<your-org>/<your-repo>.git"

import os, sys, subprocess

if not os.path.isdir("aegis"):
    r = subprocess.run(["git", "clone", REPO_URL, "aegis"], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError("git clone failed - check REPO_URL above.\\n" + r.stderr)

os.chdir("aegis")
sys.path.insert(0, os.path.abspath("."))
!pip -q install langgraph==1.2.9 langchain-core==1.4.9 mcp==1.28.1 google-adk==2.4.0 pytest
os.environ["AEGIS_MODEL"] = "mock"
print("ready:", os.getcwd())'''),

        md(step_banner(1, "Where this breaks", "the book, criticized honestly", accent="#E5484D"),
           "",
           x["limits"],
           "",
           *callout("why", "Every chapter of this book ships a deliberate simplification. Finding "
                    "them is not a gotcha — it's the transition from following a book to owning a "
                    "system.")),

        md(step_banner(2, "Measure it", "numbers you can argue with", accent="#3D7EDB"),
           "",
           "Before you fix anything, quantify it. Run this and read the numbers — they're the "
           "evidence for the design decision you're about to make."),
        code(x["benchmark"]),

        md(step_banner(3, "Build it", "spec first, then the failing test", accent="#F2A900"),
           "",
           "### Spec",
           "",
           x["spec"],
           "",
           *callout("watch", "Run the acceptance cell *before* you implement. Watching it fail is "
                    "how you know it's actually testing something.")),
        code(x["stub"]),
        md("**The acceptance test.** Run it now — it should fail. Then implement above until it "
           "passes. Do not modify this cell."),
        code(x["acceptance"]),

        md(step_banner(4, "Reference implementation", "one answer, not the answer",
                       accent="#8A4FCF"),
           "",
           "<details><summary>🔍 <b>Open only after you've made the test pass — or genuinely "
           "stuck</b></summary>\n\n"
           "Run the cell below to load a reference implementation, then re-run the acceptance "
           "test above.\n\n</details>",
           "",
           *callout("tip", "If your implementation passes and looks nothing like this one, that's "
                    "a good sign — compare the tradeoffs rather than the syntax.")),
        code(x["reference"]),

        md(step_banner(5, "Break it", "adversarial probe on what you just built",
                       accent="#E5484D"),
           "",
           "You built a control. Now attack it. The point is not that it fails — it's that you "
           "know *how* it fails before an attacker does."),
        code(x["adversarial"]),

        md(step_banner(6, "Production review", "the question you'd be asked", accent="#2FA84F"),
           "",
           x["production"],
           "",
           *callout("why", "Staff-level work is not writing the control. It's defending the "
                    "control's limits, in a room, to people who will be paged when it fails."),
           "",
           "_Your answer:_",
           "",
           "> "),
    ]

    if fms:
        cells.append(md("## Known failure modes for this chapter",
                        "",
                        "*From Appendix F — the ones the authors hit. Your implementation should "
                        "survive them.*",
                        "",
                        *[f"- **{fm['title']}** — *symptom:* {fm['symptom']} *Fix:* "
                          f"{fm['mitigation']}" for fm in fms]))

    cells.append(
        md("---",
           "**Verify against the suite.** Your changes must not break the chapter's own tests.",
           ""))
    cells.append(code(f'!cd ch{ch:02d} && AEGIS_MODEL=mock python -m pytest tests/ -q'))
    cells.append(
        md("---",
           f"*Next: Chapter {ch + 1}'s advanced notebook.*" if ch < 12 else
           "*You've finished the advanced track. The capstone assembles every component — "
           "extend it with what you built here.*"))

    return {"cells": cells,
            "metadata": {"colab": {"provenance": []},
                         "kernelspec": {"name": "python3", "display_name": "Python 3"},
                         "language_info": {"name": "python"}},
            "nbformat": 4, "nbformat_minor": 0}


def main():
    made = []
    for ch in range(1, 13):
        nb = build(ch)
        path = os.path.join(REPO, f"ch{ch:02d}", f"Aegis_Chapter{ch}_Colab_Advanced.ipynb")
        with open(path, "w") as f:
            json.dump(nb, f, indent=1)
        made.append(os.path.relpath(path, REPO))
    print(f"generated {len(made)} advanced notebooks")
    for p in made:
        print("  ", p)


if __name__ == "__main__":
    main()
