"""
WNBA Edge Lab V21.9 polished operator UI.

Display-only Flask app. It reads current artifacts through site_state_v21_9.py.
It does NOT change model formulas, staking, thresholds, Hermes approval, or betting execution.
"""
from __future__ import annotations

from flask import Flask, request

try:
    import site_state_v21_9 as state
except Exception as exc:  # Keep Render alive with a visible error instead of crashing silently.
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
    ("Validation", "/validation"),
    ("Menu", "/menu"),
]


def _safe_body(renderer_name: str) -> str:
    if state is None:
        return f"""
        <section class='panel danger-panel'>
          <div class='section-head'><div><h2>V21.9 state import failed</h2><p>The website shell loaded, but site_state_v21_9.py could not be imported.</p></div><span class='chip red'>Error</span></div>
          <pre>{STATE_IMPORT_ERROR!r}</pre>
        </section>
        """
    renderer = getattr(state, renderer_name, None)
    if renderer is None:
        return f"""
        <section class='panel danger-panel'>
          <div class='section-head'><div><h2>Missing renderer</h2><p>site_state_v21_9.py does not define {renderer_name}().</p></div><span class='chip red'>Error</span></div>
        </section>
        """
    try:
        return renderer()
    except Exception as exc:
        return f"""
        <section class='panel danger-panel'>
          <div class='section-head'><div><h2>Renderer failed</h2><p>{renderer_name}() raised an error.</p></div><span class='chip red'>Error</span></div>
          <pre>{exc!r}</pre>
        </section>
        """


def _nav_html() -> str:
    path = request.path.rstrip("/") or "/"
    links = []
    for name, href in NAV_ITEMS:
        active = " active" if (href == path or (href != "/" and path.startswith(href))) else ""
        links.append(f"<a class='nav-pill{active}' href='{href}'>{name}</a>")
    return "".join(links)


