"""
WNBA Edge Lab V21.9 — website state layer.

Single source of truth for public Flask routes. Display-only:
- no model formula changes
- no staking changes
- no threshold changes
- no auto-betting
- no bet creation/editing

Reads current artifacts and renders live state for app.py routes.
All helper functions are pure. Risk flags are parsed into visual badge pills.
Raw flag strings are never shown to the operator.
"""
from __future__ import annotations

import csv
import html
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

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


def _invalid_game(game: str) -> bool:
    """Return True if the game field is blank, nan, None, or otherwise invalid."""
    if not game:
        return True
    g = str(game).strip().lower()
    return g in ("", "nan", "none", "null") or "@" not in g


def _is_actionable_queue_row(row: Dict[str, str]) -> Tuple[bool, List[str]]:
    """Determine whether a queue row should be shown as actionable.

    Returns (is_actionable, list_of_reasons_if_not).
    Rules: invalid game, NO_LINE flag, stale (>48h), past date, is_stale=true.
    """
    reasons: List[str] = []

    # 1. Invalid game
    game = row.get("game", "")
    if _invalid_game(game):
        reasons.append("invalid-game")

    # 2. NO_LINE risk flag
    flags = row.get("risk_flags", "").upper()
    if "NO_LINE" in flags:
        reasons.append("no-line")

    # 3. Stale by created_at_utc (> 48 hours)
    created = row.get("created_at_utc", "")
    if created:
        try:
            created_clean = created.replace("Z", "+00:00")
            dt = datetime.fromisoformat(created_clean).replace(tzinfo=timezone.utc)
            age_hours = (datetime.now(timezone.utc) - dt).total_seconds() / 3600.0
            if age_hours > 48:
                reasons.append(f"stale-{age_hours:.0f}h")
        except Exception:
            pass

    # 4. Date is before today UTC
    row_date = row.get("date", "")
    if row_date:
        try:
            today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            if row_date < today_utc:
                reasons.append(f"past-date({row_date})")
        except Exception:
            pass

    # 5. Explicit is_stale flag
    stale_flag = str(row.get("is_stale", "")).strip().lower()
    if stale_flag in ("true", "1", "yes"):
        reasons.append("is-stale")

    # 6. Actionable labels are only LEAN_SUPPORT or MANUAL_REVIEW
    label = row.get("advisory_label", "").upper()
    if label not in ("LEAN_SUPPORT", "MANUAL_REVIEW"):
        reasons.append(f"label={label[:20]}")

    return (len(reasons) == 0, reasons)


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

    seen: Dict[tuple, str] = {}
    dupes: List[tuple] = []
    for r in bets:
        key = tuple((r.get(k) or "").strip().upper()
                     for k in ["Date", "Game", "Market", "Direction", "Line", "Odds", "Status"])
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
        "bets": bets, "open_bets": open_bets, "settled": settled,
        "open_stake": open_stake, "settled_pl": settled_pl, "total_stake": total_stake,
        "wins": wins, "losses": losses, "duplicates": dupes,
        "safe": safe, "safe_fetch": safe_fetch, "locks": locks,
        "signal_execution": sig, "signal_summary": sig_summary,
        "manual_review": review, "hermes_queue": hermes_queue,
        "manual_summary": manual_summary, "manual_label_counts": label_counts,
        "result_summary": result_summary, "result_rows": result_rows, "gates": gates,
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
    try:
        if not DATA_FRESHNESS.exists():
            return "unknown"
        rows = read_csv(DATA_FRESHNESS)
        if not rows:
            return "unknown"
        latest = max((r.get("created_at_utc", "") for r in rows), default="")
        if not latest:
            return "unknown"
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
    if ts_label == "unknown":
        return "warn"
    if "just now" in ts_label:
        return "green"
    if "m ago" in ts_label:
        try:
            mins = int(ts_label.split("m")[0].split()[-1])
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


def badge(label: str, cls: str = "") -> str:
    return f'<span class="chip {esc(cls)}">{esc(label)}</span>'


def card(title: str, value: Any, note: str = "", cls: str = "") -> str:
    return (
        f'<div class="v193-summary-card {esc(cls)}">'
        f'<span>{esc(title)}</span><b>{esc(str(value))}</b><p>{esc(note)}</p></div>'
    )


def section(title: str, subtitle: str, inner: str, chip: str = "V21.9") -> str:
    return (
        f'<section class="panel"><div class="section-head" style="margin-top:0">'
        f'<div><h2>{esc(title)}</h2><p>{esc(subtitle)}</p></div>'
        f'<span class="chip">{esc(chip)}</span></div>{inner}</section>'
    )


def progress_bar(label: str, current: int, target: int, cls: str = "") -> str:
    pct = min(100, int(current / target * 100)) if target > 0 else 0
    return (
        f'<div class="progress-bar-item">'
        f'<div class="progress-bar-labels"><span>{esc(label)}</span>'
        f'<span class="progress-val">{current}/{target}</span></div>'
        f'<div class="progress-track"><div class="progress-fill {esc(cls)}" '
        f'style="width:{pct}%;"></div></div></div>'
    )


def parse_risk_flags(raw: str) -> str:
    """Parse semicolon- or comma-separated risk_flags into badge pills. Raw text is never shown."""
    if not raw or raw.strip() in ("", "NONE", "None"):
        return '<span class="badge green">CLEAN</span>'
    FLAG_MAP: Dict[tuple, tuple] = {
        ("MANUAL_APPROVAL_REQUIRED",): ("warn", "MANUAL APPROVAL"),
        ("NO_AUTO_BETTING",): ("red", "NO AUTO-BET"),
        ("NO_FORMULA_REPLACEMENT",): ("red", "NO FORMULA"),
        ("NO_STAKING_CHANGES",): ("red", "NO STAKING"),
        ("NO_THRESHOLD_CHANGES",): ("red", "NO THRESHOLD"),
        ("THIN_POSITIVE_EDGE", "THIN_EDGE"): ("yellow", "THIN EDGE"),
        ("THIN_NEGATIVE_EDGE",): ("yellow", "THIN EDGE"),
        ("HIGH_ROTATION_FRAGILITY",): ("yellow", "FRAGILE"),
        ("LOW_MODEL_EDGE",): ("gray", "LOW EDGE"),
        ("NO_LINE",): ("gray", "NO LINE"),
        ("WIDE_MARKET_RANGE",): ("yellow", "WIDE RANGE"),
        ("NEGATIVE_MODEL_EDGE",): ("red", "NEG EDGE"),
        ("NEGATIVE_PRICE_EDGE",): ("red", "NEG PRICE"),
        ("PRICE_EDGE_TOO_SMALL", "SMALL_EDGE"): ("gray", "SMALL EDGE"),
    }
    flags = [f.strip() for f in raw.replace(";", ",").split(",") if f.strip()]
    badges: List[str] = []
    seen: set = set()
    for flag in flags:
        if flag in seen:
            continue
        seen.add(flag)
        matched = False
        for keys, (cls, label) in FLAG_MAP.items():
            if flag in keys:
                badges.append(f'<span class="badge {cls}">{esc(label)}</span>')
                matched = True
                break
        if not matched:
            badges.append(f'<span class="badge gray">{esc(flag[:24])}</span>')
    return " ".join(badges) if badges else '<span class="badge green">CLEAN</span>'


