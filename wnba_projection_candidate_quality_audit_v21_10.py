#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WNBA Edge Lab — Candidate Projection Quality Audit V21.10

Read-only audit for dry-run candidate projection/staking generator.
Validates candidate outputs are sane before any live wiring or promotion.

Hard constraints:
- No live output overwrite.
- No changes to production files.
- No formula/threshold/staking/actionability changes.
- Manual approval required.
- Candidate audit only.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "wnba_outputs"

# ── Candidate file paths ──────────────────────────────────────────────
PROJ_CANDIDATE = OUT / "projections_with_stakes_candidate_v21_10.csv"
REC_CANDIDATE = OUT / "recommended_bets_candidate_v21_10.csv"
SUMMARY_CANDIDATE = OUT / "projection_staking_candidate_summary_v21_10.json"

# ── Audit thresholds ──────────────────────────────────────────────────
MAX_UNITS = 0.50
MIN_CONFIDENCE_FOR_UNITS = 50.0
MIN_ABS_EDGE_FOR_UNITS = 1.0
MAX_EDGE_EQ_LINE_WARN = 0.10  # projection == line tolerance
CONFIDENCE_MIN = 0.0
CONFIDENCE_MAX = 100.0
EDGE_TOLERANCE = 0.02  # projection - line = edge rounding tolerance


def now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def safe_print(text: str = "") -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(str(text).encode("ascii", "replace").decode("ascii"))


def read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path, low_memory=False)
    except Exception as e:
        safe_print(f"[WARN] Could not read {path}: {e}")
        return pd.DataFrame()


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        safe_print(f"[WARN] Could not read {path}: {e}")
        return {}


