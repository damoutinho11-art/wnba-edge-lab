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
from datetime import datetime, timezone
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
MODEL_HEALTH = OUT / "model_health_report.csv"
CLV_SUMMARY = OUT / "signal_clv_summary.csv"
DATA_FRESHNESS = OUT / "data_freshness_v21.csv"


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


def _last_updated_from_freshness() -> str:
    """Read data_freshness_v21.csv and return a human-readable 'last updated' string."""
    try:
        if not DATA_FRESHNESS.exists():
            return "unknown"
        with DATA_FRESHNESS.open(newline="", encoding="utf-8-sig", errors="ignore") as f:
            reader = list(csv.DictReader(f))
        if not reader:
            return "unknown"
        # Find the most recent freshness timestamp
        latest = ""
        for row in reader:
            ts = row.get("created_at_utc", "")
            if ts > latest:
                latest = ts
        if not latest:
            return "unknown"
        # Parse and format
        try:
            dt = datetime.fromisoformat(latest.replace("+00:00", ""))
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            delta = now - dt
            mins = int(delta.total_seconds() / 60)
            if mins < 1:
                return "just now"
            if mins < 60:
                return f"{mins}m ago"
            hours = mins // 60
            if hours < 24:
                return f"{hours}h {mins % 60}m ago"
            return f"{hours // 24}d {hours % 24}h ago"
        except Exception:
            return latest[:16]
    except Exception:
        return "unknown"


def _freshness_color(ts_label: str) -> str:
    """Return a CSS class based on age label."""
    if ts_label == "unknown":
        return "warn"
    if "just now" in ts_label or "m ago" in ts_label:
        try:
            mins = int(ts_label.split("m")[0].split()[-1]) if "m ago" in ts_label else 0
            return "green" if mins < 60 else "warn"
        except Exception:
            return "warn"
    if "h ago" in ts_label:
        try:
            hours = int(ts_label.split("h")[0].split()[-1])
            return "warn" if hours < 6 else "red"
        except Exception:
            return "warn"
    return "red"


def data_freshness_strip() -> str:
    ts = _last_updated_from_freshness()
    cls = _freshness_color(ts)
    return (
        '<div style="display:flex;justify-content:flex-end;align-items:center;gap:8px;'
        'padding:6px 10px 10px;font-size:12px;color:var(--muted);">'
        f'<span>Data updated: <b class="{cls}">{esc(ts)}</b></span>'
        '<a class="nav-pill" href="/validation" style="font-size:11px;padding:3px 8px;">Gates</a>'
        '<a class="nav-pill" href="/dashboard" style="font-size:11px;padding:3px 8px;">Dashboard</a>'
        '</div>'
    )


def progress_bar(label: str, current: int, target: int, cls: str = "") -> str:
    """Render a progress bar showing current/target toward a gate."""
    pct = min(100, int(current / target * 100)) if target > 0 else 0
    return (
        f'<div style="margin:4px 0;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:4px;">'
        f'<span style="font-size:12px;color:var(--muted);">{esc(label)}</span>'
        f'<span style="font-size:12px;font-weight:800;">{current}/{target}</span>'
        f'</div>'
        f'<div class="progress-track"><div class="progress-fill {esc(cls)}" style="width:{pct}%;"></div></div>'
        f'</div>'
    )


