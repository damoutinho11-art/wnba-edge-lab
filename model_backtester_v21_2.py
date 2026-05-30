#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WNBA Edge Lab - Model Backtester V21.2

Purpose
-------
Fix V21.7.1 limitation: the previous backtester expected many game-level columns
that were not actually populated in game_model_features_v21.csv.

This version validates candidates directly from all available V21 feature tables:
- game_model_features_v21.csv
- team_features_v21.csv
- player_features_v21.csv
- market_features_v21.csv
- signal_execution_groups_v20.csv
- feature_column_map_v21.json when available

Outputs:
- model_backtest_v21.csv
- model_backtest_summary_v21.json
- validated_model_changes_v21.csv
- model_formula_candidate_v21.txt
- hermes_backtest_warnings_v21.csv

Safety:
- Validation only.
- No formula changes.
- No staking changes.
- No threshold changes.
- No betting.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "wnba_outputs"


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


def read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def save_csv(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_")


def find_col(df: pd.DataFrame, aliases: List[str]) -> Optional[str]:
    if df.empty:
        return None
    cmap = {norm(c): c for c in df.columns}
    for a in aliases:
        if norm(a) in cmap:
            return cmap[norm(a)]
    # fuzzy: all tokens in col
    for a in aliases:
        toks = [t for t in norm(a).split("_") if t]
        for c in df.columns:
            nc = norm(c)
            if toks and all(t in nc for t in toks):
                return c
    return None


def num_series(df: pd.DataFrame, col: Optional[str]) -> pd.Series:
    if not col or col not in df.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[col], errors="coerce")


def add_candidate(rows: List[Dict[str, Any]], candidate: str, source: str, status: str, sample_size: int, evidence: str, recommendation: str, direction: str, score: float, implementation_stage: str) -> None:
    rows.append({
        "created_at_utc": now_iso(),
        "candidate": candidate,
        "source_table": source,
        "status": status,
        "sample_size": int(sample_size),
        "direction": direction,
        "score": float(score) if score is not None and not pd.isna(score) else 0.0,
        "evidence": evidence,
        "recommendation": recommendation,
        "implementation_stage": implementation_stage,
        "approved_for_live_formula": False,
        "approved_for_manual_review": True,
        "safety_gate": "Manual review only. Do not apply live formula weight until validated against graded results and CLV.",
    })


def candidate_from_numeric(rows, df: pd.DataFrame, source: str, candidate: str, aliases: List[str], recommendation: str, direction: str, implementation_stage: str, min_n: int = 1, scale: float = 1.0) -> None:
    col = find_col(df, aliases)
    vals = num_series(df, col).dropna()
    if col and len(vals) >= min_n:
        evidence = (
            f"{candidate} found in {source}.{col}; "
            f"n={len(vals)}, mean={vals.mean():.4f}, min={vals.min():.4f}, max={vals.max():.4f}, std={vals.std() if len(vals) > 1 else 0:.4f}"
        )
        score = min(100.0, max(1.0, (float(vals.std()) if len(vals) > 1 else abs(float(vals.mean()))) * scale))
        add_candidate(rows, candidate, source, "CANDIDATE", len(vals), evidence, recommendation, direction, score, implementation_stage)
    else:
        add_candidate(
            rows,
            candidate,
            source,
            "MISSING_OR_INSUFFICIENT",
            len(vals),
            f"{candidate} not usable. Matched column={col}; numeric rows={len(vals)}.",
            f"Patch feature_builder_v21 to populate {candidate} before formula validation.",
            "diagnostic",
            0.0,
            "DIAGNOSTIC",
        )