def audit_candidates(
    proj_df: pd.DataFrame,
    rec_df: pd.DataFrame,
    summary: Dict[str, Any],
    generate_candidate: bool = False,
) -> Dict[str, Any]:
    """Run all audit checks and return verdict."""

    findings = []
    warnings = []
    errors = []

    def add_finding(msg: str):
        findings.append(msg)

    def add_warning(msg: str):
        warnings.append(msg)

    def add_error(msg: str):
        errors.append(msg)

    # 1. File existence
    if proj_df.empty:
        add_error("Candidate projection file is empty or missing")
    if rec_df.empty:
        add_error("Candidate recommended bets file is empty or missing")

    # 2. Schema check
    required_proj = [
        "game", "away_team", "home_team", "line", "projection",
        "edge", "side", "confidence", "suggested_units",
        "recommended_bet", "commence_time", "model_version",
        "formula_status", "manual_approval_required"
    ]
    required_rec = [
        "game", "recommended_bet", "side", "projection",
        "line", "edge", "suggested_units", "confidence",
        "commence_time", "model_version", "formula_status",
        "manual_approval_required"
    ]

    if not proj_df.empty:
        missing = [c for c in required_proj if c not in proj_df.columns]
        if missing:
            add_error(f"Projection candidate missing columns: {missing}")

    if not rec_df.empty:
        missing = [c for c in required_rec if c not in rec_df.columns]
        if missing:
            add_error(f"Recommended candidate missing columns: {missing}")

    # 3. Row count matches fresh game count
    fresh_games_in_summary = summary.get("stats", {}).get("total", 0)
    actual_rows = len(proj_df)
    if fresh_games_in_summary and actual_rows != fresh_games_in_summary:
        add_warning(f"Row count mismatch: summary says {fresh_games_in_summary}, file has {actual_rows}")

    # Run remaining checks only if we have data
    if proj_df.empty or rec_df.empty:
        return build_result(findings, warnings, errors, proj_df, rec_df)

    # 4. Projection populated count
    proj_filled = proj_df["projection"].apply(lambda x: pd.notna(x) and str(x).strip() != "").sum()
    add_finding(f"Projections populated: {proj_filled}/{len(proj_df)}")

    # 5. Edge populated count
    edge_filled = proj_df["edge"].apply(lambda x: pd.notna(x) and str(x).strip() != "").sum()
    add_finding(f"Edges populated: {edge_filled}/{len(proj_df)}")

    # 6. Side consistency
    side_issues = 0
    for _, row in proj_df.iterrows():
        edge_str = str(row.get("edge", "")).strip()
        side_str = str(row.get("side", "")).strip().upper()
        if edge_str and edge_str not in ("nan", ""):
            try:
                edge = float(edge_str)
                if edge > 0 and side_str != "OVER":
                    add_warning(f"Side mismatch: {row.get('game')} edge={edge} but side={side_str}")
                    side_issues += 1
                elif edge < 0 and side_str != "UNDER":
                    add_warning(f"Side mismatch: {row.get('game')} edge={edge} but side={side_str}")
                    side_issues += 1
                elif edge == 0 and side_str not in ("", "PASS", "NO_BET", "NO"):
                    add_warning(f"Side mismatch: {row.get('game')} edge=0 but side={side_str}")
                    side_issues += 1
            except ValueError:
                pass
    if side_issues == 0:
        add_finding("Side consistency: PASS (edge → OVER/UNDER mapping correct)")

    # 7. Edge math verification
    edge_math_issues = 0
    for _, row in proj_df.iterrows():
        proj_str = str(row.get("projection", "")).strip()
        line_str = str(row.get("line", "")).strip()
        edge_str = str(row.get("edge", "")).strip()
        if proj_str and line_str and edge_str and proj_str not in ("nan", "") and line_str not in ("nan", "") and edge_str not in ("nan", ""):
            try:
                proj = float(proj_str)
                line = float(line_str)
                edge = float(edge_str)
                calc_edge = round(proj - line, 2)
                if abs(edge - calc_edge) > EDGE_TOLERANCE:
                    add_warning(f"Edge math mismatch: {row.get('game')} edge={edge} but proj-line={calc_edge}")
                    edge_math_issues += 1
            except ValueError:
                pass
    if edge_math_issues == 0:
        add_finding("Edge math verification: PASS (edge = projection - line)")

    # 8. Market dependence warning
    market_dep_warnings = 0
    for _, row in proj_df.iterrows():
        proj_str = str(row.get("projection", "")).strip()
        line_str = str(row.get("line", "")).strip()
        if proj_str and line_str and proj_str not in ("nan", "") and line_str not in ("nan", ""):
            try:
                proj = float(proj_str)
                line = float(line_str)
                if abs(proj - line) < MAX_EDGE_EQ_LINE_WARN:
                    add_warning(f"Market dependence: {row.get('game')} projection≈line ({proj:.2f}≈{line:.2f})")
                    market_dep_warnings += 1
            except ValueError:
                pass
    if market_dep_warnings > 0:
        add_warning(f"Market dependence: {market_dep_warnings} rows with projection≈line (<{MAX_EDGE_EQ_LINE_WARN})")
    else:
        add_finding("Market dependence: PASS (no projection≈line)")

    # 9. Units sanity
    units_issues = 0
    units_filled = 0
    for _, row in proj_df.iterrows():
        units_str = str(row.get("suggested_units", "")).strip()
        conf_str = str(row.get("confidence", "")).strip()
        edge_str = str(row.get("edge", "")).strip()
        if units_str and units_str not in ("nan", ""):
            try:
                units = float(units_str)
                units_filled += 1
                if units < 0:
                    add_warning(f"Units sanity: {row.get('game')} units={units} < 0")
                    units_issues += 1
                if units > MAX_UNITS:
                    add_warning(f"Units sanity: {row.get('game')} units={units} > {MAX_UNITS}")
                    units_issues += 1
                if units > 0:
                    if not conf_str or conf_str in ("nan", ""):
                        add_warning(f"Units sanity: {row.get('game')} units>0 but confidence missing")
                        units_issues += 1
                    else:
                        try:
                            conf = float(conf_str)
                            if conf < MIN_CONFIDENCE_FOR_UNITS:
                                add_warning(f"Units sanity: {row.get('game')} units={units} but confidence={conf} < {MIN_CONFIDENCE_FOR_UNITS}")
                                units_issues += 1
                        except ValueError:
                            pass
                    if not edge_str or edge_str in ("nan", ""):
                        add_warning(f"Units sanity: {row.get('game')} units>0 but edge missing")
                        units_issues += 1
                    else:
                        try:
                            edge = float(edge_str)
                            if abs(edge) < MIN_ABS_EDGE_FOR_UNITS:
                                add_warning(f"Units sanity: {row.get('game')} units={units} but |edge|={abs(edge)} < {MIN_ABS_EDGE_FOR_UNITS}")
                                units_issues += 1
                        except ValueError:
                            pass
            except ValueError:
                pass
    if units_filled > 0:
        add_finding(f"Units populated: {units_filled}/{len(proj_df)}")
    if units_issues == 0:
        add_finding("Units sanity: PASS")

    # 10. Confidence sanity
    conf_issues = 0
    for _, row in proj_df.iterrows():
        conf_str = str(row.get("confidence", "")).strip()
        if conf_str and conf_str not in ("nan", ""):
            try:
                conf = float(conf_str)
                if conf < CONFIDENCE_MIN or conf > CONFIDENCE_MAX:
                    add_warning(f"Confidence sanity: {row.get('game')} confidence={conf} outside [{CONFIDENCE_MIN}, {CONFIDENCE_MAX}]")
                    conf_issues += 1
            except ValueError:
                pass
    if conf_issues == 0:
        add_finding("Confidence sanity: PASS (all in [0, 100])")

    # 11. Manual safety checks
    approval_issues = sum(1 for _, r in proj_df.iterrows() if str(r.get("manual_approval_required", "")).strip().upper() not in ("TRUE", "1", "YES"))
    formula_issues = sum(1 for _, r in proj_df.iterrows() if "CANDIDATE_DRY_RUN" not in str(r.get("formula_status", "")))
    if approval_issues > 0:
        add_error(f"Manual approval required false/missing: {approval_issues} rows")
    else:
        add_finding("Manual approval required: PASS (all True)")

    if formula_issues > 0:
        add_error(f"Missing CANDIDATE_DRY_RUN marker: {formula_issues} rows")
    else:
        add_finding("Formula status marker: PASS (all CANDIDATE_DRY_RUN)")

    # Determine verdict
    if errors:
        verdict = "CANDIDATE_AUDIT_FAIL_BLOCKED"
    elif warnings:
        verdict = "CANDIDATE_AUDIT_WARN_RESEARCH_ONLY"
    else:
        verdict = "CANDIDATE_AUDIT_PASS_RESEARCH_ONLY"

    return build_result(findings, warnings, errors, proj_df, rec_df, verdict)


