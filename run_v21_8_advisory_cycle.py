#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WNBA Edge Lab - V21.8 Advisory Cycle

Runs:
1. ultimate_fetcher_v21_4_1.py
2. feature_builder_v21.py
3. feature_diagnostics_v21.py
4. signal_execution_bridge_v20_1.py
5. hermes_state_builder_v20_1.py
6. model_audit_v20.py
7. model_upgrade_recommender_v21.py
8. model_backtester_v21_2.py
9. model_advisory_scoring_v21.py

Safe:
- no auto-betting
- no formula changes
- no staking changes
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

import pandas as pd


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "wnba_outputs"

STEPS = [
    ("Ultimate Fetcher V21.4.1", "ultimate_fetcher_v21_4_1.py"),
    ("Feature Builder V21", "feature_builder_v21.py"),
    ("Feature Diagnostics V21", "feature_diagnostics_v21.py"),
    ("Signal-to-Execution Bridge", "signal_execution_bridge_v20_1.py"),
    ("Hermes State Builder", "hermes_state_builder_v20_1.py"),
    ("Model Audit", "model_audit_v20.py"),
    ("Model Upgrade Recommender V21", "model_upgrade_recommender_v21.py"),
    ("Model Backtester V21.2", "model_backtester_v21_2.py"),
    ("Model Advisory Scoring V21", "model_advisory_scoring_v21.py"),
]


def safe_print(text=""):
    try:
        print(text)
    except UnicodeEncodeError:
        print(str(text).encode("ascii", "replace").decode("ascii"))


def load_json(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def row_count(path: Path) -> int:
    try:
        if path.exists():
            return int(pd.read_csv(path, low_memory=False).shape[0])
    except Exception:
        pass
    return 0


def run_step(name: str, script: str, args: List[str]) -> Dict[str, Any]:
    path = ROOT / script
    start = time.time()
    if not path.exists():
        return {"name": name, "script": script, "ok": False, "seconds": 0, "stdout": "", "stderr": f"Missing script: {script}", "returncode": 1}
    p = subprocess.run([sys.executable, str(path)] + args, cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace")
    return {"name": name, "script": script, "ok": p.returncode == 0, "seconds": round(time.time() - start, 2), "stdout": p.stdout.strip(), "stderr": p.stderr.strip(), "returncode": p.returncode}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--seasons", default="2025,2026")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--features", action="store_true")
    parser.add_argument("--props", action="store_true")
    parser.add_argument("--skip-sdv", action="store_true")
    parser.add_argument("--all-sdv-assets", action="store_true")
    args = parser.parse_args()

    safe_print("=" * 72)
    safe_print(" WNBA EDGE LAB - V21.8 ADVISORY CYCLE")
    safe_print("=" * 72)
    safe_print(f"Root: {ROOT}")
    safe_print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    safe_print("Fetcher: ultimate_fetcher_v21_4_1.py")
    safe_print("Safety: no auto-betting, no formula changes, no staking changes")
    safe_print("")

    results = []
    failed = False

    for name, script in STEPS:
        step_args = []
        if script == "ultimate_fetcher_v21_4_1.py":
            step_args += ["--seasons", args.seasons, "--season", str(args.season)]
            if args.features:
                step_args.append("--features")
            if args.props:
                step_args.append("--props")
            if args.skip_sdv:
                step_args.append("--skip-sdv")
            if args.all_sdv_assets:
                step_args.append("--all-sdv-assets")

        res = run_step(name, script, step_args)
        results.append(res)

        safe_print(f"[{'OK' if res['ok'] else 'FAILED'}] {name} ({res['seconds']}s)")
        if res["stdout"]:
            for line in res["stdout"].splitlines()[-12:]:
                safe_print(f"      {line}")
        if res["stderr"]:
            safe_print("      stderr:")
            for line in res["stderr"].splitlines()[-8:]:
                safe_print(f"        {line}")

        if not res["ok"]:
            failed = True
            break

    fetch = load_json(OUT / "ultimate_fetch_status_v21_4.json")
    feature_summary = load_json(OUT / "feature_builder_summary_v21.json")
    backtest = load_json(OUT / "model_backtest_summary_v21.json")
    advisory = load_json(OUT / "model_advisory_summary_v21.json")
    hermes = load_json(OUT / "hermes_state_v20.json")

    summary = {
        "created_at": datetime.now().isoformat(),
        "status": "FAILED" if failed else "OK",
        "fetch_state": fetch.get("overall_state", "unknown"),
        "fetch_readiness": fetch.get("readiness", {}),
        "feature_rows": feature_summary.get("rows", {}),
        "backtest_rows": backtest.get("rows", {}),
        "candidate_status_counts": backtest.get("candidate_status_counts", {}),
        "advisory_rows": advisory.get("rows", {}),
        "advisory_labels": advisory.get("label_counts", {}),
        "advisory_risk_flags": advisory.get("risk_flag_counts", {}),
        "mode": hermes.get("automation", {}).get("mode", "unknown"),
        "locks": hermes.get("automation", {}).get("active_locks", []),
        "approval_queue": hermes.get("approval_queue", {}).get("count", row_count(OUT / "hermes_approval_queue_v20.csv")),
        "steps": results,
    }
    (OUT / "v21_8_advisory_cycle_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")

    safe_print("")
    safe_print("=" * 72)
    safe_print(" V21.8 ADVISORY SUMMARY")
    safe_print("=" * 72)
    safe_print(f"Status: {summary['status']}")
    safe_print(f"Fetch: {summary['fetch_state']}")
    safe_print(f"Readiness: {summary['fetch_readiness']}")
    safe_print(f"Feature rows: {summary['feature_rows']}")
    safe_print(f"Backtest rows: {summary['backtest_rows']}")
    safe_print(f"Candidate statuses: {summary['candidate_status_counts']}")
    safe_print(f"Advisory rows: {summary['advisory_rows']}")
    safe_print(f"Advisory labels: {summary['advisory_labels']}")
    safe_print(f"Risk flags: {summary['advisory_risk_flags']}")
    safe_print(f"Mode: {summary['mode']}")
    safe_print(f"Locks: {', '.join(summary['locks']) if summary['locks'] else 'none'}")
    safe_print(f"Approval queue: {summary['approval_queue']}")
    safe_print("")
    safe_print("OK: V21.8 advisory cycle complete" if not failed else "FAILED: V21.8 cycle stopped")
    safe_print(f"Summary JSON: {OUT / 'v21_8_advisory_cycle_summary.json'}")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
