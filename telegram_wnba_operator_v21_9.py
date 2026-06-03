#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram WNBA Operator Interface V21.9

Provides a rich Telegram status and picks report, mirroring the website state.
Handles flexible column mapping for model advisory data and safe automation triggers.

Usage:
    python telegram_wnba_operator_v21_9.py --dry-run
    python telegram_wnba_operator_v21_9.py --picks --dry-run
    python telegram_wnba_operator_v21_9.py --send
    python telegram_wnba_operator_v21_9.py --update --send
"""

import csv
import json
import os
import sys
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Any, Optional

try:
    import requests
except ImportError:
    requests = None

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "wnba_outputs"

# Files
BET_TRACKER = ROOT / "bet_tracker.csv"
HERMES_ADVISORY = OUT / "hermes_advisory_queue_v21.csv"
MODEL_ADVISORY = OUT / "model_advisory_scores_v21.csv"
MANUAL_MARKET_REVIEW = OUT / "manual_market_review_v21_9.csv"
MODEL_RESULT_TRACKING_SUMMARY = OUT / "model_result_tracking_summary_v21_9.json"
MODEL_AUDIT_SUMMARY = OUT / "model_audit_summary_v20.json"
SAFE_AUTOMATION_SUMMARY = OUT / "v21_9_safe_automation_summary.json"
RUN_SAFE_AUTOMATION = ROOT / "run_v21_9_safe_automation_cycle.py"

# Secrets
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

# Flexible Column Mapping
COLUMN_MAP = {
    "game": ["game", "Game", "matchup", "Matchup"],
    "market": ["market", "Market", "bet_type", "MarketType"],
    "side": ["side", "Side", "selection", "Selection", "direction", "Direction"],
    "line": ["line", "Line", "LineAtSignal"],
    "odds": ["odds_decimal", "OddsDecimal", "odds", "Odds", "price"],
    "edge": ["model_edge", "edge", "Edge"],
    "confidence": ["confidence", "Confidence", "model_confidence"],
    "label": ["advisory_label", "label", "FinalSignal"],
    "risk_flags": ["risk_flags", "RiskFlags"],
    # Timing instrumentation — safe aliases; resolves to "" if blank (future bets only)
    "entry_time": ["EntryTimeUTC"],
    "game_start": ["GameStartTimeUTC"],
    "minutes_before": ["MinutesBeforeTip"],
    "bet_source": ["BetSource"],
    "approval_source": ["ApprovalSource"],
}

def resolve_col(row: Dict[str, Any], key: str) -> str:
    aliases = COLUMN_MAP.get(key, [])
    for alias in aliases:
        if alias in row and row[alias] is not None:
            val = str(row[alias]).strip()
            if val.lower() != "nan" and val != "":
                return val
    return "n/a"

def read_csv(path: Path) -> List[Dict[str, str]]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))

def read_json(path: Path) -> Any:
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def format_risk_flags(flags: str) -> str:
    if not flags or flags == "n/a":
        return "CLEAN"
    parts = [p.strip() for p in flags.replace(";", ",").split(",") if p.strip()]
    mapping = {
        "MANUAL_APPROVAL_REQUIRED": "MANUAL APPROVAL",
        "NO_AUTO_BETTING": "NO AUTO-BET",
        "NO_FORMULA_REPLACEMENT": "NO FORMULA CHANGE",
        "THIN_POSITIVE_EDGE": "THIN EDGE",
        "LOW_SAMPLE_SIZE": "LOW SAMPLE",
        "MODEL_DRIFT": "MODEL DRIFT",
        "FEATURE_STALE": "FEATURE STALE",
        "DATA_STALE": "DATA STALE",
        "API_ERROR": "API ERROR",
        "NEGATIVE_MODEL_EDGE": "NEG EDGE",
        "PRICE_EDGE_TOO_SMALL": "SMALL EDGE",
        "VALID_DATA": "VALID DATA",
        "STRONG_SIGNAL": "STRONG SIGNAL",
    }
    return ", ".join([mapping.get(p, p) for p in parts])

def infer_market(side: str, line: str) -> str:
    if side == "n/a": return "n/a"
    side_up = side.upper()
    if "OVER" in side_up or "UNDER" in side_up:
        return "Game Total"
    if line != "n/a" and line != "0":
        return "Spread"
    return "Moneyline"

def get_open_bets() -> str:
    bets = read_csv(BET_TRACKER)
    lines = ["📦 Open Bets:"]
    found = False
    for b in bets:
        status = b.get("Status", "").strip().upper()
        if status == "OPEN" or not status:
            found = True
            betid = b.get("BetID", "n/a")
            game = resolve_col(b, "game")
            market = resolve_col(b, "market")
            side = resolve_col(b, "side")
            line = resolve_col(b, "line")
            odds = resolve_col(b, "odds")
            stake = b.get("Stake", "n/a")
            lines.append(f"  • {betid}: {game} | {market} {side} {line} @ {odds} ({stake}u)")
    if not found:
        lines.append("  (none)")
    return "\n".join(lines)

def build_status() -> str:
    lines = ["📊 Update / Status:"]
    auto = read_json(SAFE_AUTOMATION_SUMMARY)
    mrt = read_json(MODEL_RESULT_TRACKING_SUMMARY)
    
    # Root keys correctly read from JSON
    status = auto.get("status", "n/a")
    # Nested fetch state
    fetch_data = auto.get("fetch", {})
    odds_st = fetch_data.get("state", "n/a")
    
    # Nested features rows
    feats = auto.get("features", {}).get("rows", {})
    m_rows = feats.get("market_features", "n/a") if feats else "n/a"
    
    # Nested tracking results
    rows = mrt.get("rows", {})
    known = rows.get("known_results", "n/a")
    clv = rows.get("clv_samples", "n/a")
    
    # Nest gates state
    gates = mrt.get("gates", {}).get("current_gate_state", "n/a")
    
    # Health from diagnostics (NESTED)
    health = "n/a"
    diag = auto.get("diagnostics", {})
    if diag and "files" in diag:
        health_file = diag["files"].get("model_health_report_v21", {})
        if health_file.get("exists"):
            # We use a generic 'OK' if the report exists and is valid
            health = "OK (Report Ready)"
    
    lines.append(f"  • Cycle: {status}")
    lines.append(f"  • Odds: {odds_st}")
    lines.append(f"  • Mkt Features: {m_rows}")
    lines.append(f"  • Known Results: {known}")
    lines.append(f"  • CLV Samples: {clv}")
    lines.append(f"  • Model Health: {health}")
    lines.append(f"  • Formula Gate: {gates}")
    return "\n".join(lines)

def build_picks() -> str:
    # Read from hermes_advisory_queue which has source-level freshness fields.
    advisory = read_csv(HERMES_ADVISORY)
    mrt = read_json(MODEL_RESULT_TRACKING_SUMMARY)

    # Fallback display-layer actionability (used when source field absent).
    def _is_actionable(row):
        game = resolve_col(row, "game")
        if not game or game == "n/a":
            return False
        flags = resolve_col(row, "risk_flags").upper()
        if "NO_LINE" in flags:
            return False
        label = resolve_col(row, "label").upper()
        if "LEAN" not in label and "MANUAL" not in label:
            return False
        stale_flag = str(row.get("is_stale", "")).strip().lower()
        if stale_flag in ("true", "1", "yes"):
            return False
        created = row.get("created_at_utc", "")
        if created:
            try:
                cc = created.replace("Z", "+00:00")
                dt = datetime.fromisoformat(cc).replace(tzinfo=timezone.utc)
                age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
                if age_hours > 48:
                    return False
            except Exception:
                pass
        row_date = row.get("date", "")
        if row_date:
            try:
                today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                if row_date < today_utc:
                    return False
            except Exception:
                pass
        return True

    # Primary gate: source-level queue_actionability if present.
    # Fallback: display-level _is_actionable() for CSVs without the field.
    NON_ACTIONABLE = {
        "SCHEDULE_UNVERIFIED_TODAY", "SCHEDULE_UNVERIFIED_FUTURE",
        "HIDDEN_NO_SCHEDULE", "HIDDEN_NO_LINE", "HIDDEN_STALE",
        "HIDDEN_INVALID", "HIDDEN_LABEL", "UNKNOWN",
    }
    source_actionable = []
    hidden_actionability: Dict[str, int] = {}
    fallback_actionable = []
    for row in advisory:
        src = str(row.get("queue_actionability", "")).strip().upper()
        if src:
            if src == "ACTIONABLE":
                source_actionable.append(row)
            else:
                hidden_actionability[src] = hidden_actionability.get(src, 0) + 1
        else:
            # Fallback to display-layer rules.
            if _is_actionable(row):
                fallback_actionable.append(row)

    # Prefer source-level classification; fall back if no source data.
    if source_actionable or hidden_actionability:
        actionable = source_actionable
    else:
        actionable = fallback_actionable

    groups = {"LEAN_SUPPORT": [], "MANUAL_REVIEW": [], "NEUTRAL": []}

    for row in actionable:
        game = resolve_col(row, "game")
        if game == "n/a":
            continue

        label = resolve_col(row, "label").upper()
        if "LEAN" in label:
            groups["LEAN_SUPPORT"].append(row)
        elif "MANUAL" in label:
            groups["MANUAL_REVIEW"].append(row)
        else:
            groups["NEUTRAL"].append(row)

    output = ["📋 Model Picks / Queue:"]
    total_actionable = sum(len(g) for g in groups.values())
    if total_actionable == 0:
        output.append("  No actionable model picks after source freshness/risk filtering.")
        output.append("  Manual approval required · No auto-betting · No formula changes.")
    hidden_count_total = len(advisory) - len(actionable)
    if hidden_count_total > 0:
        # Report source-level hidden counts if available, else generic count.
        if hidden_actionability:
            parts = ", ".join(f"{k}: {v}" for k, v in sorted(hidden_actionability.items()))
            output.append(f"  Hidden non-actionable rows: {hidden_count_total} ({parts}).")
        else:
            output.append(f"  (Hidden {hidden_count_total} non-actionable row(s): stale/no-line/invalid)")
    for label, group in groups.items():
        if not group: continue
        emoji = {"LEAN_SUPPORT": "🟢", "MANUAL_REVIEW": "🟡", "NEUTRAL": "⚪"}.get(label, "⚪")
        output.append(f"\n  {emoji} {label} ({len(group)}):")
        
        for p in group:
            game = resolve_col(p, "game")
            market_raw = resolve_col(p, "market")
            side = resolve_col(p, "side")
            line = resolve_col(p, "line")
            odds = resolve_col(p, "odds")
            edge = resolve_col(p, "edge")
            conf = resolve_col(p, "confidence")
            risk = resolve_col(p, "risk_flags")
            
            # If market is n/a, infer from side and line
            market = market_raw if market_raw != "n/a" else infer_market(side, line)
            
            # Format odds and confidence strings to omit n/a
            odds_str = f" @ {odds}" if odds != "n/a" else ""
            conf_str = f" | Conf: {conf}%" if conf != "n/a" else ""
            
            output.append(f"    • {game} | {market} {side} {line}{odds_str} | Edge: {edge}{conf_str} | Risk: {format_risk_flags(risk)}")
            
            # Reasoning
            if label in ["LEAN_SUPPORT", "MANUAL_REVIEW"]:
                reasons = []
                if edge != "n/a": reasons.append(f"Edge {edge}")
                if conf != "n/a": reasons.append(f"Conf {conf}%")
                if "NO_LINE" in risk: reasons.append("MISSING MARKET LINE")
                if "LOW_MODEL_EDGE" in risk or "THIN_POSITIVE_EDGE" in risk: 
                    reasons.append("Low statistical edge")
                
                # Check result tracker sample gate
                rows_data = mrt.get("rows", {})
                known_res = rows_data.get("known_results", 0)
                if isinstance(known_res, int) and known_res < 30:
                    reasons.append("SAMP_GATE: INSUFFICIENT_SAMPLE")
                elif "INSUFFICIENT_SAMPLE" in str(mrt.get("gates", {}).get("current_gate_state", "")) :
                    reasons.append("SAMP_GATE: INSUFFICIENT_SAMPLE")
                
                reasons.append("manual approval required")
                output.append(f"      └─ {', '.join(reasons)}")
                
    return "\n".join(output)

def build_full_report() -> str:
    lines = [
        "🏀 WNBA Edge Lab V21.9",
        "Website: https://wnba-edge-lab.onrender.com/",
        "Dashboard: /dashboard | Actions: /actions | Bets: /bets",
        "",
        build_status(),
        "",
        get_open_bets(),
        "",
        build_portfolio_risk(),
        "",
        build_picks(),
        "",
        "🔒 Safety Footer:",
        "  • Manual approval required",
        "  • No auto-betting",
        "  • No formula changes",
        "  • No staking changes",
        "  • No threshold changes",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}"
    ]
    return "\n".join(lines)

def send_telegram(message: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("ERROR: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID missing")
        return False
    if requests is None:
        print("ERROR: requests library missing")
        return False
    
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    
    # Split messages at 3500 chars
    chunks = []
    current = ""
    for line in message.split("\n"):
        if len(current) + len(line) + 1 > 3500 and current:
            chunks.append(current)
            current = line
        else:
            current = (current + "\n" + line) if current else line
    if current:
        chunks.append(current)
    
    success = True
    for chunk in chunks:
        try:
            resp = requests.post(url, json={"chat_id": TELEGRAM_CHAT_ID, "text": chunk, "parse_mode": "HTML"}, timeout=10)
            resp.raise_for_status()
        except Exception as e:
            print(f"Chunk failed: {e}")
            return success



# ── Portfolio-risk summary (READ-ONLY) ─────────────────────────────

PORTFOLIO_NON_ACTIONABLE = {
    "SCHEDULE_UNVERIFIED_TODAY", "SCHEDULE_UNVERIFIED_FUTURE",
    "HIDDEN_NO_SCHEDULE", "HIDDEN_NO_LINE", "HIDDEN_STALE",
    "HIDDEN_INVALID", "HIDDEN_LABEL", "UNKNOWN",
}


def _portfolio_market_type(market: str) -> str:
    if not market:
        return "unknown"
    m = market.upper()
    if "TOTAL" in m:
        return "totals"
    if "SPREAD" in m:
        return "spreads"
    if "MONEYLINE" in m:
        return "moneyline"
    if m in ("", "UNKNOWN", "NAN", "NONE"):
        return "unknown"
    return "props"


def _portfolio_open_status(status: str) -> str:
    s = str(status).strip().upper()
    if s in ("OPEN", "PENDING", "ACTIVE"):
        return "OPEN"
    if s in ("SETTLED", "WON", "LOST", "PUSH", "CANCELLED", "VOID"):
        return "SETTLED"
    if s == "":
        return "UNKNOWN"
    return "OTHER"


def _portfolio_settle_marker(b: Dict[str, str]) -> bool:
    if _portfolio_open_status(b.get("Status", "")) == "SETTLED":
        return True
    result = str(b.get("Result", "")).strip().upper()
    if result and result not in ("", "NAN", "NONE", "NULL"):
        return True
    pl = str(b.get("P/L", "")).strip()
    if pl and pl not in ("", "0", "0.0", "nan", "None"):
        return True
    actual = str(b.get("Actual", "")).strip()
    if actual and actual not in ("", "NAN", "NONE", "NULL"):
        return True
    return False


def _is_portfolio_open(b: Dict[str, str]) -> str:
    if _portfolio_settle_marker(b):
        return "NOT_OPEN"
    s = _portfolio_open_status(b.get("Status", ""))
    if s == "OPEN":
        return "OPEN"
    if s == "UNKNOWN":
        return "UNKNOWN"
    return "NOT_OPEN"


def build_portfolio_risk() -> str:
    """READ-ONLY portfolio-risk summary for Telegram. No writes. No formula changes."""
    bets = read_csv(BET_TRACKER)
    advisory = read_csv(HERMES_ADVISORY)

    open_bets = []
    unknown_bets = []
    for b in bets:
        c = _is_portfolio_open(b)
        if c == "OPEN":
            open_bets.append(b)
        elif c == "UNKNOWN":
            unknown_bets.append(b)

    open_stake = sum(float(b.get("Stake", "0") or "0") for b in open_bets)

    mtype_totals: Dict[str, float] = {}
    for b in open_bets:
        mt = _portfolio_market_type(b.get("Market", ""))
        mtype_totals[mt] = mtype_totals.get(mt, 0.0) + float(b.get("Stake", "0") or "0")

    actionable = []
    hidden_counts: Dict[str, int] = {}
    hidden_total = 0
    for r in advisory:
        src = str(r.get("queue_actionability", "")).strip().upper()
        if src == "ACTIONABLE":
            actionable.append(r)
        elif src:
            hidden_counts[src] = hidden_counts.get(src, 0) + 1
            hidden_total += 1
        else:
            hidden_counts["no_field"] = hidden_counts.get("no_field", 0) + 1
            hidden_total += 1

    proposed_count = len(actionable)
    proposed_units = 0.0
    units_parseable = True
    for r in actionable:
        u = r.get("units", "").strip()
        if u and u.upper() not in ("NAN", "NONE", "NULL", ""):
            try:
                proposed_units += float(u)
            except (ValueError, TypeError):
                units_parseable = False

    # Ladder detection
    lad_groups: Dict[tuple, list] = {}
    for b in open_bets:
        g = b.get("Game", "").strip()
        mt = _portfolio_market_type(b.get("Market", ""))
        d = b.get("Direction", "").strip()
        ln = b.get("Line", "").strip()
        if g and ln:
            key = (g, mt, d)
            lad_groups.setdefault(key, []).append(ln)
    ladders = [(g, mt, d, sorted(set(lines))) for (g, mt, d), lines in lad_groups.items()
               if len(set(lines)) >= 2]

    game_exposure: Dict[str, float] = {}
    for b in open_bets:
        g = b.get("Game", "").strip()
        if g:
            game_exposure[g] = game_exposure.get(g, 0.0) + float(b.get("Stake", "0") or "0")

    player_exposure: Dict[str, float] = {}
    for b in open_bets:
        p = b.get("Player", "").strip()
        if p:
            player_exposure[p] = player_exposure.get(p, 0.0) + float(b.get("Stake", "0") or "0")

    out_lines = ["\U0001f3e6 Portfolio Risk:"]

    if not open_bets:
        out_lines.append("  Open exposure: 0.00u (0 bets)")
    else:
        parts = " | ".join(
            f"{mt.title()} {exp:.2f}u"
            for mt, exp in sorted(mtype_totals.items(), key=lambda x: -x[1])
            if exp > 0
        )
        out_lines.append(f"  Open exposure: {open_stake:.2f}u ({len(open_bets)} bets)")
        out_lines.append(f"  Market split: {parts or 'none'}")
        if game_exposure:
            game_str = ", ".join(f"{g} {exp:.2f}u" for g, exp in
                                 sorted(game_exposure.items(), key=lambda x: -x[1]))
            out_lines.append(f"  Games: {game_str}")
        if player_exposure:
            player_str = ", ".join(f"{p} {exp:.2f}u" for p, exp in
                                   sorted(player_exposure.items(), key=lambda x: -x[1]))
            out_lines.append(f"  Players: {player_str}")

    if unknown_bets:
        out_lines.append(f"  \u26a0 {len(unknown_bets)} row(s) with unknown status \u2014 not counted")

    if proposed_count == 0:
        out_lines.append("  Proposed ACTIONABLE: 0 (0 rows)")
    else:
        units_str = f"{proposed_units:.2f}u" if units_parseable else "units unavailable"
        out_lines.append(f"  Proposed ACTIONABLE: {units_str} ({proposed_count} rows)")

    if hidden_total:
        hidden_parts = ", ".join(f"{k}: {v}" for k, v in sorted(hidden_counts.items()))
        out_lines.append(f"  Hidden non-actionable: {hidden_total} ({hidden_parts})")

    if ladders:
        out_lines.append(f"  \u26a0 Ladders: {len(ladders)} detected")
        for g, mt, d, lns in ladders:
            out_lines.append(f"    \u2022 {g} {mt} {d} @ {', '.join(lns)}")

    combined = open_stake + (proposed_units if units_parseable else 0.0)
    out_lines.append(f"  Combined: {combined:.2f}u open + proposed")
    out_lines.append("  Reference cap: not configured (display only)")
    out_lines.append("  Manual approval required \u00b7 No auto-betting \u00b7 No formula changes")

    return "\n".join(out_lines)


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--picks", action="store_true")
    parser.add_argument("--portfolio", action="store_true")
    args = parser.parse_args()

    if args.update:
        print("Updating features via safe automation...")
        subprocess.run([sys.executable, str(RUN_SAFE_AUTOMATION), "--features"])

    if args.portfolio:
        report = build_portfolio_risk()
    elif args.picks:
        report = build_picks()
    else:
        report = build_full_report()

    if args.dry_run:
        print("=== DRY RUN ===")
        print(report)
        print("=== END DRY RUN ===")
        return 0

    if args.send:
        if send_telegram(report):
            print("\u2705 Sent to Telegram")
            return 0
        return 1

    print("Error: Specify --dry-run or --send")
    return 1


if __name__ == "__main__":
    sys.exit(main())
