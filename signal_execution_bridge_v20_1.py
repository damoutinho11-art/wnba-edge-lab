"""
WNBA Edge Lab — V20 Signal-to-Execution Bridge

Purpose
-------
Separate model signals from execution fills.

Correct accounting model:
    1 model signal -> multiple execution fills -> 1 grouped settlement

This prevents the system from treating line-shopping/laddered fills as several
independent model signals. It also gives Hermes a clean execution-quality state.

Inputs, if present:
    bet_tracker.csv
    bet_tracker.db
    wnba_outputs/recommended_bets.csv
    wnba_outputs/projections_with_stakes.csv
    wnba_outputs/signal_tracker_with_clv.csv
    wnba_outputs/signal_tracker_graded.csv

Outputs:
    wnba_outputs/signal_execution_groups_v20.csv
    wnba_outputs/signal_execution_summary_v20.csv
    wnba_outputs/signal_execution_latest_v20.json

Run:
    python signal_execution_bridge_v20.py
"""

from __future__ import annotations

import json
import math
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "wnba_outputs"
OUTPUT_DIR.mkdir(exist_ok=True)

BET_CSV = ROOT / "bet_tracker.csv"
BET_DB = ROOT / "bet_tracker.db"
RECOMMENDED_CSV = OUTPUT_DIR / "recommended_bets.csv"
PROJECTIONS_STAKES_CSV = OUTPUT_DIR / "projections_with_stakes.csv"
SIGNAL_CLV_CSV = OUTPUT_DIR / "signal_tracker_with_clv.csv"
SIGNAL_GRADED_CSV = OUTPUT_DIR / "signal_tracker_graded.csv"

OUT_GROUPS = OUTPUT_DIR / "signal_execution_groups_v20.csv"
OUT_SUMMARY = OUTPUT_DIR / "signal_execution_summary_v20.csv"
OUT_LATEST = OUTPUT_DIR / "signal_execution_latest_v20.json"


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


def norm_col(name: str) -> str:
    return "".join(ch.lower() for ch in str(name) if ch.isalnum())


def colmap(df: pd.DataFrame) -> Dict[str, str]:
    return {norm_col(c): c for c in df.columns}


def get_col(df: pd.DataFrame, *names: str) -> Optional[str]:
    cmap = colmap(df)
    for n in names:
        key = norm_col(n)
        if key in cmap:
            return cmap[key]
    return None


def get_val(row: pd.Series, *names: str, default: Any = None) -> Any:
    for n in names:
        if n in row.index:
            v = row.get(n)
            if pd.notna(v):
                return v
    return default


def to_float(x: Any, default: float = 0.0) -> float:
    if x is None:
        return default
    try:
        if isinstance(x, str):
            s = x.strip().replace("€", "").replace("u", "").replace(",", ".")
            if s in {"", "nan", "None", "-"}:
                return default
            return float(s)
        if pd.isna(x):
            return default
        return float(x)
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


def normalize_game(game: str) -> str:
    g = to_str(game).upper()
    replacements = {
        " VS ": " @ ",
        " V ": " @ ",
        " - ": " @ ",
        "–": " @ ",
        "—": " @ ",
        "WSH": "WAS",  # common sportsbook vs model code mismatch
        "LA ": "LAS ",  # avoid loose match only where useful
    }
    for a, b in replacements.items():
        g = g.replace(a, b)
    return " ".join(g.split())


def game_from_teams(away: Any, home: Any) -> str:
    a, h = to_str(away).upper(), to_str(home).upper()
    return normalize_game(f"{a} @ {h}") if a or h else ""


def normalize_market(market: str) -> str:
    m = to_str(market).lower()
    if "total" in m:
        return "game_total"
    if "points" in m and "rebound" in m:
        return "points_rebounds"
    if "point" in m and "reb" in m:
        return "points_rebounds"
    if "rebound" in m:
        return "rebounds"
    if "point" in m:
        return "points"
    return m.replace(" ", "_") or "unknown"


