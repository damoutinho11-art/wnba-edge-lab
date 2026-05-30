"""
WNBA Edge Lab — V20 Hermes State Builder

Purpose
-------
Build one clean, structured state file for Hermes Agent.

This is NOT an auto-betting script. It prepares read-only state for:
    - mission brief generation
    - warnings
    - approval queue
    - Telegram draft prep
    - future Nous/Hermes agent integration

Inputs, if present:
    bet_tracker.csv
    wnba_outputs/projections_with_stakes.csv
    wnba_outputs/recommended_bets.csv
    wnba_outputs/model_health_report.csv
    wnba_outputs/signal_execution_groups_v20.csv
    wnba_outputs/signal_execution_summary_v20.csv
    wnba_outputs/signal_execution_latest_v20.json
    wnba_outputs/environment_regime_latest.json
    wnba_outputs/environment_memory_latest.csv
    wnba_outputs/environment_validation_summary.csv
    wnba_outputs/signal_clv_summary.csv
    wnba_outputs/signal_results_summary.csv
    wnba_outputs/telegram_message.txt
    wnba_outputs/injuries/*

Outputs:
    wnba_outputs/hermes_state_v20.json
    wnba_outputs/hermes_warnings_v20.csv
    wnba_outputs/hermes_approval_queue_v20.csv

Run:
    python hermes_state_builder_v20.py
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "wnba_outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

BET_CSV = ROOT / "bet_tracker.csv"
PROJECTIONS_STAKES_CSV = OUTPUT_DIR / "projections_with_stakes.csv"
RECOMMENDED_CSV = OUTPUT_DIR / "recommended_bets.csv"
MODEL_HEALTH_CSV = OUTPUT_DIR / "model_health_report.csv"
SIGNAL_EXEC_GROUPS_CSV = OUTPUT_DIR / "signal_execution_groups_v20.csv"
SIGNAL_EXEC_SUMMARY_CSV = OUTPUT_DIR / "signal_execution_summary_v20.csv"
SIGNAL_EXEC_LATEST_JSON = OUTPUT_DIR / "signal_execution_latest_v20.json"
ENV_REGIME_JSON = OUTPUT_DIR / "environment_regime_latest.json"
ENV_MEMORY_CSV = OUTPUT_DIR / "environment_memory_latest.csv"
ENV_VALIDATION_CSV = OUTPUT_DIR / "environment_validation_summary.csv"
SIGNAL_CLV_SUMMARY_CSV = OUTPUT_DIR / "signal_clv_summary.csv"
SIGNAL_RESULTS_SUMMARY_CSV = OUTPUT_DIR / "signal_results_summary.csv"
TELEGRAM_TXT = OUTPUT_DIR / "telegram_message.txt"
INJURY_DIR = OUTPUT_DIR / "injuries"

OUT_STATE = OUTPUT_DIR / "hermes_state_v20.json"
OUT_WARNINGS = OUTPUT_DIR / "hermes_warnings_v20.csv"
OUT_APPROVALS = OUTPUT_DIR / "hermes_approval_queue_v20.csv"


# -----------------------------------------------------------------------------
# Utilities
# -----------------------------------------------------------------------------

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def read_csv_safe(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception as exc:
        print(f"[WARN] Could not read {path}: {exc}")
        return pd.DataFrame()


def read_json_safe(path: Path, default: Any = None) -> Any:
    if default is None:
        default = {}
    if not path.exists():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"[WARN] Could not read {path}: {exc}")
        return default


def write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False, default=str), encoding="utf-8")


def norm_col(name: str) -> str:
    return "".join(ch.lower() for ch in str(name) if ch.isalnum())


def colmap(df: pd.DataFrame) -> Dict[str, str]:
    return {norm_col(c): c for c in df.columns}


def get_col(df: pd.DataFrame, *names: str) -> Optional[str]:
    if df.empty:
        return None
    cmap = colmap(df)
    for n in names:
        key = norm_col(n)
        if key in cmap:
            return cmap[key]
    return None


def val(row: pd.Series, *names: str, default: Any = None) -> Any:
    for name in names:
        if name in row.index:
            x = row.get(name)
            if pd.notna(x):
                return x
    return default


def to_float(x: Any, default: float = 0.0) -> float:
    if x is None:
        return default
    try:
        if isinstance(x, str):
            s = x.strip().replace("€", "").replace("u", "").replace("%", "").replace(",", ".")
            if s in {"", "nan", "None", "-"}:
                return default
            return float(s)
        if pd.isna(x):
            return default
        return float(x)
    except Exception:
        return default


def to_int(x: Any, default: int = 0) -> int:
    try:
        return int(round(to_float(x, default)))
    except Exception:
        return default


def to_str(x: Any, default: str = "") -> str:
    if x is None:
        return default
    try:
        if pd.isna(x):
            return default
    except Exception:
        pass
    return str(x).strip()


def money(x: float) -> str:
    return f"€{x:.2f}"


def units(x: float) -> str:
    return f"{x:.2f}u"


def pct(x: float) -> str:
    return f"{x:.1f}%"


def game_label_from_row(row: pd.Series) -> str:
    game = to_str(val(row, "game", "Game", "matchup", "Matchup", default=""))
    if game:
        return game
    away = to_str(val(row, "away", "Away", "away_team", "AwayTeam", default=""))
    home = to_str(val(row, "home", "Home", "home_team", "HomeTeam", default=""))
    if away or home:
        return f"{away} @ {home}".strip(" @")
    return "Slate game"


def market_label_from_row(row: pd.Series) -> str:
    market = to_str(val(row, "market", "Market", default=""))
    selection = to_str(val(row, "Selection", "selection", "Direction", "direction", default=""))
    line = val(row, "market_line", "MarketLine", "Line", "line", "model_line", "ModelLine", default="")
    if market and market.lower() not in {"market", "unknown"}:
        base = market
    elif selection.upper() in {"OVER", "UNDER"}:
        base = "Game Total"
    else:
        base = "Market"
    if selection:
        return f"{selection} {line}" if to_str(line) else selection
    return base


def first_row_dict(df: pd.DataFrame) -> Dict[str, Any]:
    if df.empty:
        return {}
    return {str(k): (None if pd.isna(v) else v) for k, v in df.iloc[0].to_dict().items()}


@dataclass
class WarningItem:
    severity: str
    category: str
    message: str
    action: str
    source: str


# -----------------------------------------------------------------------------
# State builders
# -----------------------------------------------------------------------------

def build_file_status() -> Dict[str, Any]:
    paths = {
        "projections_with_stakes": PROJECTIONS_STAKES_CSV,
        "recommended_bets": RECOMMENDED_CSV,
        "model_health_report": MODEL_HEALTH_CSV,
        "signal_execution_groups": SIGNAL_EXEC_GROUPS_CSV,
        "signal_execution_summary": SIGNAL_EXEC_SUMMARY_CSV,
        "environment_regime": ENV_REGIME_JSON,
        "environment_memory": ENV_MEMORY_CSV,
        "environment_validation": ENV_VALIDATION_CSV,
        "signal_clv_summary": SIGNAL_CLV_SUMMARY_CSV,
        "signal_results_summary": SIGNAL_RESULTS_SUMMARY_CSV,
        "bet_tracker": BET_CSV,
        "telegram_message": TELEGRAM_TXT,
    }
    status = {}
    for name, path in paths.items():
        status[name] = {
            "exists": path.exists(),
            "path": str(path.relative_to(ROOT)) if path.exists() else str(path),
            "modified_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds") if path.exists() else None,
            "size_bytes": path.stat().st_size if path.exists() else 0,
        }
    status["injury_dir"] = {
        "exists": INJURY_DIR.exists(),
        "path": str(INJURY_DIR.relative_to(ROOT)) if INJURY_DIR.exists() else str(INJURY_DIR),
        "file_count": len(list(INJURY_DIR.glob("*"))) if INJURY_DIR.exists() else 0,
    }
    return status


def build_model_health(warnings: List[WarningItem]) -> Dict[str, Any]:
    df = read_csv_safe(MODEL_HEALTH_CSV)
    if df.empty:
        warnings.append(WarningItem("HIGH", "model_health", "Model health report is missing.", "Run the validation/model health pipeline before allowing Hermes recommendations.", "model_health_report.csv"))
        return {"status": "MISSING", "health_label": "UNKNOWN", "score": None, "sample_warning": "MISSING"}

    r = df.iloc[-1]
    score = to_float(val(r, "ModelHealthScore", "model_health_score", default=0))
    label = to_str(val(r, "HealthLabel", "health_label", default="UNKNOWN"))
    sample_warning = to_str(val(r, "SampleWarning", "sample_warning", default=""))
    avg_clv = to_float(val(r, "AvgCLV", "avg_clv", default=0))
    beat_close = to_float(val(r, "BeatCloseRate", "beat_close_rate", default=0))
    sample_size = to_int(val(r, "SampleSize", "sample_size", "SignalsWithCLV", default=0))

    if label.upper() in {"RED", "BROKEN", "DANGER"} or score < 35:
        warnings.append(WarningItem("HIGH", "model_health", f"Model health is weak ({label}, score {score:.1f}).", "Keep automation locked and require manual review for every action.", "model_health_report.csv"))
    elif label.upper() in {"LEARNING", "YELLOW"} or sample_size < 50:
        warnings.append(WarningItem("MEDIUM", "model_health", f"Model is still in learning/sample-building mode ({label}).", "Treat output as informational until sample reliability improves.", "model_health_report.csv"))

    return {
        "status": "ONLINE",
        "health_label": label,
        "score": round(score, 2),
        "avg_clv": round(avg_clv, 3),
        "beat_close_rate": round(beat_close, 2),
        "sample_size": sample_size,
        "sample_warning": sample_warning,
        "formula_status": to_str(val(r, "FormulaStatus", default="")),
        "warning": to_str(val(r, "Warning", default="")),
    }


def build_environment(warnings: List[WarningItem]) -> Dict[str, Any]:
    env = read_json_safe(ENV_REGIME_JSON, {})
    mem = read_csv_safe(ENV_MEMORY_CSV)
    validation = read_csv_safe(ENV_VALIDATION_CSV)

    if not env:
        warnings.append(WarningItem("MEDIUM", "environment", "Environment regime file is missing.", "Run environment regime engine before relying on slate climate signals.", "environment_regime_latest.json"))
        return {"status": "MISSING", "regime": "UNKNOWN"}

    regime = to_str(env.get("environment_regime", env.get("Regime", "UNKNOWN")))
    reason = to_str(env.get("reason", env.get("Reason", "")))
    bucket_shares = env.get("bucket_shares", {}) if isinstance(env.get("bucket_shares", {}), dict) else {}
    sample = to_int(env.get("sample", env.get("Sample", 0)))
    avg_clv = to_float(env.get("avg_clv", 0))
    avg_chaos = to_float(env.get("avg_chaos", 0))
    avg_trust = to_float(env.get("avg_trust", 0))

    no_play_share = to_float(bucket_shares.get("neutral_no_play", bucket_shares.get("no_play", 0)))
    extreme_share = to_float(bucket_shares.get("extreme_over", 0))
    lean_share = to_float(bucket_shares.get("lean_over", 0))

    if sample < 20:
        warnings.append(WarningItem("MEDIUM", "environment", f"Environment sample is low ({sample}).", "Use environment labels as context, not as automatic betting rules.", "environment_regime_latest.json"))
    if no_play_share >= 50:
        warnings.append(WarningItem("MEDIUM", "environment", f"No-play/neutral share is high ({no_play_share:.1f}%).", "Require stronger edge and manual review for slate actions.", "environment_regime_latest.json"))
    if avg_chaos >= 35:
        warnings.append(WarningItem("HIGH", "environment", f"Slate chaos score is elevated ({avg_chaos:.1f}).", "Reduce action count and require injury/line confirmation.", "environment_regime_latest.json"))

    top_buckets = []
    if not validation.empty:
        sample_col = get_col(validation, "Sample")
        bucket_col = get_col(validation, "EnvironmentBucket")
        verdict_col = get_col(validation, "Verdict")
        clv_col = get_col(validation, "AvgCLV")
        for _, r in validation.head(5).iterrows():
            top_buckets.append({
                "bucket": to_str(r.get(bucket_col, "")) if bucket_col else "",
                "sample": to_int(r.get(sample_col, 0)) if sample_col else 0,
                "avg_clv": to_float(r.get(clv_col, 0)) if clv_col else 0,
                "verdict": to_str(r.get(verdict_col, "")) if verdict_col else "",
            })

    return {
        "status": "ONLINE",
        "regime": regime,
        "reason": reason,
        "sample": sample,
        "avg_clv": round(avg_clv, 3),
        "avg_chaos": round(avg_chaos, 2),
        "avg_trust": round(avg_trust, 2),
        "bucket_shares": bucket_shares,
        "no_play_share": round(no_play_share, 2),
        "extreme_over_share": round(extreme_share, 2),
        "lean_over_share": round(lean_share, 2),
        "memory_rows": len(mem),
        "validation_rows": len(validation),
        "top_bucket_validation": top_buckets,
    }


def build_bankroll_and_execution(warnings: List[WarningItem]) -> Dict[str, Any]:
    latest = read_json_safe(SIGNAL_EXEC_LATEST_JSON, {})
    groups = read_csv_safe(SIGNAL_EXEC_GROUPS_CSV)
    summary = read_csv_safe(SIGNAL_EXEC_SUMMARY_CSV)
    bets = read_csv_safe(BET_CSV)

    total_tickets = int(latest.get("total_tickets", len(bets) if not bets.empty else 0) or 0)
    total_groups = int(latest.get("total_groups", len(groups) if not groups.empty else 0) or 0)
    net_pl = to_float(latest.get("net_pl", latest.get("net_profit", 0)))

    total_staked = 0.0
    total_return = 0.0
    open_risk = 0.0
    wins = losses = pushes = 0

    if not bets.empty:
        c_stake = get_col(bets, "Stake", "ActualUnits", "SuggestedUnits")
        c_pl = get_col(bets, "P/L", "PL", "Profit", "ProfitLoss")
        c_status = get_col(bets, "Status")
        c_result = get_col(bets, "Result")
        c_odds = get_col(bets, "Odds")
        for _, r in bets.iterrows():
            stake = to_float(r.get(c_stake, 0)) if c_stake else 0.0
            pl = to_float(r.get(c_pl, 0)) if c_pl else 0.0
            odds = to_float(r.get(c_odds, 0)) if c_odds else 0.0
            status = to_str(r.get(c_status, "")).upper() if c_status else ""
            result = to_str(r.get(c_result, "")).upper() if c_result else ""
            total_staked += stake
            if status in {"OPEN", "PENDING", "PLACED"}:
                open_risk += stake
            else:
                total_return += max(0.0, stake + pl)
            if result == "WIN":
                wins += 1
            elif result == "LOSS":
                losses += 1
            elif result == "PUSH":
                pushes += 1

    if not groups.empty:
        # Correlation/grouper warnings
        fill_col = get_col(groups, "fill_count", "fills", "ticket_count")
        stake_col = get_col(groups, "grouped_stake", "total_stake", "stake")
        pl_col = get_col(groups, "grouped_profit", "profit", "net_pl")
        game_col = get_col(groups, "game")
        multi_fill_groups = 0
        max_fill_count = 0
        largest_group_stake = 0.0
        for _, r in groups.iterrows():
            fills = to_int(r.get(fill_col, 1)) if fill_col else 1
            stake = to_float(r.get(stake_col, 0)) if stake_col else 0.0
            max_fill_count = max(max_fill_count, fills)
            largest_group_stake = max(largest_group_stake, stake)
            if fills > 1:
                multi_fill_groups += 1
        if multi_fill_groups:
            warnings.append(WarningItem("INFO", "execution", f"Detected {multi_fill_groups} grouped execution signal(s) with multiple fills.", "Track these as one model signal with multiple execution fills, not as separate model wins.", "signal_execution_groups_v20.csv"))
        if max_fill_count >= 4:
            warnings.append(WarningItem("MEDIUM", "execution", f"Largest signal group has {max_fill_count} correlated fills.", "Confirm exposure is intentional and bankroll-safe before approving more fills on the same thesis.", "signal_execution_groups_v20.csv"))
    else:
        warnings.append(WarningItem("MEDIUM", "execution", "Signal execution groups are missing.", "Run signal_execution_bridge_v20.py before Hermes review.", "signal_execution_groups_v20.csv"))
        multi_fill_groups = 0
        max_fill_count = 0
        largest_group_stake = 0.0

    roi = (net_pl / total_staked * 100.0) if total_staked else 0.0
    settled = wins + losses + pushes
    win_rate = (wins / (wins + losses) * 100.0) if (wins + losses) else 0.0

    if open_risk > 1.5:
        warnings.append(WarningItem("MEDIUM", "bankroll", f"Open risk is {open_risk:.2f}u.", "Check daily exposure before approving new actions.", "bet_tracker.csv"))
    if net_pl < -1.0:
        warnings.append(WarningItem("HIGH", "bankroll", f"Net P/L is {net_pl:.2f}u.", "Consider daily stop-loss / reduced action mode.", "bet_tracker.csv"))

    return {
        "status": "ONLINE" if total_tickets or total_groups else "EMPTY",
        "total_tickets": total_tickets,
        "signal_groups": total_groups,
        "multi_fill_groups": multi_fill_groups,
        "max_fill_count": max_fill_count,
        "total_staked_units": round(total_staked, 3),
        "total_return_units": round(total_return, 3),
        "net_pl_units": round(net_pl, 3),
        "roi_percent": round(roi, 2),
        "open_risk_units": round(open_risk, 3),
        "settled_tickets": settled,
        "wins": wins,
        "losses": losses,
        "pushes": pushes,
        "ticket_win_rate": round(win_rate, 2),
        "largest_group_stake_units": round(largest_group_stake, 3),
        "summary_rows": len(summary),
    }


def build_recommended_actions(warnings: List[WarningItem]) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    rec = read_csv_safe(RECOMMENDED_CSV)
    proj = read_csv_safe(PROJECTIONS_STAKES_CSV)
    source = rec if not rec.empty else proj

    if source.empty:
        warnings.append(WarningItem("MEDIUM", "actions", "No recommended/projection actions found.", "Run the projection + staking pipeline before building approval queue.", "recommended_bets.csv"))
        return [], []

    rows = []
    pass_rows = []
    stake_col = get_col(source, "SuggestedUnits", "SuggestedUnitsRaw", "Stake", "ActualUnits")
    edge_col = get_col(source, "edge", "Edge")
    confidence_col = get_col(source, "confidence", "Confidence")
    grade_col = get_col(source, "confidence_grade", "ConfidenceGrade")
    signal_col = get_col(source, "signal", "FinalSignalNormalized", "FinalSignal", "raw_edge_signal")
    odds_col = get_col(source, "AssumedOdds", "odds", "Odds")
    line_col = get_col(source, "market_line", "MarketLine", "line", "Line")
    projection_col = get_col(source, "projection", "Projection")
    selection_col = get_col(source, "Selection", "selection", "Direction", "direction")
    reasons_col = get_col(source, "confidence_reasons", "ConfidenceReasons", "StakeReason", "reason")

    for i, r in source.iterrows():
        stake = to_float(r.get(stake_col, 0)) if stake_col else 0.0
        edge = to_float(r.get(edge_col, 0)) if edge_col else 0.0
        confidence = to_float(r.get(confidence_col, 0)) if confidence_col else 0.0
        signal = to_str(r.get(signal_col, "PASS")) if signal_col else "PASS"
        game = game_label_from_row(r)
        selection = to_str(r.get(selection_col, "")) if selection_col else ""
        line = to_float(r.get(line_col, 0)) if line_col else 0.0
        odds = to_float(r.get(odds_col, 0)) if odds_col else 0.0
        projection = to_float(r.get(projection_col, 0)) if projection_col else 0.0
        grade = to_str(r.get(grade_col, "")) if grade_col else ""
        reasons = to_str(r.get(reasons_col, "")) if reasons_col else ""
        market = f"{selection or 'Total'} {line:.1f}" if line else (selection or "Market")
        action = {
            "rank": len(rows) + 1 if stake > 0 else len(pass_rows) + 1,
            "game": game,
            "market": market,
            "selection": selection,
            "model_line": round(line, 2) if line else None,
            "assumed_odds": round(odds, 3) if odds else None,
            "projection": round(projection, 2) if projection else None,
            "edge": round(edge, 2),
            "confidence": round(confidence, 2),
            "confidence_grade": grade,
            "signal": signal,
            "suggested_units": round(stake, 3),
            "approval_state": "PENDING_MANUAL_APPROVAL" if stake > 0 else "PASS_NO_APPROVAL_REQUIRED",
            "why": reasons or f"Model edge {edge:.2f} with confidence {confidence:.0f}.",
            "risk": "Manual approval required. Confirm market line, injuries, and exposure before execution." if stake > 0 else "No stake recommended; keep as observation/pass.",
        }
        if stake > 0:
            rows.append(action)
        else:
            pass_rows.append(action)

    rows = sorted(rows, key=lambda x: (x.get("suggested_units", 0), x.get("edge", 0), x.get("confidence", 0)), reverse=True)
    for idx, item in enumerate(rows, 1):
        item["rank"] = idx

    if len(rows) > 5:
        warnings.append(WarningItem("MEDIUM", "actions", f"Approval queue has {len(rows)} recommended actions.", "Consider limiting action count or requiring stronger filters.", "recommended_bets.csv"))
    elif not rows:
        warnings.append(WarningItem("INFO", "actions", "No active recommended bets in current slate.", "Hermes should remain in observation mode.", "recommended_bets.csv"))

    return rows, pass_rows


def build_validation(warnings: List[WarningItem]) -> Dict[str, Any]:
    clv = read_csv_safe(SIGNAL_CLV_SUMMARY_CSV)
    results = read_csv_safe(SIGNAL_RESULTS_SUMMARY_CSV)

    overall_clv = {}
    if not clv.empty:
        group_col = get_col(clv, "Group")
        overall = clv[clv[group_col].astype(str).str.lower().eq("overall")] if group_col else pd.DataFrame()
        row = overall.iloc[0] if not overall.empty else clv.iloc[0]
        overall_clv = {
            "signals_with_clv": to_int(val(row, "SignalsWithCLV", default=0)),
            "beat_close_rate": to_float(val(row, "BeatCloseRate", default=0)),
            "avg_clv_points": to_float(val(row, "AvgCLVPoints", default=0)),
            "avg_clv_percent": to_float(val(row, "AvgCLVPercent", default=0)),
        }
        if overall_clv["signals_with_clv"] < 30:
            warnings.append(WarningItem("MEDIUM", "validation", f"CLV sample is low ({overall_clv['signals_with_clv']} signals).", "Avoid aggressive automation until CLV sample grows.", "signal_clv_summary.csv"))
        if overall_clv["beat_close_rate"] < 45 and overall_clv["signals_with_clv"] >= 10:
            warnings.append(WarningItem("MEDIUM", "validation", f"Beat-close rate is only {overall_clv['beat_close_rate']:.1f}%.", "Prioritize market/line quality review before scaling stakes.", "signal_clv_summary.csv"))
    else:
        warnings.append(WarningItem("MEDIUM", "validation", "CLV summary is missing.", "Run signal_clv_auto_v1.py / validation pipeline.", "signal_clv_summary.csv"))

    overall_results = {}
    if not results.empty:
        group_col = get_col(results, "Group")
        overall = results[results[group_col].astype(str).str.lower().eq("overall")] if group_col else pd.DataFrame()
        row = overall.iloc[0] if not overall.empty else results.iloc[0]
        overall_results = {
            "signals": to_int(val(row, "Signals", default=0)),
            "wins": to_int(val(row, "Wins", default=0)),
            "losses": to_int(val(row, "Losses", default=0)),
            "pushes": to_int(val(row, "Pushes", default=0)),
            "win_rate": to_float(val(row, "WinRate", default=0)),
            "avg_edge": to_float(val(row, "AvgEdge", default=0)),
        }
        if overall_results["signals"] < 50:
            warnings.append(WarningItem("MEDIUM", "validation", f"Result sample is low ({overall_results['signals']} graded signals).", "Keep Hermes in manual approval mode.", "signal_results_summary.csv"))
    else:
        warnings.append(WarningItem("MEDIUM", "validation", "Signal results summary is missing.", "Run result grader / validation pipeline.", "signal_results_summary.csv"))

    return {
        "status": "ONLINE" if overall_clv or overall_results else "MISSING",
        "clv": overall_clv,
        "results": overall_results,
    }


def build_injuries(warnings: List[WarningItem]) -> Dict[str, Any]:
    if not INJURY_DIR.exists():
        warnings.append(WarningItem("MEDIUM", "injuries", "Injury directory is missing.", "Do not approve actions without injury confirmation.", "wnba_outputs/injuries"))
        return {"status": "MISSING", "file_count": 0, "latest_file": None, "notes": "No injury feed available."}

    files = sorted([p for p in INJURY_DIR.glob("*") if p.is_file()], key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        warnings.append(WarningItem("MEDIUM", "injuries", "Injury directory exists but contains no files.", "Fetch injuries before approving actions.", "wnba_outputs/injuries"))
        return {"status": "EMPTY", "file_count": 0, "latest_file": None, "notes": "No injury files found."}

    latest = files[0]
    latest_age_hours = (datetime.now().timestamp() - latest.stat().st_mtime) / 3600.0
    if latest_age_hours > 24:
        warnings.append(WarningItem("MEDIUM", "injuries", f"Latest injury file is {latest_age_hours:.1f} hours old.", "Refresh injury feed before approving bets.", str(latest.relative_to(ROOT))))

    # Optional shallow read for CSV/json counts.
    record_count = None
    if latest.suffix.lower() == ".csv":
        d = read_csv_safe(latest)
        record_count = len(d)
    elif latest.suffix.lower() == ".json":
        payload = read_json_safe(latest, [])
        if isinstance(payload, list):
            record_count = len(payload)
        elif isinstance(payload, dict):
            record_count = len(payload.get("injuries", payload.get("items", []))) if isinstance(payload.get("injuries", payload.get("items", [])), list) else None

    return {
        "status": "ONLINE",
        "file_count": len(files),
        "latest_file": str(latest.relative_to(ROOT)),
        "latest_modified_at": datetime.fromtimestamp(latest.stat().st_mtime).isoformat(timespec="seconds"),
        "latest_age_hours": round(latest_age_hours, 2),
        "latest_record_count": record_count,
        "approval_note": "Injury state must be checked before manual approval.",
    }


def build_telegram(warnings: List[WarningItem], approval_queue: List[Dict[str, Any]]) -> Dict[str, Any]:
    exists = TELEGRAM_TXT.exists()
    text = TELEGRAM_TXT.read_text(encoding="utf-8", errors="ignore") if exists else ""
    ready = exists and bool(text.strip())
    if approval_queue and not ready:
        warnings.append(WarningItem("INFO", "telegram", "Telegram message is missing while approvals exist.", "Generate Telegram draft only after manual approval queue is reviewed.", "telegram_message.txt"))
    return {
        "status": "READY" if ready else "MISSING",
        "exists": exists,
        "characters": len(text),
        "preview": text[:500].strip(),
        "rule": "Telegram draft is preparation only; sending requires manual approval.",
    }


def build_automation_locks(warnings: List[WarningItem], model_health: Dict[str, Any], bankroll: Dict[str, Any], injuries: Dict[str, Any], environment: Dict[str, Any]) -> Dict[str, Any]:
    locks = []
    locks.append("MANUAL_APPROVAL_REQUIRED")
    if model_health.get("health_label", "").upper() in {"LEARNING", "YELLOW", "UNKNOWN"}:
        locks.append("MODEL_SAMPLE_LOCK")
    if injuries.get("status") in {"MISSING", "EMPTY"}:
        locks.append("INJURY_CONFIRMATION_LOCK")
    if environment.get("sample", 0) < 20:
        locks.append("ENVIRONMENT_SAMPLE_LOCK")
    if bankroll.get("open_risk_units", 0) > 1.5:
        locks.append("OPEN_EXPOSURE_REVIEW_LOCK")
    if bankroll.get("net_pl_units", 0) < -1.0:
        locks.append("DRAWDOWN_REVIEW_LOCK")

    return {
        "mode": "manual_approval",
        "full_automation": "LOCKED",
        "telegram_auto_send": "LOCKED",
        "bet_execution": "LOCKED",
        "active_locks": sorted(set(locks)),
        "rule": "Hermes can observe, warn, recommend, and draft. Hermes cannot place/send/execute without explicit human approval.",
    }


def build_mission_brief(actions: List[Dict[str, Any]], warnings: List[WarningItem], model_health: Dict[str, Any], environment: Dict[str, Any], bankroll: Dict[str, Any]) -> Dict[str, Any]:
    high = [w for w in warnings if w.severity.upper() == "HIGH"]
    medium = [w for w in warnings if w.severity.upper() == "MEDIUM"]
    top_action = actions[0] if actions else None

    if high:
        mode = "PROTECT_CAPITAL"
        headline = "High-priority guardrail active. Manual review required before any action."
    elif actions:
        mode = "REVIEW_QUEUE"
        headline = f"{len(actions)} action(s) pending manual approval."
    else:
        mode = "OBSERVE"
        headline = "No active betting queue. Stay in observation mode."

    brief = {
        "mode": mode,
        "headline": headline,
        "top_action": top_action,
        "priority_warning_count": len(high),
        "warning_count": len(warnings),
        "model_state": model_health.get("health_label", "UNKNOWN"),
        "environment_regime": environment.get("regime", "UNKNOWN"),
        "open_risk_units": bankroll.get("open_risk_units", 0),
        "net_pl_units": bankroll.get("net_pl_units", 0),
        "operator_instruction": "Confirm market line, injuries, exposure, and validation before approval.",
        "hermes_next_step": "Prepare concise mission brief and approval queue; do not execute bets.",
    }
    return brief


# -----------------------------------------------------------------------------
# Main
# -----------------------------------------------------------------------------

def build_state() -> Dict[str, Any]:
    warnings: List[WarningItem] = []

    file_status = build_file_status()
    model_health = build_model_health(warnings)
    environment = build_environment(warnings)
    bankroll = build_bankroll_and_execution(warnings)
    actions, pass_rows = build_recommended_actions(warnings)
    validation = build_validation(warnings)
    injuries = build_injuries(warnings)
    telegram = build_telegram(warnings, actions)
    automation_locks = build_automation_locks(warnings, model_health, bankroll, injuries, environment)
    mission_brief = build_mission_brief(actions, warnings, model_health, environment, bankroll)

    warning_rows = [asdict(w) for w in warnings]
    approval_queue = actions

    # Write tabular outputs for dashboard integration.
    pd.DataFrame(warning_rows).to_csv(OUT_WARNINGS, index=False)
    pd.DataFrame(approval_queue).to_csv(OUT_APPROVALS, index=False)

    state = {
        "schema_version": "v20.0",
        "generated_at": utc_now_iso(),
        "system": {
            "name": "WNBA Edge Lab",
            "component": "Hermes State Builder",
            "mode": "manual_approval",
            "website_version_target": "v20 model-support",
        },
        "mission_brief": mission_brief,
        "automation": automation_locks,
        "bankroll": bankroll,
        "model_health": model_health,
        "environment": environment,
        "validation": validation,
        "injuries": injuries,
        "recommended_actions": approval_queue,
        "pass_no_play_review": pass_rows[:12],
        "approval_queue": {
            "count": len(approval_queue),
            "items": approval_queue,
            "rule": "Every item requires manual approval before execution or Telegram send.",
        },
        "warnings": {
            "count": len(warning_rows),
            "high": sum(1 for w in warnings if w.severity.upper() == "HIGH"),
            "medium": sum(1 for w in warnings if w.severity.upper() == "MEDIUM"),
            "items": warning_rows,
        },
        "telegram": telegram,
        "file_status": file_status,
        "outputs": {
            "state_json": str(OUT_STATE.relative_to(ROOT)),
            "warnings_csv": str(OUT_WARNINGS.relative_to(ROOT)),
            "approval_queue_csv": str(OUT_APPROVALS.relative_to(ROOT)),
        },
    }
    write_json(OUT_STATE, state)
    return state


def main() -> None:
    state = build_state()
    print("OK: V20 Hermes State Builder complete")
    print(f"State:     {OUT_STATE}")
    print(f"Warnings:  {OUT_WARNINGS}")
    print(f"Approvals: {OUT_APPROVALS}")
    print(f"Mode:      {state['automation']['mode']}")
    print(f"Locks:     {', '.join(state['automation']['active_locks'])}")
    print(f"Actions:   {state['approval_queue']['count']} pending manual approval")
    print(f"Warnings:  {state['warnings']['count']} total / {state['warnings']['high']} high")


if __name__ == "__main__":
    main()
