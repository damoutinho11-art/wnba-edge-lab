#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WNBA Edge Lab V21 — Manual Closing Line Entry Workflow

Purpose:
    Operator manually enters closing lines from bookmaker screenshots
    while the Odds API key is expired/quota-exhausted.

    This enables CLV calculation for signals that lack closing line data.

Safety:
    - Read-only on signal_tracker_graded.csv
    - Creates/append-only to manual_closing_lines_v21.csv
    - Validates SignalID exists before accepting entry
    - Prevents duplicate SignalID entries unless --overwrite is passed
    - No changes to model, staking, thresholds, or bet_tracker

Usage:
    python manual_closing_line_entry_v21.py --summary
    python manual_closing_line_entry_v21.py --list-missing [--limit N]
    python manual_closing_line_entry_v21.py --enter
    python manual_closing_line_entry_v21.py --enter --signalid "..." --closingline 169.5 --book BetOnline
    python manual_closing_line_entry_v21.py --delete --signalid "..."
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "wnba_outputs"

SIGNAL_TRACKER = OUT / "signal_tracker_graded.csv"
DEDUPED_TRACKER = OUT / "signal_tracker_graded_deduped_v21.csv"
CLOSING_LINES = OUT / "manual_closing_lines_v21.csv"
SUMMARY_JSON = OUT / "manual_closing_lines_summary_v21.json"

REQUIRED_COLUMNS = [
    "SignalID", "Game", "Market", "Selection",
    "LineAtSignal", "ClosingLine", "ClosingBook",
    "ClosingTimeUTC", "Source", "EnteredAtUTC", "Notes",
]


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_signals_deduped() -> List[Dict[str, str]]:
    """Read the deduped signal tracker — authoritative signal list."""
    if not DEDUPED_TRACKER.exists():
        return []
    return read_csv(DEDUPED_TRACKER)


def read_signals_raw() -> List[Dict[str, str]]:
    """Read the raw signal tracker."""
    if not SIGNAL_TRACKER.exists():
        return []
    return read_csv(SIGNAL_TRACKER)


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig", errors="ignore") as f:
        return list(csv.DictReader(f))


def read_closing_lines() -> List[Dict[str, str]]:
    return read_csv(CLOSING_LINES)


