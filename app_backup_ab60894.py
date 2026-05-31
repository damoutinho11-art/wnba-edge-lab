"""
WNBA Edge Lab V21.9 clean website app.

Display-only Flask app. It reads current artifacts through site_state_v21_9.py.
It does NOT change model formulas, staking, thresholds, Hermes approval, or betting execution.
"""
from __future__ import annotations

from flask import Flask

try:
    import site_state_v21_9 as state
except Exception as exc:  # Keep Render alive with a visible error instead of crashing silently.
    state = None
    STATE_IMPORT_ERROR = exc
else:
    STATE_IMPORT_ERROR = None

app = Flask(__name__)


def _safe_body(renderer_name: str) -> str:
    if state is None:
        return f"""
        <section class='card danger'>
          <h2>V21.9 state import failed</h2>
          <p>The website shell loaded, but site_state_v21_9.py could not be imported.</p>
          <pre>{STATE_IMPORT_ERROR!r}</pre>
        </section>
        """
    renderer = getattr(state, renderer_name, None)
    if renderer is None:
        return f"""
        <section class='card danger'>
          <h2>Missing renderer</h2>
          <p>site_state_v21_9.py does not define {renderer_name}().</p>
        </section>
        """
    try:
        return renderer()
    except Exception as exc:
        return f"""
        <section class='card danger'>
          <h2>Renderer failed</h2>
          <p>{renderer_name}() raised an error.</p>
          <pre>{exc!r}</pre>
        </section>
        """


def page(title: str, body: str) -> str:
    # Version marker intentionally duplicated in header/footer so stale deploys are obvious.
    return f"""<!doctype html>
<html lang='en'>
<head>
  <meta charset='utf-8'>
  <meta name='viewport' content='width=device-width, initial-scale=1'>
  <title>WNBA Edge Lab — {title}</title>
  <style>
    :root {{
      --bg:#071016; --panel:#0f1b24; --panel2:#132532; --ink:#eef7fb; --muted:#91a7b3;
      --line:#213847; --good:#52d273; --warn:#f0c85a; --bad:#ff6b6b; --accent:#8bd3ff;
    }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; font-family:Inter,Segoe UI,Arial,sans-serif; background:var(--bg); color:var(--ink); }}
    a {{ color:var(--accent); text-decoration:none; }}
    .shell {{ max-width:1180px; margin:0 auto; padding:22px; }}
    header {{ display:flex; justify-content:space-between; gap:16px; align-items:flex-start; padding:18px 0 24px; border-bottom:1px solid var(--line); }}
    h1 {{ margin:0; font-size:30px; letter-spacing:-0.03em; }}
    h2 {{ margin:0 0 12px; font-size:20px; }}
    h3 {{ margin:0 0 8px; font-size:15px; color:var(--muted); text-transform:uppercase; letter-spacing:.08em; }}
    p {{ color:var(--muted); line-height:1.45; }}
    nav {{ display:flex; gap:8px; flex-wrap:wrap; margin-top:12px; }}
    nav a {{ padding:8px 11px; border:1px solid var(--line); border-radius:999px; background:#0b1720; color:var(--ink); font-size:13px; }}
    .badge {{ display:inline-flex; align-items:center; gap:6px; padding:7px 10px; border-radius:999px; background:#0b1720; border:1px solid var(--line); color:var(--muted); font-size:12px; font-weight:700; text-transform:uppercase; letter-spacing:.06em; }}
    .badge.good {{ color:var(--good); border-color:#285b38; }}
    .badge.warn {{ color:var(--warn); border-color:#6b5b28; }}
    .badge.bad {{ color:var(--bad); border-color:#6b3030; }}
    .grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(220px,1fr)); gap:14px; margin:16px 0; }}
    .card {{ background:linear-gradient(180deg,var(--panel),#0b1720); border:1px solid var(--line); border-radius:18px; padding:16px; box-shadow:0 12px 28px rgba(0,0,0,.18); }}
    .card.danger {{ border-color:#6b3030; }}
    .value {{ font-size:26px; font-weight:800; letter-spacing:-0.04em; }}
    .muted {{ color:var(--muted); }}
    .row {{ display:flex; justify-content:space-between; gap:12px; padding:8px 0; border-top:1px solid rgba(255,255,255,.06); }}
    .row:first-child {{ border-top:0; }}
    table {{ width:100%; border-collapse:collapse; font-size:13px; }}
    th,td {{ padding:10px 8px; border-bottom:1px solid rgba(255,255,255,.08); text-align:left; vertical-align:top; }}
    th {{ color:var(--muted); text-transform:uppercase; letter-spacing:.06em; font-size:11px; }}
    pre {{ white-space:pre-wrap; overflow:auto; background:#081019; border:1px solid var(--line); border-radius:14px; padding:14px; }}
    footer {{ margin-top:30px; padding-top:18px; border-top:1px solid var(--line); color:var(--muted); font-size:12px; }}
  </style>
</head>
<body>
  <div class='shell'>
    <header>
      <div>
        <h1>WNBA Edge Lab</h1>
        <p><strong>V21.9 · live state · Hermes manual approval</strong></p>
        <nav>
          <a href='/'>Home</a><a href='/dashboard'>Dashboard</a><a href='/actions'>Actions</a><a href='/hermes'>Hermes</a>
          <a href='/bets'>Bets</a><a href='/bankroll'>Bankroll</a><a href='/telegram'>Telegram</a><a href='/validation'>Validation</a><a href='/menu'>Menu</a>
        </nav>
      </div>
      <div><span class='badge warn'>MANUAL APPROVAL</span></div>
    </header>
    <main>{body}</main>
    <footer>V21.9 live state site · operator terminal · {title} · NO_AUTO_BETTING · MANUAL_APPROVAL_REQUIRED</footer>
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


# Compatibility routes: keep all existing public paths alive, but route them through V21.9 state.
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
    <section class='card'>
      <h2>V21.9 deployment marker</h2>
      <div class='grid'>
        <div class='card'><h3>Version</h3><div class='value'>V21.9</div><p>Clean app.py replacement</p></div>
        <div class='card'><h3>State</h3><div class='value'>Live</div><p>Reads site_state_v21_9.py</p></div>
        <div class='card'><h3>Safety</h3><div class='value'>Manual</div><p>NO_AUTO_BETTING · MANUAL_APPROVAL_REQUIRED</p></div>
      </div>
    </section>
    """
    return page("Version", body)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