def parse_risk_flags(raw: str) -> str:
    """Parse comma-separated risk_flags into individual badge pills."""
    if not raw or raw in ("", "NONE", "None"):
        return '<span class="badge green">CLEAN</span>'
    flag_map = {
        "MANUAL_APPROVAL_REQUIRED": ("warn", "MANUAL APPROVAL"),
        "NO_AUTO_BETTING": ("red", "NO AUTO-BET"),
        "NO_FORMULA_REPLACEMENT": ("red", "NO FORMULA"),
        "THIN_POSITIVE_EDGE": ("yellow", "THIN EDGE"),
        "THIN_NEGATIVE_EDGE": ("yellow", "THIN EDGE"),
        "HIGH_ROTATION_FRAGILITY": ("yellow", "FRAGILE ROTATION"),
        "LOW_MODEL_EDGE": ("gray", "LOW EDGE"),
        "NO_LINE": ("gray", "NO LINE"),
        "NO_SIDE": ("gray", "NO SIDE"),
        "WIDE_MARKET_RANGE": ("yellow", "WIDE RANGE"),
        "NEGATIVE_MODEL_EDGE": ("red", "NEG EDGE"),
        "NEGATIVE_PRICE_EDGE": ("red", "NEG PRICE"),
        "PRICE_EDGE_TOO_SMALL": ("gray", "SMALL EDGE"),
    }
    flags = [f.strip() for f in raw.replace(";", ",").split(",") if f.strip()]
    badges = []
    seen = set()
    for flag in flags:
        if flag in flag_map and flag not in seen:
            cls, label = flag_map[flag]
            badges.append(f'<span class="badge {cls}">{esc(label)}</span>')
            seen.add(flag)
        elif flag not in seen:
            # Unknown flag — show as-is in gray
            badges.append(f'<span class="badge gray">{esc(flag[:24])}</span>')
            seen.add(flag)
    return " ".join(badges) if badges else '<span class="badge green">CLEAN</span>'
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
          <div class="action-clean-grid"><div class="mini"><span>Edge</span><b>{esc(pick(r, 'model_edge', 'edge'))}</b></div><div class="mini"><span>Confidence</span><b>{esc(pick(r, 'confidence'))}</b></div><div class="mini"><span>Approval</span><b>Manual</b></div><div class="mini" style="grid-column:span 1;"><span>Risk</span><div style="margin-top:4px;">{parse_risk_flags(pick(r, 'risk_flags'))}</div></div></div>
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




def route_intro(title: str, subtitle: str, chip: str = "V21.9") -> str:
    return f"<div class=\"section-head route-intro\"><div><h2>{esc(title)}</h2><p>{esc(subtitle)}</p></div><span class=\"chip green\">{esc(chip)}</span></div>"


def executive_kpis(st: Dict[str, Any]) -> str:
    kpis = [
        card("Open Bets", len(st["open_bets"]), f"{st['open_stake']:.2f}u live exposure", "primary"),
        card("Settled P/L", money(st["settled_pl"]), f"{st['wins']}W / {st['losses']}L settled", "primary" if st["settled_pl"] >= 0 else "warn"),
        card("Model Queue", len(st["hermes_queue"] or st["manual_review"]), "manual-market review rows", "primary"),
        card("Odds API", "QUOTA-SAFE" if not st["safe_fetch"].get("odds_ready") else "READY", "paid calls protected", "warn" if not st["safe_fetch"].get("odds_ready") else "primary"),
    ]
    # Model health score from model_health_report.csv
    try:
        health_rows = read_csv(MODEL_HEALTH)
        if health_rows:
            hr = health_rows[-1]  # latest
            score = hr.get("ModelHealthScore", "—")
            label = hr.get("HealthLabel", "—")
            color = "green" if float(score or 0) >= 70 else "warn" if float(score or 0) >= 40 else "red"
            kpis.append(card("Model Health", f"{score} — {label}", f"CLV {hr.get('AvgCLV', '—')} · Win {hr.get('SignalWinRate', '—')}%", color))
    except Exception:
        pass
    return '<div class="v193-summary-grid">' + ''.join(kpis) + '</div>'


def render_home() -> str:
    st = load_state()
    body = route_intro("Command center", "Live operator view: open bets, model queue, bankroll state, and Hermes safety gates.", "manual only")
    body += executive_kpis(st)
    body += section("Open bets", "Tickets already placed and waiting for settlement.", open_bets_html(st), "OPEN")
    body += section("Next model queue", "V21.9 manual-market review rows. Advisory only; no auto-betting.", manual_queue_html(st, 6), "MODEL")
    body += safety_html(st)
    return body


