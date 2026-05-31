"""
WNBA Edge Lab V21.9 polished operator website app.

Display-only Flask app. It reads current artifacts through site_state_v21_9.py.
It does NOT change model formulas, staking, thresholds, Hermes approval, or betting execution.
"""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
from flask import Flask, request

try:
    import site_state_v21_9 as state
except Exception as exc:  # Keep Render alive with a visible error instead of crashing silently.
    state = None
    STATE_IMPORT_ERROR = exc
else:
    STATE_IMPORT_ERROR = None

app = Flask(__name__)

ROUTES = [
    ("/", "Home"),
    ("/dashboard", "Dashboard"),
    ("/actions", "Actions"),
    ("/hermes", "Hermes"),
    ("/bets", "Bets"),
    ("/bankroll", "Bankroll"),
    ("/telegram", "Telegram"),
    ("/validation", "Validation"),
    ("/menu", "Menu"),
]

ROUTE_META = {
    "Home": {
        "eyebrow": "Live command center",
        "headline": "V21.9 operator console",
        "subhead": "Model queue, open exposure, Hermes locks, and quota-safe state in one live view.",
        "tone": "primary",
    },
    "Dashboard": {
        "eyebrow": "Model state",
        "headline": "Dashboard",
        "subhead": "Live V21.9 state, open bets, automation health, and execution summary.",
        "tone": "primary",
    },
    "Actions": {
        "eyebrow": "Manual approval queue",
        "headline": "Action board",
        "subhead": "Model-supported candidates and already-entered tickets. No automatic betting.",
        "tone": "action",
    },
    "Hermes": {
        "eyebrow": "Safety layer",
        "headline": "Hermes control",
        "subhead": "Approval gates, locks, warnings, and execution discipline.",
        "tone": "hermes",
    },
    "Bets": {
        "eyebrow": "Ledger",
        "headline": "Bets and exposure",
        "subhead": "Open tickets, settled P/L, correlated exposure, and audit trail.",
        "tone": "bets",
    },
    "Bankroll": {
        "eyebrow": "Risk desk",
        "headline": "Bankroll",
        "subhead": "Stake, return, open exposure, and manual-only execution controls.",
        "tone": "bankroll",
    },
    "Telegram": {
        "eyebrow": "Message preview",
        "headline": "Telegram desk",
        "subhead": "Operator-ready summary. Review before posting or sending.",
        "tone": "telegram",
    },
    "Validation": {
        "eyebrow": "Evidence layer",
        "headline": "Validation",
        "subhead": "Result tracking, CLV, candidate gates, and promotion watchlist.",
        "tone": "validation",
    },
    "Menu": {
        "eyebrow": "Navigation",
        "headline": "Operator menu",
        "subhead": "All live V21.9 pages and compatibility routes.",
        "tone": "menu",
    },
    "Version": {
        "eyebrow": "Deploy marker",
        "headline": "Version check",
        "subhead": "Confirms Render is serving the polished V21.9 operator shell.",
        "tone": "version",
    },
}


def _safe_body(renderer_name: str) -> str:
    """Call a site_state_v21_9 renderer safely and return HTML."""
    if state is None:
        return f"""
        <section class='panel danger reveal'>
          <div class='panel-kicker'>State import</div>
          <h2>V21.9 state import failed</h2>
          <p>The website shell loaded, but <code>site_state_v21_9.py</code> could not be imported.</p>
          <pre>{escape(repr(STATE_IMPORT_ERROR))}</pre>
        </section>
        """
    renderer = getattr(state, renderer_name, None)
    if renderer is None:
        return f"""
        <section class='panel danger reveal'>
          <div class='panel-kicker'>Missing renderer</div>
          <h2>{escape(renderer_name)}() not found</h2>
          <p><code>site_state_v21_9.py</code> does not define this renderer.</p>
        </section>
        """
    try:
        return renderer()
    except Exception as exc:
        return f"""
        <section class='panel danger reveal'>
          <div class='panel-kicker'>Renderer error</div>
          <h2>{escape(renderer_name)}() failed</h2>
          <p>The shell is still live. The renderer raised:</p>
          <pre>{escape(repr(exc))}</pre>
        </section>
        """


