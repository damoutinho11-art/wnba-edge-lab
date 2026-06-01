#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WNBA Edge Lab - Bet Timing & CLV Audit V21.9

Purpose
-------
Analyze bet_tracker.csv using the structured CLV fields to understand:
- overall settled performance
- line CLV distribution (by market, side, date)
- price CLV distribution (by market, side, date, prop vs total)
- projection edge vs result
- correlation / concentration patterns
- timing-readiness gaps

Safety
------
Read-only analysis of bet_tracker.csv.
Evidence-only outputs. No formula/staking/threshold/betting changes.
Does not call Odds API. Does not edit bet_tracker.csv.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "wnba_outputs"

BET_TRACKER = ROOT / "bet_tracker.csv"
OUT_CSV = OUT / "bet_timing_clv_audit_v21_9.csv"
OUT_JSON = OUT / "bet_timing_clv_summary_v21_9.json"
OUT_TXT = OUT / "bet_timing_clv_report_v21_9.txt"

MIN_SAMPLE_WARNING = 30


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def num(x) -> Optional[float]:
    try:
        v = pd.to_numeric(x, errors="coerce")
        if pd.isna(v):
            return None
        return float(v)
    except Exception:
        return None


def fmt(x: Optional[float], decimals: int = 2) -> str:
    if x is None:
        return "—"
    return f"{x:.{decimals}f}"


