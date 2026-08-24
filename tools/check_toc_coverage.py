#!/usr/bin/env python3
"""
TOC coverage validator — EXECUTION-BASED.

The rule (and the reason this file was rewritten):

    A claim counts as COVERED only if a cell EXECUTES and PRINTS something a
    reader can check against the claim.

Token presence in the source is necessary but NOT sufficient. A notebook can
contain the string `route_with_confidence` in a comment and satisfy a grep; it
cannot print `confident=False reason=below_score_threshold` unless the code
really ran. So every claim declares `expect_output` — substrings that must appear
in captured stdout — and the validator runs the notebook to get them.

Three verdicts per claim:

    executed      cell ran; expected evidence found in its output   <- the bar
    prose-only    tokens in source, but no executed evidence        <- FAILS
    documented    honestly cannot run offline; reason recorded      <- allowed

    python tools/check_toc_coverage.py            # all built chapters
    python tools/check_toc_coverage.py 3          # one chapter
    python tools/check_toc_coverage.py --report   # full table
"""
import contextlib
import io
import json
import os
import sys
import traceback

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
from toc_claims import CLAIMS                      # noqa: E402

NB = "ch{n:02d}/Aegis_Chapter{n}_Lab.ipynb"
NB_OVERRIDE = {13: "capstone/Aegis_Chapter13_Lab.ipynb"}   # the capstone is not a chNN dir


def _nb_path(ch: int) -> str:
    return NB_OVERRIDE.get(ch, NB.format(n=ch))


def _is_shell(src: str) -> bool:
    return any(l.strip().startswith("!") for l in src.split("\n"))


def run_notebook(ch: int) -> tuple[str, str, list]:
    """Execute a lab notebook's Python cells from the repo root.

    Returns (source_text, captured_stdout, errors). Shell cells (installs,
    clones) are skipped — they are environment setup, never claim evidence.
    """
    path = os.path.join(REPO, _nb_path(ch))
    if not os.path.exists(path):
        return "", "", [f"notebook not built: {_nb_path(ch)}"]

    nb = json.load(open(path))
    source = "\n".join("".join(c["source"]) for c in nb["cells"])

    cwd = os.getcwd()
    os.chdir(REPO)
    if REPO not in sys.path:
        sys.path.insert(0, REPO)
    os.environ.setdefault("AEGIS_MODEL", "mock")

    ns = {"__name__": "__main__"}
    out, errors = [], []
    try:
        for i, cell in enumerate(nb["cells"]):
            if cell["cell_type"] != "code":
                continue
            tags = cell.get("metadata", {}).get("tags", [])
            if "setup" in tags:
                continue                      # environment setup, never claim evidence
            if "needs_api_key" in tags:
                continue                      # requires a paid key; see documented-not-demonstrated
            src = "".join(cell["source"])
            if _is_shell(src):
                continue
            buf = io.StringIO()
            try:
                with contextlib.redirect_stdout(buf):
                    exec(compile(src, f"ch{ch}_cell{i}", "exec"), ns)
                out.append(buf.getvalue())
            except Exception:
                errors.append(f"cell {i} raised: {traceback.format_exc(limit=2)}")
                out.append(buf.getvalue())
    finally:
        os.chdir(cwd)

    return source, "\n".join(out), errors


def _run_isolated(ch: int) -> tuple[str, str, list]:
    """Execute one chapter's notebook in a FRESH interpreter.

    Running every chapter in one process was giving order-dependent results:
    a `common` package imported by chapter 7 stayed in sys.modules and shadowed
    chapter 8's own `common`. A reader gets a fresh Colab kernel per notebook,
    so the verifier must match that or it is not verifying what ships.
    """
    import subprocess
    proc = subprocess.run(
        [sys.executable, os.path.abspath(__file__), "--_isolated", str(ch)],
        capture_output=True, text=True, cwd=REPO)
    try:
        payload = json.loads(proc.stdout)
    except json.JSONDecodeError:
        return "", "", [f"isolated run failed: {proc.stderr[-300:]}"]
    return payload["source"], payload["output"], payload["errors"]


def check(ch: int) -> dict:
    source, output, errors = _run_isolated(ch)
    lowered_src, lowered_out = source.lower(), output.lower()

    executed, prose_only, documented, missing = [], [], [], []

    for claim in CLAIMS[ch]:
        if claim.get("documented_not_demonstrated"):
            documented.append(claim)
            continue

        absent_tokens = [t for t in claim["must_contain"] if t.lower() not in lowered_src]
        expected = claim.get("expect_output", [])
        absent_output = [e for e in expected if e.lower() not in lowered_out]

        if absent_tokens:
            missing.append({**claim, "why": f"tokens absent from source: {absent_tokens}"})
        elif not expected:
            prose_only.append({**claim,
                               "why": "no expect_output declared — cannot verify by execution"})
        elif absent_output:
            prose_only.append({**claim,
                               "why": f"expected output not printed: {absent_output}"})
        else:
            executed.append(claim)

    return {"chapter": ch, "executed": executed, "prose_only": prose_only,
            "documented": documented, "missing": missing, "errors": errors}


def main():
    args = sys.argv[1:]

    if args and args[0] == "--_isolated":          # internal: one chapter, fresh process
        source, output, errors = run_notebook(int(args[1]))
        print(json.dumps({"source": source, "output": output, "errors": errors}))
        return

    only = int(args[0]) if args and args[0].isdigit() else None
    report = "--report" in args

    chapters = [only] if only else sorted(CLAIMS)
    built = [c for c in chapters
             if os.path.exists(os.path.join(REPO, _nb_path(c)))]
    if not built:
        print("no lab notebooks built yet")
        return

    failed = False
    tot_exec = tot_doc = tot_bad = 0

    for ch in built:
        r = check(ch)
        tot_exec += len(r["executed"])
        tot_doc += len(r["documented"])
        bad = r["prose_only"] + r["missing"]
        tot_bad += len(bad)

        n = len(r["executed"]) + len(bad) + len(r["documented"])
        status = "OK " if not bad and not r["errors"] else "FAIL"
        print(f"{status} Ch{ch:2d}  executed {len(r['executed'])}/{n}"
              + (f"   documented-not-demonstrated {len(r['documented'])}"
                 if r["documented"] else ""))

        if report:
            for c in r["executed"]:
                print(f"       executed    {c['toc']:9} {c['claim'][:58]}")
        for c in r["documented"]:
            print(f"       documented  {c['toc']:9} {c['claim'][:58]}")
            print(f"                   reason: {c['documented_not_demonstrated']}")
        for c in bad:
            print(f"       NOT COVERED {c['toc']:9} {c['claim'][:58]}")
            print(f"                   {c['why']}")
        for e in r["errors"]:
            print(f"       ERROR {e.splitlines()[0]}")

        if bad or r["errors"]:
            failed = True

    print(f"\n{tot_exec} executed · {tot_doc} documented-not-demonstrated · "
          f"{tot_bad} not covered   ({len(built)}/{len(CLAIMS)} chapters built)")

    if failed:
        print("\nCOVERAGE FAILED — a claim is covered only when a cell RUNS and PRINTS the evidence.")
        sys.exit(1)


if __name__ == "__main__":
    main()
