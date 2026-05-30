from pathlib import Path
from datetime import datetime

APP = Path('app.py')
if not APP.exists():
    raise SystemExit('ERROR: app.py not found. Run this from WNBA_EDGE_LAB_CLEAN.')

text = APP.read_text(encoding='utf-8')
backup = Path(f"app_backup_before_v21_9_site_state_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.py")
backup.write_text(text, encoding='utf-8')

replacements = {
    'v19.2 · precision system · hermes OS': 'V21.9 · safe automation · manual betting only',
    'V21.8 · advisory cycle · Hermes manual approval': 'V21.9 · safe automation · manual betting only',
    'V21.8 advisory cycle': 'V21.9 safe automation cycle',
    'v19.4 signal execution · manual approval': 'V21.9 safe automation · manual approval',
    'V19.4': 'V21.9',
}
for old, new in replacements.items():
    text = text.replace(old, new)

start = '# === V21_9_LIVE_SITE_STATE_PATCH_START ==='
end = '# === V21_9_LIVE_SITE_STATE_PATCH_END ==='
if start in text and end in text:
    text = text.split(start)[0].rstrip() + '\n\n' + text.split(end, 1)[1].lstrip()

block = r'''
# === V21_9_LIVE_SITE_STATE_PATCH_START ===
# Display-only site state wiring. Does not change model formulas, staking, thresholds, or betting execution.

def _v219_html_escape(value):
    import html
    return html.escape('' if value is None else str(value))

def _v219_to_float(value, default=0.0):
    try:
        if value is None:
            return default
        s = str(value).strip()
        if s == '' or s.lower() in {'nan', 'none', 'null'}:
            return default
        return float(s)
    except Exception:
        return default

def _v219_read_json(name, default=None):
    p = OUTPUT_DIR / name
    if default is None:
        default = {}
    try:
        if p.exists() and p.stat().st_size:
            return json.loads(p.read_text(encoding='utf-8'))
    except Exception:
        return default
    return default

def _v219_read_csv(name_or_path):
    try:
        p = Path(name_or_path)
        if not p.is_absolute() and not p.exists():
            p = OUTPUT_DIR / str(name_or_path)
        if p.exists() and p.stat().st_size:
            return pd.read_csv(p)
    except Exception:
        pass
    return pd.DataFrame()

def _v219_col(row, *names, default=''):
    for n in names:
        try:
            v = row.get(n, '')
        except Exception:
            v = ''
        if str(v).strip() and str(v).strip().lower() not in {'nan','none','null'}:
            return v
    return default

def _v219_bet_tracker_raw():
    try:
        if BET_CSV.exists() and BET_CSV.stat().st_size:
            return pd.read_csv(BET_CSV, dtype=str).fillna('')
    except Exception:
        pass
    return pd.DataFrame()

def _v219_open_bets():
    df = _v219_bet_tracker_raw()
    if df.empty:
        return df
    status = df.get('Status', '').astype(str).str.upper() if 'Status' in df.columns else pd.Series([''] * len(df))
    result = df.get('Result', '').astype(str).str.upper() if 'Result' in df.columns else pd.Series([''] * len(df))
    open_mask = status.isin(['OPEN', 'PENDING']) | result.isin(['OPEN', 'PENDING'])
    return df[open_mask].copy()

def _v219_recent_bets(limit=18):
    df = _v219_bet_tracker_raw()
    if df.empty:
        return df
    return df.tail(limit).copy()

def _v219_open_exposure(open_df=None):
    if open_df is None:
        open_df = _v219_open_bets()
    if open_df.empty or 'Stake' not in open_df.columns:
        return 0.0
    return sum(_v219_to_float(x) for x in open_df['Stake'].tolist())

def _v219_exec_summary():
    data = _v219_read_json('signal_execution_latest_v20.json', {})
    return data.get('summary', {}) if isinstance(data, dict) else {}

def _v219_automation_summary():
    return _v219_read_json('v21_9_safe_automation_summary.json', {})

def _v219_market_summary():
    return _v219_read_json('manual_market_review_summary_v21_9.json', {})

def _v219_queue_df():
    q = _v219_read_csv('hermes_manual_market_queue_v21_9.csv')
    if q.empty:
        q = _v219_read_csv('manual_market_review_v21_9.csv')
    if q.empty:
        return q
    if 'model_edge' in q.columns:
        q = q.copy()
        q['_edge_sort'] = pd.to_numeric(q['model_edge'], errors='coerce').fillna(-9999)
        q = q.sort_values('_edge_sort', ascending=False)
    return q

def _v219_state_cards():
    auto = _v219_automation_summary()
    market = _v219_market_summary()
    execs = _v219_exec_summary()
    open_df = _v219_open_bets()
    settled_pl = _v219_to_float(execs.get('net_profit', 0.0))
    total_tickets = int(_v219_to_float(execs.get('execution_tickets', len(_v219_bet_tracker_raw()))))
    groups = int(_v219_to_float(execs.get('signal_groups', 0)))
    exposure = _v219_open_exposure(open_df)
    fetch_state = (auto.get('fetch') or {}).get('state', 'UNKNOWN') if isinstance(auto, dict) else 'UNKNOWN'
    status = auto.get('status', 'UNKNOWN') if isinstance(auto, dict) else 'UNKNOWN'
    queue_rows = (market.get('rows') or {}).get('hermes_manual_queue', 0) if isinstance(market, dict) else 0
    return f"""
    <section class="metrics">
      {metric_card('V21.9 Automation', _v219_html_escape(status), 'research/model only')}
      {metric_card('Open Bets', len(open_df), f'{exposure:.2f}u exposure', 'yellow' if len(open_df) else '')}
      {metric_card('Settled P/L', f'{settled_pl:+.2f}u', f'{total_tickets} tickets / {groups} groups', 'positive' if settled_pl >= 0 else 'negative')}
      {metric_card('Manual Queue', queue_rows, 'Hermes review rows')}
      {metric_card('Odds Mode', 'Quota-safe', _v219_html_escape(fetch_state), 'yellow')}
    </section>
    <div class="v193-guardrail">
      <div class="v193-guard-card lock"><span>Betting</span><b>Manual only</b><p>No automatic execution. You place bets manually.</p></div>
      <div class="v193-guard-card ok"><span>Formula</span><b>Locked</b><p>No formula replacement from dashboard or automation.</p></div>
      <div class="v193-guard-card ok"><span>Staking</span><b>Locked</b><p>No staking change. Logged stakes only.</p></div>
      <div class="v193-guard-card warn"><span>Odds API</span><b>Skipped</b><p>Quota-safe mode prevents wasted paid calls.</p></div>
    </div>
    """

def _v219_open_bet_cards():
    df = _v219_open_bets()
    if df.empty:
        return '<div class="panel empty">No open manually logged bets found in bet_tracker.csv.</div>'
    cards = []
    for _, r in df.iterrows():
        game = _v219_html_escape(_v219_col(r, 'Game'))
        market = _v219_html_escape(_v219_col(r, 'Market'))
        side = _v219_html_escape(_v219_col(r, 'Direction', 'Side'))
        line = _v219_html_escape(_v219_col(r, 'Line'))
        odds = _v219_html_escape(_v219_col(r, 'Odds'))
        stake = _v219_html_escape(_v219_col(r, 'Stake'))
        sig = _v219_html_escape(_v219_col(r, 'FinalSignal', 'Signal', default='OPEN'))
        notes = _v219_html_escape(_v219_col(r, 'Notes', default='Manual logged ticket'))
        betid = _v219_html_escape(_v219_col(r, 'BetID'))
        cards.append(f"""
        <div class="action-card" data-signal-card="{sig}" data-units="{stake}">
          <div class="action-top"><span class="badge yellow">OPEN</span><span class="chip">{betid}</span></div>
          <h3 class="action-clean-title">{game}</h3>
          <div class="action-clean-bet"><b>{market}</b> · {side} {line} @ {odds}</div>
          <div class="action-clean-grid"><div><span>Stake</span><b>{stake}u</b></div><div><span>Status</span><b>OPEN</b></div><div><span>Signal</span><b>{sig}</b></div><div><span>Mode</span><b>Manual</b></div><div><span>Auto-bet</span><b>NO</b></div></div>
          <p class="muted">{notes}</p>
        </div>""")
    return '<div class="action-grid">' + ''.join(cards) + '</div>'

def _v219_queue_cards(limit=12):
    df = _v219_queue_df()
    if df.empty:
        return '<div class="panel empty">No manual market review queue found. Run manual_market_snapshot_v21_9.py --today and model_manual_market_review_v21_9.py.</div>'
    cards = []
    for _, r in df.head(limit).iterrows():
        label = _v219_col(r, 'advisory_label', default='REVIEW')
        badge = 'green' if str(label).upper() == 'LEAN_SUPPORT' else 'yellow' if 'REVIEW' in str(label).upper() else 'gray'
        game = _v219_html_escape(_v219_col(r, 'game'))
        market = _v219_html_escape(_v219_col(r, 'market'))
        side = _v219_html_escape(_v219_col(r, 'side'))
        line = _v219_html_escape(_v219_col(r, 'line'))
        odds = _v219_html_escape(_v219_col(r, 'odds_decimal'))
        edge = _v219_html_escape(_v219_col(r, 'model_edge'))
        conf = _v219_html_escape(_v219_col(r, 'confidence'))
        risk = _v219_html_escape(_v219_col(r, 'risk_flags'))
        explain = _v219_html_escape(_v219_col(r, 'explanation'))
        cards.append(f"""
        <div class="action-card" data-signal-card="{_v219_html_escape(label)}" data-units="0">
          <div class="action-top"><span class="badge {badge}">{_v219_html_escape(label)}</span><span class="chip">Manual approval</span></div>
          <h3 class="action-clean-title">{game}</h3>
          <div class="action-clean-bet"><b>{market}</b> · {side} {line} @ {odds}</div>
          <div class="action-clean-grid"><div><span>Model Edge</span><b>{edge}</b></div><div><span>Confidence</span><b>{conf}</b></div><div><span>Execution</span><b>Manual</b></div><div><span>Auto-bet</span><b>NO</b></div><div><span>Queue</span><b>Review</b></div></div>
          <p class="muted">{explain}</p><div class="approval-rail"><span class="approval-pill locked">{risk}</span></div>
        </div>""")
    return '<div class="action-grid">' + ''.join(cards) + '</div>'

def _v219_recent_table():
    df = _v219_recent_bets(18)
    if df.empty:
        return '<div class="panel empty">No bet tracker rows found.</div>'
    cols = [c for c in ['BetID','Date','Game','Market','Direction','Line','Odds','Stake','Result','Status','P/L','FinalSignal'] if c in df.columns]
    return table(df[cols].tail(18), max_rows=18)

def _v219_dashboard_body():
    market = _v219_market_summary()
    labels = market.get('label_counts', {}) if isinstance(market, dict) else {}
    label_html = ''.join([f'<div class="mission-row"><span>{_v219_html_escape(k)}</span><b>{_v219_html_escape(v)}</b><em>market review</em></div>' for k, v in labels.items()]) or '<div class="mission-row"><span>Queue</span><b>Pending</b><em>run review</em></div>'
    return f"""
    <section class="v19-hero"><div class="v19-hero-grid"><div><div class="v19-eyebrow"><span class="pulse-ring"></span> WNBA Edge Lab V21.9</div><h1 class="v19-title">Live operator state, not stale advisory text.</h1><p class="v19-copy">This dashboard reads bet_tracker.csv, signal_execution_latest_v20.json, v21_9_safe_automation_summary.json, and the V21.9 manual market review queue.</p></div><div class="v19-side"><div class="v19-kpi"><span>Mode</span><b>Manual</b><p>No auto-betting.</p></div><div class="v19-kpi"><span>Quota</span><b>Safe</b><p>Odds calls skipped while credits are exhausted.</p></div></div></div></section>
    {_v219_state_cards()}
    <div class="v19-section-head"><div><h2>Open bets already placed</h2><p>Manual tickets from bet_tracker.csv. This is what you made.</p></div><span class="chip">Open Exposure</span></div>{_v219_open_bet_cards()}
    <div class="v19-section-head"><div><h2>Model/Hermes market queue</h2><p>Review candidates from V21.9 manual market review. Not executed unless you place them.</p></div><span class="chip">Advisory only</span></div>{_v219_queue_cards(10)}
    <div class="v19-section-head"><div><h2>Manual market label counts</h2><p>Current V21.9 snapshot classification.</p></div></div><div class="v19-panel">{label_html}</div>
    <div class="v19-section-head"><div><h2>Recent tracker rows</h2><p>Audit trail from bet_tracker.csv.</p></div><a class="chip" href="/bets">Open full tracker</a></div>{_v219_recent_table()}
    """

def _v219_hermes_body():
    auto = _v219_automation_summary()
    safety = auto.get('safety', {}) if isinstance(auto, dict) else {}
    locks = safety.get('locks', []) if isinstance(safety, dict) else []
    locks_html = ''.join([f'<span class="approval-pill locked">{_v219_html_escape(x)}</span>' for x in locks]) or '<span class="approval-pill locked">MANUAL_APPROVAL_REQUIRED</span>'
    return f"""
    <section class="hermes-cockpit"><div class="hermes-command-card"><div class="web-eyebrow"><span class="pulse-ring"></span> Hermes · V21.9 Live State</div><h1>Review, warn, wait.</h1><p>Hermes shows what the model wants reviewed and what the operator already placed. It still cannot bet, approve, change formulas, alter staking, or change thresholds.</p><div class="approval-rail">{locks_html}</div></div><div class="v19-panel"><div class="mission-row"><span>Automation</span><b>{_v219_html_escape(auto.get('status','UNKNOWN'))}</b><em>safe cycle</em></div><div class="mission-row"><span>Betting</span><b>Manual user only</b><em>locked</em></div><div class="mission-row"><span>Odds</span><b>Quota-safe</b><em>skip paid calls</em></div></div></section>
    <div class="v19-section-head"><div><h2>Open operator tickets</h2><p>Already placed, awaiting settlement.</p></div><span class="chip">Manual exposure</span></div>{_v219_open_bet_cards()}
    <div class="v19-section-head"><div><h2>Hermes manual market queue</h2><p>Model review candidates. Manual approval required. No auto-betting.</p></div><span class="chip">Advisory only</span></div>{_v219_queue_cards(12)}
    """

def _v219_actions_body():
    return f"""{_v219_state_cards()}<div class="v19-section-head"><div><h2>What the model says to review</h2><p>Manual market queue from V21.9. These are candidates, not automatic bets.</p></div><span class="chip">Review queue</span></div>{_v219_queue_cards(18)}<div class="v19-section-head"><div><h2>What you already made</h2><p>Open manual tickets from bet_tracker.csv.</p></div><span class="chip">Open bets</span></div>{_v219_open_bet_cards()}"""

def _v219_bankroll_body():
    execs = _v219_exec_summary(); open_df = _v219_open_bets(); exposure = _v219_open_exposure(open_df); pl = _v219_to_float(execs.get('net_profit', 0.0)); tickets = int(_v219_to_float(execs.get('execution_tickets', 0))); groups = int(_v219_to_float(execs.get('signal_groups', 0)))
    return f"""<section class="metrics">{metric_card('Settled P/L', f'{pl:+.2f}u', 'from signal execution bridge', 'positive' if pl >= 0 else 'negative')}{metric_card('Open Exposure', f'{exposure:.2f}u', f'{len(open_df)} open tickets', 'yellow')}{metric_card('Tickets', tickets, f'{groups} signal groups')}{metric_card('Betting Mode', 'Manual', 'no auto-betting')}</section><div class="v19-section-head"><div><h2>Open exposure</h2><p>Live tickets still awaiting settlement.</p></div></div>{_v219_open_bet_cards()}<div class="v19-section-head"><div><h2>Recent tracker rows</h2><p>Settled and open ledger audit.</p></div></div>{_v219_recent_table()}"""

def _v219_bets_body():
    return f"""<div class="v19-section-head"><div><h2>Open tickets</h2><p>Manual bets made and waiting for results.</p></div><span class="chip">bet_tracker.csv</span></div>{_v219_open_bet_cards()}<div class="v19-section-head"><div><h2>Recent ledger</h2><p>Latest rows from bet_tracker.csv.</p></div></div>{_v219_recent_table()}"""

def _v219_validation_body():
    result = _v219_read_json('model_result_tracking_summary_v21_9.json', {}); rows = result.get('rows', {}) if isinstance(result, dict) else {}; gates = result.get('gates', {}) if isinstance(result, dict) else {}; promo = result.get('promotion_states', {}) if isinstance(result, dict) else {}; gate_html = ''.join([f'<div class="mission-row"><span>{_v219_html_escape(k)}</span><b>{_v219_html_escape(v)}</b><em>gate</em></div>' for k,v in gates.items()]); promo_html = ''.join([f'<div class="mission-row"><span>{_v219_html_escape(k)}</span><b>{_v219_html_escape(v)}</b><em>promotion</em></div>' for k,v in promo.items()])
    return f"""<section class="metrics">{metric_card('Tracking Rows', rows.get('tracking', 0), 'current advisory evidence')}{metric_card('Known Results', rows.get('known_results', 0), 'formula promotion sample')}{metric_card('Promotion', 'WATCH_ONLY', 'no formula change', 'yellow')}{metric_card('Auto-bet', 'NO', 'locked')}</section><div class="v19-section-head"><div><h2>V21.9 evidence gates</h2><p>Formula/staking/threshold changes stay blocked.</p></div></div><div class="v19-panel">{gate_html}{promo_html}</div><div class="v19-section-head"><div><h2>Open bets are execution state, not formula proof yet</h2><p>Settlement updates execution P/L. Formula evidence requires matched advisory results and minimum sample gates.</p></div></div>{_v219_open_bet_cards()}"""

def _v219_menu_body():
    return '''<div class="v19-section-head"><div><h2>V21.9 live operator routes</h2><p>These routes now read the current safe automation, manual market queue, and bet tracker state.</p></div><span class="chip">V21.9</span></div><div class="deep-menu-grid"><a class="deep-menu-card primary-route" href="/dashboard"><span>Core</span><b>Dashboard</b><p>Open bets, model queue, execution summary, quota-safe state.</p></a><a class="deep-menu-card primary-route" href="/actions"><span>Queue</span><b>Actions</b><p>Model/Hermes manual market review queue plus open tickets.</p></a><a class="deep-menu-card primary-route" href="/hermes"><span>Guard</span><b>Hermes</b><p>Manual approval, safety locks, and review queue.</p></a><a class="deep-menu-card primary-route" href="/bankroll"><span>Fund</span><b>Bankroll</b><p>Open exposure and settled execution P/L.</p></a><a class="deep-menu-card" href="/bets"><span>Ledger</span><b>Bets</b><p>Open tickets and recent bet tracker rows.</p></a><a class="deep-menu-card" href="/validation"><span>Model</span><b>Validation</b><p>V21.9 evidence gates and promotion locks.</p></a><a class="deep-menu-card" href="/diagnostics"><span>Audit</span><b>Diagnostics</b><p>Feature diagnostics and data warnings.</p></a><a class="deep-menu-card" href="/environment"><span>Data</span><b>Environment</b><p>Environment/memory route.</p></a></div>'''

def _v219_index(): return page('Home', _v219_dashboard_body())
def _v219_dashboard(): return page('Dashboard', _v219_dashboard_body())
def _v219_hermes(): return page('Hermes', _v219_hermes_body())
def _v219_actions(): return page('Actions', _v219_actions_body())
def _v219_bankroll(): return page('Bankroll', _v219_bankroll_body())
def _v219_bets(): return page('Tracker', _v219_bets_body())
def _v219_validation(): return page('Validation', _v219_validation_body())
def _v219_menu(): return page('Menu', _v219_menu_body())

app.view_functions['index'] = _v219_index
app.view_functions['dashboard'] = _v219_dashboard
app.view_functions['hermes'] = _v219_hermes
app.view_functions['actions'] = _v219_actions
app.view_functions['bankroll'] = _v219_bankroll
app.view_functions['bets'] = _v219_bets
app.view_functions['validation'] = _v219_validation
app.view_functions['menu'] = _v219_menu
# === V21_9_LIVE_SITE_STATE_PATCH_END ===
'''

text = text.rstrip() + '\n\n' + block
APP.write_text(text, encoding='utf-8')
print('OK: V21.9 live site state patch applied to app.py')
print('Backup:', backup)
print('Routes overridden: /, /dashboard, /actions, /hermes, /bankroll, /bets, /validation, /menu')