def page(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>WNBA Edge Lab — {title}</title>
  <style>
    :root {{
      --bg:#02080d;
      --bg2:#07131b;
      --panel:rgba(10,24,34,.78);
      --panel2:rgba(14,34,47,.86);
      --panel3:rgba(20,48,65,.72);
      --ink:#f4fbff;
      --muted:#9fb8c7;
      --soft:#d8effb;
      --line:rgba(139,211,255,.18);
      --line2:rgba(255,255,255,.10);
      --good:#53f39a;
      --warn:#ffd76a;
      --bad:#ff6b7f;
      --accent:#8bd3ff;
      --accent2:#b58cff;
      --shadow:0 28px 80px rgba(0,0,0,.40);
      --font:Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Arial, sans-serif;
      --font-mono:"SFMono-Regular", Consolas, "Liberation Mono", Menlo, monospace;
    }}
    * {{ box-sizing:border-box; }}
    html {{ scroll-behavior:smooth; }}
    body {{
      margin:0;
      min-height:100vh;
      font-family:var(--font);
      color:var(--ink);
      background:
        radial-gradient(circle at 18% 10%, rgba(139,211,255,.15), transparent 28%),
        radial-gradient(circle at 84% 18%, rgba(181,140,255,.13), transparent 30%),
        radial-gradient(circle at 50% 100%, rgba(83,243,154,.08), transparent 26%),
        linear-gradient(135deg, var(--bg), var(--bg2) 50%, #02060a);
      overflow-x:hidden;
    }}
    body::before {{
      content:"";
      position:fixed;
      inset:0;
      pointer-events:none;
      background-image:
        linear-gradient(rgba(255,255,255,.025) 1px, transparent 1px),
        linear-gradient(90deg, rgba(255,255,255,.018) 1px, transparent 1px);
      background-size:38px 38px;
      mask-image:linear-gradient(to bottom, rgba(0,0,0,.55), transparent 85%);
    }}
    a {{ color:inherit; text-decoration:none; }}
    .shell {{ width:min(1220px, calc(100% - 28px)); margin:0 auto; padding:22px 0 34px; }}
    .topbar {{
      position:sticky;
      top:0;
      z-index:20;
      padding:14px 0 12px;
      backdrop-filter:blur(18px);
      background:linear-gradient(180deg, rgba(2,8,13,.90), rgba(2,8,13,.50));
      border-bottom:1px solid rgba(139,211,255,.10);
    }}
    .hero {{
      position:relative;
      display:grid;
      grid-template-columns:1.35fr .65fr;
      gap:20px;
      align-items:stretch;
      margin-top:18px;
    }}
    .hero-card {{
      position:relative;
      overflow:hidden;
      border:1px solid var(--line);
      background:linear-gradient(135deg, rgba(16,36,50,.80), rgba(9,20,29,.72));
      border-radius:30px;
      padding:30px;
      box-shadow:var(--shadow);
      animation:floatIn .62s ease both;
    }}
    .hero-card::after {{
      content:"";
      position:absolute;
      width:360px;
      height:360px;
      right:-160px;
      top:-180px;
      border-radius:50%;
      background:radial-gradient(circle, rgba(139,211,255,.32), transparent 68%);
      filter:blur(2px);
      animation:pulseGlow 5s ease-in-out infinite;
    }}
    .eyebrow {{ display:flex; gap:10px; align-items:center; flex-wrap:wrap; margin-bottom:18px; }}
    .status-dot {{ width:10px; height:10px; border-radius:999px; background:var(--good); box-shadow:0 0 0 6px rgba(83,243,154,.10), 0 0 24px rgba(83,243,154,.70); }}
    h1 {{ margin:0; font-size:clamp(38px, 6vw, 72px); line-height:.92; letter-spacing:-.07em; }}
    .hero-sub {{ max-width:720px; color:var(--muted); font-size:18px; line-height:1.6; margin:20px 0 0; }}
    .hero-side {{
      border:1px solid var(--line);
      border-radius:30px;
      padding:22px;
      background:linear-gradient(180deg, rgba(10,24,34,.78), rgba(10,18,26,.84));
      box-shadow:var(--shadow);
      animation:floatIn .72s ease .06s both;
    }}
    .nav {{ display:flex; align-items:center; justify-content:space-between; gap:14px; }}
    .brand-mini {{ display:flex; align-items:center; gap:10px; color:var(--soft); font-weight:850; letter-spacing:-.03em; }}
    .brand-logo {{ width:34px; height:34px; display:grid; place-items:center; border-radius:12px; background:linear-gradient(135deg, rgba(139,211,255,.24), rgba(83,243,154,.12)); border:1px solid var(--line); }}
    .nav-links {{ display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end; }}
    .nav-pill {{
      padding:9px 13px;
      border:1px solid var(--line);
      border-radius:999px;
      color:var(--muted);
      background:rgba(6,15,22,.70);
      font-size:13px;
      transition:.18s ease;
    }}
    .nav-pill:hover, .nav-pill.active {{ color:var(--ink); border-color:rgba(139,211,255,.45); background:rgba(139,211,255,.12); transform:translateY(-1px); }}
    .manual-pill {{ display:inline-flex; align-items:center; justify-content:center; padding:9px 14px; border-radius:999px; border:1px solid rgba(255,215,106,.45); color:var(--warn); font-weight:900; letter-spacing:.08em; font-size:12px; text-transform:uppercase; background:rgba(255,215,106,.08); }}
    main {{ margin-top:22px; }}

    /* Core renderer classes from site_state_v21_9.py */
    .v192-command-strip {{ display:grid; grid-template-columns:repeat(5, minmax(0,1fr)); gap:14px; margin:18px 0 22px; }}
    .v192-chip-card, .v193-summary-card, .mini {{
      position:relative;
      overflow:hidden;
      border:1px solid var(--line);
      border-radius:22px;
      padding:16px;
      background:linear-gradient(180deg, rgba(14,34,47,.82), rgba(8,18,26,.88));
      box-shadow:0 16px 38px rgba(0,0,0,.22);
      transition:.18s ease;
    }}
    .v192-chip-card:hover, .v193-summary-card:hover, .action-clean-card:hover, .v19-card:hover {{ transform:translateY(-2px); border-color:rgba(139,211,255,.42); }}
    .v192-chip-card span, .v193-summary-card span, .mini span {{ display:block; color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.08em; font-weight:800; margin-bottom:8px; }}
    .v192-chip-card b, .v193-summary-card b, .mini b {{ display:block; color:var(--ink); font-size:clamp(20px, 3vw, 30px); line-height:1.1; letter-spacing:-.045em; }}
    .v192-chip-card p, .v193-summary-card p {{ margin:9px 0 0; color:var(--muted); font-size:13px; }}
    .v193-summary-grid {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(190px, 1fr)); gap:14px; margin:16px 0; }}
    .v193-summary-card.primary {{ border-color:rgba(83,243,154,.28); }}
    .v193-summary-card.warn {{ border-color:rgba(255,215,106,.34); }}
    .v193-summary-card.lock {{ border-color:rgba(255,107,127,.30); }}
    .panel {{
      border:1px solid var(--line);
      border-radius:28px;
      padding:20px;
      background:linear-gradient(180deg, rgba(9,22,32,.76), rgba(5,13,20,.86));
      box-shadow:var(--shadow);
      margin:18px 0;
      animation:floatIn .55s ease both;
    }}
    .danger-panel {{ border-color:rgba(255,107,127,.45); }}
    .section-head {{ display:flex; justify-content:space-between; align-items:flex-start; gap:16px; margin:28px 0 14px; padding-top:2px; }}
    .section-head h2 {{ margin:0; font-size:clamp(22px, 3vw, 34px); letter-spacing:-.055em; }}
    .section-head p {{ margin:8px 0 0; color:var(--muted); line-height:1.5; }}
    .chip, .badge {{ display:inline-flex; align-items:center; justify-content:center; gap:7px; padding:7px 11px; border-radius:999px; border:1px solid var(--line); background:rgba(139,211,255,.08); color:var(--soft); font-size:11px; font-weight:900; text-transform:uppercase; letter-spacing:.08em; white-space:nowrap; }}
    .chip.green, .badge.green {{ color:var(--good); border-color:rgba(83,243,154,.35); background:rgba(83,243,154,.09); }}
    .chip.warn, .badge.warn {{ color:var(--warn); border-color:rgba(255,215,106,.42); background:rgba(255,215,106,.08); }}
    .chip.red, .badge.red {{ color:var(--bad); border-color:rgba(255,107,127,.42); background:rgba(255,107,127,.08); }}
    .chip.gray, .badge.gray {{ color:var(--muted); }}
    .action-board {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(280px, 1fr)); gap:16px; margin-top:14px; }}
    .action-clean-card {{
      border:1px solid var(--line);
      border-radius:24px;
      padding:18px;
      background:linear-gradient(135deg, rgba(15,35,49,.90), rgba(7,16,24,.92));
      box-shadow:0 20px 50px rgba(0,0,0,.28);
      transition:.18s ease;
    }}
    .action-clean-head {{ display:flex; justify-content:space-between; gap:12px; align-items:flex-start; }}
    .action-rank-clean {{ color:var(--accent); font-size:11px; font-weight:950; letter-spacing:.10em; text-transform:uppercase; margin-bottom:7px; }}
    .action-clean-title {{ color:var(--ink); font-size:18px; font-weight:900; letter-spacing:-.035em; }}
    .action-clean-bet {{ margin:16px 0; padding:13px 14px; border-radius:16px; border:1px solid rgba(139,211,255,.16); background:rgba(139,211,255,.06); color:var(--soft); font-size:15px; font-weight:800; }}
    .action-clean-grid {{ display:grid; grid-template-columns:repeat(4, minmax(0,1fr)); gap:10px; }}
    .mini {{ padding:12px; border-radius:17px; box-shadow:none; }}
    .mini b {{ font-size:16px; letter-spacing:-.03em; overflow-wrap:anywhere; }}
    .approval-rail {{ display:flex; gap:8px; flex-wrap:wrap; margin-top:14px; }}
    .approval-pill {{ display:inline-flex; align-items:center; gap:6px; padding:7px 10px; border-radius:999px; font-size:11px; font-weight:900; letter-spacing:.05em; text-transform:uppercase; border:1px solid var(--line); color:var(--muted); background:rgba(255,255,255,.03); }}
    .approval-pill.warn {{ color:var(--warn); border-color:rgba(255,215,106,.34); }}
    .approval-pill.locked {{ color:var(--bad); border-color:rgba(255,107,127,.30); }}
    .v193-page-note {{ border:1px dashed rgba(139,211,255,.25); border-radius:20px; padding:18px; color:var(--muted); background:rgba(139,211,255,.05); }}
    .validation-compact-list {{ display:grid; gap:10px; }}
    .validation-row-lite {{ display:grid; grid-template-columns:1.2fr 1fr auto auto; gap:12px; align-items:center; border:1px solid var(--line2); border-radius:16px; padding:12px; background:rgba(255,255,255,.035); }}
    .validation-row-lite span {{ display:block; color:var(--muted); font-size:11px; text-transform:uppercase; letter-spacing:.06em; }}
    .validation-row-lite b {{ color:var(--ink); }}
    .validation-row-lite em {{ color:var(--muted); font-style:normal; }}
    .green {{ color:var(--good) !important; }} .red {{ color:var(--bad) !important; }} .gray {{ color:var(--muted) !important; }}
    .v19-grid-4 {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(230px, 1fr)); gap:14px; margin-top:16px; }}
    .v19-card {{ display:block; border:1px solid var(--line); border-radius:24px; padding:18px; background:linear-gradient(180deg, rgba(15,35,49,.82), rgba(7,16,24,.88)); box-shadow:0 16px 40px rgba(0,0,0,.24); transition:.18s ease; }}
    .v19-card span {{ color:var(--accent); font-size:11px; font-weight:900; text-transform:uppercase; letter-spacing:.08em; }}
    .v19-card b {{ display:block; font-size:22px; margin:9px 0 5px; letter-spacing:-.04em; }}
    .v19-card p {{ color:var(--muted); margin:0; }}
    pre {{ white-space:pre-wrap; overflow:auto; border:1px solid var(--line); border-radius:22px; padding:18px; background:rgba(3,9,14,.82); color:var(--soft); box-shadow:inset 0 0 0 1px rgba(255,255,255,.02); }}
    footer {{ color:var(--muted); border-top:1px solid var(--line); margin-top:30px; padding:18px 0 0; font-size:12px; }}
    .route-title {{ display:flex; justify-content:space-between; align-items:center; gap:14px; margin:18px 0; }}
    .route-title h2 {{ margin:0; font-size:18px; color:var(--muted); font-weight:800; letter-spacing:.04em; text-transform:uppercase; }}
    @keyframes floatIn {{ from {{ opacity:0; transform:translateY(14px); }} to {{ opacity:1; transform:translateY(0); }} }}
    @keyframes pulseGlow {{ 0%,100% {{ opacity:.50; transform:scale(.96); }} 50% {{ opacity:.82; transform:scale(1.06); }} }}
    @media (max-width: 880px) {{
      .hero {{ grid-template-columns:1fr; }}
      .v192-command-strip {{ grid-template-columns:repeat(2, minmax(0,1fr)); }}
      .action-clean-grid {{ grid-template-columns:repeat(2, minmax(0,1fr)); }}
      .validation-row-lite {{ grid-template-columns:1fr; }}
      .nav {{ align-items:flex-start; flex-direction:column; }}
    }}
    @media (max-width: 560px) {{
      .shell {{ width:min(100% - 18px, 1220px); }}
      .hero-card, .hero-side, .panel {{ border-radius:22px; padding:18px; }}
      .v192-command-strip {{ grid-template-columns:1fr; }}
      .nav-links {{ gap:6px; }}
      .nav-pill {{ font-size:12px; padding:8px 10px; }}
    }}
    .progress-track {{ height:6px; border-radius:999px; background:rgba(255,255,255,.08); overflow:hidden; }}
    .progress-fill {{ height:100%; border-radius:999px; background:var(--accent); transition:width .6s ease; }}
    .progress-fill.green {{ background:var(--good); }}
    .progress-fill.warn {{ background:var(--warn); }}
    .progress-fill.red {{ background:var(--bad); }}
    .progress-bar-item {{ margin:6px 0; }}
    .progress-bar-labels {{ display:flex; justify-content:space-between; align-items:center; margin-bottom:4px; }}
    .progress-bar-labels span:first-child {{ font-size:12px; color:var(--muted); }}
    .progress-val {{ font-size:12px; font-weight:800; color:var(--soft); }}
    .gates-grid {{ margin-top:12px; }}
    .gates-card {{ grid-column:1/-1; }}
    .gates-title {{ display:block; font-size:14px; font-weight:800; color:var(--soft); margin-bottom:10px; padding-bottom:8px; border-bottom:1px solid var(--line); }}
    .data-freshness-strip {{ display:flex; justify-content:flex-end; align-items:center; gap:8px; padding:6px 10px 10px; font-size:12px; color:var(--muted); }}
    .queue-card {{ transition:.18s ease; }}
    .queue-card:hover {{ transform:translateY(-2px); border-color:rgba(139,211,255,.42); }}
    .risk-mini {{ grid-column:span 1; }}
    .risk-badges {{ display:flex; flex-wrap:wrap; gap:4px; margin-top:4px; }}
  </style>
