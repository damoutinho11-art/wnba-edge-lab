"""
WNBA EDGE LAB - Model Result Tracker V21.9

Purpose
-------
Evidence layer for V21.8/V21.9 advisory scoring.
Reads advisory scores, graded signals, execution groups, and backtest candidates.
Writes model result tracking outputs that can be used to validate labels, risk flags,
confidence bands, CLV, and candidate promotion readiness before any formula change.

Safety
------
This script is READ/WRITE-OUTPUT ONLY.
It does NOT change model formulas, staking, thresholds, approvals, or execution.
It does NOT auto-bet.
Hermes remains manual approval.
"""

from __future__ import annotations

import json
import math
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "wnba_outputs"

ADVISORY_CSV = OUT / "model_advisory_scores_v21.csv"
ADVISORY_SUMMARY_JSON = OUT / "model_advisory_summary_v21.json"
BACKTEST_CSV = OUT / "model_backtest_v21.csv"
BACKTEST_SUMMARY_JSON = OUT / "model_backtest_summary_v21.json"
GRADED_SIGNALS_CSV = OUT / "signal_tracker_graded.csv"
CLV_SIGNALS_CSV = OUT / "signal_tracker_with_clv.csv"
EXEC_GROUPS_CSV = OUT / "signal_execution_groups_v20.csv"
HERMES_QUEUE_CSV = OUT / "hermes_approval_queue_v20.csv"
CYCLE_SUMMARY_JSON = OUT / "v21_8_advisory_cycle_summary.json"

TRACKING_CSV = OUT / "model_result_tracking_v21_9.csv"
TRACKING_SUMMARY_JSON = OUT / "model_result_tracking_summary_v21_9.json"
PROMOTION_WATCHLIST_CSV = OUT / "model_promotion_watchlist_v21_9.csv"

