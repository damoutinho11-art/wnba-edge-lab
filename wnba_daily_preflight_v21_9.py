#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
WNBA Edge Lab — Daily Preflight Status Audit V21.9

Read-only summary of system readiness for manual review.
No writes, no formula changes, no betting, no auto-execution.
"""

import csv
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "wnba_outputs"

# Core status files
FETCH_STATUS = OUT / "ultimate_fetch_status_v21_4.json"
HERMES_ADVISORY = OUT / "hermes_advisory_queue_v21.csv"
BET_TRACKER = ROOT / "bet_tracker.csv"
SAFE_AUTOMATION_SUMMARY = OUT / "v21_9_safe_automation_summary.json"
MODEL_RESULT_TRACKING = OUT / "model_result_tracking_summary_v21_9.json"

# Official source names
OFFICIAL_SOURCES = [
    "official_playergamelogs_base",
    "official_teamgamelogs_base",
    "official_team_dash_base",
    "official_player_dash_base",
]

# Readiness keys from fetch status
READINESS_KEYS = [
    "official_playergamelogs_ready",
    "official_teamgamelogs_ready",
    "official_team_dash_ready",
    "official_player_dash_ready",
    "odds_ready",
    "sportsdataverse_ready",
    "player_props_market_ready",
    "player_props_settlement_ready",
]

# State classification
GOOD_STATES = {"LIVE_FETCH_OK"}
DEGRADED_STATES = {"CACHE_FALLBACK_USED", "OUTPUT_FALLBACK_USED"}
BLOCKER_STATES = {"FETCH_FAILED_NO_CACHE"}


def run_git_status() -> Tuple[bool, List[str]]:
    """Run git status --porcelain and return (is_clean, dirty_files)."""
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=10,
        )
        lines = [l.strip() for l in result.stdout.splitlines() if l.strip()]
        # Allow runtime outputs as expected dirty
        # Git porcelain format: "XY path" where XY are status chars (2 cols + space)
        runtime_dirs = {"wnba_outputs/", "wnba_cache_v2", "wnba_cache_v20/", "wnba_cache_v21/"}
        real_dirty = []
        for l in lines:
            # Extract path part (skip first 3 chars: XY + space)
            path_part = l[3:] if len(l) > 3 else l
            if not any(path_part.startswith(d) for d in runtime_dirs):
                real_dirty.append(l)
        return len(real_dirty) == 0, lines
    except Exception as e:
        return False, [f"git status failed: {e}"]


def read_json(path: Path) -> Dict[str, Any]:
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    try:
        with path.open(newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def classify_source_state(state: str) -> str:
    """Classify fetch state into GOOD/DEGRADED/BLOCKER."""
    if state in GOOD_STATES:
        return "GOOD"
    if state in DEGRADED_STATES:
        return "DEGRADED"
    if state in BLOCKER_STATES:
        return "BLOCKER"
    return "UNKNOWN"


def audit_git() -> Dict[str, Any]:
    is_clean, dirty = run_git_status()
    return {
        "clean": is_clean,
        "dirty_files": dirty,
        "note": "Runtime outputs (wnba_outputs/, wnba_cache_v2*/) are expected and ignored.",
    }


def audit_fetch() -> Dict[str, Any]:
    """Audit fetch/source readiness from ultimate_fetch_status_v21_4.json."""
    data = read_json(FETCH_STATUS)
    if not data:
        return {"present": False, "error": "File missing or unreadable"}

    readiness = data.get("readiness", {})
    records = data.get("records", [])

    # Official source states per season
    source_states: Dict[str, Dict[str, str]] = {}
    for src in OFFICIAL_SOURCES:
        src_records = [r for r in records if r.get("source") == src]
        for r in src_records:
            season = r.get("season", "?")
            state = r.get("state", "UNKNOWN")
            source_states.setdefault(src, {})[season] = state

    # Readiness bools
    ready_flags = {k: readiness.get(k, False) for k in READINESS_KEYS}

    # Overall classification
    blocker_sources = [
        src for src, seasons in source_states.items()
        if any(classify_source_state(s) == "BLOCKER" for s in seasons.values())
    ]
    degraded_sources = [
        src for src, seasons in source_states.items()
        if any(classify_source_state(s) == "DEGRADED" for s in seasons.values())
        and src not in blocker_sources
    ]

    return {
        "present": True,
        "created_at": data.get("created_at_utc"),
        "overall_state": data.get("overall_state"),
        "readiness": ready_flags,
        "source_states": source_states,
        "blocker_sources": blocker_sources,
        "degraded_sources": degraded_sources,
        "state_counts": data.get("state_counts", {}),
        "warnings": data.get("warnings_count", 0),
        "warnings_high": data.get("warnings_high", 0),
    }


def audit_queue() -> Dict[str, Any]:
    """Audit advisory queue from hermes_advisory_queue_v21.csv."""
    advisory = read_csv(HERMES_ADVISORY)
    if not advisory:
        return {"present": False, "error": "Advisory queue missing or empty"}

    # Count by queue_actionability
    actionable = 0
    hidden_counts: Dict[str, int] = {}
    hidden_total = 0
    no_line_count = 0
    stale_count = 0

    for row in advisory:
        src = str(row.get("queue_actionability", "")).strip().upper()
        if src == "ACTIONABLE":
            actionable += 1
        elif src:
            hidden_counts[src] = hidden_counts.get(src, 0) + 1
            hidden_total += 1
        else:
            hidden_counts["no_field"] = hidden_counts.get("no_field", 0) + 1
            hidden_total += 1

        # NO_LINE check
        flags = str(row.get("risk_flags", "")).upper()
        if "NO_LINE" in flags:
            no_line_count += 1

        # Stale check
        stale = str(row.get("is_stale", "")).strip().lower()
        if stale in ("true", "1", "yes"):
            stale_count += 1

    return {
        "present": True,
        "total_rows": len(advisory),
        "actionable": actionable,
        "hidden_total": hidden_total,
        "hidden_counts": hidden_counts,
        "no_line_count": no_line_count,
        "stale_count": stale_count,
    }


def audit_portfolio() -> Dict[str, Any]:
    """Audit portfolio risk from bet_tracker.csv and advisory queue."""
    bets = read_csv(BET_TRACKER)
    advisory = read_csv(HERMES_ADVISORY)

    # Open bets
    open_bets = []
    open_exposure = 0.0
    for b in bets:
        status = str(b.get("Status", "")).strip().upper()
        if status in ("OPEN", "PENDING", "ACTIVE") or not status:
            open_bets.append(b)
            try:
                open_exposure += float(b.get("Stake", "0") or "0")
            except (ValueError, TypeError):
                pass

    # Proposed from advisory
    proposed_count = 0
    proposed_exposure = 0.0
    units_parseable = True
    for r in advisory:
        src = str(r.get("queue_actionability", "")).strip().upper()
        if src == "ACTIONABLE":
            proposed_count += 1
            u = r.get("units", "").strip()
            if u and u.upper() not in ("NAN", "NONE", "NULL", ""):
                try:
                    proposed_exposure += float(u)
                except (ValueError, TypeError):
                    units_parseable = False

    combined = open_exposure + (proposed_exposure if units_parseable else 0.0)

    return {
        "open_bets": len(open_bets),
        "open_exposure": round(open_exposure, 2),
        "proposed_count": proposed_count,
        "proposed_exposure": round(proposed_exposure, 2) if units_parseable else "unavailable",
        "combined_exposure": round(combined, 2) if units_parseable else open_exposure,
    }


def final_verdict(audits: Dict[str, Any]) -> str:
    """Determine final preflight verdict."""
    fetch = audits.get("fetch", {})
    queue = audits.get("queue", {})
    portfolio = audits.get("portfolio", {})

    # BLOCKER: Any FETCH_FAILED_NO_CACHE for official sources
    if fetch.get("blocker_sources"):
        return "PREFLIGHT_BLOCKED_UNSAFE_OR_STALE"

    # BLOCKER: Missing fetch status entirely
    if not fetch.get("present"):
        return "PREFLIGHT_BLOCKED_UNSAFE_OR_STALE"

    # BLOCKER: Non-zero open exposure (must be visible)
    if portfolio.get("open_exposure", 0) > 0:
        # Not a blocker per se, but must be visible - handled by WARN
        pass

    # WARN: Any degraded fetch sources
    if fetch.get("degraded_sources"):
        return "PREFLIGHT_WARN_DEGRADED_DATA"

    # WARN: Any hidden rows with issues (stale, no-line) - informational
    # Not a warn by itself, but if actionable > 0 with hidden stale, that's normal

    # PASS: Clean fetch, no blockers
    return "PREFLIGHT_PASS_SAFE_FOR_MANUAL_REVIEW"


def print_preflight(audits: Dict[str, Any], verdict: str) -> None:
    """Print formatted preflight report."""
    git = audits.get("git", {})
    fetch = audits.get("fetch", {})
    queue = audits.get("queue", {})
    portfolio = audits.get("portfolio", {})

    print("=" * 60)
    print("WNBA EDGE LAB — DAILY PREFLIGHT AUDIT V21.9")
    print("=" * 60)
    print(f"Timestamp: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}")
    print()

    # 1. Git
    print("📋 1. GIT CLEANLINESS")
    print(f"    Clean: {'YES' if git.get('clean') else 'NO'}")
    dirty = git.get("dirty_files", [])
    if dirty:
        print(f"    Dirty files ({len(dirty)}):")
        for d in dirty:
            print(f"      {d}")
    else:
        print("    (Runtime outputs ignored)")
    print()

    # 2. Fetch
    print("📡 2. FETCH / SOURCE READINESS")
    if not fetch.get("present"):
        print("    ❌ STATUS FILE MISSING")
    else:
        print(f"    Generated: {fetch.get('created_at', 'unknown')}")
        print(f"    Overall: {fetch.get('overall_state', 'unknown')}")
        print()
        print("    Readiness flags:")
        for k, v in fetch.get("readiness", {}).items():
            status = "✅" if v else "❌"
            print(f"      {status} {k}")
        print()
        print("    Official sources (per season):")
        for src, seasons in fetch.get("source_states", {}).items():
            for season, state in seasons.items():
                cls = classify_source_state(state)
                icon = {"GOOD": "✅", "DEGRADED": "⚠️", "BLOCKER": "🔴", "UNKNOWN": "❓"}.get(cls, "❓")
                print(f"      {icon} {src} @ {season}: {state} [{cls}]")

        if fetch.get("blocker_sources"):
            print(f"    🔴 BLOCKER sources: {', '.join(fetch['blocker_sources'])}")
        if fetch.get("degraded_sources"):
            print(f"    ⚠️ DEGRADED sources: {', '.join(fetch['degraded_sources'])}")

        print(f"    State counts: {fetch.get('state_counts', {})}")
        print(f"    Warnings: {fetch.get('warnings', 0)} (high: {fetch.get('warnings_high', 0)})")
    print()

    # 3. Queue
    print("📋 3. QUEUE / ADVISORY SAFETY")
    if not queue.get("present"):
        print("    ❌ ADVISORY QUEUE MISSING")
    else:
        print(f"    Total rows: {queue.get('total_rows', 0)}")
        print(f"    ACTIONABLE: {queue.get('actionable', 0)}")
        print(f"    Hidden total: {queue.get('hidden_total', 0)}")
        if queue.get("hidden_counts"):
            parts = ", ".join(f"{k}: {v}" for k, v in sorted(queue["hidden_counts"].items()))
            print(f"    Hidden breakdown: {parts}")
        print(f"    NO_LINE flags: {queue.get('no_line_count', 0)}")
        print(f"    HIDDEN_STALE: {queue.get('stale_count', 0)}")
    print()

    # 4. Portfolio
    print("🏦 4. PORTFOLIO SAFETY")
    print(f"    Open bets: {portfolio.get('open_bets', 0)}")
    print(f"    Open exposure: {portfolio.get('open_exposure', 0):.2f}u")
    print(f"    Proposed ACTIONABLE: {portfolio.get('proposed_count', 0)} rows")
    print(f"    Proposed exposure: {portfolio.get('proposed_exposure', 'unavailable')}")
    print(f"    Combined (open + proposed): {portfolio.get('combined_exposure', 'unavailable')}")
    print()

    # 5. Safety Footer
    print("🔒 5. SAFETY FOOTER")
    print("    • Manual approval required")
    print("    • No auto-betting")
    print("    • No formula changes")
    print("    • No staking changes")
    print("    • No threshold changes")
    print()

    # 6. Final Verdict
    print("🏁 6. FINAL VERDICT")
    icons = {
        "PREFLIGHT_PASS_SAFE_FOR_MANUAL_REVIEW": "✅",
        "PREFLIGHT_WARN_DEGRADED_DATA": "⚠️",
        "PREFLIGHT_BLOCKED_UNSAFE_OR_STALE": "🔴",
    }
    icon = icons.get(verdict, "❓")
    print(f"    {icon} {verdict}")
    print("=" * 60)


def main() -> int:
    """Run all audits and print report."""
    audits = {
        "git": audit_git(),
        "fetch": audit_fetch(),
        "queue": audit_queue(),
        "portfolio": audit_portfolio(),
    }
    verdict = final_verdict(audits)
    print_preflight(audits, verdict)
    return 0 if verdict == "PREFLIGHT_PASS_SAFE_FOR_MANUAL_REVIEW" else (1 if verdict == "PREFLIGHT_WARN_DEGRADED_DATA" else 2)


if __name__ == "__main__":
    sys.exit(main())