</head>
<body>
  <div class='topbar'>
    <div class='shell' style='padding-top:0;padding-bottom:0'>
      <div class='nav'>
        <a class='brand-mini' href='/'><span class='brand-logo'>🏀</span><span>WNBA Edge Lab</span></a>
        <div class='nav-links'>{_nav_html()}</div>
      </div>
    </div>
  </div>
  <div class='shell'>
    <section class='hero'>
      <div class='hero-card'>
        <div class='eyebrow'><span class='status-dot'></span><span class='chip green'>V21.9 live</span><span class='chip warn'>Quota-safe</span><span class='chip red'>No auto-betting</span></div>
        <h1>WNBA Edge Lab</h1>
        <p class='hero-sub'>Operator-grade model dashboard for live betting state, Hermes manual approval, open exposure, and V21.9 market review. Display-only: the site does not place bets or change formulas.</p>
      </div>
      <aside class='hero-side'>
        <div class='section-head' style='margin:0 0 14px;padding:0'><div><h2>{title}</h2><p>Current route</p></div><span class='manual-pill'>Manual approval</span></div>
        <div class='approval-rail'><span class='approval-pill locked'>NO_AUTO_BETTING</span><span class='approval-pill warn'>HERMES_REQUIRED</span><span class='approval-pill locked'>NO_FORMULA_CHANGE</span></div>
      </aside>
    </section>
    <main>{body}</main>
    {state.data_freshness_strip() if state else ''}
    <footer>V21.9 live state site · operator interface · {title} · NO_AUTO_BETTING · MANUAL_APPROVAL_REQUIRED</footer>
  </div>