def data_freshness_strip() -> str:
    ts = _last_updated_from_freshness()
    cls = _freshness_color(ts)
    return (
        '<div class="data-freshness-strip">'
        f'<span>Data updated: <b class="{cls}">{esc(ts)}</b></span>'
        '<a class="nav-pill" href="/validation" '
        'style="font-size:11px;padding:3px 8px;">Gates</a>'
        '<a class="nav-pill" href="/dashboard" '
        'style="font-size:11px;padding:3px 8px;">Dashboard</a></div>'
    )


def top_state_strip(st: Dict[str, Any]) -> str:
    return (
        '<section class="v192-command-strip">'
        '<div class="v192-chip-card"><span>Version</span><b>V21.9</b><p>Live state layer</p></div>'
        f'<div class="v192-chip-card"><span>Open Bets</span><b>{len(st["open_bets"])}</b>'
        f'<p>{st["open_stake"]:.2f}u exposure</p></div>'
        f'<div class="v192-chip-card"><span>Settled P/L</span><b>{money(st["settled_pl"])}</b>'
        f'<p>Bet tracker</p></div>'
        '<div class="v192-chip-card"><span>Automation</span><b>Manual</b><p>No auto-betting</p></div>'
        f'<div class="v192-chip-card"><span>Odds API</span>'
        f'<b>{"READY" if st["safe_fetch"].get("odds_ready") else "QUOTA-SAFE"}</b>'
        f'<p>Paid calls skipped</p></div>'
        "</section>"
    )


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
        edge_cls = "green" if num(edge) > 0 else "red" if num(edge) < 0 else ""
        out.append(
            f'<div class="action-clean-card">'
            f'<div class="action-clean-head"><div>'
            f'<div class="action-rank-clean">{esc(pick(r, "BetID"))} · OPEN</div>'
            f'<div class="action-clean-title">{esc(pick(r, "Game"))}</div>'
            f'</div><span class="badge green">{esc(sig)}</span></div>'
            f'<div class="action-clean-bet">{esc(subtitle)} @ {esc(odds)}</div>'
            f'<div class="action-clean-grid">'
            f'<div class="mini"><span>Stake</span><b>{esc(stake)}u</b></div>'
            f'<div class="mini"><span>Edge</span><b class="{edge_cls}">{esc(edge or "—")}</b></div>'
            f'<div class="mini"><span>Confidence</span><b>{esc(conf or "—")}</b></div>'
            f'<div class="mini"><span>Status</span><b>OPEN</b></div>'
            "</div></div>"
        )
    return '<div class="action-board">' + "".join(out) + "</div>"


def manual_queue_html(st: Dict[str, Any], limit: int = 12) -> str:
    rows = st["hermes_queue"] or st["manual_review"]
    if not rows:
        return (
            '<div class="v193-page-note"><b>No V21.9 manual market queue found.</b> '
            "Run manual_market_snapshot_v21_9.py and model_manual_market_review_v21_9.py.</div>"
        )
    # Separate actionable from non-actionable.
    # Primary gate: source-level queue_actionability if present.
    # Fallback: _is_actionable_queue_row() for rows without the field.
    NON_ACTIONABLE = {
        "SCHEDULE_UNVERIFIED_TODAY", "SCHEDULE_UNVERIFIED_FUTURE",
        "HIDDEN_NO_SCHEDULE", "HIDDEN_NO_LINE", "HIDDEN_STALE",
        "HIDDEN_INVALID", "HIDDEN_LABEL", "UNKNOWN",
    }
    actionable: List[Dict[str, str]] = []
    hidden_count = 0
    hidden_actionability: Dict[str, int] = {}
    for r in rows:
        src_action = str(r.get("queue_actionability", "")).strip().upper()
        if src_action:
            if src_action == "ACTIONABLE":
                actionable.append(r)
            else:
                hidden_count += 1
                hidden_actionability[src_action] = hidden_actionability.get(src_action, 0) + 1
        else:
            # Fallback to display-layer rules when source field missing.
            is_ok, _ = _is_actionable_queue_row(r)
            if is_ok:
                actionable.append(r)
            else:
                hidden_count += 1
                hidden_actionability["display_rules"] = hidden_actionability.get("display_rules", 0) + 1
    if not actionable:
        hidden_note = ""
        if hidden_count:
            parts = ", ".join(f"{k}: {v}" for k, v in sorted(hidden_actionability.items()))
            hidden_note = (
                f'<div class="v193-page-note" style="margin-top:8px">'
                f'<b>No actionable picks.</b> {hidden_count} row(s) hidden: {parts}.</div>'
            )
        return (
            '<div class="v193-page-note"><b>No actionable model queue rows.</b> '
            "All rows filtered by freshness/risk gates.</div>" + hidden_note
        )
    def sort_key(r: Dict[str, str]):
        label = pick(r, "advisory_label", default="")
        rank = {"LEAN_SUPPORT": 0, "MANUAL_REVIEW": 1, "NO_PLAY": 2}.get(label, 9)
        return (rank, -num(pick(r, "model_edge", "edge", default="0")))
    actionable = sorted(actionable, key=sort_key)[:limit]
    out = []
    for i, r in enumerate(actionable, 1):
        label = pick(r, "advisory_label", default="MANUAL_REVIEW")
        label_cls = "green" if label == "LEAN_SUPPORT" else "warn" if label == "MANUAL_REVIEW" else "gray"
        line = pick(r, "line")
        edge = pick(r, "model_edge", "edge")
        edge_cls = "green" if num(edge) > 0 else "red" if num(edge) < 0 else ""
        cl = pick(r, "confidence")
        risk_badges = parse_risk_flags(pick(r, "risk_flags"))
        out.append(
            f'<div class="action-clean-card queue-card">'
            f'<div class="action-clean-head"><div>'
            f'<div class="action-rank-clean">#{i:02d} MODEL QUEUE</div>'
            f'<div class="action-clean-title">{esc(pick(r, "game"))}</div>'
            f'</div><span class="badge {label_cls}">{esc(label)}</span></div>'
            f'<div class="action-clean-bet">{esc(pick(r, "market"))} · {esc(pick(r, "side"))}'
            f'{" " + esc(line) if line else ""} @ {esc(pick(r, "odds_decimal", "odds"))}</div>'
            f'<div class="action-clean-grid">'
            f'<div class="mini"><span>Edge</span><b class="{edge_cls}">{esc(edge)}</b></div>'
            f'<div class="mini"><span>Confidence</span><b>{esc(cl)}</b></div>'
            f'<div class="mini"><span>Approval</span><b>Manual</b></div>'
            f'<div class="mini risk-mini">'
            f'<span>Risk</span>'
            f'<div class="risk-badges">{risk_badges}</div>'
            f"</div></div></div>"
        )
    if hidden_count:
        parts = ", ".join(f"{k}: {v}" for k, v in sorted(hidden_actionability.items()))
        out.append(
            f'<div class="v193-page-note" style="margin-top:8px">'
            f'<b>Hidden non-actionable rows:</b> {hidden_count} ({parts}).</div>'
        )
    return '<div class="action-board">' + "".join(out) + "</div>"


