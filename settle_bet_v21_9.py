#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
WNBA Edge Lab V21.9 — Safe Bet Settlement Helper

Settle an existing OPEN bet in bet_tracker.csv.
Already-settled bets are immutable. No --force. No data loss.

Safety:
- No auto-betting.
- No formula/staking/threshold/queue changes.
- P/L always recalculated from Stake + Odds + Result.
- Notes appended, never replaced.
- Timestamped backup before every write.
- ClosingTimeUTC never invented.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parent
BET_TRACKER = ROOT / "bet_tracker.csv"

REQUIRED_COLUMNS = [
    "BetID", "Status", "Result", "P/L", "Stake", "Odds", "UpdatedAt", "Notes",
]

SETTLED_STATUSES = {"SETTLED", "WON", "LOST", "PUSH", "CANCELLED", "VOID"}
VALID_RESULTS = {"WIN", "LOSS", "PUSH"}

BACKUP_PREFIX = "bet_tracker_backup_before_settle_"


# ── Helpers ──────────────────────────────────────────────────────────────────

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def backup_name(bet_id: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"{BACKUP_PREFIX}{bet_id}_{ts}.csv"


def num(x: Any) -> Optional[float]:
    try:
        return float(str(x).strip())
    except (ValueError, TypeError):
        return None


def is_already_settled(row: Dict[str, str]) -> bool:
    status = str(row.get("Status", "")).strip().upper()
    if status in SETTLED_STATUSES:
        return True
    result = str(row.get("Result", "")).strip().upper()
    if result and result not in ("", "NAN", "NONE", "NULL"):
        return True
    pl = str(row.get("P/L", "")).strip()
    if pl and pl not in ("", "0", "0.0", "NAN", "NONE", "NULL"):
        # P/L of exactly 0.0 could be a legitimate zero, so only treat as
        # settled if the string is non-empty and non-zero.
        pl_val = num(pl)
        if pl_val is not None and pl_val != 0.0:
            return True
    actual = str(row.get("Actual", "")).strip()
    if actual and actual not in ("", "NAN", "NONE", "NULL"):
        return True
    return False


def compute_pl(result: str, stake: float, odds: float) -> float:
    r = result.upper()
    if r == "WIN":
        return round(stake * (odds - 1), 4)
    if r == "LOSS":
        return round(-stake, 4)
    if r == "PUSH":
        return 0.0
    raise ValueError(f"Invalid result: {result}")


def append_notes(existing: str, result: str, new_notes: str) -> str:
    existing = existing.strip()
    settlement_tag = f"SETTLED {result}"
    if new_notes:
        addition = f"{settlement_tag}: {new_notes}"
    else:
        addition = settlement_tag
    if existing:
        return f"{existing} | {addition}"
    return addition


def read_tracker(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        rows = list(reader)
    return fieldnames, rows


def write_tracker(path: Path, fieldnames: List[str], rows: List[Dict[str, str]]) -> None:
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def validate_csv(path: Path, fieldnames: List[str], expected_rows: int, bet_id: str) -> None:
    with path.open(newline="", encoding="utf-8-sig") as f:
        raw = f.read()
    if "\x00" in raw:
        raise RuntimeError("NULL bytes detected in written file")
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        written_fields = list(reader.fieldnames or [])
        written_rows = list(reader)
    if written_fields != fieldnames:
        raise RuntimeError(f"Field count mismatch: expected {len(fieldnames)}, got {len(written_fields)}")
    if len(written_rows) != expected_rows:
        raise RuntimeError(f"Row count mismatch: expected {expected_rows}, got {len(written_rows)}")
    found = [r for r in written_rows if r.get("BetID", "").strip().upper() == bet_id.upper()]
    if len(found) != 1:
        raise RuntimeError(f"BetID {bet_id} found {len(found)} times (expected 1)")


# ── Core logic ───────────────────────────────────────────────────────────────

def find_bet(rows: List[Dict[str, str]], bet_id: str) -> Tuple[int, Dict[str, str]]:
    """Return (index, row) for the matching BetID. Raises on miss/duplicate."""
    matches = [(i, r) for i, r in enumerate(rows)
               if r.get("BetID", "").strip().upper() == bet_id.upper()]
    if not matches:
        known = [r.get("BetID", "?") for r in rows[:10]]
        raise LookupError(
            f"BetID {bet_id} not found. Known BetIDs (first 10): {', '.join(known)}"
        )
    if len(matches) > 1:
        indices = ", ".join(str(i + 2) for i, _ in matches)  # +2 for 1-indexed + header
        raise RuntimeError(f"BetID {bet_id} duplicated at rows {indices}. Corruption.")
    return matches[0]


def build_after_row(
    row: Dict[str, str],
    result: str,
    actual: str,
    closing_line: str,
    closing_odds: str,
    closing_time_utc: str,
    clv_source: str,
    notes_addition: str,
    pl: float,
    updated_at: str,
) -> Dict[str, str]:
    new_row = dict(row)
    new_row["Status"] = "SETTLED"
    new_row["Result"] = result.upper()
    new_row["P/L"] = f"{pl:.4f}"
    new_row["UpdatedAt"] = updated_at
    if actual:
        new_row["Actual"] = actual
    if closing_line:
        new_row["ClosingLine"] = closing_line
    if closing_odds:
        new_row["ClosingOdds"] = closing_odds
    if closing_time_utc:
        new_row["ClosingTimeUTC"] = closing_time_utc
    if clv_source:
        new_row["CLV_Source"] = clv_source
    new_row["Notes"] = append_notes(row.get("Notes", ""), result.upper(), notes_addition)
    return new_row


def print_diff(before: Dict[str, str], after: Dict[str, str], fieldnames: List[str]) -> None:
    # Only show settlement-relevant fields
    show_keys = [
        "Status", "Result", "Actual", "P/L", "ClosingLine", "ClosingOdds",
        "ClosingTimeUTC", "CLV_Source", "UpdatedAt", "Notes",
    ]
    print("BEFORE:")
    for k in show_keys:
        v = before.get(k, "")
        print(f"  {k:<16} {v if v else '(empty)'}")
    print("AFTER:")
    for k in show_keys:
        v = after.get(k, "")
        if k == "P/L" and v:
            print(f"  {k:<16} {v:>10}  (recalculated)")
        else:
            print(f"  {k:<16} {v if v else '(empty)'}")


def settle(
    bet_id: str,
    result: str,
    actual: str,
    closing_line: str,
    closing_odds: str,
    closing_time_utc: str,
    clv_source: str,
    notes_addition: str,
    dry_run: bool,
    apply: bool,
    confirm: str,
    tracker_path: Path,
) -> int:
    # ── Read ──
    fieldnames, rows = read_tracker(tracker_path)

    # ── Schema validation ──
    missing = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
    if missing:
        print(f"ERROR: missing required columns: {', '.join(missing)}")
        return 1

    # ── Find bet ──
    try:
        idx, row = find_bet(rows, bet_id)
    except (LookupError, RuntimeError) as exc:
        print(f"ERROR: {exc}")
        return 1

    # ── Already settled check ──
    if is_already_settled(row):
        print(
            f"ERROR: BetID {bet_id} already settled: "
            f"Status={row.get('Status', '')} Result={row.get('Result', '')}. "
            f"No modification permitted."
        )
        return 1

    # ── Validate stake/odds ──
    stake = num(row.get("Stake"))
    if stake is None or stake <= 0:
        print(f"ERROR: Stake '{row.get('Stake')}' is not numeric or <= 0")
        return 1
    odds = num(row.get("Odds"))
    if odds is None or odds <= 1.0:
        print(f"ERROR: Odds '{row.get('Odds')}' is not numeric or <= 1.0")
        return 1

    # ── Compute P/L ──
    pl = compute_pl(result, stake, odds)

    # ── Build after row ──
    updated_at = now_iso()
    after_row = build_after_row(
        row, result, actual, closing_line, closing_odds,
        closing_time_utc, clv_source, notes_addition, pl, updated_at,
    )

    # ── Print diff ──
    if dry_run:
        print("=== DRY RUN — no changes written ===")
    else:
        print("=== SETTLEMENT ===")
    print()
    print(f"BetID:    {bet_id}")
    print(f"Game:     {row.get('Game', '')}")
    print(f"Market:   {row.get('Market', '')} {row.get('Direction', '')} {row.get('Line', '')}")
    print(f"Stake:    {stake:.4f}  Odds: {odds}")
    print()
    print_diff(row, after_row, fieldnames)

    if dry_run:
        print()
        print("DRY RUN — no changes written. No backup created.")
        print("Run with --apply --confirm-settlement YES to execute.")
        return 0

    # ── Apply path ──
    if not apply:
        print()
        print("ERROR: --apply is required to write. Use --dry-run to preview.")
        return 1

    if confirm != "YES":
        print()
        print("ERROR: --apply requires --confirm-settlement YES")
        return 1

    # ── Backup ──
    backup_path = tracker_path.parent / backup_name(bet_id)
    try:
        shutil.copy2(tracker_path, backup_path)
    except OSError as exc:
        print(f"ERROR: backup creation failed: {exc}")
        return 1
    print()
    print(f"Backup: {backup_path.name}")

    # ── Write ──
    rows[idx] = after_row
    try:
        write_tracker(tracker_path, fieldnames, rows)
    except OSError as exc:
        print(f"ERROR: write failed: {exc}")
        print(f"Restore from backup: {backup_path}")
        return 1

    # ── Validate ──
    try:
        validate_csv(tracker_path, fieldnames, len(rows), bet_id)
    except RuntimeError as exc:
        print(f"VALIDATION FAILED: {exc}")
        print(f"Restore from backup: {backup_path}")
        return 1

    print(f"OK: {bet_id} settled as {result.upper()} | P/L: {pl:.4f} | Rows: {len(rows)}")
    print("VALIDATION OK")
    print()
    print("Next: py bet_timing_clv_audit_v21_9.py")
    return 0


# ── CLI ──────────────────────────────────────────────────────────────────────

def main() -> int:
    parser = argparse.ArgumentParser(
        description="WNBA Edge Lab V21.9 — Safe Bet Settlement Helper",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--bet-id", required=True, help="BetID to settle, e.g. BET-00045")
    parser.add_argument(
        "--result", required=True, choices=["WIN", "LOSS", "PUSH", "win", "loss", "push"],
        help="Bet result",
    )
    parser.add_argument("--actual", default="", help="Final score/stat, e.g. '172' or 'CON 84, LAS 81'")
    parser.add_argument("--closing-line", default="", help="Market line at settlement")
    parser.add_argument("--closing-odds", default="", help="Odds at settlement")
    parser.add_argument(
        "--closing-time-utc", default="",
        help="Market closing time ISO 8601 UTC. Only written if provided. Never invented.",
    )
    parser.add_argument(
        "--clv-source", default="manual_settlement",
        help="CLV provenance tag (default: manual_settlement)",
    )
    parser.add_argument("--notes", default="", help="Settlement note appended to existing Notes")
    parser.add_argument("--dry-run", action="store_true", help="Show diff without writing")
    parser.add_argument("--apply", action="store_true", help="Write settlement (requires --confirm-settlement YES)")
    parser.add_argument(
        "--confirm-settlement", default="",
        help="Must be YES to proceed with --apply",
    )
    parser.add_argument(
        "--tracker", default=None,
        help=argparse.SUPPRESS,  # Internal/test use only. Overrides bet_tracker.csv path.
    )

    args = parser.parse_args()

    if not args.dry_run and not args.apply:
        parser.print_help()
        print()
        print("ERROR: specify --dry-run or --apply")
        return 1

    tracker_path = Path(args.tracker) if args.tracker else BET_TRACKER

    return settle(
        bet_id=args.bet_id,
        result=args.result.upper(),
        actual=args.actual,
        closing_line=args.closing_line,
        closing_odds=args.closing_odds,
        closing_time_utc=args.closing_time_utc,
        clv_source=args.clv_source,
        notes_addition=args.notes,
        dry_run=args.dry_run,
        apply=args.apply,
        confirm=args.confirm_settlement,
        tracker_path=tracker_path,
    )


if __name__ == "__main__":
    raise SystemExit(main())