</body>
</html>"""


@app.route("/")
def index():
    return page("Home", _safe_body("render_home"))


@app.route("/dashboard")
def dashboard():
    return page("Dashboard", _safe_body("render_dashboard"))


@app.route("/actions")
def actions():
    return page("Actions", _safe_body("render_actions"))


@app.route("/hermes")
def hermes():
    return page("Hermes", _safe_body("render_hermes"))


@app.route("/bets")
def bets():
    return page("Bets", _safe_body("render_bets"))


@app.route("/bankroll")
def bankroll():
    return page("Bankroll", _safe_body("render_bankroll"))


@app.route("/telegram")
def telegram():
    return page("Telegram", _safe_body("render_telegram"))


@app.route("/validation")
def validation():
    return page("Validation", _safe_body("render_validation"))


@app.route("/menu")
def menu():
    return page("Menu", _safe_body("render_menu"))


@app.route("/diagnostics")
def diagnostics():
    return page("Diagnostics", _safe_body("render_validation"))


@app.route("/analysis")
def analysis():
    return page("Analysis", _safe_body("render_dashboard"))


@app.route("/research")
def research():
    return page("Research", _safe_body("render_actions"))


@app.route("/memory")
def memory():
    return page("Memory", _safe_body("render_validation"))


@app.route("/environment")
def environment():
    return page("Environment", _safe_body("render_validation"))


@app.route("/intelligence")
def intelligence():
    return page("Intelligence", _safe_body("render_dashboard"))


@app.route("/history")
def history():
    return page("History", _safe_body("render_bets"))


@app.route("/stake")
@app.route("/stakes")
def stakes():
    return page("Stakes", _safe_body("render_bankroll"))


@app.route("/version")
def version():
    body = """
    <section class='panel'>
      <div class='section-head'><div><h2>V21.9 deployment marker</h2><p>Use this page to confirm Render is serving the polished operator UI.</p></div><span class='chip green'>CSS FIX</span></div>
      <div class='v193-summary-grid'>
        <div class='v193-summary-card primary'><span>Version</span><b>V21.9</b><p>Polished operator UI</p></div>
        <div class='v193-summary-card primary'><span>State</span><b>Live</b><p>Reads site_state_v21_9.py</p></div>
        <div class='v193-summary-card warn'><span>Safety</span><b>Manual</b><p>NO_AUTO_BETTING · MANUAL_APPROVAL_REQUIRED</p></div>
      </div>
    </section>
    """
    return page("Version", body)


@app.errorhandler(404)
def not_found(exc):
    body = """
    <section class='panel danger-panel'>
      <div class='section-head'><div><h2>404 — Page not found</h2><p>The requested route does not exist in V21.9.</p></div><span class='chip red'>NOT FOUND</span></div>
      <div class='approval-rail'>
        <span class='approval-pill locked'>NO_AUTO_BETTING</span>
        <span class='approval-pill locked'>MANUAL_APPROVAL_REQUIRED</span>
      </div>
    </section>
    """
    return page("404", body), 404


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
