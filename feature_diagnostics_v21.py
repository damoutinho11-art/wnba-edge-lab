#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WNBA Edge Lab - Feature Diagnostics V21

Purpose
-------
Inspect the actual V21 feature/output files and generate a precise column map
so the backtester can use the real column names.

Inputs:
  wnba_outputs/game_model_features_v21.csv
  wnba_outputs/team_features_v21.csv
  wnba_outputs/player_features_v21.csv
  wnba_outputs/market_features_v21.csv
  wnba_outputs/model_backtest_v21.csv
  wnba_outputs/model_backtest_summary_v21.json
  wnba_outputs/feature_builder_summary_v21.json

Outputs:
  wnba_outputs/feature_diagnostics_v21.csv
  wnba_outputs/feature_column_map_v21.json
  wnba_outputs/feature_diagnostics_summary_v21.json
  wnba_outputs/feature_diagnostics_report_v21.txt

Safety:
  Read-only diagnostics.
  Does not change formula, staking, thresholds, betting, or approvals.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional

import pandas as pd
import numpy as np


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "wnba_outputs"


FILES = {
    "game_model_features_v21": OUT / "game_model_features_v21.csv",
    "team_features_v21": OUT / "team_features_v21.csv",
    "player_features_v21": OUT / "player_features_v21.csv",
    "market_features_v21": OUT / "market_features_v21.csv",
    "model_backtest_v21": OUT / "model_backtest_v21.csv",
    "model_upgrade_recommendations_v21": OUT / "model_upgrade_recommendations_v21.csv",
}


CANONICAL_FEATURES = {
    "game": ["game", "matchup", "event", "signal_game"],
    "projection": ["projection", "projected_total", "model_total", "projected", "proj_total"],
    "line": ["line", "total", "market_total", "bet_line", "signal_line"],
    "edge": ["edge", "projection_minus_line", "model_edge"],
    "market_total_median": ["market_total_median", "market_median", "median_total"],
    "market_total_mean": ["market_total_mean", "market_mean", "mean_total"],
    "market_total_range": ["market_total_range", "total_range", "book_range"],
    "market_total_books": ["market_total_books", "books", "book_count"],
    "combined_playerlog_pts_l5": ["combined_playerlog_pts_l5", "combined_recent_pts_l5", "recent_points_l5"],
    "combined_dash_pts": ["combined_dash_pts", "dash_combined_pts"],
    "home_starter_minutes_concentration": ["home_starter_minutes_concentration"],
    "away_starter_minutes_concentration": ["away_starter_minutes_concentration"],
    "home_bench_minutes_share": ["home_bench_minutes_share"],
    "away_bench_minutes_share": ["away_bench_minutes_share"],
    "home_dreb_allowed": ["home_dreb_allowed_blended_dreb_allowed", "home_dreb_allowed", "home_dreb_allowed_blend"],
    "away_dreb_allowed": ["away_dreb_allowed_blended_dreb_allowed", "away_dreb_allowed", "away_dreb_allowed_blend"],
    "execution_pl": ["execution_pl", "net_pl", "profit", "p_l"],
}


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


