#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WNBA Edge Lab V21.9 — Manual Bet Entry Helper

Purpose
-------
Safely append one manually approved bet to bet_tracker.csv with timing
instrumentation. Used by the Hermes operator to record bets placed via
manual review (no auto-betting).

Safety
------
- Appends exactly ONE row per invocation with --enter.
- Never modifies existing rows.
- Never settles bets or computes P/L.
- Never calls Odds API.
- Never changes model formulas, staking, thresholds, or approvals.
- Duplicate-prevention: rejects OPEN bet with same Date+Game+Market+Direction+Line.
- --dry-run prints the row without writing.
- Fails safely if timing columns are missing from schema.

Usage
-----
    python manual_bet_entry_v21_9.py --enter \
        --game "LV Aces @ GS Valkyries" \
        --market "Game Total" \
        --direction OVER \
        --line 168.5 --odds 1.90 --stake 0.10 \
        --book manual --league WNBA --notes "model queue bet"

    python manual_bet_entry_v21_9.py --enter --dry-run \
        --game "TEST @ TEST" --market "Game Total" \
        --direction OVER --line 168.5 --odds 1.90 --stake 0.10
"""

from __future__ import annotations

import argparse
import csv
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
BET_TRACKER = ROOT / "bet_tracker.csv"

REQUIRED_COLUMNS = [
    "BetID",
    "Date",
    "League",
    "Game",
    "Market",
    "Direction",
    "Line",
    "Odds",
    "Stake",
    "Status",
    "Result",
    "EntryTimeUTC",
    "CreatedAt",
    "UpdatedAt",
    "BetSource",
    "ApprovalSource",
]

TIMING_COLUMNS = [
    "SignalTimeUTC",
    "EntryTimeUTC",
    "GameStartTimeUTC",
    "MinutesBeforeTip",
    "BetSource",
    "ApprovalSource",
]

REQUIRED_ARGS = ["--enter", "--game", "--market", "--direction", "--line", "--odds", "--stake"]

KNOWN_MARKETS = {
    "Game Total",
    "Alt Game Total",
    "Rebounds",
    "Points & Rebounds",
    "PRA",
    "Double Double",
    "Spread",
    "Moneyline",
}

KNOWN_LEAGUES = {"WNBA", "LPB", "NBA", "NFL", "NHL", "MLB"}


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_utc() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def num(x) -> Optional[float]:
    try:
        return float(str(x).strip())
    except (ValueError, TypeError):
        return None


def parse_iso(s: str) -> Optional[datetime]:
    """Parse ISO 8601 timestamp, return None on failure."""
    s = s.strip()
    if not s:
        return None
    try:
        # Handle both with and without timezone suffix
        s_clean = s.replace("Z", "+00:00")
        return datetime.fromisoformat(s_clean)
    except (ValueError, TypeError):
        return None


def next_bid(rows: List[Dict[str, str]]) -> str:
    """Generate next BetID as BET-{max+1:05d}."""
    max_n = 0
    for r in rows:
        m = re.match(r"BET-(\d+)", r.get("BetID", ""))
        if m:
            n = int(m.group(1))
            if n > max_n:
                max_n = n
    return f"BET-{max_n + 1:05d}"


def check_required_fields(fieldnames: List[str]) -> List[str]:
    """Return list of required columns missing from schema."""
    return [c for c in REQUIRED_COLUMNS if c not in fieldnames]


def check_duplicate_open(
    rows: List[Dict[str, str]],
    date: str,
    game: str,
    market: str,
    direction: str,
    line: str,
) -> Optional[str]:
    """Check for existing OPEN bet with same key. Returns matching BetID or None."""
    for r in rows:
        if r.get("Status", "").strip().upper() != "OPEN":
            continue
        if (
            r.get("Date", "").strip() == date
            and r.get("Game", "").strip() == game
            and r.get("Market", "").strip() == market
            and r.get("Direction", "").strip() == direction
            and r.get("Line", "").strip() == line
        ):
            return r.get("BetID", "")
    return None


def build_row(args: argparse.Namespace, fieldnames: List[str], next_bid_str: str) -> Dict[str, str]:
    """Build a new bet row dict with all fields."""
    row: Dict[str, str] = {col: "" for col in fieldnames}

    # Operator-supplied fields
    row["BetID"] = next_bid_str
    row["Date"] = args.date
    row["League"] = args.league
    row["Game"] = args.game
    row["Market"] = args.market
    row["Direction"] = args.direction
    row["Line"] = str(args.line)
    row["Odds"] = str(args.odds)
    row["Stake"] = str(args.stake)
    row["Book"] = args.book
    row["Player"] = args.player
    row["Signal"] = args.signal
    row["ModelVersion"] = args.model_version
    row["Notes"] = args.notes

    # Auto-filled
    row["ActualUnits"] = str(args.actual_units if args.actual_units else args.stake)
    row["SuggestedUnits"] = str(args.suggested_units if args.suggested_units else args.stake)
    row["OpeningLine"] = str(args.line)
    row["Status"] = "OPEN"
    row["Result"] = ""
    row["Actual"] = ""
    row["P/L"] = ""
    row["ClosingLine"] = ""
    row["ClosingOdds"] = ""
    row["CLV"] = ""
    row["CLV_Percent"] = ""
    row["CLV_Points"] = ""
    row["CLV_Source"] = ""
    row["PriceCLV_Percent"] = ""
    row["PriceCLV_Result"] = ""

    # Timing
    row["EntryTimeUTC"] = args.entry_time_utc or now_iso()
    row["CreatedAt"] = now_iso()
    row["UpdatedAt"] = now_iso()
    row["BetSource"] = "manual_operator"
    row["ApprovalSource"] = "hermes_manual"
    row["SignalTimeUTC"] = args.signal_time or ""
    row["GameStartTimeUTC"] = args.game_start or ""

    # MinutesBeforeTip
    if args.game_start and row["EntryTimeUTC"]:
        try:
            entry_dt = parse_iso(row["EntryTimeUTC"])
            start_dt = parse_iso(args.game_start)
            if entry_dt and start_dt:
                delta = (start_dt - entry_dt).total_seconds() / 60.0
                row["MinutesBeforeTip"] = str(round(delta, 1))
        except Exception:
            row["MinutesBeforeTip"] = ""

    # Optional model fields
    if args.projection:
        row["Projection"] = str(args.projection)
    if args.edge:
        row["Edge"] = str(args.edge)
    if args.confidence:
        row["Confidence"] = str(args.confidence)
    if args.final_signal:
        row["FinalSignal"] = args.final_signal

    return row


def validate(args: argparse.Namespace, rows: List[Dict[str, str]], fieldnames: List[str]) -> Tuple[bool, List[str], List[str]]:
    """
    Validate CLI args. Returns (is_valid, errors, warnings).
    """
    errors: List[str] = []
    warnings: List[str] = []

    # Required columns check
    missing_cols = check_required_fields(fieldnames)
    if missing_cols:
        errors.append(
            f"Schema patch required: missing columns: {missing_cols}. "
            f"Run bet_tracker.csv schema upgrade first."
        )
        return False, errors, warnings

    # Game format
    game = args.game
    if "@" not in game and " vs " not in game and " VS " not in game:
        errors.append(f"Game '{game}' does not contain '@' or ' vs ' — invalid format.")

    # Line numeric
    line_val = num(args.line)
    if line_val is None:
        errors.append(f"Line '{args.line}' is not numeric.")

    # Odds > 1.0
    odds_val = num(args.odds)
    if odds_val is None or odds_val <= 1.0:
        errors.append(f"Odds '{args.odds}' must be numeric and > 1.0.")

    # Stake > 0
    stake_val = num(args.stake)
    if stake_val is None or stake_val <= 0:
        errors.append(f"Stake '{args.stake}' must be numeric and > 0.")

    # Date format YYYY-MM-DD
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", args.date):
        errors.append(f"Date '{args.date}' is not YYYY-MM-DD format.")
    else:
        try:
            datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            errors.append(f"Date '{args.date}' is not a valid calendar date.")

    # Signal time
    if args.signal_time:
        if parse_iso(args.signal_time) is None:
            errors.append(f"Signal time '{args.signal_time}' is not valid ISO 8601.")

    # Game start
    if args.game_start:
        if parse_iso(args.game_start) is None:
            errors.append(f"Game start '{args.game_start}' is not valid ISO 8601.")

    # Duplicate check
    dup = check_duplicate_open(rows, args.date, game, args.market, args.direction, str(args.line))
    if dup:
        errors.append(f"Duplicate OPEN bet: {dup} already has Date+Game+Market+Direction+Line combination.")

    # Warnings
    if args.market not in KNOWN_MARKETS:
        warnings.append(f"Market '{args.market}' is not in known set {KNOWN_MARKETS} — proceeding anyway.")
    if args.league not in KNOWN_LEAGUES:
        warnings.append(f"League '{args.league}' is not in known set {KNOWN_LEAGUES} — proceeding anyway.")

    return len(errors) == 0, errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(
        description="WNBA Edge Lab V21.9 — Manual Bet Entry Helper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument("--enter", action="store_true", help="Add a new bet row (required to write)")
    parser.add_argument("--dry-run", action="store_true", help="Print row without writing")

    # Required bet fields
    parser.add_argument("--game", type=str, help="Game matchup, e.g. 'LV Aces @ GS Valkyries'")
    parser.add_argument("--market", type=str, help="Market, e.g. 'Game Total', 'Rebounds'")
    parser.add_argument("--direction", type=str, help="Direction/Side, e.g. 'OVER', 'UNDER'")
    parser.add_argument("--line", type=str, help="Line value, e.g. '168.5'")
    parser.add_argument("--odds", type=str, help="Decimal odds, e.g. '1.90'")
    parser.add_argument("--stake", type=str, help="Stake in units, e.g. '0.10'")

    # Optional fields
    parser.add_argument("--league", type=str, default="WNBA", help="League (default: WNBA)")
    parser.add_argument("--player", type=str, default="", help="Player name (for props)")
    parser.add_argument("--book", type=str, default="manual", help="Bookmaker (default: manual)")
    parser.add_argument("--date", type=str, default=today_utc(), help="Bet date YYYY-MM-DD (default: today UTC)")
    parser.add_argument("--signal", type=str, default="MANUAL", help="Signal tag (default: MANUAL)")
    parser.add_argument("--model-version", type=str, default="manual_operator_entry_v21_9", help="Model version tag")
    parser.add_argument("--projection", type=str, default="", help="Model projection at bet time")
    parser.add_argument("--edge", type=str, default="", help="Edge at bet time")
    parser.add_argument("--confidence", type=str, default="", help="Confidence at bet time")
    parser.add_argument("--final-signal", type=str, default="", help="Final signal label")
    parser.add_argument("--suggested-units", type=str, default="", help="Suggested units (default: same as stake)")
    parser.add_argument("--actual-units", type=str, default="", help="Actual units (default: same as stake)")
    parser.add_argument("--notes", type=str, default="", help="Notes")
    parser.add_argument("--game-start", type=str, default="", help="Game start time ISO 8601 UTC")
    parser.add_argument("--signal-time", type=str, default="", help="Signal time ISO 8601 UTC")
    parser.add_argument("--entry-time-utc", type=str, default="", help="Override EntryTimeUTC (default: now)")

    args = parser.parse_args()

    # Must use --enter
    if not args.enter:
        parser.print_help()
        print("\nERROR: --enter is required to add a bet. Use --dry-run to preview.")
        return 1

    # Check tracker exists
    if not BET_TRACKER.exists():
        print(f"ERROR: {BET_TRACKER} not found.")
        return 1

    # Read existing
    with BET_TRACKER.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames)
        rows = list(reader)

    # Validate
    is_valid, errors, warnings = validate(args, rows, fieldnames)

    for w in warnings:
        print(f"WARNING: {w}")

    if not is_valid:
        print(f"VALIDATION FAILED — {len(errors)} error(s):")
        for e in errors:
            print(f"  - {e}")
        return 1

    # Generate row
    bid = next_bid(rows)
    row = build_row(args, fieldnames, bid)

    # Dry run
    if args.dry_run:
        print(f"=== DRY RUN — no changes written ===")
        print(f"Next BetID: {bid}")
        print(f"Row to append:")
        for col in fieldnames:
            val = row.get(col, "")
            if val:
                print(f"  {col}: {val}")
        print(f"\nTotal rows after append: {len(rows) + 1}")
        return 0

    # Write
    rows.append(row)
    with BET_TRACKER.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    print(f"OK: appended {bid} to bet_tracker.csv")
    print(f"  Game:      {row['Game']}")
    print(f"  Market:    {row['Market']} {row['Direction']} {row['Line']}")
    print(f"  Odds:      {row['Odds']}")
    print(f"  Stake:     {row['Stake']}")
    print(f"  EntryTime: {row['EntryTimeUTC']}")
    print(f"  Status:    {row['Status']}")
    if row["MinutesBeforeTip"]:
        print(f"  MinutesBeforeTip: {row['MinutesBeforeTip']}")
    print(f"  Total rows: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
