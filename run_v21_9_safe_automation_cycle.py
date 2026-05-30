#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WNBA Edge Lab - V21.9 Safe Automation Cycle

Automates the research/model pipeline only:
1. Fetch data
2. Build features
3. Run diagnostics
4. Build signal/execution review state
5. Build Hermes manual approval state
6. Audit model
7. Generate upgrade recommendations
8. Backtest candidate features
9. Score advisory actions
10. Track model results / CLV evidence

Hard safety rule:
- This runner never places bets.
- This runner never auto-approves Hermes actions.
- This runner never changes formulas, staking, or thresholds.
- User/manual approval remains required for any betting decision.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    import pandas as pd
except Exception:  # pragma: no cover
    pd = None

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "wnba_outputs"
OUT.mkdir(exist_ok=True)

SAFETY_LOCKS = [
    "NO_AUTO_BETTING",
    "MANUAL_APPROVAL_REQUIRED",
    "NO_FORMULA_REPLACEMENT",
    "NO_STAKING_CHANGES",
    "NO_THRESHOLD_CHANGES",
]

PIPELINE_STEPS = [
    ("fetch", "Ultimate Fetcher V21.4.1", "ultimate_fetcher_v21_4_1.py"),
    ("features", "Feature Builder V21", "feature_builder_v21.py"),
    ("diagnostics", "Feature Diagnostics V21", "feature_diagnostics_v21.py"),
    ("execution_bridge", "Signal-to-Execution Bridge", "signal_execution_bridge_v20_1.py"),
    ("hermes_state", "Hermes State Builder", "hermes_state_builder_v20_1.py"),
    ("audit", "Model Audit", "model_audit_v20.py"),
    ("recommend", "Model Upgrade Recommender V21", "model_upgrade_recommender_v21.py"),
    ("backtest", "Model Backtester V21.2", "model_backtester_v21_2.py"),
    ("advisory", "Model Advisory Scoring V21", "model_advisory_scoring_v21.py"),
    ("result_tracker", "Model Result Tracker V21.9", "model_result_tracker_v21_9.py"),
]


def safe_print(value: Any = "") -> None:
    text = str(value)
    try:
        print(text)
    except UnicodeEncodeError:
        print(text.encode("ascii", "replace").decode("ascii"))


def read_json(path: Path) -> Dict[str, Any]:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        pass
    return {}


def row_count(path: Path) -> int:
    try:
        if path.exists() and pd is not None:
            return int(pd.read_csv(path, low_memory=False).shape[0])
        if path.exists():
            with path.open("r", encoding="utf-8", errors="replace", newline="") as f:
                return max(sum(1 for _ in csv.reader(f)) - 1, 0)
    except Exception:
        pass
    return 0


def build_step_args(script: str, args: argparse.Namespace) -> List[str]:
    step_args: List[str] = []
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
    return step_args


def automation_env() -> Dict[str, str]:
    env = os.environ.copy()
    # These are defensive markers for any downstream scripts that read env.
    env["WNBA_EDGE_LAB_AUTOMATION_MODE"] = "research_model_only"
    env["AUTO_BETTING_ENABLED"] = "false"
    env["AUTO_BETTING_DISABLED"] = "true"
    env["MANUAL_APPROVAL_REQUIRED"] = "true"
    env["FORMULA_REPLACEMENT_ALLOWED"] = "false"
    env["STAKING_CHANGES_ALLOWED"] = "false"
    env["THRESHOLD_CHANGES_ALLOWED"] = "false"
    return env