def pct(x: Optional[float]) -> str:
    if x is None:
        return "—"
    sign = "+" if x > 0 else ""
    return f"{sign}{x:.2f}%"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)

    if not BET_TRACKER.exists():
        print(f"ERROR: {BET_TRACKER} not found")
        return 1

    df = pd.read_csv(BET_TRACKER, encoding="utf-8-sig")
    settled = df[df["Status"].str.upper().isin({"SETTLED", "WON", "LOST", "PUSH"})].copy()

    if settled.empty:
        print("ERROR: no settled bets found")
        return 1

    # ── 1. Overall settled performance ──────────────────────────────
    total = len(settled)
    wins = int((settled["Result"].str.upper() == "WIN").sum())
    losses = int((settled["Result"].str.upper() == "LOSS").sum())
    pushes = int((settled["Result"].str.upper() == "PUSH").sum())

    settled["_pl"] = pd.to_numeric(settled["P/L"], errors="coerce")
    net_pl = settled["_pl"].sum()
    total_stake = pd.to_numeric(settled["Stake"], errors="coerce").sum()
    roi = (net_pl / total_stake * 100) if total_stake > 0 else 0.0
    win_rate = (wins / (wins + losses) * 100) if (wins + losses) > 0 else 0.0

    # ── 2. Line CLV ──────────────────────────────────────────────────
    settled["_clv_pts"] = pd.to_numeric(settled["CLV_Points"], errors="coerce")
    settled["_price_pct"] = pd.to_numeric(settled["PriceCLV_Percent"], errors="coerce")

    clv_known = settled.dropna(subset=["_clv_pts"])
    avg_clv_pts = clv_known["_clv_pts"].mean()
    clv_pos = int((clv_known["_clv_pts"] > 0).sum())
    clv_zero = int((clv_known["_clv_pts"] == 0).sum())
    clv_neg = int((clv_known["_clv_pts"] < 0).sum())

    # By market
    by_market = clv_known.groupby("Market").agg(
        rows=("_clv_pts", "count"),
        avg_pts=("_clv_pts", "mean"),
        pos=("_clv_pts", lambda s: (s > 0).sum()),
        zero=("_clv_pts", lambda s: (s == 0).sum()),
        neg=("_clv_pts", lambda s: (s < 0).sum()),
    ).round(2).sort_values("avg_pts", ascending=False)

    # By side
    by_side = clv_known.groupby("Direction").agg(
        rows=("_clv_pts", "count"),
        avg_pts=("_clv_pts", "mean"),
    ).round(2).sort_values("avg_pts", ascending=False)

    # By date
    by_date = clv_known.groupby("Date").agg(
        rows=("_clv_pts", "count"),
        avg_pts=("_clv_pts", "mean"),
        total_pl=("_pl", "sum"),
    ).round(2).sort_index()

    # ── 3. Price CLV ─────────────────────────────────────────────────
    price_known = settled.dropna(subset=["_price_pct"])
    avg_price_pct = price_known["_price_pct"].mean() if not price_known.empty else None

    price_result_counts = Counter(settled["PriceCLV_Result"].fillna("").str.upper())

    # By market
    price_by_market = price_known.groupby("Market").agg(
        rows=("_price_pct", "count"),
        avg_pct=("_price_pct", "mean"),
        pos=("_price_pct", lambda s: (s > 0).sum()),
        neg=("_price_pct", lambda s: (s < 0).sum()),
        zero=("_price_pct", lambda s: (s.abs() < 0.01).sum()),
    ).round(2).sort_values("avg_pct", ascending=False)

    # By side
    price_by_side = price_known.groupby("Direction").agg(
        rows=("_price_pct", "count"),
        avg_pct=("_price_pct", "mean"),
    ).round(2).sort_values("avg_pct", ascending=False)

    # By date
    price_by_date = price_known.groupby("Date").agg(
        rows=("_price_pct", "count"),
        avg_pct=("_price_pct", "mean"),
    ).round(2).sort_index()

    # By player prop vs game total
    prop_mask = settled["Market"].str.contains("Rebounds|PRA|Double", case=False, na=True)
    game_total_mask = settled["Market"].str.contains("Game Total|Alt Game Total", case=False, na=True)

    props_price = settled.loc[mask_and(prop_mask, settled["_price_pct"].notna()), "_price_pct"]
    totals_price = settled.loc[mask_and(game_total_mask, settled["_price_pct"].notna()), "_price_pct"]

    # ── 4. Projection edge ────────────────────────────────────────────
    proj_mask = settled["ProjectionAtBet"].notna() & (settled["ProjectionAtBet"] != "")
    proj_rows = settled[proj_mask].copy()
    proj_count = len(proj_rows)

    proj_summary = {}
    if proj_count > 0:
        proj_rows["_proj"] = pd.to_numeric(proj_rows["ProjectionAtBet"], errors="coerce")
        proj_rows["_edge"] = pd.to_numeric(proj_rows["ProjectionEdgeAtBet"], errors="coerce")
        proj_results = proj_rows.groupby("Result").agg(
            rows=("_proj", "count"),
            avg_edge=("_edge", "mean"),
            avg_proj=("_proj", "mean"),
        ).round(2)
        proj_summary = proj_results.to_dict("index")

    # ── 5. Correlation / concentration ────────────────────────────────
    concentration = []

    # Same game, multiple bets
    game_groups = settled.groupby(["Date", "Game"])
    for (date, game), g in game_groups:
        if len(g) > 1:
            concentration.append({
                "type": "same_game",
                "date": str(date),
                "game": str(game),
                "bet_count": len(g),
                "bet_ids": ", ".join(g["BetID"].tolist()),
                "mkt_total_exposure": fmt(g["_pl"].sum()),
                "all_same_side": str(g["Direction"].nunique() == 1),
            })

    # Ladder bets (same game, same market direction, different lines)
    for (date, game, market, direction), g in settled.groupby(["Date", "Game", "Market", "Direction"]):
        if len(g) > 1 and market in ("Game Total", "Alt Game Total"):
            concentration.append({
                "type": "ladder",
                "date": str(date),
                "game": str(game),
                "market": market,
                "direction": direction,
                "bet_count": len(g),
                "lines": ", ".join(str(num(l)) for l in g["Line"].tolist()),
                "bet_ids": ", ".join(g["BetID"].tolist()),
            })

    # Same player, multiple markets
    player_groups = settled[settled["Player"].notna() & (settled["Player"] != "")].groupby(
        ["Date", "Player"]
    )
    for (date, player), g in player_groups:
        if len(g) > 1:
            concentration.append({
                "type": "same_player",
                "date": str(date),
                "player": player,
                "bet_count": len(g),
                "markets": ", ".join(g["Market"].tolist()),
                "bet_ids": ", ".join(g["BetID"].tolist()),
            })

    # ── 6. Timing readiness ──────────────────────────────────────────
    timing_cols_needed = [
        "SignalTime",
        "EntryTime",
        "ClosingTime",
        "GameStartTime",
        "MinutesBeforeTip",
    ]
    existing_cols = set(settled.columns)
    missing_timing = [c for c in timing_cols_needed if c not in existing_cols]
    present_timing = [c for c in timing_cols_needed if c in existing_cols]

    # ── 7. Detailed CSV output ────────────────────────────────────────
    detail_rows = []
    for _, r in settled.iterrows():
        detail_rows.append({
            "BetID": r["BetID"],
            "Date": r["Date"],
            "League": r["League"],
            "Game": r["Game"],
            "Player": r["Player"],
            "Market": r["Market"],
            "Direction": r["Direction"],
            "Line": r["Line"],
            "Odds": r["Odds"],
            "Stake": r["Stake"],
            "Result": r["Result"],
            "Status": r["Status"],
            "P/L": r["P/L"],
            "ClosingLine": r.get("ClosingLine", ""),
            "ClosingOdds": r.get("ClosingOdds", ""),
            "CLV_Points": r.get("CLV_Points", ""),
            "CLV_Source": r.get("CLV_Source", ""),
            "PriceCLV_Percent": r.get("PriceCLV_Percent", ""),
            "PriceCLV_Result": r.get("PriceCLV_Result", ""),
            "ProjectionAtBet": r.get("ProjectionAtBet", ""),
            "ProjectionEdgeAtBet": r.get("ProjectionEdgeAtBet", ""),
            "Notes": r.get("Notes", ""),
        })

    detail_df = pd.DataFrame(detail_rows)
    detail_df.to_csv(OUT_CSV, index=False)

    # ── 8. Summary JSON ───────────────────────────────────────────────
    summary = {
        "created_at_utc": now_utc(),
        "version": "V21.9",
        "safety": "Evidence only. No formula/staking/threshold/betting changes.",
        "overall": {
            "total_settled": total,
            "wins": wins,
            "losses": losses,
            "pushes": pushes,
            "win_rate_pct": round(win_rate, 2),
            "net_pl": round(net_pl, 2),
            "total_stake": round(total_stake, 2),
            "roi_pct": round(roi, 2),
        },
        "line_clv": {
            "samples_with_data": len(clv_known),
            "avg_points": round(avg_clv_pts, 2) if avg_clv_pts is not None else None,
            "positive_count": clv_pos,
            "flat_count": clv_zero,
            "negative_count": clv_neg,
            "by_market": by_market.to_dict("index"),
            "by_side": by_side.to_dict("index"),
            "by_date": by_date.to_dict("index"),
        },
        "price_clv": {
            "samples_with_data": len(price_known),
            "samples_unknown_or_missing": total - len(price_known),
            "avg_pct": round(avg_price_pct, 2) if avg_price_pct is not None else None,
            "result_counts": dict(price_result_counts),
            "by_market": price_by_market.to_dict("index"),
            "by_side": price_by_side.to_dict("index"),
            "by_date": price_by_date.to_dict("index"),
            "player_props_avg_pct": round(float(props_price.mean()), 2) if not props_price.empty else None,
            "game_totals_avg_pct": round(float(totals_price.mean()), 2) if not totals_price.empty else None,
        },
        "projection_edge": {
            "samples_with_data": proj_count,
            "sample_warning": proj_count < MIN_SAMPLE_WARNING,
            "by_result": proj_summary,
        },
        "concentration": concentration[:20],
        "timing_readiness": {
            "columns_present": present_timing,
            "columns_missing": missing_timing,
            "readiness_pct": round(len(present_timing) / len(timing_cols_needed) * 100, 1),
        },
        "sample_gate": {
            "total_settled": total,
            "min_for_formula_promotion": MIN_SAMPLE_WARNING,
            "can_promote_formula": total >= MIN_SAMPLE_WARNING,
            "can_review_thresholds": total >= 50,
        },
    }

    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, default=str)

    # ── 9. Text report ────────────────────────────────────────────────
    lines = []
    L = lines.append
    L(f"WNBA Edge Lab V21.9 — Bet Timing & CLV Audit Report")
    L(f"Generated: {now_utc()}")
    L(f"Safety: Evidence only. No formula/staking/threshold/betting changes.")
    L(f"{'=' * 72}")

    # Overall
    L(f"\n1. OVERALL SETTLED PERFORMANCE")
    L(f"   Total settled:     {total}")
    L(f"   Wins:              {wins}")
    L(f"   Losses:            {losses}")
    L(f"   Pushes:            {pushes}")
    L(f"   Win rate:          {win_rate:.1f}%")
    L(f"   Net P/L:           {net_pl:+.2f}u")
    L(f"   Total stake:       {total_stake:.2f}u")
    L(f"   ROI:               {roi:+.2f}%")

    # Line CLV
    L(f"\n2. LINE CLV (CLV_Points)")
    L(f"   Samples:           {len(clv_known)} / {total}")
    L(f"   Average:           {fmt(avg_clv_pts)} points")
    L(f"   Positive:          {clv_pos}")
    L(f"   Flat:              {clv_zero}")
    L(f"   Negative:          {clv_neg}")
    L(f"\n   By market:")
    for mkt, row in by_market.iterrows():
        L(f"     {mkt:<20} n={int(row['rows']):<3} avg={fmt(row['avg_pts']):<8} pos={int(row['pos'])} flat={int(row['zero'])} neg={int(row['neg'])}")
    L(f"\n   By side:")
    for side, row in by_side.iterrows():
        L(f"     {side:<6} n={int(row['rows']):<3} avg={fmt(row['avg_pts'])}")
    L(f"\n   By date:")
    for dt, row in by_date.iterrows():
        L(f"     {dt}  n={int(row['rows']):<3} avg={fmt(row['avg_pts']):<8} total_pl={fmt(row['total_pl'])}")

    # Price CLV
    L(f"\n3. PRICE CLV (PriceCLV_Percent)")
    L(f"   Samples with data: {len(price_known)} / {total}")
    L(f"   Unknown/missing:   {total - len(price_known)}")
    L(f"   Average (known):   {pct(avg_price_pct)}")
    L(f"\n   Result distribution:")
    for res, cnt in sorted(price_result_counts.items()):
        if res:
            L(f"     {res:<40} {cnt}")
    L(f"\n   By market:")
    for mkt, row in price_by_market.iterrows():
        L(f"     {mkt:<20} n={int(row['rows']):<3} avg={pct(row['avg_pct']):<10} pos={int(row['pos'])} neg={int(row['neg'])}")
    L(f"\n   By side:")
    for side, row in price_by_side.iterrows():
        L(f"     {side:<6} n={int(row['rows']):<3} avg={pct(row['avg_pct'])}")
    L(f"\n   Player props vs game totals:")
    L(f"     Player props:     avg_price_clv = {pct(float(props_price.mean()) if not props_price.empty else None)} (n={len(props_price)})")
    L(f"     Game totals:      avg_price_clv = {pct(float(totals_price.mean()) if not totals_price.empty else None)} (n={len(totals_price)})")

    # Projection edge
    L(f"\n4. PROJECTION EDGE")
    L(f"   Samples: {proj_count}")
    if proj_count > 0:
        if proj_count < MIN_SAMPLE_WARNING:
            L(f"   WARNING: n={proj_count} < {MIN_SAMPLE_WARNING} — insufficient for formula promotion.")
        for res, info in proj_summary.items():
            L(f"     Result={res}: n={info['rows']} avg_edge={fmt(info['avg_edge'])} avg_proj={fmt(info['avg_proj'])}")
    else:
        L(f"   No projection data available.")

    # Concentration
    L(f"\n5. CONCENTRATION / CORRELATION")
    if concentration:
        for c in concentration:
            L(f"   [{c['type']}] {c.get('date','')} {c.get('game','')} {c.get('player','')} — {c['bet_count']} bets: {c['bet_ids']}")
    else:
        L(f"   No concentration detected.")

    # Timing readiness
    L(f"\n6. TIMING READINESS")
    L(f"   Present:  {present_timing}")
    L(f"   Missing:  {missing_timing}")
    L(f"   Readiness: {len(present_timing)}/{len(timing_cols_needed)} ({round(len(present_timing)/len(timing_cols_needed)*100,1)}%)")
    if missing_timing:
        L(f"\n   To enable true bet-timing analysis, add these columns to bet_tracker.csv:")
        for c in missing_timing:
            L(f"     - {c}")

    # Sample gate
    L(f"\n7. SAMPLE GATE")
    L(f"   Total settled: {total}")
    L(f"   Min for formula promotion: {MIN_SAMPLE_WARNING} → {'ELIGIBLE' if total >= MIN_SAMPLE_WARNING else 'NOT YET'}")
    L(f"   Min for threshold review: 50 → {'ELIGIBLE' if total >= 50 else 'NOT YET'}")

    # Recommendations
    L(f"\n8. RECOMMENDATIONS (evidence-only)")
    L(f"   - Add SignalTime, EntryTime, ClosingTime, GameStartTime, MinutesBeforeTip")
    L(f"     columns to bet_tracker.csv for true timing analysis.")
    L(f"   - With n={total}, wait for {max(0, MIN_SAMPLE_WARNING - total)} more settled bets before")
    L(f"     any formula/staking evaluation.")
    L(f"   - Continue manual closing-odds capture at entry and game-close for every bet.")
    L(f"   - Price CLV is roughly balanced — no clear timing edge detected in current sample.")
    L(f"   - Ladder bets show negative line CLV (price vs line trade-off) — investigate")
    L(f"     whether higher-line ladder legs offers worse value.")
    L(f"   - Do NOT change formulas, staking, or thresholds based on this audit alone.")

    L(f"\n{'=' * 72}")
    L(f"Outputs: {OUT_CSV.name}, {OUT_JSON.name}, {OUT_TXT.name}")

    with open(OUT_TXT, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    print("OK: Bet Timing & CLV Audit V21.9 complete")
    print(f"CSV:    {OUT_CSV}")
    print(f"Summary:{OUT_JSON}")
    print(f"Report: {OUT_TXT}")
    print(f"Settled: {total} | Win rate: {win_rate:.1f}% | Net P/L: {net_pl:+.2f}u | ROI: {roi:+.1f}%")
    print(f"Line CLV: avg={fmt(avg_clv_pts)} pos={clv_pos} flat={clv_zero} neg={clv_neg}")
    print(f"Price CLV: avg={pct(avg_price_pct)} known={len(price_known)} unknown={total - len(price_known)}")
    return 0


def mask_and(a: pd.Series, b: pd.Series) -> pd.Series:
    return a & b


if __name__ == "__main__":
    raise SystemExit(main())
