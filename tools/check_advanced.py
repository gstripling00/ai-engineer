#!/usr/bin/env python3
"""
Verify the ADVANCED track — including that the tests have teeth.

For every chapter:
  1. `benchmark`   must run.
  2. `stub` + `acceptance` must FAIL. (A test that passes against a
     NotImplementedError stub is vacuous — it would grade nothing. This check is
     the whole reason the file exists.)
  3. `reference` + `acceptance` must PASS.
  4. `adversarial` must run (against the reference).

    python tools/check_advanced.py        # all chapters
    python tools/check_advanced.py 7      # one chapter
"""
import contextlib
import io
import os
import sys
import traceback

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(REPO, "tools"))
os.environ.setdefault("AEGIS_MODEL", "mock")
from advanced_labs_data import ADVANCED  # noqa: E402


def run(src: str, ns: dict) -> tuple[bool, str]:
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
    failures, checked = [], 0

    for ch in sorted(ADVANCED):
        if only and ch != only:
            continue
        x = ADVANCED[ch]

        ok, out = run(x["benchmark"], {"__name__": "__bench__"})
        checked += 1
        if not ok:
            failures.append((f"ch{ch:02d} benchmark did not run", out))

        # 2. the test must have teeth: stub + acceptance MUST fail
        ns = {"__name__": "__stub__"}
        ok_stub, _ = run(x["stub"], ns)
        if not ok_stub:
            failures.append((f"ch{ch:02d} stub did not even load", _))
        else:
            ok_acc, _ = run(x["acceptance"], ns)
            checked += 1
            if ok_acc:
                failures.append(
                    (f"ch{ch:02d} VACUOUS TEST",
                     "acceptance PASSED against the unimplemented stub — it grades nothing"))

        # 3. reference + acceptance must pass
        ns = {"__name__": "__ref__"}
        ok_ref, out = run(x["reference"], ns)
        checked += 1
        if not ok_ref:
            failures.append((f"ch{ch:02d} reference failed to load", out))
            continue
        ok_acc, out = run(x["acceptance"], ns)
        checked += 1
        if not ok_acc:
            failures.append((f"ch{ch:02d} acceptance FAILED against the reference", out))
            continue

        # 4. adversarial runs against the reference namespace
        ok_adv, out = run(x["adversarial"], ns)
        checked += 1
        if not ok_adv:
            failures.append((f"ch{ch:02d} adversarial did not run", out))

    n_ch = len([c for c in ADVANCED if not only or c == only])
    print(f"checked {checked} snippets across {n_ch} chapters")
    if failures:
        print(f"\nFAILURES ({len(failures)}):\n")
        for name, out in failures:
            print(f"--- {name} ---")
            print(out.strip()[-700:])
            print()
        sys.exit(1)
    print("OK: every benchmark runs; every acceptance test FAILS on the stub and "
          "PASSES on the reference; every adversarial probe runs")


if __name__ == "__main__":
    main()
