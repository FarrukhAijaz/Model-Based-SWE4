#!/usr/bin/env python3
"""
validate_pipeline.py
====================
Connects to a shared MATLAB Engine session and invokes test_automation()
against SimulinkSample.slx + sample_test_data.xlsx.

Prerequisites
-------------
1. MATLAB must be running with a *shared session*:
       >> matlab.engine.shareEngine('AutoTestSession')
   or just:
       >> matlab.engine.shareEngine

2. The matlabengine Python package must be installed:
       pip install matlabengine

Usage
-----
    python validate_pipeline.py

The script will:
  - Connect to the first available shared MATLAB Engine
  - Call test_automation(modelPath, excelPath, outputDir)
  - Print the returned results struct as formatted JSON
"""

import json
import os
import sys
import time
from pathlib import Path

# Attempt to import MATLAB Engine
try:
    import matlab.engine
except ImportError:
    print("ERROR: matlabengine package not installed.")
    print("Install with:  pip install matlabengine")
    print("(Requires MATLAB R2022b+ on your PATH)")
    sys.exit(1)


ROOT_DIR = Path(__file__).resolve().parent
MODEL_PATH = ROOT_DIR / "SimulinkSample.slx"
EXCEL_PATH = ROOT_DIR / "sample_test_data.xlsx"
OUTPUT_DIR = ROOT_DIR / "test_output_python"
SCRIPTS_DIR = ROOT_DIR / "backend" / "matlab_scripts"


def main():
    # ── Validate files exist ────────────────────────────────────────────
    for label, p in [("Model", MODEL_PATH), ("Excel", EXCEL_PATH)]:
        if not p.exists():
            print(f"ERROR: {label} not found: {p}")
            sys.exit(1)
    print(f"  Model : {MODEL_PATH}")
    print(f"  Excel : {EXCEL_PATH}")
    print(f"  Output: {OUTPUT_DIR}")
    print()

    # ── Connect to MATLAB Engine ────────────────────────────────────────
    print("Discovering shared MATLAB Engine sessions...")
    sessions = matlab.engine.find_matlab()
    if not sessions:
        print("No shared MATLAB sessions found.")
        print("Start a shared session in MATLAB with:")
        print("    >> matlab.engine.shareEngine('AutoTestSession')")
        sys.exit(1)
    print(f"  Found sessions: {sessions}")
    session_name = sessions[0]
    print(f"  Connecting to '{session_name}'...")
    eng = matlab.engine.connect_matlab(session_name)
    print("  Connected!\n")

    # ── Prepare ─────────────────────────────────────────────────────────
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    eng.addpath(str(SCRIPTS_DIR), nargout=0)

    # Build options struct in MATLAB workspace
    eng.eval("validationOpts = struct();", nargout=0)
    eng.eval("validationOpts.cleanupHarness = false;", nargout=0)
    eng.eval("validationOpts.cleanupTestFile = false;", nargout=0)

    # ── Run pipeline ────────────────────────────────────────────────────
    print("=" * 60)
    print("  Running test_automation() ...")
    print("=" * 60)
    t0 = time.time()

    try:
        eng.eval(
            f"validationResults = test_automation("
            f"'{str(MODEL_PATH)}', "
            f"'{str(EXCEL_PATH)}', "
            f"'{str(OUTPUT_DIR)}', "
            f"validationOpts);",
            nargout=0,
        )
    except Exception as e:
        print(f"\n!!! MATLAB error:\n{e}")
        sys.exit(1)

    elapsed = time.time() - t0
    print(f"\n  Completed in {elapsed:.1f}s\n")

    # ── Extract results as JSON ─────────────────────────────────────────
    print("Extracting results...")
    try:
        eng.eval("validationJSON = jsonencode(validationResults);", nargout=0)
        results_json = eng.workspace["validationJSON"]
        results = json.loads(results_json)
    except Exception as e:
        print(f"  Could not extract results as JSON: {e}")
        # Try to at least get the success flag
        try:
            success = eng.eval("validationResults.success", nargout=1)
            print(f"  success = {success}")
        except Exception:
            pass
        return

    # ── Pretty-print results ────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  VALIDATION RESULTS")
    print("=" * 60)
    print(json.dumps(results, indent=2, default=str))

    # ── Summary ─────────────────────────────────────────────────────────
    print("\n" + "=" * 60)
    print("  SUMMARY")
    print("=" * 60)

    success = results.get("success", False)
    print(f"  Success: {success}")

    if not success:
        print(f"  Error: {results.get('error', 'unknown')}")
        return

    phases = results.get("phases", {})

    # Analysis
    analysis = phases.get("analysis", {})
    inputs = analysis.get("inputs", [])
    outputs = analysis.get("outputs", [])
    if isinstance(inputs, list):
        print(f"  Inputs:  {', '.join(i.get('name', '?') for i in inputs)}")
    if isinstance(outputs, list):
        print(f"  Outputs: {', '.join(o.get('name', '?') for o in outputs)}")

    # Execution
    execution = phases.get("execution", {})
    print(f"  Overall: {execution.get('overallOutcome', 'N/A')}")
    outcomes = execution.get("caseOutcomes", [])
    if outcomes:
        for item in outcomes:
            if isinstance(item, list) and len(item) >= 2:
                print(f"    {item[0]} → {item[1]}")

    # Coverage
    coverage = phases.get("coverage", {})
    print(f"  Coverage available: {coverage.get('available', False)}")
    if coverage.get("reportPath"):
        print(f"  Coverage report:   {coverage['reportPath']}")

    # Export
    export = phases.get("export", {})
    if export.get("excelPath"):
        print(f"  Results Excel:     {export['excelPath']}")

    print(f"\n  Artifacts in: {OUTPUT_DIR}")
    print("=" * 60)


if __name__ == "__main__":
    main()
