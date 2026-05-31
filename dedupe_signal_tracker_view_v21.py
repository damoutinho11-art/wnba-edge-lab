#!/usr/bin/env python3
"""
WNBA Edge Lab V21 — Signal Tracker Deduped View (NON-DESTRUCTIVE)

Reads signal_tracker_graded.csv, deduplicates by
  Game + Market + Selection + LineAtSignal
keeping the row with the latest RunTimestamp per group.

Writes:
  wnba_outputs/signal_tracker_graded_deduped_v21.csv
  wnba_outputs/signal_tracker_graded_deduped_summary_v21.json

Does NOT modify the source file.
"""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "wnba_outputs" / "signal_tracker_graded.csv"
OUT_CSV = ROOT / "wnba_outputs" / "signal_tracker_graded_deduped_v21.csv"
OUT_JSON = ROOT / "wnba_outputs" / "signal_tracker_graded_deduped_summary_v21.json"


def read_rows(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = list(reader.fieldnames or [])
        rows = list(reader)
    return headers, rows


def dedupe(
    rows: List[Dict[str, str]],
) -> Tuple[List[Dict[str, str]], List[Dict[str, str]], List[Dict[str, Any]]]:
    """
    Deduplicate by (Game, Market, Selection, LineAtSignal).
    Keep latest RunTimestamp per group.
    Returns (kept_rows, dropped_rows, group_summaries).
    """
    groups: Dict[tuple, List[int]] = defaultdict(list)
    for idx, row in enumerate(rows):
        key = (
            row.get("Game", ""),
            row.get("Market", ""),
            row.get("Selection", ""),
            row.get("LineAtSignal", ""),
        )
        groups[key].append(idx)

    kept: List[Dict[str, str]] = []
    dropped: List[Dict[str, str]] = []
    summaries: List[Dict[Any, Any]] = []

    for key, indices in sorted(groups.items()):
        members = [rows[i] for i in indices]
        # Tiebreak: latest RunTimestamp
        members.sort(key=lambda m: m.get("RunTimestamp", ""))
        keep = members[-1]
        drop_list = members[:-1]
        kept.append(keep)
        dropped.extend(drop_list)
        summaries.append({
            "key": " | ".join(key),
            "total_members": len(members),
            "kept_signal_id": keep.get("SignalID", ""),
            "kept_run_timestamp": keep.get("RunTimestamp", ""),
            "dropped": [
                {
                    "signal_id": d.get("SignalID", ""),
                    "run_timestamp": d.get("RunTimestamp", ""),
                    "signal_date": d.get("SignalDate", ""),
                }
                for d in drop_list
            ],
        })

    # Sort kept rows to match original file order (by row index)
    return kept, dropped, summaries


def run() -> None:
    headers, rows = read_rows(src := SRC)
    n_raw = len(rows)

    kept, dropped, summaries = dedupe(rows)

    # ---- Write deduped CSV ----
    OUT_CSV.parent.mkdir(parents=True, exist_ok=True)
    with OUT_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        for row in kept:
            writer.writerow(row)

    # ---- Write summary JSON ----
    summary: Dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_file": str(SRC),
        "source_rows": n_raw,
        "deduped_rows": len(kept),
        "dropped_rows": len(dropped),
        "dedupe_key": ["Game", "Market", "Selection", "LineAtSignal"],
        "tiebreaker": "latest RunTimestamp",
        "duplicate_groups": sum(1 for s in summaries if s["total_members"] > 1),
        "groups": summaries,
        "dropped_signal_ids": [d.get("SignalID", "") for d in dropped],
    }
    OUT_JSON.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    # ---- Print report ----
    print("=" * 60)
    print(" SIGNAL TRACKER DEDUED VIEW — RESULTS")
    print("=" * 60)
    print(f" Source          : {SRC}")
    print(f" Raw rows        : {n_raw}")
    print(f" Deduped rows    : {len(kept)}")
    print(f" Dropped rows    : {len(dropped)}")
    print(f" Duplicate groups: {summary['duplicate_groups']}")
    print()
    if dropped:
        print(" Dropped SignalIDs:")
        for d in dropped:
            print(f"   {d.get('SignalID', '')}")
    print()
    print(f" Deduped CSV  : {OUT_CSV}")
    print(f" Summary JSON : {OUT_JSON}")
    print("=" * 60)

    # ---- Validation ----
    print()
    print("VALIDATION")

    # 1. Raw rows
    raw_check = n_raw == 35
    print(f"  1. Raw rows = {n_raw}  {'PASS' if raw_check else 'FAIL (expected 35)'}")

    # 2. Deduped rows
    deduped_check = len(kept) == 28
    print(f"  2. Deduped rows = {len(kept)}  {'PASS' if deduped_check else 'FAIL (expected 28)'}")

    # 3. K3 duplicates in deduped file = 0
    key_counts: Dict[tuple, int] = defaultdict(int)
    for row in kept:
        k = (row.get("Game",""), row.get("Market",""), row.get("Selection",""), row.get("LineAtSignal",""))
        key_counts[k] += 1
    k3_dupes = sum(1 for v in key_counts.values() if v > 1)
    k3_check = k3_dupes == 0
    print(f"  3. K3 duplicates in deduped = {k3_dupes}  {'PASS' if k3_check else 'FAIL'}")

    # 4. All dropped are older RunTimestamps
    all_older = True
    for s in summaries:
        if s["total_members"] <= 1:
            continue
        keep_ts = s["kept_run_timestamp"]
        for d in s["dropped"]:
            if d["run_timestamp"] > keep_ts:
                all_older = False
                break
    print(f"  4. All dropped are older timestamps: {'PASS' if all_older else 'FAIL'}")

    all_pass = raw_check and deduped_check and k3_check and all_older
    print()
    print(f"  OVERALL: {'ALL CHECKS PASSED' if all_pass else 'SOME CHECKS FAILED'}")


if __name__ == "__main__":
    run()