def settled_recent_html(st: Dict[str, Any], limit: int = 10) -> str:
    rows = list(reversed(st["settled"]))[:limit]
    if not rows:
        return '<div class="v193-page-note">No settled bets found.</div>'
    items = []
    for r in rows:
        pl = num(r.get("P/L"))
        cls = "green" if pl > 0 else "red" if pl < 0 else "gray"
        items.append(
            f'<div class="validation-row-lite">'
            f'<div><span>{esc(pick(r, "BetID"))} · {esc(pick(r, "Market"))}</span>'
            f'<b>{esc(pick(r, "Game"))}</b></div>'
            f'<em>{esc(pick(r, "Direction"))} {esc(pick(r, "Line"))} @ {esc(pick(r, "Odds"))}</em>'
            f'<b>{esc(pick(r, "Result"))}</b>'
            f'<b class="{cls}">{money(pl)}</b></div>'
        )
    return '<div class="validation-compact-list">' + "".join(items) + "</div>"


def safety_html(st: Dict[str, Any]) -> str:
    locks = st["locks"] or [
        "MANUAL_APPROVAL_REQUIRED", "NO_AUTO_BETTING",
        "NO_FORMULA_REPLACEMENT", "NO_STAKING_CHANGES", "NO_THRESHOLD_CHANGES",
    ]
    lock_html = "".join(f'<span class="approval-pill locked">{esc(x)}</span>' for x in locks)
    fetch = st["safe_fetch"]
    if fetch:
        readiness = "".join(
            card(k.replace("_", " "), "YES" if v else "NO", "readiness",
                 "primary" if v else "warn")
            for k, v in sorted(fetch.items())
        )
    else:
        readiness = card("Fetch", "Unknown", "summary not found", "warn")
    return section(
        "Safety & readiness",
        "Current automation gates and data source readiness.",
        f'<div class="approval-rail">{lock_html}</div>'
        f'<div class="v193-summary-grid">{readiness}</div>',
        "NO AUTO-BETTING",
    )


def file_state_html(st: Dict[str, Any]) -> str:
    cells = []
    for name, ok in st["files"].items():
        cells.append(card(name, "OK" if ok else "MISSING", "required V21.9 artifact",
                          "primary" if ok else "warn"))
    dup_note = card("Duplicate bet keys", len(st["duplicates"]),
                    "audit watch only", "warn" if st["duplicates"] else "primary")
    return section(
        "Code/data wiring", "Files the website is using now.",
        '<div class="v193-summary-grid">' + "".join(cells) + dup_note + "</div>",
        "single source",
    )


def route_intro(title: str, subtitle: str, chip: str = "V21.9") -> str:
    return (
        f'<div class="section-head route-intro">'
        f'<div><h2>{esc(title)}</h2><p>{esc(subtitle)}</p></div>'
        f'<span class="chip green">{esc(chip)}</span></div>'
    )


def executive_kpis(st: Dict[str, Any]) -> str:
    kpis = [
        card("Open Bets", len(st["open_bets"]),
             f"{st['open_stake']:.2f}u live exposure", "primary"),
        card("Settled P/L", money(st["settled_pl"]),
             f"{st['wins']}W / {st['losses']}L settled",
             "primary" if st["settled_pl"] >= 0 else "warn"),
        card("Model Queue", len(st["hermes_queue"] or st["manual_review"]),
             "manual-market review rows", "primary"),
        card("Odds API",
             "QUOTA-SAFE" if not st["safe_fetch"].get("odds_ready") else "READY",
             "paid calls protected",
             "warn" if not st["safe_fetch"].get("odds_ready") else "primary"),
    ]
    try:
        health_rows = read_csv(MODEL_HEALTH)
        if health_rows:
            hr = health_rows[-1]
            score = hr.get("ModelHealthScore", "—")
            label = hr.get("HealthLabel", "—")
            color = "green" if float(score or 0) >= 70 else "warn" if float(score or 0) >= 40 else "red"
            kpis.append(card(
                "Model Health", f"{score} — {label}",
                f"CLV {hr.get('AvgCLV', '—')} · Win {hr.get('SignalWinRate', '—')}%",
                color,
            ))
    except Exception:
        pass
    return '<div class="v193-summary-grid">' + "".join(kpis) + "</div>"