def build_result(
    findings: List[str],
    warnings: List[str],
    errors: List[str],
    proj_df: pd.DataFrame,
    rec_df: pd.DataFrame,
    verdict: str = None,
) -> Dict[str, Any]:
    """Build final result dict."""
    if verdict is None:
        if errors:
            verdict = "CANDIDATE_AUDIT_FAIL_BLOCKED"
        elif warnings:
            verdict = "CANDIDATE_AUDIT_WARN_RESEARCH_ONLY"
        else:
            verdict = "CANDIDATE_AUDIT_PASS_RESEARCH_ONLY"

    result = {
        "timestamp": now_iso(),
        "verdict": verdict,
        "files": {
            "projections_candidate": str(PROJ_CANDIDATE),
            "recommended_candidate": str(REC_CANDIDATE),
            "summary_candidate": str(SUMMARY_CANDIDATE),
        },
        "counts": {
            "projection_rows": len(proj_df),
            "recommended_rows": len(rec_df),
        },
        "findings": findings,
        "warnings": warnings,
        "errors": errors,
        "summary": {
            "total_findings": len(findings),
            "total_warnings": len(warnings),
            "total_errors": len(errors),
        },
    }
    return result


def now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def print_report(result: Dict[str, Any]) -> None:
    """Print formatted audit report."""
    safe_print("=" * 70)
    safe_print("WNBA EDGE LAB — CANDIDATE PROJECTION QUALITY AUDIT V21.10")
    safe_print("=" * 70)
    safe_print(f"Timestamp: {result['timestamp']}")
    safe_print("")

    safe_print("📁 FILES CHECKED")
    safe_print("-" * 70)
    for k, v in result["files"].items():
        exists = "✅" if Path(v).exists() else "❌"
        safe_print(f"  {exists} {k}: {v}")
    safe_print("")

    safe_print("📊 COUNTS")
    safe_print("-" * 70)
    for k, v in result["counts"].items():
        safe_print(f"  {k}: {v}")
    safe_print("")

    if result["findings"]:
        safe_print("✅ FINDINGS (PASS)")
        safe_print("-" * 70)
        for f in result["findings"]:
            safe_print(f"  • {f}")
        safe_print("")

    if result["warnings"]:
        safe_print("⚠️  WARNINGS")
        safe_print("-" * 70)
        for w in result["warnings"]:
            safe_print(f"  • {w}")
        safe_print("")

    if result["errors"]:
        safe_print("❌ ERRORS")
        safe_print("-" * 70)
        for e in result["errors"]:
            safe_print(f"  • {e}")
        safe_print("")

    safe_print("📋 SUMMARY")
    safe_print("-" * 70)
    safe_print(f"  Findings (pass): {result['summary']['total_findings']}")
    safe_print(f"  Warnings:        {result['summary']['total_warnings']}")
    safe_print(f"  Errors:          {result['summary']['total_errors']}")
    safe_print("")

    safe_print("🏁 FINAL VERDICT")
    safe_print("-" * 70)
    verdict = result["verdict"]
    if verdict.endswith("PASS_RESEARCH_ONLY"):
        safe_print(f"  ✅ {verdict}")
    elif verdict.endswith("WARN_RESEARCH_ONLY"):
        safe_print(f"  ⚠️  {verdict}")
    else:
        safe_print(f"  ❌ {verdict}")
    safe_print("")

    safe_print("🔒 SAFETY FOOTER")
    safe_print("  • Manual approval required")
    safe_print("  • No auto-betting")
    safe_print("  • No formula changes")
    safe_print("  • No staking changes")
    safe_print("  • No threshold changes")
    safe_print("  • Candidate audit only — not production")
    safe_print("")
    safe_print("=" * 70)