def normalize_side(side: str) -> str:
    s = to_str(side).upper()
    if "OVER" in s:
        return "OVER"
    if "UNDER" in s:
        return "UNDER"
    if s in {"O", "OV"}:
        return "OVER"
    if s in {"U", "UN"}:
        return "UNDER"
    return s or "UNKNOWN"


def money_fmt(x: float) -> str:
    return f"€{x:.2f}"


def pct_fmt(x: float) -> str:
    return f"{x:.1f}%"


# -----------------------------------------------------------------------------
# Loaders
# -----------------------------------------------------------------------------

def load_bets() -> pd.DataFrame:
    bets = read_csv_safe(BET_CSV)

    # Fallback to SQLite if CSV missing/empty.
    if bets.empty and BET_DB.exists():
        try:
            conn = sqlite3.connect(BET_DB)
            tables = pd.read_sql_query("SELECT name FROM sqlite_master WHERE type='table'", conn)
            for t in tables["name"].tolist():
                candidate = pd.read_sql_query(f"SELECT * FROM {t}", conn)
                if not candidate.empty:
                    bets = candidate
                    break
            conn.close()
        except Exception as exc:
            print(f"[WARN] Could not read {BET_DB}: {exc}")

    if bets.empty:
        return bets

    # Normalize important columns without destroying originals.
    c_game = get_col(bets, "Game", "game")
    c_market = get_col(bets, "Market", "market")
    c_dir = get_col(bets, "Direction", "Selection", "Side")
    c_line = get_col(bets, "Line", "ExecutedLine")
    c_odds = get_col(bets, "Odds", "ExecutedOdds")
    c_stake = get_col(bets, "Stake", "ActualUnits", "SuggestedUnits")
    c_pl = get_col(bets, "P/L", "PL", "Profit", "ProfitLoss")
    c_status = get_col(bets, "Status")
    c_result = get_col(bets, "Result")
    c_actual = get_col(bets, "Actual", "ActualTotal")
    c_date = get_col(bets, "Date", "SignalDate")
    c_signal = get_col(bets, "Signal", "FinalSignal")
    c_model = get_col(bets, "ModelVersion")
    c_projection = get_col(bets, "Projection")
    c_edge = get_col(bets, "Edge")
    c_conf = get_col(bets, "Confidence")
    c_closing = get_col(bets, "ClosingLine")
    c_opening = get_col(bets, "OpeningLine")

    bets["_game_norm"] = bets[c_game].map(normalize_game) if c_game else ""
    bets["_market_norm"] = bets[c_market].map(normalize_market) if c_market else "unknown"
    bets["_side_norm"] = bets[c_dir].map(normalize_side) if c_dir else "UNKNOWN"
    bets["_line"] = bets[c_line].map(to_float) if c_line else 0.0
    bets["_odds"] = bets[c_odds].map(to_float) if c_odds else 0.0
    bets["_stake"] = bets[c_stake].map(to_float) if c_stake else 0.0
    bets["_pl"] = bets[c_pl].map(to_float) if c_pl else bets.apply(lambda r: infer_pl(r, c_result, c_odds, c_stake), axis=1)
    bets["_status"] = bets[c_status].map(lambda x: to_str(x).upper()) if c_status else "UNKNOWN"
    bets["_result"] = bets[c_result].map(lambda x: to_str(x).upper()) if c_result else "UNKNOWN"
    bets["_actual"] = bets[c_actual].map(to_float) if c_actual else math.nan
    bets["_date"] = bets[c_date].map(to_str) if c_date else ""
    bets["_signal_text"] = bets[c_signal].map(to_str) if c_signal else ""
    bets["_model_version"] = bets[c_model].map(to_str) if c_model else ""
    bets["_projection"] = bets[c_projection].map(to_float) if c_projection else math.nan
    bets["_edge"] = bets[c_edge].map(to_float) if c_edge else math.nan
    bets["_confidence"] = bets[c_conf].map(to_float) if c_conf else math.nan
    bets["_closing_line"] = bets[c_closing].map(to_float) if c_closing else math.nan
    bets["_opening_line"] = bets[c_opening].map(to_float) if c_opening else math.nan

    return bets


