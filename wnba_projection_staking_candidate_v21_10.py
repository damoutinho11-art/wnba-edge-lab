#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WNBA Edge Lab — Projection/Staking Candidate Generator V21.10

DRY-RUN ONLY by default. Does NOT write to live projection files.
Creates candidate files with _candidate_v21_10 suffix for review.

This is NOT production code. This is a candidate generator to restore
model research capability while the official projection pipeline is external.

Formula policy:
- Transparent baseline formulas only, fully documented in comments and summary JSON.
- Projection: conservative baseline using available market + team stats.
- Edge = projection - line
- Side = OVER if edge > 0 else UNDER
- Confidence: conservative, based on edge magnitude and market range
- Suggested units: conservative, only >0 if edge and confidence pass strict rules
- If insufficient inputs: projection_status = INSUFFICIENT_INPUTS, suggested_units = 0

Safety:
- No overwrite of live projection files by default
- Manual approval required
- No auto-betting
- Formula status marked as CANDIDATE_DRY_RUN
- Manual_approval_required = True
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "wnba_outputs"

# ── Output paths (candidate only) ──────────────────────────────────────
PROJECTION_CANDIDATE = OUT / "projections_with_stakes_candidate_v21_10.csv"
RECOMMENDED_CANDIDATE = OUT / "recommended_bets_candidate_v21_10.csv"
SUMMARY_CANDIDATE = OUT / "projection_staking_candidate_summary_v21_10.json"

# ── Input paths ────────────────────────────────────────────────────────
GAME_FEATURES = OUT / "game_model_features_v21.csv"
TEAM_FEATURES = OUT / "team_features_v21.csv"
MARKET_FEATURES = OUT / "market_features_v21.csv"

# ── Formula constants (transparent, documented) ────────────────────────
MODEL_VERSION = "v21.10.candidate.dry_run"

# Confidence thresholds
EDGE_UNIT_CONFIDENCE_THRESHOLD = 1.0      # min edge for unit > 0
CONFIDENCE_UNIT_THRESHOLD = 50.0           # min confidence for unit > 0
MAX_SUGGESTED_UNITS = 0.5                  # cap per game
EDGE_TO_UNIT_SCALING = 10.0                # edge points per 1.0 unit (conservative)

# Projection baseline: conservative average of market and team recent scoring
# Formula: projection = (market_total_mean + combined_playerlog_pts_l5) / 2
# When market missing, use team combined recent; when both missing, INSUFFICIENT_INPUTS

# Minimum data requirements
MIN_GAMES_FOR_PROJECTION = 1  # at least one of (market, team) must exist


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
    except Exception:
        return pd.DataFrame()


