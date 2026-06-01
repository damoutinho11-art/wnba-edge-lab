#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WNBA Edge Lab - Model Advisory Scoring V21

Purpose
-------
Create a separate advisory score beside the existing model.

This does NOT replace the projection formula.
This does NOT change staking.
This does NOT change thresholds.
This does NOT auto-bet.

It reads the V21 feature/backtest outputs and creates a manual-review score that can
be compared over time before any formula upgrade is approved.

Inputs:
  wnba_outputs/game_model_features_v21.csv
  wnba_outputs/team_features_v21.csv
  wnba_outputs/player_features_v21.csv
  wnba_outputs/market_features_v21.csv
  wnba_outputs/model_backtest_v21.csv
  wnba_outputs/validated_model_changes_v21.csv
  wnba_outputs/hermes_approval_queue_v20.csv
  wnba_outputs/recommended_bets.csv
  wnba_outputs/projections_with_stakes.csv

Outputs:
  wnba_outputs/model_advisory_scores_v21.csv
  wnba_outputs/model_advisory_summary_v21.json
  wnba_outputs/hermes_advisory_queue_v21.csv
  wnba_outputs/model_advisory_report_v21.txt

Safety:
  Advisory only.
  No formula/staking/threshold/betting changes.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "wnba_outputs"