def render_home() -> str:
    st = load_state()
    body = route_intro("Command center",
        "Live operator view: open bets, model queue, bankroll state, and Hermes safety gates.",
        "manual only")
    body += executive_kpis(st)
    body += section("Open bets", "Tickets already placed and waiting for settlement.",
                    open_bets_html(st), "OPEN")
    body += section("Next model queue",
        "V21.9 manual-market review rows. Advisory only; no auto-betting.",
        manual_queue_html(st, 6), "MODEL")
    body += safety_html(st)
    return body


def render_dashboard() -> str:
    st = load_state()
    body = route_intro("Dashboard",
        "High-signal KPI board for the current betting/model state.", "V21.9 live")
    body += executive_kpis(st)
    body += '<div class="v193-summary-grid">'
    body += card("Execution Tickets",
                 st["signal_summary"].get("execution_tickets", len(st["bets"])),
                 "signal bridge")
    body += card("Signal Groups",
                 st["signal_summary"].get("signal_groups", "—"),
                 "deduped model/execution groups")
    body += card("Open Groups",
                 st["signal_summary"].get("open_groups", len(st["open_bets"])),
                 "execution bridge")
    body += card("Formula Gate",
                 st["gates"].get("current_gate_state", "EVIDENCE_COLLECTION_ONLY"),
                 "promotion blocked", "lock")
    body += "</div>"
    try:
        clv_rows = read_csv(OUT / "signal_clv_summary.csv")
        overall = [r for r in clv_rows if r.get("Group") == "Overall"]
        if overall:
            o = overall[0]
            clv_cls = "green" if float(o.get("AvgCLVPoints", 0) or 0) > 0 else "red"
            body += '<div class="v193-summary-grid" style="margin-top:12px;">'
            body += (
                f'<div class="v193-summary-card primary"><span>CLV Summary</span>'
                f'<b class="{clv_cls}">{o.get("AvgCLVPoints", "—")} pts avg</b>'
                f'<p>Beat-close {o.get("BeatCloseRate", "—")}% · '
                f'{o.get("SignalsWithCLV", "—")} samples</p></div>'
            )
            body += "</div>"
    except Exception:
        pass
    body += section("Live open exposure", "Current OPEN rows in bet_tracker.csv.",
                    open_bets_html(st), "BET TRACKER")
    body += section("Hermes model queue", "Sorted by advisory label and model edge.",
                    manual_queue_html(st, 10), "HERMES")
    return body


def render_actions() -> str:
    st = load_state()
    body = route_intro("Actions",
        "Action board split between bets already placed and model-reviewed candidates. "
        "This page never executes bets.", "operator review")
    body += section("Already placed", "Logged OPEN tickets. Use this to avoid duplicates.",
                    open_bets_html(st), "OPEN BETS")
    body += section("Model-reviewed queue",
        "Candidate rows from manual market review. Use Hermes/manual approval before any action.",
        manual_queue_html(st, 18), "ADVISORY")
    return body


def render_hermes() -> str:
    st = load_state()
    body = route_intro("Hermes manual approval",
        "Hermes can queue, warn, and require approval. It cannot place bets or change staking.",
        "locked")
    body += safety_html(st)
    label_counts = st.get("manual_label_counts", {})
    queue_rows = st["hermes_queue"] or st["manual_review"]
    total = len(queue_rows)
    if label_counts:
        body += '<div class="v193-summary-grid" style="margin-bottom:12px;">'
        body += card("Queue Total", total, "manual-market review rows", "primary")
        for lbl, cnt in sorted(label_counts.items(), key=lambda x: -x[1]):
            cls = ("green" if "SUPPORT" in lbl else
                   "warn" if "REVIEW" in lbl else
                   "gray" if "NO_PLAY" in lbl else "")
            body += card(lbl.replace("_", " ").title(), cnt, "rows", cls)
        body += "</div>"
    body += section("Approval queue",
        "V21.9 manual market queue with labels, edge, confidence, and parsed risk badges.",
        manual_queue_html(st, 18), "QUEUE")
    body += section("Open operator bets",
        "Bets already entered by the operator, shown for exposure context.",
        open_bets_html(st), "OPEN")
    return body


def render_bets() -> str:
    st = load_state()
    body = route_intro("Bet ledger",
        "Clean ledger view from bet_tracker.csv: open tickets, recent settled results, "
        "and duplicate watch.", "ledger")
    body += '<div class="v193-summary-grid">'
    body += card("Open Tickets", len(st["open_bets"]),
                 f"{st['open_stake']:.2f}u exposure",
                 "warn" if st["open_bets"] else "primary")
    body += card("Settled Tickets", len(st["settled"]),
                 f"P/L {money(st['settled_pl'])}",
                 "primary" if st["settled_pl"] >= 0 else "warn")
    body += card("All Tickets", len(st["bets"]), "bet_tracker.csv")
    body += card("Duplicate Watch", len(st["duplicates"]),
                 "should stay 0", "warn" if st["duplicates"] else "primary")
    body += "</div>"
    body += section("Open tickets",
        "Pending settlement; this is the source of live exposure.",
        open_bets_html(st), "OPEN")
    body += section("Recent settled", "Latest settled tickets for P/L context.",
                    settled_recent_html(st, 12), "SETTLED")
    return body


def render_bankroll() -> str:
    st = load_state()
    body = route_intro("Bankroll",
        "Exposure and P/L dashboard. Stake sizing remains manual; no automated staking changes.",
        "manual stake")
    body += '<div class="v193-summary-grid">'
    body += card("Open Exposure", f"{st['open_stake']:.2f}u",
                 f"{len(st['open_bets'])} open tickets",
                 "warn" if st["open_bets"] else "primary")
    body += card("Settled P/L", money(st["settled_pl"]),
                 f"{st['wins']}W / {st['losses']}L",
                 "primary" if st["settled_pl"] >= 0 else "warn")
    bridge_pl = st["signal_summary"].get("net_profit", st["settled_pl"])
    bridge_cls = "green" if num(bridge_pl) > 0 else "red" if num(bridge_pl) < 0 else ""
    body += card("Bridge P/L", money(bridge_pl), "signal execution bridge", bridge_cls)
    body += card("Total Staked", f"{st['total_stake']:.2f}u", "all tracked tickets")
    body += "</div>"
    body += section("Open exposure detail", "Every currently open ticket.",
                    open_bets_html(st), "RISK")
    body += section("Recent realized P/L", "Recent settled entries.",
                    settled_recent_html(st, 12), "RESULTS")
    return body


