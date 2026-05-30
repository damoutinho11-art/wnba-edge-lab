#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WNBA Edge Lab - Ultimate Fetcher V21.4

Production data fetcher after confirming the working WNBA.com method.

Priority:
1. Official WNBA.com mobile/minimal-header API
2. Odds API live markets
3. SportsDataverse / wehoop historical backfill
4. Local cache fallback

Safety:
- Data only
- No formula changes
- No staking changes
- No thresholds changed
- No betting
- No Telegram
"""

from __future__ import annotations

import argparse
import gzip
import io
import json
import os
import re
import time
import zipfile
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import requests


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "wnba_outputs"
CACHE = ROOT / "wnba_cache_v21"
CACHE20 = ROOT / "wnba_cache_v20"
CACHE2 = ROOT / "wnba_cache_v2"
SDV_RAW = CACHE / "sportsdataverse" / "raw"

LEAGUE_ID = "10"
SEASON_TYPE = "Regular Season"
ODDS_SPORT_KEY = "basketball_wnba"
ODDS_REGIONS = "us,us2,eu,uk"
ODDS_MARKETS = "h2h,spreads,totals"
PROP_MARKETS = ",".join([
    "player_points",
    "player_rebounds",
    "player_assists",
    "player_threes",
    "player_points_rebounds_assists",
    "player_points_alternate",
    "player_rebounds_alternate",
    "player_assists_alternate",
    "player_threes_alternate",
])
SPORTSDATAVERSE_REPO = "sportsdataverse/sportsdataverse-data"
GITHUB_API = "https://api.github.com"

SDV_TAGS = {
    "espn_wnba_schedules": "sdv_wnba_schedules.csv",
    "espn_wnba_team_boxscores": "sdv_wnba_team_boxscores.csv",
    "espn_wnba_player_boxscores": "sdv_wnba_player_boxscores.csv",
    "espn_wnba_pbp": "sdv_wnba_pbp.csv",
    "wnba_stats_schedules": "sdv_wnba_stats_schedules.csv",
    "wnba_stats_team_boxscores": "sdv_wnba_stats_team_boxscores.csv",
    "wnba_stats_player_boxscores": "sdv_wnba_stats_player_boxscores.csv",
    "wnba_stats_pbp": "sdv_wnba_stats_pbp.csv",
}

MOBILE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
    "Referer": "https://stats.wnba.com/",
    "Accept": "application/json",
}


@dataclass
class SourceRecord:
    source: str
    layer: str
    state: str
    rows: int = 0
    events: int = 0
    path: str = ""
    fallback_path: str = ""
    error: str = ""
    freshness: str = "unknown"
    season: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["created_at_utc"] = datetime.now(timezone.utc).isoformat()
        return d


def ensure_dirs() -> None:
    for p in [OUT, CACHE, CACHE20, CACHE2, SDV_RAW]:
        p.mkdir(parents=True, exist_ok=True)


def safe_print(text: str = "") -> None:
    try:
        print(text)
    except UnicodeEncodeError:
        print(str(text).encode("ascii", "replace").decode("ascii"))


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def today_token() -> str:
    return datetime.now().strftime("%Y_%m_%d")


def save_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def load_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def save_df(path: Path, df: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)


def rows_csv(path: Path) -> int:
    try:
        if path.exists():
            return int(pd.read_csv(path, low_memory=False).shape[0])
    except Exception:
        pass
    return 0


def normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    if df is None or df.empty:
        return pd.DataFrame()
    out = df.copy()
    out.columns = [re.sub(r"[^A-Za-z0-9]+", "_", str(c).strip()).strip("_") for c in out.columns]
    return out


def first_existing(paths: List[Path]) -> Optional[Path]:
    for p in paths:
        if p and p.exists() and p.stat().st_size > 0:
            return p
    return None


# --------------------------
# Official WNBA mobile API
# --------------------------

def stats_get(endpoint: str, params: Dict[str, Any], timeout: int = 20, retries: int = 2) -> Tuple[Optional[Dict[str, Any]], str]:
    url = f"https://stats.wnba.com/stats/{endpoint}"
    errors = []
    for attempt in range(retries):
        try:
            r = requests.get(url, params=params, headers=MOBILE_HEADERS, timeout=timeout)
            r.raise_for_status()
            return r.json(), ""
        except Exception as e:
            errors.append(f"attempt {attempt+1}: {type(e).__name__}: {e}")
            time.sleep(0.8 * (attempt + 1))
    return None, " | ".join(errors)


def result_df(data: Optional[Dict[str, Any]]) -> pd.DataFrame:
    if not data:
        return pd.DataFrame()
    sets = data.get("resultSets") or data.get("resultSet") or []
    if isinstance(sets, dict):
        sets = [sets]
    if not sets:
        return pd.DataFrame()
    rs = sets[0]
    headers = rs.get("headers") or rs.get("Headers") or []
    rows = rs.get("rowSet") or rs.get("RowSet") or []
    if not headers:
        return pd.DataFrame()
    return pd.DataFrame(rows, columns=headers)


def playergamelogs_params(season: int, measure: str = "Base", per_mode: str = "PerGame") -> Dict[str, Any]:
    return {
        "Season": str(season), "SeasonType": SEASON_TYPE,
        "LeagueID": LEAGUE_ID, "MeasureType": measure, "PerMode": per_mode,
        "LastNGames": "0", "Month": "0", "Period": "0",
        "PaceAdjust": "N", "PlusMinus": "N", "Rank": "N",
        "TeamID": "0", "OpponentTeamID": "0",
    }


def leaguegamelog_params(season: int, player_or_team: str = "T") -> Dict[str, Any]:
    return {
        "Season": str(season), "SeasonType": SEASON_TYPE,
        "LeagueID": LEAGUE_ID, "PlayerOrTeam": player_or_team,
        "Sorter": "DATE", "Direction": "DESC", "Counter": "0",
        "DateFrom": "", "DateTo": "",
    }


def dash_params(season: int, measure: str = "Base", per_mode: str = "PerGame", player: bool = False) -> Dict[str, Any]:
    p = {
        "Season": str(season), "SeasonType": SEASON_TYPE, "LeagueID": LEAGUE_ID,
        "MeasureType": measure, "PerMode": per_mode,
        "PlusMinus": "N", "PaceAdjust": "N", "Rank": "N",
        "LastNGames": "0", "Month": "0", "Period": "0",
        "TeamID": "0", "OpponentTeamID": "0",
        "Outcome": "", "Location": "", "SeasonSegment": "",
        "DateFrom": "", "DateTo": "", "Conference": "", "Division": "",
        "GameSegment": "", "ShotClockRange": "", "VsConference": "", "VsDivision": "",
    }
    if player:
        p.update({
            "PlayerExperience": "", "PlayerPosition": "", "StarterBench": "",
            "DraftYear": "", "DraftPick": "", "College": "", "Country": "",
            "Height": "", "Weight": "",
        })
    return p


def official_fetch_table(source: str, endpoint: str, params: Dict[str, Any], season: int, out_path: Path, fallbacks: List[Path], timeout: int, retries: int) -> Tuple[SourceRecord, pd.DataFrame]:
    data, err = stats_get(endpoint, params, timeout=timeout, retries=retries)
    df = normalize_cols(result_df(data))
    if not df.empty:
        df["FetchTimestampUTC"] = now_iso()
        df["SourceEndpoint"] = endpoint
        df["SeasonFetched"] = season
        save_df(out_path, df)
        return SourceRecord(source, "official_wnba_mobile", "LIVE_FETCH_OK", rows=len(df), path=str(out_path), freshness="live", season=str(season)), df

    fp = first_existing([out_path] + fallbacks)
    if fp:
        try:
            df = pd.read_csv(fp, low_memory=False)
            if "SeasonFetched" not in df.columns:
                df["SeasonFetched"] = season
            if not out_path.exists() and not df.empty:
                save_df(out_path, df)
            return SourceRecord(source, "official_wnba_mobile", "CACHE_FALLBACK_USED", rows=len(df), path=str(out_path if out_path.exists() else fp), fallback_path=str(fp), error=err, freshness="cached", season=str(season)), df
        except Exception as e:
            return SourceRecord(source, "official_wnba_mobile", "FETCH_FAILED_BAD_CACHE", error=f"{err}; cache read failed {type(e).__name__}: {e}", freshness="missing", season=str(season)), pd.DataFrame()

    return SourceRecord(source, "official_wnba_mobile", "FETCH_FAILED_NO_CACHE", error=err or "empty response", freshness="missing", season=str(season)), pd.DataFrame()


def fetch_official_mobile(seasons: List[int], timeout: int, retries: int, features: bool) -> Tuple[List[SourceRecord], Dict[str, pd.DataFrame]]:
    records: List[SourceRecord] = []
    frames: Dict[str, List[pd.DataFrame]] = {"playergamelogs": [], "teamgamelogs": [], "team_dash_base": [], "player_dash_base": []}

    for season in seasons:
        rec, df = official_fetch_table(
            "official_playergamelogs_base", "playergamelogs",
            playergamelogs_params(season, "Base", "PerGame"), season,
            CACHE / f"mobile_playergamelogs_{season}.csv",
            [CACHE / f"official_wnba_playergamelogs_{season}.csv", CACHE / "sdv_wnba_player_boxscores.csv", CACHE20 / "official_player_game_logs_2026.csv"],
            timeout, retries,
        )
        records.append(rec)
        if not df.empty:
            frames["playergamelogs"].append(df)
            if season == 2026:
                save_df(CACHE20 / "official_player_game_logs_2026.csv", df)

        rec, df = official_fetch_table(
            "official_teamgamelogs_base", "leaguegamelog",
            leaguegamelog_params(season, "T"), season,
            CACHE / f"mobile_teamgamelogs_{season}.csv",
            [CACHE / f"official_wnba_team_boxscores_traditional_{season}.csv", CACHE20 / "official_team_game_logs_2026.csv", CACHE2 / "teamgamelogs_traditional_2026.csv"],
            timeout, retries,
        )
        records.append(rec)
        if not df.empty:
            frames["teamgamelogs"].append(df)
            if season == 2026:
                save_df(CACHE20 / "official_team_game_logs_2026.csv", df)
                save_df(CACHE2 / "teamgamelogs_traditional_2026.csv", df)

        rec, df = official_fetch_table(
            "official_team_dash_base", "leaguedashteamstats",
            dash_params(season, "Base", "PerGame", player=False), season,
            CACHE / f"mobile_team_dash_base_{season}.csv",
            [CACHE / f"official_legacy_team_stats_base_{season}.csv"],
            timeout, retries,
        )
        records.append(rec)
        if not df.empty:
            frames["team_dash_base"].append(df)

        rec, df = official_fetch_table(
            "official_player_dash_base", "leaguedashplayerstats",
            dash_params(season, "Base", "PerGame", player=True), season,
            CACHE / f"mobile_player_dash_base_{season}.csv",
            [CACHE / f"official_legacy_player_stats_base_{season}.csv"],
            timeout, retries,
        )
        records.append(rec)
        if not df.empty:
            frames["player_dash_base"].append(df)

        if features:
            for measure in ["Advanced", "Four Factors", "Misc", "Scoring"]:
                slug = measure.lower().replace(" ", "_")
                rec, _ = official_fetch_table(
                    f"official_team_dash_{slug}", "leaguedashteamstats",
                    dash_params(season, measure, "PerGame", player=False), season,
                    CACHE / f"mobile_team_dash_{slug}_{season}.csv",
                    [CACHE / f"official_legacy_team_stats_{slug}_{season}.csv"],
                    timeout, retries,
                )
                records.append(rec)
            for measure in ["Advanced"]:
                slug = measure.lower().replace(" ", "_")
                rec, _ = official_fetch_table(
                    f"official_player_dash_{slug}", "leaguedashplayerstats",
                    dash_params(season, measure, "PerGame", player=True), season,
                    CACHE / f"mobile_player_dash_{slug}_{season}.csv",
                    [CACHE / f"official_legacy_player_stats_{slug}_{season}.csv"],
                    timeout, retries,
                )
                records.append(rec)

        time.sleep(0.4)

    combined = {k: (pd.concat(v, ignore_index=True, sort=False) if v else pd.DataFrame()) for k, v in frames.items()}

    if not combined["playergamelogs"].empty:
        save_df(OUT / "official_mobile_playergamelogs_v21.csv", combined["playergamelogs"])
    if not combined["teamgamelogs"].empty:
        save_df(OUT / "official_mobile_teamgamelogs_v21.csv", combined["teamgamelogs"])
        save_df(OUT / "official_mobile_team_game_totals_v21.csv", build_team_game_totals(combined["teamgamelogs"]))
    if not combined["team_dash_base"].empty:
        save_df(OUT / "official_mobile_team_dash_base_v21.csv", combined["team_dash_base"])
    if not combined["player_dash_base"].empty:
        save_df(OUT / "official_mobile_player_dash_base_v21.csv", combined["player_dash_base"])

    dreb = build_dreb_allowed(combined["playergamelogs"], seasons)
    if not dreb.empty:
        save_df(OUT / "official_mobile_dreb_allowed_rankings_v21.csv", dreb)

    return records, combined


def build_team_game_totals(team_logs: pd.DataFrame) -> pd.DataFrame:
    if team_logs.empty:
        return pd.DataFrame()
    df = team_logs.copy()
    cols = {c.upper(): c for c in df.columns}
    game_col = cols.get("GAME_ID")
    date_col = cols.get("GAME_DATE")
    team_col = cols.get("TEAM_ABBREVIATION")
    matchup_col = cols.get("MATCHUP")
    pts_col = cols.get("PTS")
    if not game_col or not pts_col:
        return pd.DataFrame()
    rows = []
    for gid, g in df.groupby(game_col, dropna=False):
        pts = pd.to_numeric(g[pts_col], errors="coerce").tolist()
        teams = g[team_col].astype(str).tolist() if team_col else []
        matchups = g[matchup_col].astype(str).tolist() if matchup_col else []
        rows.append({
            "GAME_ID": gid,
            "GAME_DATE": g[date_col].iloc[0] if date_col else "",
            "TEAM_1": teams[0] if len(teams) else "",
            "TEAM_2": teams[1] if len(teams) > 1 else "",
            "PTS_1": pts[0] if len(pts) else None,
            "PTS_2": pts[1] if len(pts) > 1 else None,
            "TOTAL_POINTS": sum([x for x in pts if pd.notna(x)]) if pts else None,
            "MATCHUP_1": matchups[0] if len(matchups) else "",
            "MATCHUP_2": matchups[1] if len(matchups) > 1 else "",
            "TEAM_ROWS": len(g),
        })
    return pd.DataFrame(rows)


def build_dreb_allowed(player_logs: pd.DataFrame, seasons: List[int]) -> pd.DataFrame:
    if player_logs.empty or not {"GAME_DATE", "MATCHUP", "DREB"}.issubset(set(player_logs.columns)):
        return pd.DataFrame()
    df = player_logs.copy()
    df["GAME_DATE"] = pd.to_datetime(df["GAME_DATE"], errors="coerce")
    df["DREB"] = pd.to_numeric(df["DREB"], errors="coerce")
    df["Opp"] = df["MATCHUP"].astype(str).str.extract(r"(?:vs\.?|@)\s*(\w+)$")
    if "SeasonFetched" not in df.columns:
        df["SeasonFetched"] = pd.to_datetime(df["GAME_DATE"], errors="coerce").dt.year
    df = df.dropna(subset=["GAME_DATE", "DREB", "Opp"])
    avgs = {}
    for season, g in df.groupby("SeasonFetched"):
        opp = g.groupby(["GAME_DATE", "Opp"])["DREB"].sum().reset_index()
        avgs[int(season)] = opp.groupby("Opp")["DREB"].mean()

    weights = {s: 1 / len(seasons) for s in seasons}
    if 2025 in seasons and 2026 in seasons:
        weights = {2025: 0.6, 2026: 0.4}

    teams = sorted(set().union(*[set(s.index) for s in avgs.values()])) if avgs else []
    rows = []
    for team in teams:
        num = 0.0
        den = 0.0
        detail = {}
        for season, weight in weights.items():
            val = avgs.get(season, pd.Series(dtype=float)).get(team, None)
            detail[f"DREB_Allowed_{season}"] = val
            if val is not None and pd.notna(val):
                num += float(val) * float(weight)
                den += float(weight)
        rows.append({"Team": team, "Blended_DREB_Allowed": num / den if den else None, **detail})
    out = pd.DataFrame(rows)
    if out.empty:
        return out
    out = out.sort_values("Blended_DREB_Allowed", ascending=False).reset_index(drop=True)
    out["Rank"] = out.index + 1
    out["Signal"] = ""
    out.loc[out["Rank"] <= 5, "Signal"] = "OVER"
    out.loc[out["Rank"] >= max(1, len(out) - 3), "Signal"] = "UNDER"
    return out


# --------------------------
# Odds API
# --------------------------

def odds_key() -> Optional[str]:
    key = os.getenv("ODDS_API_KEY") or os.getenv("THE_ODDS_API_KEY")
    return key.strip() if isinstance(key, str) else key


def fetch_odds(include_props: bool) -> List[SourceRecord]:
    records = []
    key = odds_key()
    if not key:
        for src in ["odds_events", "odds_totals", "player_props"]:
            records.append(SourceRecord(src, "odds_api", "FETCH_FAILED_NO_KEY", error="ODDS_API_KEY/THE_ODDS_API_KEY missing", freshness="missing"))
        return records

    s = requests.Session()
    s.headers.update({"User-Agent": "wnba-edge-lab-v21.4"})
    base = "https://api.the-odds-api.com/v4/sports"

    try:
        r = s.get(f"{base}/{ODDS_SPORT_KEY}/events", params={"apiKey": key}, timeout=20)
        r.raise_for_status()
        data = r.json()
        path = CACHE / f"odds_events_{today_token()}.json"
        save_json(path, data)
        save_json(CACHE / "odds_events_latest.json", data)
        records.append(SourceRecord("odds_events", "odds_api", "LIVE_FETCH_OK", events=len(data) if isinstance(data, list) else 0, path=str(path), freshness="live"))
    except Exception as e:
        fp = CACHE / "odds_events_latest.json"
        old = load_json(fp)
        if old is not None:
            records.append(SourceRecord("odds_events", "odds_api", "CACHE_FALLBACK_USED", events=len(old) if isinstance(old, list) else 0, path=str(fp), fallback_path=str(fp), error=f"{type(e).__name__}: {e}", freshness="cached"))
        else:
            records.append(SourceRecord("odds_events", "odds_api", "FETCH_FAILED_NO_CACHE", error=f"{type(e).__name__}: {e}", freshness="missing"))

    # Odds endpoint fallback ladder.
    # Some Odds API keys/plans accept "regions=us&markets=totals" but reject wider
    # region/market bundles. Try the safe known-good request first, then expand.
    odds_attempts = [
        {"regions": "us", "markets": "totals", "label": "safe_us_totals"},
        {"regions": "us", "markets": "h2h,spreads,totals", "label": "us_all_core"},
        {"regions": ODDS_REGIONS, "markets": "totals", "label": "all_regions_totals"},
        {"regions": ODDS_REGIONS, "markets": ODDS_MARKETS, "label": "all_regions_all_core"},
    ]
    odds_errors = []
    odds_success = False

    for attempt in odds_attempts:
        try:
            r = s.get(
                f"{base}/{ODDS_SPORT_KEY}/odds",
                params={
                    "apiKey": key,
                    "regions": attempt["regions"],
                    "markets": attempt["markets"],
                    "oddsFormat": "decimal",
                    "dateFormat": "iso",
                },
                timeout=30,
            )
            r.raise_for_status()
            data = r.json()
            save_json(CACHE / f"odds_totals_{today_token()}.json", data)
            save_json(CACHE / "odds_totals_latest.json", data)
            df = odds_to_frame(data)
            path = CACHE / "odds_totals_latest.csv"
            save_df(path, df)
            save_df(OUT / "odds_totals_latest_v21.csv", df)
            save_df(CACHE20 / "odds_totals_latest.csv", df)
            records.append(SourceRecord(
                "odds_totals",
                "odds_api",
                "LIVE_FETCH_OK",
                rows=len(df),
                events=len(data) if isinstance(data, list) else 0,
                path=str(path),
                freshness="live",
                error=f"odds_attempt={attempt['label']}; regions={attempt['regions']}; markets={attempt['markets']}",
            ))
            odds_success = True
            break
        except Exception as e:
            odds_errors.append(f"{attempt['label']}: {type(e).__name__}: {e}")

    if not odds_success:
        fp = CACHE / "odds_totals_latest.csv"
        if fp.exists():
            records.append(SourceRecord("odds_totals", "odds_api", "CACHE_FALLBACK_USED", rows=rows_csv(fp), path=str(fp), fallback_path=str(fp), error=" | ".join(odds_errors[-4:]), freshness="cached"))
        else:
            records.append(SourceRecord("odds_totals", "odds_api", "FETCH_FAILED_NO_CACHE", error=" | ".join(odds_errors[-4:]), freshness="missing"))

    if not include_props:
        records.append(SourceRecord("player_props", "odds_api", "SKIPPED", error="Use --props to fetch player props.", freshness="skipped"))
    else:
        events = load_json(CACHE / "odds_events_latest.json")
        events = events if isinstance(events, list) else []
        rows = []
        errors = []
        for ev in events:
            event_id = ev.get("id")
            if not event_id:
                continue
            try:
                r = s.get(
                    f"{base}/{ODDS_SPORT_KEY}/events/{event_id}/odds",
                    params={"apiKey": key, "regions": ODDS_REGIONS, "markets": PROP_MARKETS, "oddsFormat": "decimal", "dateFormat": "iso"},
                    timeout=30,
                )
                r.raise_for_status()
                data = r.json()
                save_json(CACHE / f"player_props_{event_id}_{today_token()}.json", data)
                rows.extend(player_props_to_rows(data, ev))
                time.sleep(0.2)
            except Exception as e:
                errors.append(f"{event_id}: {type(e).__name__}: {e}")
        dfp = pd.DataFrame(rows)
        path = CACHE / "player_props_latest.csv"
        save_df(path, dfp)
        save_df(OUT / "player_props_latest_v21.csv", dfp)
        records.append(SourceRecord("player_props", "odds_api", "LIVE_FETCH_OK" if len(dfp) else "FETCHED_EMPTY", rows=len(dfp), path=str(path), error=" | ".join(errors[:5]), freshness="live" if len(dfp) else "empty"))

    return records


def odds_to_frame(data: Any) -> pd.DataFrame:
    rows = []
    if not isinstance(data, list):
        return pd.DataFrame()
    for game in data:
        base = {"event_id": game.get("id"), "sport_key": game.get("sport_key"), "commence_time": game.get("commence_time"), "home_team": game.get("home_team"), "away_team": game.get("away_team")}
        for book in game.get("bookmakers", []) or []:
            for market in book.get("markets", []) or []:
                for outcome in market.get("outcomes", []) or []:
                    row = dict(base)
                    row.update({"bookmaker_key": book.get("key"), "bookmaker": book.get("title"), "last_update": book.get("last_update"), "market": market.get("key"), "name": outcome.get("name"), "price": outcome.get("price"), "point": outcome.get("point")})
                    rows.append(row)
    return pd.DataFrame(rows)


def player_props_to_rows(props: Any, event_meta: Dict[str, Any]) -> List[Dict[str, Any]]:
    rows = []
    if not isinstance(props, dict):
        return rows
    base = {"event_id": props.get("id") or event_meta.get("id"), "commence_time": props.get("commence_time") or event_meta.get("commence_time"), "home_team": props.get("home_team") or event_meta.get("home_team"), "away_team": props.get("away_team") or event_meta.get("away_team")}
    for book in props.get("bookmakers", []) or []:
        for market in book.get("markets", []) or []:
            for outcome in market.get("outcomes", []) or []:
                row = dict(base)
                row.update({"bookmaker_key": book.get("key"), "bookmaker": book.get("title"), "last_update": book.get("last_update"), "market": market.get("key"), "player": outcome.get("description") or outcome.get("name"), "side": outcome.get("name"), "price": outcome.get("price"), "point": outcome.get("point")})
                rows.append(row)
    return rows


# --------------------------
# SportsDataverse/wehoop
# --------------------------

def github_headers() -> Dict[str, str]:
    h = {"Accept": "application/vnd.github+json", "User-Agent": "wnba-edge-lab-v21.4", "X-GitHub-Api-Version": "2022-11-28"}
    token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
    if token:
        h["Authorization"] = f"Bearer {token}"
    return h


def fetch_sdv(season: int, all_assets: bool) -> List[SourceRecord]:
    return [fetch_sdv_tag(tag, out_name, season, all_assets) for tag, out_name in SDV_TAGS.items()]


def fetch_sdv_tag(tag: str, out_name: str, season: int, all_assets: bool) -> SourceRecord:
    out_path = CACHE / out_name
    try:
        r = requests.get(f"{GITHUB_API}/repos/{SPORTSDATAVERSE_REPO}/releases/tags/{tag}", headers=github_headers(), timeout=30)
        r.raise_for_status()
        assets = (r.json().get("assets") or [])
        chosen = select_sdv_assets(assets, season, all_assets)
        frames = []
        errors = []
        raw_dir = SDV_RAW / tag
        raw_dir.mkdir(parents=True, exist_ok=True)
        for asset in chosen:
            try:
                path = download_sdv_asset(asset, raw_dir)
                df = read_any_table(path)
                if df is not None and not df.empty:
                    frames.append(df)
            except Exception as e:
                errors.append(f"{asset.get('name')}: {type(e).__name__}: {e}")
        if frames:
            df = normalize_cols(pd.concat(frames, ignore_index=True, sort=False))
            df = filter_by_season(df, season)
            save_df(out_path, df)
            save_df(CACHE20 / out_name, df)
            return SourceRecord(tag, "sportsdataverse", "LIVE_FETCH_OK", rows=len(df), events=len(chosen), path=str(out_path), error=" | ".join(errors[:3]), freshness="live", season=str(season))
        if out_path.exists():
            return SourceRecord(tag, "sportsdataverse", "CACHE_FALLBACK_USED", rows=rows_csv(out_path), path=str(out_path), fallback_path=str(out_path), error="Assets unparsed. " + " | ".join(errors[:3]), freshness="cached", season=str(season))
        return SourceRecord(tag, "sportsdataverse", "FETCHED_ASSETS_UNPARSED", events=len(chosen), error=" | ".join(errors[:5]) or "Downloaded assets but no parseable table.", freshness="unparsed", season=str(season))
    except Exception as e:
        if out_path.exists():
            return SourceRecord(tag, "sportsdataverse", "CACHE_FALLBACK_USED", rows=rows_csv(out_path), path=str(out_path), fallback_path=str(out_path), error=f"{type(e).__name__}: {e}", freshness="cached", season=str(season))
        return SourceRecord(tag, "sportsdataverse", "FETCH_FAILED_NO_CACHE", error=f"{type(e).__name__}: {e}", freshness="missing", season=str(season))


def select_sdv_assets(assets: List[Dict[str, Any]], season: int, all_assets: bool) -> List[Dict[str, Any]]:
    filt = [a for a in assets if not re.search(r"(sha256|checksum|md5)", a.get("name", ""), re.I)]
    if not filt:
        filt = assets
    scored = sorted(filt, key=lambda a: sdv_score(a, season), reverse=True)
    if all_assets:
        return scored
    season_assets = [a for a in scored if str(season) in a.get("name", "")]
    return season_assets[:3] if season_assets else scored[:3]


def sdv_score(asset: Dict[str, Any], season: int) -> int:
    name = asset.get("name", "").lower()
    score = 100 if str(season) in name else 0
    if name.endswith((".csv", ".csv.gz")):
        score += 80
    elif name.endswith(".parquet"):
        score += 75
    elif name.endswith((".json", ".json.gz")):
        score += 60
    elif name.endswith(".zip"):
        score += 50
    elif name.endswith((".rds", ".rda", ".rdata")):
        score += 5
    if re.search(r"(sha256|checksum|md5)", name):
        score -= 100
    score += min(int(asset.get("size") or 0) // 1_000_000, 20)
    return score


def download_sdv_asset(asset: Dict[str, Any], dest: Path) -> Path:
    dest.mkdir(parents=True, exist_ok=True)
    out = dest / asset["name"]
    if out.exists() and out.stat().st_size > 0:
        return out
    url = asset.get("browser_download_url")
    if not url:
        raise ValueError("missing browser_download_url")
    with requests.get(url, headers={"User-Agent": "wnba-edge-lab-v21.4"}, stream=True, timeout=120) as r:
        r.raise_for_status()
        tmp = out.with_suffix(out.suffix + ".tmp")
        with tmp.open("wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    f.write(chunk)
        tmp.replace(out)
    return out


def read_any_table(path: Path) -> Optional[pd.DataFrame]:
    name = path.name.lower()
    try:
        if name.endswith(".csv"):
            return pd.read_csv(path, low_memory=False)
        if name.endswith(".csv.gz"):
            return pd.read_csv(path, compression="gzip", low_memory=False)
        if name.endswith(".parquet"):
            return pd.read_parquet(path)
        if name.endswith(".json"):
            return json_to_frame(json.loads(path.read_text(encoding="utf-8")))
        if name.endswith(".json.gz"):
            with gzip.open(path, "rt", encoding="utf-8") as f:
                return json_to_frame(json.load(f))
        if name.endswith(".zip"):
            return read_zip(path)
    except Exception:
        return None
    return None


def json_to_frame(data: Any) -> Optional[pd.DataFrame]:
    if isinstance(data, list):
        return pd.json_normalize(data)
    if isinstance(data, dict):
        for key in ["data", "items", "games", "events", "rows"]:
            if isinstance(data.get(key), list):
                return pd.json_normalize(data[key])
        return pd.json_normalize(data)
    return None


def read_zip(path: Path) -> Optional[pd.DataFrame]:
    frames = []
    with zipfile.ZipFile(path) as z:
        candidates = [n for n in z.namelist() if not n.startswith("__MACOSX/") and n.lower().endswith((".csv", ".csv.gz", ".parquet", ".json", ".json.gz"))]
        for member in candidates:
            try:
                lower = member.lower()
                with z.open(member) as f:
                    if lower.endswith(".csv"):
                        frames.append(pd.read_csv(f, low_memory=False))
                    elif lower.endswith(".csv.gz"):
                        raw = f.read()
                        with gzip.open(io.BytesIO(raw), "rt", encoding="utf-8") as gz:
                            frames.append(pd.read_csv(gz, low_memory=False))
                    elif lower.endswith(".json"):
                        data = json.load(io.TextIOWrapper(f, encoding="utf-8"))
                        df = json_to_frame(data)
                        if df is not None:
                            frames.append(df)
                    elif lower.endswith(".json.gz"):
                        raw = f.read()
                        with gzip.open(io.BytesIO(raw), "rt", encoding="utf-8") as gz:
                            data = json.load(gz)
                        df = json_to_frame(data)
                        if df is not None:
                            frames.append(df)
                    elif lower.endswith(".parquet"):
                        raw = f.read()
                        frames.append(pd.read_parquet(io.BytesIO(raw)))
            except Exception:
                continue
    return pd.concat(frames, ignore_index=True, sort=False) if frames else None


def filter_by_season(df: pd.DataFrame, season: int) -> pd.DataFrame:
    if df.empty:
        return df
    for c in df.columns:
        if c.lower() in {"season", "season_year", "year", "game_season"}:
            try:
                mask = df[c].astype(str).str.contains(str(season), na=False)
                if mask.any():
                    return df.loc[mask].copy()
            except Exception:
                pass
    return df


# --------------------------
# Health
# --------------------------

def build_warnings(records: List[SourceRecord]) -> pd.DataFrame:
    rows = []
    for r in records:
        if r.state == "LIVE_FETCH_OK":
            continue
        if r.state == "SKIPPED":
            sev = "info"
        elif r.state == "CACHE_FALLBACK_USED":
            sev = "low"
        elif r.state in {"FETCHED_EMPTY", "FETCHED_ASSETS_UNPARSED"}:
            sev = "medium"
        else:
            sev = "high"
        rows.append({"source": r.source, "layer": r.layer, "season": r.season, "state": r.state, "severity": sev, "rows": r.rows, "events": r.events, "message": r.error, "fallback_path": r.fallback_path})
    return pd.DataFrame(rows)


def write_health(records: List[SourceRecord], seasons: List[int]) -> None:
    df = pd.DataFrame([r.to_dict() for r in records])
    save_df(OUT / "ultimate_fetch_assets_v21_4.csv", df)
    save_df(OUT / "data_freshness_v21.csv", df)
    save_df(OUT / "data_freshness_v20.csv", df)

    warnings = build_warnings(records)
    save_df(OUT / "hermes_data_warnings_v21.csv", warnings)
    save_df(OUT / "hermes_data_warnings_v20.csv", warnings)

    def ready(source: str) -> bool:
        if df.empty:
            return False
        m = df[df["source"] == source]["state"].astype(str)
        return any(x in {"LIVE_FETCH_OK", "CACHE_FALLBACK_USED"} for x in m)

    status = {
        "created_at_utc": now_iso(),
        "version": "v21.4",
        "seasons": seasons,
        "overall_state": "OK" if not any(str(s).startswith("FETCH_FAILED") for s in df["state"].unique()) else "OK_WITH_WARNINGS",
        "state_counts": df["state"].value_counts().to_dict() if not df.empty else {},
        "warnings_count": int(len(warnings)),
        "warnings_high": int((warnings["severity"] == "high").sum()) if not warnings.empty else 0,
        "records": [r.to_dict() for r in records],
        "readiness": {
            "official_playergamelogs_ready": ready("official_playergamelogs_base"),
            "official_team_dash_ready": ready("official_team_dash_base"),
            "official_player_dash_ready": ready("official_player_dash_base"),
            "official_teamgamelogs_ready": ready("official_teamgamelogs_base"),
            "odds_ready": ready("odds_totals"),
            "sportsdataverse_ready": any(ready(x) for x in ["espn_wnba_team_boxscores", "espn_wnba_player_boxscores", "espn_wnba_pbp"]),
            "player_props_market_ready": ready("player_props"),
            "player_props_settlement_ready": ready("official_playergamelogs_base") or ready("espn_wnba_player_boxscores"),
        },
    }
    save_json(OUT / "data_source_health_v21.json", status)
    save_json(OUT / "data_source_health_v20.json", status)
    save_json(OUT / "data_fetch_status_v20.json", status)
    save_json(OUT / "ultimate_fetch_status_v21_4.json", status)


def parse_seasons(s: str) -> List[int]:
    return [int(x.strip()) for x in str(s).split(",") if x.strip()]


def main() -> int:
    parser = argparse.ArgumentParser(description="WNBA Edge Lab Ultimate Fetcher V21.4")
    parser.add_argument("--seasons", default="2025,2026")
    parser.add_argument("--season", type=int, default=2026)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--retries", type=int, default=2)
    parser.add_argument("--features", action="store_true")
    parser.add_argument("--props", action="store_true")
    parser.add_argument("--skip-sdv", action="store_true")
    parser.add_argument("--all-sdv-assets", action="store_true")
    args = parser.parse_args()

    ensure_dirs()
    seasons = parse_seasons(args.seasons)

    safe_print("=" * 72)
    safe_print(" WNBA EDGE LAB - ULTIMATE FETCHER V21.4")
    safe_print("=" * 72)
    safe_print(f"Seasons: {seasons}")
    safe_print("Priority: official mobile WNBA.com -> Odds API -> SportsDataverse -> cache")
    safe_print("Safety: data only; no formulas/staking/thresholds/betting changed")
    safe_print("")

    records: List[SourceRecord] = []

    safe_print("[1/3] Official WNBA.com mobile/minimal-header fetch")
    official_records, _ = fetch_official_mobile(seasons, args.timeout, args.retries, args.features)
    records.extend(official_records)

    safe_print("[2/3] Odds API live markets")
    records.extend(fetch_odds(include_props=args.props))

    if args.skip_sdv:
        safe_print("[3/3] SportsDataverse skipped")
        records.append(SourceRecord("sportsdataverse", "sportsdataverse", "SKIPPED", error="--skip-sdv used", freshness="skipped"))
    else:
        safe_print("[3/3] SportsDataverse/wehoop historical backfill")
        records.extend(fetch_sdv(args.season, args.all_sdv_assets))

    write_health(records, seasons)

    status = load_json(OUT / "ultimate_fetch_status_v21_4.json") or {}
    safe_print("")
    safe_print("OK: Ultimate Fetcher V21.4 complete")
    safe_print(f"Overall: {status.get('overall_state')}")
    safe_print(f"Warnings: {status.get('warnings_count')} total / {status.get('warnings_high')} high")
    safe_print(f"Readiness: {status.get('readiness')}")
    safe_print(f"Status JSON: {OUT / 'ultimate_fetch_status_v21_4.json'}")
    safe_print("")
    for r in records:
        safe_print(f" - {r.source} {r.season}: layer={r.layer} state={r.state} rows={r.rows} events={r.events} path={r.path} fallback={r.fallback_path} error={r.error[:110]}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
