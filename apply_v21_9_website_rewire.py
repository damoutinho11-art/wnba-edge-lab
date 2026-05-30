"""
Apply V21.9 website rewire to app.py.

This script inserts a final endpoint override block before the __main__ guard so
Render/Gunicorn imports use V21.9 live state for every operator-facing route.
Display-only patch: no model formulas, staking, thresholds, or betting execution.
"""
from pathlib import Path

APP = Path("app.py")
START = "# === V21.9 LIVE WEBSITE STATE OVERRIDES START ==="
END = "# === V21.9 LIVE WEBSITE STATE OVERRIDES END ==="

BLOCK = f'''{START}
# Display-only V21.9 route rewire. All state comes from site_state_v21_9.py.
# Safety: no auto-betting, no formula changes, no staking changes, no threshold changes.
try:
    import site_state_v21_9 as _v219_site

    def _v219_page(title, body):
        return page(title, body)

    app.view_functions['index'] = lambda: _v219_page("Home", _v219_site.render_home())
    app.view_functions['dashboard'] = lambda: _v219_page("Dashboard", _v219_site.render_dashboard())
    app.view_functions['actions'] = lambda: _v219_page("Actions", _v219_site.render_actions())
    app.view_functions['hermes'] = lambda: _v219_page("Hermes", _v219_site.render_hermes())
    app.view_functions['bets'] = lambda: _v219_page("Bets", _v219_site.render_bets())
    app.view_functions['bankroll'] = lambda: _v219_page("Bankroll", _v219_site.render_bankroll())
    app.view_functions['telegram'] = lambda: _v219_page("Telegram", _v219_site.render_telegram())
    app.view_functions['validation'] = lambda: _v219_page("Validation", _v219_site.render_validation())
    app.view_functions['menu'] = lambda: _v219_page("Menu", _v219_site.render_menu())
except Exception as _v219_err:
    print("V21.9 site state override failed:", repr(_v219_err))
{END}
'''

def main():
    if not APP.exists():
        raise SystemExit("ERROR: app.py not found. Run from WNBA_EDGE_LAB_CLEAN root.")
    text = APP.read_text(encoding="utf-8", errors="ignore")

    # Remove prior block, if any.
    if START in text and END in text:
        before = text.split(START)[0]
        after = text.split(END, 1)[1]
        text = before + after

    marker = 'if __name__ == "__main__":'
    if marker in text:
        text = text.replace(marker, BLOCK + "\n" + marker, 1)
    else:
        text = text.rstrip() + "\n\n" + BLOCK + "\n"

    APP.write_text(text, encoding="utf-8")
    print("OK: inserted V21.9 website state overrides into app.py")
    print("Routes rewired: / /dashboard /actions /hermes /bets /bankroll /telegram /validation /menu")

if __name__ == "__main__":
    main()
