"""
WNBA Edge Lab V21.9 — Million Dollar Quant Trading & Operator Interface.

High-performance, display-only Flask terminal. Integrates seamless glassmorphic UI architectures,
advanced Chart.js bankroll visualizations, kinetic animations, and crystal-clear structural layouts.
"""
from __future__ import annotations

import json
from flask import Flask, request

try:
    import site_state_v21_9 as state
except Exception as exc:  # Keep cloud environments alive with a high-visibility terminal alert.
    state = None
    STATE_IMPORT_ERROR = exc
else:
    STATE_IMPORT_ERROR = None

app = Flask(__name__)

NAV_ITEMS = [
    ("Home", "/"),
    ("Dashboard", "/dashboard"),
    ("Actions", "/actions"),
    ("Hermes", "/hermes"),
    ("Bets", "/bets"),
    ("Bankroll", "/bankroll"),
    ("Telegram", "/telegram"),
    ("Portfolio", "/portfolio"),
    ("Validation", "/validation"),
    ("Menu", "/menu"),
]


def _safe_body(renderer_name: str) -> str:
    """Safely extracts data frames from state modules, wrapping errors in high-end diagnostics."""
    if state is None:
        return f"""
        <section class='panel danger-panel animate-fade-in'>
          <div class='section-head'>
            <div>
              <h2>Core Pipeline Disconnected</h2>
              <p class='error-subtext'>The application shell is operational, but 'site_state_v21_9.py' failed to initialize.</p>
            </div>
            <span class='chip red'>CRITICAL_ERR</span>
          </div>
          <div class='terminal-code-block'>
            <pre>{STATE_IMPORT_ERROR!r}</pre>
          </div>
        </section>
        """
    renderer = getattr(state, renderer_name, None)
    if renderer is None:
        return f"""
        <section class='panel danger-panel animate-fade-in'>
          <div class='section-head'>
            <div>
              <h2>Missing Pipeline Asset</h2>
              <p class='error-subtext'>The target vector reference '{renderer_name}()' is not exported by the state layer.</p>
            </div>
            <span class='chip red'>MISSING_HOOK</span>
          </div>
        </section>
        """
    try:
        return renderer()
    except Exception as exc:
        return f"""
        <section class='panel danger-panel animate-fade-in'>
          <div class='section-head'>
            <div>
              <h2>Data Render Execution Fault</h2>
              <p class='error-subtext'>An unhandled exception occurred during runtime compilation of '{renderer_name}()'.</p>
            </div>
            <span class='chip red'>EXEC_FAULT</span>
          </div>
          <div class='terminal-code-block'>
            <pre>{exc!r}</pre>
          </div>
        </section>
        """


def _cumulative_pl_data() -> tuple:
    """Read bet_tracker.csv and compute cumulative P/L sorted by Date, BetID.

    Returns (labels_json, data_json) as json.dumps() strings ready for inline JS.
    Read-only. No edits to bet_tracker.csv.
    """
    try:
        import csv as _csv
        from pathlib import Path as _Path
        bt_path = _Path(__file__).resolve().parent / "bet_tracker.csv"
        if not bt_path.exists():
            return "[]", "[]"
        with bt_path.open(newline="", encoding="utf-8-sig") as f:
            rows = list(_csv.DictReader(f))
        settled_rows = [
            r for r in rows
            if r.get("Status", "").strip().upper() in ("SETTLED", "WON", "LOST", "PUSH")
            and r.get("Result", "").strip().upper() != ""
        ]
        settled_rows.sort(key=lambda r: (r.get("Date", ""), r.get("BetID", "")))
        labels = []
        cumulative = []
        running = 0.0
        for r in settled_rows:
            bid = r.get("BetID", "?")
            labels.append(bid)
            pl_val = r.get("P/L", "")
            try:
                running += float(pl_val)
            except (ValueError, TypeError):
                pass
            cumulative.append(round(running, 2))
        if not cumulative:
            return "[]", "[]"
        return json.dumps(labels), json.dumps(cumulative)
    except Exception:
        return "[]", "[]"