def build_candidates(game: pd.DataFrame, team: pd.DataFrame, player: pd.DataFrame, market: pd.DataFrame, groups: pd.DataFrame) -> pd.DataFrame:
    rows: List[Dict[str, Any]] = []

    # Market candidates.
    candidate_from_numeric(
        rows,
        market,
        "market_features_v21",
        "market_total_range",
        ["market_total_range", "total_range", "book_range"],
        "Use as a confidence/risk gate: wide book disagreement lowers confidence, not projection.",
        "higher_range_lowers_confidence",
        "CONFIDENCE_GATE_CANDIDATE",
        min_n=1,
        scale=20,
    )
    candidate_from_numeric(
        rows,
        market,
        "market_features_v21",
        "market_total_median",
        ["market_total_median", "median_total", "market_median"],
        "Use market median as line-shopping reference and sanity check versus available line.",
        "market_reference_only",
        "MARKET_CONTEXT",
        min_n=1,
        scale=1,
    )

    # Team environment candidates.
    candidate_from_numeric(
        rows,
        team,
        "team_features_v21",
        "playerlog_team_pts_l5",
        ["playerlog_team_pts_l5", "team_pts_for_l5", "recent_pts_l5"],
        "Use as capped recent form environment candidate. Do not let recent scoring dominate baseline.",
        "higher_recent_team_points_supports_over_environment",
        "BACKTEST_ONLY",
        min_n=4,
        scale=2,
    )
    candidate_from_numeric(
        rows,
        team,
        "team_features_v21",
        "dash_pts",
        ["dash_pts", "team_dash_pts", "PTS"],
        "Use official team dashboard points as baseline scoring environment feature.",
        "higher_dash_pts_supports_over_environment",
        "BACKTEST_ONLY",
        min_n=4,
        scale=2,
    )
    candidate_from_numeric(
        rows,
        team,
        "team_features_v21",
        "starter_minutes_concentration",
        ["starter_minutes_concentration"],
        "Use as rotation pressure flag; high concentration increases dependence on starters and prop relevance.",
        "higher_concentration_increases_rotation_dependency",
        "ROTATION_CONTEXT",
        min_n=4,
        scale=100,
    )
    candidate_from_numeric(
        rows,
        team,
        "team_features_v21",
        "bench_minutes_share",
        ["bench_minutes_share"],
        "Use as depth/variance flag; lower bench share increases starter dependence.",
        "lower_bench_share_increases_starter_dependency",
        "ROTATION_CONTEXT",
        min_n=4,
        scale=100,
    )
    candidate_from_numeric(
        rows,
        team,
        "team_features_v21",
        "dreb_allowed_blend",
        ["dreb_allowed_blended_dreb_allowed", "blended_dreb_allowed", "dreb_allowed"],
        "Use first for rebound prop screening and secondarily for totals environment.",
        "higher_allowed_supports_rebound_opportunity",
        "PROP_SCREENING_CANDIDATE",
        min_n=4,
        scale=10,
    )

    # Player candidates.
    candidate_from_numeric(
        rows,
        player,
        "player_features_v21",
        "scoring_dependency",
        ["scoring_dependency"],
        "Use top scoring dependency to identify teams where totals rely heavily on one or two players.",
        "higher_dependency_increases_player_news_sensitivity",
        "PLAYER_CONTEXT",
        min_n=20,
        scale=100,
    )
    candidate_from_numeric(
        rows,
        player,
        "player_features_v21",
        "minutes_l5",
        ["minutes_l5", "min_l5"],
        "Use recent minutes as future player-prop readiness feature.",
        "higher_minutes_supports_prop_volume",
        "PROP_SCREENING_CANDIDATE",
        min_n=20,
        scale=2,
    )

    # Game-level candidates if available.
    candidate_from_numeric(
        rows,
        game,
        "game_model_features_v21",
        "projection_minus_line",
        ["projection_minus_line", "edge"],
        "Primary edge candidate. Validate against results/CLV before any formula or threshold changes.",
        "higher_absolute_edge_should_improve_signal_quality",
        "PRIMARY_EDGE_VALIDATION",
        min_n=1,
        scale=10,
    )
    candidate_from_numeric(
        rows,
        game,
        "game_model_features_v21",
        "combined_playerlog_pts_l5",
        ["combined_playerlog_pts_l5", "combined_recent_pts_l5"],
        "Combined recent team scoring candidate for totals environment.",
        "higher_combined_recent_points_supports_over",
        "BACKTEST_ONLY",
        min_n=1,
        scale=2,
    )

    # Execution candidate.
    pl_col = None
    for c in groups.columns:
        nc = norm(c)
        if nc in {"execution_pl", "net_pl", "profit", "p_l", "pl"} or ("net" in nc and "pl" in nc):
            pl_col = c
            break
    vals = num_series(groups, pl_col).dropna() if pl_col else pd.Series(dtype=float)
    if pl_col and len(vals):
        add_candidate(
            rows,
            "execution_pl_tracking",
            "signal_execution_groups_v20",
            "REPORTING_ONLY",
            len(vals),
            f"Execution P/L found in {pl_col}; n={len(vals)}, sum={vals.sum():.4f}, mean={vals.mean():.4f}.",
            "Keep execution scorecard separate from model signal scorecard so multiple fills do not distort model hit rate.",
            "reporting_only",
            min(100.0, 50 + float(vals.sum()) * 10),
            "REPORTING_ONLY",
        )
    else:
        add_candidate(
            rows,
            "execution_pl_tracking",
            "signal_execution_groups_v20",
            "MISSING_OR_INSUFFICIENT",
            0,
            "No numeric execution P/L column detected in signal_execution_groups_v20.",
            "Keep using signal bridge summary for execution accounting; patch group-level P/L naming later.",
            "diagnostic",
            0.0,
            "DIAGNOSTIC",
        )

    out = pd.DataFrame(rows)
    order = {
        "PRIMARY_EDGE_VALIDATION": 0,
        "CONFIDENCE_GATE_CANDIDATE": 1,
        "BACKTEST_ONLY": 2,
        "PROP_SCREENING_CANDIDATE": 3,
        "ROTATION_CONTEXT": 4,
        "PLAYER_CONTEXT": 5,
        "MARKET_CONTEXT": 6,
        "REPORTING_ONLY": 7,
        "DIAGNOSTIC": 8,
    }
    out["_order"] = out["implementation_stage"].map(order).fillna(99)
    out = out.sort_values(["_order", "score"], ascending=[True, False]).drop(columns=["_order"]).reset_index(drop=True)
    return out