def infer_pl(row: pd.Series, c_result: Optional[str], c_odds: Optional[str], c_stake: Optional[str]) -> float:
    result = to_str(row.get(c_result) if c_result else "").upper()
    odds = to_float(row.get(c_odds) if c_odds else 0)
    stake = to_float(row.get(c_stake) if c_stake else 0)
    if result == "WIN":
        return stake * max(odds - 1.0, 0.0)
    if result == "LOSS":
        return -stake
    return 0.0


def load_signals() -> pd.DataFrame:
    # Prefer graded because it contains result information; otherwise CLV; otherwise recommended/projections.
    for path in [SIGNAL_GRADED_CSV, SIGNAL_CLV_CSV, RECOMMENDED_CSV, PROJECTIONS_STAKES_CSV]:
        df = read_csv_safe(path)
        if not df.empty:
            return normalize_signals(df, source=path.name)
    return pd.DataFrame()


def normalize_signals(df: pd.DataFrame, source: str) -> pd.DataFrame:
    out = df.copy()

    c_signal_id = get_col(out, "SignalID")
    c_game = get_col(out, "Game")
    c_away = get_col(out, "Away", "away")
    c_home = get_col(out, "Home", "home")
    c_market = get_col(out, "Market")
    c_sel = get_col(out, "Selection")
    c_line = get_col(out, "LineAtSignal", "market_line")
    c_consensus = get_col(out, "ConsensusLine", "consensus_line")
    c_projection = get_col(out, "Projection", "projection")
    c_edge = get_col(out, "Edge", "edge")
    c_signal = get_col(out, "FinalSignal", "FinalSignalNormalized", "signal")
    c_odds = get_col(out, "AssumedOdds")
    c_units = get_col(out, "SuggestedUnits")
    c_stake = get_col(out, "SuggestedStake")
    c_conf = get_col(out, "Confidence", "confidence")
    c_grade = get_col(out, "ConfidenceGrade", "confidence_grade")
    c_closing = get_col(out, "ClosingLine")
    c_clv = get_col(out, "CLV_Points")
    c_actual = get_col(out, "ActualTotal")
    c_result = get_col(out, "WouldHaveWon", "ResultStatus")
    c_model = get_col(out, "ModelVersion", "model_version")
    c_date = get_col(out, "SignalDate", "commence_time")

    if c_game:
        out["_game_norm"] = out[c_game].map(normalize_game)
    elif c_away and c_home:
        out["_game_norm"] = out.apply(lambda r: game_from_teams(r[c_away], r[c_home]), axis=1)
    else:
        out["_game_norm"] = ""

    out["_market_norm"] = out[c_market].map(normalize_market) if c_market else "game_total"
    out["_side_norm"] = out[c_sel].map(normalize_side) if c_sel else out[c_signal].map(infer_side_from_signal) if c_signal else "UNKNOWN"
    out["_line_at_signal"] = out[c_line].map(to_float) if c_line else out[c_consensus].map(to_float) if c_consensus else 0.0
    out["_projection"] = out[c_projection].map(to_float) if c_projection else math.nan
    out["_edge"] = out[c_edge].map(to_float) if c_edge else math.nan
    out["_signal_text"] = out[c_signal].map(to_str) if c_signal else ""
    out["_assumed_odds"] = out[c_odds].map(to_float) if c_odds else 0.0
    out["_suggested_units"] = out[c_units].map(to_float) if c_units else 0.0
    out["_suggested_stake"] = out[c_stake].map(to_float) if c_stake else 0.0
    out["_confidence"] = out[c_conf].map(to_float) if c_conf else math.nan
    out["_confidence_grade"] = out[c_grade].map(to_str) if c_grade else ""
    out["_closing_line"] = out[c_closing].map(to_float) if c_closing else math.nan
    out["_clv_points"] = out[c_clv].map(to_float) if c_clv else math.nan
    out["_actual_total"] = out[c_actual].map(to_float) if c_actual else math.nan
    out["_result_status"] = out[c_result].map(to_str) if c_result else ""
    out["_model_version"] = out[c_model].map(to_str) if c_model else ""
    out["_date"] = out[c_date].map(lambda x: to_str(x)[:10]) if c_date else ""
    out["_source_file"] = source

    if c_signal_id:
        out["_signal_id"] = out[c_signal_id].map(to_str)
    else:
        out["_signal_id"] = out.apply(make_signal_id, axis=1)

    return out


