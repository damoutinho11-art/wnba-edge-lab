#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WNBA Edge Lab — Candidate Historical Sanity Audit V21.10

Read-only audit that compares the V21.10 candidate generator's outputs
against historical projection/result artifacts to detect behavioral drift,
market anchoring, and sanity issues before any live promotion.

Hard constraints:
- No live output overwrite.
- No changes to production files.
- No formula/threshold/staking/actionability changes.
- Manual approval required.
- Research audit only.
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "wnba_outputs"

# ── Historical artifact paths ─────────────────────────────────────────
HISTORICAL_FILES = {
    "projections": OUT / "projections.csv",
    "projections_diagnostics": OUT / "projections_diagnostics.csv",
    "projections_with_stakes": OUT / "projections_with_stakes.csv",
    "recommended_bets": OUT / "recommended_bets.csv",
    "projection_history": OUT / "projection_history.csv",
    "signal_tracker_graded": OUT / "signal_tracker_graded.csv",
    "signal_tracker_graded_deduped": OUT / "signal_tracker_graded_deduped_v21.csv",
    "model_result_tracking": OUT / "model_result_tracking_v21_9.csv",
}

# Candidate paths
CANDIDATE_FILES = {
    "projections_candidate": OUT / "projections_with_stakes_candidate_v21_10.csv",
    "recommended_candidate": OUT / "recommended_bets_candidate_v21_10.csv",
    "summary_candidate": OUT / "projection_staking_candidate_summary_v21_10.json",
}

# Warning thresholds
EDGE_WARN_THRESHOLD = 0.5          # candidate edge magnitude vs historical mean
CONF_WARN_THRESHOLD = 10.0         # candidate confidence vs historical mean
UNITS_MAX = 0.50
UNITS_WARN_RATIO = 0.5             # units>0 ratio > 0.5 warns
MARKET_ANCHOR_THRESHOLD = 0.10     # abs(edge) < 0.10 warns
UNITS_MAX_HARD = 0.50

def now_iso() -> str:
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

def safe_numeric(series: pd.Series) -> pd.Series:
    return pd.to_numeric(series, errors="coerce")

def get_file_info(df: pd.DataFrame, name: str) -> Dict[str, Any]:
    """Extract basic file metadata."""
    if df.empty:
        return {"exists": False, "rows": 0, "cols": 0, "cols_list": [], "date_range": None}
    date_col = None
    for c in df.columns:
        cl = c.lower()
        if any(x in cl for x in ["date", "time", "commence", "run"]):
            date_col = c
            break
    date_range = None
    if date_col:
        try:
            dates = safe_numeric(pd.to_datetime(df[date_col], errors="coerce"))
            valid_dates = dates.dropna()
            if not valid_dates.empty:
                date_range = {"min": str(valid_dates.min()), "max": str(valid_dates.max())}
        except Exception:
            pass
    return {
        "exists": True,
        "rows": len(df),
        "cols": len(df.columns),
        "cols_list": list(df.columns),
        "date_range": date_range,
    }

def compute_profile(df: pd.DataFrame, numeric_cols: List[str]) -> Dict[str, Any]:
    """Compute statistics for numeric columns."""
    profile = {}
    for col in numeric_cols:
        if col in df.columns:
            s = safe_numeric(df[col]).dropna()
            if not s.empty:
                profile[col] = {
                    "count": int(len(s)),
                    "mean": float(s.mean()),
                    "std": float(s.std()),
                    "min": float(s.min()),
                    "max": float(s.max()),
                    "median": float(s.median()),
                    "q25": float(s.quantile(0.25)),
                    "q75": float(s.quantile(0.75)),
                }
    return profile

def check_signal_breakdown(df: pd.DataFrame, signal_col: str) -> Dict[str, int]:
    if signal_col in df.columns:
        return df[signal_col].fillna("UNKNOWN").astype(str).value_counts().to_dict()
    return {}