def _nav_html() -> str:
    path = request.path.rstrip("/") or "/"
    links = []
    for name, href in NAV_ITEMS:
        active = " active" if (href == path or (href != "/" and path.startswith(href))) else ""
        links.append(f"<a class='nav-pill{active}' href='{href}'>{name}</a>")
    return "".join(links)


def page(title: str, body: str) -> str:
    current_path = request.path.rstrip("/") or "/"
    # Compute cumulative P/L for chart (only rendered on / /dashboard /bankroll /stakes)
    _cl, _cd = _cumulative_pl_data()
    
    return f"""<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>WNBA Edge Lab — {title}</title>
  
  <link rel='preconnect' href='https://fonts.googleapis.com'>
  <link rel='preconnect' href='https://fonts.gstatic.com' crossorigin>
  <link href='https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@300;400;500;600;700;800&family=JetBrains+Mono:wght@400;500;700&display=swap' rel='stylesheet'>
  
  <script src='https://cdn.jsdelivr.net/npm/chart.js'></script>
  
  <style>
    :root {{
      --bg: #030712;
      --bg-surface: #0b1329;
      --panel-glass: rgba(13, 27, 42, 0.65);
      --panel-glass-hover: rgba(27, 38, 59, 0.8);
      --border-glow: rgba(0, 229, 255, 0.15);
      --border-subtle: rgba(255, 255, 255, 0.06);
      
      --ink-primary: #f3f4f6;
      --ink-secondary: #9ca3af;
      --ink-muted: #6b7280;
      
      /* Million Dollar Quant Palette */
      --neon-cyan: #00e5ff;
      --neon-emerald: #00e676;
      --neon-amber: #ffb300;
      --neon-crimson: #ff1744;
      --neon-purple: #d500f9;
      
      --shadow-luxury: 0 20px 50px rgba(0, 0, 0, 0.6), inset 0 1px 0 rgba(255, 255, 255, 0.05);
      --font-sans: 'Plus Jakarta Sans', ui-sans-serif, system-ui, sans-serif;
      --font-mono: 'JetBrains Mono', 'SFMono-Regular', monospace;
    }}

    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    html {{ scroll-behavior: smooth; background: var(--bg); }}
    
    body {{
      min-height: 100vh;
      font-family: var(--font-sans);
      color: var(--ink-primary);
      background-color: var(--bg);
      overflow-x: hidden;
      position: relative;
    }}

    /* Cinematic Ambient Glow Vectors */
    .glow-container {{
      position: fixed;
      width: 100vw;
      height: 100vh;
      top: 0;
      left: 0;
      pointer-events: none;
      z-index: -1;
      overflow: hidden;
    }}
    .glow-blob-1 {{
      position: absolute;
      top: -10%; left: 15%; width: 550px; height: 550px;
      background: radial-gradient(circle, rgba(0, 229, 255, 0.08) 0%, transparent 70%);
      animation: ambientFloat 18s infinite alternate ease-in-out;
    }}
    .glow-blob-2 {{
      position: absolute;
      bottom: 10%; right: 10%; width: 600px; height: 600px;
      background: radial-gradient(circle, rgba(213, 0, 249, 0.05) 0%, transparent 70%);
      animation: ambientFloat 24s infinite alternate-reverse ease-in-out;
    }}
    
    /* Interactive Background Grid Matrix */
    #canvas-matrix {{
      position: fixed;
      inset: 0;
      z-index: -1;
      opacity: 0.25;
      pointer-events: none;
    }}

    .shell {{ width: min(1360px, calc(100% - 40px)); margin: 0 auto; padding: 0 0 50px; }}

    /* Highbar Sticky Navigation */
    .topbar {{
      position: sticky;
      top: 0;
      z-index: 100;
      padding: 16px 0;
      backdrop-filter: blur(24px);
      -webkit-backdrop-filter: blur(24px);
      background: rgba(3, 7, 18, 0.75);
      border-bottom: 1px solid var(--border-subtle);
    }}
    .nav {{ display: flex; align-items: center; justify-content: space-between; gap: 20px; }}
    .brand-mini {{ display: flex; align-items: center; gap: 12px; font-weight: 800; font-size: 19px; letter-spacing: -0.04em; color: var(--ink-primary); text-decoration: none; }}
    .brand-logo {{
      width: 38px;
      height: 38px;
      display: grid;
      place-items: center;
      border-radius: 12px;
      background: linear-gradient(135deg, rgba(0, 229, 255, 0.15), rgba(0, 230, 118, 0.05));
      border: 1px solid rgba(0, 229, 255, 0.3);
      font-size: 18px;
      box-shadow: 0 0 15px rgba(0, 229, 255, 0.1);
    }}
    .nav-links {{ display: flex; gap: 6px; flex-wrap: wrap; }}
    .nav-pill {{
      padding: 8px 15px;
      border: 1px solid transparent;
      border-radius: 100px;
      color: var(--ink-secondary);
      background: transparent;
      font-size: 13.5px;
      font-weight: 600;
      transition: all 0.25s cubic-bezier(0.4, 0, 0.2, 1);
      text-decoration: none;
    }}
    .nav-pill:hover {{
      color: var(--ink-primary);
      background: rgba(255, 255, 255, 0.04);
      border-color: var(--border-subtle);
    }}
    .nav-pill.active {{
      color: var(--neon-cyan);
      background: rgba(0, 229, 255, 0.08);
      border-color: rgba(0, 229, 255, 0.25);
      box-shadow: 0 0 15px rgba(0, 229, 255, 0.05);
    }}

    /* Executive Hero Dashboard Banner */
    .hero {{
      display: grid;
      grid-template-columns: 1.4fr 0.6fr;
      gap: 24px;
      align-items: stretch;
      margin-top: 30px;
    }}
    .hero-card {{
      position: relative;
      overflow: hidden;
      border: 1px solid rgba(0, 229, 255, 0.2);
      background: linear-gradient(135deg, rgba(11, 19, 41, 0.85), rgba(2, 7, 18, 0.9));
      border-radius: 24px;
      padding: 36px;
      box-shadow: var(--shadow-luxury);
      animation: slideUpFade 0.6s cubic-bezier(0.16, 1, 0.3, 1) both;
    }}
    .hero-card::before {{
      content: "";
      position: absolute;
      top: -150px; right: -150px;
      width: 350px; height: 350px;
      background: radial-gradient(circle, rgba(0, 229, 255, 0.15) 0%, transparent 70%);
      pointer-events: none;
    }}
    .eyebrow {{ display: flex; gap: 8px; align-items: center; flex-wrap:wrap; margin-bottom: 20px; }}
    .status-dot {{
      width: 8px; height: 8px; border-radius: 50%;
      background: var(--neon-emerald);
      box-shadow: 0 0 12px var(--neon-emerald), 0 0 4px var(--neon-emerald);
      animation: pulseIndicator 2s infinite ease-in-out;
    }}
    h1 {{ font-size: clamp(32px, 4.5vw, 52px); font-weight: 800; line-height: 1.05; letter-spacing: -0.05em; background: linear-gradient(to right, #ffffff, #9ca3af); -webkit-background-clip: text; -webkit-text-fill-color: transparent; }}
    .hero-sub {{ max-width: 760px; color: var(--ink-secondary); font-size: 15.5px; line-height: 1.6; margin-top: 14px; font-weight: 400; }}
    
    .hero-side {{
      border: 1px solid var(--border-subtle);
      border-radius: 24px;
      padding: 28px;
      background: var(--panel-glass);
      backdrop-filter: blur(16px);
      box-shadow: var(--shadow-luxury);
      animation: slideUpFade 0.6s cubic-bezier(0.16, 1, 0.3, 1) 0.05s both;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
    }}
    .manual-pill {{
      display: inline-flex; align-items: center; justify-content: center;
      padding: 6px 12px; border-radius: 6px;
      border: 1px solid rgba(255, 179, 0, 0.3); color: var(--neon-amber);
      font-family: var(--font-mono); font-weight: 700; font-size: 11px;
      text-transform: uppercase; background: rgba(255, 179, 0, 0.05);
      letter-spacing: 0.05em;
    }}
    .approval-rail {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 16px; }}
    .approval-pill {{
      display: inline-flex; align-items: center; gap: 6px;
      padding: 6px 12px; border-radius: 8px; font-size: 11px;
      font-family: var(--font-mono); font-weight: 600; color: var(--ink-secondary);
      border: 1px solid var(--border-subtle); background: rgba(255, 255, 255, 0.02);
    }}
    .approval-pill.warn {{ color: var(--neon-amber); border-color: rgba(255, 179, 0, 0.2); background: rgba(255, 179, 0, 0.02); }}
    .approval-pill.locked {{ color: var(--neon-crimson); border-color: rgba(255, 23, 68, 0.2); background: rgba(255, 23, 68, 0.02); }}

    main {{ margin-top: 24px; }}

    /* Structural Refactoring of State Module Targets */
    .v192-command-strip {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 16px; margin: 24px 0; }}
    .v193-summary-grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 16px; margin: 20px 0; }}
    .v19-grid-4 {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(260px, 1fr)); gap: 20px; margin: 24px 0; }}
    
    .v192-chip-card, .v193-summary-card, .mini, .v19-card, .action-clean-card {{
      position: relative; overflow: hidden;
      border: 1px solid var(--border-subtle); border-radius: 16px;
      padding: 24px; background: var(--panel-glass);
      backdrop-filter: blur(12px); box-shadow: var(--shadow-luxury);
      transition: all 0.3s cubic-bezier(0.16, 1, 0.3, 1);
    }}
    .v192-chip-card:hover, .v193-summary-card:hover, .mini:hover, .v19-card:hover, .action-clean-card:hover {{
      transform: translateY(-4px);
      border-color: rgba(0, 229, 255, 0.3);
      background: var(--panel-glass-hover);
      box-shadow: 0 30px 60px rgba(0,0,0,0.5), 0 0 30px rgba(0,229,255,0.05);
    }}
    
    .v192-chip-card span, .v193-summary-card span, .mini span, .v19-card span {{
      display: block; color: var(--ink-secondary); font-size: 11px;
      font-weight: 700; text-transform: uppercase; letter-spacing: 0.1em; margin-bottom: 10px;
    }}
    .v192-chip-card b, .v193-summary-card b, .mini b, .v19-card b {{
      display: block; color: var(--ink-primary); font-size: clamp(22px, 2.5vw, 32px);
      font-weight: 700; line-height: 1.1; letter-spacing: -0.04em;
    }}
    .v192-chip-card p, .v193-summary-card p, .v19-card p {{
      margin-top: 8px; color: var(--ink-muted); font-size: 13.5px; line-height: 1.4;
    }}

    .v193-summary-card.primary {{ border-left: 3px solid var(--neon-cyan); }}
    .v193-summary-card.warn {{ border-left: 3px solid var(--neon-amber); }}
    .v193-summary-card.lock {{ border-left: 3px solid var(--neon-crimson); }}

    /* Universal Control Panels */
    .panel {{
      border: 1px solid var(--border-subtle); border-radius: 20px;
      padding: 32px; background: linear-gradient(180deg, rgba(11, 19, 41, 0.6), rgba(3, 7, 18, 0.8));
      box-shadow: var(--shadow-luxury); margin: 24px 0;
      animation: slideUpFade 0.5s cubic-bezier(0.16, 1, 0.3, 1) both;
    }}
    .danger-panel {{ border: 1px solid rgba(25ff, 23, 68, 0.3); background: linear-gradient(180deg, rgba(29, 7, 15, 0.6), rgba(3, 7, 18, 0.9)); }}
    .terminal-code-block {{ margin-top: 16px; border-radius: 12px; overflow: hidden; border: 1px solid rgba(255,255,255,0.05); }}
    
    .section-head {{ display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; margin: 36px 0 20px; }}
    .section-head h2 {{ font-size: clamp(20px, 2.5vw, 28px); font-weight: 700; letter-spacing: -0.04em; }}
    .section-head p {{ margin-top: 6px; color: var(--ink-secondary); font-size: 14.5px; }}

    /* Quantum Data Badges */
    .chip, .badge {{
      display: inline-flex; align-items: center; justify-content: center;
      padding: 6px 12px; border-radius: 6px; font-family: var(--font-mono);
      font-size: 11px; font-weight: 700; letter-spacing: 0.04em;
      border: 1px solid var(--border-subtle); background: rgba(255,255,255,0.03);
      color: var(--ink-secondary); white-space: nowrap;
    }}
    .chip.green, .badge.green {{ color: var(--neon-emerald); border-color: rgba(0, 230, 118, 0.25); background: rgba(0, 230, 118, 0.04); }}
    .chip.warn, .badge.warn {{ color: var(--neon-amber); border-color: rgba(255, 179, 0, 0.25); background: rgba(255, 179, 0, 0.04); }}
    .chip.red, .badge.red {{ color: var(--neon-crimson); border-color: rgba(255, 23, 68, 0.25); background: rgba(255, 23, 68, 0.04); }}

    /* Quant Action Cards Layout */
    .action-board {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; margin-top: 20px; }}
    .action-clean-head {{ display: flex; justify-content: space-between; gap: 12px; align-items: flex-start; }}
    .action-rank-clean {{ font-family: var(--font-mono); color: var(--neon-cyan); font-size: 11px; font-weight: 700; letter-spacing: 0.05em; text-transform: uppercase; margin-bottom: 6px; }}
    .action-clean-title {{ font-size: 20px; font-weight: 700; letter-spacing: -0.03em; color: var(--ink-primary); }}
    .action-clean-bet {{
      margin: 20px 0; padding: 16px; border-radius: 12px;
      border: 1px solid rgba(0, 229, 255, 0.15); background: rgba(0, 229, 255, 0.03);
      color: #ffffff; font-size: 16px; font-weight: 700; font-family: var(--font-mono);
    }}
    .action-clean-grid {{ display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; }}
    .mini {{ padding: 16px; border-radius: 12px; box-shadow: none; background: rgba(255,255,255,0.01); }}
    .mini b {{ font-size: 18px; font-family: var(--font-mono); }}

    /* Data Validation Modules */
    .validation-compact-list {{ display: flex; flex-direction: column; gap: 12px; }}
    .validation-row-lite {{
      display: grid; grid-template-columns: 1.5fr 1fr 0.8fr 0.8fr; gap: 16px;
      align-items: center; border: 1px solid var(--border-subtle);
      border-radius: 12px; padding: 16px 20px; background: rgba(255, 255, 255, 0.01);
      transition: background 0.2s;
    }}
    .validation-row-lite:hover {{ background: rgba(255,255,255,0.03); }}
    .validation-row-lite span {{ display: block; color: var(--ink-muted); font-size: 11px; font-weight: 600; text-transform: uppercase; }}
    .validation-row-lite b {{ color: var(--ink-primary); font-size: 14.5px; font-weight: 600; }}
    .validation-row-lite em {{ color: var(--ink-secondary); font-style: normal; font-family: var(--font-mono); font-size: 13px; }}

    pre {{
      font-family: var(--font-mono); font-size: 13.5px; line-height: 1.5;
      white-space: pre-wrap; overflow-x: auto; border: none;
      padding: 20px; background: #020617; color: #cbd5e1;
    }}
    
    /* Performance Progress Trackers */
    .progress-track {{ height: 6px; border-radius: 100px; background: rgba(255,255,255,0.05); overflow: hidden; margin-top: 6px; }}
    .progress-fill {{ height: 100%; border-radius: 100px; background: var(--neon-cyan); transition: width 0.8s cubic-bezier(0.16, 1, 0.3, 1); }}
    .progress-fill.green {{ background: var(--neon-emerald); }}
    .progress-fill.warn {{ background: var(--neon-amber); }}
    .progress-fill.red {{ background: var(--neon-crimson); }}
    .progress-bar-item {{ margin: 12px 0; }}
    .progress-bar-labels {{ display: flex; justify-content: space-between; align-items: center; }}
    .progress-bar-labels span {{ font-size: 12.5px; color: var(--ink-secondary); font-weight: 500; }}
    .progress-val {{ font-family: var(--font-mono); font-weight: 700; color: var(--ink-primary); }}

    /* Route Subtitles & Alignment Elements */
    .route-title {{ display: flex; justify-content: space-between; align-items: center; margin: 24px 0; }}
    .route-title h2 {{ font-size: 14px; color: var(--ink-secondary); font-weight: 700; letter-spacing: 0.1em; text-transform: uppercase; font-family: var(--font-mono); }}

    .data-freshness-strip {{ display: flex; justify-content: flex-end; align-items: center; gap: 8px; padding: 12px 0; font-size: 12px; color: var(--ink-muted); font-family: var(--font-mono); }}
    footer {{ text-align: center; color: var(--ink-muted); border-top: 1px solid var(--border-subtle); margin-top: 60px; padding-top: 24px; font-size: 12px; font-family: var(--font-mono); letter-spacing: 0.02em; }}

    /* Interactive Client Chart Wrapper Container */
    .quant-chart-container {{
      width: 100%; position: relative; margin: 24px 0; padding: 24px;
      border: 1px solid var(--border-subtle); border-radius: 20px;
      background: rgba(11, 19, 41, 0.4); backdrop-filter: blur(10px);
    }}

    /* Hardware Accelerated Kinetic Animations Matrix */
    @keyframes slideUpFade {{ from {{ opacity: 0; transform: translateY(20px); }} to {{ opacity: 1; transform: translateY(0); }} }}
    @keyframes ambientFloat {{ from {{ transform: translate(0, 0) scale(1); }} to {{ transform: translate(4%, 3%) scale(1.08); }} }}
    @keyframes pulseIndicator {{ 0%, 100% {{ opacity: 0.6; transform: scale(1); }} 50% {{ opacity: 1; transform: scale(1.2); box-shadow: 0 0 16px var(--neon-emerald), 0 0 6px var(--neon-emerald); }} }}

    @media (max-width: 960px) {{
      .hero {{ grid-template-columns: 1fr; }}
      .action-clean-grid {{ grid-template-columns: 1fr; }}
      .validation-row-lite {{ grid-template-columns: 1fr 1fr; gap: 12px; }}
    }}
    @media (max-width: 640px) {{
      .nav {{ flex-direction: column; align-items: flex-start; gap: 16px; }}
      .nav-links {{ justify-content: flex-start; }}
      .hero-card {{ padding: 24px; }}
      .validation-row-lite {{ grid-template-columns: 1fr; }}
    }}
  </style>
</head>
<body>

  <div class='glow-container'>
    <div class='glow-blob-1'></div>
    <div class='glow-blob-2'></div>
  </div>
  <canvas id='canvas-matrix'></canvas>

  <div class='topbar'>
    <div class='shell' style='padding-bottom:0;'>
      <div class='nav'>
        <a class='brand-mini' href='/'><span class='brand-logo'>🏀</span><span>WNBA Edge Lab</span></a>
        <div class='nav-links'>{_nav_html()}</div>
      </div>
    </div>
  </div>

  <div class='shell'>
    <section class='hero'>
      <div class='hero-card'>
        <div class='eyebrow'>
          <span class='status-dot'></span>
          <span class='chip green'>V21.9 Enterprise</span>
          <span class='chip warn'>Risk Shield Active</span>
          <span class='chip red'>Simulation Engine Only</span>
        </div>
        <h1>WNBA Quant Matrix</h1>
        <p class='hero-sub'>High-performance operator core monitoring streaming execution parity, complex model parameters, Hermes tier authorizations, and portfolio exposures. Execution pathways are structural read-only channels.</p>
      </div>
      <aside class='hero-side'>
        <div class='section-head' style='margin:0 0 12px; padding:0;'>
          <div>
            <h2 style='font-size: 20px;'>{title}</h2>
            <p style='font-size: 13px;'>Secure Vector Context</p>
          </div>
          <span class='manual-pill'>Hermes Manual Lock</span>
        </div>
        <div class='approval-rail'>
          <span class='approval-pill locked'>NO_AUTO_EXECUTION</span>
          <span class='approval-pill warn'>HERMES_LOCK_ON</span>
          <span class='approval-pill locked'>ISOLATED_FORMULA</span>
        </div>
      </aside>
    </section>

    <main id='quant-core-injection'>
      {body}
    </main>

    <script>
      document.addEventListener("DOMContentLoaded", function() {{
        const path = {json.dumps(current_path)};
        const mainContainer = document.getElementById('quant-core-injection');
        
        // Dynamic interception rule: Instantiate banking/portfolio charts on matching operational context routes.
        if (path === '/bankroll' || path === '/dashboard' || path === '/stakes' || path === '/') {{
          
          const chartSection = document.createElement('section');
          chartSection.className = 'panel';
          chartSection.innerHTML = `
            <div class='section-head'>
              <div>
                <h2>Cumulative P/L</h2>
                <p>Realized profit/loss in units from bet_tracker.csv.</p>
              </div>
              <span class='chip green'>Live Data</span>
            </div>
            <div class='quant-chart-container'>
              <canvas id='bankrollLiveChart' style='max-height: 380px; width: 100%;'></canvas>
            </div>
          `;
          
          if(path === '/bankroll' || path === '/stakes') {{
            mainContainer.insertBefore(chartSection, mainContainer.firstChild);
          }} else {{
            mainContainer.appendChild(chartSection);
          }}

          // High-End Chart.js Modern Configuration
          const ctx = document.getElementById('bankrollLiveChart').getContext('2d');
          const cyanGrad = ctx.createLinearGradient(0, 0, 0, 350);
          cyanGrad.addColorStop(0, 'rgba(0, 229, 255, 0.22)');
          cyanGrad.addColorStop(1, 'rgba(0, 229, 255, 0.00)');

          // Real cumulative P/L from bet_tracker.csv
          const dataLabels = {_cl};
          const baseBankroll = {_cd};
          const totalPL = baseBankroll.length > 0 ? baseBankroll[baseBankroll.length - 1] : 0;

          new Chart(ctx, {{
            type: 'line',
            data: {{
              labels: dataLabels,
              datasets: [{{
                label: `Cumulative P/L (u) — ${'{'}totalPL.toFixed(2){'}'}u`,
                data: baseBankroll,
                borderColor: '#00e5ff',
                borderWidth: 2.5,
                pointBackgroundColor: '#030712',
                pointBorderColor: '#00e5ff',
                pointHoverRadius: 6,
                fill: true,
                backgroundColor: cyanGrad,
                tension: 0.22,
              }}]
            }},
            options: {{
              responsive: true,
              maintainAspectRatio: false,
              plugins: {{
                legend: {{ display: false }},
                tooltip: {{
                  backgroundColor: '#0b1329',
                  titleFont: {{ family: 'Plus Jakarta Sans', size: 13, weight: '700' }},
                  bodyFont: {{ family: 'JetBrains Mono', size: 12 }},
                  borderColor: 'rgba(0, 229, 255, 0.3)',
                  borderWidth: 1,
                  padding: 12,
                  displayColors: false,
                  callbacks: {{
                    label: function(context) {{
                      return " P/L: " + context.parsed.y.toFixed(2) + "u";
                    }}
                  }}
                }}
              }},
              scales: {{
                x: {{
                  grid: {{ color: 'rgba(255, 255, 255, 0.03)', drawBorder: false }},
                  ticks: {{ color: '#9ca3af', font: {{ family: 'JetBrains Mono', size: 10 }} }}
                }},
                y: {{
                  grid: {{ color: 'rgba(255, 255, 255, 0.04)', drawBorder: false }},
                  ticks: {{
                    color: '#9ca3af',
                    font: {{ family: 'JetBrains Mono', size: 10 }},
                    callback: function(value) {{ return value.toFixed(1) + "u"; }}
                  }}
                }}
              }}
            }}
          }});
        }}
      }});

      // Ambient Kinetic Matrix Canvas Script
      const canvas = document.getElementById('canvas-matrix');
      if (canvas) {{
        const ctx = canvas.getContext('2d');
        let width = canvas.width = window.innerWidth;
        let height = canvas.height = window.innerHeight;
        
        window.addEventListener('resize', () => {{
          width = canvas.width = window.innerWidth;
          height = canvas.height = window.innerHeight;
        }});

        const dots = Array.from({{ length: 45 }}, () => ({{
          x: Math.random() * width,
          y: Math.random() * height,
          r: Math.random() * 1.5 + 0.5,
          vX: (Math.random() - 0.5) * 0.25,
          vY: (Math.random() - 0.5) * 0.25
        }}));

        function renderMatrix() {{
          ctx.clearRect(0, 0, width, height);
          ctx.fillStyle = 'rgba(0, 229, 255, 0.4)';
          dots.forEach(dot => {{
            ctx.beginPath();
            ctx.arc(dot.x, dot.y, dot.r, 0, Math.PI * 2);
            ctx.fill();
            dot.x += dot.vX;
            dot.y += dot.vY;
            if (dot.x < 0 || dot.x > width) dot.vX *= -1;
            if (dot.y < 0 || dot.y > height) dot.vY *= -1;
          }});
          requestAnimationFrame(renderMatrix);
        }}
        renderMatrix();
      }}
    </script>

    {state.data_freshness_strip() if state else ''}
    <footer>V21.9 Enterprise Terminal Pipeline · Secure Quantum Node · Routing Identifier: {title}</footer>
  </div>
</body>
</html>"""


