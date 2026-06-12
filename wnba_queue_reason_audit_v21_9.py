#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WNBA Edge Lab — Advisory Queue Reason Audit V21.9

Read-only audit explaining exactly why each advisory row is ACTIONABLE or HIDDEN.
No writes, no formula changes, no betting, no auto-execution.
"""

import csv
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "wnba_outputs"
HERMES_ADVISORY = OUT / "hermes_advisory_queue_v21.csv"

# Hidden reason classification
HIDDEN_REASONS = {
    "HIDDEN_STALE",
    "HIDDEN_NO_LINE",
    "HIDDEN_NO_SCHEDULE",
    "HIDDEN_INVALID",
    "HIDDEN_LABEL",
    "SCHEDULE_UNVERIFIED_TODAY",
    "SCHEDULE_UNVERIFIED_FUTURE",
    "UNKNOWN",
}


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    try:
        with path.open(newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def classify_hidden_reason(row: Dict[str, str]) -> str:
    """Determine the primary hidden reason for a row."""
    # Check queue_actionability first
    actionability = str(row.get("queue_actionability", "")).strip().upper()
    if actionability and actionability != "ACTIONABLE":
        return actionability

    # Fallback: infer from risk_flags and other fields
    risk_flags = str(row.get("risk_flags", "")).upper()
    if "NO_LINE" in risk_flags:
        return "NO_LINE"

    stale = str(row.get("is_stale", "")).strip().lower()
    if stale in ("true", "1", "yes"):
        return "HIDDEN_STALE"

    label = str(row.get("advisory_label", "")).upper()
    if label not in ("LEAN_SUPPORT", "MANUAL_REVIEW"):
        return "HIDDEN_LABEL"

    line = str(row.get("line", "")).strip()
    if not line or line.lower() in ("", "nan", "none", "null"):
        return "NO_LINE"

    return "UNKNOWN"


def audit_advisory_queue(rows: List[Dict[str, str]]) -> Dict[str, Any]:
    """Audit the advisory queue and return detailed per-row analysis."""
    if not rows:
        return {
            "present": False,
            "error": "Advisory queue missing or empty",
        }

    results = {
        "present": True,
        "total_rows": len(rows),
        "actionable_count": 0,
        "hidden_count": 0,
        "reason_counts": {},
        "no_line_count": 0,
        "stale_count": 0,
        "rows": [],
    }

    for idx, row in enumerate(rows):
        actionability = str(row.get("queue_actionability", "")).strip().upper()
        is_actionable = actionability == "ACTIONABLE"

        # Determine primary hidden reason
        if is_actionable:
            primary_reason = "ACTIONABLE"
        else:
            primary_reason = classify_hidden_reason(row)

        # Count NO_LINE and STALE
        risk_flags = str(row.get("risk_flags", "")).upper()
        has_no_line = "NO_LINE" in risk_flags
        stale = str(row.get("is_stale", "")).strip().lower()
        is_stale = stale in ("true", "1", "yes")

        if has_no_line:
            results["no_line_count"] += 1
        if is_stale:
            results["stale_count"] += 1

        # Build game/market identifier
        game = row.get("game", "").strip()
        side = row.get("side", "").strip()
        line = row.get("line", "").strip()
        market = row.get("market", "").strip() or side

        # Edge/model fields
        edge = row.get("edge", "").strip()
        advisory_score = row.get("advisory_score", "").strip()
        advisory_label = row.get("advisory_label", "").strip()
        units = row.get("units", "").strip()

        # Timestamps
        created_at = row.get("created_at_utc", "").strip()
        game_start = row.get("game_start_utc", "").strip()
        game_date = row.get("game_date", "").strip()
        freshness_reason = row.get("freshness_reason", "").strip()
        signal_age_hours = row.get("signal_age_hours", "").strip()

        row_data = {
            "index": idx + 1,
            "game": game if game else "n/a",
            "market": market if market else "n/a",
            "side": side if side else "n/a",
            "line": line if line else "n/a",
            "status": "ACTIONABLE" if is_actionable else "HIDDEN",
            "primary_reason": primary_reason,
            "line_present": "YES" if line and line.lower() not in ("", "nan", "none", "null") else "NO",
            "no_line_flag": "YES" if has_no_line else "NO",
            "stale_flag": "YES" if is_stale else "NO",
            "created_at_utc": created_at if created_at else "n/a",
            "game_start_utc": game_start if game_start else "n/a",
            "game_date": game_date if game_date else "n/a",
            "freshness_reason": freshness_reason if freshness_reason else "n/a",
            "signal_age_hours": signal_age_hours if signal_age_hours else "n/a",
        }

        # Add edge/model info if present
        if edge:
            row_data["edge"] = edge
        if advisory_score:
            row_data["advisory_score"] = advisory_score
        if advisory_label:
            row_data["advisory_label"] = advisory_label
        if units:
            row_data["units"] = units

        results["rows"].append(row_data)

        if is_actionable:
            results["actionable_count"] += 1
        else:
            results["hidden_count"] += 1
            results["reason_counts"][primary_reason] = results["reason_counts"].get(primary_reason, 0) + 1

    return results


def print_audit(audit: Dict[str, Any], output_path: Path = None) -> str:
    """Format and print the audit report."""
    lines = []
    lines.append("=" * 70)
    lines.append("WNBA EDGE LAB — ADVISORY QUEUE REASON AUDIT V21.9")
    lines.append("=" * 70)
    lines.append(f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append(f"Source: {HERMES_ADVISORY}")
    lines.append("")

    if not audit.get("present"):
        lines.append("❌ QUEUE AUDIT BLOCKED — No advisory queue found")
        lines.append("")
        report = "\n".join(lines)
        print(report)
        return report

    # Summary
    lines.append("📊 SUMMARY")
    lines.append(f"  Total rows:          {audit['total_rows']}")
    lines.append(f"  ACTIONABLE:          {audit['actionable_count']}")
    lines.append(f"  HIDDEN:              {audit['hidden_count']}")
    lines.append(f"  NO_LINE flags:       {audit['no_line_count']}")
    lines.append(f"  HIDDEN_STALE flags:  {audit['stale_count']}")
    lines.append("")

    # Reason breakdown
    if audit.get("reason_counts"):
        lines.append("🔍 HIDDEN REASON BREAKDOWN")
        for reason, count in sorted(audit["reason_counts"].items(), key=lambda x: -x[1]):
            lines.append(f"  {reason}: {count}")
        lines.append("")

    # Per-row detail
    lines.append("📋 PER-ROW DETAIL")
    lines.append("-" * 70)
    for row in audit["rows"]:
        status_icon = "✅" if row["status"] == "ACTIONABLE" else "❌"
        lines.append(f"  Row {row['index']:2d} | {status_icon} {row['status']:10s} | {row['primary_reason']}")
        lines.append(f"      Game:     {row['game']}")
        if row['market'] != "n/a" and row['market'] != row['game']:
            lines.append(f"      Market:   {row['market']} {row['side']} {row['line']}")
        else:
            lines.append(f"      Side/Line: {row['side']} {row['line']}")
        lines.append(f"      Line present: {row['line_present']} | NO_LINE flag: {row['no_line_flag']} | Stale: {row['stale_flag']}")
        lines.append(f"      Created: {row['created_at_utc']} | Game Start: {row['game_start_utc']} | Game Date: {row['game_date']}")
        if "edge" in row:
            lines.append(f"      Edge: {row['edge']} | Score: {row.get('advisory_score', 'n/a')} | Label: {row.get('advisory_label', 'n/a')} | Units: {row.get('units', 'n/a')}")
        lines.append(f"      Freshness: {row['freshness_reason']} | Age: {row['signal_age_hours']}h")
        lines.append("")

    # Final verdict
    if audit["actionable_count"] == 0 and audit["hidden_count"] > 0:
        verdict = "QUEUE_AUDIT_NO_ACTIONABLE_ROWS"
        icon = "⚠️"
    elif audit["actionable_count"] > 0:
        verdict = "QUEUE_AUDIT_ACTIONABLE_ROWS_PRESENT"
        icon = "✅"
    else:
        verdict = "QUEUE_AUDIT_BLOCKED_NO_QUEUE"
        icon = "🔴"

    lines.append("🏁 FINAL VERDICT")
    lines.append(f"  {icon} {verdict}")
    lines.append("")

    # Safety footer
    lines.append("🔒 SAFETY FOOTER")
    lines.append("  • Manual approval required")
    lines.append("  • No auto-betting")
    lines.append("  • No formula changes")
    lines.append("  • No staking changes")
    lines.append("  • No threshold changes")
    lines.append("")

    lines.append("=" * 70)

    report = "\n".join(lines)
    print(report)

    if output_path:
        try:
            output_path.write_text(report, encoding="utf-8")
            print(f"\n📄 Report written to: {output_path}")
        except Exception as e:
            print(f"\n⚠️ Failed to write report: {e}")

    return report


def main() -> int:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="WNBA Advisory Queue Reason Audit V21.9")
    parser.add_argument("--output", "-o", type=Path, help="Write report to file (optional)")
    parser.add_argument("--source", type=Path, default=HERMES_ADVISORY, help="Advisory queue CSV path")
    args = parser.parse_args()

    rows = read_csv(args.source)
    audit = audit_advisory_queue(rows)
    print_audit(audit, args.output)

    # Exit code based on verdict
    if audit.get("actionable_count", 0) > 0:
        return 0
    elif audit.get("hidden_count", 0) > 0:
        return 1  # No actionable rows but queue exists
    else:
        return 2  # No queue


if __name__ == "__main__":
    sys.exit(main())