def run_historical_sanity_audit(generate_candidate: bool = False) -> Dict[str, Any]:
    """Main audit function."""
    safe_print("=" * 80)
    safe_print("WNBA EDGE LAB — CANDIDATE HISTORICAL SANITY AUDIT V21.10")
    safe_print("=" * 80)
    safe_print(f"Timestamp: {now_iso()}")
    safe_print("")

    if generate_candidate:
        safe_print("Generating candidate files...")
        from wnba_projection_staking_candidate_v21_10 import generate_candidates
        generate_candidates(write_candidate=True)

    # ── Load historical artifacts ──────────────────────────────────────
    safe_print("📁 LOADING HISTORICAL ARTIFACTS")
    safe_print("-" * 80)

    historical_data = {}
    file_info = {}

    for name, path in HISTORICAL_FILES.items():
        df = read_csv(path)
        historical_data[name] = df
        info = get_file_info(df, name)
        file_info[name] = info
        exists = "✅" if info["exists"] else "❌"
        safe_print(f"  {exists} {name}: rows={info['rows']}, cols={info['cols']}")
        if info["date_range"]:
            safe_print(f"    date_range: {info['date_range']['min']} to {info['date_range']['max']}")

    # Load candidate files
    safe_print("")
    safe_print("🧪 LOADING CANDIDATE OUTPUTS")
    safe_print("-" * 80)

    candidate_data = {}
    for name, path in CANDIDATE_FILES.items():
        if name == "summary_candidate":
            candidate_data[name] = read_json(path)
        else:
            df = read_csv(path)
            candidate_data[name] = df
            info = get_file_info(df, name)
            exists = "✅" if info["exists"] else "❌"
            safe_print(f"  {exists} {name}: rows={info['rows']}, cols={info['cols']}")

    # ── 1. Historical artifact availability ───────────────────────────
    safe_print("")
    safe_print("📋 1. HISTORICAL ARTIFACT AVAILABILITY")
    safe_print("-" * 80)

    availability = {}
    for name, info in file_info.items():
        availability[name] = {
            "exists": info["exists"],
            "rows": info["rows"],
            "cols": info["cols"],
            "date_range": info["date_range"],
        }

    # ── 2. Historical output profile ───────────────────────────────────
    safe_print("")
    safe_print("📊 2. HISTORICAL OUTPUT PROFILE")
    safe_print("-" * 80)

    # Primary historical source: projections.csv and projections_with_stakes.csv
    historical_profile = {"signals": {}}

    # From projections.csv (has projection, edge, confidence, line)
    if "projections" in historical_data and not historical_data["projections"].empty:
        df = historical_data["projections"]
        numeric_cols = ["line", "projection", "edge", "confidence", "suggested_units",
                       "books_count", "raw_total", "calibration_factor"]
        historical_profile["projections"] = compute_profile(df, numeric_cols)
        historical_profile["signals"]["projections"] = check_signal_breakdown(df, "signal")
        safe_print(f"  projections.csv: {len(df)} rows")

        # Print key stats
        for col in ["projection", "line", "edge", "confidence", "suggested_units"]:
            if col in historical_profile["projections"]:
                p = historical_profile["projections"][col]
                safe_print(f"    {col}: mean={p['mean']:.2f}, min={p['min']:.2f}, max={p['max']:.2f}, count={p['count']}")

    # From projections_with_stakes.csv (has units, signals)
    if "projections_with_stakes" in historical_data and not historical_data["projections_with_stakes"].empty:
        df = historical_data["projections_with_stakes"]
        numeric_cols = ["line", "projection", "edge", "confidence", "suggested_units",
                       "SuggestedUnits", "SuggestedUnitsRaw", "UnitValue"]
        historical_profile["projections_with_stakes"] = compute_profile(df, numeric_cols)
        historical_profile["signals"]["projections_with_stakes"] = check_signal_breakdown(df, "FinalSignalNormalized")
        safe_print(f"  projections_with_stakes: {len(df)} rows")

    # From signal_tracker_graded_deduped (has CLV, results)
    if "signal_tracker_graded_deduped" in historical_data and not historical_data["signal_tracker_graded_deduped"].empty:
        df = historical_data["signal_tracker_graded_deduped"]
        numeric_cols = ["LineAtSignal", "Projection", "Edge", "Confidence", "SuggestedUnits", 
                       "CLV_Points", "CLV_Percent"]
        historical_profile["signal_tracker"] = compute_profile(df, numeric_cols)
        historical_profile["signals"]["signal_tracker"] = check_signal_breakdown(df, "FinalSignal")
        safe_print(f"  signal_tracker_graded_deduped: {len(df)} rows")

    # ── 3. Candidate output profile ────────────────────────────────────
    safe_print("")
    safe_print("🧪 3. CANDIDATE OUTPUT PROFILE")
    safe_print("-" * 80)

    candidate_profile = {"signals": {}}

    if "projections_candidate" in candidate_data and not candidate_data["projections_candidate"].empty:
        df = candidate_data["projections_candidate"]
        numeric_cols = ["line", "projection", "edge", "confidence", "suggested_units"]
        candidate_profile["projections_candidate"] = compute_profile(df, numeric_cols)
        candidate_profile["signals"]["projections_candidate"] = check_signal_breakdown(df, "recommended_bet")

        safe_print(f"  candidate projections: {len(df)} rows")
        for col in ["line", "projection", "edge", "confidence", "suggested_units"]:
            if col in candidate_profile["projections_candidate"]:
                p = candidate_profile["projections_candidate"][col]
                safe_print(f"    {col}: mean={p['mean']:.2f}, min={p['min']:.2f}, max={p['max']:.2f}, count={p['count']}")

        candidate_profile["signals_breakdown"] = check_signal_breakdown(df, "recommended_bet")

    # ── 4. Distribution warnings ───────────────────────────────────────
    safe_print("")
    safe_print("⚠️  4. DISTRIBUTION WARNINGS")
    safe_print("-" * 80)

    warnings = []

    # Compare candidate vs historical profiles
    hist_proj = historical_profile.get("projections", {}) or historical_profile.get("projections_with_stakes", {})
    cand_proj = candidate_profile.get("projections_candidate", {})

    for metric in ["projection", "line", "edge", "confidence", "suggested_units"]:
        if metric in hist_proj and metric in cand_proj:
            hist_mean = hist_proj[metric].get("mean", 0)
            cand_mean = cand_proj[metric].get("mean", 0)
            hist_std = hist_proj[metric].get("std", 0)

            if hist_std > 0:
                diff = abs(cand_mean - hist_mean) / hist_std
                if diff > 2.0:
                    warnings.append(f"  DISTRIBUTION SHIFT: {metric} candidate mean ({cand_mean:.2f}) differs from historical ({hist_mean:.2f}) by {diff:.1f}σ")

    # Market anchoring check: candidate edge near zero
    if "projections_candidate" in candidate_data and not candidate_data["projections_candidate"].empty:
        cand_df = candidate_data["projections_candidate"]
        if "edge" in cand_df.columns:
            edges = safe_numeric(cand_df["edge"]).abs()
            near_zero = (edges < MARKET_ANCHOR_THRESHOLD).sum()
            if near_zero > 0:
                warnings.append(f"  MARKET ANCHORING WARNING: {near_zero}/{len(cand_df)} candidate edges < {MARKET_ANCHOR_THRESHOLD} (abs(edge) ≈ 0)")

    # Units sanity
    if "projections_candidate" in candidate_data and not candidate_data["projections_candidate"].empty:
        cand_df = candidate_data["projections_candidate"]
        if "suggested_units" in cand_df.columns:
            units = safe_numeric(cand_df["suggested_units"])
            units_filled = units.dropna()
            if len(units_filled) > 0:
                # Check units cap
                over_cap = (units_filled > UNITS_MAX_HARD).sum()
                if over_cap > 0:
                    warnings.append(f"  UNITS CAP: {over_cap} candidate units exceed {UNITS_MAX_HARD}")

                # Check units ratio
                units_positive = (units_filled > 0).sum()
                ratio = units_positive / len(cand_df)
                if ratio > UNITS_WARN_RATIO:
                    warnings.append(f"  HIGH UNITS RATIO: {units_positive}/{len(cand_df)} ({ratio:.1%}) have units > 0")

    # Confidence sanity
    if "projections_candidate" in candidate_data and not candidate_data["projections_candidate"].empty:
        cand_df = candidate_data["projections_candidate"]
        if "confidence" in cand_df.columns:
            conf = safe_numeric(cand_df["confidence"])
            conf_valid = conf.dropna()
            if len(conf_valid) > 0:
                conf_mean = conf_valid.mean()
                if "confidence" in hist_proj:
                    hist_conf_mean = hist_proj["confidence"].get("mean", 0)
                    if abs(conf_mean - hist_conf_mean) > CONF_WARN_THRESHOLD:
                        warnings.append(f"  CONFIDENCE SHIFT: candidate mean={conf_mean:.1f}, historical mean={hist_conf_mean:.1f} (diff={abs(conf_mean - hist_conf_mean):.1f})")

    # Print warnings
    for w in warnings:
        safe_print(f"  ⚠️ {w}")
    if not warnings:
        safe_print("  No distribution warnings.")

    # ── 5. Optional result sanity ───────────────────────────────────────
    safe_print("")
    safe_print("🔍 5. OPTIONAL RESULT SANITY (Historical)")
    safe_print("-" * 80)

    result_sanity = {}
    if "projection_history" in historical_data and not historical_data["projection_history"].empty:
        df = historical_data["projection_history"]
        # Check if ActualTotal and Result exist
        cols = df.columns.tolist()
        if "ActualTotal" in cols and "Result" in cols:
            safe_print(f"  projection_history has ActualTotal/Result: ✅")
            # We could compute win rate but not evaluating candidates
            result_sanity["has_results"] = True
        else:
            safe_print(f"  projection_history missing ActualTotal/Result: ❌")
            result_sanity["has_results"] = False

    if "signal_tracker_graded_deduped" in historical_data and not historical_data["signal_tracker_graded_deduped"].empty:
        df = historical_data["signal_tracker_graded_deduped"]
        if "WouldHaveWon" in df.columns and "ActualTotal" in df.columns:
            safe_print(f"  signal_tracker_graded has WouldHaveWon/ActualTotal: ✅")
            graded = df[df["WouldHaveWon"].notna()]
            if len(graded) > 0:
                wins = (graded["WouldHaveWon"].astype(str).str.upper() == "WIN").sum()
                result_sanity["graded_count"] = len(graded)
                result_sanity["wins"] = int(wins)
                result_sanity["win_rate"] = wins / len(graded)
                safe_print(f"  Graded signals: {len(graded)}, Wins: {wins}, Win rate: {wins/len(graded):.1%}")
            result_sanity["signal_tracker_results"] = True
        else:
            safe_print(f"  signal_tracker_graded missing WouldHaveWon/ActualTotal: ❌")

    # ── 6. Verdict ─────────────────────────────────────────────────────
    safe_print("")
    safe_print("🏁 6. FINAL VERDICT")
    safe_print("-" * 80)

    has_errors = False  # We don't generate errors, only warnings
    has_warnings = len(warnings) > 0

    if has_errors:
        verdict = "HISTORICAL_SANITY_FAIL_BLOCKED"
    elif has_warnings:
        verdict = "HISTORICAL_SANITY_WARN_RESEARCH_ONLY"
    else:
        verdict = "HISTORICAL_SANITY_PASS_RESEARCH_ONLY"

    safe_print(f"  {verdict}")
    safe_print("")

    safe_print("🔒 SAFETY FOOTER")
    safe_print("  • Manual approval required")
    safe_print("  • No auto-betting")
    safe_print("  • No formula changes")
    safe_print("  • No staking changes")
    safe_print("  • No threshold changes")
    safe_print("  • Research audit only — not production")
    safe_print("")
    safe_print("=" * 80)

    # Build result dict
    result = {
        "timestamp": now_iso(),
        "verdict": verdict,
        "historical_artifacts": availability,
        "historical_profile": historical_profile,
        "candidate_profile": candidate_profile,
        "warnings": warnings,
        "errors": [],
        "result_sanity": result_sanity,
        "summary": {
            "total_warnings": len(warnings),
            "total_errors": 0,
        },
    }

    return result


def now_iso() -> str:
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

def main() -> int:
    parser = argparse.ArgumentParser(description="Candidate Historical Sanity Audit V21.10")
    parser.add_argument("--generate-candidate", action="store_true",
                        help="Generate candidate files first")
    parser.add_argument("--output", "-o", type=Path, help="Write report JSON to file")
    args = parser.parse_args()

    result = run_historical_sanity_audit(generate_candidate=args.generate_candidate)

    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        safe_print(f"Report written to: {args.output}")

    # Exit code based on verdict
    if result["verdict"] == "HISTORICAL_SANITY_FAIL_BLOCKED":
        return 2
    elif result["verdict"] == "HISTORICAL_SANITY_WARN_RESEARCH_ONLY":
        return 1
    else:
        return 0


if __name__ == "__main__":
    from datetime import datetime, timezone
    import argparse
    import sys
    sys.exit(main())