def save_csv(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def save_json(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(name).lower()).strip("_")


def find_candidates(columns: List[str], aliases: List[str]) -> List[str]:
    norm_to_original = {normalize_name(c): c for c in columns}
    hits = []
    for alias in aliases:
        n = normalize_name(alias)
        if n in norm_to_original:
            hits.append(norm_to_original[n])
    if hits:
        return hits

    # Fuzzy fallback: all alias tokens contained in column name.
    for alias in aliases:
        toks = [t for t in normalize_name(alias).split("_") if t]
        if not toks:
            continue
        for c in columns:
            nc = normalize_name(c)
            if all(t in nc for t in toks):
                hits.append(c)
    return sorted(set(hits))


def column_stats(df: pd.DataFrame, file_key: str) -> List[Dict[str, Any]]:
    rows = []
    for c in df.columns:
        s = df[c]
        numeric = pd.to_numeric(s, errors="coerce")
        rows.append({
            "created_at_utc": now_iso(),
            "file": file_key,
            "column": c,
            "normalized_column": normalize_name(c),
            "rows": int(len(df)),
            "non_null": int(s.notna().sum()),
            "nulls": int(s.isna().sum()),
            "numeric_non_null": int(numeric.notna().sum()),
            "numeric_mean": float(numeric.mean()) if numeric.notna().any() else None,
            "numeric_min": float(numeric.min()) if numeric.notna().any() else None,
            "numeric_max": float(numeric.max()) if numeric.notna().any() else None,
            "sample_values": "; ".join([str(x) for x in s.dropna().astype(str).head(3).tolist()])[:300],
        })
    return rows


def build_column_map(data: Dict[str, pd.DataFrame]) -> Dict[str, Any]:
    mapping: Dict[str, Any] = {
        "created_at_utc": now_iso(),
        "files": {},
        "canonical_features": {},
        "diagnosis": [],
    }

    for key, df in data.items():
        mapping["files"][key] = {
            "path": str(FILES[key]),
            "exists": FILES[key].exists(),
            "rows": int(len(df)),
            "columns": list(df.columns),
        }

    # Prefer game_model_features first, then backtest, then market/team.
    search_order = [
        "game_model_features_v21",
        "model_backtest_v21",
        "market_features_v21",
        "team_features_v21",
        "player_features_v21",
    ]

    for canonical, aliases in CANONICAL_FEATURES.items():
        found = []
        for file_key in search_order:
            df = data.get(file_key, pd.DataFrame())
            if df.empty:
                continue
            hits = find_candidates(list(df.columns), aliases)
            for h in hits:
                found.append({"file": file_key, "column": h})
        mapping["canonical_features"][canonical] = found

    # Diagnose missing core features.
    core = [
        "game",
        "projection",
        "line",
        "edge",
        "market_total_median",
        "market_total_range",
        "combined_playerlog_pts_l5",
        "combined_dash_pts",
        "home_starter_minutes_concentration",
        "away_starter_minutes_concentration",
        "home_dreb_allowed",
        "away_dreb_allowed",
    ]
    for c in core:
        if not mapping["canonical_features"].get(c):
            mapping["diagnosis"].append({
                "severity": "medium",
                "feature": c,
                "message": f"No column match found for canonical feature '{c}'.",
            })

    # Backtester-specific reason.
    backtest = data.get("model_backtest_v21", pd.DataFrame())
    if not backtest.empty:
        candidate_cols = [
            "projection_minus_line",
            "recent_points_vs_line",
            "combined_dash_pts",
            "market_total_range",
            "home_starter_minutes_concentration",
            "away_starter_minutes_concentration",
            "home_bench_minutes_share",
            "away_bench_minutes_share",
            "home_dreb_allowed_blended_dreb_allowed",
            "away_dreb_allowed_blended_dreb_allowed",
            "execution_pl",
        ]
        present = [c for c in candidate_cols if c in backtest.columns]
        numeric_present = []
        for c in present:
            if pd.to_numeric(backtest[c], errors="coerce").notna().any():
                numeric_present.append(c)
        mapping["backtester_expected_columns"] = {
            "present": present,
            "numeric_present": numeric_present,
            "missing": [c for c in candidate_cols if c not in backtest.columns],
        }
        if not numeric_present:
            mapping["diagnosis"].append({
                "severity": "high",
                "feature": "backtester_candidate_detection",
                "message": "Backtester expected columns are missing or non-numeric in model_backtest_v21.",
            })

    return mapping


def write_report(mapping: Dict[str, Any], stats_df: pd.DataFrame) -> None:
    lines = []
    lines.append("WNBA EDGE LAB - V21 FEATURE DIAGNOSTICS REPORT")
    lines.append("=" * 60)
    lines.append(f"Created: {mapping['created_at_utc']}")
    lines.append("")
    lines.append("Files:")
    for key, info in mapping["files"].items():
        lines.append(f"- {key}: exists={info['exists']} rows={info['rows']} columns={len(info['columns'])}")
    lines.append("")
    lines.append("Canonical feature map:")
    for canonical, hits in mapping["canonical_features"].items():
        if hits:
            hit_text = ", ".join([f"{h['file']}::{h['column']}" for h in hits[:5]])
        else:
            hit_text = "MISSING"
        lines.append(f"- {canonical}: {hit_text}")
    lines.append("")
    lines.append("Backtester expected columns:")
    bec = mapping.get("backtester_expected_columns", {})
    lines.append(f"- present: {bec.get('present', [])}")
    lines.append(f"- numeric_present: {bec.get('numeric_present', [])}")
    lines.append(f"- missing: {bec.get('missing', [])}")
    lines.append("")
    lines.append("Diagnosis:")
    if mapping["diagnosis"]:
        for d in mapping["diagnosis"]:
            lines.append(f"- {d['severity'].upper()} | {d['feature']}: {d['message']}")
    else:
        lines.append("- No major mapping issues detected.")
    lines.append("")
    lines.append("Next recommended patch:")
    lines.append("- Use feature_column_map_v21.json to patch model_backtester_v21 so it reads the actual column names.")
    lines.append("- If game_model_features_v21 lacks projection/line columns, patch feature_builder_v21 to preserve them from projections/recommended_bets.")
    (OUT / "feature_diagnostics_report_v21.txt").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    data = {key: read_csv(path) for key, path in FILES.items()}

    stats_rows = []
    for key, df in data.items():
        stats_rows.extend(column_stats(df, key) if not df.empty else [{
            "created_at_utc": now_iso(),
            "file": key,
            "column": "",
            "normalized_column": "",
            "rows": 0,
            "non_null": 0,
            "nulls": 0,
            "numeric_non_null": 0,
            "numeric_mean": None,
            "numeric_min": None,
            "numeric_max": None,
            "sample_values": "",
        }])

    stats_df = pd.DataFrame(stats_rows)
    mapping = build_column_map(data)

    save_csv(OUT / "feature_diagnostics_v21.csv", stats_df)
    save_json(OUT / "feature_column_map_v21.json", mapping)

    summary = {
        "created_at_utc": now_iso(),
        "status": "OK",
        "files": {k: {"exists": FILES[k].exists(), "rows": int(len(v)), "columns": int(len(v.columns)) if not v.empty else 0} for k, v in data.items()},
        "diagnosis_count": len(mapping["diagnosis"]),
        "high_diagnosis": int(sum(1 for d in mapping["diagnosis"] if d.get("severity") == "high")),
        "backtester_expected_columns": mapping.get("backtester_expected_columns", {}),
        "safety": {
            "formula_changed": False,
            "staking_changed": False,
            "thresholds_changed": False,
            "auto_betting": False,
        },
    }
    save_json(OUT / "feature_diagnostics_summary_v21.json", summary)
    write_report(mapping, stats_df)

    safe_print("OK: V21 Feature Diagnostics complete")
    safe_print(f"Diagnostics CSV: {OUT / 'feature_diagnostics_v21.csv'}")
    safe_print(f"Column map:      {OUT / 'feature_column_map_v21.json'}")
    safe_print(f"Report:          {OUT / 'feature_diagnostics_report_v21.txt'}")
    safe_print(f"Diagnosis: {summary['diagnosis_count']} total / {summary['high_diagnosis']} high")
    safe_print(f"Backtester expected: {summary['backtester_expected_columns']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
