"""
WNBA Edge Lab V21.9 website state layer.

Single source of truth for public Flask routes. This module is display-only:
- no model formula changes
- no staking changes
- no threshold changes
- no auto-betting
- no bet creation/editing

It reads current artifacts and renders live state for app.py routes.
"""
from __future__ import annotations

import csv
import html
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

ROOT = Path(".")
OUT = ROOT / "wnba_outputs"
BET_TRACKER = ROOT / "bet_tracker.csv"
SAFE_AUTOMATION = OUT / "v21_9_safe_automation_summary.json"
SIGNAL_EXEC_LATEST = OUT / "signal_execution_latest_v20.json"
MANUAL_MARKET_REVIEW = OUT / "manual_market_review_v21_9.csv"
HERMES_MANUAL_QUEUE = OUT / "hermes_manual_market_queue_v21_9.csv"
MANUAL_MARKET_SUMMARY = OUT / "manual_market_review_summary_v21_9.json"
MODEL_RESULT_SUMMARY = OUT / "model_result_tracking_summary_v21_9.json"
SITE_AUDIT = OUT / "site_data_code_audit_v21_9.txt"


def esc(x: Any) -> str:
    return html.escape("" if x is None else str(x))


def money(x: Any, suffix: str = "u") -> str:
    try:
        val = float(x or 0)
        sign = "+" if val > 0 else ""
        return f"{sign}{val:.2f}{suffix}"
    except Exception:
        return f"0.00{suffix}"


def num(x: Any, default: float = 0.0) -> float:
    try:
        if x is None or x == "":
            return default
        return float(str(x).replace("+", ""))
    except Exception:
        return default


def read_json(path: Path, default: Any = None) -> Any:
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        pass
    return {} if default is None else default


def read_csv(path: Path) -> List[Dict[str, str]]:
    try:
        if not path.exists():
            return []
        with path.open(newline="", encoding="utf-8-sig", errors="ignore") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def pick(row: Dict[str, Any], *names: str, default: str = "") -> str:
    for n in names:
        if n in row and row.get(n) not in (None, ""):
            return str(row.get(n))
    return default


def status_norm(s: Any) -> str:
    return str(s or "").strip().upper()


def result_norm(s: Any) -> str:
    return str(s or "").strip().upper()


def load_state() -> Dict[str, Any]:
    bets = read_csv(BET_TRACKER)
    safe = read_json(SAFE_AUTOMATION)
    sig = read_json(SIGNAL_EXEC_LATEST)
    review = read_csv(MANUAL_MARKET_REVIEW)
    hermes_queue = read_csv(HERMES_MANUAL_QUEUE)
    manual_summary = read_json(MANUAL_MARKET_SUMMARY)
    result_summary = read_json(MODEL_RESULT_SUMMARY)

    open_bets = [r for r in bets if status_norm(r.get("Status")) == "OPEN"]
    settled = [r for r in bets if status_norm(r.get("Status")) in {"SETTLED", "WON", "LOST", "PUSH"}]

    open_stake = sum(num(r.get("Stake")) for r in open_bets)
    settled_pl = sum(num(r.get("P/L")) for r in settled)
    total_stake = sum(num(r.get("Stake")) for r in bets)
    wins = sum(1 for r in settled if result_norm(r.get("Result")) in {"WIN", "WON"})
    losses = sum(1 for r in settled if result_norm(r.get("Result")) in {"LOSS", "LOST"})

    # Dedupe watch: identical date/game/market/direction/line/odds/status.
    seen = {}
    dupes = []
    for r in bets:
        key = tuple((r.get(k) or "").strip().upper() for k in ["Date", "Game", "Market", "Direction", "Line", "Odds", "Status"])
        if key in seen:
            dupes.append((seen[key], r.get("BetID", "")))
        else:
            seen[key] = r.get("BetID", "")

    sig_summary = sig.get("summary", {}) if isinstance(sig, dict) else {}
    safe_fetch = ((safe.get("fetch") or {}).get("readiness") or {}) if isinstance(safe, dict) else {}
    safe_safety = (safe.get("safety") or {}) if isinstance(safe, dict) else {}
    locks = safe_safety.get("locks") or []

    label_counts = (manual_summary.get("label_counts") or {}) if isinstance(manual_summary, dict) else {}
    result_rows = (result_summary.get("rows") or {}) if isinstance(result_summary, dict) else {}
    gates = (result_summary.get("gates") or {}) if isinstance(result_summary, dict) else {}

    return {
        "bets": bets,
        "open_bets": open_bets,
        "settled": settled,
        "open_stake": open_stake,
        "settled_pl": settled_pl,
        "total_stake": total_stake,
        "wins": wins,
        "losses": losses,
        "duplicates": dupes,
        "safe": safe,
        "safe_fetch": safe_fetch,
        "locks": locks,
        "signal_execution": sig,
        "signal_summary": sig_summary,
        "manual_review": review,
        "hermes_queue": hermes_queue,
        "manual_summary": manual_summary,
        "manual_label_counts": label_counts,
        "result_summary": result_summary,
        "result_rows": result_rows,
        "gates": gates,
        "files": {
            "bet_tracker": BET_TRACKER.exists(),
            "safe_automation": SAFE_AUTOMATION.exists(),
            "signal_execution_latest": SIGNAL_EXEC_LATEST.exists(),
            "manual_market_review": MANUAL_MARKET_REVIEW.exists(),
            "hermes_manual_market_queue": HERMES_MANUAL_QUEUE.exists(),
            "manual_market_summary": MANUAL_MARKET_SUMMARY.exists(),
            "model_result_summary": MODEL_RESULT_SUMMARY.exists(),
        },
    }