def _nav() -> str:
    current = request.path.rstrip("/") or "/"
    links = []
    for href, label in ROUTES:
        active = " active" if (href.rstrip("/") or "/") == current else ""
        links.append(f"<a class='nav-link{active}' href='{href}'>{label}</a>")
    return "".join(links)


def page(title: str, body: str) -> str:
    meta = ROUTE_META.get(title, ROUTE_META["Home"])
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    tone = meta["tone"]
    return f"""<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <meta name='theme-color' content='#061018'>
  <title>WNBA Edge Lab — {escape(title)}</title>
  <style>
    :root {{
      --bg0:#03070c;
      --bg1:#061018;
      --bg2:#0b1520;
      --panel:rgba(13,25,36,.78);
      --panel-solid:#0d1924;
      --panel2:rgba(18,35,49,.82);
      --ink:#eef8ff;
      --muted:#92a8b7;
      --soft:#c9dce8;
      --line:rgba(146,168,183,.18);
      --line2:rgba(139,211,255,.22);
      --good:#55d68b;
      --warn:#f3ca58;
      --bad:#ff7070;
      --accent:#8bd3ff;
      --accent2:#b28cff;
      --shadow:0 24px 80px rgba(0,0,0,.38);
      --radius:24px;
    }}
    * {{ box-sizing:border-box; }}
    html {{ scroll-behavior:smooth; }}
    body {{
      margin:0;
      min-height:100vh;
      font-family:Inter,ui-sans-serif,system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",Arial,sans-serif;
      color:var(--ink);
      background:
        radial-gradient(circle at 12% 8%, rgba(139,211,255,.16), transparent 30%),
        radial-gradient(circle at 88% 4%, rgba(178,140,255,.14), transparent 28%),
        radial-gradient(circle at 50% 95%, rgba(85,214,139,.08), transparent 34%),
        linear-gradient(135deg,var(--bg0),var(--bg1) 46%,#09111a);
      overflow-x:hidden;
    }}
    body:before {{
      content:"";
      position:fixed; inset:0;
      pointer-events:none;
      background-image:linear-gradient(rgba(255,255,255,.025) 1px, transparent 1px), linear-gradient(90deg, rgba(255,255,255,.025) 1px, transparent 1px);
      background-size:42px 42px;
      mask-image:linear-gradient(to bottom, rgba(0,0,0,.8), transparent 78%);
      z-index:-1;
    }}
    body:after {{
      content:""; position:fixed; width:520px; height:520px; right:-240px; top:130px;
      background:radial-gradient(circle, rgba(139,211,255,.12), transparent 62%);
      filter:blur(8px); pointer-events:none; z-index:-1;
      animation:floatGlow 12s ease-in-out infinite alternate;
    }}
    a {{ color:inherit; text-decoration:none; }}
    code {{ color:var(--accent); }}
    .shell {{ max-width:1240px; margin:0 auto; padding:24px; }}
    .topbar {{
      position:sticky; top:0; z-index:40;
      margin:-24px -24px 0; padding:16px 24px;
      backdrop-filter:blur(18px);
      background:linear-gradient(180deg, rgba(3,7,12,.92), rgba(3,7,12,.62));
      border-bottom:1px solid rgba(255,255,255,.06);
    }}
    .topbar-inner {{ max-width:1240px; margin:0 auto; display:flex; align-items:center; justify-content:space-between; gap:14px; }}
    .brand {{ display:flex; align-items:center; gap:12px; min-width:220px; }}
    .brand-mark {{
      width:40px; height:40px; border-radius:14px;
      background:linear-gradient(135deg,var(--accent),var(--accent2));
      box-shadow:0 0 36px rgba(139,211,255,.35);
      display:grid; place-items:center; color:#061018; font-weight:950;
    }}
    .brand-title {{ font-weight:900; letter-spacing:-.04em; }}
    .brand-sub {{ color:var(--muted); font-size:12px; margin-top:2px; }}
    .nav {{ display:flex; gap:8px; flex-wrap:wrap; justify-content:flex-end; }}
    .nav-link {{
      padding:9px 12px; border:1px solid var(--line); border-radius:999px;
      color:var(--soft); background:rgba(13,25,36,.62); font-size:13px;
      transition:transform .18s ease, border-color .18s ease, background .18s ease, color .18s ease;
    }}
    .nav-link:hover {{ transform:translateY(-1px); border-color:var(--line2); background:rgba(139,211,255,.08); color:var(--ink); }}
    .nav-link.active {{ border-color:rgba(139,211,255,.45); color:var(--accent); background:rgba(139,211,255,.12); }}
    .hero {{
      position:relative; overflow:hidden;
      display:grid; grid-template-columns:minmax(0,1fr) 330px; gap:18px;
      margin:24px 0 18px;
      padding:26px;
      border:1px solid var(--line);
      border-radius:32px;
      background:linear-gradient(135deg, rgba(13,25,36,.9), rgba(18,35,49,.66));
      box-shadow:var(--shadow);
    }}
    .hero:before {{
      content:""; position:absolute; inset:-2px;
      background:radial-gradient(circle at 20% 10%, rgba(139,211,255,.22), transparent 32%), radial-gradient(circle at 90% 80%, rgba(178,140,255,.14), transparent 34%);
      opacity:.8; pointer-events:none;
    }}
    .hero > * {{ position:relative; }}
    .eyebrow {{ color:var(--accent); font-weight:900; text-transform:uppercase; letter-spacing:.12em; font-size:12px; margin-bottom:8px; }}
    h1 {{ margin:0; font-size:clamp(34px,5vw,64px); line-height:.96; letter-spacing:-.07em; }}
    .hero p {{ max-width:780px; color:var(--soft); font-size:16px; line-height:1.55; margin:14px 0 0; }}
    .hero-side {{ display:grid; gap:10px; align-content:start; }}
    .status-pill {{
      display:flex; justify-content:space-between; align-items:center; gap:10px;
      padding:13px 14px; border-radius:18px; border:1px solid var(--line);
      background:rgba(3,7,12,.35);
    }}
    .status-pill span:first-child {{ color:var(--muted); font-size:12px; text-transform:uppercase; letter-spacing:.08em; font-weight:800; }}
    .status-pill span:last-child {{ font-weight:900; color:var(--ink); }}
    .badge {{
      display:inline-flex; align-items:center; gap:8px; padding:8px 11px; border-radius:999px;
      border:1px solid var(--line); color:var(--muted); background:rgba(3,7,12,.36);
      font-size:12px; font-weight:900; text-transform:uppercase; letter-spacing:.06em;
    }}
    .badge:before {{ content:""; width:8px; height:8px; border-radius:50%; background:currentColor; box-shadow:0 0 18px currentColor; }}
    .badge.good {{ color:var(--good); border-color:rgba(85,214,139,.38); }}
    .badge.warn {{ color:var(--warn); border-color:rgba(243,202,88,.38); }}
    .badge.bad {{ color:var(--bad); border-color:rgba(255,112,112,.38); }}
    main {{ animation:pageIn .52s ease both; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(230px,1fr)); gap:14px; margin:16px 0; }}
    .card, .panel {{
      background:linear-gradient(180deg,var(--panel),rgba(7,16,24,.82));
      border:1px solid var(--line);
      border-radius:var(--radius);
      padding:17px;
      box-shadow:0 18px 45px rgba(0,0,0,.22);
      transform:translateZ(0);
    }}
    .panel {{ margin:16px 0; }}
    .card:hover, .panel:hover {{ border-color:rgba(139,211,255,.26); }}
    .danger {{ border-color:rgba(255,112,112,.5)!important; }}
    .panel-kicker, h3 {{
      margin:0 0 9px; color:var(--muted); font-size:11px; font-weight:900;
      text-transform:uppercase; letter-spacing:.11em;
    }}
    h2 {{ margin:0 0 12px; font-size:22px; letter-spacing:-.035em; }}
    h3 {{ font-size:12px; }}
    p {{ color:var(--muted); line-height:1.5; }}
    .value {{ font-size:30px; font-weight:950; letter-spacing:-.06em; }}
    .muted {{ color:var(--muted); }}
    .row {{ display:flex; justify-content:space-between; gap:12px; padding:10px 0; border-top:1px solid rgba(255,255,255,.07); }}
    .row:first-child {{ border-top:0; }}
    table {{ width:100%; border-collapse:separate; border-spacing:0; font-size:13px; overflow:hidden; }}
    th,td {{ padding:12px 10px; border-bottom:1px solid rgba(255,255,255,.08); text-align:left; vertical-align:top; }}
    th {{ color:var(--muted); text-transform:uppercase; letter-spacing:.08em; font-size:11px; font-weight:900; }}
    tr:hover td {{ background:rgba(139,211,255,.035); }}
    pre {{
      white-space:pre-wrap; overflow:auto; background:rgba(3,7,12,.55); border:1px solid var(--line);
      border-radius:18px; padding:14px; color:var(--soft);
    }}
    footer {{
      margin-top:28px; padding:18px 0 6px; color:var(--muted); font-size:12px;
      border-top:1px solid rgba(255,255,255,.08); display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap;
    }}
    .reveal {{ animation:reveal .55s ease both; }}
    .delay-1 {{ animation-delay:.08s; }} .delay-2 {{ animation-delay:.16s; }} .delay-3 {{ animation-delay:.24s; }}
    @keyframes pageIn {{ from {{ opacity:0; transform:translateY(8px); }} to {{ opacity:1; transform:translateY(0); }} }}
    @keyframes reveal {{ from {{ opacity:0; transform:translateY(14px); }} to {{ opacity:1; transform:translateY(0); }} }}
    @keyframes floatGlow {{ from {{ transform:translate3d(0,0,0) scale(1); }} to {{ transform:translate3d(-80px,80px,0) scale(1.12); }} }}
    @media (max-width:860px) {{
      .shell {{ padding:16px; }}
      .topbar {{ margin:-16px -16px 0; padding:14px 16px; position:relative; }}
      .topbar-inner {{ align-items:flex-start; flex-direction:column; }}
      .nav {{ justify-content:flex-start; }}
      .hero {{ grid-template-columns:1fr; padding:20px; border-radius:26px; }}
    }}
  </style>
</head>
<body class='route-{tone}'>
  <div class='shell'>
    <div class='topbar'>
      <div class='topbar-inner'>
        <a class='brand' href='/'>
          <div class='brand-mark'>EL</div>
          <div><div class='brand-title'>WNBA Edge Lab</div><div class='brand-sub'>V21.9 live state</div></div>
        </a>
        <nav class='nav'>{_nav()}</nav>
      </div>
    </div>

    <section class='hero reveal'>
      <div>
        <div class='eyebrow'>{escape(meta['eyebrow'])}</div>
        <h1>{escape(meta['headline'])}</h1>
        <p>{escape(meta['subhead'])}</p>
      </div>
      <div class='hero-side'>
        <div class='status-pill'><span>Mode</span><span>Manual approval</span></div>
        <div class='status-pill'><span>Automation</span><span>Research only</span></div>
        <div class='status-pill'><span>Betting</span><span>No auto-bet</span></div>
        <div class='status-pill'><span>Updated</span><span>{escape(now)}</span></div>
      </div>
    </section>

    <main class='reveal delay-1'>{body}</main>
    <footer>
      <span>V21.9 polished operator UI · {escape(title)}</span>
      <span>NO_AUTO_BETTING · MANUAL_APPROVAL_REQUIRED · NO_FORMULA_REPLACEMENT</span>
    </footer>
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


# Compatibility routes: keep existing public paths alive, but route them through V21.9 state.
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
    <section class='panel reveal'>
      <div class='panel-kicker'>Deployment marker</div>
      <h2>V21.9 polished operator UI</h2>
      <div class='grid'>
        <div class='card'><h3>Version</h3><div class='value'>V21.9</div><p>Polished app.py replacement.</p></div>
        <div class='card'><h3>State</h3><div class='value'>Live</div><p>Reads site_state_v21_9.py.</p></div>
        <div class='card'><h3>Safety</h3><div class='value'>Manual</div><p>NO_AUTO_BETTING · MANUAL_APPROVAL_REQUIRED.</p></div>
      </div>
    </section>
    """
    return page("Version", body)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
