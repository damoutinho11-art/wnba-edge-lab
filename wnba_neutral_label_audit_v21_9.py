#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WNBA Edge Lab — Neutral Label Audit V21.9

Read-only diagnostic explaining why each fresh advisory row receives NEUTRAL label.
"""

import csv
import json
import sys
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Tuple, Optional

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "wnba_outputs"

# ── paths ──────────────────────────────────────────────────────────────
ADVISORY_QUEUE = OUT / "hermes_advisory_queue_v21.csv"
ADVISORY_SCORES = OUT / "model_advisory_scores_v21.csv"
ADVISORY_SUMMARY = OUT / "model_advisory_summary_v21.json"
GAME_FEATURES = OUT / "game_model_features_v21.csv"

# ── threshold constants from model_advisory_scoring_v21.py ─────────────
LEAN_SUPPORT_THRESHOLD = 25
SUPPORT_THRESHOLD = 50
STRONG_SUPPORT_THRESHOLD = 75
LEAN_CONFLICT_THRESHOLD = -25
CONFLICT_THRESHOLD = -50
STRONG_CONFLICT_THRESHOLD = -75

LOW_MODEL_EDGE_THRESHOLD = 10  # abs(model_edge_score) < 10
WIDE_MARKET_RANGE_THRESHOLD = 1.5
HIGH_ROTATION_CONC_THRESHOLD = 0.78
ROTATION_RISK_PENALTY_THRESHOLD = -5

def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()

def safe_print(text: str = "") -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(str(text).encode("ascii", "replace").decode("ascii"))

def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    try:
        with path.open(newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []

def read_json(path: Path) -> Dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def to_float(x: Any) -> float:
    try:
        return float(x)
    except (ValueError, TypeError):
        return 0.0

def to_int(x: Any) -> int:
    try:
        return int(x)
    except (ValueError, TypeError):
        return 0

def analyze_row(row: Dict[str, Any], game_features: Dict[str, Any]) -> Dict[str, Any]:
    """Analyze a single advisory score row for NEUTRAL drivers."""
    game = row.get("game", "").strip()
    side = row.get("side", "").strip().upper()
    line = row.get("line", "").strip()
    projection = row.get("projection", "").strip()
    edge = row.get("edge", "").strip()
    units = row.get("units", "").strip()
    label = row.get("advisory_label", "").strip().upper()
    risk_flags = row.get("risk_flags", "").strip().upper()
    source = row.get("source", "").strip()
    
    scores = {
        "model_edge_score": to_float(row.get("model_edge_score", 0)),
        "recent_scoring_score": to_float(row.get("recent_scoring_score", 0)),
        "dashboard_scoring_score": to_float(row.get("dashboard_scoring_score", 0)),
        "rotation_concentration_score": to_float(row.get("rotation_concentration_score", 0)),
        "rotation_risk_penalty": to_float(row.get("rotation_risk_penalty", 0)),
        "bench_depth_score": to_float(row.get("bench_depth_score", 0)),
        "dreb_environment_score": to_float(row.get("dreb_environment_score", 0)),
        "market_range_penalty": to_float(row.get("market_range_penalty", 0)),
    }
    
    advisory_score = to_float(row.get("advisory_score", 0))
    
    # Determine NEUTRAL reasons
    reasons = []
    
    # Check thresholds
    if abs(advisory_score) < LEAN_SUPPORT_THRESHOLD:
        reasons.append(f"advisory_score({advisory_score:.2f}) < LEAN_SUPPORT_THRESHOLD({LEAN_SUPPORT_THRESHOLD})")
    
    # Component-level analysis
    missing_components = []
    neutral_components = []
    
    # 1. Model edge score
    mes = scores["model_edge_score"]
    if abs(mes) < LOW_MODEL_EDGE_THRESHOLD:
        if mes == 0:
            reasons.append(f"model_edge_score=0 (missing edge or projection/line)")
        else:
            reasons.append(f"model_edge_score({mes:.2f}) < LOW_MODEL_EDGE_THRESHOLD({LOW_MODEL_EDGE_THRESHOLD}) low statistical edge")
    elif mes < 0:
        reasons.append(f"model_edge_score({mes:.2f}) < 0 (edge against chosen side)")
    
    # 2. Recent scoring
    if scores["recent_scoring_score"] == 0:
        reasons.append("recent_scoring_score=0 (missing recent scoring data or line)")
    elif scores["recent_scoring_score"] < 0:
        reasons.append(f"recent_scoring_score({scores['recent_scoring_score']:.2f}) < 0")
    
    # 3. Dashboard scoring
    if scores["dashboard_scoring_score"] == 0:
        reasons.append("dashboard_scoring_score=0 (missing dash stats or line)")
    elif scores["dashboard_scoring_score"] < 0:
        reasons.append(f"dashboard_scoring_score({scores['dashboard_scoring_score']:.2f}) < 0")
    
    # 4. Rotation risk
    if scores["rotation_risk_penalty"] < ROTATION_RISK_PENALTY_THRESHOLD:
        reasons.append(f"rotation_risk_penalty({scores['rotation_risk_penalty']:.2f}) <= {ROTATION_RISK_PENALTY_THRESHOLD}")
    
    # 5. Rotation concentration
    if scores["rotation_concentration_score"] < 0:
        reasons.append("rotation_concentration_score < 0")
    
    # 6. Bench depth
    if scores["bench_depth_score"] < 0:
        reasons.append("bench_depth_score < 0")
    
    # 7. DREB environment
    if scores["dreb_environment_score"] < 0:
        reasons.append("dreb_environment_score < 0")
    
    # 8. Market range
    if scores["market_range_penalty"] < 0:
        reasons.append("market_range_penalty < 0 (wide market range)")
    
    # Missing data flags
    if not side or side in ("NAN", "NONE", ""):
        reasons.append("NO_SIDE (missing side/selection)")
    if not line or line in ("NAN", "NONE", ""):
        reasons.append("NO_LINE (missing market total)")
    if not projection or projection in ("NAN", "NONE", ""):
        reasons.append("NO_PROJECTION (missing model projection)")
    if not edge or edge in ("NAN", "NONE", ""):
        reasons.append("NO_EDGE (missing model edge)")
    
    # Risk flags
    if "NO_LINE" in risk_flags:
        reasons.append("risk_flag: NO_LINE")
    if "LOW_MODEL_EDGE" in risk_flags:
        reasons.append("risk_flag: LOW_MODEL_EDGE")
    if "NO_SIDE" in risk_flags:
        reasons.append("risk_flag: NO_SIDE")
    if "WIDE_MARKET_RANGE" in risk_flags:
        reasons.append("risk_flag: WIDE_MARKET_RANGE")
    if "HIGH_ROTATION_FRAGILITY" in risk_flags:
        reasons.append("risk_flag: HIGH_ROTATION_FRAGILITY")
    
    # If no specific reasons found and still NEUTRAL
    if not reasons and label == "NEUTRAL":
        reasons.append("advisory_score within NEUTRAL band (-25 to +25)")
    
    # Determine top driving factors
    top_factors = []
    if abs(advisory_score) < LEAN_SUPPORT_THRESHOLD:
        top_factors.append(f"advisory_score={advisory_score:.2f} in NEUTRAL band")
    if abs(scores["model_edge_score"]) < LOW_MODEL_EDGE_THRESHOLD:
        top_factors.append(f"model_edge_score={scores['model_edge_score']:.2f}")
    if scores["recent_scoring_score"] == 0:
        top_factors.append("recent_scoring_score=0")
    if scores["dashboard_scoring_score"] == 0:
        top_factors.append("dashboard_scoring_score=0")
    
    return {
        "game": game,
        "source": source,
        "side": side if side else "N/A",
        "line": line if line else "N/A",
        "projection": projection if projection else "N/A",
        "edge": edge if edge else "N/A",
        "advisory_score": advisory_score,
        "advisory_label": label,
        "risk_flags": risk_flags if risk_flags else "NONE",
        "advisory_score_components": scores,
        "reasons": reasons,
        "top_factors": top_factors[:3],
        "is_neutral": label == "NEUTRAL",
    }

def load_game_features_lookup(game_features_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Create a lookup dict for game features by game name."""
    lookup = {}
    for row in game_features_rows:
        game = row.get("game", "").strip()
        if game:
            lookup[game] = row
    return lookup