def badge(label: str, cls: str = "") -> str:
    return f'<span class="chip {esc(cls)}">{esc(label)}</span>'


def card(title: str, value: Any, note: str = "", cls: str = "") -> str:
    return f'''<div class="v193-summary-card {esc(cls)}"><span>{esc(title)}</span><b>{esc(value)}</b><p>{esc(note)}</p></div>'''


def section(title: str, subtitle: str, inner: str, chip: str = "V21.9") -> str:
    return f'''<section class="panel"><div class="section-head" style="margin-top:0"><div><h2>{esc(title)}</h2><p>{esc(subtitle)}</p></div><span class="chip">{esc(chip)}</span></div>{inner}</section>'''


def top_state_strip(st: Dict[str, Any]) -> str:
    return f'''<section class="v192-command-strip">
      <div class="v192-chip-card"><span>Version</span><b>V21.9</b><p>Live state layer</p></div>
      <div class="v192-chip-card"><span>Open Bets</span><b>{len(st['open_bets'])}</b><p>{st['open_stake']:.2f}u exposure</p></div>
      <div class="v192-chip-card"><span>Settled P/L</span><b>{money(st['settled_pl'])}</b><p>Bet tracker</p></div>
      <div class="v192-chip-card"><span>Automation</span><b>Manual</b><p>No auto-betting</p></div>
      <div class="v192-chip-card"><span>Odds API</span><b>{'READY' if st['safe_fetch'].get('odds_ready') else 'QUOTA-SAFE'}</b><p>Paid calls skipped</p></div>
    </section>'''


def open_bets_html(st: Dict[str, Any], limit: Optional[int] = None) -> str:
    rows = st["open_bets"]
    if limit:
        rows = rows[:limit]
    if not rows:
        return '<div class="v193-page-note"><b>No open bets.</b> The tracker currently has no OPEN rows.</div>'
    out = []
    for r in rows:
        market = pick(r, "Market")
        side = pick(r, "Direction")
        line = pick(r, "Line")
        odds = pick(r, "Odds")
        stake = pick(r, "Stake")
        sig = pick(r, "FinalSignal", "Signal", default="MANUAL")
        edge = pick(r, "Edge", default="")
        conf = pick(r, "Confidence", default="")
        subtitle = f"{market} · {side}" + (f" {line}" if line not in ("", "0", "0.0") else "")
        out.append(f'''<div class="action-clean-card">
          <div class="action-clean-head"><div><div class="action-rank-clean">{esc(pick(r, 'BetID'))} · OPEN</div><div class="action-clean-title">{esc(pick(r, 'Game'))}</div></div><span class="badge green">{esc(sig)}</span></div>
          <div class="action-clean-bet">{esc(subtitle)} @ {esc(odds)}</div>
          <div class="action-clean-grid"><div class="mini"><span>Stake</span><b>{esc(stake)}u</b></div><div class="mini"><span>Edge</span><b>{esc(edge or '—')}</b></div><div class="mini"><span>Confidence</span><b>{esc(conf or '—')}</b></div><div class="mini"><span>Status</span><b>OPEN</b></div></div>
          <div class="approval-rail"><span class="approval-pill warn">Manual approval recorded</span><span class="approval-pill locked">No auto-bet</span></div>
        </div>''')
    return '<div class="action-board">' + ''.join(out) + '</div>'