TEAM_ALIASES = {
    "ATLANTA DREAM": "ATL",
    "ATL": "ATL",
    "CHICAGO SKY": "CHI",
    "CHI": "CHI",
    "CONNECTICUT SUN": "CON",
    "CONN SUN": "CON",
    "CON": "CON",
    "DALLAS WINGS": "DAL",
    "DAL": "DAL",
    "GOLDEN STATE VALKYRIES": "GSV",
    "GOLDEN STATE": "GSV",
    "GSV": "GSV",
    "INDIANA FEVER": "IND",
    "IND": "IND",
    "LAS VEGAS ACES": "LVA",
    "LVA": "LVA",
    "LOS ANGELES SPARKS": "LAS",
    "LA SPARKS": "LAS",
    "LAS": "LAS",
    "MINNESOTA LYNX": "MIN",
    "MIN": "MIN",
    "NEW YORK LIBERTY": "NYL",
    "NEW YORK": "NYL",
    "NYL": "NYL",
    "PHOENIX MERCURY": "PHO",
    "PHO": "PHO",
    "SEATTLE STORM": "SEA",
    "SEA": "SEA",
    "WASHINGTON MYSTICS": "WAS",
    "WAS": "WAS",
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


def norm_name(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", str(s).lower()).strip("_")


# ── Team normalization for schedule matching ─────────────────────

TEAM_NAME_TO_ABBR: Dict[str, str] = {
    # Full names → schedule abbreviation
    "LOS ANGELES SPARKS": "LA", "LA SPARKS": "LA",
    "LAS VEGAS ACES": "LV", "LV ACES": "LV",
    "GOLDEN STATE VALKYRIES": "GS", "GS VALKYRIES": "GS",
    "CONNECTICUT SUN": "CON", "CON SUN": "CON", "CONN SUN": "CON",
    "ATLANTA DREAM": "ATL",
    "CHICAGO SKY": "CHI",
    "DALLAS WINGS": "DAL",
    "INDIANA FEVER": "IND", "IND FEVER": "IND",
    "MINNESOTA LYNX": "MIN",
    "NEW YORK LIBERTY": "NY",
    "PHOENIX MERCURY": "PHX",
    "SEATTLE STORM": "SEA",
    "WASHINGTON MYSTICS": "WSH", "WAS MYSTICS": "WSH",
    "PORTLAND FIRE": "POR", "POR FIRE": "POR",
    "TORONTO": "TOR",
    # Already-abbreviated variants → schedule abbreviation
    "LAS": "LA", "LVA": "LV", "LVA": "LV",
    "GSV": "GS",
    "NYL": "NY",
    "WAS": "WSH",
    # Pass-through (already correct)
    "ATL": "ATL", "CHI": "CHI", "CON": "CON", "DAL": "DAL",
    "IND": "IND", "MIN": "MIN", "PHX": "PHX", "SEA": "SEA",
    "TOR": "TOR", "NY": "NY", "LA": "LA", "LV": "LV", "GS": "GS",
    "POR": "POR", "WSH": "WSH",
}


def normalize_team_token(token: str) -> str:
    """Normalize a team name/abbreviation token to schedule abbreviation."""
    if not token:
        return ""
    cleaned = token.strip().upper()
    # Exact match
    if cleaned in TEAM_NAME_TO_ABBR:
        return TEAM_NAME_TO_ABBR[cleaned]
    # Prefix match: try first 3 chars as abbreviation
    abbr3 = cleaned[:3]
    if abbr3 in TEAM_NAME_TO_ABBR:
        return TEAM_NAME_TO_ABBR[abbr3]
    # Substring match against known names
    for name, abbr in TEAM_NAME_TO_ABBR.items():
        if cleaned in name or name in cleaned:
            return abbr
    return cleaned[:3] if len(cleaned) >= 3 else cleaned


def normalize_game_to_abbr(game_text: str) -> Tuple[str, str]:
    """Parse queue game text into (away_abbr, home_abbr) for schedule lookup."""
    if not game_text:
        return "", ""
    text = str(game_text).strip()
    if text.upper() in ("NAN", "NONE", "NULL", ""):
        return "", ""
    # Split on @ or vs
    parts = re.split(r"\s*@\s*|\s+[Vv][Ss]\.?\s*", text, maxsplit=1)
    if len(parts) != 2:
        return "", ""
    away_raw, home_raw = parts[0].strip(), parts[1].strip()
    return normalize_team_token(away_raw), normalize_team_token(home_raw)


_SCHEDULE_INDEX: Optional[Dict[str, str]] = None


def _load_schedule_index() -> Dict[str, str]:
    """Load schedule into a (date + away_abbr + home_abbr) → game_date_time index.
    Uses raw line parsing to handle multiline boxscore fields.
    """
    global _SCHEDULE_INDEX
    if _SCHEDULE_INDEX is not None:
        return _SCHEDULE_INDEX

    index: Dict[str, str] = {}
    sched_path = OUT / "wnba_cache_v21" / "sdv_wnba_schedules.csv"
    if not sched_path.exists():
        _SCHEDULE_INDEX = index
        return index

    try:
        with sched_path.open(encoding="utf-8-sig") as f:
            header = f.readline().strip()
            cols = header.split(",")
            away_idx = cols.index("away_abbreviation")
            home_idx = cols.index("home_abbreviation")
            dt_idx = cols.index("game_date_time")
            gd_idx = cols.index("game_date")
            comp_idx = cols.index("status_type_completed")

            buffer = ""
            for line in f:
                buffer += line
                while True:
                    match = re.search(r"\n(\d{7,})", buffer)
                    if not match:
                        break
                    row_end = match.start()
                    row_data = buffer[:row_end]
                    buffer = buffer[row_end + 1 :]

                    parts = []
                    in_q = False
                    cur = ""
                    for ch in row_data:
                        if ch == '"':
                            in_q = not in_q
                        elif ch == "," and not in_q:
                            parts.append(cur)
                            cur = ""
                        else:
                            cur += ch
                    parts.append(cur)

                    if len(parts) > max(away_idx, home_idx, dt_idx, comp_idx):
                        away = parts[away_idx].strip()
                        home = parts[home_idx].strip()
                        gdt = parts[dt_idx].strip()
                        gdate = parts[gd_idx].strip()
                        completed = parts[comp_idx].strip().lower() in ("true", "1")
                        if away and home and gdate:
                            key = f"{gdate}|{away}|{home}"
                            index[key] = gdt if gdt else ""
                            index[f"{away}|{home}|{gdate}"] = gdt if gdt else ""
                            # Also index by completed status
                            if completed:
                                index[f"{gdate}|{away}|{home}|completed"] = "true"
    except Exception:
        pass

    _SCHEDULE_INDEX = index
    return index


def lookup_game_start_utc(game_text: str, row_date: str = "") -> str:
    """Look up game start time from schedule. Returns ISO UTC string or ''."""
    away_abbr, home_abbr = normalize_game_to_abbr(game_text)
    if not away_abbr or not home_abbr:
        return ""

    idx = _load_schedule_index()

    # Try with date first
    if row_date:
        key = f"{row_date}|{away_abbr}|{home_abbr}"
        if key in idx:
            return idx[key]

    # Try all keys matching away+home (most recent date)
    best = ""
    for key, val in idx.items():
        if key.startswith(f"{away_abbr}|{home_abbr}|") and val:
            if val > best:  # ISO strings compare correctly
                best = val

    return best


def _is_schedule_completed(game_text: str, row_date: str = "") -> bool:
    """Check if schedule says game is completed."""
    away_abbr, home_abbr = normalize_game_to_abbr(game_text)
    if not away_abbr or not home_abbr:
        return False

    idx = _load_schedule_index()
    if row_date:
        key = f"{row_date}|{away_abbr}|{home_abbr}|completed"
        return idx.get(key) == "true"

    for key, val in idx.items():
        if val == "true" and f"|{away_abbr}|{home_abbr}|" in key:
            return True
    return False


def compute_queue_freshness(row: Dict[str, str]) -> Dict[str, str]:
    """Compute freshness metadata for a queue row. Returns dict of 5 new fields."""
    reasons: List[str] = []
    game_start_utc = ""

    # Schedule lookup
    row_date = row.get("date", "")
    raw_game = row.get("game", "")
    away_abbr, home_abbr = normalize_game_to_abbr(raw_game)

    if not away_abbr or not home_abbr:
        reasons.append("invalid_game")
    else:
        game_start_utc = lookup_game_start_utc(raw_game, row_date)
        if not game_start_utc:
            # No schedule match — derive fallback from row date or created_at_utc.
            reasons.append("no_schedule_match")
            fallback_date = row_date.strip() if row_date else ""
            if not fallback_date:
                # Use the date portion of created_at_utc as fallback.
                created_raw = row.get("created_at_utc", "")
                if created_raw:
                    fallback_date = created_raw[:10]  # "YYYY-MM-DD"
            if fallback_date:
                today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                if fallback_date < today_utc:
                    reasons.append("past_date_fallback")
                    is_stale = True
                elif fallback_date == today_utc:
                    reasons.append("date_fallback_today")
                else:
                    reasons.append("date_fallback_future")
            # If no fallback_date at all → stays no_schedule_match only (un-actionable).
        elif _is_schedule_completed(raw_game, row_date):
            reasons.append("game_completed")

    # Age
    signal_age_hours = 0.0
    created = row.get("created_at_utc", "")
    if created:
        try:
            clean = created.replace("Z", "+00:00")
            dt = datetime.fromisoformat(clean).replace(tzinfo=timezone.utc)
            signal_age_hours = round(
                (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0, 1
            )
            if signal_age_hours > 48:
                reasons.append("age_gt_48h")
        except Exception:
            pass

    # Stale determination
    is_stale = False
    if signal_age_hours > 48:
        is_stale = True
    if game_start_utc:
        try:
            clean = game_start_utc.replace("Z", "+00:00")
            if datetime.now(timezone.utc) >= datetime.fromisoformat(clean):
                is_stale = True
                if "game_completed" not in reasons:
                    reasons.append("game_started")
        except Exception:
            pass
    if "game_completed" in reasons:
        is_stale = True

    # No line
    flags = str(row.get("risk_flags", "")).upper()
    line_val = str(row.get("line", "")).strip()
    if "NO_LINE" in flags:
        reasons.append("no_line")
    if not line_val or line_val.lower() in ("nan", "none"):
        reasons.append("no_line")

    # Label check
    label = str(row.get("advisory_label", "")).upper()
    if label not in ("LEAN_SUPPORT", "MANUAL_REVIEW"):
        reasons.append(f"non_actionable_label:{label[:20]}")

    # Actionability — strict: ACTIONABLE requires verified game_start_utc.
    # - invalid_game always hidden.
    # - no_schedule_match + past_date_fallback → HIDDEN_STALE (is_stale already true).
    # - no_schedule_match + date_fallback_today → SCHEDULE_UNVERIFIED_TODAY (not actionable).
    # - no_schedule_match + date_fallback_future → SCHEDULE_UNVERIFIED_FUTURE (not actionable).
    # - no_schedule_match + no date at all → HIDDEN_NO_SCHEDULE.
    # - game_start_utc present → allow other checks to pass through to ACTIONABLE.
    has_date_fallback = any(
        r in reasons for r in ("past_date_fallback", "date_fallback_today", "date_fallback_future")
    )
    if "invalid_game" in reasons:
        actionability = "HIDDEN_INVALID"
    elif "past_date_fallback" in reasons:
        actionability = "HIDDEN_STALE"
    elif "no_schedule_match" in reasons and not has_date_fallback:
        actionability = "HIDDEN_NO_SCHEDULE"
    elif "date_fallback_today" in reasons and not game_start_utc:
        actionability = "SCHEDULE_UNVERIFIED_TODAY"
    elif "date_fallback_future" in reasons and not game_start_utc:
        actionability = "SCHEDULE_UNVERIFIED_FUTURE"
    elif "no_line" in reasons:
        actionability = "HIDDEN_NO_LINE"
    elif is_stale:
        actionability = "HIDDEN_STALE"
    elif label not in ("LEAN_SUPPORT", "MANUAL_REVIEW"):
        actionability = "HIDDEN_LABEL"
    else:
        # Reached only when game_start_utc is verified AND all other gates pass.
        actionability = "ACTIONABLE"

    return {
        "game_start_utc": game_start_utc,
        "signal_age_hours": str(signal_age_hours),
        "is_stale": "true" if is_stale else "false",
        "freshness_reason": "; ".join(reasons) if reasons else "",
        "queue_actionability": actionability,
    }


def get_col(df: pd.DataFrame, aliases: List[str]) -> Optional[str]:
    if df.empty:
        return None
    cmap = {norm_name(c): c for c in df.columns}
    for a in aliases:
        n = norm_name(a)
        if n in cmap:
            return cmap[n]
    for a in aliases:
        toks = [t for t in norm_name(a).split("_") if t]
        for c in df.columns:
            nc = norm_name(c)
            if toks and all(t in nc for t in toks):
                return c
    return None


def num(x) -> float:
    try:
        v = pd.to_numeric(x, errors="coerce")
        if pd.isna(v):
            return np.nan
        return float(v)
    except Exception:
        return np.nan


def num_series(df: pd.DataFrame, col: Optional[str]) -> pd.Series:
    if not col or col not in df.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[col], errors="coerce")


def team_code(x: Any) -> str:
    if pd.isna(x):
        return ""
    s = str(x).strip().upper()
    s = re.sub(r"\s+", " ", s)
    return TEAM_ALIASES.get(s, s[:3] if len(s) >= 3 else s)


def extract_teams(text: Any) -> Tuple[str, str]:
    if pd.isna(text):
        return "", ""
    s = str(text).upper()
    m = re.search(r"\b([A-Z]{2,4})\s*@\s*([A-Z]{2,4})\b", s)
    if m:
        return team_code(m.group(1)), team_code(m.group(2))
    m = re.search(r"\b([A-Z]{2,4})\s+(?:VS\.?|V)\s+([A-Z]{2,4})\b", s)
    if m:
        return team_code(m.group(1)), team_code(m.group(2))
    return "", ""


def infer_side(row: pd.Series) -> str:
    for c in ["bet", "market", "side", "pick", "selection", "recommended_side"]:
        if c in row.index:
            s = str(row[c]).upper()
            if "OVER" in s:
                return "OVER"
            if "UNDER" in s:
                return "UNDER"
    return ""


def clip_score(value: float, low: float = -100.0, high: float = 100.0) -> float:
    if pd.isna(value):
        return 0.0
    return float(max(low, min(high, value)))


def score_to_label(score: float) -> str:
    if score >= 75:
        return "STRONG_SUPPORT"
    if score >= 50:
        return "SUPPORT"
    if score >= 25:
        return "LEAN_SUPPORT"
    if score <= -75:
        return "STRONG_CONFLICT"
    if score <= -50:
        return "CONFLICT"
    if score <= -25:
        return "LEAN_CONFLICT"
    return "NEUTRAL"


def build_base_actions(recommended: pd.DataFrame, projections: pd.DataFrame, hermes_queue: pd.DataFrame, game_features: pd.DataFrame) -> pd.DataFrame:
    frames = []

    for source_name, df in [
        ("hermes_approval_queue_v20", hermes_queue),
        ("recommended_bets", recommended),
        ("projections_with_stakes", projections),
        ("game_model_features_v21", game_features),
    ]:
        if df.empty:
            continue
        out = df.copy()
        out["_source"] = source_name
        frames.append(out)

    if not frames:
        return pd.DataFrame()

    base = pd.concat(frames, ignore_index=True, sort=False)

    game_col = get_col(base, ["game", "matchup", "event", "GAME", "Matchup"])
    line_col = get_col(base, ["line", "total", "market_total", "bet_line", "signal_line", "Line"])
    proj_col = get_col(base, ["projection", "projected_total", "model_total", "Projection"])
    edge_col = get_col(base, ["edge", "projection_minus_line", "model_edge", "Edge"])
    units_col = get_col(base, ["units", "suggested_units", "stake", "Stake"])

    rows = []
    seen = set()

    for _, r in base.iterrows():
        game_text = str(r.get(game_col, "")) if game_col else ""
        away, home = extract_teams(game_text)
        side = infer_side(r)

        # Keep only useful rows. Some projection rows may have no side; still keep for diagnostics if game exists.
        key = (game_text, side, str(r.get(line_col, "")) if line_col else "")
        if key in seen:
            continue
        seen.add(key)

        row = {
            "created_at_utc": now_iso(),
            "source": r.get("_source", ""),
            "game": game_text,
            "away_team": away,
            "home_team": home,
            "side": side,
            "line": num(r.get(line_col)) if line_col else np.nan,
            "projection": num(r.get(proj_col)) if proj_col else np.nan,
            "edge": num(r.get(edge_col)) if edge_col else np.nan,
            "units": num(r.get(units_col)) if units_col else np.nan,
        }

        if pd.isna(row["edge"]) and pd.notna(row["projection"]) and pd.notna(row["line"]):
            row["edge"] = row["projection"] - row["line"]

        if not row["side"] and pd.notna(row["edge"]):
            row["side"] = "OVER" if row["edge"] > 0 else "UNDER"

        rows.append(row)

    return pd.DataFrame(rows)


def team_lookup(team_features: pd.DataFrame) -> pd.DataFrame:
    if team_features.empty or "team" not in team_features.columns:
        return pd.DataFrame()
    tf = team_features.copy()
    tf["_team"] = tf["team"].apply(team_code)
    return tf.drop_duplicates("_team", keep="last").set_index("_team", drop=False)


def build_market_lookup(market_features: pd.DataFrame) -> pd.DataFrame:
    if market_features.empty:
        return pd.DataFrame()
    mf = market_features.copy()
    hc = get_col(mf, ["home_team"])
    ac = get_col(mf, ["away_team"])
    if hc:
        mf["_home"] = mf[hc].apply(team_code)
    else:
        mf["_home"] = ""
    if ac:
        mf["_away"] = mf[ac].apply(team_code)
    else:
        mf["_away"] = ""
    return mf


def feature_value(team_row: Optional[pd.Series], aliases: List[str]) -> float:
    if team_row is None:
        return np.nan
    for a in aliases:
        for c in team_row.index:
            if norm_name(c) == norm_name(a):
                return num(team_row[c])
    # fuzzy
    toks_all = [[t for t in norm_name(a).split("_") if t] for a in aliases]
    for toks in toks_all:
        for c in team_row.index:
            nc = norm_name(c)
            if toks and all(t in nc for t in toks):
                return num(team_row[c])
    return np.nan


def side_multiplier(side: str) -> int:
    side = str(side).upper()
    if side == "OVER":
        return 1
    if side == "UNDER":
        return -1
    return 0


def advisory_score_row(row: pd.Series, team_idx: pd.DataFrame, market_features: pd.DataFrame, player_features: pd.DataFrame) -> Dict[str, Any]:
    away = team_code(row.get("away_team", ""))
    home = team_code(row.get("home_team", ""))
    side = str(row.get("side", "")).upper()
    sm = side_multiplier(side)

    home_row = team_idx.loc[home] if home and not team_idx.empty and home in team_idx.index else None
    away_row = team_idx.loc[away] if away and not team_idx.empty and away in team_idx.index else None

    components = {}

    # Current model edge support.
    edge = num(row.get("edge"))
    if pd.notna(edge):
        components["model_edge_score"] = clip_score(edge * 10 * sm)
    else:
        components["model_edge_score"] = 0.0

    # Team recent scoring environment.
    h_recent = feature_value(home_row, ["playerlog_team_pts_l5", "team_pts_for_l5"])
    a_recent = feature_value(away_row, ["playerlog_team_pts_l5", "team_pts_for_l5"])
    line = num(row.get("line"))
    if pd.notna(h_recent) and pd.notna(a_recent) and pd.notna(line):
        recent_vs_line = (h_recent + a_recent) - line
        components["recent_scoring_score"] = clip_score(recent_vs_line * 3 * sm)
    else:
        components["recent_scoring_score"] = 0.0

    # Dashboard scoring environment.
    h_dash = feature_value(home_row, ["dash_pts"])
    a_dash = feature_value(away_row, ["dash_pts"])
    if pd.notna(h_dash) and pd.notna(a_dash) and pd.notna(line):
        dash_vs_line = (h_dash + a_dash) - line
        components["dashboard_scoring_score"] = clip_score(dash_vs_line * 2 * sm)
    else:
        components["dashboard_scoring_score"] = 0.0

    # Rotation concentration: supports confidence only mildly; high concentration increases fragility/news sensitivity.
    h_conc = feature_value(home_row, ["starter_minutes_concentration"])
    a_conc = feature_value(away_row, ["starter_minutes_concentration"])
    conc_vals = [v for v in [h_conc, a_conc] if pd.notna(v)]
    if conc_vals:
        avg_conc = float(np.mean(conc_vals))
        # above .72 = high concentration. It can support sharper reads but increases player-news risk.
        components["rotation_concentration_score"] = clip_score((avg_conc - 0.70) * 100)
        components["rotation_risk_penalty"] = -abs(clip_score((avg_conc - 0.78) * 100)) if avg_conc > 0.78 else 0.0
    else:
        components["rotation_concentration_score"] = 0.0
        components["rotation_risk_penalty"] = 0.0

    # Bench share: lower bench share = more starter dependent = higher fragility.
    h_bench = feature_value(home_row, ["bench_minutes_share"])
    a_bench = feature_value(away_row, ["bench_minutes_share"])
    bench_vals = [v for v in [h_bench, a_bench] if pd.notna(v)]
    if bench_vals:
        avg_bench = float(np.mean(bench_vals))
        components["bench_depth_score"] = clip_score((avg_bench - 0.28) * 100)
    else:
        components["bench_depth_score"] = 0.0

    # DREB context mostly for props/rebound environment. Keep small for totals advisory.
    h_dreb_allowed = feature_value(home_row, ["dreb_allowed_blended_dreb_allowed", "blended_dreb_allowed"])
    a_dreb_allowed = feature_value(away_row, ["dreb_allowed_blended_dreb_allowed", "blended_dreb_allowed"])
    dreb_vals = [v for v in [h_dreb_allowed, a_dreb_allowed] if pd.notna(v)]
    if dreb_vals:
        avg_dreb = float(np.mean(dreb_vals))
        components["dreb_environment_score"] = clip_score((avg_dreb - 24.0) * 3 * sm)
    else:
        components["dreb_environment_score"] = 0.0

    # Market range confidence gate. Wide range lowers confidence.
    market_range = np.nan
    if not market_features.empty:
        mf = market_features.copy()
        if "_home" not in mf.columns or "_away" not in mf.columns:
            mf = build_market_lookup(mf)
        if not mf.empty:
            match = mf[(mf.get("_home", "") == home) & (mf.get("_away", "") == away)]
            if match.empty:
                match = mf[(mf.get("_home", "") == away) & (mf.get("_away", "") == home)]
            if not match.empty:
                rc = get_col(match, ["market_total_range"])
                if rc:
                    market_range = num(match.iloc[0].get(rc))

    if pd.notna(market_range):
        components["market_range_penalty"] = -clip_score(max(0.0, market_range - 1.0) * 20, 0, 35)
        components["market_range"] = market_range
    else:
        components["market_range_penalty"] = 0.0
        components["market_range"] = np.nan

    # Weighted advisory score.
    weights = {
        "model_edge_score": 0.30,
        "recent_scoring_score": 0.18,
        "dashboard_scoring_score": 0.15,
        "rotation_concentration_score": 0.07,
        "rotation_risk_penalty": 0.10,
        "bench_depth_score": 0.05,
        "dreb_environment_score": 0.05,
        "market_range_penalty": 0.10,
    }
    advisory = sum(components[k] * weights[k] for k in weights)
    advisory = clip_score(advisory)

    # Agreement with current side.
    label = score_to_label(advisory)

    # Risk flags.
    flags = []
    if pd.isna(row.get("line")):
        flags.append("NO_LINE")
    if not side:
        flags.append("NO_SIDE")
    if pd.notna(market_range) and market_range >= 1.5:
        flags.append("WIDE_MARKET_RANGE")
    if components.get("rotation_risk_penalty", 0) < -5:
        flags.append("HIGH_ROTATION_FRAGILITY")
    if abs(components.get("model_edge_score", 0)) < 10:
        flags.append("LOW_MODEL_EDGE")

    return {
        **components,
        "advisory_score": advisory,
        "advisory_label": label,
        "risk_flags": ", ".join(flags),
    }


def build_advisory_scores(actions: pd.DataFrame, team_features: pd.DataFrame, market_features: pd.DataFrame, player_features: pd.DataFrame) -> pd.DataFrame:
    if actions.empty:
        return pd.DataFrame()

    team_idx = team_lookup(team_features)
    rows = []

    for _, r in actions.iterrows():
        base = r.to_dict()
        scores = advisory_score_row(r, team_idx, market_features, player_features)
        rows.append({**base, **scores})

    out = pd.DataFrame(rows)

    # Rank actionable rows first.
    if not out.empty:
        out["manual_review_priority"] = out["advisory_score"].abs().rank(ascending=False, method="dense")
        out = out.sort_values(["manual_review_priority", "game"], ascending=[True, True]).reset_index(drop=True)

    return out


def build_hermes_queue(scores: pd.DataFrame) -> pd.DataFrame:
    if scores.empty:
        return pd.DataFrame(columns=[
            "created_at_utc", "date",
            "game", "side", "line",
            "projection", "edge", "units",
            "advisory_score", "advisory_label", "risk_flags",
            "manual_review_priority",
            "game_start_utc", "signal_age_hours",
            "is_stale", "freshness_reason", "queue_actionability",
            "approval_state", "message",
        ])

    q = scores.copy()
    # Merge in date from original source if available
    q["date"] = q["date"] if "date" in q.columns else ""
    q["approval_state"] = "ADVISORY_ONLY_MANUAL_REVIEW"
    q["message"] = q.apply(
        lambda r: (
            f"{r.get('game','')} {r.get('side','')} advisory={r.get('advisory_score',0):.1f} "
            f"label={r.get('advisory_label','')} flags={r.get('risk_flags','')}"
        ),
        axis=1,
    )

    # Compute freshness for each row
    fresh_rows = []
    for _, row in q.iterrows():
        row_dict = row.to_dict()
        fresh = compute_queue_freshness(row_dict)
        row_dict.update(fresh)
        fresh_rows.append(row_dict)

    result = pd.DataFrame(fresh_rows)

    keep = [
        "created_at_utc", "date",
        "game", "side", "line",
        "projection", "edge", "units",
        "advisory_score", "advisory_label", "risk_flags",
        "manual_review_priority",
        "game_start_utc", "signal_age_hours",
        "is_stale", "freshness_reason", "queue_actionability",
        "approval_state", "message",
    ]
    return result[[c for c in keep if c in result.columns]]


def write_report(scores: pd.DataFrame, summary: Dict[str, Any]) -> None:
    lines = []
    lines.append("WNBA EDGE LAB - V21 ADVISORY SCORING REPORT")
    lines.append("=" * 58)
    lines.append(f"Created: {summary['created_at_utc']}")
    lines.append("")
    lines.append("Status: advisory only. No live model formula changed.")
    lines.append("")
    lines.append(f"Rows scored: {summary['rows']['advisory_scores']}")
    lines.append(f"Hermes advisory queue: {summary['rows']['hermes_advisory_queue']}")
    lines.append("")
    lines.append("Label counts:")
    for k, v in summary.get("label_counts", {}).items():
        lines.append(f"- {k}: {v}")
    lines.append("")
    lines.append("Top advisory rows:")
    if scores.empty:
        lines.append("- No advisory rows generated.")
    else:
        for _, r in scores.head(10).iterrows():
            lines.append(
                f"- {r.get('game','')} | {r.get('side','')} | line={r.get('line','')} | "
                f"score={r.get('advisory_score',0):.1f} | {r.get('advisory_label','')} | flags={r.get('risk_flags','')}"
            )
    lines.append("")
    lines.append("Next validation:")
    lines.append("- Compare advisory_score buckets against actual results and CLV.")
    lines.append("- Keep MANUAL_APPROVAL_REQUIRED and MODEL_SAMPLE_LOCK active.")
    lines.append("- Do not use advisory score to change staking yet.")
    (OUT / "model_advisory_report_v21.txt").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    game_features = read_csv(OUT / "game_model_features_v21.csv")
    team_features = read_csv(OUT / "team_features_v21.csv")
    player_features = read_csv(OUT / "player_features_v21.csv")
    market_features = read_csv(OUT / "market_features_v21.csv")
    model_backtest = read_csv(OUT / "model_backtest_v21.csv")
    validated = read_csv(OUT / "validated_model_changes_v21.csv")
    hermes_queue = read_csv(OUT / "hermes_approval_queue_v20.csv")
    recommended = read_csv(OUT / "recommended_bets.csv")
    projections = read_csv(OUT / "projections_with_stakes.csv")

    actions = build_base_actions(recommended, projections, hermes_queue, game_features)
    scores = build_advisory_scores(actions, team_features, market_features, player_features)
    queue = build_hermes_queue(scores)

    save_csv(OUT / "model_advisory_scores_v21.csv", scores)
    save_csv(OUT / "hermes_advisory_queue_v21.csv", queue)

    label_counts = scores["advisory_label"].value_counts().to_dict() if not scores.empty and "advisory_label" in scores.columns else {}
    flag_counts: Dict[str, int] = {}
    if not scores.empty and "risk_flags" in scores.columns:
        for flags in scores["risk_flags"].fillna("").astype(str):
            for f in [x.strip() for x in flags.split(",") if x.strip()]:
                flag_counts[f] = flag_counts.get(f, 0) + 1

    summary = {
        "created_at_utc": now_iso(),
        "status": "OK",
        "version": "v21",
        "rows": {
            "base_actions": int(len(actions)),
            "advisory_scores": int(len(scores)),
            "hermes_advisory_queue": int(len(queue)),
            "team_features": int(len(team_features)),
            "player_features": int(len(player_features)),
            "market_features": int(len(market_features)),
            "model_backtest": int(len(model_backtest)),
            "validated_model_changes": int(len(validated)),
        },
        "label_counts": label_counts,
        "risk_flag_counts": flag_counts,
        "safety": {
            "formula_changed": False,
            "staking_changed": False,
            "thresholds_changed": False,
            "auto_betting": False,
            "advisory_only": True,
        },
    }
    save_json(OUT / "model_advisory_summary_v21.json", summary)
    write_report(scores, summary)

    safe_print("OK: V21 Model Advisory Scoring complete")
    safe_print(f"Actions: {len(actions)}")
    safe_print(f"Advisory scores: {len(scores)}")
    safe_print(f"Hermes advisory queue: {len(queue)}")
    safe_print(f"Labels: {label_counts}")
    safe_print(f"Risk flags: {flag_counts}")
    safe_print(f"Scores CSV: {OUT / 'model_advisory_scores_v21.csv'}")
    safe_print(f"Summary:    {OUT / 'model_advisory_summary_v21.json'}")
    safe_print("Note: advisory only; no formula/staking/threshold changes applied")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