@app.route("/")
def index():
    return page("Overview Terminal", _safe_body("render_home"))


@app.route("/dashboard")
def dashboard():
    return page("Performance Dashboard", _safe_body("render_dashboard"))


@app.route("/actions")
def actions():
    return page("Algorithmic Actions", _safe_body("render_actions"))


@app.route("/hermes")
def hermes():
    return page("Hermes Control Core", _safe_body("render_hermes"))


@app.route("/bets")
def bets():
    return page("Exposure Ledger", _safe_body("render_bets"))


@app.route("/bankroll")
def bankroll():
    return page("Capital Allocations", _safe_body("render_bankroll"))


@app.route("/telegram")
def telegram():
    return page("Telemetry Streams", _safe_body("render_telegram"))


@app.route("/portfolio")
def portfolio():
    return page("Portfolio Risk", _safe_body("render_portfolio_risk"))


@app.route("/validation")
def validation():
    return page("Data Validation Metrics", _safe_body("render_validation"))


@app.route("/menu")
def menu():
    return page("System Index Menu", _safe_body("render_menu"))


@app.route("/diagnostics")
def diagnostics():
    return page("System Diagnostics", _safe_body("render_validation"))


@app.route("/analysis")
def analysis():
    return page("Market State Analysis", _safe_body("render_dashboard"))