def write_csv(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def write_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")


def to_float(x: Any, default: float = np.nan) -> float:
    try:
        v = pd.to_numeric(x, errors="coerce")
        if pd.isna(v):
            return default
        return float(v)
    except Exception:
        return default


def to_int(x: Any, default: int = 0) -> int:
    try:
        v = pd.to_numeric(x, errors="coerce")
        if pd.isna(v):
            return default
        return int(v)
    except Exception:
        return default


def normalize_team_code(code: str) -> str:
    """Normalize team code to standard 3-char format."""
    if not code or pd.isna(code):
        return ""
    s = str(code).strip().upper()
    # Handle known variations
    mapping = {
        "LAS": "LAS", "LA": "LAS",
        "LVA": "LVA", "LV": "LVA",
        "GSV": "GSV", "GS": "GSV",
        "NYL": "NYL", "NY": "NYL",
        "WAS": "WAS", "WSH": "WAS",
        "PHX": "PHX", "PHO": "PHX",
        "SEA": "SEA",
        "CON": "CON",
        "ATL": "ATL",
        "CHI": "CHI",
        "DAL": "DAL",
        "IND": "IND",
        "MIN": "MIN",
        "POR": "POR", "PDX": "POR",
        "TOR": "TOR",
        "SEA": "SEA",
    }
    return mapping.get(s, s[:3] if len(s) >= 3 else s)


def build_team_lookup(team_features: pd.DataFrame) -> Dict[str, Dict[str, float]]:
    """Build team features lookup by team code."""
    if team_features.empty or "team" not in team_features.columns:
        return {}

    lookup = {}
    for _, row in team_features.iterrows():
        team_code = normalize_team_code(row.get("team", ""))
        if not team_code:
            continue
        lookup[team_code] = {
            "dash_pts": to_float(row.get("dash_pts", np.nan)),
            "dash_plus_minus": to_float(row.get("dash_plus_minus", np.nan)),
            "playerlog_team_pts_l5": to_float(row.get("playerlog_team_pts_l5", np.nan)),
            "team_pts_for_l5": to_float(row.get("team_pts_for_l5", np.nan)),
            "starter_minutes_concentration": to_float(row.get("starter_minutes_concentration", np.nan)),
            "bench_minutes_share": to_float(row.get("bench_minutes_share", np.nan)),
            "dreb_allowed": to_float(row.get("dreb_allowed_blended_dreb_allowed", np.nan)),
        }
    return lookup


def build_market_lookup(market_features: pd.DataFrame) -> Dict[Tuple[str, str], Dict[str, float]]:
    """Build market features lookup by (home_code, away_code)."""
    if market_features.empty:
        return {}

    lookup = {}
    for _, row in market_features.iterrows():
        home = normalize_team_code(row.get("home_team", ""))
        away = normalize_team_code(row.get("away_team", ""))
        if home and away:
            lookup[(home, away)] = {
                "market_total_mean": to_float(row.get("market_total_mean", np.nan)),
                "market_total_median": to_float(row.get("market_total_median", np.nan)),
                "market_total_min": to_float(row.get("market_total_min", np.nan)),
                "market_total_max": to_float(row.get("market_total_max", np.nan)),
                "market_total_range": to_float(row.get("market_total_range", np.nan)),
                "market_total_books": to_int(row.get("market_total_books", 0)),
            }
            # Also add reverse lookup
            lookup[(away, home)] = lookup[(home, away)]
    return lookup


def get_game_from_game_features(row: pd.Series) -> Optional[str]:
    """Extract game string from game_features row."""
    game = row.get("game", "")
    if pd.isna(game) or not game or str(game).strip().lower() == "nan":
        # Try to reconstruct from away/home
        away = str(row.get("away_team", "")).strip().upper()
        home = str(row.get("home_team", "")).strip().upper()
        if away and home:
            return f"{away} @ {home}"
        return None
    game = str(game).strip()
    if game.lower() == "nan":
        away = str(row.get("away_team", "")).strip().upper()
        home = str(row.get("home_team", "")).strip().upper()
        if away and home:
            return f"{away} @ {home}"
        return None
    return game


def compute_projection(
    market: Dict[str, float],
    away_tf: Dict[str, float],
    home_tf: Dict[str, float],
    line: float,
) -> Tuple[Optional[float], str]:
    """
    Compute projection using conservative baseline.

    Returns (projection, projection_status)
    """
    market_total = market.get("market_total_mean", np.nan)
    away_recent = away_tf.get("playerlog_team_pts_l5", np.nan) or away_tf.get("team_pts_for_l5", np.nan)
    home_recent = home_tf.get("playerlog_team_pts_l5", np.nan) or home_tf.get("team_pts_for_l5", np.nan)

    has_market = not pd.isna(market_total)
    has_away_recent = not pd.isna(away_recent)
    has_home_recent = not pd.isna(home_recent)
    has_combined_recent = has_away_recent and has_home_recent

    if not has_market and not has_combined_recent:
        return None, "INSUFFICIENT_INPUTS"

    if has_market and has_combined_recent:
        combined_recent = away_recent + home_recent
        # Weighted average: 60% market, 40% team recent
        projection = 0.6 * market_total + 0.4 * combined_recent
        return projection, "MARKET_TEAM_BLEND"
    elif has_market:
        projection = market_total
        return projection, "MARKET_ONLY"
    else:  # has_combined_recent only
        combined_recent = away_recent + home_recent
        projection = combined_recent
        return projection, "TEAM_RECENT_ONLY"


def compute_confidence(
    projection: float,
    line: float,
    market: Dict[str, float],
    away_tf: Dict[str, float],
    home_tf: Dict[str, float],
) -> float:
    """
    Compute confidence score (0-100) based on:
    - Edge magnitude
    - Market range (tighter = higher confidence)
    - Availability of data sources
    """
    edge = abs(projection - line)

    # Base confidence from edge
    if edge >= 3.0:
        conf = 75
    elif edge >= 2.0:
        conf = 65
    elif edge >= 1.0:
        conf = 55
    elif edge >= 0.5:
        conf = 45
    else:
        conf = 35

    # Penalize wide market range
    market_range = market.get("market_total_range", 0)
    if market_range > 2.0:
        conf -= 15
    elif market_range > 1.0:
        conf -= 8
    elif market_range > 0.5:
        conf -= 3

    # Boost for multiple data sources
    data_sources = 1  # projection exists
    if market.get("market_total_books", 0) >= 5:
        data_sources += 1
    if not pd.isna(away_tf.get("dash_pts", np.nan)) and not pd.isna(home_tf.get("dash_pts", np.nan)):
        data_sources += 1

    if data_sources >= 3:
        conf += 5
    elif data_sources >= 2:
        conf += 2

    # Clamp
    return max(20.0, min(90.0, conf))


def compute_suggested_units(
    edge: float,
    confidence: float,
    style: str = "conservative",
) -> float:
    """
    Compute suggested units using conservative Kelly-inspired formula.

    Returns 0.0 unless edge and confidence pass strict thresholds.
    """
    if abs(edge) < EDGE_UNIT_CONFIDENCE_THRESHOLD:
        return 0.0
    if confidence < CONFIDENCE_UNIT_THRESHOLD:
        return 0.0

    # Conservative: units = (edge / scaling) * (confidence / 100)
    raw_units = (abs(edge) / EDGE_TO_UNIT_SCALING) * (confidence / 100.0)

    # Cap at conservative max
    units = min(raw_units, MAX_SUGGESTED_UNITS)

    # Round to 2 decimal places
    return round(units, 2)


def determine_signal(
    edge: float,
    confidence: float,
    units: float,
) -> str:
    """Determine signal label."""
    if units <= 0:
        return "NO_BET"

    if edge > 0:
        if confidence >= 75 and abs(edge) >= 3.0:
            return "STRONG_OVER"
        elif confidence >= 60 and abs(edge) >= 2.0:
            return "LEAN_OVER"
        else:
            return "WATCHLIST_OVER"
    else:
        if confidence >= 75 and abs(edge) >= 3.0:
            return "STRONG_UNDER"
        elif confidence >= 60 and abs(edge) >= 2.0:
            return "LEAN_UNDER"
        else:
            return "WATCHLIST_UNDER"


def compute_stake_reason(
    edge: float,
    confidence: float,
    units: float,
    signal: str,
    projection_status: str,
) -> str:
    """Generate human-readable stake reason."""
    parts = []

    if units <= 0:
        if abs(edge) < EDGE_UNIT_CONFIDENCE_THRESHOLD:
            parts.append(f"edge {edge:+.1f} below {EDGE_UNIT_CONFIDENCE_THRESHOLD} threshold")
        elif confidence < CONFIDENCE_UNIT_THRESHOLD:
            parts.append(f"confidence {confidence:.0f} below {CONFIDENCE_UNIT_THRESHOLD} threshold")
        else:
            parts.append("no bet")
        return "No stake: " + "; ".join(parts)

    if signal.startswith("STRONG"):
        parts.append(f"strong signal: {abs(edge):.1f} pt edge, {confidence:.0f}% conf")
    elif signal.startswith("LEAN"):
        parts.append(f"lean signal: {abs(edge):.1f} pt edge, {confidence:.0f}% conf")
    else:
        parts.append(f"watchlist: {abs(edge):.1f} pt edge, {confidence:.0f}% conf")

    parts.append(f"candidate units: {units:.2f}")
    parts.append(f"projection: {projection_status}")

    return "; ".join(parts)


def generate_candidates(
    write_candidate: bool = False,
) -> Dict[str, Any]:
    """Main generation function."""

    safe_print("=" * 70)
    safe_print("WNBA EDGE LAB — PROJECTION/STAKING CANDIDATE V21.10")
    safe_print("DRY-RUN MODE" if not write_candidate else "WRITE-CANDIDATE MODE")
    safe_print("=" * 70)
    safe_print(f"Timestamp: {now_iso()}")
    safe_print("")

    # Load inputs
    game_features = read_csv(GAME_FEATURES)
    team_features = read_csv(TEAM_FEATURES)
    market_features = read_csv(MARKET_FEATURES)

    if game_features.empty:
        safe_print("❌ No game features found!")
        return {"verdict": "NO_GAME_FEATURES", "rows": 0}

    safe_print(f"Loaded: {len(game_features)} game rows, {len(team_features)} team rows, {len(market_features)} market rows")

    # Build lookups
    team_lookup = build_team_lookup(team_features)
    market_lookup = build_market_lookup(market_features)

    safe_print(f"Team lookup: {len(team_lookup)} teams")
    safe_print(f"Market lookup: {len(market_lookup)} matchups")

    # Process each game
    candidates = []
    stats = {
        "total": 0,
        "with_projection": 0,
        "with_edge": 0,
        "with_units": 0,
        "insufficient_inputs": 0,
        "signals": {},
    }

    for _, row in game_features.iterrows():
        game = get_game_from_game_features(row)
        if not game:
            continue

        away = normalize_team_code(row.get("away_team", ""))
        home = normalize_team_code(row.get("home_team", ""))

        if not away or not home:
            continue

        # Get line from game features or market
        line = to_float(row.get("line", np.nan))
        if pd.isna(line):
            # Try market lookup
            mkt = market_lookup.get((home, away), {})
            line = to_float(mkt.get("market_total_mean", np.nan))

        if pd.isna(line):
            # Skip games without line
            continue

        # Get data
        market = market_lookup.get((home, away), {})
        if not market:
            market = market_lookup.get((away, home), {})

        away_tf = team_lookup.get(away, {})
        home_tf = team_lookup.get(home, {})

        # Compute projection
        projection, proj_status = compute_projection(market, away_tf, home_tf, line)

        # Compute edge
        edge = None
        if projection is not None:
            edge = projection - line

        # Compute confidence
        confidence = None
        if projection is not None:
            confidence = compute_confidence(projection, line, market, away_tf, home_tf)

        # Compute side
        side = ""
        if edge is not None:
            side = "OVER" if edge > 0 else "UNDER" if edge < 0 else ""

        # Compute units
        units = 0.0
        signal = "NO_BET"
        if edge is not None and confidence is not None:
            units = compute_suggested_units(edge, confidence)
            signal = determine_signal(edge, confidence, units)

        # Stake reason
        reason = compute_stake_reason(edge or 0, confidence or 0, units, signal, proj_status)

        # Begin_time / commence_time from market or schedule
        commence_time = ""
        mkt = market_lookup.get((home, away), {}) or market_lookup.get((away, home), {})
        # Note: market_features doesn't have commence_time, would need schedule
        # For candidate, use empty or generate from current date

        # Build candidate row
        candidate = {
            "game": game,
            "away_team": away,
            "home_team": home,
            "line": round(line, 2) if not pd.isna(line) else "",
            "projection": round(projection, 2) if projection is not None else "",
            "edge": round(edge, 2) if edge is not None else "",
            "side": side,
            "confidence": round(confidence, 2) if confidence is not None else "",
            "suggested_units": round(units, 2) if units > 0 else "",
            "recommended_bet": signal,
            "commence_time": commence_time,
            "model_version": MODEL_VERSION,
            "formula_status": f"CANDIDATE_DRY_RUN:{proj_status}",
            "manual_approval_required": True,
            "stake_reason": reason,
            "market_total_range": round(market.get("market_total_range", 0), 2) if market else "",
            "market_total_books": market.get("market_total_books", 0) if market else "",
        }

        candidates.append(candidate)

        # Update stats
        stats["total"] += 1
        if projection is not None:
            stats["with_projection"] += 1
        if edge is not None:
            stats["with_edge"] += 1
        if units > 0:
            stats["with_units"] += 1
        if proj_status == "INSUFFICIENT_INPUTS":
            stats["insufficient_inputs"] += 1
        stats["signals"][signal] = stats["signals"].get(signal, 0) + 1

    # Print summary
    safe_print("")
    safe_print("📊 CANDIDATE GENERATION SUMMARY")
    safe_print("-" * 70)
    safe_print(f"Total games:           {stats['total']}")
    safe_print(f"With projection:       {stats['with_projection']}")
    safe_print(f"With edge:             {stats['with_edge']}")
    safe_print(f"With units > 0:        {stats['with_units']}")
    safe_print(f"Insufficient inputs:   {stats['insufficient_inputs']}")
    safe_print("")
    safe_print("Signal breakdown:")
    for sig, cnt in sorted(stats["signals"].items(), key=lambda x: -x[1]):
        safe_print(f"  {sig}: {cnt}")

    safe_print("")

    # Build summary
    summary = {
        "timestamp": now_iso(),
        "model_version": MODEL_VERSION,
        "status": "CANDIDATE_DRY_RUN",
        "inputs": {
            "game_features_count": len(game_features),
            "team_features_count": len(team_features),
            "market_features_count": len(market_features),
        },
        "stats": stats,
        "formula": {
            "projection": "weighted_average(market_total_mean=0.6, team_combined_recent=0.4) or market_only or team_recent_only",
            "edge": "projection - line",
            "side": "OVER if edge > 0 else UNDER",
            "confidence": "base_from_edge + market_range_penalty + data_source_bonus (clamped 20-90)",
            "suggested_units": f"min(|edge|/{EDGE_TO_UNIT_SCALING} * confidence/100, {MAX_SUGGESTED_UNITS}) if |edge|>={EDGE_UNIT_CONFIDENCE_THRESHOLD} and confidence>={CONFIDENCE_UNIT_THRESHOLD} else 0",
            "signal": "STRONG/LEAN/WATCHLIST OVER/UNDER based on edge magnitude and confidence",
        },
        "constants": {
            "EDGE_UNIT_CONFIDENCE_THRESHOLD": EDGE_UNIT_CONFIDENCE_THRESHOLD,
            "CONFIDENCE_UNIT_THRESHOLD": CONFIDENCE_UNIT_THRESHOLD,
            "MAX_SUGGESTED_UNITS": MAX_SUGGESTED_UNITS,
            "EDGE_TO_UNIT_SCALING": EDGE_TO_UNIT_SCALING,
        },
        "candidates": candidates,
    }

    # Print sample candidates
    safe_print("")
    safe_print("📋 SAMPLE CANDIDATES (first 5)")
    safe_print("-" * 70)
    for c in candidates[:5]:
        safe_print(f"  {c['game']:20s} line={str(c['line']):>7s} proj={str(c['projection']):>7s} edge={str(c['edge']):>6s} side={c['side']:5s} conf={str(c['confidence']):>5s} units={str(c['suggested_units']):>4s} signal={c['recommended_bet']}")

    # Write candidate files if requested
    if write_candidate:
        if not candidates:
            safe_print("")
            safe_print("⚠️ No candidates generated, nothing to write.")
        else:
            out_proj = []
            out_recs = []

            for c in candidates:
                if c["projection"]:
                    # projections_with_stakes format
                    out_proj.append({
                        "game": c["game"],
                        "away_team": c["away_team"],
                        "home_team": c["home_team"],
                        "line": c["line"],
                        "projection": c["projection"],
                        "edge": c["edge"],
                        "side": c["side"],
                        "confidence": c["confidence"],
                        "suggested_units": c["suggested_units"],
                        "recommended_bet": c["recommended_bet"],
                        "commence_time": c["commence_time"],
                        "model_version": c["model_version"],
                        "formula_status": c["formula_status"],
                        "manual_approval_required": c["manual_approval_required"],
                        "stake_reason": c["stake_reason"],
                        "market_total_range": c["market_total_range"],
                        "market_total_books": c["market_total_books"],
                    })

                    out_recs.append({
                        "game": c["game"],
                        "away_team": c["away_team"],
                        "home_team": c["home_team"],
                        "line": c["line"],
                        "projection": c["projection"],
                        "edge": c["edge"],
                        "side": c["side"],
                        "confidence": c["confidence"],
                        "suggested_units": c["suggested_units"],
                        "recommended_bet": c["recommended_bet"],
                        "commence_time": c["commence_time"],
                        "model_version": c["model_version"],
                        "formula_status": c["formula_status"],
                        "manual_approval_required": c["manual_approval_required"],
                        "stake_reason": c["stake_reason"],
                    })

            # Write candidate files
            if out_proj:
                df_proj = pd.DataFrame(out_proj)
                write_csv(PROJECTION_CANDIDATE, df_proj)
                safe_print(f"✅ Written: {PROJECTION_CANDIDATE} ({len(out_proj)} rows)")

            if out_recs:
                df_recs = pd.DataFrame(out_recs)
                write_csv(RECOMMENDED_CANDIDATE, df_recs)
                safe_print(f"✅ Written: {RECOMMENDED_CANDIDATE} ({len(out_recs)} rows)")

            # Summary written separately (not in production outputs)
            safe_print(f"✅ Summary: {SUMMARY_CANDIDATE}")

    # Always write summary JSON
    write_json(SUMMARY_CANDIDATE, summary)
    safe_print(f"✅ Summary JSON: {SUMMARY_CANDIDATE}")

    # Safety footer
    safe_print("")
    safe_print("🔒 SAFETY FOOTER")
    safe_print("  • Manual approval required")
    safe_print("  • No auto-betting")
    safe_print("  • No formula changes to production")
    safe_print("  • No staking changes to production")
    safe_print("  • No threshold changes to production")
    safe_print("  • Candidate outputs only — not live")
    safe_print("")
    safe_print("=" * 70)

    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description="Projection/Staking Candidate Generator V21.10")
    parser.add_argument("--write-candidate", action="store_true",
                        help="Write candidate files (dry-run by default)")
    args = parser.parse_args()

    summary = generate_candidates(write_candidate=args.write_candidate)

    if not summary.get("candidates"):
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())