def manual_queue_html(st: Dict[str, Any], limit: int = 12) -> str:
    rows = st["hermes_queue"] or st["manual_review"]
    if not rows:
        return '<div class="v193-page-note"><b>No V21.9 manual market queue found.</b> Run manual_market_snapshot_v21_9.py and model_manual_market_review_v21_9.py.</div>'
    # sort by advisory then edge desc
    def sort_key(r: Dict[str, str]):
        label = pick(r, "advisory_label", default="")
        rank = {"LEAN_SUPPORT": 0, "MANUAL_REVIEW": 1, "NO_PLAY": 2}.get(label, 9)
        return (rank, -num(pick(r, "model_edge", "edge", default="0")))
    rows = sorted(rows, key=sort_key)[:limit]
    out = []
    for i, r in enumerate(rows, 1):
        label = pick(r, "advisory_label", default="MANUAL_REVIEW")
        label_cls = "green" if label == "LEAN_SUPPORT" else "warn" if label == "MANUAL_REVIEW" else "gray"
        line = pick(r, "line")
        out.append(f'''<div class="action-clean-card">
          <div class="action-clean-head"><div><div class="action-rank-clean">#{i:02d} MODEL QUEUE</div><div class="action-clean-title">{esc(pick(r, 'game'))}</div></div><span class="badge {label_cls}">{esc(label)}</span></div>
          <div class="action-clean-bet">{esc(pick(r, 'market'))} · {esc(pick(r, 'side'))}{(' ' + esc(line)) if line else ''} @ {esc(pick(r, 'odds_decimal', 'odds'))}</div>
          <div class="action-clean-grid"><div class="mini"><span>Edge</span><b>{esc(pick(r, 'model_edge', 'edge'))}</b></div><div class="mini"><span>Confidence</span><b>{esc(pick(r, 'confidence'))}</b></div><div class="mini"><span>Approval</span><b>Manual</b></div><div class="mini"><span>Risk</span><b>{esc(pick(r, 'risk_flags'))}</b></div></div>
          <div class="approval-rail"><span class="approval-pill warn">MANUAL_APPROVAL_REQUIRED</span><span class="approval-pill locked">NO_AUTO_BETTING</span></div>
        </div>''')
    return '<div class="action-board">' + ''.join(out) + '</div>'


def settled_recent_html(st: Dict[str, Any], limit: int = 10) -> str:
    rows = list(reversed(st["settled"]))[:limit]
    if not rows:
        return '<div class="v193-page-note">No settled bets found.</div>'
    items = []
    for r in rows:
        pl = num(r.get("P/L"))
        cls = "green" if pl > 0 else "red" if pl < 0 else "gray"
        items.append(f'''<div class="validation-row-lite"><div><span>{esc(pick(r,'BetID'))} · {esc(pick(r,'Market'))}</span><b>{esc(pick(r,'Game'))}</b></div><em>{esc(pick(r,'Direction'))} {esc(pick(r,'Line'))} @ {esc(pick(r,'Odds'))}</em><b>{esc(pick(r,'Result'))}</b><b class="{cls}">{money(pl)}</b></div>''')
    return '<div class="validation-compact-list">' + ''.join(items) + '</div>'


def safety_html(st: Dict[str, Any]) -> str:
    locks = st["locks"] or ["MANUAL_APPROVAL_REQUIRED", "NO_AUTO_BETTING", "NO_FORMULA_REPLACEMENT", "NO_STAKING_CHANGES", "NO_THRESHOLD_CHANGES"]
    lock_html = ''.join(f'<span class="approval-pill locked">{esc(x)}</span>' for x in locks)
    fetch = st["safe_fetch"]
    readiness = ''.join(card(k.replace('_', ' '), "YES" if v else "NO", "readiness", "primary" if v else "warn") for k, v in fetch.items()) if fetch else card("Fetch", "Unknown", "summary not found", "warn")
    return section("Safety & readiness", "Current automation gates and data source readiness.", f'<div class="approval-rail">{lock_html}</div><div class="v193-summary-grid">{readiness}</div>', "NO AUTO-BETTING")


def file_state_html(st: Dict[str, Any]) -> str:
    cells = []
    for name, ok in st["files"].items():
        cells.append(card(name, "OK" if ok else "MISSING", "required V21.9 artifact", "primary" if ok else "warn"))
    dup_note = card("Duplicate bet keys", len(st["duplicates"]), "audit watch only", "warn" if st["duplicates"] else "primary")
    return section("Code/data wiring", "Files the website is using now.", '<div class="v193-summary-grid">' + ''.join(cells) + dup_note + '</div>', "single source")