@app.route("/research")
def research():
    return page("Quantitative Research Vectors", _safe_body("render_actions"))


@app.route("/memory")
def memory():
    return page("Volatile Cache Architecture", _safe_body("render_validation"))


@app.route("/environment")
def environment():
    return page("Runtime Environment Matrix", _safe_body("render_validation"))


@app.route("/intelligence")
def intelligence():
    return page("Model Intelligence Node", _safe_body("render_dashboard"))


@app.route("/history")
def history():
    return page("Historical Backtest Ledger", _safe_body("render_bets"))


@app.route("/stake")
@app.route("/stakes")
def stakes():
    return page("Staking Allocation Matrices", _safe_body("render_bankroll"))


@app.route("/version")
def version():
    body = """
    <section class='panel animate-fade-in'>
      <div class='section-head'>
        <div>
          <h2>System Compilation Specifications</h2>
          <p>Production cluster environment markers verifying deployment parity.</p>
        </div>
        <span class='chip green'>ACTIVE LAYER</span>
      </div>
      <div class='v193-summary-grid'>
        <div class='v193-summary-card primary'><span>Cluster Revision</span><b>V21.9 Gold</b><p>Premium Trading Core UI</p></div>
        <div class='v193-summary-card primary'><span>Telemetry Hook</span><b>Operational</b><p>Pipes verified from site_state_v21_9</p></div>
        <div class='v193-summary-card warn'><span>Guardrail Policy</span><b>Isolated</b><p>MANUAL_APPROVAL_REQUIRED · READ_ONLY</p></div>
      </div>
    </section>
    """
    return page("System Status", body)


@app.errorhandler(404)
def not_found(exc):
    body = """
    <section class='panel danger-panel animate-fade-in'>
      <div class='section-head'>
        <div>
          <h2>404 — Invalid Allocation Destination</h2>
          <p>The target tracking pipeline coordinate does not exist in the V21.9 deployment map.</p>
        </div>
        <span class='chip red'>ROUTING_ERROR</span>
      </div>
      <div class='approval-rail'>
        <span class='approval-pill locked'>RESTRICTED_ACCESS</span>
        <span class='approval-pill locked'>SANDBOX_SHIELD_ACTIVE</span>
      </div>
    </section>
    """
    return page("404 Invalidation", body), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)