def infer_side_from_signal(x: Any) -> str:
    return normalize_side(to_str(x))


def make_signal_id(row: pd.Series) -> str:
    date = to_str(row.get("_date")) or "unknown-date"
    game = to_str(row.get("_game_norm")) or "unknown-game"
    market = to_str(row.get("_market_norm")) or "unknown-market"
    side = to_str(row.get("_side_norm")) or "unknown-side"
    line = to_float(row.get("_line_at_signal"))
    model = to_str(row.get("_model_version")) or "unknown-model"
    return f"{date}|WNBA|{game}|{market}|{side}|{line:g}|{model}"


# -----------------------------------------------------------------------------
# Matching and grouping
# -----------------------------------------------------------------------------

def side_clv_points(side: str, signal_line: float, closing_line: float) -> float:
    if pd.isna(signal_line) or pd.isna(closing_line):
        return math.nan
    side = normalize_side(side)
    # For OVER, lower close than signal is favorable to having bet Over earlier only if you executed better line later.
    # For model signal CLV, standard line-value relative to close:
    #   OVER signal at 169.5, close 165.5 means close moved against the model if interpreted strictly.
    # However user clarified execution was at better/safer lines after market changed.
    # We therefore store both strict_model_clv and execution_line_value elsewhere.
    if side == "OVER":
        return closing_line - signal_line
    if side == "UNDER":
        return signal_line - closing_line
    return closing_line - signal_line


def execution_line_value(side: str, model_line: float, executed_line: float) -> float:
    if pd.isna(model_line) or pd.isna(executed_line):
        return math.nan
    side = normalize_side(side)
    # How much better the executed fill is versus the original model line.
    if side == "OVER":
        return model_line - executed_line  # lower Over line = better execution
    if side == "UNDER":
        return executed_line - model_line  # higher Under line = better execution
    return model_line - executed_line


def match_signal_for_group(group_key: Tuple[str, str, str], bets_g: pd.DataFrame, signals: pd.DataFrame) -> Optional[pd.Series]:
    if signals.empty:
        return None
    game, market, side = group_key
    candidates = signals[
        (signals["_game_norm"] == game)
        & (signals["_market_norm"] == market)
        & (signals["_side_norm"] == side)
    ].copy()
    if candidates.empty:
        # If exact side missing, allow game+market only.
        candidates = signals[(signals["_game_norm"] == game) & (signals["_market_norm"] == market)].copy()
    if candidates.empty:
        return None

    # Prefer non-PASS and highest suggested units/confidence/absolute edge.
    candidates["_is_action"] = ~candidates["_signal_text"].str.upper().str.contains("PASS", na=False)
    candidates["_score"] = (
        candidates["_is_action"].astype(int) * 1000
        + candidates["_suggested_units"].fillna(0) * 100
        + candidates["_confidence"].fillna(0)
        + candidates["_edge"].abs().fillna(0)
    )
    candidates = candidates.sort_values("_score", ascending=False)
    return candidates.iloc[0]