def run_audit(output_path: Optional[Path] = None) -> Dict[str, Any]:
    """Run the neutral label audit."""
    safe_print("=" * 80)
    safe_print("WNBA EDGE LAB — NEUTRAL LABEL AUDIT V21.9")
    safe_print("=" * 80)
    safe_print(f"Timestamp: {now_iso()}")
    safe_print("")
    
    # Load data
    queue_rows = read_csv(ADVISORY_QUEUE)
    score_rows = read_csv(ADVISORY_SCORES)
    summary = read_json(ADVISORY_SUMMARY)
    game_features_rows = read_csv(GAME_FEATURES)
    game_features_lookup = load_game_features_lookup(game_features_rows)
    
    if not score_rows:
        safe_print("❌ ADVISORY SCORES MISSING OR EMPTY")
        return {"verdict": "NEUTRAL_AUDIT_BLOCKED_NO_SCORES", "error": "No advisory scores found"}
    
    # Build game_features lookup
    game_features_dict = {}
    for row in game_features_rows:
        game = row.get("game", "").strip()
        if game:
            game_features_dict[game] = row
    
    # Analyze each score row
    analysis_results = []
    for row in score_rows:
        result = analyze_row(row, game_features_dict.get(row.get("game", "").strip(), {}))
        analysis_results.append(result)
    
    # Summary stats
    total = len(analysis_results)
    neutral_count = sum(1 for r in analysis_results if r["is_neutral"])
    non_neutral_count = total - neutral_count
    
    advisory_scores = [r["advisory_score"] for r in analysis_results]
    edge_scores = [r["advisory_score_components"]["model_edge_score"] for r in analysis_results]
    recent_scores = [r["advisory_score_components"]["recent_scoring_score"] for r in analysis_results]
    dash_scores = [r["advisory_score_components"]["dashboard_scoring_score"] for r in analysis_results]
    rotation_penalties = [r["advisory_score_components"]["rotation_risk_penalty"] for r in analysis_results]
    
    reason_counts = {}
    for r in analysis_results:
        for reason in r["reasons"]:
            reason_counts[reason] = reason_counts.get(reason, 0) + 1
    
    # Missing field counts
    missing_side = sum(1 for r in analysis_results if not r["side"] or r["side"] == "N/A")
    missing_line = sum(1 for r in analysis_results if r["line"] == "N/A")
    missing_proj = sum(1 for r in analysis_results if r["projection"] == "N/A")
    missing_edge = sum(1 for r in analysis_results if r["edge"] == "N/A")
    
    # Print detailed per-row analysis
    safe_print("📋 PER-ROW NEUTRAL ANALYSIS")
    safe_print("-" * 80)
    for i, r in enumerate(analysis_results, 1):
        safe_print(f"Row {i:2d} | Game: {r['game']:30s} | Score: {r['advisory_score']:6.2f} | Label: {r['advisory_label']:12s} | Side: {r['side']:5s} | Line: {r['line']:8s}")
        if r["reasons"]:
            for reason in r["reasons"][:4]:
                safe_print(f"         → {reason}")
        if len(r["reasons"]) > 4:
            safe_print(f"         → ... and {len(r['reasons']) - 4} more reasons")
        safe_print("")
    
    # Summary
    safe_print("📊 SUMMARY")
    safe_print("-" * 80)
    safe_print(f"Total rows:              {total}")
    safe_print(f"NEUTRAL:                 {neutral_count} ({100*neutral_count/total:.1f}%)")
    safe_print(f"Non-NEUTRAL:             {non_neutral_count} ({100*non_neutral_count/total:.1f}%)")
    safe_print(f"Advisory Score:          min={min(advisory_scores):.2f} max={max(advisory_scores):.2f} mean={sum(advisory_scores)/total:.2f}")
    safe_print(f"Model Edge Score:        min={min(edge_scores):.2f} max={max(edge_scores):.2f} mean={sum(edge_scores)/total:.2f}")
    safe_print(f"Recent Scoring:          min={min(recent_scores):.2f} max={max(recent_scores):.2f} mean={sum(recent_scores)/total:.2f}")
    safe_print(f"Dashboard Scoring:       min={min(dash_scores):.2f} max={max(dash_scores):.2f} mean={sum(dash_scores)/total:.2f}")
    safe_print(f"Rotation Penalty:        min={min(rotation_penalties):.2f} max={max(rotation_penalties):.2f} mean={sum(rotation_penalties)/total:.2f}")
    safe_print(f"")
    safe_print(f"Missing SIDE:            {missing_side}")
    safe_print(f"Missing LINE:            {missing_line}")
    safe_print(f"Missing PROJECTION:      {missing_proj}")
    safe_print(f"Missing EDGE:            {missing_edge}")
    safe_print(f"")
    
    safe_print("🔍 TOP NEUTRAL DRIVERS")
    for reason, count in sorted(reason_counts.items(), key=lambda x: -x[1])[:10]:
        safe_print(f"  {reason}: {count} rows")
    
    # Verdict
    if total == 0:
        verdict = "NEUTRAL_AUDIT_BLOCKED_NO_SCORES"
    elif neutral_count == total:
        verdict = "NEUTRAL_AUDIT_ALL_NEUTRAL"
    elif neutral_count > 0:
        verdict = "NEUTRAL_AUDIT_MIXED_LABELS"
    else:
        verdict = "NEUTRAL_AUDIT_ALL_ACTIONABLE"
    
    safe_print("")
    safe_print("🏁 FINAL VERDICT")
    safe_print(f"  {verdict}")
    safe_print("")
    
    # Safety footer
    safe_print("🔒 SAFETY FOOTER")
    safe_print("  • Manual approval required")
    safe_print("  • No auto-betting")
    safe_print("  • No formula changes")
    safe_print("  • No staking changes")
    safe_print("  • No threshold changes")
    safe_print("")
    safe_print("=" * 80)
    
    result = {
        "verdict": verdict,
        "total_rows": total,
        "neutral_count": neutral_count,
        "non_neutral_count": non_neutral_count,
        "advisory_score_stats": {
            "min": min(advisory_scores),
            "max": max(advisory_scores),
            "mean": sum(advisory_scores) / total,
        },
        "edge_score_stats": {
            "min": min(edge_scores),
            "max": max(edge_scores),
            "mean": sum(edge_scores) / total,
        },
        "missing_fields": {
            "side": missing_side,
            "line": missing_line,
            "projection": missing_proj,
            "edge": missing_edge,
        },
        "reason_counts": reason_counts,
        "rows": analysis_results,
    }
    
    if output_path:
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
            safe_print(f"📄 Report written to: {output_path}")
        except Exception as e:
            safe_print(f"⚠️ Failed to write report: {e}")
    
    return result

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="WNBA Neutral Label Audit V21.9")
    parser.add_argument("--output", "-o", type=Path, help="Write report JSON to file")
    args = parser.parse_args()
    
    result = run_audit(args.output)
    return 0 if result.get("verdict") in ("NEUTRAL_AUDIT_ALL_NEUTRAL", "NEUTRAL_AUDIT_MIXED_LABELS") else 2

if __name__ == "__main__":
    sys.exit(main())