#!/usr/bin/env python3
"""Validate every generated notebook: valid JSON, beginner scaffolding present,
pinned deps, and (for chapter notebooks) an expected-output panel."""
import glob, json, os, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
errs = []
nbs = sorted(glob.glob(os.path.join(REPO, "ch*/Aegis_Chapter*_Colab.ipynb")))
nbs.append(os.path.join(REPO, "capstone/Aegis_Capstone_Colab.ipynb"))
INTERMEDIATE_NBS = sorted(glob.glob(os.path.join(REPO, "ch*/Aegis_Chapter*_Colab_Intermediate.ipynb")))
ADVANCED_NBS = sorted(glob.glob(os.path.join(REPO, "ch*/Aegis_Chapter*_Colab_Advanced.ipynb")))
for p in nbs:
    rel = os.path.relpath(p, REPO)
    if not os.path.exists(p):
        errs.append(f"{rel}: missing"); continue
    try:
        nb = json.load(open(p))
    except Exception as e:
        errs.append(f"{rel}: invalid JSON ({e})"); continue
    if nb.get("nbformat") != 4:
        errs.append(f"{rel}: nbformat != 4")
    src = "\n".join("".join(c["source"]) for c in nb["cells"])
    for need, label in [("data:image/svg+xml", "SVG step banners"),
                        ("![progress]", "progress bars"),
                        ("Checkpoint", "checkpoint callouts"),
                        ("git clone", "clone cell"),
                        ("google-adk==2.4.0", "ADK 2.4.0 pin"),
                        ("You should see", "expected-output panel")]:
        if need not in src:
            errs.append(f"{rel}: missing {label}")
# --- intermediate track: different scaffolding, different requirements ---
if len(INTERMEDIATE_NBS) != 12:
    errs.append(f"expected 12 intermediate notebooks, found {len(INTERMEDIATE_NBS)}")
for p in INTERMEDIATE_NBS:
    rel = os.path.relpath(p, REPO)
    try:
        nb = json.load(open(p))
    except Exception as e:
        errs.append(f"{rel}: invalid JSON ({e})"); continue
    src_all = "\n".join("".join(c["source"]) for c in nb["cells"])
    for need, label in [("Exercise 1", "exercises"),
                        ("<details><summary>", "collapsible solutions"),
                        ("Check your work", "self-grading checks"),
                        ("assert ", "assertions"),
                        ("Challenge", "challenge section"),
                        ("google-adk==2.4.0", "ADK 2.4.0 pin")]:
        if need not in src_all:
            errs.append(f"{rel}: missing {label}")

# --- advanced track: spec + failing acceptance test ---
if len(ADVANCED_NBS) != 12:
    errs.append(f"expected 12 advanced notebooks, found {len(ADVANCED_NBS)}")
for p in ADVANCED_NBS:
    rel = os.path.relpath(p, REPO)
    try:
        nb = json.load(open(p))
    except Exception as e:
        errs.append(f"{rel}: invalid JSON ({e})"); continue
    src_all = "\n".join("".join(c["source"]) for c in nb["cells"])
    for need, label in [("Where this breaks", "limits section"),
                        ("Measure it", "benchmark section"),
                        ("### Spec", "spec"),
                        ("NotImplementedError", "stub"),
                        ("ACCEPTANCE", "acceptance test"),
                        ("Break it", "adversarial section"),
                        ("Production review", "production analysis"),
                        ("google-adk==2.4.0", "ADK 2.4.0 pin")]:
        if need not in src_all:
            errs.append(f"{rel}: missing {label}")

if errs:
    print("NOTEBOOK VALIDATION FAILED:")
    for e in errs:
        print("  -", e)
    sys.exit(1)
print(f"OK: {len(nbs)} beginner (12 chapters + capstone) + {len(INTERMEDIATE_NBS)} intermediate "
      f"+ {len(ADVANCED_NBS)} advanced notebooks = {len(nbs) + len(INTERMEDIATE_NBS) + len(ADVANCED_NBS)} total, "
      f"all scaffolding present")
