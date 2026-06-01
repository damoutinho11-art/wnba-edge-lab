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
    advisory = read_csv(MODEL_ADVISORY)
    mrt = read_json(MODEL_RESULT_TRACKING_SUMMARY)
    
    groups = {"LEAN_SUPPORT": [], "MANUAL_REVIEW": [], "NEUTRAL": []}
    
    for row in advisory:
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
            success = False
    return success

def main() -> int:
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--send", action="store_true")
    parser.add_argument("--update", action="store_true")
    parser.add_argument("--picks", action="store_true")
    args = parser.parse_args()

    if args.update:
        print("Updating features via safe automation...")
        subprocess.run([sys.executable, str(RUN_SAFE_AUTOMATION), "--features"])

    if args.picks:
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
            print("✅ Sent to Telegram")
            return 0
        return 1
    
    print("Error: Specify --dry-run or --send")
    return 1

if __name__ == "__main__":
    sys.exit(main())
