#!/usr/bin/env python3
"""
WNBA Edge Lab V21 — Signal Tracker Dedupe Audit (READ-ONLY)

Analyzes signal_tracker_graded.csv for duplicate/redundant rows under
four candidate dedupe keys. Writes three audit artifacts and prints a
summary. Does NOT modify any source file.

Outputs:
  wnba_outputs/signal_tracker_dedupe_audit_v21.json   — structured report
  wnba_outputs/signal_tracker_dedupe_audit_v21.csv     — per-row group labels
  wnba_outputs/signal_tracker_dedupe_audit_v21.txt     — human-readable summary
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
OUT_JSON = ROOT / "wnba_outputs" / "signal_tracker_dedupe_audit_v21.json"
OUT_CSV = ROOT / "wnba_outputs" / "signal_tracker_dedupe_audit_v21.csv"
OUT_TXT = ROOT / "wnba_outputs" / "signal_tracker_dedupe_audit_v21.txt"


def read_rows(path: Path) -> Tuple[List[str], List[Dict[str, str]]]:
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        headers = list(reader.fieldnames or [])
        rows = list(reader)
    return headers, rows


def group_by(rows: List[Dict[str, str]], key_func) -> Dict[tuple, List[int]]:
    """Return {key: [list of row indices]}."""
    groups: Dict[tuple, List[int]] = defaultdict(list)
    for idx, row in enumerate(rows):
        groups[key_func(row)].append(idx)
    return dict(groups)


def dupes_only(groups: Dict[tuple, List[int]]) -> Dict[tuple, List[int]]:
    """Return only groups with count > 1."""
    return {k: v for k, v in groups.items() if len(v) > 1}


def fmt_key(k: tuple) -> str:
    return " | ".join(str(x) for x in k)


def run() -> None:
    headers, rows = read_rows(SRC)
    n = len(rows)

    # ------------------------------------------------------------------ #
    # Define the four candidate dedupe keys
    # ------------------------------------------------------------------ #
    key_defs: List[Dict[str, Any]] = [
        {
            "id": "K1_SignalID_exact",
            "label": "K1: SignalID exact match",
            "columns": ["SignalID"],
            "key_func": lambda r: (r.get("SignalID", ""),),
        },
        {
            "id": "K2_Game_Market_Selection_Line_Date",
            "label": "K2: Game + Market + Selection + LineAtSignal + SignalDate",
            "columns": ["Game", "Market", "Selection", "LineAtSignal", "SignalDate"],
            "key_func": lambda r: (
                r.get("Game", ""),
                r.get("Market", ""),
                r.get("Selection", ""),
                r.get("LineAtSignal", ""),
                r.get("SignalDate", ""),
            ),
        },
        {
            "id": "K3_Game_Market_Selection_Line",
            "label": "K3: Game + Market + Selection + LineAtSignal (ignore date)",
            "columns": ["Game", "Market", "Selection", "LineAtSignal"],
            "key_func": lambda r: (
                r.get("Game", ""),
                r.get("Market", ""),
                r.get("Selection", ""),
                r.get("LineAtSignal", ""),
            ),
        },
        {
            "id": "K4_Game_Market_Selection",
            "label": "K4: Game + Market + Selection (ignore line)",
            "columns": ["Game", "Market", "Selection"],
            "key_func": lambda r: (
                r.get("Game", ""),
                r.get("Market", ""),
                r.get("Selection", ""),
            ),
        },
    ]

    results: List[Dict[str, Any]] = []

    for kd in key_defs:
        groups = group_by(rows, kd["key_func"])
        dups = dupes_only(groups)
        total_duped_rows = sum(len(v) for v in dups.values())
        total_groups = len(groups)
        total_dup_groups = len(dups)
        rows_that_would_drop = total_duped_rows - total_dup_groups  # keep 1 per group

        # Detail each duplicate group
        group_details: List[Dict[str, Any]] = []
        for key_tuple, indices in sorted(dups.items()):
            members = []
            for idx in indices:
                row = rows[idx]
                members.append({
                    "row_index": idx + 2,  # +2 for 1-indexed + header
                    "SignalID": row.get("SignalID", ""),
                    "RunTimestamp": row.get("RunTimestamp", ""),
                    "SignalDate": row.get("SignalDate", ""),
                    "Game": row.get("Game", ""),
                    "Market": row.get("Market", ""),
                    "Selection": row.get("Selection", ""),
                    "LineAtSignal": row.get("LineAtSignal", ""),
                    "Edge": row.get("Edge", ""),
                    "FinalSignal": row.get("FinalSignal", ""),
                    "ResultStatus": row.get("ResultStatus", ""),
                    "CLV_Points": row.get("CLV_Points", ""),
                    "ClosingLine": row.get("ClosingLine", ""),
                })
            # Recommended keep: latest RunTimestamp
            keep = max(members, key=lambda m: m["RunTimestamp"])
            drop = [m for m in members if m["SignalID"] != keep["SignalID"]]

            group_details.append({
                "key": fmt_key(key_tuple),
                "member_count": len(indices),
                "recommended_keep": keep["SignalID"],
                "recommended_drop": [d["SignalID"] for d in drop],
                "drop_count": len(drop),
                "members": members,
            })

        results.append({
            "key_id": kd["id"],
            "key_label": kd["label"],
            "key_columns": kd["columns"],
            "total_rows": n,
            "total_groups": total_groups,
            "unique_groups": total_groups - total_dup_groups,
            "duplicate_groups": total_dup_groups,
            "rows_in_duplicate_groups": total_duped_rows,
            "rows_that_would_keep": n - rows_that_would_drop,
            "rows_that_would_drop": rows_that_would_drop,
            "group_details": group_details,
        })

    # ------------------------------------------------------------------ #
    # Build JSON report
    # ------------------------------------------------------------------ #
    report: Dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_file": str(SRC),
        "source_rows": n,
        "results": results,
    }
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(report, indent=2), encoding="utf-8")

    # ------------------------------------------------------------------ #
    # Build CSV audit (per-row group membership under each key)
    # ------------------------------------------------------------------ #
    csv_headers = [
        "row_index",
        "SignalID",
        "RunTimestamp",
        "Game",
        "Market",
        "Selection",
        "LineAtSignal",
        "SignalDate",
        "Edge",
        "FinalSignal",
        "ResultStatus",
    ]
    for kd in key_defs:
        csv_headers.append(f"{kd['id']}_group_size")
        csv_headers.append(f"{kd['id']}_is_dup")
        csv_headers.append(f"{kd['id']}_recommended_action")  # KEEP or DROP

    csv_rows: List[Dict[str, str]] = []
    for idx, row in enumerate(rows):
        out: Dict[str, str] = {
            "row_index": str(idx + 2),
            "SignalID": row.get("SignalID", ""),
            "RunTimestamp": row.get("RunTimestamp", ""),
            "Game": row.get("Game", ""),
            "Market": row.get("Market", ""),
            "Selection": row.get("Selection", ""),
            "LineAtSignal": row.get("LineAtSignal", ""),
            "SignalDate": row.get("SignalDate", ""),
            "Edge": row.get("Edge", ""),
            "FinalSignal": row.get("FinalSignal", ""),
            "ResultStatus": row.get("ResultStatus", ""),
        }
        for kd in key_defs:
            kd_result = results[key_defs.index(kd)]
            key_tuple = kd["key_func"](row)
            # Find group
            group_size = 0
            is_dup = False
            action = "KEEP"
            for gd in kd_result["group_details"]:
                if gd["key"] == fmt_key(key_tuple):
                    group_size = gd["member_count"]
                    is_dup = group_size > 1
                    if is_dup:
                        # Check if this row is the recommended keep
                        if row.get("SignalID", "") != gd["recommended_keep"]:
                            action = "DROP"
                    break
            out[f"{kd['id']}_group_size"] = str(group_size)
            out[f"{kd['id']}_is_dup"] = "YES" if is_dup else "NO"
            out[f"{kd['id']}_recommended_action"] = action
        csv_rows.append(out)

    with OUT_CSV.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=csv_headers)
        writer.writeheader()
        writer.writerows(csv_rows)

    # ------------------------------------------------------------------ #
    # Build TXT human-readable summary
    # ------------------------------------------------------------------ #
    lines: List[str] = []
    lines.append("=" * 72)
    lines.append("WNBA EDGE LAB V21 — SIGNAL TRACKER DEDUPE AUDIT")
    lines.append("=" * 72)
    lines.append(f"Generated : {report['generated_at_utc']}")
    lines.append(f"Source    : {SRC}")
    lines.append(f"Rows      : {n}")
    lines.append("")

    for kd, kd_result in zip(key_defs, results):
        lines.append("-" * 72)
        lines.append(kd_result["key_label"])
        lines.append(f"  Columns : {', '.join(kd_result['key_columns'])}")
        lines.append(f"  Total groups          : {kd_result['total_groups']}")
        lines.append(f"  Unique groups         : {kd_result['unique_groups']}")
        lines.append(f"  Duplicate groups      : {kd_result['duplicate_groups']}")
        lines.append(f"  Rows in dup groups    : {kd_result['rows_in_duplicate_groups']}")
        lines.append(f"  Rows that would KEEP  : {kd_result['rows_that_would_keep']}")
        lines.append(f"  Rows that would DROP  : {kd_result['rows_that_would_drop']}")
        lines.append("")

        if kd_result["group_details"]:
            lines.append("  Duplicate groups detail:")
            for gd in kd_result["group_details"]:
                lines.append(f"  [{gd['member_count']} rows] key={gd['key']}")
                lines.append(f"    KEEP → {gd['recommended_keep']}")
                for d_sig in gd["recommended_drop"]:
                    lines.append(f"    DROP → {d_sig}")
                lines.append("")
        else:
            lines.append("  (no duplicates found under this key)")
            lines.append("")

    # Recommendation
    lines.append("=" * 72)
    lines.append("RECOMMENDATION")
    lines.append("=" * 72)
    k1 = results[0]
    k2 = results[1]
    k3 = results[2]
    k4 = results[3]

    if k1["duplicate_groups"] > 0:
        lines.append("K1 (SignalID exact): HAS duplicates. These are true identical rows.")
        lines.append("  → Dedupe by SignalID first if any exist.")
    else:
        lines.append("K1 (SignalID exact): No duplicates. Every row has a unique SignalID.")

    if k2["duplicate_groups"] > 0:
        lines.append("K2 (+Game+Market+Selection+Line+Date): Same signal fired multiple times")
        lines.append("  on the same day. This indicates a run-to-run reproducibility issue.")
    else:
        lines.append("K2 (+Game+Market+Selection+Line+Date): No duplicates. Each signal is")
        lines.append("  unique within a single date.")

    if k3["duplicate_groups"] > 0:
        lines.append(f"K3 (+Game+Market+Selection+Line, ignore date): {k3['duplicate_groups']} groups")
        lines.append(f"  ({k3['rows_that_would_drop']} rows) would be dropped. These are the same game/pick/line")
        lines.append(f"  re-evaluated on consecutive days. Recommended: dedupe by K3 keeping latest RunTimestamp.")
    else:
        lines.append("K3 (+Game+Market+Selection+Line): No cross-date duplicates.")

    if k4["duplicate_groups"] > 0:
        lines.append(f"K4 (+Game+Market+Selection, ignore line): {k4['duplicate_groups']} groups.")
        lines.append(f"  Wider net — catches same game with different lines. Only use if the goal is")
        lines.append(f"  one-signal-per-game-market-selection.")
    else:
        lines.append("K4 (+Game+Market+Selection, ignoring line): No duplicates.")

    lines.append("")
    lines.append("SUGGESTED KEY: K3 (Game + Market + Selection + LineAtSignal)")
    lines.append("  Rationale: Same game/pick/line on consecutive days is the same model thesis.")
    lines.append("  The later RunTimestamp has more up-to-date closing line data.")
    lines.append(f"  Impact: {n} → {k3['rows_that_would_keep']} rows ({k3['rows_that_would_drop']} dropped)")
    lines.append("")
    lines.append("=" * 72)

    OUT_TXT.write_text("\n".join(lines), encoding="utf-8")

    # ------------------------------------------------------------------ #
    # Print summary to stdout
    # ------------------------------------------------------------------ #
    print("\n".join(lines))
    print(f"\nAudit artifacts written:")
    print(f"  JSON : {OUT_JSON}")
    print(f"  CSV  : {OUT_CSV}")
    print(f"  TXT  : {OUT_TXT}")


if __name__ == "__main__":
    run()