def render_telegram() -> str:
    st = load_state()
    lines = [
        "WNBA EDGE LAB V21.9 — MANUAL ONLY",
        f"Open bets: {len(st['open_bets'])} / exposure {st['open_stake']:.2f}u",
        f"Settled P/L: {money(st['settled_pl'])}",
        "Safety: NO_AUTO_BETTING · MANUAL_APPROVAL_REQUIRED · NO_FORMULA_REPLACEMENT",
        "", "OPEN BETS:",
    ]
    for r in st["open_bets"]:
        ln = pick(r, "Line")
        lines.append(
            f"- {pick(r,'Game')} | {pick(r,'Market')} {pick(r,'Direction')} {ln} "
            f"@ {pick(r,'Odds')} | {pick(r,'Stake')}u | "
            f"{pick(r,'FinalSignal','Signal', default='MANUAL')}"
        )
    lines += ["", "MODEL QUEUE:"]
    raw_queue = st["hermes_queue"] or st["manual_review"]
    # Use source-level queue_actionability as primary gate.
    NON_ACTIONABLE = {
        "SCHEDULE_UNVERIFIED_TODAY", "SCHEDULE_UNVERIFIED_FUTURE",
        "HIDDEN_NO_SCHEDULE", "HIDDEN_NO_LINE", "HIDDEN_STALE",
        "HIDDEN_INVALID", "HIDDEN_LABEL", "UNKNOWN",
    }
    actionable_queue = []
    hidden_queue_count = 0
    hidden_actionability: Dict[str, int] = {}
    for r in raw_queue:
        src = str(r.get("queue_actionability", "")).strip().upper()
        if src:
            if src == "ACTIONABLE":
                actionable_queue.append(r)
            else:
                hidden_queue_count += 1
                hidden_actionability[src] = hidden_actionability.get(src, 0) + 1
        else:
            # Fallback: display-layer rules.
            is_ok, _ = _is_actionable_queue_row(r)
            if is_ok:
                actionable_queue.append(r)
            else:
                hidden_queue_count += 1
                hidden_actionability["display_rules"] = hidden_actionability.get("display_rules", 0) + 1
    if not actionable_queue:
        lines.append("  No actionable model picks after source freshness/risk filtering.")
        if hidden_queue_count:
            parts = ", ".join(f"{k}: {v}" for k, v in sorted(hidden_actionability.items()))
            lines.append(f"  Hidden non-actionable rows: {hidden_queue_count} ({parts}).")
    else:
        for r in actionable_queue[:8]:
            lines.append(
                f"- {pick(r,'advisory_label', default='REVIEW')} | {pick(r,'game')} | "
                f"{pick(r,'market')} {pick(r,'side')} {pick(r,'line')} @ "
                f"{pick(r,'odds_decimal','odds')} | edge {pick(r,'model_edge','edge')} | "
                f"conf {pick(r,'confidence')}"
            )
        if hidden_queue_count:
            parts = ", ".join(f"{k}: {v}" for k, v in sorted(hidden_actionability.items()))
            lines.append(f"")
            lines.append(f"Hidden non-actionable rows: {hidden_queue_count} ({parts}).")
    text = "\n".join(lines)
    body = route_intro("Telegram",
        "Copy-ready operator message generated from V21.9 live state, "
        "not legacy telegram_message.txt.", "copy")
    body += (
        f'<section class="panel"><pre style="white-space:pre-wrap;'
        f'font-family:var(--font-mono);line-height:1.7">{esc(text)}</pre></section>'
    )
    return body


def render_validation() -> str:
    st = load_state()
    body = route_intro("Validation",
        "Evidence collection and formula-promotion gates. This page validates; "
        "it does not change formulas.", "evidence only")
    body += '<div class="v193-summary-grid">'
    body += card("Tracking Rows", st["result_rows"].get("tracking", 0),
                 "V21.9 result tracker")
    body += card("Known Results", st["result_rows"].get("known_results", 0),
                 "current advisory rows")
    body += card("CLV Samples", st["result_rows"].get("clv_samples", 0),
                 "current advisory rows")
    body += card("Formula Change", "BLOCKED",
                 st["gates"].get("current_gate_state", "EVIDENCE_COLLECTION_ONLY"), "lock")
    body += "</div>"
    # Gate progress bars
    known = st["result_rows"].get("known_results", 0)
    tracking = st["result_rows"].get("tracking", 0)
    clv_samples = st["result_rows"].get("clv_samples", 0)
    settled = len(st["settled"])
    decided = st["result_rows"].get("decided_results", 0)
    body += '<div class="v193-summary-grid gates-grid">'
    body += '<div class="v193-summary-card lock gates-card">'
    body += '<span class="gates-title">Formula Promotion Gates</span>'
    body += progress_bar("Settled Results (formula gate)", settled, 30,
                         "red" if settled < 15 else "warn" if settled < 30 else "green")
    body += progress_bar("Known Results (formula gate)", known, 30,
                         "red" if known < 15 else "warn" if known < 30 else "green")
    body += progress_bar("Known Results (threshold gate)", known, 50,
                         "red" if known < 25 else "warn" if known < 50 else "green")
    body += progress_bar("Tracking Rows", tracking, 30,
                         "red" if tracking < 15 else "warn" if tracking < 30 else "green")
    body += progress_bar("CLV Samples", clv_samples, 20,
                         "red" if clv_samples < 10 else "warn" if clv_samples < 20 else "green")
    body += progress_bar("Decided Results", decided, 30,
                         "red" if decided < 15 else "warn" if decided < 30 else "green")
    body += "</div></div>"
    body += section("Current model queue labels",
        "Review labels for the manual market slate.",
        manual_queue_html(st, 18), "QUEUE")
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
    cards = "".join(
        f'<a class="v19-card" href="{href}"><span>V21.9</span>'
        f'<b>{esc(name)}</b><p>{esc(desc)}</p></a>'
        for name, href, desc in links
    )
    body = route_intro("Menu",
        "Route launcher. Every route reads the same V21.9 state layer.", "live")
    body += '<div class="v193-summary-grid">'
    body += card("Open Bets", len(st["open_bets"]),
                 f"{st['open_stake']:.2f}u exposure", "primary")
    body += card("Settled P/L", money(st["settled_pl"]), "bet tracker",
                 "primary" if st["settled_pl"] >= 0 else "warn")
    body += card("Queue Rows",
                 len(st["hermes_queue"] or st["manual_review"]), "manual market review")
    body += "</div>"
    body += f'<div class="v19-grid-4">{cards}</div>'
    return body


