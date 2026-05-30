#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WNBA Edge Lab - Model Upgrade Recommender V21

Purpose
-------
Read the V21 feature layer and model audit/execution outputs, then produce a precise,
ranked model-change plan.

Inputs:
  wnba_outputs/game_model_features_v21.csv
  wnba_outputs/team_features_v21.csv
  wnba_outputs/player_features_v21.csv
  wnba_outputs/market_features_v21.csv
  wnba_outputs/model_audit_summary_v20.json
  wnba_outputs/signal_execution_groups_v20.csv
  wnba_outputs/signal_execution_summary_v20.csv
  wnba_outputs/ultimate_fetch_status_v21_4.json
  wnba_outputs/hermes_state_v20.json

Outputs:
  wnba_outputs/model_upgrade_recommendations_v21.csv
  wnba_outputs/model_upgrade_recommendations_v21.json
  wnba_outputs/model_change_plan_v21.txt
  wnba_outputs/hermes_model_upgrade_queue_v21.csv

Safety:
  This file does NOT change model formulas, staking, thresholds, picks, or execution.
"""

from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any

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


def numeric_col(df: pd.DataFrame, col: str) -> pd.Series:
    if col not in df.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[col], errors="coerce")


def add_rec(recs: List[Dict[str, Any]], area: str, title: str, priority: int, status: str, evidence: str, change: str, safety: str, owner: str = "model") -> None:
    recs.append({
        "created_at_utc": now_iso(),
        "priority": priority,
        "area": area,
        "title": title,
        "status": status,
        "evidence": evidence,
        "recommended_change": change,
        "safety_gate": safety,
        "owner": owner,
    })


def summarize_execution(groups: pd.DataFrame, summary: pd.DataFrame) -> Dict[str, Any]:
    out = {"groups": len(groups), "tickets": None, "net_pl": None, "avg_group_pl": None}
    if not groups.empty:
        # Try common P/L columns.
        for c in groups.columns:
            cl = c.lower()
            if ("net" in cl or "profit" in cl or "p_l" in cl or "pl" == cl) and pd.api.types.is_numeric_dtype(pd.to_numeric(groups[c], errors="coerce")):
                vals = pd.to_numeric(groups[c], errors="coerce")
                if vals.notna().any():
                    out["avg_group_pl"] = float(vals.mean())
                    out["net_pl"] = float(vals.sum())
                    break
    if not summary.empty:
        for c in summary.columns:
            cl = c.lower()
            val = summary[c].iloc[0] if len(summary) else None
            if "ticket" in cl:
                try: out["tickets"] = float(val)
                except Exception: pass
            if ("net" in cl and ("p" in cl or "pl" in cl)) or "p/l" in cl:
                try: out["net_pl"] = float(val)
                except Exception: pass
    return out


def build_recommendations() -> Dict[str, Any]:
    game = read_csv(OUT / "game_model_features_v21.csv")
    team = read_csv(OUT / "team_features_v21.csv")
    player = read_csv(OUT / "player_features_v21.csv")
    market = read_csv(OUT / "market_features_v21.csv")
    groups = read_csv(OUT / "signal_execution_groups_v20.csv")
    exec_summary_csv = read_csv(OUT / "signal_execution_summary_v20.csv")
    audit = read_json(OUT / "model_audit_summary_v20.json")
    fetch = read_json(OUT / "ultimate_fetch_status_v21_4.json")
    hermes = read_json(OUT / "hermes_state_v20.json")

    recs: List[Dict[str, Any]] = []
    data_rows = {
        "game_model_features_v21": len(game),
        "team_features_v21": len(team),
        "player_features_v21": len(player),
        "market_features_v21": len(market),
        "signal_execution_groups_v20": len(groups),
    }

    readiness = fetch.get("readiness", {})
    exec_info = summarize_execution(groups, exec_summary_csv)

    # 1. Data readiness.
    if readiness.get("official_playergamelogs_ready") and readiness.get("official_team_dash_ready") and readiness.get("official_player_dash_ready"):
        add_rec(
            recs,
            "data",
            "Promote official WNBA mobile data to primary model source",
            1,
            "READY",
            f"Official player logs/team dash/player dash are ready. Rows: game={len(game)}, team={len(team)}, player={len(player)}.",
            "Use official_mobile_playergamelogs_v21, official_mobile_team_dash_base_v21, and official_mobile_player_dash_base_v21 as primary feature inputs before SportsDataverse fallback.",
            "Safe: read-only feature input promotion; no formula change until backtest.",
        )
    else:
        add_rec(
            recs,
            "data",
            "Keep official WNBA mobile data behind fallback gate",
            1,
            "BLOCKED",
            f"Readiness: {readiness}",
            "Do not promote official WNBA source until player logs/team/player dashboards are consistently ready.",
            "Gate: data readiness must be true for official player logs, team dash, and player dash.",
        )

    # 2. Market feature usage.
    if not market.empty:
        rng = numeric_col(market, "market_total_range")
        avg_range = float(rng.mean()) if rng.notna().any() else None
        add_rec(
            recs,
            "market",
            "Add market consensus and line-shopping range to model context",
            1,
            "READY",
            f"market_features_v21 has {len(market)} events. Average total range={avg_range if avg_range is not None else 'n/a'}.",
            "Add market_total_median, market_total_range, and market_total_books as non-predictive context gates: avoid overreacting when book range is wide; prioritize best available line versus consensus.",
            "Safe: context/gating only; do not alter projected total directly until measured.",
        )
    else:
        add_rec(recs, "market", "Market feature table missing", 1, "BLOCKED", "market_features_v21 is empty.", "Fix Odds API key/session before adding market consensus logic.", "Gate: odds_ready true and market rows > 0.")

    # 3. Projection-vs-line calibration.
    if not game.empty:
        if "projection_minus_line" in game.columns:
            edge = numeric_col(game, "projection_minus_line")
        elif "edge" in game.columns:
            edge = numeric_col(game, "edge")
        else:
            edge = pd.Series(dtype=float)
        n_edges = int(edge.notna().sum())
        avg_abs_edge = float(edge.abs().mean()) if n_edges else None
        add_rec(
            recs,
            "projection",
            "Introduce V21 feature audit before changing projected total formula",
            1,
            "READY",
            f"game_model_features_v21 has {len(game)} games; usable projection/line edge rows={n_edges}; avg abs edge={avg_abs_edge if avg_abs_edge is not None else 'n/a'}.",
            "Run a correlation/backtest layer that compares projection_minus_line against result, CLV, and execution P/L before applying any formula weights.",
            "Gate: no formula change until backtest sample is large enough and audit improves.",
        )
    else:
        add_rec(recs, "projection", "No game model features available", 1, "BLOCKED", "game_model_features_v21 is empty.", "Fix feature_builder_v21 joins against projections/recommended bets.", "Gate: game_model_features rows > 0.")

    # 4. Team form feature.
    if not team.empty:
        cols = set(team.columns)
        available = [c for c in ["playerlog_team_pts_l5", "dash_pts", "starter_minutes_concentration", "bench_minutes_share", "dreb_allowed_blended_dreb_allowed"] if c in cols]
        add_rec(
            recs,
            "features",
            "Add team form and rotation pressure layer",
            2,
            "READY" if available else "PARTIAL",
            f"team_features_v21 rows={len(team)}; available key columns={available}.",
            "Create a team environment score using recent playerlog_team_pts_l5, dash_pts, starter_minutes_concentration, bench_minutes_share, and DREB allowed blend. Use as an adjustment candidate, not live formula yet.",
            "Gate: compare against closing totals and results for at least 30-50 games before live weight.",
        )
    else:
        add_rec(recs, "features", "Team feature table missing", 2, "BLOCKED", "team_features_v21 is empty.", "Fix official player/team log ingestion.", "Gate: team_features rows >= 13.")

    # 5. Player concentration / props readiness.
    if not player.empty:
        dep = numeric_col(player, "scoring_dependency")
        high_dep = int((dep >= 0.22).sum()) if dep.notna().any() else 0
        add_rec(
            recs,
            "player",
            "Use player concentration for totals and future props",
            2,
            "READY",
            f"player_features_v21 rows={len(player)}; high scoring-dependency players={high_dep}.",
            "Build team concentration features: top scorer dependency, starter minutes concentration, and bench share. For props, require player market data plus settlement readiness.",
            "Gate: player props remain manual/research until --props returns live market rows.",
        )
    else:
        add_rec(recs, "player", "Player feature table missing", 2, "BLOCKED", "player_features_v21 is empty.", "Fix official playergamelogs pull.", "Gate: player_features rows > 100.")

    # 6. DREB allowed feature.
    if not team.empty and "dreb_allowed_blended_dreb_allowed" in team.columns:
        vals = numeric_col(team, "dreb_allowed_blended_dreb_allowed")
        add_rec(
            recs,
            "rebounding",
            "Promote blended DREB allowed as first validated matchup feature",
            2,
            "READY",
            f"DREB allowed blend exists for {int(vals.notna().sum())} teams; range={float(vals.min()) if vals.notna().any() else 'n/a'}-{float(vals.max()) if vals.notna().any() else 'n/a'}.",
            "Use blended DREB allowed as a matchup pressure feature for rebound props and totals environment. Keep weight advisory until historical validation.",
            "Gate: validate against player rebound prop outcomes before auto-use.",
        )
    else:
        add_rec(recs, "rebounding", "DREB allowed blend not attached to team features", 2, "PARTIAL", "DREB CSV may exist but column was not merged into team_features_v21.", "Check team abbreviation normalization for DREB allowed rankings.", "Gate: dreb_allowed_blended_dreb_allowed present.")

    # 7. Execution accounting.
    if exec_info.get("groups", 0) > 0:
        add_rec(
            recs,
            "execution",
            "Separate model signal quality from execution fill quality",
            1,
            "READY",
            f"Execution groups={exec_info.get('groups')}; tickets={exec_info.get('tickets')}; net P/L={exec_info.get('net_pl')}.",
            "Keep two scorecards: model recommended line/edge and actual execution fill/CLV. Do not let multiple fills of one signal distort model hit rate.",
            "Safe: reporting/accounting only.",
        )
    else:
        add_rec(recs, "execution", "Execution groups missing", 1, "BLOCKED", "signal_execution_groups_v20 is empty.", "Fix signal_execution_bridge output before model scoring.", "Gate: execution groups > 0.")

    # 8. Hermes / safety.
    locks = hermes.get("automation", {}).get("active_locks", [])
    add_rec(
        recs,
        "hermes",
        "Keep Hermes in manual approval during model upgrade",
        1,
        "REQUIRED",
        f"Active locks: {locks}",
        "Maintain MANUAL_APPROVAL_REQUIRED and MODEL_SAMPLE_LOCK until V21 backtest demonstrates stable improvement.",
        "Required: no auto-betting or threshold changes.",
        owner="hermes",
    )

    # 9. Odds API issue.
    fetch_records = fetch.get("records", [])
    odds_bad = [r for r in fetch_records if r.get("source") == "odds_totals" and r.get("state") != "LIVE_FETCH_OK"]
    if odds_bad:
        add_rec(
            recs,
            "data",
            "Refresh Odds API key/session before live deployment",
            1,
            "ACTION_NEEDED",
            f"Odds totals state: {odds_bad[0].get('state')} error={odds_bad[0].get('error')}",
            "Reset ODDS_API_KEY in current PowerShell session and confirm odds_totals returns LIVE_FETCH_OK before new actions.",
            "Gate: odds_totals LIVE_FETCH_OK for same-day recommendations.",
        )

    # Sort by priority then status.
    rec_df = pd.DataFrame(recs).sort_values(["priority", "area", "title"]).reset_index(drop=True)

    # Hermes queue: only actionable/relevant items.
    queue = rec_df[rec_df["status"].isin(["READY", "ACTION_NEEDED", "REQUIRED", "PARTIAL"])].copy()
    queue["approval_required"] = True
    queue["implementation_state"] = "PENDING_REVIEW"

    summary = {
        "created_at_utc": now_iso(),
        "status": "OK",
        "rows": {
            "recommendations": int(len(rec_df)),
            "hermes_queue": int(len(queue)),
        },
        "data_rows": data_rows,
        "execution": exec_info,
        "fetch_readiness": readiness,
        "top_priorities": rec_df.head(5).to_dict(orient="records"),
        "safety": {
            "formula_changed": False,
            "staking_changed": False,
            "thresholds_changed": False,
            "auto_betting": False,
        },
    }

    return {"recommendations": rec_df, "queue": queue, "summary": summary}


def write_plan(rec_df: pd.DataFrame, summary: Dict[str, Any]) -> None:
    lines = []
    lines.append("WNBA EDGE LAB - V21 MODEL CHANGE PLAN")
    lines.append("=" * 52)
    lines.append(f"Created: {summary['created_at_utc']}")
    lines.append("")
    lines.append("Safety:")
    lines.append("- No formula changes applied.")
    lines.append("- No staking changes applied.")
    lines.append("- No threshold changes applied.")
    lines.append("- No auto-betting enabled.")
    lines.append("")
    lines.append("Current evidence:")
    for k, v in summary.get("data_rows", {}).items():
        lines.append(f"- {k}: {v} rows")
    lines.append("")
    lines.append("Recommended implementation order:")
    for _, r in rec_df.sort_values(["priority", "area"]).iterrows():
        lines.append("")
        lines.append(f"P{int(r['priority'])} | {r['area'].upper()} | {r['status']} | {r['title']}")
        lines.append(f"Evidence: {r['evidence']}")
        lines.append(f"Change: {r['recommended_change']}")
        lines.append(f"Safety gate: {r['safety_gate']}")
    lines.append("")
    lines.append("Next engineering step:")
    lines.append("Build model_backtester_v21.py to validate these feature candidates against results/CLV before changing the projection formula.")
    (OUT / "model_change_plan_v21.txt").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    result = build_recommendations()
    rec_df = result["recommendations"]
    queue = result["queue"]
    summary = result["summary"]

    save_csv(OUT / "model_upgrade_recommendations_v21.csv", rec_df)
    save_csv(OUT / "hermes_model_upgrade_queue_v21.csv", queue)
    save_json(OUT / "model_upgrade_recommendations_v21.json", summary)
    write_plan(rec_df, summary)

    safe_print("OK: V21 Model Upgrade Recommender complete")
    safe_print(f"Recommendations: {len(rec_df)}")
    safe_print(f"Hermes queue: {len(queue)}")
    safe_print(f"CSV:  {OUT / 'model_upgrade_recommendations_v21.csv'}")
    safe_print(f"JSON: {OUT / 'model_upgrade_recommendations_v21.json'}")
    safe_print(f"Plan: {OUT / 'model_change_plan_v21.txt'}")
    safe_print("Note: recommendations only; no formula/staking/threshold changes applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