def render_home() -> str:
    st = load_state()
    body = top_state_strip(st)
    body += '<div class="section-head"><div><h2>V21.9 live operator state</h2><p>Website now reads bet_tracker, signal execution, safe automation, and manual market queue.</p></div><span class="chip">Manual only</span></div>'
    body += '<div class="v193-summary-grid">'
    body += card("Open Bets", len(st["open_bets"]), f"{st['open_stake']:.2f}u exposure", "primary")
    body += card("Settled P/L", money(st["settled_pl"]), f"{st['wins']}W / {st['losses']}L", "primary" if st["settled_pl"] >= 0 else "warn")
    body += card("Execution Tickets", st["signal_summary"].get("execution_tickets", len(st["bets"])), "signal bridge")
    body += card("Manual Queue", len(st["hermes_queue"]), "Hermes V21.9 market queue")
    body += card("Quota Mode", "ACTIVE" if not st["safe_fetch"].get("odds_ready") else "ODDS READY", "paid calls protected", "warn")
    body += '</div>'
    body += section("Open bets you made", "Current OPEN tickets from bet_tracker.csv.", open_bets_html(st), "OPEN")
    body += section("Model / Hermes queue", "Advisory-only market review; not execution.", manual_queue_html(st, 8), "LEAN SUPPORT")
    body += safety_html(st)
    return body


def render_dashboard() -> str:
    st = load_state()
    body = top_state_strip(st)
    body += '<div class="section-head"><div><h2>V21.9 Dashboard</h2><p>Live state from the current ledger, execution bridge, safe automation, and manual market review.</p></div><span class="chip">V21.9</span></div>'
    body += '<div class="v193-summary-grid">'
    body += card("Open Bets", len(st["open_bets"]), f"{st['open_stake']:.2f}u exposure", "primary")
    body += card("Pending / Open Groups", st["signal_summary"].get("open_groups", len(st["open_bets"])), "signal bridge")
    body += card("Settled Groups", st["signal_summary"].get("settled_groups", len(st["settled"])), "signal bridge")
    body += card("Net P/L", money(st["signal_summary"].get("net_profit", st["settled_pl"])), "signal bridge")
    body += card("Manual Queue", len(st["hermes_queue"]), str(st["manual_label_counts"] or {}))
    body += card("Formula Gate", st["gates"].get("current_gate_state", "EVIDENCE_COLLECTION_ONLY"), "no promotion")
    body += '</div>'
    body += section("Open bets", "Exactly what is currently marked OPEN.", open_bets_html(st), "bet_tracker.csv")
    body += section("V21.9 model queue", "Operator-entered market lines evaluated by model context.", manual_queue_html(st, 12), "Hermes")
    body += safety_html(st)
    body += file_state_html(st)
    return body


def render_actions() -> str:
    st = load_state()
    body = top_state_strip(st)
    body += '<div class="section-head"><div><h2>Actions</h2><p>Today\'s actionable view: open bets already made plus remaining model queue. No auto-execution.</p></div><span class="chip">Manual approval</span></div>'
    body += section("Open bets already made", "These are not recommendations; these are logged OPEN tickets.", open_bets_html(st), "OPEN")
    body += section("Model queue / potential actions", "LEAN_SUPPORT and MANUAL_REVIEW rows from V21.9 manual market review.", manual_queue_html(st, 18), "Advisory")
    return body


def render_hermes() -> str:
    st = load_state()
    body = top_state_strip(st)
    body += '<div class="section-head"><div><h2>Hermes · V21.9 Manual Approval</h2><p>Hermes can warn and queue. It cannot place bets.</p></div><span class="chip">Locked</span></div>'
    body += safety_html(st)
    body += section("Hermes manual market queue", "Queue built from manual_market_review_v21_9 and marked manual approval required.", manual_queue_html(st, 18), "MANUAL")
    body += section("Open operator bets", "Bets already entered manually by the operator.", open_bets_html(st), "OPEN")
    return body


def render_bets() -> str:
    st = load_state()
    body = top_state_strip(st)
    body += '<div class="section-head"><div><h2>Bets ledger</h2><p>Open and settled tickets from bet_tracker.csv.</p></div><span class="chip">Ledger</span></div>'
    body += '<div class="v193-summary-grid">'
    body += card("Open", len(st["open_bets"]), f"{st['open_stake']:.2f}u")
    body += card("Settled", len(st["settled"]), f"P/L {money(st['settled_pl'])}")
    body += card("Total Tickets", len(st["bets"]), "bet_tracker.csv")
    body += card("Duplicates", len(st["duplicates"]), "audit key watch", "warn" if st["duplicates"] else "primary")
    body += '</div>'
    body += section("Open bets", "Current pending tickets.", open_bets_html(st), "OPEN")
    body += section("Recent settled bets", "Recent closed tickets for bankroll context.", settled_recent_html(st), "SETTLED")
    return body