def group_bets(bets: pd.DataFrame, signals: pd.DataFrame) -> pd.DataFrame:
    if bets.empty:
        return pd.DataFrame()

    group_cols = ["_date", "_game_norm", "_market_norm", "_side_norm"]
    rows: List[Dict[str, Any]] = []

    for key, g in bets.groupby(group_cols, dropna=False):
        date, game, market, side = key
        signal = match_signal_for_group((game, market, side), g, signals)

        lines = [to_float(x, math.nan) for x in g["_line"].tolist()]
        odds = [to_float(x, math.nan) for x in g["_odds"].tolist()]
        stakes = [to_float(x, 0) for x in g["_stake"].tolist()]
        pls = [to_float(x, 0) for x in g["_pl"].tolist()]
        settled_mask = g["_status"].str.upper().eq("SETTLED") | g["_result"].isin(["WIN", "LOSS", "PUSH"])

        total_stake = sum(stakes)
        total_profit = sum(pls)
        # Return = stake + profit for winners/losses combined at portfolio level.
        total_return = total_stake + total_profit if settled_mask.any() else 0.0
        roi = (total_profit / total_stake * 100.0) if total_stake else 0.0

        valid_lines = [x for x in lines if not pd.isna(x)]
        valid_odds = [x for x in odds if not pd.isna(x) and x > 0]
        avg_line = sum(valid_lines) / len(valid_lines) if valid_lines else math.nan
        avg_odds = sum(valid_odds) / len(valid_odds) if valid_odds else math.nan

        if normalize_side(side) == "OVER":
            best_line = min(valid_lines) if valid_lines else math.nan
            worst_line = max(valid_lines) if valid_lines else math.nan
        elif normalize_side(side) == "UNDER":
            best_line = max(valid_lines) if valid_lines else math.nan
            worst_line = min(valid_lines) if valid_lines else math.nan
        else:
            best_line = min(valid_lines) if valid_lines else math.nan
            worst_line = max(valid_lines) if valid_lines else math.nan

        model_signal_id = ""
        model_line = math.nan
        model_odds = math.nan
        model_projection = math.nan
        model_edge = math.nan
        model_confidence = math.nan
        confidence_grade = ""
        final_signal = ""
        closing_line = math.nan
        strict_model_clv = math.nan
        model_source = "unmatched"

        if signal is not None:
            model_signal_id = to_str(signal.get("_signal_id"))
            model_line = to_float(signal.get("_line_at_signal"), math.nan)
            model_odds = to_float(signal.get("_assumed_odds"), math.nan)
            model_projection = to_float(signal.get("_projection"), math.nan)
            model_edge = to_float(signal.get("_edge"), math.nan)
            model_confidence = to_float(signal.get("_confidence"), math.nan)
            confidence_grade = to_str(signal.get("_confidence_grade"))
            final_signal = to_str(signal.get("_signal_text"))
            closing_line = to_float(signal.get("_closing_line"), math.nan)
            strict_model_clv = to_float(signal.get("_clv_points"), math.nan)
            if pd.isna(strict_model_clv) and not pd.isna(closing_line):
                strict_model_clv = side_clv_points(side, model_line, closing_line)
            model_source = to_str(signal.get("_source_file"))
        else:
            # Use bet-level metadata if available.
            model_line = to_float(g["_opening_line"].dropna().iloc[0], math.nan) if g["_opening_line"].notna().any() else math.nan
            closing_line = to_float(g["_closing_line"].dropna().iloc[0], math.nan) if g["_closing_line"].notna().any() else math.nan
            model_projection = to_float(g["_projection"].dropna().iloc[0], math.nan) if g["_projection"].notna().any() else math.nan
            model_edge = to_float(g["_edge"].dropna().iloc[0], math.nan) if g["_edge"].notna().any() else math.nan
            model_confidence = to_float(g["_confidence"].dropna().iloc[0], math.nan) if g["_confidence"].notna().any() else math.nan
            final_signal = to_str(g["_signal_text"].dropna().iloc[0]) if g["_signal_text"].notna().any() else ""
            model_signal_id = f"EXEC_ONLY|{date}|{game}|{market}|{side}|{avg_line:g}"

        exec_values = [execution_line_value(side, model_line, x) for x in valid_lines] if not pd.isna(model_line) else []
        exec_values_clean = [x for x in exec_values if not pd.isna(x)]
        avg_exec_value = sum(exec_values_clean) / len(exec_values_clean) if exec_values_clean else math.nan
        best_exec_value = max(exec_values_clean) if exec_values_clean else math.nan

        result_status = infer_group_result(g)
        actual = infer_actual(g)
        tickets = len(g)
        correlated = tickets > 1
        execution_type = "grouped_execution" if tickets > 1 else "single_execution"
        exposure_label = "CORRELATED" if correlated else "SINGLE"

        if tickets > 1:
            hermes_note = (
                f"Grouped {tickets} fills as one {side} {market} thesis. "
                "Count bankroll P/L per ticket, but count validation as one model signal."
            )
        else:
            hermes_note = "Single execution fill. Count as one signal/fill unless manually linked otherwise."

        if correlated and not pd.isna(avg_exec_value):
            if avg_exec_value > 0:
                hermes_note += f" Execution improved average line by {avg_exec_value:.2f} pts versus model line."
            elif avg_exec_value < 0:
                hermes_note += f" Execution was {abs(avg_exec_value):.2f} pts worse than model line."

        row = {
            "GroupID": f"{date}|{game}|{market}|{side}",
            "Date": date,
            "Game": game,
            "Market": market,
            "Side": side,
            "ModelSignalID": model_signal_id,
            "ModelSource": model_source,
            "ModelSignal": final_signal,
            "ModelLine": model_line,
            "ModelOdds": model_odds,
            "ModelProjection": model_projection,
            "ModelEdge": model_edge,
            "ModelConfidence": model_confidence,
            "ConfidenceGrade": confidence_grade,
            "ClosingLine": closing_line,
            "StrictModelCLVPoints": strict_model_clv,
            "ExecutionTickets": tickets,
            "ExecutionType": execution_type,
            "ExposureLabel": exposure_label,
            "ExecutedLines": ", ".join(f"{x:g}" for x in valid_lines),
            "ExecutedOdds": ", ".join(f"{x:g}" for x in valid_odds),
            "AverageExecutedLine": avg_line,
            "BestExecutedLine": best_line,
            "WorstExecutedLine": worst_line,
            "AverageExecutedOdds": avg_odds,
            "AverageExecutionLineValue": avg_exec_value,
            "BestExecutionLineValue": best_exec_value,
            "TotalStake": total_stake,
            "TotalReturn": total_return,
            "NetProfit": total_profit,
            "ROI_Percent": roi,
            "Status": result_status,
            "Actual": actual,
            "BetIDs": ", ".join(g[get_col(g, "BetID")].map(to_str).tolist()) if get_col(g, "BetID") else "",
            "HermesNote": hermes_note,
            "UpdatedAt": utc_now_iso(),
        }
        rows.append(row)

    groups = pd.DataFrame(rows)
    if not groups.empty:
        groups = groups.sort_values(["Date", "Game", "Market", "Side"], ascending=[False, True, True, True])
    return groups