def render_dashboard() -> str:
    st = load_state()
    body = route_intro("Dashboard", "High-signal KPI board for the current betting/model state.", "V21.9 live")
    body += executive_kpis(st)
    body += '<div class="v193-summary-grid">'
    body += card("Execution Tickets", st["signal_summary"].get("execution_tickets", len(st["bets"])), "signal bridge")
    body += card("Signal Groups", st["signal_summary"].get("signal_groups", "—"), "deduped model/execution groups")
    body += card("Open Groups", st["signal_summary"].get("open_groups", len(st["open_bets"])), "execution bridge")
    body += card("Formula Gate", st["gates"].get("current_gate_state", "EVIDENCE_COLLECTION_ONLY"), "promotion blocked", "lock")
    body += '</div>'
    # CLV summary from signal_clv_summary.csv
    try:
        clv_rows = read_csv(OUT / "signal_clv_summary.csv")
        overall = [r for r in clv_rows if r.get("Group") == "Overall"]
        if overall:
            o = overall[0]
            clv_cls = "green" if float(o.get("AvgCLVPoints", 0) or 0) > 0 else "red"
            body += '<div class="v193-summary-grid" style="margin-top:12px;">'
            body += f'<div class="v193-summary-card primary"><span>CLV Summary</span><b class="{clv_cls}">{o.get("AvgCLVPoints", "—")} pts avg</b><p>Beat-close {o.get("BeatCloseRate", "—")}% · {o.get("SignalsWithCLV", "—")} samples</p></div>'
            body += '</div>'
    except Exception:
        pass
    body += section("Live open exposure", "Current OPEN rows in bet_tracker.csv.", open_bets_html(st), "BET TRACKER")
    body += section("Hermes model queue", "Sorted by advisory label and model edge.", manual_queue_html(st, 10), "HERMES")
    return body


def render_actions() -> str:
    st = load_state()
    body = route_intro("Actions", "Action board split between bets already placed and model-reviewed candidates. This page never executes bets.", "operator review")
    body += section("Already placed", "Logged OPEN tickets. Use this to avoid duplicates.", open_bets_html(st), "OPEN BETS")
    body += section("Model-reviewed queue", "Candidate rows from manual market review. Use Hermes/manual approval before any action.", manual_queue_html(st, 18), "ADVISORY")
    return body


def render_hermes() -> str:
    st = load_state()
    body = route_intro("Hermes manual approval", "Hermes can queue, warn, and require approval. It cannot place bets or change staking.", "locked")
    body += safety_html(st)
    # Label count summary
    label_counts = st.get("manual_label_counts", {})
    queue_rows = st["hermes_queue"] or st["manual_review"]
    total = len(queue_rows)
    if label_counts:
        body += '<div class="v193-summary-grid" style="margin-bottom:12px;">'
        body += card("Queue Total", total, "manual-market review rows", "primary")
        for lbl, cnt in sorted(label_counts.items(), key=lambda x: -x[1]):
            cls = "green" if "SUPPORT" in lbl else "warn" if "REVIEW" in lbl else "gray" if "NO_PLAY" in lbl else ""
            body += card(lbl.replace("_", " ").title(), cnt, "rows", cls)
        body += '</div>'
    body += section("Approval queue", "V21.9 manual market queue with labels, edge, confidence, and risk flags.", manual_queue_html(st, 18), "QUEUE")
    body += section("Open operator bets", "Bets already entered by the operator, shown for exposure context.", open_bets_html(st), "OPEN")
    return body


def render_bets() -> str:
    st = load_state()
    body = route_intro("Bet ledger", "Clean ledger view from bet_tracker.csv: open tickets, recent settled results, and duplicate watch.", "ledger")
    body += '<div class="v193-summary-grid">'
    body += card("Open Tickets", len(st["open_bets"]), f"{st['open_stake']:.2f}u exposure", "warn" if st["open_bets"] else "primary")
    body += card("Settled Tickets", len(st["settled"]), f"P/L {money(st['settled_pl'])}", "primary" if st["settled_pl"] >= 0 else "warn")
    body += card("All Tickets", len(st["bets"]), "bet_tracker.csv")
    body += card("Duplicate Watch", len(st["duplicates"]), "should stay 0", "warn" if st["duplicates"] else "primary")
    body += '</div>'
    body += section("Open tickets", "Pending settlement; this is the source of live exposure.", open_bets_html(st), "OPEN")
    body += section("Recent settled", "Latest settled tickets for P/L context.", settled_recent_html(st, 12), "SETTLED")
    return body