def main() -> int:
    parser = argparse.ArgumentParser(description="Candidate Projection Quality Audit V21.10")
    parser.add_argument("--generate-candidate", action="store_true",
                        help="Also generate candidate files before audit")
    parser.add_argument("--output", "-o", type=Path, help="Write report JSON to file")
    args = parser.parse_args()

    from wnba_projection_staking_candidate_v21_10 import generate_candidates

    if args.generate_candidate:
        safe_print("Generating candidate files...")
        generate_candidates(write_candidate=True)

    # Load candidate files
    proj_df = read_csv(PROJ_CANDIDATE)
    rec_df = read_csv(REC_CANDIDATE)
    summary = read_json(SUMMARY_CANDIDATE)

    if proj_df.empty:
        safe_print(f"❌ Candidate projection file not found: {PROJ_CANDIDATE}")
        safe_print("Run with --generate-candidate first, or run wnba_projection_staking_candidate_v21_10.py --write-candidate")
        return 1

    safe_print(f"Loaded candidate files: {len(proj_df)} projections, {len(rec_df)} recommended")
    safe_print("")

    result = audit_candidates(proj_df, rec_df, summary, generate_candidate=args.generate_candidate)
    print_report(result)

    if args.output:
        result["output_path"] = str(args.output)
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        safe_print(f"Report written to: {args.output}")

    # Exit code based on verdict
    if result["verdict"] == "CANDIDATE_AUDIT_FAIL_BLOCKED":
        return 2
    elif result["verdict"] == "CANDIDATE_AUDIT_WARN_RESEARCH_ONLY":
        return 1
    else:
        return 0


if __name__ == "__main__":
    sys.exit(main())