def write_closing_lines(rows: List[Dict[str, str]]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with CLOSING_LINES.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=REQUIRED_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def append_closing_line(row: Dict[str, str]) -> None:
    exists = CLOSING_LINES.exists()
    OUT.mkdir(parents=True, exist_ok=True)
    with CLOSING_LINES.open("a", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=REQUIRED_COLUMNS, extrasaction="ignore")
        if not exists:
            writer.writeheader()
        writer.writerow(row)


def load_closing_line_map() -> Dict[str, Dict[str, str]]:
    """Return {SignalID: row} for existing closing lines."""
    return {r.get("SignalID", ""): r for r in read_closing_lines() if r.get("SignalID")}


def cmd_summary(signals: List[Dict[str, str]], closing_map: Dict[str, Dict[str, str]]) -> None:
    total = len(signals)
    have_closing = sum(1 for s in signals if s.get("SignalID", "") in closing_map)
    missing = total - have_closing

    # Count by ResultStatus
    status_counts: Dict[str, int] = {}
    for s in signals:
        st = s.get("ResultStatus", "UNKNOWN").strip().upper() or "UNKNOWN"
        status_counts[st] = status_counts.get(st, 0) + 1

    # Count by Game (unique games)
    games = set()
    for s in signals:
        g = s.get("Game", "").strip()
        if g:
            games.add(g)

    summary = {
        "generated_at_utc": now_iso(),
        "signal_source": str(DEDUPED_TRACKER),
        "total_signals": total,
        "signals_with_closing_line": have_closing,
        "signals_missing_closing_line": missing,
        "closing_line_coverage_pct": round(have_closing / total * 100, 1) if total else 0,
        "unique_games": len(games),
        "result_status_counts": dict(sorted(status_counts.items(), key=lambda x: -x[1])),
        "closing_line_file": str(CLOSING_LINES),
        "closing_line_entries": len(closing_map),
    }

    SUMMARY_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("=" * 60)
    print(" MANUAL CLOSING LINE ENTRY — SUMMARY")
    print("=" * 60)
    print(f" Signals (deduped)              : {total}")
    print(f" With closing line              : {have_closing}")
    print(f" Missing closing line           : {missing}")
    print(f" Coverage                       : {summary['closing_line_coverage_pct']}%")
    print(f" Unique games                   : {len(games)}")
    print()
    print(" Result status breakdown:")
    for status, cnt in summary["result_status_counts"].items():
        print(f"   {status:12s} : {cnt}")
    print()
    print(f" Closing line file              : {CLOSING_LINES}")
    print(f" Summary JSON                   : {SUMMARY_JSON}")
    print("=" * 60)


def cmd_list_missing(signals: List[Dict[str, str]], closing_map: Dict[str, Dict[str, str]],
                     limit: int = 10) -> None:
    missing_signals = [s for s in signals if s.get("SignalID", "") not in closing_map]
    print(f"Signals missing closing line: {len(missing_signals)} of {len(signals)}")
    print(f"Showing first {min(limit, len(missing_signals))}:\n")

    for s in missing_signals[:limit]:
        sig = s.get("SignalID", "")
        game = s.get("Game", "")
        market = s.get("Market", "")
        sel = s.get("Selection", "")
        line = s.get("LineAtSignal", "")
        clv_src = s.get("CLV_Source", "")
        result = s.get("ResultStatus", "")
        print(f"  SignalID : {sig}")
        print(f"  Game     : {game}")
        print(f"  Market   : {market} · {sel}")
        print(f"  Line     : {line}")
        print(f"  CLV Src  : {clv_src  or 'NONE'}")
        print(f"  Result   : {result}")
        print()

    if not missing_signals:
        print("  All signals have closing line entries.")


def validate_signalid(signalid: str, signals: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    """Validate that a SignalID exists in the deduped tracker."""
    for s in signals:
        if s.get("SignalID", "") == signalid:
            return s
    return None


def cmd_enter(signals: List[Dict[str, str]], closing_map: Dict[str, Dict[str, str]],
              signalid: Optional[str] = None, closingline: Optional[str] = None,
              book: str = "manual", source: str = "operator_screenshot",
              overwrite: bool = False, closing_time: str = "", notes: str = "") -> None:

    existing_lines = list(read_closing_lines())

    # Interactive mode if no signalid provided
    if signalid is None:
        print("=== Manual Closing Line Entry ===")
        print(f"Enter 'q' at any prompt to cancel.\n")
        signalid_input = input("SignalID: ").strip()
        if signalid_input.lower() == "q":
            print("Cancelled.")
            return
        signalid = signalid_input

    sig = validate_signalid(signalid, signals)
    if sig is None:
        print(f"ERROR: SignalID '{signalid}' not found in deduped tracker ({DEDUPED_TRACKER}).")
        print("Available SignalIDs (first 5):")
        for s in signals[:5]:
            print(f"  {s.get('SignalID','')}  |  {s.get('Game','')}  |  {s.get('Market','')} {s.get('Selection','')}")
        sys.exit(1)

    # Check for existing entry
    if signalid in closing_map and not overwrite:
        existing = closing_map[signalid]
        print(f"WARNING: Closing line already exists for SignalID '{signalid}':")
        print(f"  Existing: ClosingLine={existing.get('ClosingLine','')} "
              f"Book={existing.get('ClosingBook','')} "
              f"Entered={existing.get('EnteredAtUTC','')}")
        print("Use --overwrite to replace. Exiting without changes.")
        sys.exit(1)

    # Get closing line value
    if closingline is None:
        closingline_input = input(f"ClosingLine (Signal LineAtSignal={sig.get('LineAtSignal','')}): ").strip()
        if closingline_input.lower() == "q":
            print("Cancelled.")
            return
        closingline = closingline_input

    if not closingline:
        print("ERROR: ClosingLine cannot be empty.")
        sys.exit(1)

    # Get book if not provided
    if book == "manual" and closingline is not None:
        book_input = input("ClosingBook [manual]: ").strip()
        if book_input.lower() == "q":
            print("Cancelled.")
            return
        if book_input:
            book = book_input

    # Get source
    src_input = input(f"Source [{source}]: ").strip()
    if src_input.lower() == "q":
        print("Cancelled.")
        return
    if src_input:
        source = src_input

    # Get closing time
    if not closing_time:
        time_input = input("ClosingTimeUTC (leave blank for 'unknown'): ").strip()
        if time_input.lower() == "q":
            print("Cancelled.")
            return
        closing_time = time_input if time_input else "unknown"

    # Get notes
    notes_input = input("Notes (optional): ").strip()
    if notes_input.lower() == "q":
        print("Cancelled.")
        return
    if notes_input:
        notes = notes_input

    row = {
        "SignalID": signalid,
        "Game": sig.get("Game", ""),
        "Market": sig.get("Market", ""),
        "Selection": sig.get("Selection", ""),
        "LineAtSignal": sig.get("LineAtSignal", ""),
        "ClosingLine": closingline,
        "ClosingBook": book,
        "ClosingTimeUTC": closing_time,
        "Source": source,
        "EnteredAtUTC": now_iso(),
        "Notes": notes,
    }

    if overwrite and signalid in closing_map:
        # Remove old entry
        existing_lines = [r for r in existing_lines if r.get("SignalID", "") != signalid]

    existing_lines.append(row)
    write_closing_lines(existing_lines)

    print(f"\nOK: Closing line entered for SignalID '{signalid}'")
    print(f"  LineAtSignal : {sig.get('LineAtSignal','')}")
    print(f"  ClosingLine  : {closingline}")
    print(f"  ClosingBook  : {book}")
    print(f"  Source       : {source}")
    print(f"  EnteredAtUTC : {row['EnteredAtUTC']}")

    # Immediate CLV hint
    try:
        signal_line = float(sig.get("LineAtSignal", 0) or 0)
        close_line = float(closingline)
        clv = close_line - signal_line
        clv_str = f"+{clv:.2f}" if clv > 0 else f"{clv:.2f}"
        print(f"  CLV hint     : {clv_str} pts ({'BEAT close' if clv > 0 else 'NO BEAT' if clv == 0 else 'LOST to close'})")
    except (ValueError, TypeError):
        pass


def cmd_delete(closing_map: Dict[str, Dict[str, str]], signalid: str,
               force: bool = False) -> None:
    if signalid not in closing_map:
        print(f"SignalID '{signalid}' not found in closing lines. Nothing to delete.")
        sys.exit(1)

    existing = closing_map[signalid]
    if not force:
        print(f"About to delete closing line for SignalID '{signalid}':")
        for k, v in existing.items():
            print(f"  {k}: {v}")
        confirm = input("Confirm delete? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Cancelled.")
            return

    existing_lines = list(read_closing_lines())
    existing_lines = [r for r in existing_lines if r.get("SignalID", "") != signalid]
    write_closing_lines(existing_lines)
    print(f"OK: Deleted closing line for SignalID '{signalid}'.")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="WNBA Edge Lab V21 — Manual Closing Line Entry Workflow",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --summary
  %(prog)s --list-missing --limit 10
  %(prog)s --enter
  %(prog)s --enter --signalid "2026-05-28|WNBA|LAS @ WAS|Game Total|OVER|169.0|v2.4" --closingline 168.5 --book BetOnline
  %(prog)s --delete --signalid "2026-05-28|WNBA|LAS @ WAS|Game Total|OVER|169.0|v2.4"
        """,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--summary", action="store_true",
                       help="Print summary of closing line coverage")
    group.add_argument("--list-missing", action="store_true",
                       help="List signals missing closing lines")
    group.add_argument("--enter", action="store_true",
                       help="Enter a closing line (interactive or --signalid)")
    group.add_argument("--delete", action="store_true",
                       help="Delete a closing line entry")

    parser.add_argument("--signalid", type=str, default=None,
                        help="SignalID to enter/delete (non-interactive mode)")
    parser.add_argument("--closingline", type=str, default=None,
                        help="Closing line value (e.g. 169.5)")
    parser.add_argument("--book", type=str, default="manual",
                        help="Bookmaker name for closing line [default: manual]")
    parser.add_argument("--source", type=str, default="operator_screenshot",
                        help="Source of closing line data [default: operator_screenshot]")
    parser.add_argument("--closing-time", type=str, default="",
                        help="Closing time in UTC ISO format (blank = 'unknown')")
    parser.add_argument("--notes", type=str, default="",
                        help="Optional notes")
    parser.add_argument("--limit", type=int, default=10,
                        help="Limit for --list-missing [default: 10]")
    parser.add_argument("--overwrite", action="store_true",
                        help="Overwrite existing closing line entry for SignalID")
    parser.add_argument("--force", action="store_true",
                        help="Skip confirmation for --delete")

    args = parser.parse_args()

    signals = read_signals_deduped()
    if not signals:
        print(f"ERROR: No signals found in {DEDUPED_TRACKER}. Run dedupe first.")
        return 1

    closing_map = load_closing_line_map()

    if args.summary:
        cmd_summary(signals, closing_map)
    elif args.list_missing:
        cmd_list_missing(signals, closing_map, limit=args.limit)
    elif args.enter:
        cmd_enter(
            signals, closing_map,
            signalid=args.signalid,
            closingline=args.closingline,
            book=args.book,
            source=args.source,
            overwrite=args.overwrite,
            closing_time=args.closing_time,
            notes=args.notes,
        )
    elif args.delete:
        if not args.signalid:
            print("--delete requires --signalid")
            return 1
        cmd_delete(closing_map, args.signalid, force=args.force)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
