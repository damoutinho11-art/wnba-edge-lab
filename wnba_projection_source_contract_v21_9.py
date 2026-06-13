#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WNBA Edge Lab — Projection/Staking Source Contract Guard V21.9

Read-only diagnostic that reports projection/staking source availability
and validates schema contracts for downstream consumers.
"""

from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "wnba_outputs"

# ── Required schema contracts ───────────────────────────────────────────

PROJECTIONS_STAKES_REQUIRED = [
    "game",
    "away_team",
    "home_team",
    "line",
    "projection",
    "edge",
    "side",
    "confidence",
    "suggested_units",
    "recommended_bet",
    "commence_time",
]

PROJECTIONS_STAKES_ALIASES = {
    "confidence": ["confidence", "confidence_score", "Confidence", "ConfidenceScore"],
    "suggested_units": ["suggested_units", "SuggestedUnits", "suggested_units_raw", "SuggestedUnitsRaw"],
    "recommended_bet": ["recommended_bet", "Selection", "signal", "Signal", "FinalSignalNormalized"],
    "commence_time": ["commence_time", "CommenceTime", "game_start_utc", "GameStartUTC"],
    "side": ["side", "Side", "Selection"],
    "edge": ["edge", "Edge", "projection_minus_line"],
    "projection": ["projection", "Projection", "projected_total", "model_total"],
    "line": ["line", "Line", "market_line", "consensus_line", "market_total"],
    "away_team": ["away_team", "away", "away팀", "Away", "away_abbreviation"],
    "home_team": ["home_team", "home", "Home", "home_abbreviation"],
    "game": ["game", "Game", "matchup", "Matchup"],
}

RECOMMENDED_BETS_REQUIRED = [
    "game",
    "recommended_bet",
    "side",
    "projection",
    "line",
    "edge",
    "suggested_units",
    "confidence",
    "commence_time",
]

RECOMMENDED_BETS_ALIASES = {
    "confidence": ["confidence", "confidence_score", "Confidence", "ConfidenceScore"],
    "suggested_units": ["suggested_units", "SuggestedUnits", "suggested_units_raw", "SuggestedUnitsRaw"],
    "recommended_bet": ["recommended_bet", "Selection", "signal", "Signal", "FinalSignalNormalized"],
    "commence_time": ["commence_time", "CommenceTime", "game_start_utc", "GameStartUTC"],
    "side": ["side", "Side", "Selection"],
    "edge": ["edge", "Edge", "projection_minus_line"],
    "projection": ["projection", "Projection", "projected_total", "model_total"],
    "line": ["line", "Line", "market_line", "consensus_line", "market_total"],
    "game": ["game", "Game", "matchup", "Matchup"],
}

# ── File paths ────────────────────────────────────────────────────────────

FILES_TO_CHECK = {
    "projections_with_stakes": OUT / "projections_with_stakes.csv",
    "recommended_bets": OUT / "recommended_bets.csv",
    "game_model_features": OUT / "game_model_features_v21.csv",
    "hermes_advisory_queue": OUT / "hermes_advisory_queue_v21.csv",
}


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


def normalize_cols(rows: List[Dict[str, str]]) -> List[Dict[str, str]]:
    """Normalize column names to lowercase for matching."""
    if not rows:
        return []
    out = []
    for row in rows:
        norm = {}
        for k, v in row.items():
            norm[k.strip().lower()] = v
        out.append(norm)
    return out


def resolve_column(rows: List[Dict[str, str]], required: str, aliases: List[str]) -> Optional[str]:
    """Find the actual column name that matches required field."""
    if not rows:
        return None
    cols = {k.lower(): k for k in rows[0].keys()}
    for alias in aliases:
        if alias.lower() in cols:
            return cols[alias.lower()]
    # Fuzzy: check if required is a prefix of any column
    for c in cols:
        if c.startswith(required.lower()):
            return cols[c]
    return None


def check_schema(rows: List[Dict[str, str]], required: List[str], aliases_map: Dict[str, List[str]]) -> Tuple[bool, List[str], List[str]]:
    """Check if CSV has all required columns (with aliases). Returns (valid, missing, found_columns)."""
    if not rows:
        return False, required, []
    found = []
    missing = []
    for req in required:
        col = resolve_column(rows, req, aliases_map.get(req, [req]))
        if col:
            found.append(f"{req} -> {col}")
        else:
            missing.append(req)
    return len(missing) == 0, missing, found


def get_game_date_range(rows: List[Dict[str, str]]) -> Tuple[Optional[str], Optional[str]]:
    """Extract min/max game dates from rows."""
    if not rows:
        return None, None
    dates = []
    col_candidates = ["commence_time", "date", "game_date", "game_start_utc"]
    for row in rows:
        for c in col_candidates:
            if c in row and row[c]:
                val = row[c].strip()
                if val:
                    try:
                        # Try parsing various formats
                        for fmt in ["%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%dT%H:%M:%S+00:00", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"]:
                            try:
                                parse_val = val if "T" in val else val[:19] if len(val) >= 19 else val
                                dt = datetime.strptime(parse_val, fmt)
                                dates.append(dt)
                                break
                            except ValueError:
                                continue
                    except Exception:
                        pass
    if dates:
        return min(dates).strftime("%Y-%m-%d"), max(dates).strftime("%Y-%m-%d")
    return None, None


def get_fresh_games(game_features_rows: List[Dict[str, str]]) -> List[str]:
    """Get list of fresh games from game_model_features."""
    fresh = []
    for row in game_features_rows:
        game = row.get("game") or row.get("Game") or row.get("matchup")
        if game and "nan" not in game.lower():
            fresh.append(game.strip())
    return fresh


def get_covered_games(proj_rows: List[Dict[str, str]], col_map: Dict[str, str]) -> List[str]:
    """Get list of games covered by projections."""
    covered = []
    if not proj_rows or not col_map.get("game"):
        return []
    game_col = col_map["game"]
    for row in proj_rows:
        game = row.get(game_col)
        if game and "nan" not in game.lower():
            covered.append(game.strip())
    return covered


def is_stale(max_date: Optional[str]) -> bool:
    """Check if max date is older than today."""
    if not max_date:
        return True
    try:
        max_dt = datetime.strptime(max_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
        today = datetime.now(timezone.utc)
        return max_dt < today
    except Exception:
        return True


def run_contract_check(output_path: Optional[Path] = None) -> Dict[str, Any]:
    """Run the full contract check."""
    safe_print("=" * 80)
    safe_print("WNBA EDGE LAB — PROJECTION/STAKING SOURCE CONTRACT V21.9")
    safe_print("=" * 80)
    safe_print(f"Timestamp: {now_iso()}")
    safe_print("")

    # Load all files
    file_data = {}
    for name, path in FILES_TO_CHECK.items():
        rows = read_csv(path)
        normalized = normalize_cols(rows)
        file_data[name] = {
            "path": path,
            "exists": path.exists(),
            "rows": rows,
            "normalized": normalized,
            "row_count": len(rows),
        }

    # Check projections_with_stakes
    proj = file_data["projections_with_stakes"]
    recs = file_data["recommended_bets"]
    gmf = file_data["game_model_features"]
    queue = file_data["hermes_advisory_queue"]

    safe_print("📁 FILE EXISTENCE & ROW COUNTS")
    safe_print("-" * 80)
    for name, data in file_data.items():
        exists = "✅" if data["exists"] else "❌"
        safe_print(f"  {exists} {name}: rows={data['row_count']}")

    # Schema validation
    safe_print("")
    safe_print("📋 SCHEMA VALIDATION")
    safe_print("-" * 80)

    proj_valid, proj_missing, proj_found = check_schema(
        proj["normalized"], PROJECTIONS_STAKES_REQUIRED, PROJECTIONS_STAKES_ALIASES
    )
    recs_valid, recs_missing, recs_found = check_schema(
        recs["normalized"], RECOMMENDED_BETS_REQUIRED, RECOMMENDED_BETS_ALIASES
    )

    safe_print("projections_with_stakes.csv:")
    if proj_found:
        for f in proj_found:
            safe_print(f"  ✅ {f}")
    if proj_missing:
        for m in proj_missing:
            safe_print(f"  ❌ MISSING: {m}")
    if not proj["exists"]:
        safe_print("  ❌ FILE DOES NOT EXIST")

    safe_print("")
    safe_print("recommended_bets.csv:")
    if recs_found:
        for f in recs_found:
            safe_print(f"  ✅ {f}")
    if recs_missing:
        for m in recs_missing:
            safe_print(f"  ❌ MISSING: {m}")
    if not recs["exists"]:
        safe_print("  ❌ FILE DOES NOT EXIST")

    # Date ranges
    safe_print("")
    safe_print("📅 DATE RANGES")
    safe_print("-" * 80)

    proj_min, proj_max = get_game_date_range(proj["normalized"])
    recs_min, recs_max = get_game_date_range(recs["normalized"])
    gmf_min, gmf_max = get_game_date_range(gmf["normalized"])

    if proj_min:
        safe_print(f"projections_with_stakes: {proj_min} to {proj_max} (stale: {is_stale(proj_max)})")
    else:
        safe_print("projections_with_stakes: NO DATE INFO")

    if recs_min:
        safe_print(f"recommended_bets: {recs_min} to {recs_max} (stale: {is_stale(recs_max)})")
    else:
        safe_print("recommended_bets: NO DATE INFO")

    if gmf_min:
        safe_print(f"game_model_features (fresh): {gmf_min} to {gmf_max}")

    # Fresh games coverage
    safe_print("")
    safe_print("🎯 FRESH GAMES COVERAGE")
    safe_print("-" * 80)

    fresh_games = get_fresh_games(gmf["rows"])
    safe_print(f"Fresh games from game_model_features: {len(fresh_games)}")
    for g in fresh_games:
        safe_print(f"  - {g}")

    proj_col_map = {}
    for req in ["game", "away_team", "home_team", "commence_time"]:
        proj_col_map[req] = resolve_column(
            proj["normalized"], req, PROJECTIONS_STAKES_ALIASES.get(req, [req])
        )
    covered = get_covered_games(proj["normalized"], proj_col_map)

    safe_print(f"Games in projections_with_stakes: {len(covered)}")
    for g in covered:
        safe_print(f"  - {g}")

    missing = [g for g in fresh_games if g not in covered]
    safe_print(f"Fresh games MISSING from projections: {len(missing)}")
    for g in missing:
        safe_print(f"  - {g}")

    # Verdict
    safe_print("")
    safe_print("🏁 FINAL VERDICT")
    safe_print("-" * 80)

    verdict = "PROJECTION_SOURCE_READY"
    reasons = []

    if not proj["exists"] or not recs["exists"]:
        verdict = "PROJECTION_SOURCE_MISSING"
        reasons.append("One or both source files missing")
    elif proj["row_count"] == 0 or recs["row_count"] == 0:
        verdict = "PROJECTION_SOURCE_EMPTY"
        reasons.append("Source files exist but are empty")
    elif not proj_valid or not recs_valid:
        verdict = "PROJECTION_SOURCE_SCHEMA_INVALID"
        reasons.append("Schema validation failed")
    elif is_stale(proj_max):
        verdict = "PROJECTION_SOURCE_STALE"
        reasons.append(f"projections_with_stakes max date ({proj_max}) is stale")
    elif missing:
        verdict = "PROJECTION_SOURCE_INCOMPLETE"
        reasons.append(f"{len(missing)} fresh games not covered by projections")

    if verdict == "PROJECTION_SOURCE_READY":
        safe_print(f"  ✅ {verdict}")
    else:
        safe_print(f"  ❌ {verdict}")
        for r in reasons:
            safe_print(f"     → {r}")

    # Safety footer
    safe_print("")
    safe_print("🔒 SAFETY FOOTER")
    safe_print("  • Manual approval required")
    safe_print("  • No auto-betting")
    safe_print("  • No formula changes")
    safe_print("  • No staking changes")
    safe_print("  • No threshold changes")
    safe_print("")
    safe_print("=" * 80)

    result = {
        "timestamp": now_iso(),
        "verdict": verdict,
        "reasons": reasons,
        "files": {
            name: {
                "exists": data["exists"],
                "row_count": data["row_count"],
                "path": str(data["path"]),
            }
            for name, data in file_data.items()
        },
        "schema": {
            "projections_with_stakes": {
                "valid": proj_valid,
                "missing": proj_missing,
                "found": proj_found,
                "date_range": {"min": proj_min, "max": proj_max},
                "stale": is_stale(proj_max) if proj_max else True,
            },
            "recommended_bets": {
                "valid": recs_valid,
                "missing": recs_missing,
                "found": recs_found,
                "date_range": {"min": recs_min, "max": recs_max},
                "stale": is_stale(recs_max) if recs_max else True,
            },
        },
        "coverage": {
            "fresh_games_count": len(fresh_games),
            "fresh_games": fresh_games,
            "covered_games": covered,
            "missing_games": missing,
        },
    }

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(result, indent=2, default=str), encoding="utf-8")
        safe_print(f"Report written to: {output_path}")

    return result


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Projection/Staking Source Contract Guard V21.9")
    parser.add_argument("--output", "-o", type=Path, help="Write report JSON to file")
    args = parser.parse_args()

    result = run_contract_check(args.output)

    # Map verdict to exit code
    verdict_codes = {
        "PROJECTION_SOURCE_READY": 0,
        "PROJECTION_SOURCE_STALE": 1,
        "PROJECTION_SOURCE_MISSING": 2,
        "PROJECTION_SOURCE_EMPTY": 2,
        "PROJECTION_SOURCE_SCHEMA_INVALID": 3,
        "PROJECTION_SOURCE_INCOMPLETE": 1,
    }
    return verdict_codes.get(result["verdict"], 2)


if __name__ == "__main__":
    sys.exit(main())