def render_bankroll() -> str:
    st = load_state()
    body = top_state_strip(st)
    body += '<div class="section-head"><div><h2>Bankroll</h2><p>Ticket-level stake, open exposure, and settled P/L.</p></div><span class="chip">Manual Ledger</span></div>'
    body += '<div class="v193-summary-grid">'
    body += card("Open Exposure", f"{st['open_stake']:.2f}u", f"{len(st['open_bets'])} open tickets", "warn" if st["open_bets"] else "primary")
    body += card("Settled P/L", money(st["settled_pl"]), f"{st['wins']}W / {st['losses']}L", "primary" if st["settled_pl"] >= 0 else "warn")
    body += card("Bridge P/L", money(st["signal_summary"].get("net_profit", st["settled_pl"])), "signal execution")
    body += card("Total Stake", f"{st['total_stake']:.2f}u", "all tickets")
    body += '</div>'
    body += section("Open exposure", "Tickets awaiting settlement.", open_bets_html(st), "OPEN")
    body += section("Recent settled ledger", "Bankroll P/L source.", settled_recent_html(st), "SETTLED")
    return body


def render_telegram() -> str:
    st = load_state()
    lines = [
        "WNBA EDGE LAB V21.9 — MANUAL ONLY",
        f"Open bets: {len(st['open_bets'])} / exposure {st['open_stake']:.2f}u",
        f"Settled P/L: {money(st['settled_pl'])}",
        "Safety: NO_AUTO_BETTING · MANUAL_APPROVAL_REQUIRED · NO_FORMULA_REPLACEMENT",
        "",
        "OPEN BETS:",
    ]
    for r in st["open_bets"]:
        line = pick(r, "Line")
        lines.append(f"- {pick(r,'Game')} | {pick(r,'Market')} {pick(r,'Direction')} {line} @ {pick(r,'Odds')} | {pick(r,'Stake')}u | {pick(r,'FinalSignal','Signal', default='MANUAL')}")
    lines += ["", "MODEL QUEUE:"]
    for r in (st["hermes_queue"] or st["manual_review"])[:8]:
        lines.append(f"- {pick(r,'advisory_label', default='REVIEW')} | {pick(r,'game')} | {pick(r,'market')} {pick(r,'side')} {pick(r,'line')} @ {pick(r,'odds_decimal','odds')} | edge {pick(r,'model_edge','edge')} | conf {pick(r,'confidence')}")
    text = "\n".join(lines)
    return f'''<div class="section-head"><div><h2>Telegram message</h2><p>Generated from V21.9 live state, not legacy telegram_message.txt.</p></div><span class="chip">Copy</span></div><section class="panel"><pre style="white-space:pre-wrap;font-family:var(--font-mono);line-height:1.7">{esc(text)}</pre></section>'''


def render_validation() -> str:
    st = load_state()
    body = top_state_strip(st)
    body += '<div class="section-head"><div><h2>Validation</h2><p>Evidence collection layer and formula-promotion gates.</p></div><span class="chip">Evidence only</span></div>'
    body += '<div class="v193-summary-grid">'
    body += card("Tracking Rows", st["result_rows"].get("tracking", 0), "V21.9 result tracker")
    body += card("Known Results", st["result_rows"].get("known_results", 0), "current advisory rows")
    body += card("CLV Samples", st["result_rows"].get("clv_samples", 0), "current advisory rows")
    body += card("Formula Change", "BLOCKED", st["gates"].get("current_gate_state", "EVIDENCE_COLLECTION_ONLY"), "lock")
    body += '</div>'
    body += section("Model queue", "Current market review labels.", manual_queue_html(st, 18), "review")
    body += safety_html(st)
    return body


def render_menu() -> str:
    st = load_state()
    links = [
        ("Dashboard", "/dashboard", "Live V21.9 state"),
        ("Actions", "/actions", "Open bets and model queue"),
        ("Hermes", "/hermes", "Manual approval queue"),
        ("Bets", "/bets", "Open/settled ledger"),
        ("Bankroll", "/bankroll", "P/L and exposure"),
        ("Telegram", "/telegram", "Generated message"),
        ("Validation", "/validation", "Evidence gates"),
        ("Diagnostics", "/diagnostics", "Technical outputs"),
    ]
    cards = ''.join(f'<a class="v19-card" href="{href}"><span>V21.9</span><b>{esc(name)}</b><p>{esc(desc)}</p></a>' for name, href, desc in links)
    return top_state_strip(st) + f'<div class="section-head"><div><h2>Menu</h2><p>All key routes are wired to the V21.9 state layer.</p></div><span class="chip">Live</span></div><div class="v19-grid-4">{cards}</div>'
