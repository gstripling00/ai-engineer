#!/usr/bin/env python3
"""
Generate the INTERMEDIATE Colab notebook for each chapter.

Different pedagogy from the beginner track (make_notebooks.py):
  * no click-by-click; the reader is assumed to know Colab
  * the chapter's key source file is EMBEDDED and read with an engineer's eye
  * exploration happens IN-PROCESS (import the module, poke the internals),
    not by shelling out to a script
  * exercises are TODO cells with hidden solutions and assertion-based checks —
    the notebook grades itself
  * each chapter ends with a design argument (no single right answer) and a
    challenge (no solution given)

    python tools/make_intermediate_notebooks.py
"""
import json
import os
import sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
sys.path.insert(0, os.path.join(REPO, "instructor"))
from nb_visuals import step_banner, pill, callout   # noqa: E402
from intermediate_labs_data import INTERMEDIATE     # noqa: E402
from chapter_slides_data import CHAPTER_SLIDES, title  # noqa: E402


def md(*lines):
    return {"cell_type": "markdown", "metadata": {}, "source": [l + "\n" for l in lines]}


def code(src: str, collapsed: bool = False):
    meta = {"cellView": "form"} if collapsed else {}
    return {"cell_type": "code", "metadata": meta, "execution_count": None,
            "outputs": [], "source": [l + "\n" for l in src.strip().split("\n")]}


def source_excerpt(ch: int, relpath: str, max_lines: int = 40) -> list[str]:
    """Embed the head of the chapter's key file so the reader reads code, not prose."""
    path = os.path.join(REPO, f"ch{ch:02d}", relpath)
    if not os.path.exists(path):
        return ["*(source not found)*"]
    lines = open(path).read().split("\n")
    # skip the module docstring; start at the first import or def
    start = 0
    for i, l in enumerate(lines):
        if l.startswith(("import ", "from ", "def ", "class ", "@")):
            start = i
            break
    body = lines[start:start + max_lines]
    return ["```python"] + body + ["```"]


def build(ch: int) -> dict:
    d = CHAPTER_SLIDES[ch]
    x = INTERMEDIATE[ch]
    readfile, notice = x["read"]

    cells = [
        md(f"# Aegis · Chapter {ch} — {title(ch)}",
           f"### Intermediate track",
           "",
           f"{pill('INTERMEDIATE', '#8A4FCF')} &nbsp; {pill('IN-PROCESS', '#3D7EDB')} "
           f"&nbsp; {pill('SELF-GRADING', '#2FA84F')}",
           "",
           x["frame"],
           "",
           "**How this track differs.** You won't shell out to demo scripts. You'll import the "
           "chapter's modules, drive them directly, and complete exercises whose assertions grade "
           "themselves. Solutions are one cell below each exercise — resist them until you've "
           "tried.",
           "",
           f"*Prerequisite: the Chapter {ch} beginner notebook, or equivalent comfort with the "
           f"chapter's demo.*"),

        md(step_banner(0, "Setup", "pinned deps, one cell", accent="#6B7885")),
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

        md(step_banner(1, "Read the implementation", "before you run anything", accent="#3D7EDB"),
           "",
           f"**`ch{ch:02d}/{readfile}`** — what to notice: {notice}",
           "",
           *source_excerpt(ch, readfile),
           "",
           *callout("why", d["beat"])),

        md(step_banner(2, "Probe it in-process", "drive the module yourself", accent="#8A4FCF"),
           "",
           "Not a script invocation — the chapter's own objects, in your kernel, printing their "
           "internals."),
        code(x["probe"]),
    ]

    for i, ex in enumerate(x["exercises"], 1):
        cells += [
            md(step_banner(2 + i, f"Exercise {i}", "your turn", accent="#F2A900"),
               "",
               ex["prompt"]),
            code(ex["starter"]),
            md("<details><summary>💡 <b>Solution</b> (open only after trying)</summary>\n\n"
               "Run the cell below to see one working answer.\n\n</details>"),
            code(ex["solution"]),
            md("**Check your work** — this cell asserts; a green run means you're right."),
            code(ex["check"]),
        ]

    last = 2 + len(x["exercises"])
    cells += [
        md(step_banner(last + 1, "Verify against the suite", "the authors' own tests",
                       accent="#2FA84F")),
        code(f'!cd ch{ch:02d} && AEGIS_MODEL=mock python -m pytest tests/ -q'),

        md(step_banner(last + 2, "The argument worth having", "no single right answer",
                       accent="#E5484D"),
           "",
           x["design"],
           "",
           *callout("why", "Intermediate practitioners are separated from beginners by which "
                    "tradeoffs they can *argue*, not which APIs they can call. Write your answer "
                    "in the cell below — the act of writing it is the exercise.")),
        {"cell_type": "markdown", "metadata": {},
         "source": ["_Your answer:_\n", "\n", "> \n"]},

        md("## Challenge (no solution provided)",
           "",
           x["challenge"],
           "",
           *callout("tip", "If you build it, the chapter's test suite is your acceptance "
                    "criteria — extend it rather than replacing it."),
           "",
           "---",
           f"*Next: Chapter {ch + 1}'s intermediate notebook, or the capstone, where every "
           f"chapter's component runs as one system.*" if ch < 12 else
           "*Next: the capstone — every chapter's component, assembled into one system.*"),
    ]

    return {"cells": cells,
            "metadata": {"colab": {"provenance": []},
                         "kernelspec": {"name": "python3", "display_name": "Python 3"},
                         "language_info": {"name": "python"}},
            "nbformat": 4, "nbformat_minor": 0}


def main():
    made = []
    for ch in range(1, 13):
        nb = build(ch)
        path = os.path.join(REPO, f"ch{ch:02d}", f"Aegis_Chapter{ch}_Colab_Intermediate.ipynb")
        with open(path, "w") as f:
            json.dump(nb, f, indent=1)
        made.append(os.path.relpath(path, REPO))
    print(f"generated {len(made)} intermediate notebooks")
    for p in made:
        print("  ", p)


if __name__ == "__main__":
    main()