def run_step(step_id: str, name: str, script: str, args: argparse.Namespace) -> Dict[str, Any]:
    path = ROOT / script
    started = datetime.now(timezone.utc).isoformat()
    start = time.time()
    if not path.exists():
        return {
            "step_id": step_id,
            "name": name,
            "script": script,
            "ok": False,
            "returncode": 1,
            "seconds": 0,
            "started_at": started,
            "stdout_tail": "",
            "stderr_tail": f"Missing script: {script}",
        }

    cmd = [sys.executable, str(path)] + build_step_args(script, args)
    p = subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=automation_env(),
    )
    seconds = round(time.time() - start, 2)
    stdout_tail = "\n".join(p.stdout.strip().splitlines()[-20:])
    stderr_tail = "\n".join(p.stderr.strip().splitlines()[-20:])
    return {
        "step_id": step_id,
        "name": name,
        "script": script,
        "ok": p.returncode == 0,
        "returncode": p.returncode,
        "seconds": seconds,
        "started_at": started,
        "stdout_tail": stdout_tail,
        "stderr_tail": stderr_tail,
    }


def collect_summary(results: List[Dict[str, Any]], failed_step: Optional[str]) -> Dict[str, Any]:
    fetch = read_json(OUT / "ultimate_fetch_status_v21_4.json")
    features = read_json(OUT / "feature_builder_summary_v21.json")
    diagnostics = read_json(OUT / "feature_diagnostics_summary_v21.json")
    hermes = read_json(OUT / "hermes_state_v20.json")
    audit = read_json(OUT / "model_audit_summary_v20.json")
    backtest = read_json(OUT / "model_backtest_summary_v21.json")
    advisory = read_json(OUT / "model_advisory_summary_v21.json")
    tracker = read_json(OUT / "model_result_tracking_summary_v21_9.json")

    automation_mode = hermes.get("automation", {}).get("mode", "manual_approval")
    locks = hermes.get("automation", {}).get("active_locks", []) or []
    if not locks:
        locks = ["MANUAL_APPROVAL_REQUIRED"]

    return {
        "version": "V21.9_SAFE_AUTOMATION",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "status": "FAILED" if failed_step else "OK",
        "failed_step": failed_step,
        "automation_scope": "research_model_pipeline_only",
        "betting_execution": "manual_user_only",
        "safety": {
            "auto_betting": False,
            "formula_replacement": False,
            "staking_changes": False,
            "threshold_changes": False,
            "manual_approval_required": True,
            "locks": sorted(set(list(locks) + SAFETY_LOCKS)),
        },
        "fetch": {
            "state": fetch.get("overall_state", "unknown"),
            "readiness": fetch.get("readiness", {}),
        },
        "features": {
            "rows": features.get("rows", {}),
            "warnings": row_count(OUT / "hermes_feature_warnings_v21.csv"),
        },
        "diagnostics": diagnostics,
        "hermes": {
            "mode": automation_mode,
            "approval_queue": hermes.get("approval_queue", {}).get("count", row_count(OUT / "hermes_approval_queue_v20.csv")),
            "warnings": row_count(OUT / "hermes_warnings_v20.csv"),
        },
        "audit": audit,
        "backtest": backtest,
        "advisory": {
            "rows": advisory.get("rows", {}),
            "labels": advisory.get("label_counts", {}),
            "risk_flags": advisory.get("risk_flag_counts", {}),
        },
        "result_tracking": tracker,
        "output_files": {
            "automation_summary": str(OUT / "v21_9_safe_automation_summary.json"),
            "result_tracking": str(OUT / "model_result_tracking_v21_9.csv"),
            "result_tracking_summary": str(OUT / "model_result_tracking_summary_v21_9.json"),
            "promotion_watchlist": str(OUT / "model_promotion_watchlist_v21_9.csv"),
        },
        "steps": results,
    }