def infer_group_result(g: pd.DataFrame) -> str:
    results = set(g["_result"].dropna().astype(str).str.upper().tolist())
    statuses = set(g["_status"].dropna().astype(str).str.upper().tolist())
    if "OPEN" in statuses and not ({"WIN", "LOSS", "PUSH"} & results):
        return "OPEN"
    if results == {"WIN"}:
        return "WON"
    if results == {"LOSS"}:
        return "LOST"
    if "PUSH" in results and len(results) == 1:
        return "PUSH"
    if {"WIN", "LOSS"} & results:
        return "MIXED"
    if "SETTLED" in statuses:
        return "SETTLED"
    return "UNKNOWN"


def infer_actual(g: pd.DataFrame) -> float:
    vals = [to_float(x, math.nan) for x in g["_actual"].tolist()]
    vals = [x for x in vals if not pd.isna(x)]
    if not vals:
        return math.nan
    # For same game totals this should be identical. Return max frequency-ish via first non-null.
    return vals[0]


def build_summary(groups: pd.DataFrame) -> pd.DataFrame:
    if groups.empty:
        return pd.DataFrame([
            {
                "Metric": "signal_execution_groups",
                "Value": 0,
                "UpdatedAt": utc_now_iso(),
            }
        ])

    total_groups = len(groups)
    total_tickets = int(groups["ExecutionTickets"].sum())
    total_stake = float(groups["TotalStake"].sum())
    total_profit = float(groups["NetProfit"].sum())
    total_return = float(groups["TotalReturn"].sum())
    roi = (total_profit / total_stake * 100.0) if total_stake else 0.0
    correlated = int((groups["ExecutionTickets"] > 1).sum())
    open_groups = int(groups["Status"].astype(str).str.upper().eq("OPEN").sum())
    settled_groups = total_groups - open_groups

    avg_exec_value = groups["AverageExecutionLineValue"].dropna()
    avg_exec_value_val = float(avg_exec_value.mean()) if not avg_exec_value.empty else math.nan

    rows = [
        ("signal_groups", total_groups),
        ("execution_tickets", total_tickets),
        ("correlated_groups", correlated),
        ("open_groups", open_groups),
        ("settled_groups", settled_groups),
        ("total_stake", round(total_stake, 4)),
        ("total_return", round(total_return, 4)),
        ("net_profit", round(total_profit, 4)),
        ("roi_percent", round(roi, 2)),
        ("avg_execution_line_value", round(avg_exec_value_val, 3) if not pd.isna(avg_exec_value_val) else ""),
    ]
    return pd.DataFrame([{"Metric": k, "Value": v, "UpdatedAt": utc_now_iso()} for k, v in rows])