MODEL_VERSION = "v21.9"
MIN_SAMPLE_FOR_FORMULA_PROMOTION = 30
MIN_SAMPLE_FOR_THRESHOLD_REVIEW = 50


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_csv_safe(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception as exc:
        print(f"WARN: failed to read {path.name}: {exc}")
        return pd.DataFrame()


def read_json_safe(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as exc:
        print(f"WARN: failed to read {path.name}: {exc}")
        return {}


def is_blank(value: Any) -> bool:
    if value is None:
        return True
    try:
        if isinstance(value, float) and math.isnan(value):
            return True
    except Exception:
        pass
    return str(value).strip() == ""


def as_float(value: Any, default: Optional[float] = None) -> Optional[float]:
    if is_blank(value):
        return default
    try:
        return float(value)
    except Exception:
        return default


def as_str(value: Any, default: str = "") -> str:
    if is_blank(value):
        return default
    return str(value).strip()


def normalize_team_game(game: Any, away: Any = None, home: Any = None) -> str:
    raw = as_str(game).upper()
    if raw and "@" in raw:
        raw = re.sub(r"\s+", " ", raw)
        return raw
    away_s = as_str(away).upper()
    home_s = as_str(home).upper()
    if away_s and home_s:
        return f"{away_s} @ {home_s}"
    return raw


def normalize_side(value: Any) -> str:
    s = as_str(value).upper()
    if "OVER" in s:
        return "OVER"
    if "UNDER" in s:
        return "UNDER"
    return s


def confidence_band(score: Any) -> str:
    x = as_float(score)
    if x is None:
        return "UNKNOWN"
    if x >= 70:
        return "70+"
    if x >= 55:
        return "55-69"
    if x >= 40:
        return "40-54"
    if x >= 25:
        return "25-39"
    return "0-24"


def score_band(score: Any) -> str:
    x = as_float(score)
    if x is None:
        return "UNKNOWN"
    if x >= 50:
        return "50+"
    if x >= 35:
        return "35-49"
    if x >= 20:
        return "20-34"
    if x >= 10:
        return "10-19"
    return "0-9"


def derive_result(side: Any, line: Any, actual_total: Any, fallback: Any = None) -> str:
    fallback_s = as_str(fallback).upper()
    if fallback_s in {"WON", "WIN", "TRUE"}:
        return "WON"
    if fallback_s in {"LOST", "LOSS", "FALSE"}:
        return "LOST"
    if fallback_s in {"PUSH", "VOID"}:
        return fallback_s

    side_s = normalize_side(side)
    ln = as_float(line)
    actual = as_float(actual_total)
    if side_s not in {"OVER", "UNDER"} or ln is None or actual is None:
        return "UNKNOWN"
    if actual == ln:
        return "PUSH"
    if side_s == "OVER":
        return "WON" if actual > ln else "LOST"
    if side_s == "UNDER":
        return "WON" if actual < ln else "LOST"
    return "UNKNOWN"


def derive_clv(side: Any, line: Any, closing_line: Any, fallback: Any = None) -> Optional[float]:
    fallback_x = as_float(fallback)
    if fallback_x is not None:
        return fallback_x
    side_s = normalize_side(side)
    ln = as_float(line)
    close = as_float(closing_line)
    if side_s not in {"OVER", "UNDER"} or ln is None or close is None:
        return None
    if side_s == "OVER":
        return close - ln
    return ln - close


def match_rows(advisory_row: pd.Series, graded: pd.DataFrame, exec_groups: pd.DataFrame) -> Tuple[Dict[str, Any], str]:
    """Match an advisory row to the closest graded signal or execution group."""
    game = normalize_team_game(advisory_row.get("game"), advisory_row.get("away_team"), advisory_row.get("home_team"))
    side = normalize_side(advisory_row.get("side"))
    line = as_float(advisory_row.get("line"))

    best: Dict[str, Any] = {}
    source = "NO_MATCH"

    candidates: List[Tuple[float, str, pd.Series]] = []

    if not graded.empty:
        g = graded.copy()
        g["_game_norm"] = g.apply(lambda r: normalize_team_game(r.get("Game"), r.get("Away"), r.get("Home")), axis=1)
        g["_side_norm"] = g.get("Selection", pd.Series(dtype=str)).map(normalize_side)
        mask = (g["_game_norm"] == game) & (g["_side_norm"] == side)
        for _, row in g[mask].iterrows():
            row_line = as_float(row.get("LineAtSignal"))
            distance = abs((row_line or 0.0) - (line or row_line or 0.0)) if row_line is not None else 999.0
            # Prefer graded rows with a non-open status and line proximity.
            status_bonus = 0.0 if as_str(row.get("ResultStatus")).upper() in {"GRADED", "WON", "LOST", "PUSH"} else 2.0
            candidates.append((distance + status_bonus, "signal_tracker_graded", row))

    if not exec_groups.empty:
        e = exec_groups.copy()
        e["_game_norm"] = e.get("Game", pd.Series(dtype=str)).map(normalize_team_game)
        e["_side_norm"] = e.get("Side", pd.Series(dtype=str)).map(normalize_side)
        mask = (e["_game_norm"] == game) & (e["_side_norm"] == side)
        for _, row in e[mask].iterrows():
            row_line = as_float(row.get("ModelLine")) or as_float(row.get("AverageExecutedLine"))
            distance = abs((row_line or 0.0) - (line or row_line or 0.0)) if row_line is not None else 999.0
            status_bonus = 0.0 if as_str(row.get("Status")).upper() in {"WON", "LOST", "PUSH"} else 2.0
            candidates.append((distance + status_bonus, "signal_execution_groups", row))

    if not candidates:
        return best, source

    _, source, row = sorted(candidates, key=lambda x: x[0])[0]
    if source == "signal_tracker_graded":
        best = {
            "matched_signal_id": row.get("SignalID"),
            "matched_source": source,
            "matched_market": row.get("Market"),
            "matched_line": as_float(row.get("LineAtSignal")),
            "closing_line": as_float(row.get("ClosingLine")),
            "actual_total": as_float(row.get("ActualTotal")),
            "result_status_raw": row.get("ResultStatus"),
            "would_have_won_raw": row.get("WouldHaveWon"),
            "clv_points_raw": as_float(row.get("CLV_Points")),
            "beat_close_raw": row.get("BeatClose"),
            "graded_confidence": row.get("Confidence"),
            "graded_confidence_grade": row.get("ConfidenceGrade"),
            "graded_final_signal": row.get("FinalSignal"),
        }
    else:
        best = {
            "matched_signal_id": row.get("GroupID"),
            "matched_source": source,
            "matched_market": row.get("Market"),
            "matched_line": as_float(row.get("ModelLine")) or as_float(row.get("AverageExecutedLine")),
            "closing_line": as_float(row.get("ClosingLine")),
            "actual_total": as_float(row.get("Actual")),
            "result_status_raw": row.get("Status"),
            "would_have_won_raw": None,
            "clv_points_raw": as_float(row.get("StrictModelCLVPoints")),
            "beat_close_raw": None,
            "graded_confidence": row.get("ModelConfidence"),
            "graded_confidence_grade": row.get("ConfidenceGrade"),
            "graded_final_signal": row.get("ModelSignal"),
            "execution_tickets": row.get("ExecutionTickets"),
            "total_stake": as_float(row.get("TotalStake")),
            "net_profit": as_float(row.get("NetProfit")),
            "roi_percent": as_float(row.get("ROI_Percent")),
        }
    return best, source


def group_summary(df: pd.DataFrame, group_col: str) -> List[Dict[str, Any]]:
    if df.empty or group_col not in df.columns:
        return []
    rows: List[Dict[str, Any]] = []
    for key, g in df.groupby(group_col, dropna=False):
        key_s = "NONE" if is_blank(key) else str(key)
        known = g[g["result"] != "UNKNOWN"] if "result" in g.columns else pd.DataFrame()
        won = int((known["result"] == "WON").sum()) if not known.empty else 0
        lost = int((known["result"] == "LOST").sum()) if not known.empty else 0
        push = int((known["result"] == "PUSH").sum()) if not known.empty else 0
        decided = won + lost
        rows.append({
            "group": key_s,
            "rows": int(len(g)),
            "known_results": int(len(known)),
            "won": won,
            "lost": lost,
            "push": push,
            "win_rate_decided": round(won / decided, 4) if decided else None,
            "avg_advisory_score": round(float(pd.to_numeric(g.get("advisory_score"), errors="coerce").mean()), 4) if "advisory_score" in g.columns else None,
            "avg_clv_points": round(float(pd.to_numeric(g.get("clv_points"), errors="coerce").mean()), 4) if "clv_points" in g.columns else None,
            "positive_clv_rate": round(float((pd.to_numeric(g.get("clv_points"), errors="coerce") > 0).mean()), 4) if "clv_points" in g.columns and pd.to_numeric(g.get("clv_points"), errors="coerce").notna().any() else None,
            "sample_gate": "PASS" if len(g) >= MIN_SAMPLE_FOR_FORMULA_PROMOTION else "INSUFFICIENT_SAMPLE",
        })
    return rows


def build_tracking() -> pd.DataFrame:
    advisory = read_csv_safe(ADVISORY_CSV)
    graded = read_csv_safe(GRADED_SIGNALS_CSV)
    exec_groups = read_csv_safe(EXEC_GROUPS_CSV)

    if advisory.empty:
        raise SystemExit(f"ERROR: missing/empty required input: {ADVISORY_CSV}")

    out_rows: List[Dict[str, Any]] = []
    for idx, row in advisory.iterrows():
        game = normalize_team_game(row.get("game"), row.get("away_team"), row.get("home_team"))
        side = normalize_side(row.get("side"))
        line = as_float(row.get("line"))
        matched, source = match_rows(row, graded, exec_groups)
        actual_total = matched.get("actual_total")
        closing_line = matched.get("closing_line")
        result = derive_result(side, line or matched.get("matched_line"), actual_total, matched.get("result_status_raw") or matched.get("would_have_won_raw"))
        clv_points = derive_clv(side, line or matched.get("matched_line"), closing_line, matched.get("clv_points_raw"))
        risk_flags = as_str(row.get("risk_flags"), "NONE") or "NONE"
        advisory_score = as_float(row.get("advisory_score"))
        manual_priority = as_float(row.get("manual_review_priority"))

        out = {
            "created_at_utc": now_utc(),
            "tracker_version": MODEL_VERSION,
            "advisory_row_id": idx + 1,
            "game": game,
            "away_team": as_str(row.get("away_team")),
            "home_team": as_str(row.get("home_team")),
            "side": side,
            "line": line,
            "projection": as_float(row.get("projection")),
            "edge": as_float(row.get("edge")),
            "units": as_float(row.get("units")),
            "advisory_score": advisory_score,
            "advisory_score_band": score_band(advisory_score),
            "advisory_label": as_str(row.get("advisory_label"), "UNKNOWN"),
            "risk_flags": risk_flags,
            "manual_review_priority": manual_priority,
            "manual_review_band": "P1" if manual_priority == 1 else "P2" if manual_priority == 2 else "P3_OR_UNKNOWN",
            "model_edge_score": as_float(row.get("model_edge_score")),
            "recent_scoring_score": as_float(row.get("recent_scoring_score")),
            "dashboard_scoring_score": as_float(row.get("dashboard_scoring_score")),
            "rotation_concentration_score": as_float(row.get("rotation_concentration_score")),
            "rotation_risk_penalty": as_float(row.get("rotation_risk_penalty")),
            "bench_depth_score": as_float(row.get("bench_depth_score")),
            "dreb_environment_score": as_float(row.get("dreb_environment_score")),
            "market_range_penalty": as_float(row.get("market_range_penalty")),
            "market_range": as_float(row.get("market_range")),
            "matched_source": source,
            **matched,
            "actual_total": actual_total,
            "closing_line": closing_line,
            "clv_points": clv_points,
            "clv_state": "POSITIVE" if clv_points is not None and clv_points > 0 else "NEGATIVE" if clv_points is not None and clv_points < 0 else "FLAT" if clv_points == 0 else "UNKNOWN",
            "result": result,
            "result_known": result in {"WON", "LOST", "PUSH"},
            "formula_change_allowed": False,
            "staking_change_allowed": False,
            "threshold_change_allowed": False,
            "auto_betting_allowed": False,
            "safety_note": "Evidence only. Manual review required. No formula/staking/threshold/execution change applied.",
        }
        out_rows.append(out)

    df = pd.DataFrame(out_rows)
    return df


def build_promotion_watchlist(tracking: pd.DataFrame) -> pd.DataFrame:
    backtest = read_csv_safe(BACKTEST_CSV)
    rows: List[Dict[str, Any]] = []

    if backtest.empty:
        return pd.DataFrame([{
            "created_at_utc": now_utc(),
            "tracker_version": MODEL_VERSION,
            "candidate": "NO_BACKTEST_FILE",
            "promotion_state": "BLOCKED",
            "reason": "model_backtest_v21.csv missing or empty",
            "approved_for_live_formula": False,
            "approved_for_manual_review": False,
        }])

    known_results = int((tracking["result"] != "UNKNOWN").sum()) if not tracking.empty and "result" in tracking.columns else 0
    decided_results = int(tracking["result"].isin(["WON", "LOST"]).sum()) if not tracking.empty and "result" in tracking.columns else 0
    clv_samples = int(pd.to_numeric(tracking.get("clv_points"), errors="coerce").notna().sum()) if not tracking.empty else 0

    for _, row in backtest.iterrows():
        sample_size = int(as_float(row.get("sample_size"), 0) or 0)
        status = as_str(row.get("status"), "UNKNOWN")
        stage = as_str(row.get("implementation_stage"), "UNKNOWN")
        ready = bool(row.get("backtest_ready")) if not is_blank(row.get("backtest_ready")) else False
        requires_results = bool(row.get("requires_result_dataset")) if not is_blank(row.get("requires_result_dataset")) else True

        blockers: List[str] = []
        if status != "CANDIDATE":
            blockers.append(f"status={status}")
        if sample_size < MIN_SAMPLE_FOR_FORMULA_PROMOTION:
            blockers.append(f"feature_sample<{MIN_SAMPLE_FOR_FORMULA_PROMOTION}")
        if requires_results and decided_results < MIN_SAMPLE_FOR_FORMULA_PROMOTION:
            blockers.append(f"decided_results<{MIN_SAMPLE_FOR_FORMULA_PROMOTION}")
        if clv_samples < MIN_SAMPLE_FOR_FORMULA_PROMOTION:
            blockers.append(f"clv_samples<{MIN_SAMPLE_FOR_FORMULA_PROMOTION}")
        if not ready:
            blockers.append("backtest_ready=false")

        promotion_state = "FORMULA_REVIEW_ELIGIBLE" if not blockers else "WATCH_ONLY"
        rows.append({
            "created_at_utc": now_utc(),
            "tracker_version": MODEL_VERSION,
            "candidate": row.get("candidate"),
            "source_table": row.get("source_table"),
            "status": status,
            "implementation_stage": stage,
            "feature_sample_size": sample_size,
            "backtest_score": as_float(row.get("score")),
            "direction": row.get("direction"),
            "recommendation": row.get("recommendation"),
            "evidence": row.get("evidence"),
            "known_advisory_results": known_results,
            "decided_advisory_results": decided_results,
            "clv_samples": clv_samples,
            "promotion_state": promotion_state,
            "blockers": "; ".join(blockers) if blockers else "NONE",
            "approved_for_live_formula": False,
            "approved_for_manual_review": bool(row.get("approved_for_manual_review")) if not is_blank(row.get("approved_for_manual_review")) else True,
            "safety_gate": "Manual review only. No live formula/staking/threshold changes.",
        })

    return pd.DataFrame(rows)


def build_summary(tracking: pd.DataFrame, watchlist: pd.DataFrame) -> Dict[str, Any]:
    advisory_summary = read_json_safe(ADVISORY_SUMMARY_JSON)
    backtest_summary = read_json_safe(BACKTEST_SUMMARY_JSON)
    cycle_summary = read_json_safe(CYCLE_SUMMARY_JSON)

    result_counts = tracking["result"].value_counts(dropna=False).to_dict() if "result" in tracking.columns else {}
    clv_series = pd.to_numeric(tracking.get("clv_points"), errors="coerce") if not tracking.empty else pd.Series(dtype=float)
    known_clv = clv_series.dropna()

    summary = {
        "created_at_utc": now_utc(),
        "status": "OK",
        "version": MODEL_VERSION,
        "purpose": "Validate advisory scores, labels, risk flags, and candidates against results/CLV before any formula change.",
        "inputs": {
            "model_advisory_scores_v21": int(len(read_csv_safe(ADVISORY_CSV))),
            "model_backtest_v21": int(len(read_csv_safe(BACKTEST_CSV))),
            "signal_tracker_graded": int(len(read_csv_safe(GRADED_SIGNALS_CSV))),
            "signal_execution_groups_v20": int(len(read_csv_safe(EXEC_GROUPS_CSV))),
            "hermes_approval_queue_v20": int(len(read_csv_safe(HERMES_QUEUE_CSV))),
        },
        "rows": {
            "tracking": int(len(tracking)),
            "promotion_watchlist": int(len(watchlist)),
            "matched_rows": int((tracking.get("matched_source", pd.Series(dtype=str)) != "NO_MATCH").sum()) if not tracking.empty else 0,
            "known_results": int((tracking.get("result", pd.Series(dtype=str)) != "UNKNOWN").sum()) if not tracking.empty else 0,
            "decided_results": int(tracking.get("result", pd.Series(dtype=str)).isin(["WON", "LOST"]).sum()) if not tracking.empty else 0,
            "clv_samples": int(known_clv.shape[0]),
        },
        "result_counts": {str(k): int(v) for k, v in result_counts.items()},
        "clv": {
            "avg_points": round(float(known_clv.mean()), 4) if not known_clv.empty else None,
            "median_points": round(float(known_clv.median()), 4) if not known_clv.empty else None,
            "positive_clv_rate": round(float((known_clv > 0).mean()), 4) if not known_clv.empty else None,
            "flat_clv_rate": round(float((known_clv == 0).mean()), 4) if not known_clv.empty else None,
            "negative_clv_rate": round(float((known_clv < 0).mean()), 4) if not known_clv.empty else None,
        },
        "by_advisory_label": group_summary(tracking, "advisory_label"),
        "by_risk_flags": group_summary(tracking, "risk_flags"),
        "by_advisory_score_band": group_summary(tracking, "advisory_score_band"),
        "promotion_states": watchlist.get("promotion_state", pd.Series(dtype=str)).value_counts(dropna=False).to_dict() if not watchlist.empty else {},
        "gates": {
            "formula_change_allowed": False,
            "staking_change_allowed": False,
            "threshold_change_allowed": False,
            "auto_betting_allowed": False,
            "min_sample_for_formula_promotion": MIN_SAMPLE_FOR_FORMULA_PROMOTION,
            "min_sample_for_threshold_review": MIN_SAMPLE_FOR_THRESHOLD_REVIEW,
            "current_gate_state": "EVIDENCE_COLLECTION_ONLY",
        },
        "source_summaries": {
            "advisory_summary_rows": advisory_summary.get("rows", {}),
            "advisory_label_counts": advisory_summary.get("label_counts", {}),
            "advisory_risk_flag_counts": advisory_summary.get("risk_flag_counts", {}),
            "backtest_rows": backtest_summary.get("rows", {}),
            "candidate_status_counts": backtest_summary.get("candidate_status_counts", {}),
            "cycle_fetch_readiness": cycle_summary.get("fetch_readiness", {}),
            "cycle_locks": cycle_summary.get("locks", []),
        },
        "safety": {
            "formula_changed": False,
            "staking_changed": False,
            "thresholds_changed": False,
            "auto_betting": False,
            "hermes_manual_approval_required": True,
            "note": "V21.9 tracker creates evidence artifacts only; it does not alter live model behavior.",
        },
        "outputs": {
            "tracking_csv": str(TRACKING_CSV),
            "summary_json": str(TRACKING_SUMMARY_JSON),
            "promotion_watchlist_csv": str(PROMOTION_WATCHLIST_CSV),
        },
    }
    return summary


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    tracking = build_tracking()
    watchlist = build_promotion_watchlist(tracking)
    summary = build_summary(tracking, watchlist)

    tracking.to_csv(TRACKING_CSV, index=False)
    watchlist.to_csv(PROMOTION_WATCHLIST_CSV, index=False)
    with TRACKING_SUMMARY_JSON.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("OK: V21.9 Model Result Tracker complete")
    print(f"Tracking rows: {len(tracking)}")
    print(f"Matched rows: {summary['rows']['matched_rows']}")
    print(f"Known results: {summary['rows']['known_results']}")
    print(f"CLV samples: {summary['rows']['clv_samples']}")
    print(f"Promotion watchlist rows: {len(watchlist)}")
    print(f"Result counts: {summary['result_counts']}")
    print(f"Promotion states: {summary['promotion_states']}")
    print(f"CSV: {TRACKING_CSV}")
    print(f"Summary: {TRACKING_SUMMARY_JSON}")
    print(f"Watchlist: {PROMOTION_WATCHLIST_CSV}")
    print("Note: evidence only; no formula/staking/threshold/auto-betting changes applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