def write_run_log(summary: Dict[str, Any]) -> None:
    lines = [
        "WNBA EDGE LAB V21.9 SAFE AUTOMATION RUN",
        f"Created: {summary['created_at']}",
        f"Status: {summary['status']}",
        f"Scope: {summary['automation_scope']}",
        f"Betting execution: {summary['betting_execution']}",
        "",
        "Safety:",
        f"- auto_betting={summary['safety']['auto_betting']}",
        f"- manual_approval_required={summary['safety']['manual_approval_required']}",
        f"- formula_replacement={summary['safety']['formula_replacement']}",
        f"- staking_changes={summary['safety']['staking_changes']}",
        f"- threshold_changes={summary['safety']['threshold_changes']}",
        "- locks=" + ", ".join(summary['safety']['locks']),
        "",
        f"Fetch: {summary['fetch'].get('state')}",
        f"Feature rows: {summary['features'].get('rows')}",
        f"Advisory: {summary['advisory'].get('rows')}",
        f"Labels: {summary['advisory'].get('labels')}",
        f"Risk flags: {summary['advisory'].get('risk_flags')}",
        f"Result tracking: {summary.get('result_tracking', {})}",
        "",
        "Steps:",
    ]
    for step in summary["steps"]:
        lines.append(f"- {'OK' if step['ok'] else 'FAILED'} {step['name']} ({step['seconds']}s)")
    (OUT / "v21_9_safe_automation_run_log.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="WNBA Edge Lab V21.9 safe automation cycle. Research/model only; no betting execution.")
    parser.add_argument("--seasons", default="2025,2026")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--features", action="store_true")
    parser.add_argument("--props", action="store_true")
    parser.add_argument("--skip-sdv", action="store_true")
    parser.add_argument("--all-sdv-assets", action="store_true")
    parser.add_argument("--continue-on-error", action="store_true", help="Continue later steps after a failure. Default stops on first failure.")
    args = parser.parse_args()

    safe_print("=" * 76)
    safe_print(" WNBA EDGE LAB - V21.9 SAFE AUTOMATION CYCLE")
    safe_print("=" * 76)
    safe_print(f"Root: {ROOT}")
    safe_print(f"Started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    safe_print("Scope: research/model automation only")
    safe_print("Safety: NO auto-betting, NO formula/staking/threshold changes, manual approval required")
    safe_print("")

    results: List[Dict[str, Any]] = []
    failed_step: Optional[str] = None

    for step_id, name, script in PIPELINE_STEPS:
        res = run_step(step_id, name, script, args)
        results.append(res)
        safe_print(f"[{'OK' if res['ok'] else 'FAILED'}] {name} ({res['seconds']}s)")
        if res["stdout_tail"]:
            for line in res["stdout_tail"].splitlines()[-10:]:
                safe_print(f"      {line}")
        if res["stderr_tail"]:
            safe_print("      stderr:")
            for line in res["stderr_tail"].splitlines()[-8:]:
                safe_print(f"        {line}")
        if not res["ok"] and not args.continue_on_error:
            failed_step = step_id
            break
        elif not res["ok"] and failed_step is None:
            failed_step = step_id

    summary = collect_summary(results, failed_step)
    (OUT / "v21_9_safe_automation_summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")
    write_run_log(summary)

    safe_print("")
    safe_print("=" * 76)
    safe_print(" V21.9 SAFE AUTOMATION SUMMARY")
    safe_print("=" * 76)
    safe_print(f"Status: {summary['status']}")
    safe_print(f"Scope: {summary['automation_scope']}")
    safe_print(f"Betting execution: {summary['betting_execution']}")
    safe_print(f"Safety locks: {', '.join(summary['safety']['locks'])}")
    safe_print(f"Fetch: {summary['fetch']['state']}")
    safe_print(f"Feature rows: {summary['features']['rows']}")
    safe_print(f"Advisory rows: {summary['advisory']['rows']}")
    safe_print(f"Advisory labels: {summary['advisory']['labels']}")
    safe_print(f"Risk flags: {summary['advisory']['risk_flags']}")
    safe_print(f"Result tracking: {summary['result_tracking']}")
    safe_print(f"Summary JSON: {OUT / 'v21_9_safe_automation_summary.json'}")
    safe_print(f"Run log: {OUT / 'v21_9_safe_automation_run_log.txt'}")
    return 0 if summary["status"] == "OK" else 1


if __name__ == "__main__":
    raise SystemExit(main())
