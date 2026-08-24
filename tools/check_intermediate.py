#!/usr/bin/env python3
"""
Execute every intermediate-track snippet for real.

The exercises are only worth anything if they run. This executes each chapter's
`probe`, then `solution` + `check` for every exercise, in one namespace per
exercise (so `check` sees the variables `solution` defined), from the repo root
with AEGIS_MODEL=mock.

    python tools/check_intermediate.py          # run everything, report failures
    python tools/check_intermediate.py 5        # just chapter 5
"""
import io
import os
import sys
import contextlib
import traceback

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
os.environ.setdefault("AEGIS_MODEL", "mock")
from intermediate_labs_data import INTERMEDIATE  # noqa: E402


def run_snippet(src: str, ns: dict) -> tuple[bool, str]:
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf):
            exec(compile(src, "<snippet>", "exec"), ns)
        return True, buf.getvalue()
    except Exception:
        return False, buf.getvalue() + "\n" + traceback.format_exc(limit=2)


def main():
    only = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else None
    os.chdir(REPO)
    failures = []
    ran = 0
    for ch in sorted(INTERMEDIATE):
        if only and ch != only:
            continue
        x = INTERMEDIATE[ch]
        ok, out = run_snippet(x["probe"], {"__name__": "__probe__"})
        ran += 1
        if not ok:
            failures.append((f"ch{ch:02d} probe", out))
        for i, ex in enumerate(x["exercises"], 1):
            ns = {"__name__": "__ex__"}
            ok, out = run_snippet(ex["solution"], ns)
            ran += 1
            if not ok:
                failures.append((f"ch{ch:02d} ex{i} solution", out))
                continue
            ok, out = run_snippet(ex["check"], ns)
            ran += 1
            if not ok:
                failures.append((f"ch{ch:02d} ex{i} check", out))
    print(f"executed {ran} snippets across "
          f"{len([c for c in INTERMEDIATE if not only or c == only])} chapters")
    if failures:
        print(f"\nFAILURES ({len(failures)}):\n")
        for name, out in failures:
            print(f"--- {name} ---")
            print(out.strip()[-700:])
            print()
        sys.exit(1)
    print("OK: every probe, solution, and check runs and passes its assertions")


if __name__ == "__main__":
    main()
