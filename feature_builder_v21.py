#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WNBA Edge Lab - Feature Builder V21

Purpose
-------
Build model-ready features from the stable V21 data stack:

Primary official layer:
  wnba_outputs/official_mobile_playergamelogs_v21.csv
  wnba_outputs/official_mobile_teamgamelogs_v21.csv
  wnba_outputs/official_mobile_team_dash_base_v21.csv
  wnba_outputs/official_mobile_player_dash_base_v21.csv
  wnba_outputs/official_mobile_dreb_allowed_rankings_v21.csv

Historical/backfill layer:
  wnba_cache_v21/sdv_wnba_team_boxscores.csv
  wnba_cache_v21/sdv_wnba_player_boxscores.csv
  wnba_cache_v21/sdv_wnba_pbp.csv
  wnba_cache_v21/sdv_wnba_schedules.csv

Market/model context:
  wnba_outputs/odds_totals_latest_v21.csv
  wnba_outputs/projections_with_stakes.csv
  wnba_outputs/recommended_bets.csv

Outputs
-------
wnba_outputs/team_features_v21.csv
wnba_outputs/player_features_v21.csv
wnba_outputs/market_features_v21.csv
wnba_outputs/game_model_features_v21.csv
wnba_outputs/feature_builder_summary_v21.json
wnba_outputs/hermes_feature_warnings_v21.csv

Safety
------
Advisory feature generation only.
No projection formula changes.
No staking changes.
No thresholds changed.
No betting.
No Telegram.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import numpy as np


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "wnba_outputs"
CACHE = ROOT / "wnba_cache_v21"


