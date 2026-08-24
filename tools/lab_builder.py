"""
Shared scaffolding for the canonical *_Lab.ipynb track.

Every chapter's lab notebook opens the same way, and that opening is the
production-mirroring contract:

  * ONE requirements.txt. No notebook pins anything itself. Change a version in
    that file and it changes for every lab, every chapter, and CI.
  * The clone FAILS LOUDLY. No `|| echo`; a failed clone raises immediately
    rather than surfacing as a confusing ModuleNotFoundError three cells later.
  * check_env.py runs before any lab code, so a broken environment announces
    itself with the fix rather than a stack trace.
  * Secrets come from the environment. Never a literal key in a committed cell.

No icons, no emoji, no images — plain markdown and code.
"""

REPO_PLACEHOLDER = "https://github.com/<your-org>/<your-repo>.git"


def md(*lines):
    return {"cell_type": "markdown", "metadata": {},
            "source": [l + "\n" for l in lines]}


def code(src: str, tags: list | None = None):
    meta = {"tags": tags} if tags else {}
    return {"cell_type": "code", "metadata": meta, "execution_count": None,
            "outputs": [], "source": [l + "\n" for l in src.strip().split("\n")]}


def setup_cells(chapter: int) -> list:
    """The identical opening of every lab notebook."""
    return [
        md("## Setup",
           "",
           "Every lab in this book installs from **one** `requirements.txt` in the companion",
           "repository. No notebook pins its own versions: change a dependency there and it",
           "changes everywhere, including CI. That is how the labs mirror a production",
           "service rather than a pile of scratch files.",
           "",
           "The clone below fails loudly on purpose. A setup step that swallows its own",
           "error surfaces later as a confusing `ModuleNotFoundError`, and you waste an hour",
           "looking in the wrong place."),
        code(f'''REPO_URL = "{REPO_PLACEHOLDER}"

import os, sys, subprocess

if not os.path.isdir("aegis"):
    result = subprocess.run(["git", "clone", REPO_URL, "aegis"],
                            capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("git clone failed - check REPO_URL above.\\n" + result.stderr)

os.chdir("aegis")
sys.path.insert(0, os.path.abspath("."))
print("repo:", os.getcwd())''', tags=["setup"]),
        code('''!pip -q install -r requirements.txt''', tags=["setup"]),
        md("Now verify the environment before running any lab code. This is the same check CI",
           "runs, and it catches the one dependency conflict that would otherwise waste your",
           "afternoon."),
        code('''!python tools/check_env.py''', tags=["setup"]),
        md("### Choosing a model tier",
           "",
           "The labs read `AEGIS_MODEL` and swap the model behind a single seam:",
           "",
           "| Tier | Cost | Determinism | Use it for |",
           "|---|---|---|---|",
           "| `mock` | free, no key | identical every run | learning the control flow; the test suite; CI |",
           "| `openai` | billed per call | varies run to run | seeing a real model make these decisions |",
           "",
           "Start on `mock`. Everything in this chapter runs there. When you switch to",
           "`openai`, the code does not change — only the seam does.",
           "",
           "Set the key from the environment, never as a literal in a cell. In Colab use the",
           "key icon in the sidebar (Secrets); the cell below reads it without printing it."),
        code('''import os

os.environ["AEGIS_MODEL"] = "mock"     # free, deterministic, no key

# To use a real model instead, uncomment these two lines:
# from getpass import getpass
# os.environ["OPENAI_API_KEY"] = getpass("OPENAI_API_KEY: "); os.environ["AEGIS_MODEL"] = "openai"

print("model tier:", os.environ["AEGIS_MODEL"])''', tags=["setup"]),
    ]


def build(chapter: int, title: str, intro_cells: list, body_cells: list,
          closing_cells: list) -> dict:
    cells = intro_cells + setup_cells(chapter) + body_cells + closing_cells
    return {"cells": cells,
            "metadata": {"colab": {"provenance": []},
                         "kernelspec": {"name": "python3", "display_name": "Python 3"},
                         "language_info": {"name": "python"}},
            "nbformat": 4, "nbformat_minor": 0}