def build_backtest_table(candidates: pd.DataFrame) -> pd.DataFrame:
    # Keep this as the central validation table for now.
    out = candidates.copy()
    out["backtest_ready"] = out["status"].isin(["CANDIDATE", "REPORTING_ONLY"])
    out["requires_result_dataset"] = out["implementation_stage"].isin(["PRIMARY_EDGE_VALIDATION", "BACKTEST_ONLY", "CONFIDENCE_GATE_CANDIDATE"])
    return out


def build_validated_changes(candidates: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for _, r in candidates.iterrows():
        stage = str(r.get("implementation_stage", ""))
        status = str(r.get("status", ""))
        if status == "CANDIDATE" and stage in {"CONFIDENCE_GATE_CANDIDATE", "PROP_SCREENING_CANDIDATE", "ROTATION_CONTEXT", "PLAYER_CONTEXT", "MARKET_CONTEXT"}:
            rows.append({
                "created_at_utc": now_iso(),
                "candidate": r["candidate"],
                "implementation_stage": stage,
                "approved_for_live_formula": False,
                "approved_for_manual_review": True,
                "reason": r["evidence"],
                "next_step": "Manual review / validation sample. Do not auto-apply.",
            })
    return pd.DataFrame(rows, columns=[
        "created_at_utc",
        "candidate",
        "implementation_stage",
        "approved_for_live_formula",
        "approved_for_manual_review",
        "reason",
        "next_step",
    ])


def build_warnings(candidates: pd.DataFrame) -> pd.DataFrame:
    rows = []
    missing = candidates[candidates["status"] == "MISSING_OR_INSUFFICIENT"] if not candidates.empty else pd.DataFrame()
    if len(missing):
        rows.append({
            "created_at_utc": now_iso(),
            "severity": "medium",
            "source": "model_backtester_v21_2",
            "message": f"{len(missing)} candidates missing or insufficient. See model_backtest_v21.csv.",
        })
    primary = candidates[candidates["implementation_stage"] == "PRIMARY_EDGE_VALIDATION"] if not candidates.empty else pd.DataFrame()
    if primary.empty or not (primary["status"] == "CANDIDATE").any():
        rows.append({
            "created_at_utc": now_iso(),
            "severity": "medium",
            "source": "model_backtester_v21_2",
            "message": "Primary projection edge candidate is not populated. Feature builder likely needs projection/line preservation patch.",
        })
    return pd.DataFrame(rows)


def write_formula_candidate(candidates: pd.DataFrame) -> None:
    lines = []
    lines.append("WNBA EDGE LAB - V21.2 FORMULA CANDIDATE")
    lines.append("=" * 54)
    lines.append(f"Created: {now_iso()}")
    lines.append("")
    lines.append("Status: NOT APPLIED")
    lines.append("")
    lines.append("Safe candidate architecture:")
    lines.append("projected_total_candidate = current_projected_total")
    lines.append("  + capped_team_recent_form_adjustment")
    lines.append("  + capped_rotation_pressure_adjustment")
    lines.append("  + market_context_confidence_gate")
    lines.append("")
    lines.append("Do first:")
    lines.append("1. Use market_total_range only as confidence gate.")
    lines.append("2. Use DREB allowed blend only for prop/rebound screening.")
    lines.append("3. Use starter/bench concentration only as news sensitivity context.")
    lines.append("4. Do not change projection formula until projection_minus_line is populated and graded.")
    lines.append("")
    lines.append("Candidate table:")
    for _, r in candidates.iterrows():
        lines.append(f"- {r['candidate']} | {r['status']} | {r['implementation_stage']} | {r['evidence']}")
    (OUT / "model_formula_candidate_v21.txt").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    game = read_csv(OUT / "game_model_features_v21.csv")
    team = read_csv(OUT / "team_features_v21.csv")
    player = read_csv(OUT / "player_features_v21.csv")
    market = read_csv(OUT / "market_features_v21.csv")
    groups = read_csv(OUT / "signal_execution_groups_v20.csv")
    fetch = read_json(OUT / "ultimate_fetch_status_v21_4.json")
    column_map = read_json(OUT / "feature_column_map_v21.json")

    candidates = build_candidates(game, team, player, market, groups)
    backtest = build_backtest_table(candidates)
    validated = build_validated_changes(candidates)
    warnings = build_warnings(candidates)

    save_csv(OUT / "model_backtest_v21.csv", backtest)
    save_csv(OUT / "validated_model_changes_v21.csv", validated)
    save_csv(OUT / "hermes_backtest_warnings_v21.csv", warnings)
    write_formula_candidate(candidates)

    summary = {
        "created_at_utc": now_iso(),
        "status": "OK",
        "version": "v21.2",
        "rows": {
            "backtest": int(len(backtest)),
            "feature_candidates": int(len(candidates)),
            "validated_changes": int(len(validated)),
            "warnings": int(len(warnings)),
        },
        "inputs": {
            "game_model_features_v21": int(len(game)),
            "team_features_v21": int(len(team)),
            "player_features_v21": int(len(player)),
            "market_features_v21": int(len(market)),
            "signal_execution_groups_v20": int(len(groups)),
        },
        "candidate_status_counts": candidates["status"].value_counts().to_dict() if not candidates.empty else {},
        "implementation_stage_counts": candidates["implementation_stage"].value_counts().to_dict() if not candidates.empty else {},
        "fetch_readiness": fetch.get("readiness", {}),
        "column_map_available": bool(column_map),
        "safety": {
            "formula_changed": False,
            "staking_changed": False,
            "thresholds_changed": False,
            "auto_betting": False,
        },
    }
    save_json(OUT / "model_backtest_summary_v21.json", summary)

    safe_print("OK: V21.2 Model Backtester complete")
    safe_print(f"Backtest rows: {len(backtest)}")
    safe_print(f"Feature candidates: {len(candidates)}")
    safe_print(f"Validated/manual-review changes: {len(validated)}")
    safe_print(f"Warnings: {len(warnings)}")
    safe_print(f"Candidate statuses: {summary['candidate_status_counts']}")
    safe_print(f"Implementation stages: {summary['implementation_stage_counts']}")
    safe_print(f"Backtest CSV: {OUT / 'model_backtest_v21.csv'}")
    safe_print(f"Summary JSON: {OUT / 'model_backtest_summary_v21.json'}")
    safe_print("Note: validation only; no formula/staking/threshold changes applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