TEAM_ALIASES = {
    "ATLANTA DREAM": "ATL",
    "ATL DREAM": "ATL",
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


def save_df(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def save_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def norm_col_map(df: pd.DataFrame) -> Dict[str, str]:
    return {str(c).lower(): c for c in df.columns}


def get_col(df: pd.DataFrame, candidates: List[str]) -> Optional[str]:
    cmap = norm_col_map(df)
    for c in candidates:
        if c.lower() in cmap:
            return cmap[c.lower()]
    return None


def to_num(s) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def team_code(value) -> str:
    if pd.isna(value):
        return ""
    s = str(value).strip().upper()
    s = re.sub(r"\s+", " ", s)
    return TEAM_ALIASES.get(s, s[:3] if len(s) >= 3 else s)


def parse_matchup_opp(matchup: str) -> str:
    if pd.isna(matchup):
        return ""
    s = str(matchup).upper().strip()
    m = re.search(r"(?:VS\.?|@)\s*([A-Z]{2,4})$", s)
    return m.group(1) if m else ""


def prepare_player_logs(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()

    date_col = get_col(out, ["GAME_DATE", "game_date"])
    team_col = get_col(out, ["TEAM_ABBREVIATION", "team_abbreviation", "team_abbrev", "team"])
    matchup_col = get_col(out, ["MATCHUP", "matchup"])
    player_col = get_col(out, ["PLAYER_NAME", "player_name", "athlete_display_name", "display_name"])
    game_col = get_col(out, ["GAME_ID", "game_id"])

    if date_col:
        out["_game_date"] = pd.to_datetime(out[date_col], errors="coerce")
    else:
        out["_game_date"] = pd.NaT

    if team_col:
        out["_team"] = out[team_col].apply(team_code)
    else:
        out["_team"] = ""

    if matchup_col:
        out["_opp"] = out[matchup_col].apply(parse_matchup_opp)
    else:
        out["_opp"] = ""

    if player_col:
        out["_player"] = out[player_col].astype(str)
    else:
        out["_player"] = ""

    if game_col:
        out["_game_id"] = out[game_col].astype(str)
    else:
        out["_game_id"] = ""

    for c in ["MIN", "minutes", "PTS", "points", "REB", "rebounds", "DREB", "OREB", "AST", "FG3M", "TOV", "FGA", "FTA"]:
        if c in out.columns:
            out[c] = to_num(out[c])

    return out


def prepare_team_logs(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    date_col = get_col(out, ["GAME_DATE", "game_date"])
    team_col = get_col(out, ["TEAM_ABBREVIATION", "team_abbreviation", "team_abbrev", "team"])
    matchup_col = get_col(out, ["MATCHUP", "matchup"])
    game_col = get_col(out, ["GAME_ID", "game_id"])

    out["_game_date"] = pd.to_datetime(out[date_col], errors="coerce") if date_col else pd.NaT
    out["_team"] = out[team_col].apply(team_code) if team_col else ""
    out["_opp"] = out[matchup_col].apply(parse_matchup_opp) if matchup_col else ""
    out["_game_id"] = out[game_col].astype(str) if game_col else ""

    for c in out.columns:
        if str(c).upper() in {"PTS", "REB", "DREB", "OREB", "AST", "TOV", "FGA", "FGM", "FG3A", "FG3M", "FTA", "FTM", "PLUS_MINUS"}:
            out[c] = to_num(out[c])
    return out


def build_team_features(player_logs: pd.DataFrame, team_logs: pd.DataFrame, team_dash: pd.DataFrame, dreb_rank: pd.DataFrame, sdv_team: pd.DataFrame, sdv_pbp: pd.DataFrame) -> pd.DataFrame:
    rows = []

    # Core recent form from official team logs when possible.
    team_logs = prepare_team_logs(team_logs)
    player_logs = prepare_player_logs(player_logs)

    teams = set()
    if not team_logs.empty and "_team" in team_logs.columns:
        teams.update([x for x in team_logs["_team"].dropna().unique() if x])
    if not player_logs.empty and "_team" in player_logs.columns:
        teams.update([x for x in player_logs["_team"].dropna().unique() if x])
    if not team_dash.empty:
        tc = get_col(team_dash, ["TEAM_ABBREVIATION", "team_abbreviation", "TEAM_NAME", "team_name"])
        if tc:
            teams.update([team_code(x) for x in team_dash[tc].dropna().unique()])
    if not dreb_rank.empty and "Team" in dreb_rank.columns:
        teams.update([team_code(x) for x in dreb_rank["Team"].dropna().unique()])

    for team in sorted(teams):
        row = {
            "team": team,
            "created_at_utc": now_iso(),
            "source_priority": "official_mobile_first",
        }

        tg = team_logs[team_logs["_team"] == team].copy() if not team_logs.empty else pd.DataFrame()
        if not tg.empty:
            tg = tg.sort_values("_game_date")
            pts_col = get_col(tg, ["PTS", "points"])
            plus_col = get_col(tg, ["PLUS_MINUS", "plus_minus"])
            dreb_col = get_col(tg, ["DREB", "dreb"])
            ast_col = get_col(tg, ["AST", "ast"])
            tov_col = get_col(tg, ["TOV", "tov"])

            if pts_col:
                pts = to_num(tg[pts_col])
                row["team_games_official"] = int(pts.notna().sum())
                for n in [3, 5, 10]:
                    row[f"team_pts_for_l{n}"] = float(pts.tail(n).mean()) if len(pts.dropna()) else np.nan
            if plus_col:
                pm = to_num(tg[plus_col])
                for n in [3, 5, 10]:
                    row[f"team_margin_l{n}"] = float(pm.tail(n).mean()) if len(pm.dropna()) else np.nan
            if dreb_col:
                row["team_dreb_pg_official"] = float(to_num(tg[dreb_col]).mean())
            if ast_col:
                row["team_ast_pg_official"] = float(to_num(tg[ast_col]).mean())
            if tov_col:
                row["team_tov_pg_official"] = float(to_num(tg[tov_col]).mean())
        else:
            row["team_games_official"] = 0

        # Player-derived team totals, useful because playergamelogs worked live.
        pg = player_logs[player_logs["_team"] == team].copy() if not player_logs.empty else pd.DataFrame()
        if not pg.empty:
            pts_col = get_col(pg, ["PTS", "points"])
            min_col = get_col(pg, ["MIN", "minutes"])
            fga_col = get_col(pg, ["FGA", "field_goals_attempted"])
            fta_col = get_col(pg, ["FTA", "free_throws_attempted"])
            fg3m_col = get_col(pg, ["FG3M", "three_point_field_goals_made"])
            ast_col = get_col(pg, ["AST", "assists"])
            reb_col = get_col(pg, ["REB", "rebounds"])

            if pts_col:
                game_pts = pg.groupby("_game_id")[pts_col].sum(min_count=1)
                row["playerlog_team_pts_l3"] = float(game_pts.tail(3).mean())
                row["playerlog_team_pts_l5"] = float(game_pts.tail(5).mean())
                row["playerlog_team_pts_l10"] = float(game_pts.tail(10).mean())
                row["playerlog_team_games"] = int(game_pts.shape[0])

            if min_col:
                gm = pg.groupby("_game_id")[min_col].apply(lambda x: to_num(x).sum())
                row["playerlog_total_minutes_pg"] = float(gm.mean()) if len(gm) else np.nan

                # minutes concentration: share of minutes held by top 5 player-game minutes within game.
                conc = []
                bench_share = []
                for _, g in pg.groupby("_game_id"):
                    mins = to_num(g[min_col]).dropna().sort_values(ascending=False)
                    total = mins.sum()
                    if total > 0:
                        conc.append(mins.head(5).sum() / total)
                        bench_share.append(mins.iloc[5:].sum() / total if len(mins) > 5 else 0.0)
                row["starter_minutes_concentration"] = float(np.mean(conc)) if conc else np.nan
                row["bench_minutes_share"] = float(np.mean(bench_share)) if bench_share else np.nan

            if fga_col:
                fga = pg.groupby("_game_id")[fga_col].sum(min_count=1)
                row["team_fga_pg_playerlog"] = float(fga.mean())
            if fta_col:
                fta = pg.groupby("_game_id")[fta_col].sum(min_count=1)
                row["team_fta_pg_playerlog"] = float(fta.mean())
            if fg3m_col:
                threes = pg.groupby("_game_id")[fg3m_col].sum(min_count=1)
                row["team_3pm_pg_playerlog"] = float(threes.mean())
            if ast_col:
                ast = pg.groupby("_game_id")[ast_col].sum(min_count=1)
                row["team_ast_pg_playerlog"] = float(ast.mean())
            if reb_col:
                reb = pg.groupby("_game_id")[reb_col].sum(min_count=1)
                row["team_reb_pg_playerlog"] = float(reb.mean())

        # Official team dash stats.
        if not team_dash.empty:
            td = team_dash.copy()
            tc = get_col(td, ["TEAM_ABBREVIATION", "TEAM_NAME", "team_abbreviation", "team_name"])
            if tc:
                td["_team"] = td[tc].apply(team_code)
                tr = td[td["_team"] == team]
                if not tr.empty:
                    tr = tr.tail(1)
                    for src, dst in [
                        ("GP", "dash_gp"),
                        ("W", "dash_wins"),
                        ("L", "dash_losses"),
                        ("W_PCT", "dash_win_pct"),
                        ("PTS", "dash_pts"),
                        ("PLUS_MINUS", "dash_plus_minus"),
                        ("OFF_RATING", "dash_off_rating"),
                        ("DEF_RATING", "dash_def_rating"),
                        ("NET_RATING", "dash_net_rating"),
                        ("PACE", "dash_pace"),
                    ]:
                        c = get_col(tr, [src])
                        if c:
                            row[dst] = float(pd.to_numeric(tr[c], errors="coerce").iloc[0]) if pd.notna(pd.to_numeric(tr[c], errors="coerce").iloc[0]) else np.nan

        # DREB allowed rankings.
        if not dreb_rank.empty and "Team" in dreb_rank.columns:
            dr = dreb_rank.copy()
            dr["_team"] = dr["Team"].apply(team_code)
            one = dr[dr["_team"] == team]
            if not one.empty:
                one = one.iloc[0]
                for c in ["Rank", "Blended_DREB_Allowed", "DREB_Allowed_2025", "DREB_Allowed_2026"]:
                    if c in one.index:
                        row[f"dreb_allowed_{c.lower()}"] = one[c]
                if "Signal" in one.index:
                    row["dreb_allowed_signal"] = one["Signal"]

        rows.append(row)

    out = pd.DataFrame(rows)
    return out


def build_player_features(player_logs: pd.DataFrame, player_dash: pd.DataFrame) -> pd.DataFrame:
    player_logs = prepare_player_logs(player_logs)
    rows = []

    if not player_logs.empty and "_player" in player_logs.columns:
        for (team, player), g in player_logs.groupby(["_team", "_player"], dropna=False):
            if not player:
                continue
            g = g.sort_values("_game_date")
            row = {"team": team, "player": player, "created_at_utc": now_iso()}
            row["games"] = int(g["_game_id"].nunique()) if "_game_id" in g.columns else int(len(g))

            for raw, name in [
                ("MIN", "minutes"),
                ("PTS", "points"),
                ("REB", "rebounds"),
                ("DREB", "dreb"),
                ("AST", "assists"),
                ("FG3M", "threes"),
                ("TOV", "turnovers"),
                ("FGA", "fga"),
                ("FTA", "fta"),
            ]:
                c = get_col(g, [raw, name])
                if c:
                    vals = to_num(g[c])
                    row[f"{name}_avg"] = float(vals.mean()) if vals.notna().any() else np.nan
                    row[f"{name}_l3"] = float(vals.tail(3).mean()) if vals.notna().any() else np.nan
                    row[f"{name}_l5"] = float(vals.tail(5).mean()) if vals.notna().any() else np.nan

            pts_col = get_col(g, ["PTS", "points"])
            if pts_col:
                team_game_pts = player_logs[player_logs["_team"] == team].groupby("_game_id")[pts_col].sum(min_count=1)
                player_pts = g.groupby("_game_id")[pts_col].sum(min_count=1)
                shares = []
                for gid, val in player_pts.items():
                    total = team_game_pts.get(gid, np.nan)
                    if pd.notna(total) and total > 0:
                        shares.append(val / total)
                row["scoring_dependency"] = float(np.mean(shares)) if shares else np.nan

            rows.append(row)

    out = pd.DataFrame(rows)

    # Add dash stats if available.
    if not out.empty and not player_dash.empty:
        pdash = player_dash.copy()
        pc = get_col(pdash, ["PLAYER_NAME", "player_name"])
        tc = get_col(pdash, ["TEAM_ABBREVIATION", "TEAM_NAME", "team_abbreviation", "team_name"])
        if pc:
            pdash["_player"] = pdash[pc].astype(str)
            pdash["_team"] = pdash[tc].apply(team_code) if tc else ""
            keep = ["_team", "_player"]
            for src in ["GP", "W", "L", "W_PCT", "MIN", "PTS", "REB", "AST", "PLUS_MINUS"]:
                c = get_col(pdash, [src])
                if c:
                    pdash[f"dash_{src.lower()}"] = pd.to_numeric(pdash[c], errors="coerce")
                    keep.append(f"dash_{src.lower()}")
            slim = pdash[keep].drop_duplicates(["_team", "_player"], keep="last")
            out = out.merge(slim, left_on=["team", "player"], right_on=["_team", "_player"], how="left")
            out = out.drop(columns=[c for c in ["_team", "_player"] if c in out.columns])

    return out


def build_market_features(odds: pd.DataFrame) -> pd.DataFrame:
    if odds.empty:
        return pd.DataFrame()

    df = odds.copy()
    market_col = get_col(df, ["market"])
    point_col = get_col(df, ["point"])
    price_col = get_col(df, ["price"])
    home_col = get_col(df, ["home_team"])
    away_col = get_col(df, ["away_team"])
    event_col = get_col(df, ["event_id"])
    book_col = get_col(df, ["bookmaker", "bookmaker_key"])

    if not market_col or not point_col:
        return pd.DataFrame()

    totals = df[df[market_col].astype(str).str.lower() == "totals"].copy()
    if totals.empty:
        return pd.DataFrame()

    totals["_point"] = pd.to_numeric(totals[point_col], errors="coerce")
    totals["_price"] = pd.to_numeric(totals[price_col], errors="coerce") if price_col else np.nan
    rows = []

    group_cols = [event_col] if event_col else []
    if home_col:
        group_cols.append(home_col)
    if away_col:
        group_cols.append(away_col)
    if not group_cols:
        group_cols = [market_col]

    for keys, g in totals.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        row = {}
        for c, k in zip(group_cols, keys):
            row[c] = k
        row["market_total_mean"] = float(g["_point"].mean())
        row["market_total_median"] = float(g["_point"].median())
        row["market_total_min"] = float(g["_point"].min())
        row["market_total_max"] = float(g["_point"].max())
        row["market_total_range"] = float(g["_point"].max() - g["_point"].min())
        row["market_total_books"] = int(g[book_col].nunique()) if book_col else int(len(g))
        row["market_total_rows"] = int(len(g))
        rows.append(row)

    return pd.DataFrame(rows)


def extract_teams_from_game_text(text: str) -> Tuple[str, str]:
    if pd.isna(text):
        return "", ""
    s = str(text).upper()
    # Try "LAS @ WAS"
    m = re.search(r"\b([A-Z]{2,4})\s*@\s*([A-Z]{2,4})\b", s)
    if m:
        return m.group(1), m.group(2)
    # Try "LAS VS WAS"
    m = re.search(r"\b([A-Z]{2,4})\s+(?:VS\.?|V)\s+([A-Z]{2,4})\b", s)
    if m:
        return m.group(1), m.group(2)
    return "", ""


def build_game_model_features(team_features: pd.DataFrame, market_features: pd.DataFrame, projections: pd.DataFrame, recs: pd.DataFrame) -> pd.DataFrame:
    # Start from projections if available, else recommended bets.
    base = projections.copy() if not projections.empty else recs.copy()
    if base.empty:
        return pd.DataFrame()

    game_col = get_col(base, ["game", "matchup", "GAME", "Matchup"])
    proj_col = get_col(base, ["projection", "projected_total", "model_total", "Projection"])
    line_col = get_col(base, ["line", "total", "market_total", "Line"])
    edge_col = get_col(base, ["edge", "Edge"])
    conf_col = get_col(base, ["confidence", "Confidence"])

    rows = []
    tf = team_features.copy()
    if not tf.empty and "team" in tf.columns:
        tf = tf.set_index("team", drop=False)

    for _, r in base.iterrows():
        game_txt = str(r[game_col]) if game_col else ""
        away, home = extract_teams_from_game_text(game_txt)
        row = {"game": game_txt, "away_team": away, "home_team": home, "created_at_utc": now_iso()}

        if proj_col:
            row["projection"] = pd.to_numeric(r.get(proj_col), errors="coerce")
        if line_col:
            row["line"] = pd.to_numeric(r.get(line_col), errors="coerce")
        if edge_col:
            row["edge"] = pd.to_numeric(r.get(edge_col), errors="coerce")
        if conf_col:
            row["confidence"] = pd.to_numeric(r.get(conf_col), errors="coerce")

        for side, team in [("away", away), ("home", home)]:
            if team and not tf.empty and team in tf.index:
                tr = tf.loc[team]
                if isinstance(tr, pd.DataFrame):
                    tr = tr.iloc[0]
                for col in [
                    "team_pts_for_l3",
                    "team_pts_for_l5",
                    "team_pts_for_l10",
                    "team_margin_l5",
                    "playerlog_team_pts_l5",
                    "starter_minutes_concentration",
                    "bench_minutes_share",
                    "dash_pts",
                    "dash_plus_minus",
                    "dash_pace",
                    "dreb_allowed_blended_dreb_allowed",
                    "dreb_allowed_rank",
                ]:
                    if col in tr.index:
                        row[f"{side}_{col}"] = tr[col]

        # Combined features.
        if "home_playerlog_team_pts_l5" in row and "away_playerlog_team_pts_l5" in row:
            row["combined_playerlog_pts_l5"] = pd.to_numeric(row["home_playerlog_team_pts_l5"], errors="coerce") + pd.to_numeric(row["away_playerlog_team_pts_l5"], errors="coerce")
        if "home_dash_pts" in row and "away_dash_pts" in row:
            row["combined_dash_pts"] = pd.to_numeric(row["home_dash_pts"], errors="coerce") + pd.to_numeric(row["away_dash_pts"], errors="coerce")
        if "projection" in row and "line" in row:
            row["projection_minus_line"] = pd.to_numeric(row["projection"], errors="coerce") - pd.to_numeric(row["line"], errors="coerce")

        rows.append(row)

    out = pd.DataFrame(rows)

    # Try attach market consensus by fuzzy team names if available.
    if not out.empty and not market_features.empty:
        mf = market_features.copy()
        home_col = get_col(mf, ["home_team"])
        away_col = get_col(mf, ["away_team"])
        if home_col and away_col:
            mf["_home_code"] = mf[home_col].apply(team_code)
            mf["_away_code"] = mf[away_col].apply(team_code)
            out = out.merge(
                mf,
                left_on=["home_team", "away_team"],
                right_on=["_home_code", "_away_code"],
                how="left",
                suffixes=("", "_market"),
            )

    return out


def build_warnings(inputs: Dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for name, df in inputs.items():
        if df.empty:
            rows.append({"source": name, "severity": "medium", "message": f"{name} missing or empty"})
    return pd.DataFrame(rows)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    player_logs = read_csv(OUT / "official_mobile_playergamelogs_v21.csv")
    team_logs = read_csv(OUT / "official_mobile_teamgamelogs_v21.csv")
    team_dash = read_csv(OUT / "official_mobile_team_dash_base_v21.csv")
    player_dash = read_csv(OUT / "official_mobile_player_dash_base_v21.csv")
    dreb_rank = read_csv(OUT / "official_mobile_dreb_allowed_rankings_v21.csv")
    odds = read_csv(OUT / "odds_totals_latest_v21.csv")

    sdv_team = read_csv(CACHE / "sdv_wnba_team_boxscores.csv")
    sdv_player = read_csv(CACHE / "sdv_wnba_player_boxscores.csv")
    sdv_pbp = read_csv(CACHE / "sdv_wnba_pbp.csv")
    projections = read_csv(OUT / "projections_with_stakes.csv")
    recs = read_csv(OUT / "recommended_bets.csv")

    inputs = {
        "official_mobile_playergamelogs_v21": player_logs,
        "official_mobile_teamgamelogs_v21": team_logs,
        "official_mobile_team_dash_base_v21": team_dash,
        "official_mobile_player_dash_base_v21": player_dash,
        "official_mobile_dreb_allowed_rankings_v21": dreb_rank,
        "odds_totals_latest_v21": odds,
        "sdv_wnba_team_boxscores": sdv_team,
        "sdv_wnba_player_boxscores": sdv_player,
        "sdv_wnba_pbp": sdv_pbp,
        "projections_with_stakes": projections,
        "recommended_bets": recs,
    }

    team_features = build_team_features(player_logs, team_logs, team_dash, dreb_rank, sdv_team, sdv_pbp)
    player_features = build_player_features(player_logs, player_dash)
    market_features = build_market_features(odds)
    game_features = build_game_model_features(team_features, market_features, projections, recs)
    warnings = build_warnings(inputs)

    save_df(OUT / "team_features_v21.csv", team_features)
    save_df(OUT / "player_features_v21.csv", player_features)
    save_df(OUT / "market_features_v21.csv", market_features)
    save_df(OUT / "game_model_features_v21.csv", game_features)
    save_df(OUT / "hermes_feature_warnings_v21.csv", warnings)

    # Backward-friendly aliases for dashboard/next tools.
    save_df(OUT / "model_features_v21.csv", game_features)

    summary = {
        "created_at_utc": now_iso(),
        "status": "OK",
        "version": "v21",
        "rows": {
            "team_features": int(len(team_features)),
            "player_features": int(len(player_features)),
            "market_features": int(len(market_features)),
            "game_model_features": int(len(game_features)),
            "warnings": int(len(warnings)),
        },
        "inputs": {k: int(len(v)) for k, v in inputs.items()},
        "feature_groups": [
            "official_team_form",
            "official_player_form",
            "official_team_dashboard",
            "official_player_dashboard",
            "dreb_allowed_blend",
            "market_consensus",
            "projection_context",
        ],
        "safety": {
            "formula_changed": False,
            "staking_changed": False,
            "thresholds_changed": False,
            "auto_betting": False,
        },
    }
    save_json(OUT / "feature_builder_summary_v21.json", summary)

    safe_print("OK: V21 Feature Builder complete")
    safe_print(f"Team features:   {OUT / 'team_features_v21.csv'}")
    safe_print(f"Player features: {OUT / 'player_features_v21.csv'}")
    safe_print(f"Market features: {OUT / 'market_features_v21.csv'}")
    safe_print(f"Game features:   {OUT / 'game_model_features_v21.csv'}")
    safe_print(f"Rows: teams={len(team_features)} players={len(player_features)} market={len(market_features)} games={len(game_features)} warnings={len(warnings)}")
    safe_print("Note: advisory only; no projection/staking formula changed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