def render_bankroll() -> str:
    st = load_state()
    body = route_intro("Bankroll", "Exposure and P/L dashboard. Stake sizing remains manual; no automated staking changes.", "manual stake")
    body += '<div class="v193-summary-grid">'
    body += card("Open Exposure", f"{st['open_stake']:.2f}u", f"{len(st['open_bets'])} open tickets", "warn" if st["open_bets"] else "primary")
    body += card("Settled P/L", money(st["settled_pl"]), f"{st['wins']}W / {st['losses']}L", "primary" if st["settled_pl"] >= 0 else "warn")
    body += card("Bridge P/L", money(st["signal_summary"].get("net_profit", st["settled_pl"])), "signal execution bridge")
    body += card("Total Staked", f"{st['total_stake']:.2f}u", "all tracked tickets")
    body += '</div>'
    body += section("Open exposure detail", "Every currently open ticket.", open_bets_html(st), "RISK")
    body += section("Recent realized P/L", "Recent settled entries.", settled_recent_html(st, 12), "RESULTS")
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
    body = route_intro("Telegram", "Copy-ready operator message generated from V21.9 live state, not legacy telegram_message.txt.", "copy")
    body += f"<section class=\"panel\"><pre style=\"white-space:pre-wrap;font-family:var(--font-mono);line-height:1.7\">{esc(text)}</pre></section>"
    return body


def render_validation() -> str:
    st = load_state()
    body = route_intro("Validation", "Evidence collection and formula-promotion gates. This page validates; it does not change formulas.", "evidence only")
    body += '<div class="v193-summary-grid">'
    body += card("Tracking Rows", st["result_rows"].get("tracking", 0), "V21.9 result tracker")
    body += card("Known Results", st["result_rows"].get("known_results", 0), "current advisory rows")
    body += card("CLV Samples", st["result_rows"].get("clv_samples", 0), "current advisory rows")
    body += card("Formula Change", "BLOCKED", st["gates"].get("current_gate_state", "EVIDENCE_COLLECTION_ONLY"), "lock")
    body += '</div>'
    # Progress bars toward formula promotion gates
    known = st["result_rows"].get("known_results", 0)
    tracking = st["result_rows"].get("tracking", 0)
    clv_samples = st["result_rows"].get("clv_samples", 0)
    settled = len(st["settled"])
    body += '<div class="v193-summary-grid" style="margin-top:12px;">'
    body += '<div class="v193-summary-card lock" style="grid-column:1/-1;">'
    body += '<span>Formula Promotion Gates</span>'
    body += progress_bar("Settled Results (formula)", settled, 30, "red" if settled < 15 else "warn" if settled < 30 else "green")
    body += progress_bar("Known Results (formula)", known, 30, "red" if known < 15 else "warn" if known < 30 else "green")
    body += progress_bar("Known Results (thresholds)", known, 50, "red" if known < 25 else "warn" if known < 50 else "green")
    body += progress_bar("Tracking Rows", tracking, 30, "red" if tracking < 15 else "warn" if tracking < 30 else "green")
    body += progress_bar("CLV Samples", clv_samples, 20, "red" if clv_samples < 10 else "warn" if clv_samples < 20 else "green")
    body += '</div>'
    body += '</div>'
    body += section("Current model queue labels", "Review labels for the manual market slate.", manual_queue_html(st, 18), "QUEUE")
    body += safety_html(st)
    body += file_state_html(st)
    return body


def render_menu() -> str:
    st = load_state()
    links = [
        ("Dashboard", "/dashboard", "KPI board and state summary"),
        ("Actions", "/actions", "Open bets and model-reviewed candidates"),
        ("Hermes", "/hermes", "Manual approval queue and locks"),
        ("Bets", "/bets", "Open/settled bet ledger"),
        ("Bankroll", "/bankroll", "P/L, exposure, stake totals"),
        ("Telegram", "/telegram", "Copy-ready operator message"),
        ("Validation", "/validation", "Evidence gates and sample status"),
        ("Version", "/version", "Deployment marker"),
    ]
    cards = ''.join(f'<a class="v19-card" href="{href}"><span>V21.9</span><b>{esc(name)}</b><p>{esc(desc)}</p></a>' for name, href, desc in links)
    body = route_intro("Menu", "Route launcher. Every route reads the same V21.9 state layer.", "live")
    body += '<div class="v193-summary-grid">'
    body += card("Open Bets", len(st["open_bets"]), f"{st['open_stake']:.2f}u exposure", "primary")
    body += card("Settled P/L", money(st["settled_pl"]), "bet tracker", "primary" if st["settled_pl"] >= 0 else "warn")
    body += card("Queue Rows", len(st["hermes_queue"] or st["manual_review"]), "manual market review")
    body += '</div>'
    body += f'<div class="v19-grid-4">{cards}</div>'
    return body