# ── Portfolio-risk view helpers ─────────────────────────────────────

HERMES_ADVISORY = OUT / "hermes_advisory_queue_v21.csv"


def _market_type(market: str) -> str:
    """Classify a market string into totals / spreads / moneyline / props / unknown."""
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


def _open_status(status: str) -> str:
    """Classify bet Status into OPEN / SETTLED / UNKNOWN_OPEN_STATUS / AMBIGUOUS."""
    s = str(status).strip().upper()
    if s in ("OPEN", "PENDING", "ACTIVE"):
        return "OPEN"
    if s in ("SETTLED", "WON", "LOST", "PUSH", "CANCELLED", "VOID"):
        return "SETTLED"
    if s == "":
        return "UNKNOWN_OPEN_STATUS"
    return "AMBIGUOUS"


def _settle_marker(b: Dict[str, str]) -> bool:
    """Return True if a bet_tracker row shows clear settlement evidence."""
    status = str(b.get("Status", "")).strip().upper()
    result = str(b.get("Result", "")).strip().upper()
    pl = str(b.get("P/L", "")).strip()
    actual = str(b.get("Actual", "")).strip()
    if status in ("SETTLED", "WON", "LOST", "PUSH", "CANCELLED", "VOID"):
        return True
    if result and result not in ("", "NAN", "NONE", "NULL"):
        return True
    if pl and pl not in ("", "0", "0.0", "nan", "None"):
        return True
    if actual and actual not in ("", "NAN", "NONE", "NULL"):
        return True
    return False


def _is_open_bet(b: Dict[str, str]) -> str:
    """Determine if a bet_tracker row should count as open exposure.

    Returns: "OPEN", "UNKNOWN_OPEN_STATUS", or "NOT_OPEN".
    """
    settled = _settle_marker(b)
    if settled:
        return "NOT_OPEN"

    status = str(b.get("Status", "")).strip()
    os = _open_status(status)
    if os == "OPEN":
        return "OPEN"
    if os == "UNKNOWN_OPEN_STATUS":
        return "UNKNOWN_OPEN_STATUS"
    return "NOT_OPEN"


def _detect_ladders(bets: List[Dict[str, str]]) -> List[Dict[str, Any]]:
    """Detect same-game + same-market-type + same-direction bets at different lines.

    Returns list of ladder dicts with keys: game, market_type, direction, lines, count.
    """
    groups: Dict[tuple, List[Dict[str, str]]] = {}
    for b in bets:
        game = b.get("Game", "").strip()
        mtype = _market_type(b.get("Market", ""))
        direction = b.get("Direction", "").strip()
        line = b.get("Line", "").strip()
        if game and line:
            key = (game, mtype, direction)
            if key not in groups:
                groups[key] = []
            groups[key].append(b)

    ladders = []
    for (game, mtype, direction), members in groups.items():
        lines = []
        seen_lines = set()
        for b in members:
            ln = b.get("Line", "").strip()
            if ln and ln not in seen_lines:
                lines.append(ln)
                seen_lines.add(ln)
        if len(lines) >= 2:
            ladders.append({
                "game": game,
                "market_type": mtype,
                "direction": direction,
                "lines": lines,
                "count": len(members),
            })
    return ladders