def build_latest_json(groups: pd.DataFrame, summary: pd.DataFrame) -> Dict[str, Any]:
    summary_dict = {str(r["Metric"]): r["Value"] for _, r in summary.iterrows()}
    latest_groups = []
    if not groups.empty:
        for _, r in groups.head(10).iterrows():
            latest_groups.append({
                "group_id": to_str(r.get("GroupID")),
                "date": to_str(r.get("Date")),
                "game": to_str(r.get("Game")),
                "market": to_str(r.get("Market")),
                "side": to_str(r.get("Side")),
                "model_line": to_float(r.get("ModelLine"), math.nan),
                "executed_lines": to_str(r.get("ExecutedLines")),
                "tickets": int(to_float(r.get("ExecutionTickets"), 0)),
                "stake": to_float(r.get("TotalStake"), 0),
                "profit": to_float(r.get("NetProfit"), 0),
                "roi_percent": to_float(r.get("ROI_Percent"), 0),
                "status": to_str(r.get("Status")),
                "exposure_label": to_str(r.get("ExposureLabel")),
                "hermes_note": to_str(r.get("HermesNote")),
            })

    warnings = []
    if summary_dict.get("correlated_groups", 0):
        warnings.append("Correlated execution groups detected. Count each group as one model signal for validation.")
    if summary_dict.get("open_groups", 0):
        warnings.append("Open execution groups exist. Bankroll settlement is not final.")

    return {
        "version": "v20_signal_execution_bridge",
        "updated_at": utc_now_iso(),
        "mode": "manual_approval",
        "summary": summary_dict,
        "latest_groups": latest_groups,
        "warnings": warnings,
        "rules": {
            "model_validation": "count one signal per ModelSignalID/GroupID, not one signal per execution fill",
            "bankroll": "count real ticket-level stake/return/profit",
            "hermes": "warn on correlated exposure; recognize improved execution line value separately from model quality",
        },
    }


def run() -> None:
    bets = load_bets()
    signals = load_signals()

    if bets.empty:
        print("[WARN] No bet tracker data found. Writing empty V20 signal-execution outputs.")
        groups = pd.DataFrame()
    else:
        groups = group_bets(bets, signals)

    summary = build_summary(groups)
    latest = build_latest_json(groups, summary)

    groups.to_csv(OUT_GROUPS, index=False)
    summary.to_csv(OUT_SUMMARY, index=False)
    OUT_LATEST.write_text(json.dumps(latest, indent=2, ensure_ascii=False), encoding="utf-8")

    print("OK: V20 Signal-to-Execution Bridge complete")
    print(f"Groups:  {OUT_GROUPS}")
    print(f"Summary: {OUT_SUMMARY}")
    print(f"Latest:  {OUT_LATEST}")
    if not groups.empty:
        print(f"Detected {len(groups)} signal/execution groups from {int(groups['ExecutionTickets'].sum())} tickets.")
        print(f"Net P/L: {money_fmt(float(groups['NetProfit'].sum()))}")


if __name__ == "__main__":
    run()