def render_portfolio_risk() -> str:
    """READ-ONLY daily portfolio-risk view. No writes. No formula changes.

    Reads bet_tracker.csv for open exposure and hermes_advisory_queue_v21.csv
    for proposed ACTIONABLE exposure. Hidden/non-actionable rows never contribute.
    """
    # Load data
    st = load_state()
    bets = st["bets"]
    advisory = read_csv(HERMES_ADVISORY)

    # ── Section 1: Open exposure from bet_tracker.csv ────────────
    open_bets: List[Dict[str, str]] = []
    unknown_status_bets: List[Dict[str, str]] = []

    for b in bets:
        classification = _is_open_bet(b)
        if classification == "OPEN":
            open_bets.append(b)
        elif classification == "UNKNOWN_OPEN_STATUS":
            unknown_status_bets.append(b)

    open_stake = sum(num(b.get("Stake")) for b in open_bets)
    unknown_stake = sum(num(b.get("Stake")) for b in unknown_status_bets)

    # Market-type breakdown
    mtype_totals: Dict[str, float] = {}
    mtype_counts: Dict[str, int] = {}
    for b in open_bets:
        mt = _market_type(b.get("Market", ""))
        mtype_totals[mt] = mtype_totals.get(mt, 0.0) + num(b.get("Stake"))
        mtype_counts[mt] = mtype_counts.get(mt, 0) + 1

    # Unique games and players
    open_games: Dict[str, float] = {}
    open_players: Dict[str, float] = {}
    for b in open_bets:
        g = b.get("Game", "").strip()
        if g and not _invalid_game(g):
            open_games[g] = open_games.get(g, 0.0) + num(b.get("Stake"))
        p = b.get("Player", "").strip()
        if p:
            open_players[p] = open_players.get(p, 0.0) + num(b.get("Stake"))

    open_ladders = _detect_ladders(open_bets)

    # ── Section 2: Proposed exposure from ACTIONABLE queue ───────
    actionable_rows: List[Dict[str, str]] = []
    hidden_actionability: Dict[str, int] = {}
    hidden_total = 0
    for r in advisory:
        src = str(r.get("queue_actionability", "")).strip().upper()
        if src == "ACTIONABLE":
            actionable_rows.append(r)
        elif src:
            hidden_actionability[src] = hidden_actionability.get(src, 0) + 1
            hidden_total += 1
        else:
            hidden_actionability["no_actionability_field"] = \
                hidden_actionability.get("no_actionability_field", 0) + 1
            hidden_total += 1

    proposed_count = len(actionable_rows)
    proposed_units = 0.0
    proposed_units_parseable = True
    for r in actionable_rows:
        u = r.get("units", "").strip()
        if u and u.upper() not in ("NAN", "NONE", "NULL", ""):
            try:
                proposed_units += float(u)
            except (ValueError, TypeError):
                proposed_units_parseable = False

    # Same-game correlation for proposed (group by game_start_utc + game)
    proposed_game_groups: Dict[str, Dict[str, Any]] = {}
    for r in actionable_rows:
        g = r.get("game", "").strip()
        gsu = r.get("game_start_utc", "").strip()
        if gsu and gsu.upper() not in ("NAN", "NONE", "NULL", ""):
            key = f"{gsu}|{g}"
            label = "verified"
        elif g and not _invalid_game(g):
            key = f"PARTIAL|{g}"
            label = "partial"
        else:
            key = f"UNVERIFIED|{g or 'unknown'}"
            label = "unverified"
        if key not in proposed_game_groups:
            proposed_game_groups[key] = {"rows": [], "label": label}
        proposed_game_groups[key]["rows"].append(r)

    # Same-player for proposed
    proposed_has_player = any(
        r.get("player", "").strip()
        and r.get("player", "").strip().upper() not in ("", "NAN", "NONE", "NULL")
        for r in actionable_rows
    )

    # ── Build HTML ───────────────────────────────────────────────
    body = route_intro("Portfolio risk",
        "Daily pre-entry risk view. Open exposure from bet_tracker. "
        "Proposed exposure from ACTIONABLE queue rows only. "
        "DISPLAY ONLY · No auto-betting · No formula/staking/threshold changes.",
        "READ-ONLY")

    # Summary cards
    total_combined = open_stake + (proposed_units if proposed_units_parseable else 0.0)
    body += '<div class="v193-summary-grid">'
    body += card("Open exposure", f"{open_stake:.2f}u",
                 f"{len(open_bets)} open bet(s)", "primary" if open_bets else "")
    body += card("Proposed ACTIONABLE",
                 f"{proposed_units:.2f}u" if proposed_units_parseable else "units unavailable",
                 f"{proposed_count} row(s)", "warn" if proposed_count else "")
    body += card("Combined",
                 f"{total_combined:.2f}u" if proposed_units_parseable
                 else f"{open_stake:.2f}u + ?",
                 "open + proposed", "primary")
    body += card("Hidden non-actionable", str(hidden_total),
                 "diagnostic only", "gray")
    body += "</div>"

    # ── Open exposure detail ─────────────────────────────────────
    open_inner = ""
    if not open_bets and not unknown_status_bets:
        open_inner += (
            '<div class="v193-page-note">'
            "<b>No open bets found.</b> bet_tracker.csv has no OPEN rows.</div>"
        )
    else:
        if unknown_status_bets:
            open_inner += (
                f'<div class="v193-page-note" style="margin-bottom:8px">'
                f"<b>⚠ {len(unknown_status_bets)} row(s) with blank/unknown status</b> "
                f"({unknown_stake:.2f}u) — not counted in open exposure. "
                f"Review Status field in bet_tracker.csv.</div>"
            )

        # Market concentration
        open_inner += '<div class="v193-summary-grid" style="margin-bottom:12px;">'
        for mt_label in ("totals", "spreads", "moneyline", "props", "unknown"):
            if mt_label in mtype_totals:
                open_inner += card(
                    mt_label.title(),
                    f"{mtype_totals[mt_label]:.2f}u",
                    f"{mtype_counts[mt_label]} bet(s)",
                    "primary" if mt_label != "unknown" else "warn"
                )
        open_inner += "</div>"

        # By game
        if open_games:
            open_inner += '<div class="approval-rail" style="margin:6px 0 10px;">'
            open_inner += (
                '<span style="font-size:12px;color:var(--ink-secondary);'
                'margin-right:8px;">Open games:</span>'
            )
            for g, exp in sorted(open_games.items(), key=lambda x: -x[1]):
                open_inner += f'<span class="chip">{esc(g)} — {exp:.2f}u</span>'
            open_inner += "</div>"

        # By player
        if open_players:
            open_inner += '<div class="approval-rail" style="margin:6px 0 10px;">'
            open_inner += (
                '<span style="font-size:12px;color:var(--ink-secondary);'
                'margin-right:8px;">Open players:</span>'
            )
            for p, exp in sorted(open_players.items(), key=lambda x: -x[1]):
                open_inner += f'<span class="chip warn">{esc(p)} — {exp:.2f}u</span>'
            open_inner += "</div>"

        # Ladder detection
        if open_ladders:
            open_inner += '<div style="margin-top:8px;">'
            for lad in open_ladders:
                lines_str = ", ".join(esc(l) for l in lad["lines"])
                open_inner += (
                    f'<div class="v193-page-note" '
                    f'style="border-left:3px solid var(--neon-amber);">'
                    f'<b>⚠ LADDER:</b> {esc(lad["game"])} {esc(lad["market_type"])} '
                    f'{esc(lad["direction"])} @ {lines_str} '
                    f'({lad["count"]} bets)</div>'
                )
            open_inner += "</div>"

        # Open bet detail cards
        if open_bets:
            open_inner += '<div class="action-board" style="margin-top:10px;">'
            for b in open_bets:
                market = b.get("Market", "")
                direction = b.get("Direction", "")
                line = b.get("Line", "")
                odds = b.get("Odds", "")
                stake = b.get("Stake", "")
                game = b.get("Game", "")
                betid = b.get("BetID", "")
                player = b.get("Player", "")
                subtitle = f"{market} {direction}" + (f" {line}" if line else "")
                if player:
                    subtitle = f"{player} · {subtitle}"
                open_inner += (
                    f'<div class="action-clean-card">'
                    f'<div class="action-clean-head"><div>'
                    f'<div class="action-rank-clean">{esc(betid)} · OPEN</div>'
                    f'<div class="action-clean-title">{esc(game)}</div>'
                    f'</div><span class="badge green">OPEN</span></div>'
                    f'<div class="action-clean-bet">{esc(subtitle)} @ {esc(odds)}</div>'
                    f'<div class="action-clean-grid">'
                    f'<div class="mini"><span>Stake</span><b>{esc(stake)}u</b></div>'
                    f'<div class="mini"><span>Market</span><b>{esc(market)}</b></div>'
                    f'</div></div>'
                )
            open_inner += "</div>"

    body += section("Current open exposure",
        "Unsettled bets from bet_tracker.csv. These represent live financial exposure.",
        open_inner, "OPEN")

    # ── Proposed ACTIONABLE exposure ──────────────────────────────
    proposed_inner = ""
    if proposed_count == 0:
        proposed_inner += (
            '<div class="v193-page-note">'
            "<b>No ACTIONABLE queue rows.</b> Proposed exposure = 0. "
            "Hidden rows are diagnostic only and never contribute.</div>"
        )
    else:
        proposed_inner += (
            f'<div class="v193-page-note" style="margin-bottom:8px">'
            f"<b>{proposed_count} ACTIONABLE row(s)</b> — "
            f'units: {f"{proposed_units:.2f}u" if proposed_units_parseable else "unavailable"}. '
            "Manual approval required.</div>"
        )

    # Same-game correlation
    if proposed_game_groups:
        proposed_inner += '<div class="approval-rail" style="margin:6px 0 10px;">'
        proposed_inner += (
            '<span style="font-size:12px;color:var(--ink-secondary);'
            'margin-right:8px;">Proposed games:</span>'
        )
        for key, info in sorted(proposed_game_groups.items()):
            rows = info["rows"]
            label = info["label"]
            g_display = key.split("|", 1)[-1] if "|" in key else key
            n = len(rows)
            chip_cls = ("green" if label == "verified"
                        else "warn" if label == "partial" else "red")
            proposed_inner += (
                f'<span class="chip {chip_cls}">'
                f'{esc(g_display)} — {n} pick(s) [{label}]</span>'
            )
        proposed_inner += "</div>"

    # Same-player
    if proposed_count > 0:
        if proposed_has_player:
            proposed_inner += (
                '<div class="v193-page-note" style="margin-bottom:8px;">'
                "Player-level proposed risk: present in ACTIONABLE rows.</div>"
            )
        else:
            proposed_inner += (
                '<div class="v193-page-note" style="margin-bottom:8px;">'
                "Player-level proposed risk: unavailable — ACTIONABLE queue has no player fields.</div>"
            )

    # ACTIONABLE row cards
    if actionable_rows:
        proposed_inner += '<div class="action-board" style="margin-top:10px;">'
        for r in actionable_rows:
            game = r.get("game", "")
            side = r.get("side", "")
            line = r.get("line", "")
            label = r.get("advisory_label", "REVIEW")
            gsu = r.get("game_start_utc", "")
            units_disp = r.get("units", "")
            edge = r.get("edge", "")
            risk_badges = parse_risk_flags(r.get("risk_flags", ""))
            label_cls = ("green" if label == "LEAN_SUPPORT"
                         else "warn" if label == "MANUAL_REVIEW" else "gray")
            timing_note = (
                f" ⏱ {gsu[:16]}"
                if gsu and gsu.upper() not in ("NAN", "NONE", "NULL", "")
                else " ⏱ unverified"
            )
            proposed_inner += (
                f'<div class="action-clean-card queue-card">'
                f'<div class="action-clean-head"><div>'
                f'<div class="action-rank-clean">MODEL QUEUE</div>'
                f'<div class="action-clean-title">{esc(game)}{esc(timing_note)}</div>'
                f'</div><span class="badge {label_cls}">{esc(label)}</span></div>'
                f'<div class="action-clean-bet">{esc(side)} {esc(line)}</div>'
                f'<div class="action-clean-grid">'
                f'<div class="mini"><span>Units</span>'
                f'<b>{esc(units_disp) if units_disp else "—"}</b></div>'
                f'<div class="mini"><span>Edge</span>'
                f'<b>{esc(edge) if edge else "—"}</b></div>'
                f'<div class="mini risk-mini"><span>Risk</span>'
                f'<div class="risk-badges">{risk_badges}</div></div>'
                f'</div></div>'
            )
        proposed_inner += "</div>"

    body += section("Proposed ACTIONABLE exposure",
        "Only queue_actionability=ACTIONABLE rows. Hidden/non-actionable rows never contribute.",
        proposed_inner, "PROPOSED")

    # ── Hidden / diagnostic ───────────────────────────────────────
    hidden_inner = ""
    if hidden_total == 0:
        hidden_inner += '<div class="v193-page-note">No hidden queue rows.</div>'
    else:
        parts = ", ".join(f"{k}: {v}" for k, v in sorted(hidden_actionability.items()))
        hidden_inner += (
            f'<div class="v193-page-note">'
            f"<b>{hidden_total} hidden non-actionable row(s):</b> {parts}. "
            "Diagnostic only — not in proposed exposure.</div>"
        )

    body += section("Hidden / diagnostic queue rows",
        "Non-actionable rows. Never contribute to proposed exposure.",
        hidden_inner, "DIAGNOSTIC")

    # ── Daily exposure reference ─────────────────────────────────
    ref_inner = ""
    ref_inner += '<div class="v193-summary-grid">'
    ref_inner += card("Open exposure", f"{open_stake:.2f}u",
                      f"{len(open_bets)} bet(s)", "primary")
    ref_inner += card("Proposed ACTIONABLE",
                      f"{proposed_units:.2f}u" if proposed_units_parseable
                      else "units unavailable",
                      f"{proposed_count} row(s)", "warn" if proposed_count else "")
    ref_inner += card("Combined",
                      f"{total_combined:.2f}u" if proposed_units_parseable
                      else f"{open_stake:.2f}u + ?",
                      "open + proposed", "primary")
    ref_inner += card("Reference cap", "not configured",
                      "display only — no enforcement", "gray")
    ref_inner += "</div>"
    ref_inner += (
        '<div class="v193-page-note" style="margin-top:8px;">'
        "DISPLAY ONLY. No auto-betting. No formula/staking/threshold changes. "
        "Manual approval always required.</div>"
    )

    body += section("Daily exposure reference",
        "Display-only summary. No enforcement. No auto-betting.",
        ref_inner, "DISPLAY ONLY")

    body += safety_html(st)
    return body

