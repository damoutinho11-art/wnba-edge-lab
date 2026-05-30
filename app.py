from pathlib import Path
import sqlite3
import json
import html
import pandas as pd
from flask import Flask, redirect, request

app = Flask(__name__)

OUTPUT_DIR = Path("wnba_outputs")
PROJECTIONS_CSV = OUTPUT_DIR / "projections.csv"
PROJECTIONS_STAKES_CSV = OUTPUT_DIR / "projections_with_stakes.csv"
RECOMMENDED_CSV = OUTPUT_DIR / "recommended_bets.csv"
RANKINGS_CSV = OUTPUT_DIR / "rankings.csv"
TELEGRAM_TXT = OUTPUT_DIR / "telegram_message.txt"
HISTORY_CSV = OUTPUT_DIR / "projection_history.csv"
EVALUATION_SUMMARY_CSV = OUTPUT_DIR / "bet_evaluation_summary.csv"
DIAGNOSTICS_CSV = OUTPUT_DIR / "projections_diagnostics.csv"
SIGNAL_CLV_SUMMARY_CSV = OUTPUT_DIR / "signal_clv_summary.csv"
SIGNAL_RESULTS_SUMMARY_CSV = OUTPUT_DIR / "signal_results_summary.csv"
SIGNAL_GRADED_CSV = OUTPUT_DIR / "signal_tracker_graded.csv"
SIGNAL_WITH_CLV_CSV = OUTPUT_DIR / "signal_tracker_with_clv.csv"
MODEL_HEALTH_CSV = OUTPUT_DIR / "model_health_report.csv"
INSIGHT_REPORT_CSV = OUTPUT_DIR / "insight_engine_report.csv"
DASHBOARD_INSIGHTS_TXT = OUTPUT_DIR / "dashboard_insights.txt"
MODEL_HEALTH_TIMELINE_CSV = OUTPUT_DIR / "model_health_timeline.csv"
RESEARCH_SNAPSHOT_HISTORY_CSV = OUTPUT_DIR / "research_snapshot_history.csv"
DAILY_RESEARCH_SNAPSHOT_JSON = OUTPUT_DIR / "daily_research_snapshot.json"

BET_CSV = Path("bet_tracker.csv")
BET_DB = Path("bet_tracker.db")


CSS = """
@import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;500;600;700;800;900&family=JetBrains+Mono:ital,wght@0,300;0,400;0,500;0,600;1,300&family=Fraunces:ital,opsz,wght@0,9..144,300;0,9..144,600;0,9..144,700;1,9..144,400&display=swap');

:root{
  /* ── Core palette ── */
  --bg0:#020509; --bg1:#050b14; --bg2:#080f1c;
  --card:#09131f; --card2:#0c1828;
  --line:#152033; --line2:#1e3050;
  --text:#e8eef8; --text2:#beccdf;
  --muted:#5a7599; --muted2:#324d6a;

  /* ── Accent system ── */
  --green:#05e89a;  --green-d:rgba(5,232,154,.12);
  --red:#f84b6e;    --red-d:rgba(248,75,110,.12);
  --yellow:#f5c842; --yellow-d:rgba(245,200,66,.1);
  --orange:#f07832; --orange-d:rgba(240,120,50,.1);
  --blue:#3d82f5;   --blue-d:rgba(61,130,245,.1);
  --cyan:#00c8f0;   --cyan-d:rgba(0,200,240,.1);
  --purple:#8b5cf6; --purple-d:rgba(139,92,246,.1);
  --pink:#ec4899;

  /* ── Glow shadows ── */
  --glow-green:0 0 28px rgba(5,232,154,.22);
  --glow-blue:0 0 28px rgba(61,130,245,.22);
  --glow-red:0 0 28px rgba(248,75,110,.22);
  --glow-cyan:0 0 28px rgba(0,200,240,.2);

  /* ── Typography ── */
  --font-display:'Outfit',sans-serif;
  --font-serif:'Fraunces',serif;
  --font-mono:'JetBrains Mono',monospace;

  /* ── Geometry ── */
  --r-card:18px;
  --r-card-lg:24px;
  --r-pill:999px;
  --r-sm:10px;

  /* ── Motion ── */
  --ease-out:cubic-bezier(.16,1,.3,1);
  --ease-spring:cubic-bezier(.34,1.56,.64,1);
  --transition:all .2s cubic-bezier(.16,1,.3,1);
}
/* ===== RESET & BASE ===== */
*,*::before,*::after{box-sizing:border-box;margin:0;padding:0}

/* ===== AMBIENT BACKGROUND ===== */
html{
  background:var(--bg0);
  scroll-behavior:smooth;
}
body{
  color:var(--text);
  font-family:var(--font-display);
  font-size:14px;
  line-height:1.55;
  min-height:100vh;
  overflow-x:hidden;
  background:
    radial-gradient(ellipse 70% 45% at 0% -5%, rgba(0,200,240,.07) 0%, transparent 60%),
    radial-gradient(ellipse 55% 38% at 100% 0%, rgba(139,92,246,.09) 0%, transparent 55%),
    radial-gradient(ellipse 45% 55% at 55% 105%, rgba(5,232,154,.04) 0%, transparent 58%),
    linear-gradient(170deg, #020509 0%, #050b14 55%, #020509 100%);
}

/* Grain texture */
body::before{
  content:"";
  position:fixed;inset:0;
  pointer-events:none;z-index:0;
  opacity:.028;
  background-image:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='256' height='256'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.72' numOctaves='4' stitchTiles='stitch'/%3E%3C/filter%3E%3Crect width='256' height='256' filter='url(%23n)' opacity='1'/%3E%3C/svg%3E");
  background-size:180px;
}

/* Subtle dot grid */
body::after{
  content:"";
  position:fixed;inset:0;
  pointer-events:none;z-index:0;
  background-image: radial-gradient(circle, rgba(61,130,245,.045) 1px, transparent 1px);
  background-size:36px 36px;
  mask-image:linear-gradient(to bottom, rgba(0,0,0,.55) 0%, transparent 72%);
  animation:gridDrift 28s linear infinite;
}
@keyframes gridDrift{from{background-position:0 0}to{background-position:36px 36px}}

/* Ambient orbs */
.ambient-orb{
  position:fixed;
  border-radius:50%;
  pointer-events:none;
  z-index:0;
  filter:blur(90px);
  animation:orbDrift 22s ease-in-out infinite alternate;
}
.ambient-orb.a{width:560px;height:560px;left:-220px;top:-120px;background:radial-gradient(circle,rgba(0,200,240,.065),transparent 70%);animation-delay:0s}
.ambient-orb.b{width:440px;height:440px;right:-160px;top:-40px;background:radial-gradient(circle,rgba(139,92,246,.06),transparent 70%);animation-delay:-7s}
.ambient-orb.c{width:380px;height:380px;left:28%;bottom:-120px;background:radial-gradient(circle,rgba(5,232,154,.04),transparent 70%);animation-delay:-14s}
@keyframes orbDrift{from{transform:translate(0,0) scale(1)}to{transform:translate(24px,-16px) scale(1.07)}}

a{color:inherit;text-decoration:none}

/* ===== TOPBAR ===== */
.topbar{
  position:sticky;top:0;z-index:100;
  background:rgba(2,5,9,.82);
  backdrop-filter:blur(28px) saturate(200%);
  border-bottom:1px solid rgba(255,255,255,.055);
  box-shadow:0 1px 0 rgba(0,200,240,.05), 0 8px 32px rgba(0,0,0,.35);
}
.top-inner{max-width:1280px;margin:0 auto;padding:0 24px}
.brand-row{display:flex;justify-content:space-between;align-items:center;gap:16px;padding:13px 0 10px}
.logo{display:flex;align-items:center;gap:13px}

/* Logo mark */
.logo-mark{
  position:relative;
  width:40px;height:40px;
  display:grid;place-items:center;
  flex-shrink:0;
}
.logo-mark svg{position:absolute;inset:0;width:100%;height:100%}
.logo-mark span{
  position:relative;z-index:2;
  font-family:var(--font-display);
  font-weight:800;font-size:15px;letter-spacing:-.02em;
  background:linear-gradient(135deg,var(--cyan),var(--purple));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
}

.logo-text h1{
  font-family:var(--font-display);
  font-size:16px;font-weight:700;
  letter-spacing:-.04em;line-height:1.1;
  color:var(--text);
}
.logo-text h1 em{
  font-style:normal;
  background:linear-gradient(135deg,var(--cyan),var(--purple));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
}
.logo-text p{color:var(--muted);font-size:10.5px;margin-top:2px;font-family:var(--font-mono);letter-spacing:.04em}

.status-pill{
  display:flex;align-items:center;gap:7px;
  border:1px solid rgba(5,232,154,.18);
  color:var(--green);
  background:rgba(5,232,154,.05);
  padding:6px 12px;border-radius:var(--r-pill);
  font-size:10.5px;font-weight:600;
  font-family:var(--font-mono);letter-spacing:.08em;
  text-transform:uppercase;
  box-shadow:0 0 20px rgba(5,232,154,.06);
}
.dot{
  width:6px;height:6px;border-radius:50%;
  background:var(--green);
  box-shadow:0 0 0 3px rgba(5,232,154,.14),0 0 10px var(--green);
  animation:pulseGreen 2.2s ease-in-out infinite;
  flex-shrink:0;
}
@keyframes pulseGreen{
  0%,100%{box-shadow:0 0 0 3px rgba(5,232,154,.14),0 0 10px rgba(5,232,154,.55)}
  50%{box-shadow:0 0 0 6px rgba(5,232,154,.05),0 0 18px rgba(5,232,154,.8)}
}

/* ===== NAV ===== */
.nav{
  display:flex;gap:3px;
  overflow-x:auto;padding:0 0 10px;
  scrollbar-width:none;
}
.nav::-webkit-scrollbar{display:none}
.nav a{
  white-space:nowrap;
  padding:6px 13px;
  border-radius:var(--r-pill);
  border:1px solid transparent;
  color:var(--muted);
  font-weight:500;font-size:11.5px;
  font-family:var(--font-display);
  letter-spacing:-.01em;
  transition:var(--transition);
  position:relative;
}
.nav a:hover{color:var(--text2);background:rgba(255,255,255,.04);border-color:rgba(255,255,255,.07)}
.nav a.active-nav{
  color:var(--text);
  background:rgba(61,130,245,.1);
  border-color:rgba(61,130,245,.22);
  font-weight:600;
}

/* ===== MAIN SHELL ===== */
.shell{
  position:relative;z-index:1;
  max-width:1280px;margin:0 auto;padding:24px;
}

/* ===== GLASS CARDS ===== */
.glass,.panel,.game-card,.team-card,.bet-card{
  position:relative;
  background:linear-gradient(145deg,rgba(9,19,31,.88),rgba(5,11,20,.94));
  border:1px solid rgba(255,255,255,.07);
  border-radius:var(--r-card);
  box-shadow:0 2px 16px rgba(0,0,0,.4),inset 0 1px 0 rgba(255,255,255,.05);
  overflow:hidden;
}
.glass::before,.panel::before,.game-card::before,.team-card::before,.bet-card::before{
  content:"";
  position:absolute;inset:0;
  background:linear-gradient(145deg,rgba(255,255,255,.022) 0%,transparent 55%);
  pointer-events:none;
  border-radius:inherit;
}

/* Card hover */
.game-card,.team-card,.bet-card{
  transition:transform .24s var(--ease-out),box-shadow .24s,border-color .24s;
}
.game-card:hover,.team-card:hover,.bet-card:hover{
  transform:translateY(-5px) scale(1.004);
  box-shadow:0 20px 60px rgba(0,0,0,.55),0 0 0 1px rgba(61,130,245,.18),var(--glow-blue);
  border-color:rgba(61,130,245,.18);
}

/* ===== HERO LAYOUT ===== */
.hero{display:grid;grid-template-columns:1.35fr .65fr;gap:14px;margin:22px 0}
.hero-main{padding:30px;min-height:200px}
.hero-main h2{
  font-family:var(--font-display);
  font-size:40px;letter-spacing:-.07em;margin:0 0 10px;line-height:.96;
  background:linear-gradient(135deg,var(--text) 25%,var(--cyan));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
}
.hero-main p{color:var(--muted);font-size:13px;line-height:1.65;max-width:480px}
.hero-actions{margin-top:22px;display:flex;gap:10px;flex-wrap:wrap}

.btn{
  display:inline-flex;align-items:center;gap:7px;
  padding:9px 16px;border-radius:10px;
  border:1px solid rgba(255,255,255,.1);
  background:rgba(255,255,255,.04);
  font-weight:600;font-size:12px;
  font-family:var(--font-display);
  color:var(--text2);letter-spacing:-.01em;
  transition:var(--transition);cursor:pointer;
}
.btn:hover{border-color:rgba(61,130,245,.35);background:rgba(61,130,245,.08);color:var(--text);transform:translateY(-1px)}
.btn.primary{
  background:linear-gradient(135deg,var(--blue),var(--purple));
  border:0;color:#fff;
  box-shadow:0 4px 24px rgba(61,130,245,.28);
}
.btn.primary:hover{box-shadow:0 8px 36px rgba(61,130,245,.44);transform:translateY(-2px)}

.hero-side{padding:22px;display:flex;flex-direction:column;justify-content:center;gap:18px}
.hero-side .big{
  font-family:var(--font-display);
  font-size:54px;font-weight:800;letter-spacing:-.1em;
  line-height:1;
}
.hero-side .big.positive{
  background:linear-gradient(135deg,var(--green),var(--cyan));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
}
.hero-side .big.negative{
  background:linear-gradient(135deg,var(--red),var(--orange));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
}
.hero-side .label{color:var(--muted);font-size:10.5px;font-family:var(--font-mono);text-transform:uppercase;letter-spacing:.1em}

/* ===== METRICS STRIP ===== */
.metrics{
  display:grid;
  grid-template-columns:repeat(4,minmax(0,1fr));
  gap:10px;
  margin:18px 0 22px;
}
.metric{
  position:relative;overflow:hidden;
  background:linear-gradient(145deg,rgba(9,19,31,.88),rgba(5,11,20,.94));
  border:1px solid rgba(255,255,255,.07);
  border-radius:16px;padding:16px 18px;
  box-shadow:0 2px 12px rgba(0,0,0,.3);
  animation:metricRise .5s var(--ease-out) both;
  transition:var(--transition);
  cursor:default;
  min-width:0;
}
.metric:hover{border-color:rgba(61,130,245,.22);transform:translateY(-3px);box-shadow:0 14px 44px rgba(0,0,0,.4),var(--glow-blue)}
.metric::after{
  content:"";
  position:absolute;top:0;left:0;right:0;height:1px;
  background:linear-gradient(90deg,transparent,rgba(61,130,245,.28),transparent);
}
.metric:nth-child(1){animation-delay:.00s}
.metric:nth-child(2){animation-delay:.05s}
.metric:nth-child(3){animation-delay:.10s}
.metric:nth-child(4){animation-delay:.15s}
.metric:nth-child(5){animation-delay:.20s}
.metric:nth-child(6){animation-delay:.25s}
@keyframes metricRise{
  from{opacity:0;transform:translateY(18px)}
  to{opacity:1;transform:none}
}
.metric .label{
  color:var(--muted);font-size:9.5px;font-weight:600;
  font-family:var(--font-mono);text-transform:uppercase;letter-spacing:.1em;
}
.metric .value{
  font-family:var(--font-display);
  font-size:26px;font-weight:700;letter-spacing:-.06em;
  margin-top:6px;line-height:1;
}
.metric .hint{font-size:10px;color:var(--muted2);margin-top:6px;font-family:var(--font-mono)}

/* ===== SECTION HEADERS ===== */
.section-head{
  display:flex;justify-content:space-between;align-items:flex-end;
  gap:12px;margin:32px 0 16px;
}
.section-head h2{
  font-family:var(--font-display);
  font-size:21px;font-weight:700;letter-spacing:-.05em;
  color:var(--text);
}
.section-head p{margin:4px 0 0;color:var(--muted);font-size:12px;font-family:var(--font-mono)}
.chip{
  display:inline-flex;align-items:center;gap:6px;
  border:1px solid rgba(61,130,245,.18);
  background:rgba(61,130,245,.07);
  border-radius:var(--r-pill);padding:5px 11px;
  font-size:10.5px;font-weight:600;color:rgba(147,197,253,.85);
  font-family:var(--font-mono);letter-spacing:.02em;
}
.toolbar{display:flex;gap:7px;flex-wrap:wrap;align-items:center}

/* ===== CARD GRIDS ===== */
.cards,.team-grid{
  display:grid;
  grid-template-columns:repeat(auto-fit,minmax(290px,1fr));
  gap:12px;
}
.game-card,.team-card,.bet-card{
  padding:20px;
  animation:cardIn .42s var(--ease-out) both;
}
@keyframes cardIn{
  from{opacity:0;transform:translateY(14px) scale(.985)}
  to{opacity:1;transform:none}
}

/* Stagger */
.cards > *:nth-child(1){animation-delay:.00s}
.cards > *:nth-child(2){animation-delay:.04s}
.cards > *:nth-child(3){animation-delay:.08s}
.cards > *:nth-child(4){animation-delay:.12s}
.cards > *:nth-child(5){animation-delay:.16s}
.cards > *:nth-child(6){animation-delay:.20s}

.game-top,.bet-head{
  display:flex;justify-content:space-between;
  align-items:flex-start;gap:10px;
}
.game-title,.bet-title{
  font-family:var(--font-display);
  font-size:16px;font-weight:700;letter-spacing:-.04em;
}
.game-sub,.bet-sub{color:var(--muted);font-size:10.5px;margin-top:4px;font-family:var(--font-mono)}

/* ===== BADGES ===== */
.badge{
  display:inline-flex;align-items:center;justify-content:center;
  padding:4px 10px;border-radius:var(--r-pill);
  font-size:9.5px;font-weight:700;
  font-family:var(--font-mono);
  letter-spacing:.07em;border:1px solid transparent;
  text-transform:uppercase;white-space:nowrap;
  flex-shrink:0;
}
.badge.green{background:rgba(5,232,154,.1);color:var(--green);border-color:rgba(5,232,154,.22);box-shadow:0 0 10px rgba(5,232,154,.1)}
.badge.red{background:rgba(248,75,110,.1);color:var(--red);border-color:rgba(248,75,110,.22);box-shadow:0 0 10px rgba(248,75,110,.1)}
.badge.yellow{background:rgba(245,200,66,.1);color:var(--yellow);border-color:rgba(245,200,66,.22)}
.badge.orange{background:rgba(240,120,50,.1);color:var(--orange);border-color:rgba(240,120,50,.22)}
.badge.gray{background:rgba(90,117,153,.08);color:var(--muted);border-color:rgba(90,117,153,.18)}
.badge.win{background:rgba(5,232,154,.11);color:var(--green);border-color:rgba(5,232,154,.28)}
.badge.loss{background:rgba(248,75,110,.11);color:var(--red);border-color:rgba(248,75,110,.28)}
.badge.push{background:rgba(245,200,66,.1);color:var(--yellow);border-color:rgba(245,200,66,.22)}
.badge.pass{background:rgba(90,117,153,.07);color:var(--muted);border-color:rgba(90,117,153,.14)}

/* ===== SCORELINE ===== */
.scoreline{
  display:flex;align-items:center;justify-content:center;
  gap:10px;padding:14px 0 10px;
}
.team-score{
  text-align:center;flex:1;
  background:rgba(2,5,9,.55);
  border:1px solid rgba(255,255,255,.06);
  border-radius:12px;padding:12px 8px;
  transition:var(--transition);
}
.team-score:hover{border-color:rgba(61,130,245,.18)}
.team-score .team{color:var(--muted);font-size:9.5px;font-weight:600;font-family:var(--font-mono);text-transform:uppercase;letter-spacing:.08em}
.team-score .score{
  font-family:var(--font-display);
  font-size:26px;font-weight:700;margin-top:4px;letter-spacing:-.07em;
}
.vs{color:var(--muted2);font-size:9px;font-weight:700;font-family:var(--font-mono);letter-spacing:.06em}

/* ===== MINI STATS ===== */
.edge-row,.bet-kpis{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:13px}
.bet-kpis{grid-template-columns:repeat(4,1fr)}
.mini{
  background:rgba(2,5,9,.55);
  border:1px solid rgba(255,255,255,.06);
  border-radius:10px;padding:10px;
  transition:var(--transition);
}
.mini:hover{border-color:rgba(61,130,245,.16)}
.mini span{display:block;color:var(--muted);font-size:9.5px;font-weight:600;font-family:var(--font-mono);text-transform:uppercase;letter-spacing:.06em}
.mini b{font-size:14px;display:block;margin-top:4px;font-family:var(--font-display);font-weight:700;letter-spacing:-.04em}

/* ===== PROGRESS BAR ===== */
.progress{
  height:3px;border-radius:var(--r-pill);
  background:rgba(2,5,9,.8);
  overflow:hidden;margin-top:14px;
}
.progress>div{
  height:100%;border-radius:var(--r-pill);
  background:linear-gradient(90deg,var(--blue),var(--cyan),var(--green));
  width:var(--w);
  animation:fillProgress 1s var(--ease-out) forwards;
  position:relative;
}
.progress>div::after{
  content:"";
  position:absolute;right:0;top:0;bottom:0;
  width:18px;
  background:linear-gradient(90deg,transparent,rgba(255,255,255,.5));
  filter:blur(2px);
}
@keyframes fillProgress{from{width:0}to{width:var(--w)}}

/* ===== DETAILS GRID ===== */
.details{
  margin-top:14px;
  border-top:1px solid rgba(255,255,255,.05);
  padding-top:12px;
  display:grid;grid-template-columns:1fr 1fr;gap:10px;
}
.detail{font-size:10.5px;color:var(--muted);font-family:var(--font-mono)}
.detail b{display:block;color:var(--text);font-size:12px;margin-top:2px;font-family:var(--font-display);font-weight:600;letter-spacing:-.02em}

/* ===== TEAM CARDS ===== */
.team-name{font-family:var(--font-display);font-size:20px;font-weight:700;letter-spacing:-.05em}
.team-meta{color:var(--muted);font-size:10.5px;margin-top:3px;font-family:var(--font-mono)}
.team-bars{display:grid;gap:10px;margin-top:16px}
.bar-row{display:grid;grid-template-columns:76px 1fr 48px;gap:8px;align-items:center;color:var(--muted);font-size:10.5px;font-weight:600;font-family:var(--font-mono);letter-spacing:.02em}
.bar{height:5px;background:rgba(2,5,9,.8);border-radius:var(--r-pill);overflow:hidden}
.bar div{
  height:100%;border-radius:var(--r-pill);
  background:linear-gradient(90deg,var(--blue),var(--cyan));
  width:var(--w);
  animation:fillProgress 1.2s var(--ease-out) forwards;
}
/* ===== PANEL & TABLE ===== */
.panel{padding:20px;margin:14px 0}
.table-wrap{
  overflow-x:auto;border-radius:14px;
  border:1px solid rgba(255,255,255,.06);
  background:rgba(2,5,9,.45);
}
table{width:100%;border-collapse:collapse;font-size:12px}
th,td{padding:11px 14px;border-bottom:1px solid rgba(255,255,255,.05);text-align:left;transition:background .14s}
th{
  color:var(--muted);background:rgba(5,11,20,.9);
  font-size:9.5px;font-weight:600;
  text-transform:uppercase;letter-spacing:.1em;
  font-family:var(--font-mono);
}
tr:hover td{background:rgba(61,130,245,.04)}
tr:last-child td{border-bottom:0}

.positive{color:var(--green)}
.negative{color:var(--red)}
.yellow{color:var(--yellow)}
.neutral{color:var(--muted)}
.muted{color:var(--muted)}

.empty{
  padding:44px 24px;text-align:center;
  color:var(--muted);font-family:var(--font-mono);font-size:11.5px;
  letter-spacing:.02em;
}
.empty::before{
  content:"◎";
  display:block;font-size:26px;margin-bottom:12px;
  opacity:.25;
}

pre{
  background:rgba(2,5,9,.75);
  border:1px solid rgba(255,255,255,.07);
  border-radius:14px;padding:18px;
  white-space:pre-wrap;line-height:1.65;
  font-family:var(--font-mono);font-size:11.5px;
  color:#7a9ab8;
}

/* ===== FOOTER ===== */
.footer{
  color:var(--muted2);text-align:center;
  font-size:10.5px;padding:36px 0 28px;
  font-family:var(--font-mono);letter-spacing:.06em;
  border-top:1px solid rgba(255,255,255,.04);
  margin-top:48px;
}
.footer::before{
  content:"WNBA EDGE LAB  ·  ";
  color:var(--muted2);
}

/* ===== POLICY CARDS ===== */
.policy-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px}
.policy-card{
  background:linear-gradient(145deg,rgba(9,19,31,.88),rgba(5,11,20,.94));
  border:1px solid rgba(255,255,255,.07);
  border-radius:16px;padding:18px;
  box-shadow:0 2px 12px rgba(0,0,0,.3);
  transition:var(--transition);
}
.policy-card:hover{transform:translateY(-3px);border-color:rgba(61,130,245,.18)}
.policy-card h3{margin:0 0 8px;font-size:14px;font-family:var(--font-display);font-weight:700;letter-spacing:-.04em}
.policy-card p{margin:0;color:var(--muted);font-size:11.5px;line-height:1.55;font-family:var(--font-mono)}

/* ===== DRIVER GRID ===== */
.driver-grid{display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-top:14px}
.driver{
  background:rgba(2,5,9,.55);
  border:1px solid rgba(255,255,255,.06);
  border-radius:10px;padding:10px;
  transition:var(--transition);
}
.driver:hover{transform:scale(1.02)}
.driver span{display:block;color:var(--muted);font-size:9.5px;font-weight:600;font-family:var(--font-mono);text-transform:uppercase;letter-spacing:.07em}
.driver b{display:block;margin-top:4px;font-size:12px;font-weight:600;font-family:var(--font-display)}
.driver.positive{border-color:rgba(5,232,154,.2);background:rgba(5,232,154,.05)}
.driver.negative{border-color:rgba(248,75,110,.2);background:rgba(248,75,110,.05)}
.driver.neutral{border-color:rgba(255,255,255,.06)}

/* ===== VALIDATION & HEALTH CARDS ===== */
.validation-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:12px}
.health-card{
  background:linear-gradient(145deg,rgba(9,19,31,.88),rgba(5,11,20,.94));
  border:1px solid rgba(255,255,255,.07);
  border-radius:20px;padding:20px;
  position:relative;overflow:hidden;
  box-shadow:0 2px 12px rgba(0,0,0,.3);
  animation:cardIn .45s var(--ease-out) both;
  transition:var(--transition);
}
.health-card:hover{transform:translateY(-4px);border-color:rgba(61,130,245,.2);box-shadow:0 14px 44px rgba(0,0,0,.4),var(--glow-blue)}
.health-card::after{
  content:"";
  position:absolute;inset:-80px auto auto -80px;
  width:160px;height:160px;
  background:radial-gradient(circle,rgba(0,200,240,.1),transparent 65%);
  pointer-events:none;
}
.health-card h3{
  margin:0;font-size:10.5px;font-weight:700;
  font-family:var(--font-mono);
  color:var(--muted);text-transform:uppercase;letter-spacing:.08em;
  display:flex;align-items:center;gap:8px;
}
.health-card .mega{
  font-family:var(--font-display);
  font-size:40px;font-weight:800;letter-spacing:-.09em;
  margin-top:10px;line-height:1;
}
.health-card .caption{color:var(--muted);font-size:10.5px;margin-top:6px;line-height:1.4;font-family:var(--font-mono)}

/* ===== SPARKLINE ===== */
.sparkline{
  height:3px;border-radius:var(--r-pill);
  overflow:hidden;background:rgba(2,5,9,.8);
  margin-top:16px;
}
.sparkline div{
  height:100%;width:var(--w);
  background:linear-gradient(90deg,var(--blue),var(--cyan),var(--green));
  border-radius:var(--r-pill);
  animation:fillProgress 1.2s var(--ease-out) forwards;
  position:relative;
}
.sparkline div::after{
  content:"";
  position:absolute;right:0;top:-2px;bottom:-2px;
  width:6px;background:white;border-radius:50%;
  filter:blur(2px);opacity:.7;
}

/* ===== RESULT CARDS ===== */
.result-card{
  background:linear-gradient(145deg,rgba(9,19,31,.88),rgba(5,11,20,.94));
  border:1px solid rgba(255,255,255,.07);
  border-radius:18px;padding:16px;
  animation:cardIn .48s var(--ease-out) both;
  transition:var(--transition);
}
.result-card:hover{transform:translateY(-3px);border-color:rgba(61,130,245,.2)}
.result-top{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}
.result-title{font-size:15px;font-weight:700;letter-spacing:-.04em;font-family:var(--font-display)}
.result-sub{color:var(--muted);font-size:10.5px;margin-top:4px;font-family:var(--font-mono)}
.radar{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;margin-top:12px}
.radar .mini{min-height:58px}

/* ===== TIMELINE ===== */
.timeline{display:grid;gap:7px;margin-top:12px}
.timeline-row{
  display:grid;grid-template-columns:84px 1fr auto;gap:9px;align-items:center;
  padding:9px 12px;
  background:rgba(2,5,9,.45);
  border:1px solid rgba(255,255,255,.055);
  border-radius:11px;
  transition:var(--transition);
}
.timeline-row:hover{background:rgba(61,130,245,.05);border-color:rgba(61,130,245,.14)}
.timeline-row span{color:var(--muted);font-size:9.5px;font-weight:600;font-family:var(--font-mono)}
.timeline-row b{font-size:13px;font-weight:600;font-family:var(--font-display);letter-spacing:-.03em}

/* ===== PULSE RINGS ===== */
.pulse-ring{
  display:inline-flex;
  width:7px;height:7px;border-radius:50%;
  background:var(--green);
  box-shadow:0 0 0 3px rgba(5,232,154,.12),0 0 10px rgba(5,232,154,.55);
  animation:pulseGreen 2.2s ease-in-out infinite;
  flex-shrink:0;
}
.pulse-ring.red{background:var(--red);box-shadow:0 0 0 3px rgba(248,75,110,.12),0 0 10px rgba(248,75,110,.5);animation:pulseRed 2.2s ease-in-out infinite}
.pulse-ring.yellow{background:var(--yellow);box-shadow:0 0 0 3px rgba(245,200,66,.12),0 0 10px rgba(245,200,66,.5)}
@keyframes pulseRed{0%,100%{box-shadow:0 0 0 3px rgba(248,75,110,.12),0 0 10px rgba(248,75,110,.5)}50%{box-shadow:0 0 0 6px rgba(248,75,110,.05),0 0 18px rgba(248,75,110,.7)}}

/* ===== MEMORY SECTION ===== */
.memory-grid{display:grid;grid-template-columns:1.08fr .92fr;gap:14px;margin-top:14px}
.memory-feed{display:grid;gap:11px}
.memory-card{
  border:1px solid rgba(255,255,255,.07);
  background:linear-gradient(145deg,rgba(9,19,31,.88),rgba(5,11,20,.94));
  border-radius:18px;padding:16px;
  box-shadow:0 2px 12px rgba(0,0,0,.3);
  animation:cardIn .48s var(--ease-out) both;
  transition:var(--transition);
}
.memory-card:hover{transform:translateY(-3px);border-color:rgba(61,130,245,.2)}
.memory-card-top{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}
.memory-date{font-size:16px;font-weight:700;letter-spacing:-.05em;font-family:var(--font-display)}
.memory-note{color:var(--muted);font-size:12px;line-height:1.55;margin-top:8px;font-family:var(--font-mono)}

.trend-pill{
  display:inline-flex;align-items:center;gap:6px;
  padding:5px 10px;border-radius:var(--r-pill);
  font-size:9.5px;font-weight:700;font-family:var(--font-mono);
  border:1px solid rgba(255,255,255,.08);background:rgba(255,255,255,.04);
  transition:var(--transition);
}
.trend-pill.up{color:var(--green);border-color:rgba(5,232,154,.22);background:rgba(5,232,154,.07)}
.trend-pill.down{color:var(--red);border-color:rgba(248,75,110,.22);background:rgba(248,75,110,.07)}
.trend-pill.flat{color:var(--yellow);border-color:rgba(245,200,66,.22);background:rgba(245,200,66,.07)}

.memory-kpis{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:12px}
.memory-kpi{background:rgba(2,5,9,.55);border:1px solid rgba(255,255,255,.06);border-radius:11px;padding:10px}
.memory-kpi span{display:block;color:var(--muted);font-size:9.5px;font-weight:600;font-family:var(--font-mono);text-transform:uppercase;letter-spacing:.07em}
.memory-kpi b{display:block;margin-top:4px;font-size:15px;font-family:var(--font-display);font-weight:700;letter-spacing:-.05em}

.timeline-list{
  border:1px solid rgba(255,255,255,.07);border-radius:18px;
  background:rgba(2,5,9,.5);overflow:hidden;
  box-shadow:0 2px 12px rgba(0,0,0,.3);
}
.timeline-item{
  display:grid;grid-template-columns:86px 1fr auto;
  gap:10px;padding:11px 16px;
  border-bottom:1px solid rgba(255,255,255,.05);
  align-items:center;transition:background .14s;
}
.timeline-item:last-child{border-bottom:0}
.timeline-item:hover{background:rgba(61,130,245,.04)}
.timeline-item span{color:var(--muted);font-size:9.5px;font-weight:600;font-family:var(--font-mono)}
.timeline-item b{font-size:13px;font-weight:600;font-family:var(--font-display);letter-spacing:-.03em}
.timeline-item em{font-style:normal;color:var(--muted2);font-size:10.5px;font-family:var(--font-mono)}

/* ===== CHART PANELS ===== */
.chart-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px;margin-top:14px}
.chart-panel{
  position:relative;overflow:hidden;
  border:1px solid rgba(255,255,255,.07);border-radius:18px;
  background:linear-gradient(145deg,rgba(9,19,31,.88),rgba(5,11,20,.94));
  box-shadow:0 2px 12px rgba(0,0,0,.3),inset 0 1px 0 rgba(255,255,255,.04);
  padding:18px;animation:cardIn .5s var(--ease-out) both;
}
.chart-panel::before{
  content:"";position:absolute;right:-60px;top:-60px;
  width:150px;height:150px;border-radius:50%;
  background:radial-gradient(circle,rgba(0,200,240,.08),transparent 70%);
  pointer-events:none;
}
.chart-head{display:flex;align-items:flex-start;justify-content:space-between;gap:10px;margin-bottom:14px}
.chart-title{font-size:15px;font-weight:700;letter-spacing:-.05em;font-family:var(--font-display)}
.chart-sub{color:var(--muted);font-size:10.5px;margin-top:3px;line-height:1.35;font-family:var(--font-mono)}
.chart-canvas-wrap{position:relative;height:260px}
.chart-panel canvas{position:relative;z-index:2}

.research-metrics{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:14px 0}
.research-metric{
  border:1px solid rgba(255,255,255,.07);background:rgba(2,5,9,.5);
  border-radius:16px;padding:14px;
  box-shadow:0 2px 10px rgba(0,0,0,.2);
  transition:var(--transition);
}
.research-metric:hover{transform:translateY(-3px);border-color:rgba(61,130,245,.2)}
.research-metric span{display:block;color:var(--muted);font-size:9.5px;font-weight:600;font-family:var(--font-mono);text-transform:uppercase;letter-spacing:.08em}
.research-metric b{display:block;font-size:26px;letter-spacing:-.07em;margin-top:6px;font-family:var(--font-display);font-weight:700}
.research-metric small{display:block;color:var(--muted2);font-size:9.5px;margin-top:4px;font-family:var(--font-mono)}

/* ===== INTELLIGENCE / BRAIN PANEL ===== */
body.v11-enhanced::before{
  animation:ambientShift 16s ease-in-out infinite alternate;
}
@keyframes ambientShift{from{filter:hue-rotate(0deg)}to{filter:hue-rotate(20deg)}}

.live-strip{
  display:flex;gap:8px;overflow-x:auto;padding:9px 14px;
  margin:0 0 16px;border:1px solid rgba(255,255,255,.07);
  border-radius:var(--r-pill);background:rgba(2,5,9,.65);
  backdrop-filter:blur(20px);
  box-shadow:0 2px 16px rgba(0,0,0,.2),inset 0 1px 0 rgba(255,255,255,.04);
  scrollbar-width:none;
}
.live-strip::-webkit-scrollbar{display:none}

.status-dot{
  width:6px;height:6px;border-radius:50%;
  background:var(--green);flex-shrink:0;
  box-shadow:0 0 0 3px rgba(5,232,154,.12),0 0 8px rgba(5,232,154,.5);
  animation:pulseGreen 2.2s ease-in-out infinite;
}
.status-dot.yellow{background:var(--yellow);box-shadow:0 0 0 3px rgba(245,200,66,.12),0 0 8px rgba(245,200,66,.5)}
.status-dot.red{background:var(--red);box-shadow:0 0 0 3px rgba(248,75,110,.12),0 0 8px rgba(248,75,110,.5)}

.intelligence-hero{
  display:grid;grid-template-columns:1.08fr .92fr;gap:14px;
  align-items:stretch;margin-bottom:16px;
}
.brain-panel{
  position:relative;overflow:hidden;
  border:1px solid rgba(61,130,245,.14);border-radius:22px;padding:24px;
  background:linear-gradient(145deg,rgba(8,16,30,.96),rgba(4,10,18,.98)),
    radial-gradient(circle at 82% 12%,rgba(0,200,240,.1),transparent 42%);
  box-shadow:0 8px 48px rgba(0,0,0,.45),inset 0 1px 0 rgba(255,255,255,.05);
  animation:cardIn .55s var(--ease-out) both;
}
.brain-panel::before{
  content:"";position:absolute;inset:0;pointer-events:none;
  background:linear-gradient(118deg,transparent 28%,rgba(255,255,255,.032),transparent 68%);
  transform:translateX(-100%);animation:shimmer 9s ease-in-out infinite;
}
@keyframes shimmer{58%,100%{transform:translateX(128%)}}
@keyframes panelRise{from{opacity:0;transform:translateY(16px) scale(.99)}to{opacity:1;transform:none}}

.brain-kicker{
  display:inline-flex;align-items:center;gap:8px;
  border:1px solid rgba(0,200,240,.18);background:rgba(0,200,240,.06);
  padding:6px 12px;border-radius:var(--r-pill);
  color:#90ddf0;font-size:9.5px;font-weight:700;
  font-family:var(--font-mono);letter-spacing:.1em;text-transform:uppercase;
}
.brain-title{
  font-family:var(--font-display);
  font-size:34px;line-height:.95;
  margin:14px 0 10px;font-weight:800;letter-spacing:-.08em;
  background:linear-gradient(135deg,var(--text) 38%,var(--cyan));
  -webkit-background-clip:text;-webkit-text-fill-color:transparent;
}
.brain-copy{color:var(--muted);font-size:12px;line-height:1.65;max-width:760px;font-family:var(--font-mono)}

.intel-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px;margin-top:16px}
.intel-stat{
  background:rgba(2,5,9,.55);border:1px solid rgba(255,255,255,.07);
  border-radius:13px;padding:13px;transition:var(--transition);
}
.intel-stat:hover{transform:translateY(-2px);border-color:rgba(61,130,245,.22);box-shadow:0 8px 24px rgba(0,0,0,.3)}
.intel-stat span{display:block;color:var(--muted);font-size:9.5px;font-weight:600;font-family:var(--font-mono);text-transform:uppercase;letter-spacing:.08em}
.intel-stat b{display:block;margin-top:5px;font-size:20px;letter-spacing:-.06em;font-family:var(--font-display);font-weight:700}

.insight-feed{display:grid;gap:9px}
.insight-card{
  position:relative;overflow:hidden;
  border:1px solid rgba(255,255,255,.07);border-radius:16px;padding:16px;
  background:linear-gradient(145deg,rgba(9,19,31,.88),rgba(5,11,20,.94));
  box-shadow:0 2px 12px rgba(0,0,0,.25);
  animation:cardIn .48s var(--ease-out) both;
  transition:var(--transition);
}
.insight-card:hover{transform:translateY(-2px);border-color:rgba(61,130,245,.18)}
.insight-card::before{
  content:"";position:absolute;left:0;top:0;bottom:0;width:3px;
  background:var(--cyan);border-radius:0 2px 2px 0;
}
.insight-card.low::before{background:var(--yellow)}
.insight-card.medium::before{background:var(--blue)}
.insight-card.high::before{background:var(--green)}
.insight-card.very-low::before{background:var(--muted2)}

.insight-top{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}
.insight-title{font-size:14px;font-weight:700;letter-spacing:-.04em;font-family:var(--font-display)}
.insight-detail{color:var(--muted);font-size:11.5px;line-height:1.55;margin-top:8px;font-family:var(--font-mono)}
.insight-action{
  margin-top:10px;padding:9px 12px;border-radius:10px;
  background:rgba(2,5,9,.45);border:1px solid rgba(255,255,255,.06);
  color:#aac0da;font-size:11px;font-family:var(--font-mono);
}
.conf-badge{
  display:inline-flex;align-items:center;gap:5px;
  padding:4px 9px;border-radius:var(--r-pill);
  border:1px solid rgba(255,255,255,.1);background:rgba(255,255,255,.05);
  color:#b8cce0;font-size:9.5px;font-weight:700;
  font-family:var(--font-mono);text-transform:uppercase;letter-spacing:.06em;
  flex-shrink:0;
}
.conf-badge.high{color:var(--green);border-color:rgba(5,232,154,.22);background:rgba(5,232,154,.07)}
.conf-badge.medium{color:var(--blue);border-color:rgba(61,130,245,.22);background:rgba(61,130,245,.07)}
.conf-badge.low{color:var(--yellow);border-color:rgba(245,200,66,.22);background:rgba(245,200,66,.07)}

.research-console{
  border-radius:16px;border:1px solid rgba(255,255,255,.07);
  background:rgba(2,5,9,.75);
  box-shadow:inset 0 1px 0 rgba(255,255,255,.04),0 2px 16px rgba(0,0,0,.3);
  overflow:hidden;
}
.console-head{
  display:flex;justify-content:space-between;align-items:center;
  padding:11px 16px;border-bottom:1px solid rgba(255,255,255,.06);
  background:rgba(5,11,20,.7);
}
.console-head b{font-size:10.5px;letter-spacing:.1em;text-transform:uppercase;font-family:var(--font-mono);color:var(--muted)}
.console-body{
  padding:16px;font-family:var(--font-mono);
  color:#7a9db8;font-size:11.5px;line-height:1.65;
  white-space:pre-wrap;max-height:340px;overflow:auto;
}
.console-body::-webkit-scrollbar{width:4px}
.console-body::-webkit-scrollbar-track{background:transparent}
.console-body::-webkit-scrollbar-thumb{background:rgba(61,130,245,.2);border-radius:4px}

.float-orb{
  position:absolute;width:200px;height:200px;border-radius:50%;
  background:radial-gradient(circle,rgba(139,92,246,.1),transparent 70%);
  right:-80px;bottom:-80px;
  animation:orbFloat 11s ease-in-out infinite alternate;
  pointer-events:none;
}
@keyframes orbFloat{from{transform:translateY(0)}to{transform:translateY(-22px) translateX(-12px)}}

/* ===== MODEL HEALTH ===== */
.health-hero{
  display:grid;grid-template-columns:160px 1fr;gap:20px;
  align-items:center;
  background:linear-gradient(145deg,rgba(9,19,31,.92),rgba(4,10,18,.98));
  border:1px solid rgba(255,255,255,.07);border-radius:22px;padding:22px;
  box-shadow:0 6px 40px rgba(0,0,0,.32);
  position:relative;overflow:hidden;margin:14px 0 18px;
}
.health-hero::after{
  content:"";position:absolute;right:-60px;top:-60px;
  width:180px;height:180px;border-radius:50%;
  background:radial-gradient(circle,rgba(0,200,240,.12),transparent 70%);
}
.gauge{
  width:148px;height:148px;border-radius:50%;
  display:grid;place-items:center;
  background:
    conic-gradient(var(--gauge-color) calc(var(--score)*1%), rgba(5,11,20,.95) 0),
    radial-gradient(circle,#040a12 57%,transparent 58%);
  position:relative;
  animation:popGauge .72s var(--ease-out) both;
  box-shadow:0 0 36px rgba(0,0,0,.45);
}
.gauge::before{
  content:"";position:absolute;inset:11px;border-radius:50%;
  background:#030810;border:1px solid rgba(255,255,255,.06);
}
.gauge-inner{position:relative;text-align:center;z-index:2}
.gauge-score{
  font-family:var(--font-display);
  font-size:32px;font-weight:800;letter-spacing:-.08em;
  background:var(--gauge-color);-webkit-background-clip:text;-webkit-text-fill-color:transparent;
}
.gauge-label{font-size:9.5px;color:var(--muted);font-weight:600;text-transform:uppercase;letter-spacing:.08em;font-family:var(--font-mono)}
@keyframes popGauge{from{opacity:0;transform:scale(.84) rotate(-16deg)}to{opacity:1;transform:none}}

.health-info h2{margin:0;font-size:22px;letter-spacing:-.06em;font-family:var(--font-display);font-weight:700}
.health-info p{margin:8px 0 0;color:var(--muted);font-size:12px;line-height:1.55;font-family:var(--font-mono)}

.component-grid{display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-top:14px}
.component{
  background:rgba(2,5,9,.55);border:1px solid rgba(255,255,255,.06);
  border-radius:11px;padding:10px;transition:var(--transition);
}
.component:hover{border-color:rgba(61,130,245,.18);transform:translateY(-2px)}
.component span{display:block;color:var(--muted);font-size:9.5px;font-weight:600;font-family:var(--font-mono);text-transform:uppercase;letter-spacing:.06em}
.component b{display:block;margin-top:5px;font-size:14px;font-family:var(--font-display);font-weight:700;letter-spacing:-.05em}

/* ===== PICK CARDS (Validation) ===== */
.pick-card{
  border:1px solid rgba(255,255,255,.07);
  background:linear-gradient(145deg,rgba(9,19,31,.88),rgba(5,11,20,.94));
  border-radius:18px;padding:17px;
  animation:cardIn .45s var(--ease-out) both;
  transition:var(--transition);
}
.pick-card:hover{transform:translateY(-3px);border-color:rgba(61,130,245,.18)}
.pick-top{display:flex;justify-content:space-between;gap:10px;align-items:flex-start}
.pick-top h3{margin:0;font-size:15px;font-weight:700;letter-spacing:-.04em;font-family:var(--font-display)}
.pick-top p{margin:4px 0 0;color:var(--muted);font-size:10.5px;font-family:var(--font-mono)}
.mini-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:12px}
.mini-grid .mini{min-height:52px}
.mini-val{
  display:grid;grid-template-columns:repeat(2,1fr);gap:8px;margin-top:8px;
  padding-top:10px;border-top:1px solid rgba(255,255,255,.05);
}

/* ===== SUMMARY BOX ===== */
.summary-box{
  margin-top:12px;color:#8aaabb;font-size:11px;line-height:1.55;
  background:rgba(2,5,9,.45);border:1px solid rgba(255,255,255,.06);
  border-radius:10px;padding:10px;font-family:var(--font-mono);
}

/* ===== FILTER BUTTONS ===== */
.filter-row{display:flex;gap:7px;overflow-x:auto;margin:12px 0 18px;scrollbar-width:none}
.filter-row::-webkit-scrollbar{display:none}
.filter-btn{
  border:1px solid rgba(255,255,255,.09);background:rgba(255,255,255,.035);
  color:var(--muted);border-radius:var(--r-pill);padding:7px 14px;
  font-size:11px;font-weight:600;font-family:var(--font-display);letter-spacing:-.01em;
  cursor:pointer;transition:var(--transition);white-space:nowrap;
}
.filter-btn:hover{border-color:rgba(61,130,245,.28);color:var(--text)}
.filter-btn.active{
  background:linear-gradient(135deg,var(--blue),var(--purple));
  border:0;color:#fff;
  box-shadow:0 4px 18px rgba(61,130,245,.28);
}
.hidden-card{display:none!important}


/* ===== HERMES COMMAND CENTER V16 ===== */
.command-hero{
  display:grid;grid-template-columns:1.15fr .85fr;gap:14px;margin:22px 0 16px;
}
.command-main{
  padding:30px;min-height:230px;display:flex;flex-direction:column;justify-content:space-between;
  border-color:rgba(0,200,240,.14);
}
.command-kicker{display:flex;align-items:center;gap:8px;color:var(--cyan);font-family:var(--font-mono);font-size:10.5px;font-weight:700;text-transform:uppercase;letter-spacing:.1em;margin-bottom:14px}
.command-title{
  font-family:var(--font-display);
  font-size:46px;
  line-height:1;
  letter-spacing:-.07em;
  max-width:620px;
}

.command-title span{
  color:var(--cyan);
}
.command-sub{color:var(--muted);font-size:13px;max-width:650px;margin-top:12px;line-height:1.65;font-family:var(--font-mono)}
.command-grid{
  display:grid;
  grid-template-columns:repeat(4,1fr);
  gap:8px;
  margin:24px 0 0;
}
.command-tile{background:rgba(2,5,9,.5);border:1px solid rgba(255,255,255,.07);border-radius:13px;padding:13px;transition:var(--transition)}
.command-tile:hover{transform:translateY(-3px);border-color:rgba(0,200,240,.22);box-shadow:0 12px 35px rgba(0,0,0,.35)}
.command-tile span{display:block;color:var(--muted);font-family:var(--font-mono);font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.09em}
.command-tile b{display:block;margin-top:6px;font-family:var(--font-display);font-size:21px;font-weight:800;letter-spacing:-.06em}
.command-side{padding:22px;display:flex;flex-direction:column;gap:10px}
.operator-card{background:rgba(2,5,9,.5);border:1px solid rgba(255,255,255,.07);border-radius:14px;padding:13px;display:grid;grid-template-columns:1fr auto;gap:12px;align-items:center;transition:var(--transition)}
.operator-card:hover{border-color:rgba(5,232,154,.18);background:rgba(5,232,154,.03);transform:translateY(-2px)}
.operator-card .name{font-family:var(--font-display);font-size:15px;font-weight:700;letter-spacing:-.04em}
.operator-card .desc{font-family:var(--font-mono);font-size:10px;color:var(--muted);margin-top:3px}
.operator-state{font-family:var(--font-mono);font-size:10.5px;font-weight:700;border-radius:999px;padding:5px 10px;border:1px solid rgba(61,130,245,.18);color:var(--cyan);background:rgba(61,130,245,.08);white-space:nowrap}
.command-layout{display:grid;grid-template-columns:1.05fr .95fr;gap:14px;margin:16px 0}
.command-stack{display:grid;gap:12px}
.action-compact .cards{grid-template-columns:repeat(auto-fit,minmax(330px,1fr))}
.env-mini-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-top:12px}
.env-mini{background:rgba(2,5,9,.5);border:1px solid rgba(255,255,255,.06);border-radius:12px;padding:11px}
.env-mini span{display:block;color:var(--muted);font-family:var(--font-mono);font-size:9.5px;text-transform:uppercase;font-weight:700;letter-spacing:.07em}
.env-mini b{display:block;margin-top:5px;font-family:var(--font-display);font-size:18px;font-weight:800;letter-spacing:-.06em}
.activity-feed{display:grid;gap:7px;margin-top:10px}
.activity-row{display:grid;grid-template-columns:82px 1fr auto;gap:10px;align-items:center;background:rgba(2,5,9,.45);border:1px solid rgba(255,255,255,.06);border-radius:12px;padding:10px 12px;transition:var(--transition)}
.activity-row:hover{background:rgba(61,130,245,.05);border-color:rgba(61,130,245,.15);transform:translateX(3px)}
.activity-row span{color:var(--muted);font-family:var(--font-mono);font-size:9.5px;font-weight:700;text-transform:uppercase;letter-spacing:.05em}
.activity-row b{font-size:12px;font-weight:700;font-family:var(--font-display);letter-spacing:-.02em}
.activity-row em{font-style:normal;color:var(--green);font-family:var(--font-mono);font-size:10px;font-weight:800}
.terminal-section{border-color:rgba(5,232,154,.1);box-shadow:0 0 28px rgba(5,232,154,.03),0 2px 16px rgba(0,0,0,.35)}
@media(max-width:960px){.command-hero,.command-layout{grid-template-columns:1fr}.command-grid{grid-template-columns:repeat(2,1fr)}}
@media(max-width:560px){.command-title{font-size:34px}.command-grid,.env-mini-grid{grid-template-columns:1fr}.activity-row{grid-template-columns:1fr}.operator-card{grid-template-columns:1fr}}

/* ===== RESPONSIVE ===== */
@media(max-width:900px){
  .hero{grid-template-columns:1fr}
  .metrics{grid-template-columns:repeat(3,1fr)}
  .memory-grid{grid-template-columns:1fr}
  .intelligence-hero{grid-template-columns:1fr}
  .chart-grid{grid-template-columns:1fr}
  .research-metrics{grid-template-columns:repeat(2,minmax(0,1fr))}
  .health-hero{grid-template-columns:1fr}
  .component-grid{grid-template-columns:repeat(3,1fr)}
}
@media(max-width:620px){
  .shell{padding:14px}
  .top-inner{padding:0 14px}
  .hero-main h2{font-size:30px}
  .metrics{grid-template-columns:repeat(2,1fr)}
  .cards,.team-grid{grid-template-columns:1fr}
  .details{grid-template-columns:1fr}
  .status-pill{display:none}
  .bet-kpis{grid-template-columns:repeat(2,1fr)}
  .nav{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));overflow:visible;gap:4px}
  .nav a{text-align:center;padding:7px 4px;font-size:10.5px}
  .brain-title{font-size:26px}
  .component-grid{grid-template-columns:repeat(2,1fr)}
  .research-metrics{grid-template-columns:repeat(2,1fr)}
}
@media(max-width:480px){
  .metrics{grid-template-columns:repeat(2,1fr)}
  .chart-canvas-wrap{height:220px}
  .timeline-item{grid-template-columns:1fr;gap:4px}
  .research-metrics{grid-template-columns:1fr}
}



/* ===== V17 CLEAN POLISH LAYER ===== */
:root{--type-xs:9.5px;--type-sm:11px;--type-body:12.5px;--type-md:15px;--type-lg:20px;--type-xl:28px;--type-hero:42px}
.section-head{margin:26px 0 14px;align-items:center}
.section-head h2{font-size:22px!important;line-height:1.05!important;letter-spacing:-.045em!important}
.section-head p{font-size:11.5px!important;line-height:1.45!important;max-width:720px}
.command-title{font-size:42px!important;line-height:.98!important;letter-spacing:-.06em!important;max-width:660px!important}
.command-main{min-height:220px!important;padding:28px!important}
.command-sub{font-size:12px!important;max-width:720px!important}
.metrics{grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:10px!important}
.metric{padding:15px 16px!important;min-height:92px!important}
.metric .label,.command-tile span,.mini span,.env-mini span{font-size:9.2px!important;line-height:1.15!important}
.metric .value{font-size:25px!important;line-height:1.05!important;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.metric .hint{font-size:9.5px!important;line-height:1.25!important}
.game-title,.bet-title,.result-title,.chart-title,.memory-date{font-size:16px!important;line-height:1.15!important}
.game-sub,.bet-sub,.detail,.timeline-row span,.activity-row span{font-size:10px!important;line-height:1.35!important}
.cards,.team-grid{gap:13px!important}
.game-card,.team-card,.bet-card,.panel{border-radius:18px!important}

.action-panel-clean{margin:24px 0 22px}
.action-panel-clean .section-head{margin-top:0}
.action-grid-clean{display:grid;grid-template-columns:repeat(auto-fit,minmax(360px,1fr));gap:14px}
.action-card-clean{position:relative;padding:22px;border:1px solid rgba(5,232,154,.20);border-radius:22px;background:linear-gradient(145deg,rgba(8,20,30,.96),rgba(3,9,17,.98));box-shadow:0 18px 55px rgba(0,0,0,.42),0 0 30px rgba(5,232,154,.055);overflow:hidden;animation:cardIn .42s var(--ease-out) both;transition:var(--transition)}
.action-card-clean:hover{transform:translateY(-5px);border-color:rgba(5,232,154,.34);box-shadow:0 24px 70px rgba(0,0,0,.52),0 0 38px rgba(5,232,154,.12)}
.action-card-clean::after{content:"";position:absolute;right:-80px;top:-80px;width:190px;height:190px;border-radius:50%;background:radial-gradient(circle,rgba(5,232,154,.11),transparent 70%);pointer-events:none}
.action-head-clean{display:flex;justify-content:space-between;gap:12px;align-items:flex-start;margin-bottom:16px;position:relative;z-index:2}
.action-rank-clean{font-family:var(--font-mono);font-size:10px;color:var(--green);font-weight:800;letter-spacing:.12em;text-transform:uppercase}
.action-game-clean{font-family:var(--font-display);font-size:24px;font-weight:800;letter-spacing:-.055em;line-height:1.05;margin-top:4px;color:var(--text)}
.action-bet-clean{position:relative;z-index:2;font-family:var(--font-display);font-size:38px;font-weight:900;letter-spacing:-.075em;line-height:.95;color:var(--green);margin:12px 0 8px;text-shadow:0 0 28px rgba(5,232,154,.18)}
.action-meta-clean{position:relative;z-index:2;font-family:var(--font-mono);font-size:12px;color:var(--text2);margin-bottom:14px}
.action-meta-clean strong{color:var(--text);font-weight:800}
.action-kpis-clean{position:relative;z-index:2;display:grid;grid-template-columns:repeat(3,1fr);gap:8px}
.action-kpis-clean .mini{background:rgba(2,5,9,.62)}

.env-page-hero{display:grid;grid-template-columns:1fr .9fr;gap:14px;margin:22px 0 18px}
.env-page-title{font-family:var(--font-display);font-size:38px;font-weight:850;letter-spacing:-.065em;line-height:1;margin:0;color:var(--text)}
.env-page-copy{font-family:var(--font-mono);font-size:11.5px;color:var(--muted);line-height:1.6;margin-top:10px;max-width:720px}
.env-grid-clean{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:10px;margin-top:14px}
.env-tile-clean{background:rgba(2,5,9,.55);border:1px solid rgba(255,255,255,.065);border-radius:14px;padding:14px;transition:var(--transition)}
.env-tile-clean:hover{transform:translateY(-3px);border-color:rgba(0,200,240,.22)}
.env-tile-clean span{display:block;color:var(--muted);font-family:var(--font-mono);font-size:9.5px;text-transform:uppercase;font-weight:800;letter-spacing:.09em}
.env-tile-clean b{display:block;margin-top:6px;font-family:var(--font-display);font-size:24px;font-weight:850;letter-spacing:-.065em;line-height:1.05}
.env-panel-split{display:grid;grid-template-columns:1.05fr .95fr;gap:14px;margin-top:16px}

@media(max-width:960px){.metrics{grid-template-columns:repeat(2,minmax(0,1fr))!important}.env-page-hero,.env-panel-split{grid-template-columns:1fr}.action-grid-clean{grid-template-columns:1fr}.action-bet-clean{font-size:32px}.command-title{font-size:36px!important}}
@media(max-width:560px){.metrics{grid-template-columns:1fr!important}.command-grid{grid-template-columns:1fr!important}.action-game-clean{font-size:20px}.action-bet-clean{font-size:28px}.action-kpis-clean{grid-template-columns:1fr}.env-page-title{font-size:30px}}


/* ===== PAGE LOAD ANIMATION ===== */
@keyframes pageIn{
  from{opacity:0;transform:translateY(10px)}
  to{opacity:1;transform:none}
}
.shell{animation:pageIn .38s var(--ease-out) both}

/* ===== V17.1 SAFETY / RHYTHM PATCH ===== */
.command-tile,.env-mini,.operator-card,.activity-row,.metric,.panel{min-width:0}
.command-tile b,.env-mini b,.metric .value,.health-card .mega,.operator-state{font-variant-numeric:tabular-nums}
.command-grid{align-items:stretch}
.command-tile{display:flex;flex-direction:column;justify-content:space-between;gap:8px;min-height:78px}
.operator-card{min-height:72px}
.activity-row{min-height:50px}
.env-tile-clean{min-height:82px}
.action-card-clean{min-height:220px}
.action-bet-clean{overflow-wrap:anywhere}
@media(max-width:620px){.env-page-hero{grid-template-columns:1fr}.action-grid-clean{grid-template-columns:1fr}.action-card-clean{min-height:auto}}

/* ===== V17.2 ELITE POLISH PASS ===== */
:root{--elite-border:rgba(255,255,255,.085);--elite-soft:rgba(255,255,255,.038);--elite-ink:#f1f6ff}
.shell{padding-top:20px!important}
.topbar{border-bottom-color:rgba(0,200,240,.08)!important}
.logo-text h1{font-size:17px!important;letter-spacing:-.05em!important}
.logo-text p{color:#6e89aa!important}
.nav{gap:5px!important;padding-bottom:12px!important}
.nav a{font-size:11px!important;padding:7px 12px!important;border-color:rgba(255,255,255,.035)}
.nav a.active-nav{background:linear-gradient(135deg,rgba(61,130,245,.18),rgba(139,92,246,.12))!important;border-color:rgba(0,200,240,.20)!important;box-shadow:0 0 22px rgba(61,130,245,.08)}
.command-hero{grid-template-columns:1.22fr .78fr!important;gap:16px!important;margin-top:18px!important}
.command-main{min-height:242px!important;border-color:rgba(0,200,240,.18)!important;box-shadow:0 22px 70px rgba(0,0,0,.42),inset 0 1px 0 rgba(255,255,255,.055)!important}
.command-title{font-size:44px!important;line-height:.94!important;letter-spacing:-.072em!important;color:var(--elite-ink)}
.command-sub{font-size:12.2px!important;line-height:1.58!important;color:rgba(190,204,223,.86)!important;max-width:700px!important}
.command-grid{grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:9px!important;margin-top:22px!important}
.command-tile{min-height:86px!important;padding:14px!important;background:linear-gradient(145deg,rgba(2,8,15,.74),rgba(4,12,22,.58))!important;border-color:var(--elite-border)!important}
.command-tile b{font-size:22px!important;line-height:1!important;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.command-side{gap:9px!important;padding:20px!important}
.operator-card{min-height:76px!important;padding:14px!important;border-color:var(--elite-border)!important}
.operator-card .name{font-size:15.5px!important}
.operator-state{max-width:160px;overflow:hidden;text-overflow:ellipsis;text-align:right}
.section-head{margin:28px 0 13px!important}
.section-head h2{font-size:23px!important;letter-spacing:-.055em!important}
.section-head p{color:rgba(90,117,153,.95)!important}
.panel{padding:19px!important;border-color:var(--elite-border)!important}
.metrics{gap:11px!important}
.metric{min-height:96px!important;border-color:var(--elite-border)!important;background:linear-gradient(145deg,rgba(9,19,31,.9),rgba(4,10,18,.96))!important}
.metric .value{font-size:26px!important}
.cards,.team-grid,.validation-grid{gap:14px!important}
.game-card,.team-card,.bet-card,.health-card,.result-card,.memory-card,.chart-panel{border-color:var(--elite-border)!important}
.game-card,.team-card,.bet-card{min-height:236px}
.action-panel-clean{margin-top:20px!important}
.action-grid-clean{grid-template-columns:repeat(auto-fit,minmax(380px,1fr))!important;gap:15px!important}
.action-card-clean{min-height:232px!important;padding:23px!important;border-color:rgba(5,232,154,.24)!important}
.action-game-clean{font-size:23px!important}
.action-bet-clean{font-size:36px!important;line-height:.96!important}
.action-meta-clean{font-size:11.5px!important;color:rgba(190,204,223,.9)!important}
.action-kpis-clean .mini{min-height:66px}
.env-page-hero{grid-template-columns:1.08fr .92fr!important;gap:16px!important;margin-top:18px!important}
.env-page-title{font-size:40px!important;line-height:.96!important;letter-spacing:-.075em!important}
.env-page-copy{color:rgba(190,204,223,.78)!important}
.env-grid-clean{gap:9px!important}
.env-tile-clean{min-height:92px!important;padding:15px!important;border-color:var(--elite-border)!important;background:linear-gradient(145deg,rgba(2,8,15,.7),rgba(4,12,22,.55))!important}
.env-tile-clean b{font-size:25px!important;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.env-panel-split{gap:16px!important}
.table-wrap{border-color:rgba(255,255,255,.075)!important}
th{font-size:9px!important;color:#7894b6!important}
td{font-size:11.7px!important;color:rgba(232,238,248,.88)}
.activity-feed{gap:8px!important}
.activity-row{min-height:54px!important;border-color:var(--elite-border)!important}
.empty{border-radius:14px;background:rgba(2,5,9,.28);border:1px dashed rgba(255,255,255,.07)}
@media(max-width:960px){.command-hero{grid-template-columns:1fr!important}.command-side{display:grid;grid-template-columns:repeat(2,minmax(0,1fr))}.env-page-hero,.env-panel-split{grid-template-columns:1fr!important}.action-grid-clean{grid-template-columns:1fr!important}}
@media(max-width:620px){.shell{padding:14px!important}.command-title{font-size:34px!important}.command-grid,.command-side{grid-template-columns:1fr!important}.action-card-clean{padding:18px!important}.action-bet-clean{font-size:29px!important}.env-page-title{font-size:31px!important}.nav{grid-template-columns:repeat(3,minmax(0,1fr))!important}}

/* ===== V17.3 PRECISION POLISH PASS ===== */
:root{
  --precision-line:rgba(124,170,220,.105);
  --precision-panel:linear-gradient(145deg,rgba(8,18,31,.94),rgba(3,8,15,.985));
  --precision-terminal:rgba(1,5,10,.62);
}
body{font-feature-settings:"tnum" 1,"ss01" 1}
.topbar{box-shadow:0 1px 0 rgba(0,200,240,.065),0 14px 42px rgba(0,0,0,.38)!important}
.brand-row{padding-top:12px!important;padding-bottom:9px!important}
.logo-mark{width:38px!important;height:38px!important}
.status-pill{padding:7px 13px!important;background:rgba(5,232,154,.065)!important;border-color:rgba(5,232,154,.22)!important}
.nav{scroll-padding:24px!important}
.nav a{position:relative;overflow:hidden}
.nav a.active-nav::after{content:"";position:absolute;left:14px;right:14px;bottom:2px;height:2px;border-radius:999px;background:linear-gradient(90deg,var(--cyan),var(--purple));opacity:.85}
.shell{max-width:1320px!important}
.glass,.panel,.game-card,.team-card,.bet-card,.health-card,.result-card,.memory-card,.chart-panel,.action-card-clean{background:var(--precision-panel)!important;border-color:var(--precision-line)!important}
.command-hero{align-items:stretch!important;margin-bottom:18px!important}
.command-main::after{content:"";position:absolute;inset:auto 24px 0 24px;height:1px;background:linear-gradient(90deg,transparent,rgba(0,200,240,.32),rgba(139,92,246,.18),transparent);pointer-events:none}
.command-kicker{font-size:10px!important;color:#8be7ff!important;letter-spacing:.14em!important}
.command-title{max-width:720px!important;text-wrap:balance}
.command-sub{text-wrap:pretty}
.command-grid{margin-top:24px!important}
.command-tile{position:relative;overflow:hidden;isolation:isolate}
.command-tile::before{content:"";position:absolute;inset:0;background:radial-gradient(circle at 85% 0%,rgba(0,200,240,.08),transparent 42%);opacity:.7;z-index:-1}
.command-tile span,.env-tile-clean span,.metric .label,.mini span,.health-card h3,.chip,.badge{letter-spacing:.105em!important}
.command-tile b,.metric .value,.env-tile-clean b,.mini b{font-variant-numeric:tabular-nums!important}
.command-side{background:linear-gradient(145deg,rgba(7,16,28,.93),rgba(2,7,13,.985))!important}
.operator-card{background:rgba(1,5,10,.48)!important}
.operator-card .desc{color:rgba(90,117,153,.92)!important}
.operator-state{border-color:rgba(0,200,240,.20)!important;background:rgba(0,200,240,.065)!important;color:#99e7ff!important}
.section-head{padding-top:2px!important}
.section-head h2{text-wrap:balance}
.section-head p{text-wrap:pretty;color:rgba(142,162,190,.72)!important}
.metrics{margin-top:16px!important;margin-bottom:24px!important}
.metric{position:relative;overflow:hidden}
.metric::before{content:"";position:absolute;inset:0 0 auto 0;height:1px;background:linear-gradient(90deg,transparent,rgba(0,200,240,.22),transparent)}
.metric .hint{color:rgba(90,117,153,.82)!important}
.cards,.team-grid,.validation-grid,.chart-grid,.memory-feed{align-items:stretch!important}
.game-card,.team-card,.bet-card,.result-card,.memory-card,.health-card{display:flex;flex-direction:column;justify-content:space-between}
.game-top,.bet-head,.result-top,.pick-top,.memory-card-top{min-height:46px}
.edge-row,.bet-kpis,.mini-grid,.memory-kpis,.radar{margin-top:14px!important}
.mini,.memory-kpi,.driver,.component,.intel-stat,.research-metric{background:rgba(1,5,10,.48)!important;border-color:rgba(255,255,255,.07)!important}
.action-card-clean{border-color:rgba(5,232,154,.28)!important;box-shadow:0 18px 64px rgba(0,0,0,.46),0 0 34px rgba(5,232,154,.075)!important}
.action-rank-clean{color:#7dffc8!important}
.action-game-clean{text-wrap:balance}
.action-bet-clean{text-wrap:balance;max-width:92%}
.action-meta-clean{padding:9px 11px;border:1px solid rgba(255,255,255,.07);border-radius:12px;background:rgba(1,5,10,.42)}
.action-kpis-clean{margin-top:12px!important}
.env-page-hero .panel{min-height:100%}
.env-page-title{text-wrap:balance;max-width:720px}
.env-page-copy{text-wrap:pretty}
.env-tile-clean{position:relative;overflow:hidden}
.env-tile-clean::after{content:"";position:absolute;right:-30px;top:-30px;width:85px;height:85px;border-radius:50%;background:radial-gradient(circle,rgba(0,200,240,.08),transparent 70%);pointer-events:none}
.env-panel-split .panel{min-width:0}
.table-wrap{background:rgba(1,5,10,.52)!important;border-radius:16px!important}
th{position:sticky;top:0;z-index:3;background:rgba(4,11,20,.98)!important}
td,th{vertical-align:middle!important}
td{line-height:1.35!important}
tr:nth-child(even) td{background:rgba(255,255,255,.012)}
.empty{min-height:118px!important;display:grid!important;place-items:center!important;color:rgba(142,162,190,.72)!important}
.live-strip{border-color:var(--precision-line)!important;background:rgba(1,5,10,.54)!important}
.validation-note,.summary-box,.research-console,.timeline-list{border-color:var(--precision-line)!important;background:var(--precision-terminal)!important}
.footer{margin-top:42px!important;padding-top:28px!important;color:rgba(50,77,106,.9)!important}
@media(max-width:960px){.command-hero,.env-page-hero,.env-panel-split,.memory-grid,.intelligence-hero,.chart-grid{grid-template-columns:1fr!important}.command-side{grid-template-columns:repeat(2,minmax(0,1fr))!important}.command-main{min-height:auto!important}.action-grid-clean{grid-template-columns:1fr!important}}
@media(max-width:620px){.topbar{position:sticky!important}.brand-row{align-items:flex-start!important}.nav{grid-template-columns:repeat(3,minmax(0,1fr))!important}.nav a{font-size:10px!important;padding:8px 4px!important}.command-title{font-size:32px!important;letter-spacing:-.06em!important}.command-main{padding:22px!important}.command-side,.command-grid{grid-template-columns:1fr!important}.metric{min-height:84px!important}.action-bet-clean{max-width:100%;font-size:27px!important}.env-tile-clean b{font-size:21px!important}.panel{padding:16px!important}td,th{padding:10px 11px!important}}

/* ===== V17.4 APEX OPERATOR POLISH ===== */
:root{
  --apex-hairline:rgba(255,255,255,.082);
  --apex-cyan:rgba(0,200,240,.24);
  --apex-green:rgba(5,232,154,.22);
  --apex-shadow:0 18px 70px rgba(0,0,0,.48);
}
.shell{padding-top:22px!important}
.topbar{border-bottom-color:rgba(255,255,255,.07)!important}
.logo-text h1{font-size:15.5px!important;letter-spacing:-.035em!important}
.logo-text p{color:rgba(90,117,153,.88)!important}
.status-pill{box-shadow:0 0 28px rgba(5,232,154,.075)!important}
.nav{gap:4px!important;padding-bottom:11px!important}
.nav a{font-size:11px!important;padding:7px 13px!important;color:rgba(122,151,188,.88)!important}
.nav a:hover{transform:translateY(-1px);color:rgba(232,238,248,.96)!important}
.nav a.active-nav{background:linear-gradient(135deg,rgba(61,130,245,.12),rgba(139,92,246,.09))!important;border-color:rgba(0,200,240,.22)!important;box-shadow:0 0 22px rgba(0,200,240,.055)!important}
.live-strip{margin-bottom:18px!important}
.command-hero{gap:16px!important;margin-top:20px!important}
.command-main{padding:30px!important;border-color:rgba(0,200,240,.18)!important;box-shadow:var(--apex-shadow),inset 0 1px 0 rgba(255,255,255,.055)!important}
.command-title{font-size:43px!important;line-height:.94!important;letter-spacing:-.075em!important}
.command-sub{margin-top:13px!important;font-size:12.2px!important;color:rgba(190,204,223,.80)!important;max-width:760px!important}
.command-grid{grid-template-columns:repeat(4,minmax(0,1fr))!important;gap:9px!important;margin-top:26px!important}
.command-tile{min-height:86px!important;padding:14px!important;border-color:var(--apex-hairline)!important;background:linear-gradient(145deg,rgba(1,5,10,.58),rgba(6,15,26,.44))!important}
.command-tile b{font-size:22px!important;line-height:1.02!important;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.command-side{padding:20px!important;gap:9px!important;border-color:rgba(255,255,255,.075)!important}
.operator-card{min-height:70px!important;padding:12px 13px!important}
.operator-card .name{font-size:14.5px!important;line-height:1.1!important}
.operator-card .desc{font-size:9.7px!important;line-height:1.35!important}
.operator-state{font-size:9.8px!important;padding:5px 9px!important}
.section-head{margin:28px 0 13px!important;min-height:34px!important}
.section-head h2{font-size:21px!important;letter-spacing:-.055em!important}
.section-head p{font-size:11px!important;color:rgba(142,162,190,.68)!important}
.chip{padding:5px 10px!important;font-size:9.8px!important;border-color:rgba(0,200,240,.18)!important;background:rgba(0,200,240,.055)!important;color:#9be9ff!important}
.metrics{gap:11px!important}
.metric{border-color:var(--apex-hairline)!important;min-height:94px!important;padding:15px 17px!important}
.metric .value{font-size:26px!important;letter-spacing:-.07em!important}
.metric:hover,.game-card:hover,.team-card:hover,.bet-card:hover,.result-card:hover,.memory-card:hover,.health-card:hover{transform:translateY(-3px)!important;box-shadow:0 18px 58px rgba(0,0,0,.43),0 0 0 1px rgba(0,200,240,.11)!important}
.panel{padding:19px!important;margin:13px 0!important;border-color:var(--apex-hairline)!important}
.cards,.team-grid,.validation-grid{gap:14px!important}
.game-card,.team-card,.bet-card,.result-card,.memory-card,.health-card,.pick-card{border-color:var(--apex-hairline)!important;min-width:0!important}
.game-title,.bet-title,.result-title{font-size:15.5px!important;letter-spacing:-.045em!important}
.game-sub,.bet-sub,.result-sub{color:rgba(90,117,153,.82)!important}
.badge{font-size:9px!important;padding:4px 9px!important}
.scoreline{padding-top:13px!important}
.team-score{background:rgba(1,5,10,.54)!important;border-color:rgba(255,255,255,.065)!important}
.edge-row,.bet-kpis{gap:7px!important}
.mini{padding:9px!important;min-width:0!important}
.mini b{font-size:13.5px!important;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.action-panel-clean{margin-top:22px!important}
.action-grid-clean{grid-template-columns:repeat(auto-fit,minmax(370px,1fr))!important;gap:14px!important}
.action-card-clean{min-height:222px!important;padding:22px!important;border-color:rgba(5,232,154,.30)!important}
.action-card-clean::after{opacity:.82!important}
.action-game-clean{font-size:22px!important}
.action-bet-clean{font-size:34px!important;margin-top:10px!important;margin-bottom:9px!important;letter-spacing:-.07em!important}
.action-meta-clean{font-size:11.2px!important;margin-bottom:12px!important}
.action-kpis-clean{gap:7px!important}
.env-page-hero{gap:15px!important;margin:20px 0 16px!important}
.env-page-title{font-size:39px!important;letter-spacing:-.075em!important}
.env-page-copy{font-size:11.3px!important;color:rgba(190,204,223,.76)!important}
.env-grid-clean{grid-template-columns:repeat(auto-fit,minmax(168px,1fr))!important;gap:9px!important}
.env-tile-clean{min-height:88px!important;padding:14px!important;border-color:var(--apex-hairline)!important}
.env-tile-clean b{font-size:23px!important;line-height:1.04!important}
.env-panel-split{gap:15px!important;margin-top:14px!important}
.activity-row{min-height:52px!important;padding:9px 11px!important;grid-template-columns:78px 1fr auto!important}
.activity-row b{font-size:11.8px!important}
.activity-row em{font-size:9.7px!important}
.table-wrap{border-radius:15px!important;max-width:100%!important}
table{font-size:11.5px!important}
th,td{padding:10px 12px!important}
th{letter-spacing:.095em!important}
pre,.console-body{font-size:11px!important;line-height:1.62!important}
.empty{min-height:108px!important;padding:34px 22px!important}
.footer::before{content:"WNBA EDGE LAB · APEX COMMAND · "!important}
@media(max-width:960px){.command-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important}.operator-card{min-height:68px!important}.action-grid-clean{grid-template-columns:1fr!important}.env-grid-clean{grid-template-columns:repeat(2,minmax(0,1fr))!important}}
@media(max-width:620px){.shell{padding:13px!important}.nav{grid-template-columns:repeat(3,minmax(0,1fr))!important}.nav a{padding:7px 4px!important}.command-title{font-size:31px!important}.command-main{padding:20px!important}.command-grid,.command-side,.env-grid-clean{grid-template-columns:1fr!important}.command-tile{min-height:76px!important}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))!important}.action-bet-clean{font-size:26px!important}.activity-row{grid-template-columns:1fr!important}.env-page-title{font-size:30px!important}th,td{padding:9px 10px!important}}



/* ===== V17.5 OPERATOR FOCUS POLISH ===== */
:root{
  --focus-line:rgba(255,255,255,.095);
  --focus-panel:linear-gradient(145deg,rgba(7,17,29,.92),rgba(2,7,14,.98));
  --focus-terminal:rgba(1,5,10,.66);
}
.shell{max-width:1300px!important;padding-top:20px!important}
.top-inner{max-width:1300px!important}
.brand-row{padding-top:12px!important;padding-bottom:9px!important}
.logo-mark{width:38px!important;height:38px!important}
.status-pill{padding:5px 11px!important;font-size:10px!important}
.nav{padding-bottom:10px!important}
.nav a{font-size:10.8px!important;padding:7px 12px!important}
.live-strip{padding:8px 13px!important;margin-bottom:16px!important}
.command-hero{grid-template-columns:minmax(0,1.2fr) minmax(320px,.8fr)!important;gap:15px!important;margin:18px 0 15px!important}
.command-main{min-height:214px!important;padding:28px!important;background:linear-gradient(145deg,rgba(8,20,32,.96),rgba(2,7,14,.99))!important}
.command-kicker{margin-bottom:12px!important;color:#98edff!important}
.command-title{font-size:41px!important;line-height:.95!important;max-width:700px!important}
.command-sub{font-size:11.8px!important;line-height:1.58!important;max-width:800px!important;color:rgba(190,204,223,.76)!important}
.command-grid{margin-top:23px!important;gap:8px!important}
.command-tile{min-height:80px!important;padding:13px!important;background:rgba(1,5,10,.58)!important;border-color:var(--focus-line)!important}
.command-tile span{font-size:9px!important;letter-spacing:.105em!important;color:rgba(142,162,190,.76)!important}
.command-tile b{font-size:21px!important;margin-top:5px!important}
.command-side{padding:17px!important;display:grid!important;align-content:start!important;background:linear-gradient(145deg,rgba(6,15,26,.88),rgba(2,7,14,.96))!important}
.operator-card{min-height:64px!important;padding:11px 12px!important;background:var(--focus-terminal)!important;border-color:rgba(255,255,255,.075)!important}
.operator-card .name{font-size:14px!important}
.operator-card .desc{font-size:9.4px!important;color:rgba(90,117,153,.78)!important}
.operator-state{font-size:9.4px!important;max-width:132px!important;overflow:hidden!important;text-overflow:ellipsis!important;text-align:center!important}
.section-head{margin:25px 0 12px!important;align-items:center!important}
.section-head h2{font-size:20.5px!important;line-height:1.05!important}
.section-head p{font-size:10.8px!important;line-height:1.42!important}
.chip{font-size:9.5px!important;padding:4px 9px!important}
.metrics{margin:16px 0 20px!important;gap:10px!important}
.metric{min-height:88px!important;padding:14px 15px!important;background:var(--focus-panel)!important;border-color:var(--focus-line)!important}
.metric .value{font-size:24px!important}.metric .hint{font-size:9.2px!important}
.cards,.team-grid,.validation-grid{gap:12px!important}
.game-card,.team-card,.bet-card,.result-card,.memory-card,.health-card,.pick-card,.panel,.chart-panel{background:var(--focus-panel)!important;border-color:var(--focus-line)!important}
.game-card,.team-card,.bet-card{padding:18px!important}
.game-title,.bet-title,.result-title{font-size:15px!important;line-height:1.13!important}
.scoreline{gap:8px!important;padding:12px 0 9px!important}.team-score{padding:10px 7px!important}.team-score .score{font-size:24px!important}
.edge-row,.bet-kpis,.mini-grid{gap:7px!important}.mini{padding:8px!important;border-color:rgba(255,255,255,.065)!important;background:rgba(1,5,10,.56)!important}.mini span,.memory-kpi span,.research-metric span,.component span{font-size:9px!important}.mini b{font-size:13px!important}
.details{gap:8px!important;margin-top:12px!important;padding-top:11px!important}
.action-panel-clean{margin:20px 0 20px!important}.action-grid-clean{grid-template-columns:repeat(auto-fit,minmax(350px,1fr))!important;gap:12px!important}.action-card-clean{min-height:205px!important;padding:20px!important;border-radius:20px!important;background:linear-gradient(145deg,rgba(6,20,27,.96),rgba(2,7,14,.99))!important}.action-rank-clean{font-size:9.5px!important}.action-game-clean{font-size:20px!important;line-height:1.05!important}.action-bet-clean{font-size:31px!important;line-height:.94!important;margin:9px 0 8px!important}.action-meta-clean{font-size:10.8px!important;line-height:1.45!important}.action-kpis-clean{grid-template-columns:repeat(3,minmax(0,1fr))!important;gap:7px!important}
.env-page-hero{grid-template-columns:minmax(0,1.05fr) minmax(300px,.95fr)!important;margin-top:18px!important;gap:14px!important}.env-page-title{font-size:37px!important;line-height:.96!important}.env-page-copy{font-size:11px!important;line-height:1.55!important}.env-grid-clean{grid-template-columns:repeat(auto-fit,minmax(160px,1fr))!important;gap:8px!important}.env-tile-clean{min-height:82px!important;padding:13px!important;background:var(--focus-terminal)!important}.env-tile-clean span{font-size:9px!important}.env-tile-clean b{font-size:21px!important}.env-panel-split{gap:13px!important}
.activity-feed{gap:6px!important}.activity-row{min-height:48px!important;padding:8px 10px!important;grid-template-columns:74px 1fr auto!important;background:var(--focus-terminal)!important}.activity-row span{font-size:9px!important}.activity-row b{font-size:11.5px!important}.activity-row em{font-size:9.3px!important}
.table-wrap{background:rgba(1,5,10,.58)!important;border-color:rgba(255,255,255,.07)!important}table{font-size:11.2px!important}th,td{padding:9px 11px!important}th{font-size:9px!important;background:rgba(4,10,18,.96)!important;color:rgba(142,162,190,.78)!important}tr:hover td{background:rgba(0,200,240,.035)!important}
.empty{min-height:98px!important;padding:30px 20px!important;font-size:11px!important;color:rgba(142,162,190,.68)!important}
.health-hero{padding:20px!important;gap:17px!important}.gauge{width:136px!important;height:136px!important}.gauge-score{font-size:30px!important}.component-grid{gap:7px!important}.component{padding:9px!important}
.research-metrics{gap:9px!important;margin:12px 0!important}.research-metric{padding:12px!important}.chart-grid{gap:12px!important}.chart-panel{padding:16px!important}.chart-canvas-wrap{height:244px!important}.memory-grid{gap:12px!important}.memory-kpis{gap:7px!important}.timeline-item,.timeline-row{padding:9px 12px!important}pre,.console-body{font-size:10.8px!important;line-height:1.58!important}
.footer{margin-top:38px!important;padding-bottom:24px!important}.footer::before{content:"WNBA EDGE LAB · OPERATOR FOCUS · "!important}
@media(max-width:960px){.command-hero,.env-page-hero{grid-template-columns:1fr!important}.command-side{grid-template-columns:repeat(2,minmax(0,1fr))!important}.command-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important}.env-grid-clean{grid-template-columns:repeat(2,minmax(0,1fr))!important}.action-grid-clean{grid-template-columns:1fr!important}}
@media(max-width:620px){.shell{padding:12px!important}.brand-row{gap:10px!important}.logo-text p{display:none!important}.nav{grid-template-columns:repeat(3,minmax(0,1fr))!important}.nav a{font-size:9.8px!important;padding:7px 3px!important}.command-title{font-size:29px!important}.command-main{padding:19px!important}.command-grid,.command-side,.env-grid-clean{grid-template-columns:1fr!important}.operator-state{max-width:100%!important}.metrics{grid-template-columns:repeat(2,minmax(0,1fr))!important}.action-bet-clean{font-size:24px!important}.action-card-clean{padding:18px!important}.env-page-title{font-size:28px!important}.activity-row{grid-template-columns:1fr!important}.chart-canvas-wrap{height:210px!important}th,td{padding:8px 9px!important}}



/* ===== V18.1 TODAY REFINEMENT — CLEAN HOME COMMAND FLOW ===== */
.today-status-strip{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:8px;margin:14px 0 18px;}
.today-status-tile{border:1px solid rgba(255,255,255,.065);border-radius:15px;padding:12px 13px;background:linear-gradient(145deg,rgba(7,17,28,.88),rgba(3,8,15,.96));box-shadow:0 2px 14px rgba(0,0,0,.28);min-height:74px;overflow:hidden;}
.today-status-tile span{display:block;color:var(--muted);font-family:var(--font-mono);font-size:9.3px;font-weight:800;text-transform:uppercase;letter-spacing:.085em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.today-status-tile b{display:block;margin-top:6px;font-family:var(--font-display);font-size:22px;font-weight:850;letter-spacing:-.07em;line-height:1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.today-status-tile small{display:block;margin-top:6px;color:var(--muted2);font-family:var(--font-mono);font-size:9.6px;line-height:1.25;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.today-flow{display:grid;grid-template-columns:1.04fr .96fr;gap:14px;margin:18px 0;}
.today-panel{position:relative;border:1px solid rgba(255,255,255,.07);border-radius:20px;padding:18px;background:linear-gradient(145deg,rgba(8,18,30,.92),rgba(3,8,15,.98));box-shadow:0 3px 22px rgba(0,0,0,.34);overflow:hidden;}
.today-panel::before{content:"";position:absolute;inset:0;background:linear-gradient(140deg,rgba(255,255,255,.025),transparent 52%);pointer-events:none}
.today-panel-head{display:flex;justify-content:space-between;align-items:flex-start;gap:12px;margin-bottom:12px;position:relative;z-index:2}
.today-kicker{display:flex;align-items:center;gap:7px;color:var(--cyan);font-family:var(--font-mono);font-size:9.6px;font-weight:850;text-transform:uppercase;letter-spacing:.11em}
.today-panel-title{font-family:var(--font-display);font-size:22px;font-weight:850;letter-spacing:-.065em;line-height:1.02;margin-top:6px}
.today-panel-sub{color:var(--muted);font-family:var(--font-mono);font-size:10.8px;line-height:1.5;margin-top:6px;max-width:680px}
.today-list{display:grid;gap:8px;position:relative;z-index:2}
.today-row{display:grid;grid-template-columns:86px 1fr auto;gap:10px;align-items:center;border:1px solid rgba(255,255,255,.06);border-radius:13px;padding:10px 12px;background:rgba(2,5,9,.48);}
.today-row span{color:var(--muted);font-family:var(--font-mono);font-size:9.4px;font-weight:800;text-transform:uppercase;letter-spacing:.07em}
.today-row b{font-family:var(--font-display);font-size:13.5px;font-weight:760;letter-spacing:-.03em;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.today-row em{font-style:normal;color:var(--green);font-family:var(--font-mono);font-size:10px;font-weight:850;white-space:nowrap}
.today-row.warn em{color:var(--yellow)}
.today-row.lock em{color:var(--cyan)}
.today-main-layout{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(320px,.75fr);gap:14px;align-items:start;margin-top:10px}
.today-side-stack{display:grid;gap:14px}
.today-compact-projections .cards{grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:11px}
.today-compact-projections .game-card{padding:16px;min-height:0}
.today-compact-projections .scoreline{padding:10px 0 8px}
.today-compact-projections .details{display:none}
.today-compact-projections .progress{margin-top:11px}
@media(max-width:1060px){.today-status-strip{grid-template-columns:repeat(3,minmax(0,1fr))}.today-flow,.today-main-layout{grid-template-columns:1fr}.today-side-stack{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:620px){.today-status-strip{grid-template-columns:repeat(2,minmax(0,1fr));gap:7px}.today-status-tile{min-height:68px;padding:11px}.today-status-tile b{font-size:19px}.today-flow{gap:10px}.today-panel{padding:15px;border-radius:17px}.today-panel-title{font-size:20px}.today-row{grid-template-columns:1fr;gap:4px}.today-side-stack{grid-template-columns:1fr}.today-compact-projections .cards{grid-template-columns:1fr}}


/* ===== V18.2 WEBSITE EDITION ===== */
.site-hero{display:grid;grid-template-columns:1.18fr .82fr;gap:16px;margin:18px 0 20px;align-items:stretch}
.site-hero-main{padding:34px;min-height:310px;display:flex;flex-direction:column;justify-content:space-between;border-radius:26px;border-color:rgba(0,200,240,.16);background:radial-gradient(circle at 78% 18%,rgba(0,200,240,.12),transparent 34%),radial-gradient(circle at 15% 88%,rgba(5,232,154,.07),transparent 34%),linear-gradient(145deg,rgba(9,19,31,.94),rgba(4,10,18,.985))}
.site-eyebrow{display:inline-flex;align-items:center;gap:8px;width:max-content;border:1px solid rgba(0,200,240,.18);background:rgba(0,200,240,.06);color:#9ce8f8;padding:7px 13px;border-radius:999px;font-family:var(--font-mono);font-size:10px;text-transform:uppercase;letter-spacing:.11em;font-weight:800}
.site-title{font-family:var(--font-display);font-size:58px;line-height:.91;letter-spacing:-.085em;max-width:850px;margin:18px 0 14px;background:linear-gradient(135deg,var(--text) 28%,var(--cyan) 72%,var(--purple));-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.site-copy{color:rgba(190,204,223,.82);font-family:var(--font-mono);font-size:12.5px;line-height:1.7;max-width:760px}
.site-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:24px}.site-actions .btn{padding:10px 16px}
.site-side{display:grid;grid-template-columns:1fr 1fr;gap:10px}
.site-card{position:relative;overflow:hidden;min-height:145px;border:1px solid rgba(255,255,255,.075);border-radius:20px;background:linear-gradient(145deg,rgba(9,19,31,.9),rgba(3,8,15,.97));padding:18px;box-shadow:0 12px 38px rgba(0,0,0,.34);transition:var(--transition)}
.site-card:hover{transform:translateY(-4px);border-color:rgba(0,200,240,.22);box-shadow:0 20px 54px rgba(0,0,0,.42),0 0 32px rgba(0,200,240,.08)}
.site-card::after{content:"";position:absolute;right:-46px;top:-46px;width:115px;height:115px;border-radius:50%;background:radial-gradient(circle,rgba(0,200,240,.09),transparent 70%)}
.site-card span{display:block;color:var(--muted);font-family:var(--font-mono);font-size:9.5px;text-transform:uppercase;letter-spacing:.1em;font-weight:800}
.site-card b{display:block;margin-top:8px;font-family:var(--font-display);font-size:28px;line-height:.98;letter-spacing:-.07em;font-weight:850;color:var(--text)}
.site-card p{margin-top:10px;color:var(--muted);font-family:var(--font-mono);font-size:10.5px;line-height:1.45}
.site-section-label{display:flex;justify-content:space-between;align-items:flex-end;gap:14px;margin:26px 0 12px;padding-top:14px;border-top:1px solid rgba(255,255,255,.055)}
.site-section-label h2{font-family:var(--font-display);font-size:25px;line-height:1;letter-spacing:-.06em;margin:0}
.site-section-label p{margin:6px 0 0;color:var(--muted);font-family:var(--font-mono);font-size:11px;line-height:1.5;max-width:760px}
.website-band{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:14px 0 18px}
.website-band-card{border:1px solid rgba(255,255,255,.07);background:rgba(2,5,9,.48);border-radius:16px;padding:15px;min-height:112px;transition:var(--transition)}
.website-band-card:hover{transform:translateY(-3px);border-color:rgba(61,130,245,.2);background:rgba(61,130,245,.045)}
.website-band-card span{font-family:var(--font-mono);font-size:9px;color:var(--cyan);font-weight:800;text-transform:uppercase;letter-spacing:.11em}
.website-band-card b{display:block;font-family:var(--font-display);font-size:17px;letter-spacing:-.045em;line-height:1.1;margin-top:8px}
.website-band-card p{font-family:var(--font-mono);font-size:10px;color:var(--muted);line-height:1.45;margin-top:7px}
.topbar{border-bottom-color:rgba(0,200,240,.08)!important}.logo-text h1{font-size:17px!important}.footer{margin-top:58px!important;padding:30px 0!important;border-top-color:rgba(0,200,240,.07)!important}
@media(max-width:980px){.site-hero{grid-template-columns:1fr}.site-side{grid-template-columns:repeat(2,minmax(0,1fr))}.website-band{grid-template-columns:repeat(2,minmax(0,1fr))}.site-title{font-size:46px}}
@media(max-width:620px){.site-hero-main{padding:24px;min-height:auto}.site-title{font-size:38px}.site-side,.website-band{grid-template-columns:1fr}.site-card{min-height:auto}.site-section-label{display:block}}

/* ===== V18.3 TRUE WEBSITE RESET ===== */
.web-home{display:grid;gap:18px;margin-top:18px}.web-hero{position:relative;overflow:hidden;border:1px solid rgba(0,200,240,.16);border-radius:30px;padding:42px;background:radial-gradient(circle at 78% 18%,rgba(0,200,240,.14),transparent 32%),radial-gradient(circle at 18% 82%,rgba(5,232,154,.08),transparent 36%),linear-gradient(145deg,rgba(9,19,31,.96),rgba(3,8,15,.99));box-shadow:0 24px 80px rgba(0,0,0,.42),inset 0 1px 0 rgba(255,255,255,.06)}.web-hero-grid{position:relative;z-index:2;display:grid;grid-template-columns:minmax(0,1.12fr) minmax(340px,.88fr);gap:28px;align-items:end}.web-eyebrow{display:inline-flex;align-items:center;gap:8px;border:1px solid rgba(0,200,240,.18);background:rgba(0,200,240,.06);color:#9ce8f8;padding:7px 13px;border-radius:999px;font-family:var(--font-mono);font-size:10px;text-transform:uppercase;letter-spacing:.12em;font-weight:850}.web-title{font-family:var(--font-display);font-size:70px;line-height:.88;letter-spacing:-.095em;max-width:920px;margin:20px 0 16px;background:linear-gradient(135deg,var(--text) 18%,var(--cyan) 68%,var(--purple));-webkit-background-clip:text;-webkit-text-fill-color:transparent}.web-copy{color:rgba(190,204,223,.86);font-family:var(--font-mono);font-size:13px;line-height:1.75;max-width:780px}.web-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:26px}.web-actions .btn{padding:10px 17px}.web-kpi-panel{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px}.web-kpi{min-height:126px;border:1px solid rgba(255,255,255,.075);border-radius:20px;background:rgba(2,5,9,.48);padding:18px;box-shadow:0 12px 38px rgba(0,0,0,.3);transition:var(--transition)}.web-kpi:hover{transform:translateY(-4px);border-color:rgba(0,200,240,.22);background:rgba(0,200,240,.045)}.web-kpi span{display:block;color:var(--muted);font-family:var(--font-mono);font-size:9.3px;text-transform:uppercase;letter-spacing:.105em;font-weight:850}.web-kpi b{display:block;margin-top:8px;font-family:var(--font-display);font-size:34px;line-height:.95;letter-spacing:-.08em;font-weight:900;color:var(--text)}.web-kpi p{margin-top:10px;color:var(--muted);font-family:var(--font-mono);font-size:10.5px;line-height:1.45}.web-section{margin:10px 0}.web-section-head{display:flex;justify-content:space-between;align-items:flex-end;gap:16px;margin:26px 0 12px}.web-section-head h2{margin:0;font-family:var(--font-display);font-size:30px;line-height:.96;letter-spacing:-.07em}.web-section-head p{margin:7px 0 0;color:var(--muted);font-family:var(--font-mono);font-size:11.2px;line-height:1.55;max-width:780px}.web-feature-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.web-feature{position:relative;overflow:hidden;min-height:170px;border:1px solid rgba(255,255,255,.07);border-radius:22px;background:linear-gradient(145deg,rgba(9,19,31,.9),rgba(3,8,15,.97));padding:20px;transition:var(--transition);box-shadow:0 8px 30px rgba(0,0,0,.28)}.web-feature:hover{transform:translateY(-5px);border-color:rgba(61,130,245,.22);box-shadow:0 18px 55px rgba(0,0,0,.4),0 0 32px rgba(61,130,245,.07)}.web-feature span{font-family:var(--font-mono);font-size:9.4px;color:var(--cyan);font-weight:850;text-transform:uppercase;letter-spacing:.11em}.web-feature b{display:block;font-family:var(--font-display);font-size:21px;letter-spacing:-.055em;line-height:1.04;margin-top:10px}.web-feature p{font-family:var(--font-mono);font-size:10.7px;color:var(--muted);line-height:1.55;margin-top:10px}.web-split{display:grid;grid-template-columns:minmax(0,1fr) minmax(340px,.8fr);gap:14px;align-items:stretch}.web-preview{border:1px solid rgba(255,255,255,.07);border-radius:24px;background:linear-gradient(145deg,rgba(9,19,31,.88),rgba(3,8,15,.98));padding:22px;overflow:hidden}.web-preview h3{font-family:var(--font-display);font-size:24px;letter-spacing:-.06em;margin:0 0 7px}.web-preview p{font-family:var(--font-mono);font-size:11px;color:var(--muted);line-height:1.55;margin:0 0 14px}.web-mini-list{display:grid;gap:8px}.web-mini-row{display:grid;grid-template-columns:90px 1fr auto;gap:10px;align-items:center;border:1px solid rgba(255,255,255,.06);border-radius:13px;background:rgba(2,5,9,.52);padding:10px 12px}.web-mini-row span{color:var(--muted);font-family:var(--font-mono);font-size:9.4px;text-transform:uppercase;letter-spacing:.08em;font-weight:850}.web-mini-row b{font-family:var(--font-display);font-size:13px;letter-spacing:-.03em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.web-mini-row em{font-style:normal;color:var(--green);font-family:var(--font-mono);font-size:10px;font-weight:850;white-space:nowrap}.web-mini-row.warn em{color:var(--yellow)}
.hermes-product{display:grid;gap:16px;margin-top:18px}.hermes-hero{position:relative;overflow:hidden;border:1px solid rgba(5,232,154,.16);border-radius:30px;padding:38px;background:radial-gradient(circle at 82% 18%,rgba(5,232,154,.12),transparent 34%),radial-gradient(circle at 18% 90%,rgba(0,200,240,.08),transparent 38%),linear-gradient(145deg,rgba(8,18,30,.96),rgba(3,8,15,.99));box-shadow:0 24px 80px rgba(0,0,0,.42)}.hermes-hero h1{font-family:var(--font-display);font-size:62px;line-height:.9;letter-spacing:-.09em;max-width:900px;margin:18px 0 12px;background:linear-gradient(135deg,var(--text) 24%,var(--green) 74%,var(--cyan));-webkit-background-clip:text;-webkit-text-fill-color:transparent}.hermes-hero p{font-family:var(--font-mono);font-size:12.5px;line-height:1.72;color:rgba(190,204,223,.84);max-width:820px}.hermes-hero-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:24px}.hermes-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.hermes-card{position:relative;overflow:hidden;border:1px solid rgba(255,255,255,.07);border-radius:22px;background:linear-gradient(145deg,rgba(9,19,31,.9),rgba(3,8,15,.97));padding:20px;min-height:170px;box-shadow:0 8px 30px rgba(0,0,0,.28);transition:var(--transition)}.hermes-card:hover{transform:translateY(-5px);border-color:rgba(5,232,154,.22);box-shadow:0 18px 55px rgba(0,0,0,.4),0 0 34px rgba(5,232,154,.08)}.hermes-card span{font-family:var(--font-mono);font-size:9.4px;color:var(--green);font-weight:850;text-transform:uppercase;letter-spacing:.11em}.hermes-card b{display:block;font-family:var(--font-display);font-size:22px;letter-spacing:-.055em;line-height:1.04;margin-top:10px}.hermes-card p{font-family:var(--font-mono);font-size:10.8px;color:var(--muted);line-height:1.55;margin-top:10px}.hermes-state{display:grid;grid-template-columns:1fr 1fr;gap:14px}.hermes-status-list,.hermes-ladder{display:grid;gap:8px}.hermes-status-row,.hermes-step{display:grid;grid-template-columns:1fr auto;gap:12px;align-items:center;border:1px solid rgba(255,255,255,.06);border-radius:13px;background:rgba(2,5,9,.52);padding:11px 13px}.hermes-status-row b,.hermes-step b{font-size:13px;letter-spacing:-.03em}.hermes-status-row span,.hermes-step em{font-family:var(--font-mono);font-size:10px;font-weight:850;border-radius:999px;padding:5px 10px;border:1px solid rgba(255,255,255,.08);white-space:nowrap;font-style:normal}.hermes-status-row .ok,.hermes-step.active em{color:var(--green);border-color:rgba(5,232,154,.22);background:rgba(5,232,154,.07)}.hermes-status-row .warn,.hermes-step.locked em{color:var(--yellow);border-color:rgba(245,200,66,.22);background:rgba(245,200,66,.07)}.hermes-step{grid-template-columns:54px 1fr auto}.hermes-step span{color:var(--cyan);font-family:var(--font-mono);font-size:10px;font-weight:900}
@media(max-width:1080px){.web-hero-grid,.web-split,.hermes-state{grid-template-columns:1fr}.web-feature-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.hermes-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.web-title{font-size:56px}.hermes-hero h1{font-size:52px}}@media(max-width:640px){.web-hero,.hermes-hero{padding:25px;border-radius:24px}.web-title{font-size:42px}.hermes-hero h1{font-size:40px}.web-kpi-panel,.web-feature-grid,.hermes-grid{grid-template-columns:1fr}.web-mini-row,.hermes-step{grid-template-columns:1fr;gap:5px}.web-section-head{display:block}.web-kpi{min-height:auto}.nav{grid-template-columns:repeat(3,minmax(0,1fr))!important}}

/* ===== V18.4 PUBLIC WEBSITE POLISH ===== */
.topbar{border-bottom:1px solid rgba(255,255,255,.07)!important}
.nav{justify-content:flex-end;gap:6px!important}
.nav a{padding:7px 15px!important;font-size:12px!important}
.logo-text p{letter-spacing:.08em!important}
.shell{padding-top:28px!important}
.web-home{gap:24px!important}
.web-hero{padding:54px!important;border-radius:34px!important}
.web-hero-grid{grid-template-columns:minmax(0,1.08fr) minmax(330px,.72fr)!important;align-items:center!important}
.web-title{font-size:74px!important;line-height:.86!important;max-width:940px!important}
.web-copy{font-size:14px!important;max-width:720px!important;color:rgba(210,222,238,.88)!important}
.web-kpi-panel{gap:12px!important}
.web-kpi{min-height:118px!important;background:rgba(2,5,9,.38)!important}
.web-kpi b{font-size:31px!important}
.web-section-head{margin-top:34px!important}
.web-feature-grid{grid-template-columns:repeat(3,minmax(0,1fr))!important}
.web-feature{min-height:188px!important}
.web-feature:nth-child(4){grid-column:span 3;min-height:140px!important;display:grid;grid-template-columns:220px 1fr;align-items:center;column-gap:22px}
.web-feature:nth-child(4) p{margin-top:0!important;font-size:11.3px!important}
.web-split{grid-template-columns:minmax(0,1fr) minmax(0,1fr)!important}
.public-proof-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}
.public-proof{border:1px solid rgba(255,255,255,.07);border-radius:22px;background:linear-gradient(145deg,rgba(9,19,31,.88),rgba(3,8,15,.98));padding:20px;min-height:150px;box-shadow:0 8px 30px rgba(0,0,0,.26)}
.public-proof span{display:block;color:var(--cyan);font-family:var(--font-mono);font-size:9.5px;font-weight:850;text-transform:uppercase;letter-spacing:.11em}
.public-proof b{display:block;margin-top:10px;font-family:var(--font-display);font-size:22px;line-height:1.04;letter-spacing:-.055em}
.public-proof p{margin-top:10px;color:var(--muted);font-family:var(--font-mono);font-size:10.8px;line-height:1.55}
.hermes-hero{padding:50px!important;border-radius:34px!important}
.hermes-hero h1{font-size:66px!important;max-width:980px!important}
.hermes-grid{grid-template-columns:repeat(4,minmax(0,1fr))!important}
.hermes-card{min-height:180px!important}
.hermes-agent-strip{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin-top:22px}
.hermes-agent-strip .web-mini-row{grid-template-columns:1fr!important;gap:6px;min-height:94px}
.hermes-agent-strip .web-mini-row b{font-size:14px;white-space:normal}
.hermes-state{grid-template-columns:1fr 1fr!important}
.deep-link-strip{display:flex;gap:8px;flex-wrap:wrap;margin-top:10px}
.deep-link-strip a{font-family:var(--font-mono);font-size:10px;color:var(--muted);border:1px solid rgba(255,255,255,.06);border-radius:999px;padding:6px 10px;background:rgba(255,255,255,.025)}
.deep-link-strip a:hover{color:var(--text);border-color:rgba(0,200,240,.22)}
@media(max-width:1080px){.web-hero-grid,.web-split,.hermes-state{grid-template-columns:1fr!important}.web-feature-grid,.public-proof-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important}.web-feature:nth-child(4){grid-column:auto;display:block;min-height:188px!important}.hermes-grid,.hermes-agent-strip{grid-template-columns:repeat(2,minmax(0,1fr))!important}.web-title{font-size:58px!important}.hermes-hero h1{font-size:54px!important}.nav{justify-content:flex-start}}
@media(max-width:640px){.web-hero,.hermes-hero{padding:28px!important}.web-title{font-size:43px!important}.hermes-hero h1{font-size:40px!important}.web-feature-grid,.public-proof-grid,.hermes-grid,.hermes-agent-strip{grid-template-columns:1fr!important}.nav{display:flex!important;overflow-x:auto!important}.web-feature:nth-child(4){min-height:auto!important}}


"""
CSS += """
/* ===== V19 WEBSITE + TERMINAL + BANKROLL ===== */
:root{--v19-border:rgba(255,255,255,.075);--v19-glass:linear-gradient(145deg,rgba(9,19,31,.92),rgba(3,8,15,.98))}
.logo-text p{letter-spacing:.095em!important;color:rgba(0,200,240,.85)!important}.nav{align-items:center;justify-content:flex-end;gap:7px!important}.nav a,.nav-menu-btn{white-space:nowrap;padding:7px 14px!important;border-radius:999px;border:1px solid transparent;color:var(--muted);font-size:11.5px!important;font-family:var(--font-display);font-weight:650;background:transparent;cursor:pointer;transition:var(--transition)}.nav a:hover,.nav-menu:hover .nav-menu-btn{color:var(--text);background:rgba(255,255,255,.045);border-color:rgba(255,255,255,.075)}.nav a.active-nav{color:#fff;background:linear-gradient(135deg,rgba(61,130,245,.22),rgba(139,92,246,.18));border-color:rgba(61,130,245,.28)}.nav-menu{position:relative;display:inline-flex}.nav-menu-btn{display:inline-flex;align-items:center;gap:7px}.nav-menu-panel{position:absolute;right:0;top:calc(100% + 8px);width:255px;display:none;grid-template-columns:1fr;gap:5px;padding:10px;border:1px solid rgba(255,255,255,.1);border-radius:18px;background:rgba(3,8,15,.97);box-shadow:0 22px 70px rgba(0,0,0,.55);backdrop-filter:blur(24px);z-index:200}.nav-menu:hover .nav-menu-panel,.nav-menu:focus-within .nav-menu-panel{display:grid}.nav-menu-panel a{display:flex!important;justify-content:space-between!important;padding:9px 11px!important;border-radius:12px!important;font-family:var(--font-mono)!important;font-size:10.5px!important}.nav-menu-panel a::after{content:"→";opacity:.45}
.v19-home{display:grid;gap:18px;margin-top:14px}.v19-hero{position:relative;overflow:hidden;border:1px solid rgba(0,200,240,.16);border-radius:34px;padding:54px;background:radial-gradient(circle at 82% 12%,rgba(0,200,240,.14),transparent 34%),radial-gradient(circle at 8% 92%,rgba(5,232,154,.08),transparent 42%),linear-gradient(145deg,rgba(9,19,31,.98),rgba(2,5,9,1));box-shadow:0 28px 90px rgba(0,0,0,.48)}.v19-hero-grid{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(320px,.72fr);gap:30px;align-items:center}.v19-eyebrow{display:inline-flex;align-items:center;gap:8px;padding:7px 13px;border-radius:999px;border:1px solid rgba(0,200,240,.18);background:rgba(0,200,240,.06);color:#9ce8f8;font-family:var(--font-mono);font-size:10px;text-transform:uppercase;letter-spacing:.12em;font-weight:900}.v19-title{font-family:var(--font-display);font-size:76px;line-height:.86;letter-spacing:-.098em;max-width:940px;margin:20px 0 16px;background:linear-gradient(135deg,var(--text) 18%,var(--cyan) 64%,var(--purple));-webkit-background-clip:text;-webkit-text-fill-color:transparent}.v19-copy{font-family:var(--font-mono);font-size:13px;line-height:1.76;color:rgba(190,204,223,.86);max-width:820px}.v19-actions{display:flex;gap:10px;flex-wrap:wrap;margin-top:26px}.v19-side{display:grid;grid-template-columns:1fr 1fr;gap:10px}.v19-kpi,.v19-card,.v19-panel,.bank-card,.risk-card{border:1px solid var(--v19-border);background:var(--v19-glass);border-radius:22px;padding:18px;box-shadow:0 10px 36px rgba(0,0,0,.32);transition:var(--transition)}.v19-kpi{min-height:126px}.v19-kpi:hover,.v19-card:hover,.bank-card:hover,.risk-card:hover{transform:translateY(-4px);border-color:rgba(0,200,240,.2)}.v19-kpi span,.v19-card span,.bank-card span,.risk-card span{display:block;color:var(--muted);font-family:var(--font-mono);font-size:9.4px;text-transform:uppercase;letter-spacing:.105em;font-weight:900}.v19-kpi b{display:block;margin-top:8px;font-family:var(--font-display);font-size:34px;line-height:.95;letter-spacing:-.08em}.v19-kpi p,.v19-card p,.bank-card p,.risk-card p{margin-top:9px;color:var(--muted);font-family:var(--font-mono);font-size:10.5px;line-height:1.48}.v19-section-head{display:flex;justify-content:space-between;align-items:flex-end;gap:14px;margin:28px 0 13px}.v19-section-head h2{font-family:var(--font-display);font-size:32px;line-height:.95;letter-spacing:-.075em;margin:0}.v19-section-head p{margin:7px 0 0;color:var(--muted);font-family:var(--font-mono);font-size:11.3px;line-height:1.5;max-width:780px}.v19-grid-4{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.v19-grid-3{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px}.v19-grid-2{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.v19-card{min-height:168px}.v19-card b,.bank-card b,.risk-card b{display:block;margin-top:10px;font-family:var(--font-display);font-size:22px;line-height:1.02;letter-spacing:-.06em}.v19-card span{color:var(--cyan)}.v19-workflow{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.workflow-step{position:relative;border:1px solid rgba(255,255,255,.07);border-radius:18px;padding:16px;background:rgba(2,5,9,.55)}.workflow-step em{font-style:normal;color:var(--cyan);font-family:var(--font-mono);font-size:10px;font-weight:900}.workflow-step b{display:block;margin-top:8px;font-size:17px;letter-spacing:-.045em}.workflow-step p{margin-top:7px;color:var(--muted);font-family:var(--font-mono);font-size:10px;line-height:1.45}.terminal-layout{display:grid;grid-template-columns:minmax(0,1.2fr) minmax(330px,.8fr);gap:14px;align-items:start}.terminal-stack{display:grid;gap:14px}.mission-row{display:grid;grid-template-columns:92px 1fr auto;gap:10px;align-items:center;border:1px solid rgba(255,255,255,.06);border-radius:14px;background:rgba(2,5,9,.52);padding:11px 13px}.mission-row span{font-family:var(--font-mono);font-size:9.5px;color:var(--muted);font-weight:900;text-transform:uppercase}.mission-row b{font-size:13px;letter-spacing:-.025em;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}.mission-row em{font-style:normal;color:var(--green);font-family:var(--font-mono);font-size:10px;font-weight:900}.bank-hero{display:grid;grid-template-columns:minmax(0,1fr) minmax(300px,.55fr);gap:14px;margin:18px 0}.bank-health{border:1px solid rgba(5,232,154,.17);border-radius:28px;padding:30px;background:radial-gradient(circle at 82% 18%,rgba(5,232,154,.11),transparent 36%),var(--v19-glass)}.bank-health h1{font-family:var(--font-display);font-size:54px;line-height:.9;letter-spacing:-.085em;margin:12px 0}.bank-number{font-family:var(--font-display);font-size:54px;font-weight:900;letter-spacing:-.09em;line-height:.95}.bank-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.bank-card{min-height:112px}.bank-card b{font-size:26px}.risk-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.risk-card.ok{border-color:rgba(5,232,154,.16);background:linear-gradient(145deg,rgba(5,232,154,.055),rgba(3,8,15,.98))}.risk-card.warn{border-color:rgba(245,200,66,.18);background:linear-gradient(145deg,rgba(245,200,66,.06),rgba(3,8,15,.98))}.risk-card.lock{border-color:rgba(248,75,110,.16);background:linear-gradient(145deg,rgba(248,75,110,.055),rgba(3,8,15,.98))}.action-board{display:grid;gap:12px}.action-clean-card{border:1px solid rgba(5,232,154,.18);border-radius:24px;background:radial-gradient(circle at 88% 0%,rgba(5,232,154,.09),transparent 34%),var(--v19-glass);padding:22px;box-shadow:0 18px 55px rgba(0,0,0,.4)}.action-clean-head{display:flex;justify-content:space-between;gap:12px;align-items:flex-start}.action-clean-title{font-family:var(--font-display);font-size:25px;font-weight:900;letter-spacing:-.065em}.action-clean-bet{font-family:var(--font-display);font-size:36px;font-weight:950;letter-spacing:-.078em;color:var(--green);line-height:.95;margin:14px 0 8px}.action-clean-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:8px;margin-top:14px}.action-clean-grid .mini{min-height:64px}.deep-menu-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.deep-menu-card{display:block;border:1px solid rgba(255,255,255,.07);border-radius:20px;background:var(--v19-glass);padding:18px;min-height:132px;transition:var(--transition)}.deep-menu-card:hover{transform:translateY(-4px);border-color:rgba(61,130,245,.22)}.deep-menu-card span{display:block;color:var(--cyan);font-family:var(--font-mono);font-size:9.5px;text-transform:uppercase;letter-spacing:.11em;font-weight:900}.deep-menu-card b{display:block;margin-top:9px;font-size:20px;letter-spacing:-.055em}.deep-menu-card p{margin-top:8px;color:var(--muted);font-family:var(--font-mono);font-size:10.4px;line-height:1.45}.missing-smart{border:1px dashed rgba(245,200,66,.28);background:rgba(245,200,66,.045);border-radius:18px;padding:18px;color:var(--yellow);font-family:var(--font-mono);font-size:11px}.footer::after{content:" · V21.8 advisory cycle · manual approval · no auto-betting";color:rgba(0,200,240,.65)}
.bankroll-chart-panel{border:1px solid rgba(0,200,240,.14);border-radius:26px;background:radial-gradient(circle at 88% 0%,rgba(0,200,240,.09),transparent 36%),var(--v19-glass);padding:22px;box-shadow:0 18px 60px rgba(0,0,0,.42);margin:16px 0}.bankroll-chart-head{display:flex;justify-content:space-between;align-items:flex-start;gap:14px;margin-bottom:14px}.bankroll-chart-head h2{font-family:var(--font-display);font-size:28px;line-height:1;letter-spacing:-.07em;margin:0}.bankroll-chart-head p{margin:6px 0 0;color:var(--muted);font-family:var(--font-mono);font-size:11px;line-height:1.45;max-width:680px}.bankroll-chart-wrap{height:310px;position:relative}.bankroll-summary-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:12px 0 0}.bankroll-summary-card{border:1px solid rgba(255,255,255,.07);border-radius:18px;background:rgba(2,5,9,.52);padding:15px}.bankroll-summary-card span{display:block;color:var(--muted);font-family:var(--font-mono);font-size:9.5px;text-transform:uppercase;letter-spacing:.1em;font-weight:900}.bankroll-summary-card b{display:block;margin-top:7px;font-family:var(--font-display);font-size:22px;letter-spacing:-.06em}.bankroll-summary-card p{margin-top:7px;color:var(--muted);font-family:var(--font-mono);font-size:10.5px;line-height:1.45}.nav a[href="/menu"]{border-color:rgba(0,200,240,.14)!important;background:rgba(0,200,240,.045)!important}.nav a[href="/menu"].active-nav{background:linear-gradient(135deg,rgba(0,200,240,.20),rgba(139,92,246,.14))!important}.deep-menu-grid{margin-top:14px}.deep-menu-card.primary-route{border-color:rgba(0,200,240,.18);background:radial-gradient(circle at 90% 0%,rgba(0,200,240,.08),transparent 38%),var(--v19-glass)}

/* ===== V19.2 PRECISION SYSTEM LAYER ===== */
.nav{align-items:center}.nav a{position:relative}.nav a.active-nav::after{content:"";position:absolute;left:14px;right:14px;bottom:2px;height:2px;border-radius:999px;background:linear-gradient(90deg,var(--cyan),var(--purple));opacity:.9}
.v192-command-strip{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin:16px 0}.v192-chip-card{border:1px solid rgba(255,255,255,.075);border-radius:18px;background:rgba(2,5,9,.55);padding:15px;min-height:96px;box-shadow:0 8px 28px rgba(0,0,0,.22)}.v192-chip-card span{display:block;color:var(--muted);font-family:var(--font-mono);font-size:9.2px;text-transform:uppercase;letter-spacing:.105em;font-weight:900}.v192-chip-card b{display:block;margin-top:7px;font-family:var(--font-display);font-size:24px;letter-spacing:-.07em;line-height:1}.v192-chip-card p{margin-top:7px;color:var(--muted);font-family:var(--font-mono);font-size:10px;line-height:1.35}
.v192-brief{border:1px solid rgba(0,200,240,.13);border-radius:24px;padding:20px;background:radial-gradient(circle at 88% 0%,rgba(0,200,240,.08),transparent 36%),var(--v19-glass);box-shadow:0 16px 55px rgba(0,0,0,.36)}.v192-brief h3{font-family:var(--font-display);font-size:25px;line-height:1;letter-spacing:-.065em;margin:0 0 12px}.v192-brief-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:9px}.v192-brief-card{border:1px solid rgba(255,255,255,.065);border-radius:16px;background:rgba(2,5,9,.55);padding:14px}.v192-brief-card span{display:block;color:var(--cyan);font-family:var(--font-mono);font-size:9.3px;text-transform:uppercase;letter-spacing:.1em;font-weight:900}.v192-brief-card b{display:block;margin-top:8px;font-size:18px;letter-spacing:-.05em}.v192-brief-card p{margin-top:6px;color:var(--muted);font-family:var(--font-mono);font-size:10px;line-height:1.4}
.action-clean-card{display:grid;gap:12px}.action-clean-bet{word-break:break-word}.action-reason-grid{display:grid;grid-template-columns:1.1fr .9fr .75fr;gap:9px;margin-top:4px}.reason-box{border:1px solid rgba(255,255,255,.065);border-radius:14px;background:rgba(2,5,9,.54);padding:13px;min-height:90px}.reason-box span{display:block;color:var(--muted);font-family:var(--font-mono);font-size:9.2px;text-transform:uppercase;letter-spacing:.1em;font-weight:900}.reason-box b{display:block;margin-top:7px;font-family:var(--font-display);font-size:15px;letter-spacing:-.04em;line-height:1.15}.reason-box p{margin-top:6px;color:var(--muted);font-family:var(--font-mono);font-size:10px;line-height:1.42}.approval-rail{display:flex;gap:8px;flex-wrap:wrap;margin-top:2px}.approval-pill{display:inline-flex;align-items:center;gap:6px;border:1px solid rgba(255,255,255,.075);border-radius:999px;background:rgba(255,255,255,.035);padding:7px 11px;font-family:var(--font-mono);font-size:9.7px;font-weight:900;text-transform:uppercase;color:var(--muted)}.approval-pill.ready{color:var(--green);border-color:rgba(5,232,154,.22);background:rgba(5,232,154,.07)}.approval-pill.locked{color:var(--red);border-color:rgba(248,75,110,.18);background:rgba(248,75,110,.055)}.approval-pill.warn{color:var(--yellow);border-color:rgba(245,200,66,.18);background:rgba(245,200,66,.055)}
.bank-limit-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:14px 0}.bank-limit-card{border:1px solid rgba(255,255,255,.07);border-radius:18px;background:rgba(2,5,9,.54);padding:15px;min-height:108px}.bank-limit-card span{display:block;color:var(--muted);font-family:var(--font-mono);font-size:9.4px;text-transform:uppercase;letter-spacing:.105em;font-weight:900}.bank-limit-card b{display:block;margin-top:8px;font-size:24px;letter-spacing:-.065em}.bank-limit-card p{margin-top:7px;color:var(--muted);font-family:var(--font-mono);font-size:10.3px;line-height:1.42}.bank-limit-card.ok{border-color:rgba(5,232,154,.16)}.bank-limit-card.warn{border-color:rgba(245,200,66,.2)}.bank-limit-card.lock{border-color:rgba(248,75,110,.18)}
.hermes-approval-board{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:14px 0}.approval-card{border:1px solid rgba(255,255,255,.075);border-radius:18px;background:var(--v19-glass);padding:16px;min-height:132px}.approval-card span{display:block;color:var(--cyan);font-family:var(--font-mono);font-size:9.5px;text-transform:uppercase;letter-spacing:.1em;font-weight:900}.approval-card b{display:block;margin-top:8px;font-size:21px;letter-spacing:-.055em}.approval-card p{margin-top:8px;color:var(--muted);font-family:var(--font-mono);font-size:10.4px;line-height:1.45}.injury-status{border-color:rgba(245,200,66,.2)!important;background:linear-gradient(145deg,rgba(245,200,66,.055),rgba(3,8,15,.98))!important}
@media(max-width:1100px){.v192-command-strip,.bank-limit-grid,.hermes-approval-board{grid-template-columns:repeat(2,minmax(0,1fr))}.action-reason-grid{grid-template-columns:1fr}.v192-brief-grid{grid-template-columns:1fr}.terminal-layout{grid-template-columns:1fr!important}}
@media(max-width:680px){.v192-command-strip,.bank-limit-grid,.hermes-approval-board{grid-template-columns:1fr}.command-title{font-size:34px!important}.action-clean-card{padding:17px}.action-clean-grid{grid-template-columns:repeat(2,minmax(0,1fr))!important}.bankroll-chart-wrap{height:240px}.v19-title{font-size:38px!important}.shell{padding-left:13px!important;padding-right:13px!important}}

@media(max-width:1080px){.v19-hero-grid,.terminal-layout,.bank-hero{grid-template-columns:1fr}.v19-grid-4,.deep-menu-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.v19-title{font-size:58px}.v19-workflow,.bank-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.risk-grid{grid-template-columns:1fr}.action-clean-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:680px){.bankroll-summary-grid{grid-template-columns:1fr}.bankroll-chart-wrap{height:260px}.brand-row{align-items:flex-start}.status-pill{display:none}.nav{justify-content:flex-start!important}.nav a{font-size:10.5px!important;padding:7px 10px!important}.nav-menu-panel{left:0;right:auto}.v19-hero{padding:26px;border-radius:25px}.v19-title{font-size:42px}.v19-side,.v19-grid-4,.v19-grid-3,.v19-grid-2,.v19-workflow,.bank-grid,.action-clean-grid,.deep-menu-grid{grid-template-columns:1fr}.v19-section-head{display:block}.mission-row{grid-template-columns:1fr;gap:5px}.bank-health h1,.bank-number{font-size:38px}.action-clean-bet{font-size:28px}}
"""




def page(title, body):
    public_links = [("/", "Home"), ("/dashboard", "Dashboard"), ("/bankroll", "Bankroll"), ("/hermes", "Hermes"), ("/menu", "Menu")]
    menu_section_paths = {"/actions", "/environment", "/research", "/memory", "/validation", "/diagnostics", "/bets", "/telegram", "/history", "/rankings", "/analysis", "/intelligence"}
    current_path = request.path.rstrip("/") or "/"
    active_path = {"/stakes": "/actions", "/stake": "/actions"}.get(current_path, current_path)
    nav_html = "".join(
        f'<a href="{href}" class="{"active-nav" if ((href.rstrip("/") or "/") == active_path or (href == "/menu" and active_path in menu_section_paths)) else ""}">{label}</a>'
        for href, label in public_links
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><title>Edge Lab — {title}</title><link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin><style>{CSS}</style><script src="https://cdn.jsdelivr.net/npm/chart.js"></script></head>
<body><div class="ambient-orb a"></div><div class="ambient-orb b"></div><div class="ambient-orb c"></div>
<div class="topbar"><div class="top-inner"><div class="brand-row"><div class="logo"><div class="logo-mark"><svg viewBox="0 0 40 40" fill="none"><polygon points="20,2 36,11 36,29 20,38 4,29 4,11" fill="none" stroke="url(#lg1)" stroke-width="1.4"/><polygon points="20,9 30,15 30,25 20,31 10,25 10,15" fill="url(#lg2)" opacity=".12"/><defs><linearGradient id="lg1" x1="4" y1="2" x2="36" y2="38" gradientUnits="userSpaceOnUse"><stop stop-color="#00c8f0"/><stop offset="1" stop-color="#8b5cf6"/></linearGradient><linearGradient id="lg2" x1="10" y1="9" x2="30" y2="31" gradientUnits="userSpaceOnUse"><stop stop-color="#00c8f0"/><stop offset="1" stop-color="#8b5cf6"/></linearGradient></defs></svg><span>W</span></div><div class="logo-text"><h1>WNBA <em>Edge Lab</em></h1><p>V21.8 · advisory cycle · Hermes manual approval</p></div></div><div class="status-pill"><span class="dot"></span>MANUAL APPROVAL</div></div><nav class="nav">{nav_html}</nav></div></div>
<main class="shell">{body}<div class="footer">V21.8 advisory site · operator terminal · {title}</div></main>
<script>
function filterCards(mode) {{ document.querySelectorAll('.filter-btn').forEach(function(b) {{ b.classList.remove('active'); }}); var active = document.querySelector('[data-filter="' + mode + '"]'); if (active) active.classList.add('active'); document.querySelectorAll('[data-signal-card]').forEach(function(card) {{ var sig = (card.getAttribute('data-signal-card') || '').toUpperCase(); var units = parseFloat(card.getAttribute('data-units') || '0'); var show = true; if (mode === 'signals') show = sig !== 'PASS'; if (mode === 'recommended') show = units > 0; card.classList.toggle('hidden-card', !show); }}); }}
if (typeof Chart !== 'undefined') {{ Chart.defaults.color = '#5a7599'; Chart.defaults.font.family = "'JetBrains Mono', monospace"; Chart.defaults.font.size = 11; }}
</script></body></html>"""
def read_csv(path):
    try:
        if not path.exists():
            return pd.DataFrame()
        if path.stat().st_size == 0:
            return pd.DataFrame()
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    except Exception:
        return pd.DataFrame()

def normalize(df):
    if df.empty: return df
    df = df.copy()
    df.columns = [c.strip().lower().replace(" ","_").replace("/","_") for c in df.columns]
    aliases = {"p_l":"profit_loss","profitloss":"profit_loss","pl":"profit_loss","betid":"bet_id","finalsignal":"final_signal","suggestedunits":"suggested_units","suggestedstake":"suggested_stake","assumedodds":"assumed_odds","actualunits":"actual_units"}
    df = df.rename(columns={c:aliases.get(c,c) for c in df.columns})
    if "result" not in df.columns and "status" in df.columns: df["result"] = df["status"]
    if "status" not in df.columns and "result" in df.columns: df["status"] = df["result"].apply(lambda x: "OPEN" if str(x).upper()=="PENDING" else "SETTLED")
    if "profit_loss" not in df.columns: df["profit_loss"] = 0.0
    if "stake" not in df.columns: df["stake"] = 0.0
    if "odds" not in df.columns: df["odds"] = 0.0
    return df

def load_bets():
    if BET_CSV.exists(): return normalize(pd.read_csv(BET_CSV))
    if BET_DB.exists():
        conn = sqlite3.connect(BET_DB)
        try: return normalize(pd.read_sql_query("SELECT * FROM bets", conn))
        finally: conn.close()
    return pd.DataFrame()

def safe_float(x, default=0.0):
    try:
        if pd.isna(x) or x == "": return default
        return float(x)
    except Exception: return default

def fmt(x, dec=1):
    try: return f"{float(x):.{dec}f}"
    except Exception: return str(x)

def metric_card(label, value, hint="", cls=""):
    return f'<div class="metric"><div class="label">{label}</div><div class="value {cls}">{value}</div><div class="hint">{hint}</div></div>'

def signal_badge(signal):
    s = str(signal).upper()
    cls = "gray"
    if "WATCHLIST" in s: cls = "orange"
    elif "LEAN" in s: cls = "yellow"
    elif ("OVER" in s or "WIN" in s) and "PASS" not in s: cls = "green"
    elif ("UNDER" in s or "LOSS" in s) and "PASS" not in s: cls = "red"
    elif "PENDING" in s or "OPEN" in s: cls = "yellow"
    return f'<span class="badge {cls}">{signal}</span>'

def table(df, cols=None, max_rows=80):
    if df.empty: return '<div class="empty">No data found.</div>'
    show = df.copy()
    if cols:
        cols = [c for c in cols if c in show.columns]
        if cols: show = show[cols]
    return '<div class="table-wrap">' + show.head(max_rows).to_html(index=False, escape=False) + '</div>'

def calc_pl(row):
    result = str(row.get("result","")).upper()
    try:
        existing = float(row.get("profit_loss"))
        return existing
    except Exception: pass
    stake = safe_float(row.get("stake",0)); odds = safe_float(row.get("odds",0))
    if result == "WIN": return stake * (odds - 1)
    if result == "LOSS": return -stake
    return 0.0

def projection_cards(df):
    if df.empty: return '<div class="panel empty">No projections found. Run the model first.</div>'
    data = normalize(df)
    cards = []
    for i, (_, r) in enumerate(data.iterrows()):
        game = r.get("game","")
        signal = r.get("final_signal", r.get("signal","PASS"))
        line = r.get("line",""); proj = r.get("projection",""); edge = safe_float(r.get("edge",0)); conf=safe_float(r.get("confidence",0))
        book = r.get("book", r.get("bookmaker",""))
        away_score = r.get("away_projected_points",""); home_score = r.get("home_projected_points","")
        pace = r.get("expected_pace_per40", r.get("expected_pace","")); raw = r.get("raw_total","")
        consensus = r.get("consensus", r.get("consensus_line","")); pp_away = r.get("away_pp100",""); pp_home = r.get("home_pp100","")
        edge_cls = "positive" if edge > 0 else "negative" if edge < 0 else "neutral"
        w = max(4,min(100,int(conf if conf else abs(edge)*10)))
        cards.append(f"""
        <div class="game-card" style="animation-delay:{min(i*.045,.35)}s">
          <div class="game-top"><div><div class="game-title">{game}</div><div class="game-sub">Line {line} - {book}</div></div>{signal_badge(signal)}</div>
          <div class="scoreline"><div class="team-score"><div class="team">Away</div><div class="score">{fmt(away_score,1)}</div></div><div class="vs">VS</div><div class="team-score"><div class="team">Home</div><div class="score">{fmt(home_score,1)}</div></div></div>
          <div class="edge-row"><div class="mini"><span>Projection</span><b>{fmt(proj,1)}</b></div><div class="mini"><span>Edge</span><b class="{edge_cls}">{edge:+.1f}</b></div><div class="mini"><span>Confidence</span><b>{fmt(conf,0)}</b></div></div>
          <div class="progress"><div style="--w:{w}%"></div></div>
          <div class="details"><div class="detail">Pace Per40<b>{fmt(pace,1)}</b></div><div class="detail">Raw Total<b>{fmt(raw,1)}</b></div><div class="detail">Consensus<b>{consensus}</b></div><div class="detail">PP100<b>{fmt(pp_away,1)} / {fmt(pp_home,1)}</b></div></div>
        </div>""")
    return '<div class="cards">' + "".join(cards) + '</div>'

def todays_action_panel(df):
    if df.empty:
        return ""

    data = normalize(df)

    if "suggested_units" in data.columns:
        data = data[data["suggested_units"].apply(safe_float) > 0].copy()

    if data.empty:
        return ""

    if "suggested_units" in data.columns:
        data = data.sort_values(by="suggested_units", key=lambda s: s.apply(safe_float), ascending=False)

    rows = []
    for i, (_, r) in enumerate(data.iterrows(), start=1):
        game = r.get("game", "")
        if not game or str(game).lower() == "nan":
            away = r.get("away", "")
            home = r.get("home", "")
            game = f"{away} @ {home}" if away or home else ""

        selection = str(r.get("selection", "")).strip()
        line = r.get("line", r.get("market_line", ""))
        units = safe_float(r.get("suggested_units", 0))
        odds = r.get("assumed_odds", r.get("odds", ""))
        edge = safe_float(r.get("edge", 0))
        conf = safe_float(r.get("confidence", 0))
        signal = r.get("final_signal", r.get("final_signal_normalized", r.get("signal", "")))
        stake = safe_float(r.get("suggested_stake", 0))

        rows.append(f"""
        <div class="action-card-clean" style="animation-delay:{min((i-1)*.05,.25)}s">
          <div class="action-head-clean">
            <div>
              <div class="action-rank-clean">Action #{i}</div>
              <div class="action-game-clean">{game}</div>
            </div>
            {signal_badge(signal)}
          </div>
          <div class="action-bet-clean">{selection} {line}</div>
          <div class="action-meta-clean"><strong>{units:.2f}u</strong> @ {odds} · Stake {stake:.2f}</div>
          <div class="action-kpis-clean">
            <div class="mini"><span>Units</span><b>{units:.3f}u</b></div>
            <div class="mini"><span>Edge</span><b class="{'positive' if edge>0 else 'negative' if edge<0 else 'neutral'}">{edge:+.1f}</b></div>
            <div class="mini"><span>Confidence</span><b>{fmt(conf,0)}/100</b></div>
          </div>
        </div>
        """)

    return f"""
    <div class="action-panel-clean">
      <div class="section-head">
        <div>
          <h2>Today's Action</h2>
          <p>Exact bets ranked by suggested units. Clean operator blotter, not automatic execution.</p>
        </div>
        <div class="toolbar"><span class="chip">Exact Bet</span><span class="chip">Research Only</span></div>
      </div>
      <div class="action-grid-clean">{''.join(rows)}</div>
    </div>
    """


def staking_cards(df):
    if df.empty:
        return '<div class="panel empty">Run staking_tracker_bridge_v2_5.py first.</div>'

    data = normalize(df)

    if "suggested_units" in data.columns:
        nz = data[data["suggested_units"].apply(safe_float) > 0].copy()
        if not nz.empty:
            data = nz

    cards = []

    for _, r in data.iterrows():
        game = r.get("game", "")
        if not game or str(game).lower() == "nan":
            away = r.get("away", "")
            home = r.get("home", "")
            game = f"{away} @ {home}" if away or home else ""

        signal = r.get("final_signal", r.get("final_signal_normalized", r.get("signal", "PASS")))
        line = r.get("line", r.get("market_line", ""))
        selection = r.get("selection", "")
        units = safe_float(r.get("suggested_units", 0))
        stake = safe_float(r.get("suggested_stake", 0))
        edge = safe_float(r.get("edge", 0))
        conf = safe_float(r.get("confidence", 0))
        odds = r.get("assumed_odds", r.get("odds", ""))
        reason = r.get("stake_reason", "")

        cards.append(f"""
        <div class="game-card">
          <div class="game-top">
            <div>
              <div class="game-title">{game}</div>
              <div class="game-sub">Exact Bet</div>
              <div style="margin-top:8px;font-size:26px;font-weight:900;color:var(--green);font-family:var(--font-display);letter-spacing:-.05em;line-height:1;">
                {selection} {line}
              </div>
              <div style="margin-top:7px;color:var(--muted);font-family:var(--font-mono);font-size:12px;">
                {units:.3f}u @ {odds}
              </div>
            </div>
            {signal_badge(signal)}
          </div>

          <div class="edge-row">
            <div class="mini"><span>Units</span><b>{units:.3f}u</b></div>
            <div class="mini"><span>Stake</span><b>{stake:.2f}</b></div>
            <div class="mini"><span>Edge</span><b class="{'positive' if edge>0 else 'negative' if edge<0 else 'neutral'}">{edge:+.1f}</b></div>
          </div>

          <div class="details">
            <div class="detail">Confidence<b>{fmt(conf,0)}/100</b></div>
            <div class="detail">Odds<b>{odds}</b></div>
            <div class="detail">Reason<b>{reason}</b></div>
          </div>
        </div>
        """)

    return '<div class="cards">' + "".join(cards) + '</div>'


def team_cards(df):
    if df.empty: return '<div class="panel empty">No rankings.csv found.</div>'
    data = normalize(df)
    team_col = "team_abbreviation" if "team_abbreviation" in data.columns else "team" if "team" in data.columns else data.columns[0]
    pace_col = "pace_per40" if "pace_per40" in data.columns else None
    off_col = "off_rating" if "off_rating" in data.columns else None
    def_col = "def_rating" if "def_rating" in data.columns else None
    def width(val, col):
        if not col or col not in data.columns: return 50
        series = pd.to_numeric(data[col], errors="coerce")
        lo, hi = series.min(), series.max()
        v = safe_float(val)
        if pd.isna(lo) or pd.isna(hi) or hi == lo: return 50
        return max(5,min(100,int(8 + 84*(v-lo)/(hi-lo))))
    cards=[]
    for _, r in data.iterrows():
        team = r.get(team_col,"")
        pace = r.get(pace_col,"") if pace_col else ""
        off = r.get(off_col,"") if off_col else ""
        deff = r.get(def_col,"") if def_col else ""
        cards.append(f"""<div class="team-card"><div class="team-name">{team}</div><div class="team-meta">2026 advanced team profile</div><div class="team-bars"><div class="bar-row"><span>Pace</span><div class="bar"><div style="--w:{width(pace,pace_col)}%"></div></div><b>{fmt(pace,1)}</b></div><div class="bar-row"><span>Off Rtg</span><div class="bar"><div style="--w:{width(off,off_col)}%"></div></div><b>{fmt(off,1)}</b></div><div class="bar-row"><span>Def Rtg</span><div class="bar"><div style="--w:{width(deff,def_col)}%"></div></div><b>{fmt(deff,1)}</b></div></div></div>""")
    return '<div class="team-grid">' + "".join(cards) + '</div>'

def bet_cards(df, max_cards=60):
    if df.empty: return '<div class="panel empty">No bets yet.</div>'
    cards=[]
    for _, r in df.head(max_cards).iterrows():
        game=r.get("game",""); player=r.get("player",""); market=r.get("market",""); direction=r.get("direction",""); line=r.get("line",""); odds=r.get("odds",""); stake=r.get("stake",""); result=str(r.get("result","")); pl=safe_float(r.get("profit_loss",0)); signal=r.get("signal",""); date=r.get("date","")
        title=f"{game}" + (f" - {player}" if player and str(player)!="nan" else "")
        cards.append(f"""<div class="bet-card"><div class="bet-head"><div><div class="bet-title">{title}</div><div class="bet-sub">{date} - {market} - {signal}</div></div>{signal_badge(result)}</div><div class="bet-kpis"><div class="mini"><span>Selection</span><b>{direction} {line}</b></div><div class="mini"><span>Odds</span><b>{odds}</b></div><div class="mini"><span>Stake</span><b>{stake}u</b></div><div class="mini"><span>P/L</span><b class="{'positive' if pl>=0 else 'negative'}">{pl:+.2f}u</b></div></div></div>""")
    return '<div class="cards">' + "".join(cards) + '</div>'



def pick_value(payload, *keys, default=""):
    if not isinstance(payload, dict):
        return default
    for k in keys:
        if k in payload and payload[k] not in [None, ""]:
            return payload[k]
    return default


def active_signal_count(df):
    if df.empty:
        return 0
    data = normalize(df)
    sig_col = "final_signal" if "final_signal" in data.columns else "final_signal_normalized" if "final_signal_normalized" in data.columns else "signal" if "signal" in data.columns else None
    if not sig_col:
        return 0
    sig = data[sig_col].fillna("PASS").astype(str).str.upper()
    return int((~sig.eq("PASS")).sum())


def recommended_count_and_units(df):
    if df.empty:
        return 0, 0.0, 0.0
    data = normalize(df)
    if "suggested_units" not in data.columns:
        return 0, 0.0, 0.0
    units = data["suggested_units"].apply(safe_float)
    rec = int((units > 0).sum())
    total_units = float(units.sum())
    total_stake = float(data["suggested_stake"].apply(safe_float).sum()) if "suggested_stake" in data.columns else 0.0
    return rec, total_units, total_stake



def todays_mission_brief(proj_df, stake_df):
    proj = normalize(proj_df)
    stake = normalize(stake_df)

    rec, total_units, total_stake = recommended_count_and_units(stake)
    sigs = active_signal_count(proj)

    avg_edge = 0.0
    top_edge = 0.0
    if not proj.empty and "edge" in proj.columns:
        edge_series = proj["edge"].apply(safe_float)
        avg_edge = float(edge_series.mean()) if len(edge_series) else 0.0
        top_edge = float(edge_series.abs().max()) if len(edge_series) else 0.0

    env = read_json_safe(OUTPUT_DIR / "environment_regime_latest.json")
    integrity = read_json_safe(OUTPUT_DIR / "data_integrity_latest.json")
    regime = pick_value(env, "environment_regime", "EnvironmentRegime", default="LEARNING")
    integrity_score = pick_value(integrity, "integrity_score", "IntegrityScore", "score", default="WAIT")

    top_label = "No active recommendation"
    top_units = "0.00u"
    if not stake.empty and "suggested_units" in stake.columns:
        ranked = stake.copy()
        ranked["_units"] = ranked["suggested_units"].apply(safe_float)
        ranked = ranked.sort_values("_units", ascending=False)
        if not ranked.empty and safe_float(ranked.iloc[0].get("_units", 0)) > 0:
            r = ranked.iloc[0]
            game = r.get("game", "")
            bet = r.get("recommended_bet", r.get("bet", r.get("selection", r.get("final_signal", ""))))
            top_label = f"{game} · {bet}" if game else str(bet)
            top_units = f"{safe_float(r.get('_units', 0)):.2f}u"

    exposure_state = "Clear" if total_units <= 3 else "Review" if total_units <= 6 else "High"
    signal_state = "Active" if rec else "Observe"
    env_state = "Ready" if regime not in ["", "LEARNING"] else "Learning"

    alerts = [
        ("Action", top_label, top_units, "lock" if rec else "warn"),
        ("Exposure", f"{total_units:.2f}u suggested · ${total_stake:.2f} capital", exposure_state, "warn" if exposure_state != "Clear" else ""),
        ("Environment", f"Regime {regime} · integrity {integrity_score}", env_state, ""),
        ("Discipline", "No auto-bets. No formula/staking changes from UI layer.", "LOCK", "lock"),
    ]
    alert_html = "".join([f'<div class="alert-row {cls}"><span>{a}</span><b>{b}</b><em>{c}</em></div>' for a,b,c,cls in alerts])

    return f"""
    <section class="mission-brief">
      <div class="mission-card">
        <div class="mission-kicker"><span class="pulse-ring"></span>Today's Mission Brief</div>
        <h2 class="mission-title">What matters now: signal, exposure, regime, discipline.</h2>
        <div class="mission-copy">Fast operator scan before reviewing tickets. This panel summarizes the slate without changing model outputs, formulas, staking, thresholds, or backend files.</div>
        <div class="mission-grid">
          <div class="mission-tile"><span>Signals</span><b>{sigs}</b></div>
          <div class="mission-tile"><span>Actions</span><b>{rec}</b></div>
          <div class="mission-tile"><span>Exposure</span><b>{total_units:.2f}u</b></div>
          <div class="mission-tile"><span>Top Edge</span><b>{top_edge:.1f}</b></div>
          <div class="mission-tile"><span>Avg Edge</span><b>{avg_edge:+.1f}</b></div>
          <div class="mission-tile"><span>Regime</span><b>{regime}</b></div>
          <div class="mission-tile"><span>Integrity</span><b>{integrity_score}</b></div>
          <div class="mission-tile"><span>Status</span><b>{signal_state}</b></div>
        </div>
      </div>
      <div class="mission-card">
        <div class="mission-kicker"><span class="pulse-ring yellow"></span>Operator Alerts</div>
        <div class="alert-stack">{alert_html}</div>
      </div>
    </section>
    """


def operator_intelligence_panel(proj_df, stake_df):
    proj = normalize(proj_df)
    stake = normalize(stake_df)

    rows = []
    if not stake.empty:
        data = stake.copy()
        if "suggested_units" in data.columns:
            data["_priority_units"] = data["suggested_units"].apply(safe_float)
        else:
            data["_priority_units"] = 0.0
        if "edge" in data.columns:
            data["_priority_edge"] = data["edge"].apply(lambda x: abs(safe_float(x)))
        else:
            data["_priority_edge"] = 0.0
        data["_priority_score"] = data["_priority_units"] * 100 + data["_priority_edge"]
        data = data.sort_values("_priority_score", ascending=False).head(4)
        for _, r in data.iterrows():
            units = safe_float(r.get("suggested_units", 0))
            if units <= 0 and safe_float(r.get("_priority_edge", 0)) <= 0:
                continue
            game = r.get("game", "")
            bet = r.get("recommended_bet", r.get("bet", r.get("selection", r.get("final_signal", "Review"))))
            edge = safe_float(r.get("edge", r.get("_priority_edge", 0)))
            conf = r.get("confidence", r.get("model_confidence", r.get("Confidence", "")))
            subtitle = f"{bet} · {units:.2f}u · edge {edge:+.1f}"
            if conf not in [None, ""]:
                subtitle += f" · conf {fmt(conf,0)}"
            rows.append((game or "Slate action", subtitle, f"{units:.2f}u"))

    if not rows and not proj.empty:
        data = proj.copy()
        if "edge" in data.columns:
            data["_abs_edge"] = data["edge"].apply(lambda x: abs(safe_float(x)))
            data = data.sort_values("_abs_edge", ascending=False).head(4)
            for _, r in data.iterrows():
                game = r.get("game", "")
                signal = r.get("final_signal", r.get("signal", "Review"))
                edge = safe_float(r.get("edge", 0))
                rows.append((game or "Market watch", f"{signal} · edge {edge:+.1f}", "WATCH"))

    if not rows:
        priority_html = '<div class="empty">No priority actions yet. Slate is in observation mode.</div>'
    else:
        priority_html = "".join([
            f'<div class="priority-row"><div class="priority-rank">#{idx}</div><div class="priority-main"><b>{title}</b><span>{sub}</span></div><div class="priority-score">{score}</div></div>'
            for idx, (title, sub, score) in enumerate(rows, 1)
        ])

    rec, total_units, total_stake = recommended_count_and_units(stake)
    sigs = active_signal_count(proj)
    pass_count = 0
    if not proj.empty:
        sig_col = "final_signal" if "final_signal" in proj.columns else "final_signal_normalized" if "final_signal_normalized" in proj.columns else "signal" if "signal" in proj.columns else None
        if sig_col:
            sig = proj[sig_col].fillna("PASS").astype(str).str.upper()
            pass_count = int(sig.eq("PASS").sum())
    env = read_json_safe(OUTPUT_DIR / "environment_regime_latest.json")
    regime = pick_value(env, "environment_regime", "EnvironmentRegime", default="LEARNING")
    chaos = pick_value(env, "avg_chaos", "AvgChaos", default="—")
    trust = pick_value(env, "avg_trust", "AvgTrust", default="—")

    watch_html = f"""
      <div class="watch-grid">
        <div class="watch-tile"><span>Action Queue</span><b>{rec}</b><small>{total_units:.2f}u · ${total_stake:.2f} exposure</small></div>
        <div class="watch-tile"><span>Signal Mix</span><b>{sigs}</b><small>{pass_count} pass/observe states</small></div>
        <div class="watch-tile"><span>Environment</span><b>{regime}</b><small>Chaos {chaos} · Trust {trust}</small></div>
        <div class="watch-tile"><span>Operator Mode</span><b>{'Execute' if rec else 'Observe'}</b><small>Manual review required before any bet</small></div>
      </div>
      <div class="injury-placeholder">Injury Integration: reserved slot. Connect injury feed later; this panel is intentionally display-only and does not change projections.</div>
    """

    return f"""
    <section class="operator-intel">
      <div class="operator-intel-card">
        <div class="operator-intel-head">
          <div>
            <div class="operator-intel-kicker"><span class="pulse-ring"></span>Priority Queue</div>
            <div class="operator-intel-title">Highest-leverage items to review first.</div>
            <div class="operator-intel-sub">Ranks actions by suggested units and edge so the operator sees the slate in execution order.</div>
          </div>
          <span class="chip">V18</span>
        </div>
        <div class="priority-stack">{priority_html}</div>
      </div>
      <div class="operator-intel-card">
        <div class="operator-intel-head">
          <div>
            <div class="operator-intel-kicker"><span class="pulse-ring yellow"></span>Context Watch</div>
            <div class="operator-intel-title">Exposure, regime, and safety checks.</div>
            <div class="operator-intel-sub">A compact read on risk, signal state, market climate, and discipline locks.</div>
          </div>
        </div>
        {watch_html}
      </div>
    </section>
    """


def component_status(path, online_label="Online", missing_label="Missing"):
    p = Path(path)
    if p.exists() and p.stat().st_size > 0:
        return online_label, "online"
    return missing_label, "missing"


def hermes_system_status_panel():
    components = [
        ("Research Brain", DAILY_RESEARCH_SNAPSHOT_JSON, "daily_research_snapshot.json"),
        ("Hermes Cycle", OUTPUT_DIR / "hermes_cycle_latest.json", "hermes_cycle_latest.json"),
        ("Environment Memory", OUTPUT_DIR / "environment_memory_latest.csv", "environment_memory_latest.csv"),
        ("Validation Engine", OUTPUT_DIR / "environment_validation_summary.csv", "environment_validation_summary.csv"),
        ("Hypothesis Registry", OUTPUT_DIR / "hypothesis_registry.csv", "hypothesis_registry.csv"),
        ("Telegram Output", TELEGRAM_TXT, "telegram_message.txt"),
    ]
    rows = []
    online_count = 0
    for name, path, detail in components:
        label, cls = component_status(path)
        if cls == "online":
            online_count += 1
        rows.append(f'<div class="hermes-status-row"><div><b>{name}</b><span>{detail}</span></div><div class="status-token {cls}">{label}</div></div>')
    rows.append('<div class="hermes-status-row"><div><b>Injury Feed</b><span>Reserved integration slot. Display-only until connected.</span></div><div class="status-token pending">Pending</div></div>')
    readiness = int(round((online_count / len(components)) * 100)) if components else 0
    mode = "Manual Approval"
    ladder = [
        ("L0", "Manual dashboard", "Active", True),
        ("L1", "Hermes mission brief", "Ready", True),
        ("L2", "Alerts and environment warnings", "Ready", True),
        ("L3", "Suggested bet actions", "Review", False),
        ("L4", "Telegram preparation", "Guarded", False),
        ("L5", "Approved workflow execution", "Locked", False),
        ("L6", "Full automation after validation gates", "Locked", False),
    ]
    ladder_html = "".join([
        f'<div class="automation-step {"active" if active else ""}"><span>{level}</span><b>{name}</b><em>{state}</em></div>'
        for level, name, state, active in ladder
    ])
    return f"""
    <section class="hermes-readiness">
      <div class="hermes-panel">
        <div class="hermes-head">
          <div>
            <div class="hermes-kicker"><span class="pulse-ring"></span>Hermes System Status</div>
            <div class="hermes-title">Automation readiness without breaking discipline.</div>
            <div class="hermes-copy">This panel checks whether the research, validation, environment, memory, and messaging layers are present. It does not execute bets and does not change model outputs.</div>
          </div>
          <span class="chip">{readiness}% Ready</span>
        </div>
        <div class="hermes-grid">{"".join(rows)}</div>
      </div>
      <div class="hermes-panel">
        <div class="hermes-head">
          <div>
            <div class="hermes-kicker"><span class="pulse-ring yellow"></span>Automation Mode</div>
            <div class="hermes-title">{mode}</div>
            <div class="hermes-copy">Hermes is being staged as an operator assistant first: research, alerts, mission brief, and approval workflow before execution.</div>
          </div>
        </div>
        <div class="automation-ladder">{ladder_html}</div>
        <div class="hermes-lock"><b>Discipline Lock:</b> Hermes cannot bypass staking rules, thresholds, validation gates, or manual approval in this version.</div>
      </div>
    </section>
    """


def system_audit_snapshot_panel():
    proj = read_csv(PROJECTIONS_CSV)
    stakes = read_csv(PROJECTIONS_STAKES_CSV)
    rec = read_csv(RECOMMENDED_CSV)
    health = read_csv(MODEL_HEALTH_CSV)
    clv = read_csv(SIGNAL_CLV_SUMMARY_CSV)
    env_memory = read_csv(OUTPUT_DIR / "environment_memory_latest.csv")
    cards = [
        ("Projection Rows", len(proj), "projections.csv"),
        ("Stake Rows", len(stakes), "projections_with_stakes.csv"),
        ("Recommended", len(rec), "recommended_bets.csv"),
        ("Health Rows", len(health), "model_health_report.csv"),
        ("CLV Rows", len(clv), "signal_clv_summary.csv"),
        ("Env Memory", len(env_memory), "environment_memory_latest.csv"),
    ]
    html = "".join([f'<div class="system-audit-card"><span>{a}</span><b>{b}</b><small>{c}</small></div>' for a,b,c in cards])
    return f'<div class="section-head"><div><h2>System Audit Snapshot</h2><p>Fast file/data presence check for model refinement work.</p></div><span class="chip">V18</span></div><div class="system-audit-grid">{html}</div>'



def website_landing_hero(proj_df, stake_df):
    sigs = active_signal_count(proj_df)
    rec, total_units, total_stake = recommended_count_and_units(stake_df)
    health = latest_health_dict()
    health_score = safe_float(health.get("modelhealthscore", health.get("ModelHealthScore", 0)), 0)
    env = read_json_safe(OUTPUT_DIR / "environment_regime_latest.json")
    env_regime = pick_value(env, "environment_regime", "EnvironmentRegime", default="LEARNING")
    return f"""
    <section class="site-hero">
      <div class="glass site-hero-main">
        <div>
          <div class="site-eyebrow"><span class="pulse-ring"></span> WNBA Edge Lab · Hermes OS</div>
          <h1 class="site-title">A research-grade betting command website.</h1>
          <p class="site-copy">Model projections, staking discipline, environment intelligence, research memory, and Hermes automation readiness in one local-first operator website. The system surfaces what matters, protects the workflow, and keeps final approval human-controlled.</p>
          <div class="site-actions">
            <a class="btn primary" href="/stakes">Review Today’s Actions</a>
            <a class="btn" href="/hermes">Hermes Readiness</a>
            <a class="btn" href="/environment">Environment Desk</a>
          </div>
        </div>
      </div>
      <div class="site-side">
        <div class="site-card"><span>Signals</span><b>{sigs}</b><p>Non-pass model opinions requiring operator awareness.</p></div>
        <div class="site-card"><span>Actions</span><b>{rec}</b><p>Recommended stake candidates under current rules.</p></div>
        <div class="site-card"><span>Exposure</span><b>{total_units:.2f}u</b><p>Total suggested unit load before approval.</p></div>
        <div class="site-card"><span>System</span><b>{health_score:.1f}</b><p>Model health score · environment: {env_regime}</p></div>
      </div>
    </section>
    """


def website_capability_band():
    items = [
        ("Model", "Projection Engine", "Slate projections, edges, confidence, and stake candidates."),
        ("Environment", "Market Climate", "Chaos, trust, CLV, and bucket validation context."),
        ("Research", "Memory Layer", "Hypotheses, learning loops, and research snapshots."),
        ("Hermes", "Automation Guard", "Readiness checks, manual approval, and future agent control."),
    ]
    cards = ''.join([f'<div class="website-band-card"><span>{a}</span><b>{b}</b><p>{c}</p></div>' for a,b,c in items])
    return f'<section class="website-band">{cards}</section>'


def site_section_label(title, copy, chip="Operator Surface"):
    return f"""
    <div class="site-section-label">
      <div><h2>{title}</h2><p>{copy}</p></div>
      <span class="chip">{chip}</span>
    </div>
    """

def command_center_hero(proj_df, stake_df):
    health = latest_health_dict()
    integrity = read_json_safe(OUTPUT_DIR / "data_integrity_latest.json")
    env = read_json_safe(OUTPUT_DIR / "environment_regime_latest.json")
    regime = read_json_safe(OUTPUT_DIR / "memory_regime_latest.json")

    health_score = safe_float(health.get("modelhealthscore", health.get("ModelHealthScore", pick_value(regime, "health", "health_score", "Health", default=0))), 0)
    health_label = health.get("healthlabel", health.get("HealthLabel", pick_value(regime, "regime", "Regime", "environment_regime", default="LEARNING")))
    sample = health.get("samplesize", health.get("SampleSize", pick_value(regime, "sample", "sample_size", "Sample", default="")))
    avg_clv = safe_float(health.get("avgclv", health.get("AvgCLV", pick_value(regime, "avg_clv", "AvgCLV", default=0))), 0)
    wr = safe_float(health.get("signalwinrate", health.get("SignalWinRate", pick_value(regime, "signal_wr", "SignalWR", default=0))), 0)
    integrity_score = pick_value(integrity, "integrity_score", "IntegrityScore", "score", default="93")
    env_regime = pick_value(env, "environment_regime", "EnvironmentRegime", default="LEARNING")
    env_clv = pick_value(env, "avg_clv", "AvgCLV", default="")

    sigs = active_signal_count(proj_df)
    rec, total_units, total_stake = recommended_count_and_units(stake_df)

    return f"""
    <section class="command-hero">
      <div class="glass command-main">
        <div>
          <div class="command-kicker"><span class="pulse-ring"></span>Hermes Command Center</div>
          <div class="command-title">Hermes operator focus for decisive slate execution.</div>
          <div class="command-sub">Faster scan flow, cleaner exposure awareness, sharper environment context, and fewer distractions between signal and action. Models stay frozen; execution gets sharper.</div>
        </div>
        <div class="command-grid">
          <div class="command-tile"><span>Health</span><b>{health_score:.1f}</b></div>
          <div class="command-tile"><span>Regime</span><b>{health_label}</b></div>
          <div class="command-tile"><span>Integrity</span><b>{integrity_score}</b></div>
          <div class="command-tile"><span>Sample</span><b>{sample}</b></div>
          <div class="command-tile"><span>Avg CLV</span><b class="{'positive' if avg_clv >= 0 else 'negative'}">{avg_clv:+.2f}</b></div>
          <div class="command-tile"><span>Signal WR</span><b>{wr:.1f}%</b></div>
          <div class="command-tile"><span>Actions</span><b>{rec}</b></div>
          <div class="command-tile"><span>Units</span><b>{total_units:.2f}u</b></div>
        </div>
      </div>
      <div class="glass command-side">
        <div class="operator-card"><div><div class="name">Environment Regime</div><div class="desc">Macro market condition layer</div></div><div class="operator-state">{env_regime}</div></div>
        <div class="operator-card"><div><div class="name">Environment CLV</div><div class="desc">Bucket-level market agreement</div></div><div class="operator-state">{env_clv}</div></div>
        <div class="operator-card"><div><div class="name">Signals Today</div><div class="desc">Non-pass model opinions</div></div><div class="operator-state">{sigs}</div></div>
        <div class="operator-card"><div><div class="name">Capital at Risk</div><div class="desc">Suggested stake exposure</div></div><div class="operator-state">${total_stake:.2f}</div></div>
      </div>
    </section>
    """


def environment_command_panel():
    env = read_json_safe(OUTPUT_DIR / "environment_regime_latest.json")
    buckets = read_csv(OUTPUT_DIR / "environment_bucket_report.csv")
    shares = env.get("bucket_shares", {}) if isinstance(env, dict) else {}
    regime = pick_value(env, "environment_regime", "EnvironmentRegime", default="LEARNING")
    reason = pick_value(env, "reason", "Reason", default="Sample still building.")
    avg_clv = pick_value(env, "avg_clv", "AvgCLV", default="")
    avg_chaos = pick_value(env, "avg_chaos", "AvgChaos", default="")
    avg_trust = pick_value(env, "avg_trust", "AvgTrust", default="")
    no_play = shares.get("neutral_no_play", shares.get("no_play", ""))

    if not buckets.empty:
        b = normalize(buckets)
        cols = [c for c in ["game", "environmentbucket", "edge", "confidence", "chaosscore", "trustscore"] if c in b.columns]
        table_html = table(b, cols=cols, max_rows=6)
    else:
        table_html = '<div class="empty">No environment bucket report yet.</div>'

    return f"""
    <div class="panel terminal-section">
      <div class="section-head" style="margin-top:0"><div><h2>Environment Command</h2><p>{reason}</p></div><span class="chip">{regime}</span></div>
      <div class="env-mini-grid">
        <div class="env-mini"><span>Avg Env CLV</span><b>{avg_clv}</b></div>
        <div class="env-mini"><span>Chaos</span><b>{avg_chaos}</b></div>
        <div class="env-mini"><span>Trust</span><b>{avg_trust}</b></div>
        <div class="env-mini"><span>No Play %</span><b>{no_play}</b></div>
        <div class="env-mini"><span>Extreme Over</span><b>{shares.get('extreme_over','')}</b></div>
        <div class="env-mini"><span>Lean Over</span><b>{shares.get('lean_over','')}</b></div>
      </div>
      <div style="margin-top:12px">{table_html}</div>
    </div>
    """


def hypothesis_command_panel():
    hyp = read_csv(OUTPUT_DIR / "hypothesis_memory_latest.csv")
    if hyp.empty:
        return '<div class="panel"><div class="section-head" style="margin-top:0"><div><h2>Hypothesis Command</h2><p>No hypothesis memory available yet.</p></div></div><div class="empty">Run hypothesis memory engine.</div></div>'
    h = normalize(hyp)
    cols = [c for c in ["hypothesisid", "hypothesisname", "memorystate", "status", "sample", "winrate", "roi", "avgclv", "priority"] if c in h.columns]
    return f"""
    <div class="panel">
      <div class="section-head" style="margin-top:0"><div><h2>Hypothesis Command</h2><p>Edge discovery memory state.</p></div><span class="chip">Research Only</span></div>
      {table(h, cols=cols, max_rows=6)}
    </div>
    """


def hermes_activity_feed():
    items = [
        ("Cycle", "Research Brain outputs loaded", "OK" if (OUTPUT_DIR / "research_brain_run_log.txt").exists() else "WAIT"),
        ("Integrity", "Data integrity latest report available", "OK" if (OUTPUT_DIR / "data_integrity_latest.json").exists() else "WAIT"),
        ("Environment", "Regime + bucket layers connected", "OK" if (OUTPUT_DIR / "environment_regime_latest.json").exists() else "WAIT"),
        ("Hypotheses", "Memory layer connected", "OK" if (OUTPUT_DIR / "hypothesis_memory_latest.csv").exists() else "WAIT"),
        ("Telegram", "Operator message file available", "OK" if TELEGRAM_TXT.exists() else "WAIT"),
        ("Rule", "No auto-bets, no auto-formula changes", "LOCK"),
    ]
    rows = ''.join([f'<div class="activity-row"><span>{a}</span><b>{b}</b><em>{c}</em></div>' for a,b,c in items])
    return f"""
    <div class="panel">
      <div class="section-head" style="margin-top:0"><div><h2>Hermes Activity</h2><p>Operator system heartbeat.</p></div><span class="chip">Live OS</span></div>
      <div class="activity-feed">{rows}</div>
    </div>
    """


def command_center_projection_summary(df):
    if df.empty:
        return '<div class="panel empty">No projections loaded.</div>'
    data = normalize(df)
    if "edge" in data.columns:
        data = data.assign(_abs_edge=data["edge"].apply(lambda x: abs(safe_float(x))))
        data = data.sort_values("_abs_edge", ascending=False)
    return projection_cards(data.head(6))


def today_status_strip(proj_df, stake_df):
    proj = normalize(proj_df)
    stake = normalize(stake_df)
    rec, total_units, total_stake = recommended_count_and_units(stake)
    sigs = active_signal_count(proj)
    games = len(proj) if not proj.empty else 0
    avg_edge = 0.0
    top_edge = 0.0
    if not proj.empty and "edge" in proj.columns:
        edge_series = proj["edge"].apply(safe_float)
        avg_edge = float(edge_series.mean()) if len(edge_series) else 0.0
        top_edge = float(edge_series.abs().max()) if len(edge_series) else 0.0
    env = read_json_safe(OUTPUT_DIR / "environment_regime_latest.json")
    regime = pick_value(env, "environment_regime", "EnvironmentRegime", default="LEARNING")
    exposure_state = "Clear" if total_units <= 3 else "Review" if total_units <= 6 else "High"
    tiles = [
        ("Games", games, "market totals"),
        ("Signals", sigs, "non-pass opinions"),
        ("Actions", rec, "tickets > 0u"),
        ("Exposure", f"{total_units:.2f}u", exposure_state),
        ("Top Edge", f"{top_edge:.1f}", "absolute"),
        ("Regime", regime, f"avg edge {avg_edge:+.1f}"),
    ]
    return '<section class="today-status-strip">' + ''.join([
        f'<div class="today-status-tile"><span>{a}</span><b>{b}</b><small>{c}</small></div>'
        for a,b,c in tiles
    ]) + '</section>'


def today_brief_clean(proj_df, stake_df):
    proj = normalize(proj_df)
    stake = normalize(stake_df)
    rec, total_units, total_stake = recommended_count_and_units(stake)
    env = read_json_safe(OUTPUT_DIR / "environment_regime_latest.json")
    integrity = read_json_safe(OUTPUT_DIR / "data_integrity_latest.json")
    regime = pick_value(env, "environment_regime", "EnvironmentRegime", default="LEARNING")
    integrity_score = pick_value(integrity, "integrity_score", "IntegrityScore", "score", default="WAIT")

    top_action = "No active bet. Observe slate."
    top_state = "OBSERVE"
    if not stake.empty and "suggested_units" in stake.columns:
        ranked = stake.copy()
        ranked["_units"] = ranked["suggested_units"].apply(safe_float)
        ranked = ranked.sort_values("_units", ascending=False)
        if not ranked.empty and safe_float(ranked.iloc[0].get("_units", 0)) > 0:
            r = ranked.iloc[0]
            game = r.get("game", "")
            bet = r.get("recommended_bet", r.get("bet", r.get("selection", r.get("final_signal", "Review"))))
            top_action = f"{game} · {bet}" if game else str(bet)
            top_state = f"{safe_float(r.get('_units', 0)):.2f}u"

    exposure_state = "CLEAR" if total_units <= 3 else "REVIEW" if total_units <= 6 else "HIGH"
    mode = "Execute Review" if rec else "Observation"

    mission_rows = [
        ("Mode", f"{mode}: {rec} action(s), {total_units:.2f}u exposure", exposure_state, "warn" if exposure_state != "CLEAR" else ""),
        ("Top", top_action, top_state, "" if rec else "warn"),
        ("Market", f"Environment {regime} · integrity {integrity_score}", "CHECK", ""),
        ("Rule", "Manual approval only. No auto-bets from dashboard.", "LOCK", "lock"),
    ]
    mission_html = ''.join([f'<div class="today-row {cls}"><span>{a}</span><b>{b}</b><em>{c}</em></div>' for a,b,c,cls in mission_rows])

    review_rows = []
    if not stake.empty:
        data = stake.copy()
        data["_units"] = data["suggested_units"].apply(safe_float) if "suggested_units" in data.columns else 0.0
        data["_edge"] = data["edge"].apply(lambda x: abs(safe_float(x))) if "edge" in data.columns else 0.0
        data = data.sort_values(["_units", "_edge"], ascending=False).head(4)
        for i, (_, r) in enumerate(data.iterrows(), 1):
            units = safe_float(r.get("_units", 0))
            edge = safe_float(r.get("edge", r.get("_edge", 0)))
            if units <= 0 and abs(edge) <= 0:
                continue
            game = r.get("game", "Slate item")
            bet = r.get("recommended_bet", r.get("bet", r.get("selection", r.get("final_signal", "Review"))))
            review_rows.append((f"#{i}", f"{game} · {bet}", f"{units:.2f}u" if units > 0 else "WATCH", ""))
    if not review_rows and not proj.empty and "edge" in proj.columns:
        data = proj.copy()
        data["_abs_edge"] = data["edge"].apply(lambda x: abs(safe_float(x)))
        for i, (_, r) in enumerate(data.sort_values("_abs_edge", ascending=False).head(4).iterrows(), 1):
            review_rows.append((f"#{i}", f"{r.get('game','Market watch')} · {r.get('final_signal', r.get('signal','Review'))}", f"{safe_float(r.get('edge',0)):+.1f}", "warn"))
    if not review_rows:
        review_html = '<div class="empty">Nothing urgent. Slate is in observation mode.</div>'
    else:
        review_html = ''.join([f'<div class="today-row {cls}"><span>{a}</span><b>{b}</b><em>{c}</em></div>' for a,b,c,cls in review_rows])

    return f"""
    <section class="today-flow">
      <div class="today-panel">
        <div class="today-panel-head">
          <div>
            <div class="today-kicker"><span class="pulse-ring"></span>Today Brief</div>
            <div class="today-panel-title">Clean slate command: what matters now.</div>
            <div class="today-panel-sub">Reduced homepage noise. Review state, top action, market condition, and discipline lock before opening tickets.</div>
          </div>
          <span class="chip">V18.1</span>
        </div>
        <div class="today-list">{mission_html}</div>
      </div>
      <div class="today-panel">
        <div class="today-panel-head">
          <div>
            <div class="today-kicker"><span class="pulse-ring yellow"></span>Review Queue</div>
            <div class="today-panel-title">First four items only.</div>
            <div class="today-panel-sub">The full tables stay on their own pages. Today stays fast.</div>
          </div>
        </div>
        <div class="today-list">{review_html}</div>
      </div>
    </section>
    """


def true_website_home(proj_df, stake_df):
    sigs = active_signal_count(proj_df)
    rec, total_units, total_stake = recommended_count_and_units(stake_df)
    health = latest_health_dict()
    health_score = safe_float(health.get("modelhealthscore", health.get("ModelHealthScore", 0)), 0)
    env = read_json_safe(OUTPUT_DIR / "environment_regime_latest.json")
    env_regime = pick_value(env, "environment_regime", "EnvironmentRegime", default="LEARNING")
    norm = normalize(stake_df)
    top = None
    if not norm.empty:
        work = norm.copy()
        if "suggested_units" in work.columns:
            work["__units"] = work["suggested_units"].apply(safe_float)
            work = work.sort_values("__units", ascending=False)
            top = work.iloc[0].to_dict() if not work.empty else None
    top_game = pick_value(top or {}, "game", "Game", default="No active card")
    top_bet = pick_value(top or {}, "recommended_bet", "RecommendedBet", "bet", default="Awaiting slate")
    top_units = safe_float(pick_value(top or {}, "suggested_units", "SuggestedUnits", default=0), 0)
    return f"""
    <main class="web-home">
      <section class="web-hero">
        <div class="web-hero-grid">
          <div>
            <div class="web-eyebrow"><span class="pulse-ring"></span> Public Command Website</div>
            <h1 class="web-title">WNBA intelligence, organized for decisions.</h1>
            <p class="web-copy">Edge Lab is a research website for projections, staking discipline, environment context, validation memory, and Hermes automation readiness. The homepage stays clean. The work happens inside focused desks.</p>
            <div class="web-actions">
              <a class="btn primary" href="/stakes">Open Action Board</a>
              <a class="btn" href="/environment">View Environment</a>
              <a class="btn" href="/hermes">Hermes Agent</a>
            </div>
            <div class="deep-link-strip">
              <a href="/analysis">Model Lab</a><a href="/validation">Validation</a><a href="/diagnostics">Diagnostics</a><a href="/memory">Memory</a><a href="/telegram">Telegram</a>
            </div>
          </div>
          <div class="web-kpi-panel">
            <div class="web-kpi"><span>Signals</span><b>{sigs}</b><p>Active model opinions currently above pass state.</p></div>
            <div class="web-kpi"><span>Actions</span><b>{rec}</b><p>Stake candidates generated by existing rules.</p></div>
            <div class="web-kpi"><span>Exposure</span><b>{total_units:.2f}u</b><p>Recommended unit load before human approval.</p></div>
            <div class="web-kpi"><span>Health</span><b>{health_score:.1f}</b><p>System health · environment {env_regime}</p></div>
          </div>
        </div>
      </section>

      <section class="web-section">
        <div class="web-section-head"><div><h2>Choose your desk</h2><p>Five public paths. The old dashboard clutter is moved into deep links, not the main navigation.</p></div><span class="chip">Website</span></div>
        <div class="web-feature-grid">
          <a class="web-feature" href="/stakes"><span>01 / Action</span><b>Review today’s board</b><p>Exact bets, unit sizing, exposure, and manual approval state.</p></a>
          <a class="web-feature" href="/environment"><span>02 / Conditions</span><b>Read the market climate</b><p>Chaos, trust, bucket mix, CLV posture, and environment memory.</p></a>
          <a class="web-feature" href="/research"><span>03 / Research</span><b>Track learning memory</b><p>Daily research snapshots, insights, hypotheses, and model notes.</p></a>
          <a class="web-feature" href="/hermes"><span>04 / Hermes</span><b>Automation stays guarded</b><p>Hermes observes, warns, recommends, and prepares operator workflows. It does not bypass approval, staking rules, thresholds, or validation gates.</p></a>
        </div>
      </section>

      <section class="web-section">
        <div class="web-section-head"><div><h2>Live slate snapshot</h2><p>Home only shows the minimum. No repeated command center blocks. No raw tables.</p></div><span class="chip">Today</span></div>
        <div class="web-split">
          <div class="web-preview"><h3>Top review item</h3><p>The first card in the current stake queue. Full context stays on Actions.</p><div class="web-mini-list">
            <div class="web-mini-row"><span>Game</span><b>{top_game}</b><em>Review</em></div>
            <div class="web-mini-row"><span>Bet</span><b>{top_bet}</b><em>{top_units:.2f}u</em></div>
            <div class="web-mini-row warn"><span>Mode</span><b>Manual approval required</b><em>Locked</em></div>
          </div></div>
          <div class="web-preview"><h3>Operating posture</h3><p>Hermes readiness, research memory, and discipline remain separated from the homepage.</p><div class="web-mini-list">
            <div class="web-mini-row"><span>Hermes</span><b>Guardrail mode active</b><em>Manual</em></div>
            <div class="web-mini-row"><span>Research</span><b>Memory desk available</b><em>Online</em></div>
            <div class="web-mini-row"><span>Discipline</span><b>No execution without approval</b><em>Locked</em></div>
          </div></div>
        </div>
      </section>

      <section class="web-section">
        <div class="web-section-head"><div><h2>How Edge Lab works</h2><p>A website layer on top of the analytics engine, built for disciplined review before automation.</p></div></div>
        <div class="public-proof-grid">
          <div class="public-proof"><span>Model</span><b>Projects the slate</b><p>Scores, totals, edge, confidence, and diagnostics are generated by the existing backend.</p></div>
          <div class="public-proof"><span>Environment</span><b>Checks the conditions</b><p>Chaos, trust, and bucket memory are observational context, not formula overrides.</p></div>
          <div class="public-proof"><span>Operator</span><b>Approves the action</b><p>Hermes can assist the workflow, but approval and discipline gates stay in control.</p></div>
        </div>
      </section>
    </main>
    """

def hermes_product_experience():
    checks = [
        ("Research Brain", (OUTPUT_DIR / "daily_research_snapshot.json").exists()),
        ("Hermes Cycle", (OUTPUT_DIR / "dashboard_insights.txt").exists()),
        ("Environment Memory", (OUTPUT_DIR / "environment_memory_latest.csv").exists()),
        ("Validation Engine", (OUTPUT_DIR / "environment_validation_summary.csv").exists()),
        ("Hypothesis Registry", (OUTPUT_DIR / "hypothesis_registry.csv").exists()),
        ("Telegram Output", TELEGRAM_TXT.exists()),
        ("Injury Feed", False),
    ]
    rows = "".join([f'<div class="hermes-status-row"><b>{name}</b><span class="{"ok" if ok else "warn"}">{"Online" if ok else "Pending"}</span></div>' for name, ok in checks])
    steps = [("L0", "Manual dashboard", "Active", "active"), ("L1", "Mission brief generation", "Ready", "active"), ("L2", "Alerts and warnings", "Ready", "active"), ("L3", "Suggested bet actions", "Guarded", "locked"), ("L4", "Telegram preparation", "Guarded", "locked"), ("L5", "Approved workflow execution", "Locked", "locked"), ("L6", "Full automation", "Locked", "locked")]
    ladder = "".join([f'<div class="hermes-step {cls}"><span>{lvl}</span><b>{label}</b><em>{state}</em></div>' for lvl,label,state,cls in steps])
    return f"""
    <main class="hermes-product">
      <section class="hermes-hero">
        <div class="web-eyebrow"><span class="pulse-ring"></span> Hermes Agent OS</div>
        <h1>Automation with brakes, memory, and approval.</h1>
        <p>Hermes is not a betting robot. It is the agent layer that observes the slate, warns about risk, prepares review queues, drafts operator outputs, and eventually runs approved workflows. Every automation stage remains gated by validation, staking discipline, and human approval.</p>
        <div class="hermes-hero-actions"><a class="btn primary" href="/stakes">Review Actions</a><a class="btn" href="/environment">Environment Risk</a><a class="btn" href="/research">Research Memory</a></div>
        <div class="hermes-agent-strip">
          <div class="web-mini-row"><span>Mode</span><b>Manual approval</b><em>Locked</em></div>
          <div class="web-mini-row"><span>Role</span><b>Operator assistant</b><em>Guarded</em></div>
          <div class="web-mini-row"><span>Execution</span><b>No auto-bet flow</b><em>Blocked</em></div>
          <div class="web-mini-row"><span>Next</span><b>Mission brief automation</b><em>Ready</em></div>
        </div>
      </section>

      <section class="hermes-grid">
        <div class="hermes-card"><span>Observe</span><b>Read the system</b><p>Collect slate state, model health, exposure, environment regime, validation state, and research memory.</p></div>
        <div class="hermes-card"><span>Warn</span><b>Surface risk</b><p>Flag missing files, bad regimes, exposure pressure, low validation, stale research, and injury-feed gaps.</p></div>
        <div class="hermes-card"><span>Recommend</span><b>Prepare review</b><p>Rank what the operator should inspect first. Suggestions are not execution commands.</p></div>
        <div class="hermes-card"><span>Approve</span><b>Keep control</b><p>Telegram preparation and workflow execution remain gated until approval and validation rules are satisfied.</p></div>
      </section>

      <section class="hermes-state">
        <div class="web-preview"><h3>System readiness</h3><p>Component visibility for the future Hermes automation agent.</p><div class="hermes-status-list">{rows}</div></div>
        <div class="web-preview"><h3>Automation ladder</h3><p>Safe phased path. Approval remains mandatory until validation says otherwise.</p><div class="hermes-ladder">{ladder}</div></div>
      </section>

      <section class="web-section">
        <div class="web-section-head"><div><h2>Guardrails</h2><p>Hermes gets stronger only by respecting the rules that protect the bankroll.</p></div><span class="chip">Safety</span></div>
        <div class="public-proof-grid">
          <div class="public-proof"><span>Discipline</span><b>Staking rules stay frozen</b><p>No automation layer can override units, thresholds, or pass states without explicit review.</p></div>
          <div class="public-proof"><span>Validation</span><b>Low sample means caution</b><p>Environment and signal memory inform review priority; they do not create automatic bets.</p></div>
          <div class="public-proof"><span>Approval</span><b>Human remains final gate</b><p>Hermes can draft, warn, and prepare. Execution waits for the operator.</p></div>
        </div>
      </section>
    </main>
    """


def _norm(df):
    return normalize(df) if isinstance(df, pd.DataFrame) else pd.DataFrame()

def file_state(path, label):
    exists = Path(path).exists()
    return f'<div class="mission-row"><span>{label}</span><b>{Path(path).name}</b><em>{"Online" if exists else "Missing"}</em></div>'

def smart_missing(filename, action="Run the pipeline or upload the output file."):
    return f'<div class="missing-smart"><b>Waiting for {filename}</b><br>{action}</div>'

def slate_stats():
    proj = _norm(read_csv(PROJECTIONS_CSV)); stakes = _norm(read_csv(PROJECTIONS_STAKES_CSV)); bets = _norm(load_bets())
    games = len(proj) if not proj.empty else 0
    rec = 0; units = 0.0; stake_total = 0.0
    if not stakes.empty:
        unit_col = "suggestedunits" if "suggestedunits" in stakes.columns else "suggested_units" if "suggested_units" in stakes.columns else None
        stake_col = "suggestedstake" if "suggestedstake" in stakes.columns else "suggested_stake" if "suggested_stake" in stakes.columns else None
        if unit_col:
            units = stakes[unit_col].apply(safe_float).sum(); rec = int((stakes[unit_col].apply(safe_float) > 0).sum())
        if stake_col: stake_total = stakes[stake_col].apply(safe_float).sum()
    open_bets = 0
    if not bets.empty and "result" in bets.columns:
        open_bets = int(bets["result"].astype(str).str.upper().isin(["PENDING", "OPEN", ""]).sum())
    return {"games": games, "recommended": rec, "units": units, "stake": stake_total, "open_bets": open_bets}

def bankroll_snapshot():
    df = load_bets()
    if df.empty:
        return {"current": 100.0, "pl": 0.0, "roi": 0.0, "settled": 0, "pending": 0, "wins": 0, "losses": 0, "stake": 0.0, "avg_stake": 0.0, "drawdown": 0.0}
    df = df.copy(); df["profit_loss"] = df.apply(calc_pl, axis=1)
    result = df.get("result", pd.Series([], dtype=str)).astype(str).str.upper()
    settled = df[~result.isin(["PENDING", "OPEN", ""])] if not result.empty else df.iloc[0:0]
    pending = df[result.isin(["PENDING", "OPEN", ""])] if not result.empty else df.iloc[0:0]
    stake = pd.to_numeric(settled.get("stake", 0), errors="coerce").fillna(0).sum() if not settled.empty else 0.0
    pl = pd.to_numeric(settled.get("profit_loss", 0), errors="coerce").fillna(0).sum() if not settled.empty else 0.0
    roi = (pl / stake * 100) if stake else 0.0
    wins = int((settled.get("result", pd.Series([], dtype=str)).astype(str).str.upper() == "WIN").sum()) if not settled.empty else 0
    losses = int((settled.get("result", pd.Series([], dtype=str)).astype(str).str.upper() == "LOSS").sum()) if not settled.empty else 0
    avg_stake = (stake / len(settled)) if len(settled) else 0.0
    return {"current": 100.0 + pl, "pl": pl, "roi": roi, "settled": len(settled), "pending": len(pending), "wins": wins, "losses": losses, "stake": stake, "avg_stake": avg_stake, "drawdown": min(0.0, pl)}

def v19_home():
    ss = slate_stats(); bank = bankroll_snapshot()
    return f'''<main class="v19-home"><section class="v19-hero"><div class="v19-hero-grid"><div><div class="v19-eyebrow"><span class="pulse-ring"></span> WNBA Edge Lab</div><h1 class="v19-title">A betting research terminal with agent-grade discipline.</h1><p class="v19-copy">Edge Lab combines projections, staking discipline, environment memory, research validation, bankroll control, and Hermes automation readiness into one public website and private operator terminal.</p><div class="v19-actions"><a class="btn primary" href="/dashboard">Open Dashboard</a><a class="btn" href="/bankroll">Bankroll Tracker</a><a class="btn" href="/hermes">Hermes Agent</a></div></div><div class="v19-side"><div class="v19-kpi"><span>Slate</span><b>{ss['games']}</b><p>Projected games currently visible.</p></div><div class="v19-kpi"><span>Actions</span><b>{ss['recommended']}</b><p>Recommended bets needing review.</p></div><div class="v19-kpi"><span>Exposure</span><b>{ss['units']:.2f}u</b><p>Slate exposure from staking.</p></div><div class="v19-kpi"><span>Bankroll P/L</span><b>{bank['pl']:+.2f}u</b><p>Settled tracker performance.</p></div></div></div></section><section><div class="v19-section-head"><div><h2>Four desks. One workflow.</h2><p>Home stays clean. Deep operations live inside dedicated desks.</p></div><span class="chip">V21.8</span></div><div class="v19-grid-4"><a class="v19-card" href="/dashboard"><span>Terminal</span><b>Operator Dashboard</b><p>Mission brief, actions, risk, environment, model health, and activity feed.</p></a><a class="v19-card" href="/bankroll"><span>Fund</span><b>Bankroll Control</b><p>P/L, ROI, pending exposure, drawdown, and unit discipline.</p></a><a class="v19-card" href="/actions"><span>Action</span><b>Bet Review Desk</b><p>Recommended actions, pass states, stake sizes, and approval status.</p></a><a class="v19-card" href="/hermes"><span>Agent</span><b>Hermes Automation</b><p>Observe, warn, recommend, and prepare workflows with manual approval.</p></a></div></section><section><div class="v19-section-head"><div><h2>Today snapshot</h2><p>Only the minimum public context belongs on Home.</p></div><a class="chip" href="/dashboard">Open terminal</a></div><div class="v19-grid-3"><div class="v19-panel"><div class="mission-row"><span>Mode</span><b>Manual approval</b><em>Locked</em></div><div class="mission-row"><span>Actions</span><b>{ss['recommended']} bets to review</b><em>{ss['units']:.2f}u</em></div><div class="mission-row"><span>Risk</span><b>Hermes cannot execute bets</b><em>Safe</em></div></div><div class="v19-panel">{file_state(PROJECTIONS_CSV, 'Model')}{file_state(PROJECTIONS_STAKES_CSV, 'Staking')}{file_state(MODEL_HEALTH_CSV, 'Health')}</div><div class="v19-panel">{file_state(OUTPUT_DIR / 'environment_memory_latest.csv', 'Memory')}{file_state(OUTPUT_DIR / 'environment_validation_summary.csv', 'Validation')}{file_state(TELEGRAM_TXT, 'Telegram')}</div></div></section></main>'''

def action_board(df, limit=12):
    data = _norm(df)
    if data.empty:
        return smart_missing('projections_with_stakes.csv', 'Run the staking pipeline to populate the action board.')
    unit_col = "suggestedunits" if "suggestedunits" in data.columns else "suggested_units" if "suggested_units" in data.columns else None
    if unit_col:
        data["_units"] = data[unit_col].apply(safe_float)
        data = data.sort_values("_units", ascending=False)
    cards = []
    for i, (_, r) in enumerate(data.head(limit).iterrows(), start=1):
        game = r.get("game", r.get("matchup", "Slate game"))
        bet = r.get("recommended_bet", r.get("finalsignal", r.get("final_signal", "Review")))
        units = safe_float(r.get(unit_col, 0)) if unit_col else 0
        stake = r.get("suggestedstake", r.get("suggested_stake", ""))
        edge = r.get("edge", r.get("model_edge", ""))
        conf = r.get("confidence", r.get("confidence_score", ""))
        env = r.get("environmentbucket", r.get("environment_bucket", r.get("environmentaction", "Watch")))
        odds = r.get("odds", r.get("assumedodds", r.get("assumed_odds", "")))
        market = r.get("market", r.get("bet_type", r.get("type", "Market")))
        status = "Approval Required" if units > 0 else "No Play / Pass"
        badge = "green" if units > 0 else "gray"
        risk_state = "Ready" if units > 0 and units <= 2.5 else "Review" if units > 0 else "Pass"
        risk_cls = "ready" if risk_state == "Ready" else "warn" if risk_state == "Review" else "locked"
        why = "Positive unit output from the frozen staking model." if units > 0 else "Model output is below bet threshold or marked as pass."
        risk = "Standard review" if units <= 2.5 else "High exposure review"
        if units <= 0:
            risk = "No exposure"
        cards.append(f'''<div class="action-clean-card">
          <div class="action-clean-head"><div><div class="action-rank-clean">#{i:02d} Review</div><div class="action-clean-title">{game}</div></div><span class="badge {badge}">{status}</span></div>
          <div class="action-clean-bet">{bet}</div>
          <div class="action-meta-clean">Market: <strong>{market}</strong> · Stake: <strong>{units:.2f}u</strong> · Amount: <strong>{stake}</strong> · Odds: <strong>{odds}</strong></div>
          <div class="action-clean-grid"><div class="mini"><span>Units</span><b>{units:.2f}</b></div><div class="mini"><span>Edge</span><b>{edge}</b></div><div class="mini"><span>Confidence</span><b>{conf}</b></div><div class="mini"><span>Environment</span><b>{env}</b></div><div class="mini"><span>Approval</span><b>Manual</b></div></div>
          <div class="action-reason-grid">
            <div class="reason-box"><span>Why this bet</span><b>{why}</b><p>Use this as the review starting point, not automatic execution.</p></div>
            <div class="reason-box"><span>Risk context</span><b>{risk}</b><p>Check bankroll exposure, environment state, and any injury/news gaps before approval.</p></div>
            <div class="reason-box"><span>Operator action</span><b>{'Approve / reject manually' if units > 0 else 'Respect pass state'}</b><p>Hermes is locked from execution.</p></div>
          </div>
          <div class="approval-rail"><span class="approval-pill {risk_cls}">{risk_state}</span><span class="approval-pill locked">No auto-bet</span><span class="approval-pill warn">Injury check pending</span></div>
        </div>''')
    return '<div class="action-board">' + ''.join(cards) + '</div>'

def risk_safety_panel():
    ss = slate_stats(); bank = bankroll_snapshot(); exposure_cls = "ok" if ss['units'] <= 3 else "warn" if ss['units'] <= 6 else "lock"; draw_cls = "ok" if bank['pl'] >= 0 else "warn" if bank['pl'] > -5 else "lock"
    return f'''<section><div class="v19-section-head"><div><h2>Risk & safety</h2><p>Hermes cannot bypass these gates.</p></div><span class="chip">Guardrails</span></div><div class="risk-grid"><div class="risk-card {exposure_cls}"><span>Open Exposure</span><b>{ss['units']:.2f}u</b><p>Manual review required before Telegram or execution.</p></div><div class="risk-card {draw_cls}"><span>Bankroll P/L</span><b>{bank['pl']:+.2f}u</b><p>Drawdown state informs automation readiness.</p></div><div class="risk-card lock"><span>Automation</span><b>Locked</b><p>Full automation disabled until validation and approval gates clear.</p></div></div></section>'''


def v192_operator_brief():
    ss = slate_stats(); bank = bankroll_snapshot()
    exposure = "Normal" if ss['units'] <= 3 else "Elevated" if ss['units'] <= 6 else "Locked"
    return f'''<section class="v192-brief"><h3>Operator brief</h3><div class="v192-brief-grid"><div class="v192-brief-card"><span>First read</span><b>{ss['recommended']} actions to review</b><p>Start with actions, then validate environment and exposure.</p></div><div class="v192-brief-card"><span>Exposure</span><b>{ss['units']:.2f}u · {exposure}</b><p>Current slate output. Manual approval stays required.</p></div><div class="v192-brief-card"><span>Bankroll state</span><b>{bank['pl']:+.2f}u P/L</b><p>Performance state informs Hermes automation readiness.</p></div></div></section>'''

def v192_command_strip():
    ss = slate_stats()
    return f'''<section class="v192-command-strip"><div class="v192-chip-card"><span>Mode</span><b>Manual</b><p>Hermes cannot execute.</p></div><div class="v192-chip-card"><span>Actions</span><b>{ss['recommended']}</b><p>Need review.</p></div><div class="v192-chip-card"><span>Exposure</span><b>{ss['units']:.2f}u</b><p>Slate output.</p></div><div class="v192-chip-card"><span>Open Bets</span><b>{ss['open_bets']}</b><p>Tracker state.</p></div><div class="v192-chip-card injury-status"><span>Injuries</span><b>Pending</b><p>Feed placeholder.</p></div></section>'''

def bank_limit_panel():
    ss = slate_stats(); bank = bankroll_snapshot()
    exp_cls = "ok" if ss['units'] <= 3 else "warn" if ss['units'] <= 6 else "lock"
    loss_cls = "ok" if bank['pl'] >= -3 else "warn" if bank['pl'] >= -7 else "lock"
    return f'''<section><div class="v19-section-head"><div><h2>Bankroll risk limits</h2><p>Hard operator reminders for daily discipline. These are display guardrails only; model logic remains unchanged.</p></div><span class="chip">Risk Rules</span></div><div class="bank-limit-grid"><div class="bank-limit-card {exp_cls}"><span>Slate Exposure</span><b>{ss['units']:.2f}u</b><p>Target comfort: under 3u. Elevated above 3u. Locked review above 6u.</p></div><div class="bank-limit-card {loss_cls}"><span>Loss Pressure</span><b>{bank['pl']:+.2f}u</b><p>Drawdown state should reduce automation confidence.</p></div><div class="bank-limit-card ok"><span>Single Bet Rule</span><b>Manual</b><p>Any larger stake requires human review before Telegram.</p></div><div class="bank-limit-card lock"><span>Automation Gate</span><b>Locked</b><p>No execution until approval and validation gates are satisfied.</p></div></div></section>'''

def hermes_pending_approvals():
    ss = slate_stats()
    return f'''<section><div class="v19-section-head"><div><h2>Pending approvals</h2><p>Hermes can prepare the queue, but the operator is the final gate.</p></div><span class="chip">Approval Desk</span></div><div class="hermes-approval-board"><div class="approval-card"><span>Action Queue</span><b>{ss['recommended']} items</b><p>Recommended bets require approve/reject review before Telegram preparation.</p></div><div class="approval-card"><span>Risk Queue</span><b>{ss['units']:.2f}u exposure</b><p>Bankroll and open-risk state must be accepted by the operator.</p></div><div class="approval-card injury-status"><span>Injury Queue</span><b>Feed pending</b><p>Injury integration is reserved and should block full automation until wired.</p></div></div></section>'''

def v19_dashboard():
    proj = read_csv(PROJECTIONS_CSV)
    stakes = read_csv(PROJECTIONS_STAKES_CSV)
    return f'''{command_center_hero(proj, stakes)}{v192_command_strip()}<section class="terminal-layout"><div class="terminal-stack">{v192_operator_brief()}<div class="v19-section-head"><div><h2>Today’s action board</h2><p>Review actions first. Each card now explains why, risk, and approval state.</p></div><a class="chip" href="/actions">Open Actions</a></div>{action_board(stakes, limit=5)}<div class="v19-section-head"><div><h2>Slate projection context</h2><p>Projection cards stay below the action review so the operator flow stays sharp.</p></div></div>{projection_cards(proj)}</div><aside class="terminal-stack">{risk_safety_panel()}{bank_limit_panel()}{environment_command_panel()}{model_health_panel()}{hermes_activity_feed()}</aside></section>'''


def bankroll_chart_payload(df):
    if df.empty:
        return {"labels": ["Start"], "equity": [100.0], "pl": [0.0]}
    data = normalize(df).copy()
    data["profit_loss"] = data.apply(calc_pl, axis=1)
    result = data.get("result", pd.Series([""] * len(data))).astype(str).str.upper()
    settled = data[~result.isin(["PENDING", "OPEN", ""])].copy()
    if settled.empty:
        return {"labels": ["Start"], "equity": [100.0], "pl": [0.0]}
    date_cols = [c for c in ["date", "game_date", "settled_at", "created_at", "timestamp"] if c in settled.columns]
    if date_cols:
        settled["_sort_date"] = pd.to_datetime(settled[date_cols[0]], errors="coerce")
        settled = settled.sort_values(["_sort_date"], na_position="last")
        labels = settled[date_cols[0]].astype(str).replace("nan", "Bet").tolist()
    else:
        settled = settled.reset_index(drop=True)
        labels = [f"Bet {i}" for i in range(1, len(settled) + 1)]
    pl_values = pd.to_numeric(settled["profit_loss"], errors="coerce").fillna(0).round(3).tolist()
    equity = []
    running = 100.0
    for v in pl_values:
        running += float(v)
        equity.append(round(running, 3))
    if len(labels) > 30:
        labels, equity, pl_values = labels[-30:], equity[-30:], pl_values[-30:]
    return {"labels": labels, "equity": equity, "pl": pl_values}

def bankroll_chart_panel(df, bank):
    payload = bankroll_chart_payload(df)
    labels = json.dumps(payload["labels"])
    equity = json.dumps(payload["equity"])
    pl = json.dumps(payload["pl"])
    if len(payload["labels"]) <= 1:
        return '''<section class="bankroll-chart-panel"><div class="bankroll-chart-head"><div><h2>Bankroll curve</h2><p>No settled bankroll history yet. The chart activates after bets are graded in the tracker.</p></div><a class="chip" href="/bets">Open tracker</a></div><div class="missing-smart">Waiting for settled bet history. Bankroll starts at 100.00u.</div></section>'''
    return f'''<section class="bankroll-chart-panel"><div class="bankroll-chart-head"><div><h2>Bankroll curve</h2><p>Clean performance view only. Full bet logs stay in Tracker so Bankroll does not duplicate every ticket.</p></div><a class="chip" href="/bets">Full tracker</a></div><div class="bankroll-chart-wrap"><canvas id="bankrollCurveChart"></canvas></div></section><script>
(function(){{
  var el = document.getElementById('bankrollCurveChart');
  if (!el || typeof Chart === 'undefined') return;
  new Chart(el, {{
    data: {{ labels: {labels}, datasets: [{{ type: 'line', label: 'Bankroll', data: {equity}, tension: .34, fill: true, pointRadius: 3, borderWidth: 2 }}, {{ type: 'bar', label: 'Bet P/L', data: {pl}, yAxisID: 'plAxis' }}] }},
    options: {{ responsive: true, maintainAspectRatio: false, interaction: {{ mode: 'index', intersect: false }}, plugins: {{ legend: {{ display: true }} }}, scales: {{ y: {{ title: {{ display: true, text: 'Bankroll units' }}, grid: {{ color: 'rgba(255,255,255,.055)' }} }}, plAxis: {{ position: 'right', title: {{ display: true, text: 'Bet P/L' }}, grid: {{ drawOnChartArea: false }} }}, x: {{ grid: {{ display: false }}, ticks: {{ maxTicksLimit: 8 }} }} }} }}
  }});
}})();
</script>'''

def bankroll_summary_panel(bank, ss):
    return f'''<section class="bankroll-summary-grid"><div class="bankroll-summary-card"><span>Automation Gate</span><b>Manual Approval</b><p>Hermes can warn and prepare. It cannot execute.</p></div><div class="bankroll-summary-card"><span>Exposure Check</span><b>{ss['units']:.2f}u</b><p>Current slate exposure from staking output.</p></div><div class="bankroll-summary-card"><span>Performance State</span><b>{bank['pl']:+.2f}u</b><p>Settled tracker P/L. Full ticket list is on Tracker.</p></div></section>'''

def v19_bankroll():
    bank = bankroll_snapshot(); ss = slate_stats(); df = load_bets()
    body = f'''<section class="bank-hero"><div class="bank-health"><div class="v19-eyebrow"><span class="pulse-ring"></span> Bankroll Control</div><h1>Fund discipline before bet volume.</h1><p class="v19-copy">Bankroll is the safety layer Hermes must respect. This page shows performance, exposure, drawdown, and guardrails — not a duplicate list of every bet.</p></div><div class="v19-panel"><span class="muted">Current Bankroll</span><div class="bank-number">{bank['current']:.2f}u</div><div class="mission-row"><span>P/L</span><b>{bank['pl']:+.2f}u</b><em>{bank['roi']:+.1f}% ROI</em></div><div class="mission-row"><span>Open Risk</span><b>{ss['units']:.2f}u slate</b><em>{bank['pending']} open</em></div></div></section><section class="bank-grid"><div class="bank-card"><span>Settled</span><b>{bank['settled']}</b><p>Graded bets in tracker.</p></div><div class="bank-card"><span>Wins / Losses</span><b>{bank['wins']} / {bank['losses']}</b><p>Closed ticket result count.</p></div><div class="bank-card"><span>Average Stake</span><b>{bank['avg_stake']:.2f}u</b><p>Average settled stake.</p></div><div class="bank-card"><span>Drawdown</span><b>{bank['drawdown']:.2f}u</b><p>Negative P/L pressure if any.</p></div></section>'''
    body += bankroll_chart_panel(df, bank)
    body += bankroll_summary_panel(bank, ss)
    body += bank_limit_panel()
    body += risk_safety_panel()
    return body

def v19_hermes():
    checks = [("Research Brain", DASHBOARD_INSIGHTS_TXT.exists() or INSIGHT_REPORT_CSV.exists()), ("Hermes Cycle", DAILY_RESEARCH_SNAPSHOT_JSON.exists()), ("Environment Memory", (OUTPUT_DIR / "environment_memory_latest.csv").exists()), ("Validation Engine", (OUTPUT_DIR / "environment_validation_summary.csv").exists()), ("Hypothesis Registry", (OUTPUT_DIR / "hypothesis_registry.csv").exists()), ("Telegram Output", TELEGRAM_TXT.exists()), ("Injury Feed", False)]
    rows = ''.join([f'<div class="hermes-status-row"><b>{n}</b><span class="{"ok" if ok else "warn"}">{"Online" if ok else "Pending"}</span></div>' for n,ok in checks])
    return f'''<main class="hermes-product"><section class="hermes-hero"><div class="web-eyebrow"><span class="pulse-ring"></span> Hermes Agent OS</div><h1>Automation with brakes, not shortcuts.</h1><p>Hermes is the operating agent for Edge Lab. Its job is to observe the slate, warn on risk, build the review queue, prepare outputs, and wait for approval. Bankroll, validation, injury status, and discipline locks are first-class gates.</p><div class="hermes-hero-actions"><a class="btn primary" href="/actions">Review Pending Actions</a><a class="btn" href="/bankroll">Bankroll Guardrails</a><a class="btn" href="/dashboard">Open Dashboard</a></div></section>{hermes_pending_approvals()}<section class="v19-workflow"><div class="workflow-step"><em>01</em><b>Observe</b><p>Read projections, staking, model health, research memory, bankroll, and environment state.</p></div><div class="workflow-step"><em>02</em><b>Warn</b><p>Flag missing files, bad regimes, overexposure, stale outputs, injury gaps, and drawdown risk.</p></div><div class="workflow-step"><em>03</em><b>Recommend</b><p>Create a review queue. Recommendations are not execution commands.</p></div><div class="workflow-step"><em>04</em><b>Approve</b><p>Operator approval remains mandatory before Telegram preparation or execution workflows.</p></div></section><section class="hermes-state"><div class="web-preview"><h3>System readiness</h3><p>Hermes component map for the automation path.</p><div class="hermes-status-list">{rows}</div></div><div class="web-preview"><h3>Automation modes</h3><p>Current mode is intentionally conservative.</p><div class="hermes-ladder"><div class="hermes-step active"><span>L0</span><b>Manual dashboard</b><em>Active</em></div><div class="hermes-step active"><span>L1</span><b>Mission brief</b><em>Ready</em></div><div class="hermes-step active"><span>L2</span><b>Alerts and warnings</b><em>Ready</em></div><div class="hermes-step locked"><span>L3</span><b>Suggested actions</b><em>Guarded</em></div><div class="hermes-step locked"><span>L4</span><b>Telegram preparation</b><em>Approval</em></div><div class="hermes-step locked"><span>L5</span><b>Workflow execution</b><em>Locked</em></div><div class="hermes-step locked"><span>L6</span><b>Full automation</b><em>Locked</em></div></div></div></section>{risk_safety_panel()}</main>'''

def v19_menu():
    items = [("Dashboard", "/dashboard", "Primary operator terminal and mission control."), ("Bankroll", "/bankroll", "Fund control, bankroll curve, exposure, and guardrails."), ("Actions", "/actions", "Recommended bets, pass states, and approval context."), ("Environment", "/environment", "Bucket, regime, chaos, trust, and validation desk."), ("Research", "/research", "Research memory, insight reports, and learning state."), ("Memory", "/memory", "Daily snapshots and trend notes."), ("Validation", "/validation", "Signal results, CLV, and model health validation."), ("Diagnostics", "/diagnostics", "Projection diagnostics and data integrity checks."), ("Tracker", "/bets", "Full bet log and settled ticket history."), ("Telegram", "/telegram", "Telegram-ready operator output."), ("History", "/history", "Projection history and slate archive."), ("Teams", "/rankings", "Team profiles and ratings."), ("Analysis", "/analysis", "Post-result analysis by signal and odds bucket."), ("Intelligence", "/intelligence", "Research brain and insight engine.")]
    primary = {"Dashboard", "Bankroll", "Actions", "Environment"}
    cards=''.join([f'<a class="deep-menu-card {"primary-route" if name in primary else ""}" href="{href}"><span>{"Core Desk" if name in primary else "Lab Route"}</span><b>{name}</b><p>{desc}</p></a>' for name,href,desc in items])
    return f'<div class="v19-section-head"><div><h2>Full lab menu</h2><p>Every route is accessible here. The top navigation stays clean and the Menu link now opens this page directly.</p></div><span class="chip">Menu</span></div><div class="deep-menu-grid">{cards}</div>'
@app.route("/")
def index():
    return page("Home", v19_home())

@app.route("/dashboard")
def dashboard():
    return page("Dashboard", v19_dashboard())

@app.route("/bankroll")
def bankroll():
    return page("Bankroll", v19_bankroll())

@app.route("/actions")
def actions():
    df = read_csv(PROJECTIONS_STAKES_CSV)
    norm = normalize(df)
    ss = slate_stats()
    body = f'''<section class="metrics">{metric_card("Recommended", ss['recommended'], "bets > 0 units")}{metric_card("Total Units", f"{ss['units']:.2f}u", "slate exposure")}{metric_card("Stake", f"{ss['stake']:.2f}", "currency units")}{metric_card("Approval", "Manual", "Hermes locked")}</section>
    <div class="v19-section-head"><div><h2>Actions desk</h2><p>Recommended bets, pass states, risk context, why-this-bet notes, and approval state.</p></div><span class="chip">Manual Approval</span></div>
    {action_board(norm, limit=20)}
    <div class="v19-section-head"><div><h2>Audit path</h2><p>Raw staking data stays available without duplicating it into the main review flow.</p></div><a class="chip" href="/telegram">Telegram Output</a></div>
    <div class="v19-panel"><div class="mission-row"><span>Raw Table</span><b>Hidden from primary workflow</b><em>Cleaner</em></div><div class="mission-row"><span>Debug</span><b>Use Diagnostics / Validation / Tracker for deep audit</b><em>Available</em></div><div class="mission-row"><span>Rule</span><b>Do not approve without bankroll, environment, and injury check</b><em>Manual</em></div></div>'''
    return page("Actions", body)

@app.route("/stake")
def stake_redirect():
    return redirect("/actions")

@app.route("/stakes")
def stakes():
    return redirect("/actions")

@app.route("/menu")
def menu():
    return page("Menu", v19_menu())

@app.route("/rankings")
def rankings():
    df=read_csv(RANKINGS_CSV)
    body='<div class="section-head"><div><h2>Team Profiles</h2><p>Rating cards with actual values and relative bars.</p></div><div class="toolbar"><span class="chip">Pace</span><span class="chip">Off Rating</span><span class="chip">Def Rating</span></div></div>' + team_cards(df)
    return page("Teams", body)


def history_cards(df):
    if df.empty:
        return '<div class="panel empty">No projection history found. Run projection_history_v3.py first.</div>'

    data = normalize(df)

    # Keep only rows that have real games when possible.
    if "game" in data.columns:
        valid = data[data["game"].notna() & (data["game"].astype(str).str.lower() != "nan")].copy()
        if not valid.empty:
            data = valid

    # Latest run only for the card board.
    latest_run = None
    if "runtimestamp" in data.columns:
        latest_run = data["runtimestamp"].max()
        latest = data[data["runtimestamp"] == latest_run].copy()
    else:
        latest = data.copy()

    cards = []
    if "edge" in latest.columns:
        latest["_edge_num"] = latest["edge"].apply(safe_float)
    else:
        latest["_edge_num"] = 0

    sig_col = "finalsignal" if "finalsignal" in latest.columns else "final_signal" if "final_signal" in latest.columns else None
    if sig_col:
        latest["_is_signal"] = (~latest[sig_col].fillna("PASS").astype(str).str.upper().eq("PASS")).astype(int)
    else:
        latest["_is_signal"] = 0

    unit_col = "suggestedunits" if "suggestedunits" in latest.columns else "suggested_units" if "suggested_units" in latest.columns else None
    if unit_col:
        latest["_units_num"] = latest[unit_col].apply(safe_float)
    else:
        latest["_units_num"] = 0

    latest = latest.sort_values(["_is_signal", "_units_num", "_edge_num"], ascending=[False, False, False])

    for _, r in latest.iterrows():
        game = r.get("game", "")
        line = r.get("line", "")
        proj = r.get("projection", "")
        edge = safe_float(r.get("edge", 0))
        conf = safe_float(r.get("confidence", 0))
        signal = r.get("finalsignal", r.get("final_signal", ""))
        units = safe_float(r.get("suggestedunits", r.get("suggested_units", 0)))
        stake = safe_float(r.get("suggestedstake", r.get("suggested_stake", 0)))
        run = r.get("runtimestamp", "")
        edge_cls = "positive" if edge > 0 else "negative" if edge < 0 else "neutral"

        cards.append(f"""
        <div class="game-card" data-signal-card="{signal}" data-units="{units}">
          <div class="game-top">
            <div>
              <div class="game-title">{game}</div>
              <div class="game-sub">Run {run} - Line {line}</div>
            </div>
            {signal_badge(signal)}
          </div>
          <div class="edge-row">
            <div class="mini"><span>Projection</span><b>{fmt(proj,1)}</b></div>
            <div class="mini"><span>Edge</span><b class="{edge_cls}">{edge:+.1f}</b></div>
            <div class="mini"><span>Confidence</span><b>{fmt(conf,0)}</b></div>
          </div>
          <div class="details">
            <div class="detail">Suggested Units<b>{units:.2f}u</b></div>
            <div class="detail">Suggested Stake<b>{stake:.2f}</b></div>
          </div>
        </div>
        """)

    return '<div class="cards">' + "".join(cards) + '</div>'


@app.route("/history")
def history():
    df = read_csv(HISTORY_CSV)
    if df.empty:
        return page("History", '<div class="panel empty">No projection_history.csv found. Run projection_history_v3.py first.</div>')

    norm = normalize(df)

    # Prefer rows with real game names for analytics.
    if "game" in norm.columns:
        valid = norm[norm["game"].notna() & (norm["game"].astype(str).str.lower() != "nan")].copy()
    else:
        valid = norm.copy()

    if valid.empty:
        valid = norm.copy()

    runs = valid["runtimestamp"].nunique() if "runtimestamp" in valid.columns else 0
    rows = len(valid)
    avg_edge = valid["edge"].apply(safe_float).mean() if "edge" in valid.columns else 0
    max_edge = valid["edge"].apply(safe_float).max() if "edge" in valid.columns else 0
    latest_run = valid["runtimestamp"].max() if "runtimestamp" in valid.columns else ""

    signal_col = "finalsignal" if "finalsignal" in valid.columns else "final_signal" if "final_signal" in valid.columns else None
    signal_count = 0
    if signal_col:
        sigs = valid[signal_col].fillna("PASS").astype(str).str.upper()
        signal_count = (~sigs.eq("PASS")).sum()

    body = f"""
    <section class="metrics">
      {metric_card("Runs", runs, "model snapshots")}
      {metric_card("Rows", rows, "valid projections")}
      {metric_card("Avg Edge", f"{avg_edge:+.1f}", "points")}
      {metric_card("Max Edge", f"{max_edge:+.1f}", "top edge")}
      {metric_card("Signals", signal_count, "non-pass rows")}
      {metric_card("Latest", latest_run[-8:] if latest_run else "-", "run time")}
    </section>
    <div class="section-head">
      <div><h2>Latest Run History</h2><p>Latest saved model run, signals first, sorted by edge.</p></div>
      <div class="toolbar"><span class="chip">Projection archive</span><span class="chip">Validation base</span></div>
    </div>
    <div class="filter-row">
      <button class="filter-btn active" data-filter="all" onclick="filterCards('all')">All</button>
      <button class="filter-btn" data-filter="signals" onclick="filterCards('signals')">Signals Only</button>
      <button class="filter-btn" data-filter="recommended" onclick="filterCards('recommended')">Staked Only</button>
    </div>
    {history_cards(valid)}
    """

    signal_col_for_group = "finalsignal" if "finalsignal" in valid.columns else "final_signal" if "final_signal" in valid.columns else None
    if signal_col_for_group:
        grouped = valid.groupby(signal_col_for_group).agg(
            rows=(signal_col_for_group, "count"),
            avg_edge=("edge", lambda s: pd.to_numeric(s, errors="coerce").mean()),
            avg_confidence=("confidence", lambda s: pd.to_numeric(s, errors="coerce").mean()),
        ).reset_index().rename(columns={signal_col_for_group: "signal"})
        body += '<div class="section-head"><div><h2>Signal Summary</h2><p>Stored history grouped by final signal.</p></div></div>'
        body += '<div class="panel">' + table(grouped, max_rows=50) + '</div>'

    return page("History", body)



@app.route("/telegram")
def telegram():
    text=TELEGRAM_TXT.read_text(encoding="utf-8", errors="ignore") if TELEGRAM_TXT.exists() else "No telegram_message.txt found."
    return page("Telegram", f'<div class="section-head"><div><h2>Telegram Preview</h2><p>Copy-ready alert text.</p></div></div><div class="panel"><pre>{text}</pre></div>')


def analysis_metric_rows(summary, group_name):
    if summary.empty:
        return pd.DataFrame()
    data = normalize(summary)
    if "group" not in data.columns:
        return pd.DataFrame()
    return data[data["group"].astype(str).str.upper() == group_name.upper()].copy()


def analysis_cards(df, title, empty_text="No data."):
    if df.empty:
        return f'<div class="panel empty">{empty_text}</div>'

    # Sort best first by P_L if available
    if "p_l" in df.columns:
        df = df.copy()
        df["_pl_num"] = df["p_l"].apply(safe_float)
        df = df.sort_values("_pl_num", ascending=False)
    elif "roi" in df.columns:
        df = df.copy()
        df["_roi_num"] = df["roi"].apply(safe_float)
        df = df.sort_values("_roi_num", ascending=False)

    cards = []
    for _, r in df.iterrows():
        name = r.get("name", "")
        bets = r.get("bets", "")
        wins = r.get("wins", "")
        losses = r.get("losses", "")
        roi = safe_float(r.get("roi", 0))
        pl = safe_float(r.get("p_l", 0))
        wr = safe_float(r.get("winrate", r.get("win_rate", 0)))
        cls = "positive" if pl >= 0 else "negative"
        label = "KEEP STUDYING" if pl > 0 else "CAUTION"

        cards.append(f"""
        <div class="game-card">
          <div class="game-top">
            <div>
              <div class="game-title">{name}</div>
              <div class="game-sub">{wins}-{losses} - {bets} bets - WR {wr:.1f}%</div>
            </div>
            {signal_badge(label)}
          </div>
          <div class="edge-row">
            <div class="mini"><span>P/L</span><b class="{cls}">{pl:+.2f}u</b></div>
            <div class="mini"><span>ROI</span><b class="{cls}">{roi:+.1f}%</b></div>
            <div class="mini"><span>Bets</span><b>{bets}</b></div>
          </div>
        </div>
        """)
    return '<div class="cards">' + "".join(cards) + '</div>'



def diag_class(label):
    s = str(label).upper()
    if "POSITIVE" in s:
        return "positive"
    if "NEGATIVE" in s:
        return "negative"
    return "neutral"


def diagnostic_cards(df):
    if df.empty:
        return '<div class="panel empty">No diagnostics found. Run diagnostic_layer_v1.py first.</div>'

    data = normalize(df)

    # Sort by signals first, then edge.
    if "edge" in data.columns:
        data["_edge_num"] = data["edge"].apply(safe_float)
    else:
        data["_edge_num"] = 0

    signal_col = "finalsignalnormalized" if "finalsignalnormalized" in data.columns else "signal" if "signal" in data.columns else None
    if signal_col:
        data["_is_signal"] = (~data[signal_col].fillna("PASS").astype(str).str.upper().eq("PASS")).astype(int)
    else:
        data["_is_signal"] = 0

    data = data.sort_values(["_is_signal", "_edge_num"], ascending=[False, False])

    cards = []
    for _, r in data.iterrows():
        game = r.get("game", "")
        line = r.get("market_line", r.get("line", ""))
        proj = r.get("projection", "")
        edge = safe_float(r.get("edge", 0))
        signal = r.get("finalsignalnormalized", r.get("signal", ""))
        summary = r.get("diagnostic_summary", "")
        edge_cls = "positive" if edge > 0 else "negative" if edge < 0 else "neutral"

        drivers = [
            ("Pace", r.get("pace_diag", "NEUTRAL")),
            ("Offense", r.get("offense_diag", "NEUTRAL")),
            ("Defense", r.get("defense_diag", "NEUTRAL")),
            ("eFG", r.get("efg_diag", "NEUTRAL")),
            ("TOV", r.get("tov_diag", "NEUTRAL")),
            ("OREB", r.get("oreb_diag", "NEUTRAL")),
            ("FTA", r.get("fta_diag", "NEUTRAL")),
        ]

        driver_html = ""
        for name, val in drivers:
            driver_html += f'<div class="driver {diag_class(val)}"><span>{name}</span><b>{val}</b></div>'

        cards.append(f"""
        <div class="game-card">
          <div class="game-top">
            <div>
              <div class="game-title">{game}</div>
              <div class="game-sub">Line {line} - Projection {fmt(proj,1)}</div>
            </div>
            {signal_badge(signal)}
          </div>
          <div class="edge-row">
            <div class="mini"><span>Edge</span><b class="{edge_cls}">{edge:+.1f}</b></div>
            <div class="mini"><span>Market</span><b>{line}</b></div>
            <div class="mini"><span>Projection</span><b>{fmt(proj,1)}</b></div>
          </div>
          <div class="driver-grid">{driver_html}</div>
          <div class="summary-box">{summary}</div>
        </div>
        """)
    return '<div class="cards">' + "".join(cards) + '</div>'




def first_existing_col(df, names):
    if df is None or df.empty:
        return None
    cols = {str(c).lower(): c for c in df.columns}
    for n in names:
        if str(n).lower() in cols:
            return cols[str(n).lower()]
    return None

def safe_series(df, names, default=""):
    c = first_existing_col(df, names)
    if c is None:
        return pd.Series([default] * len(df), index=df.index)
    return df[c]

def validation_health_cards(clv_summary, result_summary, graded):
    beat_rate = 0.0
    avg_clv = 0.0
    clv_count = 0

    if not clv_summary.empty:
        clv = normalize(clv_summary)
        group_col = first_existing_col(clv, ["group"])
        if group_col:
            overall = clv[clv[group_col].astype(str).str.upper().eq("OVERALL")]
            if not overall.empty:
                r = overall.iloc[0]
                beat_rate = safe_float(r.get(first_existing_col(clv, ["beatcloserate"]) or "beatcloserate", 0), 0) or 0
                avg_clv = safe_float(r.get(first_existing_col(clv, ["avgclvpoints"]) or "avgclvpoints", 0), 0) or 0
                clv_count = int(safe_float(r.get(first_existing_col(clv, ["signalswithclv"]) or "signalswithclv", 0), 0) or 0)

    win_rate = 0.0
    graded_count = 0

    if not result_summary.empty:
        res = normalize(result_summary)
        group_col = first_existing_col(res, ["group"])
        if group_col:
            overall = res[res[group_col].astype(str).str.upper().eq("OVERALL")]
            if not overall.empty:
                r = overall.iloc[0]
                win_rate = safe_float(r.get(first_existing_col(res, ["winrate"]) or "winrate", 0), 0) or 0
                graded_count = int(safe_float(r.get(first_existing_col(res, ["signals"]) or "signals", 0), 0) or 0)

    open_count = 0
    if not graded.empty:
        g = normalize(graded)
        status_col = first_existing_col(g, ["resultstatus", "result_status"])
        if status_col:
            open_count = int((g[status_col].astype(str).str.upper() != "GRADED").sum())
        else:
            open_count = len(g)

    beat_w = max(5, min(100, beat_rate))
    win_w = max(5, min(100, win_rate))
    clv_w = max(5, min(100, 50 + avg_clv * 10))

    return f"""
    <section class="validation-grid">
      <div class="health-card">
        <h3><span class="pulse-ring"></span>Beat Close Rate</h3>
        <div class="mega {'positive' if beat_rate >= 50 else 'negative'}">{beat_rate:.1f}%</div>
        <div class="caption">{clv_count} model signals with automated CLV</div>
        <div class="sparkline"><div style="--w:{beat_w}%"></div></div>
      </div>
      <div class="health-card">
        <h3><span class="pulse-ring {'red' if avg_clv < 0 else ''}"></span>Average CLV</h3>
        <div class="mega {'positive' if avg_clv >= 0 else 'negative'}">{avg_clv:+.2f}</div>
        <div class="caption">Average closing-line value in points</div>
        <div class="sparkline"><div style="--w:{clv_w}%"></div></div>
      </div>
      <div class="health-card">
        <h3><span class="pulse-ring {'yellow' if graded_count < 20 else ''}"></span>Signal Win Rate</h3>
        <div class="mega {'positive' if win_rate >= 52 else 'negative'}">{win_rate:.1f}%</div>
        <div class="caption">{graded_count} graded model signals</div>
        <div class="sparkline"><div style="--w:{win_w}%"></div></div>
      </div>
      <div class="health-card">
        <h3>Open Signals</h3>
        <div class="mega">{open_count}</div>
        <div class="caption">Signals still waiting for final result</div>
        <div class="sparkline"><div style="--w:{max(5,min(100,open_count*10))}%"></div></div>
      </div>
    </section>
    """

def validation_signal_cards(df):
    if df.empty:
        return '<div class="panel empty">No signal validation rows yet.</div>'

    data = normalize(df)
    cards = []

    def pick(row, *names, default=""):
        for name in names:
            if name in row:
                value = row.get(name)
                if not pd.isna(value) and str(value).lower() != "nan":
                    return value
        return default

    def val_class(value):
        try:
            v = float(value)
        except Exception:
            return ""
        if v > 0:
            return "pos"
        if v < 0:
            return "neg"
        return ""

    for _, row in data.head(80).iterrows():
        game = pick(row, "game", "Game", default="Unknown Game")

        direction = str(pick(row, "direction", "Direction", "selection", "Selection", default="")).upper()
        line = pick(row, "line", "Line", "signalline", "SignalLine", default="")
        final_signal = pick(row, "finalsignal", "FinalSignal", "finalsignalnormalized", "FinalSignalNormalized", default="")

        edge = safe_float(pick(row, "edge", "Edge", default=0), 0)
        close = pick(row, "closingline", "ClosingLine", "close", "Close", default="")
        clv = safe_float(
            pick(row, "clv_points_clean", "CLV_Points_Clean", "clv_points", "CLV_Points", "clv", "CLV", default=0),
            0,
        )

        beat_close = pick(row, "beatclose", "BeatClose", default="")
        validation_grade = pick(
            row,
            "validationgrade",
            "ValidationGrade",
            "wouldhavewon",
            "WouldHaveWon",
            "result",
            "Result",
            default="",
        )

        grade = validation_grade or beat_close or "NAN"
        grade = str(grade).upper()
        if grade in ["", "NAN", "NONE", "<NA>"]:
            grade = "NAN"

        final_total = pick(
            row,
            "finaltotal",
            "FinalTotal",
            "final_total",
            "GameTotal",
            "gametotal",
            "actual",
            "Actual",
            "final",
            "Final",
            default="",
        )

        confidence = pick(row, "confidence", "Confidence", default="")
        signal_line = f"{direction} {line}".strip()

        if final_total == "":
            final_total_html = '<span class="muted">Open / not graded</span>'
        else:
            final_total_html = final_total

        grade_class = "win" if grade == "WIN" else "loss" if grade == "LOSS" else "push" if grade == "PUSH" else "pass"

        cards.append(f"""
        <div class="pick-card">
          <div class="pick-top">
            <div>
              <h3>{game}</h3>
              <p>{signal_line} - {final_signal}</p>
            </div>
            <span class="badge {grade_class}">{grade}</span>
          </div>

          <div class="mini-grid">
            <div class="mini"><span>Edge</span><b class="{val_class(edge)}">{edge:+.1f}</b></div>
            <div class="mini"><span>Close</span><b>{close}</b></div>
            <div class="mini"><span>CLV</span><b class="{val_class(clv)}">{clv:+.2f}</b></div>
            <div class="mini"><span>Beat Close</span><b>{beat_close if beat_close else "-"}</b></div>
          </div>

          <div class="mini wide"><span>Signal Line</span><b>{signal_line}</b></div>
          <div class="mini wide"><span>Final Total</span><b>{final_total_html}</b><p>Confidence {confidence}</p></div>
        </div>
        """)

    return "".join(cards)


def validation_summary_section(title, df, group_prefix):
    if df.empty:
        return ""
    data = normalize(df)
    group_col = first_existing_col(data, ["group"])
    if not group_col:
        return ""
    subset = data[data[group_col].astype(str).str.upper().str.startswith(group_prefix.upper())].copy()
    if subset.empty:
        return ""
    return f'<div class="section-head"><div><h2>{title}</h2><p>Validation grouped by {group_prefix.lower()}.</p></div></div><div class="panel">{table(subset, max_rows=80)}</div>'



def read_text_safe(path):
    try:
        if not path.exists() or path.stat().st_size == 0:
            return ""
        return path.read_text(encoding="utf-8")
    except Exception:
        return ""

def latest_health_dict():
    df = read_csv(MODEL_HEALTH_CSV)
    if df.empty:
        return {}
    return normalize(df).iloc[-1].to_dict()

def count_rows(path):
    df = read_csv(path)
    return 0 if df.empty else len(df)

def live_status_strip():
    health = latest_health_dict()
    label = str(health.get("healthlabel", health.get("HealthLabel", "NO HEALTH"))).upper()
    color = str(health.get("healthcolor", health.get("HealthColor", "YELLOW"))).upper()
    dot = "red" if color == "RED" else "yellow" if color in ["YELLOW", "ORANGE"] else ""

    projection_ok = "OK" if PROJECTIONS_CSV.exists() else "MISSING"
    diag_ok = "OK" if DIAGNOSTICS_CSV.exists() else "MISSING"
    clv_ok = "UPDATED" if SIGNAL_WITH_CLV_CSV.exists() else "PENDING"
    graded_ok = "GRADED" if SIGNAL_GRADED_CSV.exists() else "PENDING"
    insights_n = count_rows(INSIGHT_REPORT_CSV)

    return f"""
    <div class="live-strip">
      <div class="status-pill"><span class="status-dot"></span>MODEL {projection_ok}</div>
      <div class="status-pill"><span class="status-dot"></span>DIAGNOSTICS {diag_ok}</div>
      <div class="status-pill"><span class="status-dot {'yellow' if clv_ok == 'PENDING' else ''}"></span>CLV {clv_ok}</div>
      <div class="status-pill"><span class="status-dot {'yellow' if graded_ok == 'PENDING' else ''}"></span>RESULTS {graded_ok}</div>
      <div class="status-pill"><span class="status-dot {dot}"></span>HEALTH {label}</div>
      <div class="status-pill"><span class="status-dot {'yellow' if insights_n < 3 else ''}"></span>INSIGHTS {insights_n}</div>
    </div>
    """

def insight_cards(limit=6):
    df = read_csv(INSIGHT_REPORT_CSV)
    if df.empty:
        return '<div class="panel empty">No insights yet. Run insight_engine_v1.py.</div>'

    data = normalize(df).head(limit)
    cards = []
    for _, r in data.iterrows():
        conf = str(r.get("confidence", r.get("Confidence", "LOW"))).upper()
        klass = conf.lower().replace(" ", "-")
        title = r.get("title", r.get("Title", "Insight"))
        detail = r.get("detail", r.get("Detail", ""))
        sample = r.get("samplesize", r.get("SampleSize", ""))
        effect = r.get("effect", r.get("Effect", ""))
        action = r.get("action", r.get("Action", "Observe only"))
        category = r.get("category", r.get("Category", "Research"))

        cards.append(f"""
        <div class="insight-card {klass}">
          <div class="insight-top">
            <div>
              <div class="insight-title">{title}</div>
              <div class="game-sub">{category} - sample {sample} - effect {effect}</div>
            </div>
            <span class="conf-badge {klass}">{conf}</span>
          </div>
          <div class="insight-detail">{detail}</div>
          <div class="insight-action"><b>Action:</b> {action}</div>
        </div>
        """)
    return '<div class="insight-feed">' + "".join(cards) + '</div>'

def intelligence_hero():
    health = latest_health_dict()
    score = safe_float(health.get("modelhealthscore", health.get("ModelHealthScore", 0)), 0)
    label = health.get("healthlabel", health.get("HealthLabel", "UNKNOWN"))
    sample = health.get("samplesize", health.get("SampleSize", ""))
    avg_clv = safe_float(health.get("avgclv", health.get("AvgCLV", 0)), 0)
    beat = safe_float(health.get("beatcloserate", health.get("BeatCloseRate", 0)), 0)
    wr = safe_float(health.get("signalwinrate", health.get("SignalWinRate", 0)), 0)
    insights_n = count_rows(INSIGHT_REPORT_CSV)

    return f"""
    <div class="intelligence-hero">
      <div class="brain-panel">
        <div class="float-orb"></div>
        <div class="brain-kicker"><span class="status-dot yellow"></span>Research Intelligence</div>
        <div class="brain-title">WNBA Edge Lab Intelligence Terminal</div>
        <div class="brain-copy">
          Closed-loop research layer combining model health, signal validation, CLV, result grading, diagnostics, and sample-aware insights. Formula remains frozen while the system learns.
        </div>
        <div class="intel-grid">
          <div class="intel-stat"><span>Health Score</span><b>{score:.1f}/100</b></div>
          <div class="intel-stat"><span>State</span><b>{label}</b></div>
          <div class="intel-stat"><span>Tracked Sample</span><b>{sample}</b></div>
          <div class="intel-stat"><span>Insights</span><b>{insights_n}</b></div>
          <div class="intel-stat"><span>Avg CLV</span><b>{avg_clv:+.2f}</b></div>
          <div class="intel-stat"><span>Beat Close</span><b>{beat:.1f}%</b></div>
          <div class="intel-stat"><span>Signal WR</span><b>{wr:.1f}%</b></div>
          <div class="intel-stat"><span>Formula</span><b>Frozen</b></div>
        </div>
      </div>
      <div>{insight_cards(limit=3)}</div>
    </div>
    """

def intelligence_console():
    txt = read_text_safe(DASHBOARD_INSIGHTS_TXT)
    if not txt:
        txt = "No dashboard insights yet. Run insight_engine_v1.py."
    return f"""
    <div class="research-console">
      <div class="console-head"><b>Research Console</b><span class="chip">Insight Engine v1</span></div>
      <div class="console-body">{txt}</div>
    </div>
    """


def model_health_panel():
    health = read_csv(MODEL_HEALTH_CSV)
    if health.empty:
        return """
        <div class="health-hero">
          <div class="gauge" style="--score:0;--gauge-color:var(--muted2)">
            <div class="gauge-inner"><div class="gauge-score">--</div><div class="gauge-label">No Data</div></div>
          </div>
          <div class="health-info">
            <h2>Model Health Not Available</h2>
            <p>Run <b>model_health_engine_v1_1.py</b> after the validation pipeline to generate the model health report.</p>
          </div>
        </div>
        """

    h = normalize(health).iloc[-1]
    score = safe_float(h.get("modelhealthscore", h.get("ModelHealthScore", 0)), 0) or 0
    label = h.get("healthlabel", h.get("HealthLabel", "UNKNOWN"))
    color = str(h.get("healthcolor", h.get("HealthColor", "YELLOW"))).upper()
    sample = h.get("samplesize", h.get("SampleSize", ""))
    warning = h.get("samplewarning", h.get("SampleWarning", ""))
    avg_clv = safe_float(h.get("avgclv", h.get("AvgCLV", 0)), 0) or 0
    beat = safe_float(h.get("beatcloserate", h.get("BeatCloseRate", 0)), 0) or 0
    wr = safe_float(h.get("signalwinrate", h.get("SignalWinRate", 0)), 0) or 0

    clv_score = safe_float(h.get("clvqualityscore", h.get("CLVQualityScore", 0)), 0) or 0
    beat_score = safe_float(h.get("beatclosescore", h.get("BeatCloseScore", 0)), 0) or 0
    win_score = safe_float(h.get("winratescore", h.get("WinRateScore", 0)), 0) or 0
    recent_score = safe_float(h.get("recentformscore", h.get("RecentFormScore", 0)), 0) or 0
    sample_score = safe_float(h.get("samplereliabilityscore", h.get("SampleReliabilityScore", 0)), 0) or 0

    gauge_color = "var(--green)"
    if color == "RED":
        gauge_color = "var(--red)"
    elif color == "ORANGE":
        gauge_color = "var(--orange)"
    elif color == "YELLOW":
        gauge_color = "var(--yellow)"

    sample_note = "Low sample - learning mode" if str(warning).upper() == "LOW SAMPLE" else "Sample reliability active"

    return f"""
    <div class="health-hero">
      <div class="gauge" style="--score:{max(0,min(100,score))};--gauge-color:{gauge_color}">
        <div class="gauge-inner">
          <div class="gauge-score">{score:.1f}</div>
          <div class="gauge-label">{label}</div>
        </div>
      </div>
      <div class="health-info">
        <h2>Model Health - {label}</h2>
        <p>{sample_note}. Formula status remains <b>FROZEN</b>. Health evaluates the model; it does not change projections, signals, or stakes.</p>
        <div class="component-grid">
          <div class="component"><span>CLV Quality</span><b>{clv_score:.1f}</b></div>
          <div class="component"><span>Beat Close</span><b>{beat_score:.1f}</b></div>
          <div class="component"><span>Win Rate</span><b>{win_score:.1f}</b></div>
          <div class="component"><span>Recent Form</span><b>{recent_score:.1f}</b></div>
          <div class="component"><span>Sample</span><b>{sample_score:.1f}</b></div>
        </div>
        <p>Raw: Avg CLV {avg_clv:+.2f} - Beat Close {beat:.1f}% - Signal WR {wr:.1f}% - Sample {sample}</p>
      </div>
    </div>
    """





def research_data_payload():
    timeline = read_csv(MODEL_HEALTH_TIMELINE_CSV)
    timeline = normalize(timeline) if not timeline.empty else pd.DataFrame()

    graded = read_csv(SIGNAL_GRADED_CSV)
    graded = normalize(graded) if not graded.empty else pd.DataFrame()

    with_clv = read_csv(SIGNAL_WITH_CLV_CSV)
    with_clv = normalize(with_clv) if not with_clv.empty else pd.DataFrame()

    labels = []
    health_scores = []
    sample_sizes = []

    if not timeline.empty:
        time_col = "runtimestamp" if "runtimestamp" in timeline.columns else "RunTimestamp" if "RunTimestamp" in timeline.columns else None
        score_col = "modelhealthscore" if "modelhealthscore" in timeline.columns else "ModelHealthScore" if "ModelHealthScore" in timeline.columns else None
        sample_col = "samplesize" if "samplesize" in timeline.columns else "SampleSize" if "SampleSize" in timeline.columns else None

        if time_col:
            labels = [str(x)[5:16] for x in timeline[time_col].tail(30).tolist()]
        if score_col:
            health_scores = [safe_float(x, 0) for x in timeline[score_col].tail(30).tolist()]
        if sample_col:
            sample_sizes = [safe_float(x, 0) for x in timeline[sample_col].tail(30).tolist()]

    clv_values = []
    if not with_clv.empty:
        clv_col = "clv_points" if "clv_points" in with_clv.columns else "CLV_Points" if "CLV_Points" in with_clv.columns else None
        if clv_col:
            clv_values = [safe_float(x, None) for x in with_clv[clv_col].tolist()]
            clv_values = [x for x in clv_values if x is not None]

    buckets = ["<-3", "-3:-1", "-1:0", "0:1", "1:3", "3+"]
    bucket_counts = [0,0,0,0,0,0]
    for v in clv_values:
        if v < -3: bucket_counts[0] += 1
        elif v < -1: bucket_counts[1] += 1
        elif v < 0: bucket_counts[2] += 1
        elif v < 1: bucket_counts[3] += 1
        elif v < 3: bucket_counts[4] += 1
        else: bucket_counts[5] += 1

    conf_labels = ["<40","40-49","50-59","60-69","70+"]
    conf_counts = [0,0,0,0,0]
    conf_wr = [0,0,0,0,0]

    if not graded.empty:
        conf_col = "confidence" if "confidence" in graded.columns else "Confidence" if "Confidence" in graded.columns else None
        result_col = "wouldhavewon" if "wouldhavewon" in graded.columns else "WouldHaveWon" if "WouldHaveWon" in graded.columns else None

        if conf_col:
            for _, row in graded.iterrows():
                c = safe_float(row.get(conf_col), None)
                if c is None:
                    continue
                idx = 0 if c < 40 else 1 if c < 50 else 2 if c < 60 else 3 if c < 70 else 4
                conf_counts[idx] += 1

            if result_col:
                for bidx in range(5):
                    wins = losses = 0
                    for _, row in graded.iterrows():
                        c = safe_float(row.get(conf_col), None)
                        if c is None:
                            continue
                        idx = 0 if c < 40 else 1 if c < 50 else 2 if c < 60 else 3 if c < 70 else 4
                        if idx != bidx:
                            continue
                        res = str(row.get(result_col, "")).upper()
                        if res == "WIN": wins += 1
                        elif res == "LOSS": losses += 1
                    conf_wr[bidx] = round((wins / (wins + losses) * 100), 1) if wins + losses else 0

    return {
        "health_labels": labels,
        "health_scores": health_scores,
        "sample_sizes": sample_sizes,
        "clv_buckets": buckets,
        "clv_counts": bucket_counts,
        "conf_labels": conf_labels,
        "conf_counts": conf_counts,
        "conf_wr": conf_wr,
        "total_clv": len(clv_values),
        "total_health": len(health_scores),
        "total_graded": len(graded) if not graded.empty else 0,
    }

def research_metrics_html(payload):
    latest_health = payload["health_scores"][-1] if payload["health_scores"] else 0
    prev_health = payload["health_scores"][-2] if len(payload["health_scores"]) >= 2 else latest_health
    delta = latest_health - prev_health
    latest_sample = payload["sample_sizes"][-1] if payload["sample_sizes"] else 0
    total_clv = payload["total_clv"]
    total_graded = payload["total_graded"]

    return f"""
    <div class="research-metrics">
      <div class="research-metric"><span>Health</span><b>{latest_health:.1f}</b><small>{delta:+.1f} vs previous</small></div>
      <div class="research-metric"><span>Sample</span><b>{latest_sample:.0f}</b><small>validation credibility</small></div>
      <div class="research-metric"><span>CLV Rows</span><b>{total_clv}</b><small>market agreement samples</small></div>
      <div class="research-metric"><span>Graded</span><b>{total_graded}</b><small>result samples</small></div>
    </div>
    """

def research_charts_html(payload):
    import json
    data = json.dumps(payload)
    return f"""
    <div class="chart-grid">
      <div class="chart-panel">
        <div class="chart-head">
          <div><div class="chart-title">Health Timeline</div><div class="chart-sub">Model health score trajectory over time.</div></div>
          <span class="chip">Trajectory</span>
        </div>
        <div class="chart-canvas-wrap"><canvas id="healthTimelineChart"></canvas></div>
      </div>

      <div class="chart-panel">
        <div class="chart-head">
          <div><div class="chart-title">Sample Growth</div><div class="chart-sub">Validation sample accumulation.</div></div>
          <span class="chip">Credibility</span>
        </div>
        <div class="chart-canvas-wrap"><canvas id="sampleGrowthChart"></canvas></div>
      </div>

      <div class="chart-panel">
        <div class="chart-head">
          <div><div class="chart-title">CLV Distribution</div><div class="chart-sub">Market movement quality by CLV bucket.</div></div>
          <span class="chip">Market</span>
        </div>
        <div class="chart-canvas-wrap"><canvas id="clvDistributionChart"></canvas></div>
      </div>

      <div class="chart-panel">
        <div class="chart-head">
          <div><div class="chart-title">Confidence Clusters</div><div class="chart-sub">Signal count and win rate by confidence band.</div></div>
          <span class="chip">Calibration</span>
        </div>
        <div class="chart-canvas-wrap"><canvas id="confidenceClusterChart"></canvas></div>
      </div>
    </div>

    <script>
    const researchData = {data};

    function makeGradient(ctx, area, c1, c2){{
      const g = ctx.createLinearGradient(0, area.bottom, 0, area.top);
      g.addColorStop(0, c1);
      g.addColorStop(1, c2);
      return g;
    }}

    const commonOptions = {{
      responsive: true,
      maintainAspectRatio: false,
      animation: {{ duration: 1600, easing: 'easeOutQuart' }},
      plugins: {{
        legend: {{ labels: {{ color: '#cbd5e1', boxWidth: 10, font: {{ size: 11, weight: 'bold' }} }} }},
        tooltip: {{
          backgroundColor: 'rgba(2,6,23,.94)',
          borderColor: 'rgba(148,163,184,.25)',
          borderWidth: 1,
          titleColor: '#e2e8f0',
          bodyColor: '#cbd5e1',
          padding: 10,
          cornerRadius: 12
        }}
      }},
      scales: {{
        x: {{ ticks: {{ color: '#7a90b8', maxRotation: 0 }}, grid: {{ color: 'rgba(77,143,255,.06)' }} }},
        y: {{ ticks: {{ color: '#7a90b8' }}, grid: {{ color: 'rgba(77,143,255,.06)' }} }}
      }}
    }};

    function renderCharts(){{
      const healthEl = document.getElementById('healthTimelineChart');
      if(healthEl){{
        new Chart(healthEl, {{
          type: 'line',
          data: {{
            labels: researchData.health_labels,
            datasets: [{{
              label: 'Health Score',
              data: researchData.health_scores,
              borderWidth: 3,
              tension: .42,
              pointRadius: 3,
              pointHoverRadius: 6,
              fill: true,
              borderColor: '#00d4ff',
              backgroundColor: function(context){{
                const chart = context.chart;
                const area = chart.chartArea;
                if(!area) return 'rgba(0,212,255,.12)';
                return makeGradient(chart.ctx, area, 'rgba(0,212,255,.02)', 'rgba(0,212,255,.24)');
              }}
            }}]
          }},
          options: commonOptions
        }});
      }}

      const sampleEl = document.getElementById('sampleGrowthChart');
      if(sampleEl){{
        new Chart(sampleEl, {{
          type: 'line',
          data: {{
            labels: researchData.health_labels,
            datasets: [{{
              label: 'Sample Size',
              data: researchData.sample_sizes,
              borderWidth: 3,
              tension: .38,
              fill: true,
              borderColor: '#00f5a0',
              backgroundColor: function(context){{
                const chart = context.chart;
                const area = chart.chartArea;
                if(!area) return 'rgba(0,245,160,.12)';
                return makeGradient(chart.ctx, area, 'rgba(0,245,160,.02)', 'rgba(0,245,160,.22)');
              }}
            }}]
          }},
          options: commonOptions
        }});
      }}

      const clvEl = document.getElementById('clvDistributionChart');
      if(clvEl){{
        new Chart(clvEl, {{
          type: 'bar',
          data: {{
            labels: researchData.clv_buckets,
            datasets: [{{
              label: 'Signals',
              data: researchData.clv_counts,
              borderWidth: 1,
              borderRadius: 10,
              borderColor: 'rgba(0,212,255,.35)',
              backgroundColor: 'rgba(0,212,255,.24)'
            }}]
          }},
          options: commonOptions
        }});
      }}

      const confEl = document.getElementById('confidenceClusterChart');
      if(confEl){{
        new Chart(confEl, {{
          type: 'bar',
          data: {{
            labels: researchData.conf_labels,
            datasets: [
              {{
                label: 'Signal Count',
                data: researchData.conf_counts,
                borderRadius: 10,
                backgroundColor: 'rgba(77,143,255,.28)',
                borderColor: 'rgba(77,143,255,.45)',
                borderWidth: 1
              }},
              {{
                label: 'Win Rate %',
                data: researchData.conf_wr,
                type: 'line',
                borderColor: '#ffc94d',
                backgroundColor: 'rgba(255,201,77,.10)',
                borderWidth: 3,
                tension: .35
              }}
            ]
          }},
          options: commonOptions
        }});
      }}
    }}
    renderCharts();
    </script>
    """


def read_json_safe(path):
    try:
        if not path.exists() or path.stat().st_size == 0:
            return {}
        import json
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

def snapshot_history_df():
    df = read_csv(RESEARCH_SNAPSHOT_HISTORY_CSV)
    return normalize(df) if not df.empty else pd.DataFrame()

def memory_payload():
    df = snapshot_history_df()
    if df.empty:
        return {
            "labels": [],
            "health": [],
            "sample": [],
            "clv": [],
            "wr": [],
            "insights": [],
            "rows": 0,
        }

    labels = []
    if "snapshotdate" in df.columns:
        labels = [str(x)[5:] for x in df["snapshotdate"].tail(30).tolist()]
    elif "SnapshotDate" in df.columns:
        labels = [str(x)[5:] for x in df["SnapshotDate"].tail(30).tolist()]

    def series(*names):
        for n in names:
            if n in df.columns:
                return [safe_float(x, 0) for x in df[n].tail(30).tolist()]
        return []

    return {
        "labels": labels,
        "health": series("healthscore", "HealthScore"),
        "sample": series("samplesize", "SampleSize"),
        "clv": series("avgclvpoints", "AvgCLVPoints"),
        "wr": series("signalwinrate", "SignalWinRate"),
        "insights": series("insightcount", "InsightCount"),
        "rows": len(df),
    }

def trend_direction(values):
    vals = [safe_float(v, None) for v in values if safe_float(v, None) is not None]
    if len(vals) < 2:
        return "flat", 0
    delta = vals[-1] - vals[0] if len(vals) < 7 else vals[-1] - vals[-7]
    if delta > 0.25:
        return "up", delta
    if delta < -0.25:
        return "down", delta
    return "flat", delta

def memory_metrics_html(payload):
    health = payload["health"][-1] if payload["health"] else 0
    sample = payload["sample"][-1] if payload["sample"] else 0
    clv = payload["clv"][-1] if payload["clv"] else 0
    wr = payload["wr"][-1] if payload["wr"] else 0

    h_dir, h_delta = trend_direction(payload["health"])
    c_dir, c_delta = trend_direction(payload["clv"])
    w_dir, w_delta = trend_direction(payload["wr"])

    return f"""
    <div class="research-metrics">
      <div class="research-metric"><span>Current Health</span><b>{health:.1f}</b><small class="{h_dir}">{h_delta:+.1f} trend</small></div>
      <div class="research-metric"><span>Sample</span><b>{sample:.0f}</b><small>tracked memory</small></div>
      <div class="research-metric"><span>Avg CLV</span><b>{clv:+.2f}</b><small>{c_delta:+.2f} trend</small></div>
      <div class="research-metric"><span>Signal WR</span><b>{wr:.1f}%</b><small>{w_delta:+.1f} trend</small></div>
    </div>
    """

def memory_charts_html(payload):
    import json
    data = json.dumps(payload)
    return f"""
    <div class="chart-grid">
      <div class="chart-panel">
        <div class="chart-head">
          <div><div class="chart-title">Persistent Health Memory</div><div class="chart-sub">Health score from daily research snapshots.</div></div>
          <span class="chip">Memory</span>
        </div>
        <div class="chart-canvas-wrap"><canvas id="memoryHealthChart"></canvas></div>
      </div>

      <div class="chart-panel">
        <div class="chart-head">
          <div><div class="chart-title">CLV + Win Rate Direction</div><div class="chart-sub">Market agreement and result performance over time.</div></div>
          <span class="chip">Trend</span>
        </div>
        <div class="chart-canvas-wrap"><canvas id="memoryClvWrChart"></canvas></div>
      </div>

      <div class="chart-panel">
        <div class="chart-head">
          <div><div class="chart-title">Sample Growth Memory</div><div class="chart-sub">Longitudinal validation sample growth.</div></div>
          <span class="chip">Trust</span>
        </div>
        <div class="chart-canvas-wrap"><canvas id="memorySampleChart"></canvas></div>
      </div>

      <div class="chart-panel">
        <div class="chart-head">
          <div><div class="chart-title">Insight Volume</div><div class="chart-sub">Number of generated insights by snapshot.</div></div>
          <span class="chip">Learning</span>
        </div>
        <div class="chart-canvas-wrap"><canvas id="memoryInsightChart"></canvas></div>
      </div>
    </div>

    <script>
    const memoryData = {data};

    const memoryOptions = {{
      responsive: true,
      maintainAspectRatio: false,
      animation: {{ duration: 1600, easing: 'easeOutQuart' }},
      plugins: {{
        legend: {{ labels: {{ color: '#cbd5e1', boxWidth: 10, font: {{ size: 11, weight: 'bold' }} }} }},
        tooltip: {{
          backgroundColor: 'rgba(2,6,23,.94)',
          borderColor: 'rgba(148,163,184,.25)',
          borderWidth: 1,
          titleColor: '#e2e8f0',
          bodyColor: '#cbd5e1',
          padding: 10,
          cornerRadius: 12
        }}
      }},
      scales: {{
        x: {{ ticks: {{ color: '#7a90b8', maxRotation: 0 }}, grid: {{ color: 'rgba(77,143,255,.06)' }} }},
        y: {{ ticks: {{ color: '#7a90b8' }}, grid: {{ color: 'rgba(77,143,255,.06)' }} }}
      }}
    }};

    function makeMemoryLine(id, label, values, color){{
      const el = document.getElementById(id);
      if(!el) return;
      new Chart(el, {{
        type: 'line',
        data: {{
          labels: memoryData.labels,
          datasets: [{{
            label: label,
            data: values,
            borderColor: color,
            backgroundColor: color.replace('1)', '.12)'),
            borderWidth: 3,
            tension: .4,
            fill: true,
            pointRadius: 3
          }}]
        }},
        options: memoryOptions
      }});
    }}

    makeMemoryLine('memoryHealthChart', 'Health', memoryData.health, 'rgba(103,232,249,1)');
    makeMemoryLine('memorySampleChart', 'Sample', memoryData.sample, 'rgba(46,229,157,1)');
    makeMemoryLine('memoryInsightChart', 'Insights', memoryData.insights, 'rgba(183,148,246,1)');

    const mixEl = document.getElementById('memoryClvWrChart');
    if(mixEl){{
      new Chart(mixEl, {{
        type: 'line',
        data: {{
          labels: memoryData.labels,
          datasets: [
            {{
              label: 'Avg CLV',
              data: memoryData.clv,
              borderColor: 'rgba(103,232,249,1)',
              backgroundColor: 'rgba(103,232,249,.10)',
              borderWidth: 3,
              tension: .4,
              fill: true
            }},
            {{
              label: 'Signal WR %',
              data: memoryData.wr,
              borderColor: 'rgba(255,209,102,1)',
              backgroundColor: 'rgba(255,209,102,.08)',
              borderWidth: 3,
              tension: .4,
              fill: false
            }}
          ]
        }},
        options: memoryOptions
      }});
    }}
    </script>
    """

def memory_feed_html(limit=10):
    df = snapshot_history_df()
    if df.empty:
        return '<div class="panel empty">No research snapshot history yet. Run daily_research_snapshot_v1.py.</div>'

    rows = df.tail(limit).iloc[::-1]
    cards = []
    for _, r in rows.iterrows():
        date = r.get("snapshotdate", r.get("SnapshotDate", ""))
        timestamp = r.get("snapshottimestamp", r.get("SnapshotTimestamp", ""))
        health = safe_float(r.get("healthscore", r.get("HealthScore", 0)), 0)
        label = r.get("healthlabel", r.get("HealthLabel", ""))
        sample = safe_float(r.get("samplesize", r.get("SampleSize", 0)), 0)
        clv = safe_float(r.get("avgclvpoints", r.get("AvgCLVPoints", 0)), 0)
        wr = safe_float(r.get("signalwinrate", r.get("SignalWinRate", 0)), 0)
        insights = safe_float(r.get("insightcount", r.get("InsightCount", 0)), 0)

        cards.append(f"""
        <div class="memory-card">
          <div class="memory-card-top">
            <div>
              <div class="memory-date">{date}</div>
              <div class="game-sub">{timestamp}</div>
            </div>
            {signal_badge(label)}
          </div>
          <div class="memory-kpis">
            <div class="memory-kpi"><span>Health</span><b>{health:.1f}</b></div>
            <div class="memory-kpi"><span>Sample</span><b>{sample:.0f}</b></div>
            <div class="memory-kpi"><span>Avg CLV</span><b>{clv:+.2f}</b></div>
            <div class="memory-kpi"><span>Signal WR</span><b>{wr:.1f}%</b></div>
          </div>
          <div class="memory-note">Insights generated: {insights:.0f}. Formula status remains frozen until sample thresholds are met.</div>
        </div>
        """)
    return '<div class="memory-feed">' + "".join(cards) + '</div>'

def memory_timeline_list(limit=14):
    df = snapshot_history_df()
    if df.empty:
        return ""
    rows = df.tail(limit).iloc[::-1]
    html = ['<div class="timeline-list">']
    for _, r in rows.iterrows():
        date = r.get("snapshotdate", r.get("SnapshotDate", ""))
        health = safe_float(r.get("healthscore", r.get("HealthScore", 0)), 0)
        label = r.get("healthlabel", r.get("HealthLabel", ""))
        sample = safe_float(r.get("samplesize", r.get("SampleSize", 0)), 0)
        html.append(f"""
        <div class="timeline-item">
          <span>{date}</span>
          <b>Health {health:.1f} - {label}</b>
          <em>Sample {sample:.0f}</em>
        </div>
        """)
    html.append('</div>')
    return "".join(html)

@app.route("/memory")
def memory():
    payload = memory_payload()
    body = f"""
    {live_status_strip()}
    <div class="section-head">
      <div><h2>Persistent Intelligence Memory</h2><p>Daily research snapshots, trend direction, and longitudinal model state.</p></div>
      <div class="toolbar"><span class="chip">Memory</span><span class="chip">Snapshots</span><span class="chip">Hermes-ready</span></div>
    </div>
    {memory_metrics_html(payload)}
    {memory_charts_html(payload)}

    <div class="memory-grid">
      <div>
        <div class="section-head"><div><h2>Research Memory Feed</h2><p>Latest daily intelligence snapshots.</p></div></div>
        {memory_feed_html(limit=10)}
      </div>
      <div>
        <div class="section-head"><div><h2>Snapshot Timeline</h2><p>Compact model-memory trail.</p></div></div>
        {memory_timeline_list(limit=14)}
      </div>
    </div>
    """
    return page("Memory", body)




@app.route("/environment")
def environment():
    env_json = read_json_safe(OUTPUT_DIR / "environment_regime_latest.json")
    buckets = read_csv(OUTPUT_DIR / "environment_bucket_report.csv")
    validation = read_csv(OUTPUT_DIR / "environment_validation_summary.csv")
    memory = read_csv(OUTPUT_DIR / "environment_memory_latest.csv")

    shares = pick_value(env_json, "bucket_shares", "BucketShares", default={})
    if not isinstance(shares, dict):
        shares = {}

    regime = pick_value(env_json, "environment_regime", "Regime", default="LEARNING")
    reason = pick_value(env_json, "reason", "Reason", default="Environment classification is still sample-building.")
    avg_clv = pick_value(env_json, "avg_clv", "AvgCLV", default="")
    avg_chaos = pick_value(env_json, "avg_chaos", "AvgChaos", default="")
    avg_trust = pick_value(env_json, "avg_trust", "AvgTrust", default="")
    no_play = shares.get("neutral_no_play", shares.get("no_play", ""))
    extreme = shares.get("extreme_over", "")
    lean = shares.get("lean_over", "")

    b = normalize(buckets)
    if not b.empty:
        bucket_cols = [c for c in ["game", "environmentbucket", "edge", "confidence", "chaosscore", "trustscore", "environmentaction"] if c in b.columns]
        bucket_table = table(b, cols=bucket_cols, max_rows=12)
    else:
        bucket_table = '<div class="empty">No environment bucket report yet.</div>'

    v = normalize(validation)
    if not v.empty:
        val_cols = [c for c in ["environmentbucket", "verdict", "sample", "graded", "winrate", "avgclv", "avgchaos", "avgtrust"] if c in v.columns]
        validation_table = table(v, cols=val_cols, max_rows=8)
    else:
        validation_table = '<div class="empty">No environment validation summary yet.</div>'

    m = normalize(memory)
    if not m.empty:
        mem_cols = [c for c in ["environmentbucket", "memorystate", "sample", "winrate", "avgclv", "avgedge", "avgconfidence", "avgchaos", "avgtrust"] if c in m.columns]
        memory_table = table(m, cols=mem_cols, max_rows=8)
    else:
        memory_table = '<div class="empty">No environment memory yet.</div>'

    body = f"""
    <div class="env-page-hero">
      <div class="panel">
        <div class="command-kicker"><span class="pulse-ring"></span> Environment Center</div>
        <h1 class="env-page-title">Environment intelligence for trust, chaos, and resistance.</h1>
        <p class="env-page-copy">Projection estimates the number. Environment grades the conditions around it. This page stays observational and separate from staking or formula changes.</p>
        <div class="env-grid-clean">
          <div class="env-tile-clean"><span>Regime</span><b>{regime}</b></div>
          <div class="env-tile-clean"><span>Avg Env CLV</span><b>{avg_clv}</b></div>
          <div class="env-tile-clean"><span>Chaos</span><b>{avg_chaos}</b></div>
          <div class="env-tile-clean"><span>Trust</span><b>{avg_trust}</b></div>
        </div>
      </div>
      <div class="panel">
        <div class="section-head" style="margin-top:0"><div><h2>Bucket Mix</h2><p>{reason}</p></div><span class="chip">Observational</span></div>
        <div class="env-grid-clean">
          <div class="env-tile-clean"><span>No Play</span><b>{no_play}</b></div>
          <div class="env-tile-clean"><span>Extreme Over</span><b>{extreme}</b></div>
          <div class="env-tile-clean"><span>Lean Over</span><b>{lean}</b></div>
        </div>
      </div>
    </div>

    <div class="env-panel-split">
      <div class="panel"><div class="section-head" style="margin-top:0"><div><h2>Bucket Report</h2><p>Game-level environment classification.</p></div></div>{bucket_table}</div>
      <div class="panel"><div class="section-head" style="margin-top:0"><div><h2>Validation Summary</h2><p>Environment outcomes and CLV state.</p></div></div>{validation_table}</div>
    </div>

    <div class="panel"><div class="section-head" style="margin-top:0"><div><h2>Environment Memory</h2><p>Longitudinal bucket memory. Observational only.</p></div><span class="chip">No Formula Changes</span></div>{memory_table}</div>
    """
    return page("Environment", body)

@app.route("/research")
def research():
    payload = research_data_payload()
    body = f"""
    {live_status_strip()}
    <div class="section-head">
      <div><h2>Research Visualization Layer</h2><p>Health trajectory, sample growth, market agreement, and confidence calibration.</p></div>
      <div class="toolbar"><span class="chip">Chart.js</span><span class="chip">Animated</span><span class="chip">Quant View</span></div>
    </div>
    {research_metrics_html(payload)}
    {research_charts_html(payload)}
    """
    return page("Research", body)



@app.route("/intelligence")
def intelligence():
    body = f"""
    {live_status_strip()}
    {intelligence_hero()}

    <div class="section-head">
      <div><h2>Insight Feed</h2><p>Sample-aware research observations generated by the Insight Engine.</p></div>
      <div class="toolbar"><span class="chip">Observe</span><span class="chip">Measure</span><span class="chip">Do not overfit</span></div>
    </div>
    {insight_cards(limit=12)}

    <div class="section-head">
      <div><h2>Research Console</h2><p>Plain-language briefing for future Hermes integration.</p></div>
    </div>
    {intelligence_console()}

    <div class="section-head">
      <div><h2>Insight Data</h2><p>Full insight table for auditability.</p></div>
    </div>
    <div class="panel">{table(read_csv(INSIGHT_REPORT_CSV), max_rows=80) if not read_csv(INSIGHT_REPORT_CSV).empty else "No insight report yet."}</div>
    """
    return page("Intelligence", body)



@app.route("/validation")
def validation():
    try:
        clv_summary = read_csv(SIGNAL_CLV_SUMMARY_CSV)
        result_summary = read_csv(SIGNAL_RESULTS_SUMMARY_CSV)
        graded = read_csv(SIGNAL_GRADED_CSV)
        with_clv = read_csv(SIGNAL_WITH_CLV_CSV)

        if graded.empty and with_clv.empty and clv_summary.empty and result_summary.empty:
            return page("Validation", '<div class="panel empty">No validation files yet. Run signal_clv_auto_v1.py and signal_result_grader_v1.py.</div>')

        active_file = graded if not graded.empty else with_clv

        body = f"""
        {live_status_strip()}
        <div class="section-head">
          <div><h2>Closed-Loop Validation</h2><p>Model signal -> market close -> final result. This is the core learning layer.</p></div>
          <div class="toolbar"><span class="chip">CLV</span><span class="chip">Result grading</span><span class="chip">Signal learning</span></div>
        </div>

        <div class="validation-note">
          This page evaluates model signals, not necessarily real bets. It shows whether the model is beating the market and whether signal quality translates into actual outcomes.
        </div>

        {model_health_panel()}

        {intelligence_console()}

        {validation_health_cards(clv_summary, result_summary, active_file)}

        <div class="section-head">
          <div><h2>Signal Validation Cards</h2><p>Tracked signals with line movement, CLV, and final grading when available.</p></div>
        </div>
        {validation_signal_cards(active_file)}
        """

        body += validation_summary_section("CLV by Final Signal", clv_summary, "FinalSignal")
        body += validation_summary_section("Results by Final Signal", result_summary, "FinalSignal")
        body += validation_summary_section("Diagnostics vs CLV", clv_summary, "PaceDiag")
        body += validation_summary_section("Diagnostics vs Results", result_summary, "PaceDiag")

        return page("Validation", body)

    except Exception as e:
        body = f"""
        <div class="panel">
          <h2>Validation page error</h2>
          <p class="muted">The dashboard did not crash globally. The validation route caught this error:</p>
          <pre>{type(e).__name__}: {e}</pre>
          <p class="muted">Send this error text back so we can patch the exact cause.</p>
        </div>
        """
        return page("Validation Error", body)


@app.route("/diagnostics")
def diagnostics():
    df = read_csv(DIAGNOSTICS_CSV)

    if df.empty:
        body = '<div class="panel empty">No projections_diagnostics.csv found. Run diagnostic_layer_v1.py first.</div>'
        return page("Diagnostics", body)

    data = normalize(df)

    total = len(data)
    neg_watch = 0
    lean_count = 0
    if "finalsignalnormalized" in data.columns:
        sigs = data["finalsignalnormalized"].astype(str).str.upper()
        lean_count = sigs.str.contains("LEAN").sum()
        watch = data[sigs.str.contains("WATCHLIST")].copy()
        if not watch.empty:
            diag_cols = ["pace_diag", "offense_diag", "efg_diag", "tov_diag", "oreb_diag"]
            existing = [c for c in diag_cols if c in watch.columns]
            if existing:
                neg_watch = watch[existing].apply(lambda row: sum("NEGATIVE" in str(v).upper() for v in row), axis=1).sum()

    body = f"""
    <section class="metrics">
      {metric_card("Games", total, "diagnosed")}
      {metric_card("Leans", lean_count, "active lean signals")}
      {metric_card("Watch Negatives", int(neg_watch), "negative flags on watchlists")}
      {metric_card("Formula", "Frozen", "diagnostics only")}
    </section>

    <div class="section-head">
      <div><h2>Model Diagnostics</h2><p>Explanatory drivers only. These do not affect projection, confidence, signal, or stake yet.</p></div>
      <div class="toolbar"><span class="chip">Observer layer</span><span class="chip">No overfitting</span></div>
    </div>
    {diagnostic_cards(data)}
    """
    return page("Diagnostics", body)



@app.route("/analysis")
def analysis():
    summary = read_csv(EVALUATION_SUMMARY_CSV)

    if summary.empty:
        body = '<div class="panel empty">No bet_evaluation_summary.csv found. Run bet_evaluator.py first.</div>'
        return page("Analysis", body)

    data = normalize(summary)

    signal_df = analysis_metric_rows(summary, "Signal")
    market_df = analysis_metric_rows(summary, "Market")
    odds_df = analysis_metric_rows(summary, "OddsBucket")

    # Overall from summary cannot reconstruct exactly, so use bet tracker if available.
    bets = load_bets()
    if not bets.empty:
        bets = bets.copy()
        bets["profit_loss"] = bets.apply(calc_pl, axis=1)
        result = bets["result"].astype(str).str.upper()
        settled = bets[result.isin(["WIN", "LOSS"])].copy()
        wins = (settled["result"].astype(str).str.upper() == "WIN").sum()
        losses = (settled["result"].astype(str).str.upper() == "LOSS").sum()
        stake = pd.to_numeric(settled.get("stake", 0), errors="coerce").fillna(0).sum()
        pl = pd.to_numeric(settled.get("profit_loss", 0), errors="coerce").fillna(0).sum()
        roi = (pl / stake * 100) if stake else 0
    else:
        settled = pd.DataFrame()
        wins = losses = stake = pl = roi = 0

    body = f"""
    <section class="metrics">
      {metric_card("Settled", len(settled), "evaluated bets")}
      {metric_card("Record", f"{wins}-{losses}", "wins-losses")}
      {metric_card("P/L", f"{pl:+.2f}u", "historical units", "positive" if pl >= 0 else "negative")}
      {metric_card("ROI", f"{roi:+.1f}%", "settled stake", "positive" if roi >= 0 else "negative")}
      {metric_card("Sample", "Early", "do not overfit")}
      {metric_card("Target", "100+", "before formula changes")}
    </section>

    <div class="section-head">
      <div><h2>Betting Policy Notes</h2><p>Risk filters can change now. Model formula stays unchanged until larger sample.</p></div>
    </div>
    <div class="policy-grid">
      <div class="policy-card"><h3 class="negative">Retired for now</h3><p>Speculative Over: 0-2 and -100% ROI. No auto-bet unless upgraded by role/minutes data.</p></div>
      <div class="policy-card"><h3 class="yellow">Caution</h3><p>Rebounds market is 6-6 and slightly negative. Require stronger confirmation before increasing stakes.</p></div>
      <div class="policy-card"><h3 class="positive">Promising</h3><p>Wing vs Generous DREB, Game Totals, DREB Generous Total, and High Usage Big vs Stingy remain worth tracking.</p></div>
      <div class="policy-card"><h3>Discipline Rule</h3><p>Do not change projection formulas before at least 100 settled bets or a meaningful backtest.</p></div>
    </div>

    <div class="section-head"><div><h2>Signal Performance</h2><p>Historical signal quality from your placed bets.</p></div></div>
    {analysis_cards(signal_df, "Signals")}

    <div class="section-head"><div><h2>Market Performance</h2><p>Totals vs props by actual bet results.</p></div></div>
    {analysis_cards(market_df, "Markets")}

    <div class="section-head"><div><h2>Odds Buckets</h2><p>Where your pricing has performed best.</p></div></div>
    {analysis_cards(odds_df, "Odds")}
    """
    return page("Analysis", body)




@app.route("/hermes")
def hermes():
    return page("Hermes", v19_hermes())

@app.route("/bets")
def bets():
    df=load_bets()
    if df.empty: return page("Tracker", '<div class="panel empty">Run bet_tracker_seed.py first.</div>')
    df=df.copy(); df["profit_loss"]=df.apply(calc_pl, axis=1)
    if "date" in df.columns: df=df.sort_values("date", ascending=False)
    result=df["result"].astype(str).str.upper(); settled=df[~result.isin(["PENDING","OPEN",""])].copy(); pending=df[result.isin(["PENDING","OPEN"])].copy()
    wins=(settled["result"].astype(str).str.upper()=="WIN").sum(); losses=(settled["result"].astype(str).str.upper()=="LOSS").sum(); stake=pd.to_numeric(settled.get("stake",0), errors="coerce").fillna(0).sum(); pl=pd.to_numeric(settled.get("profit_loss",0), errors="coerce").fillna(0).sum(); roi=(pl/stake*100) if stake else 0
    body=f"""<section class="metrics">{metric_card("Settled",len(settled),"graded bets")}{metric_card("Wins",wins,"green tickets","positive")}{metric_card("Losses",losses,"red tickets","negative")}{metric_card("P/L",f"{pl:+.2f}u","unit profit","positive" if pl>=0 else "negative")}{metric_card("ROI",f"{roi:+.1f}%","settled stake","positive" if roi>=0 else "negative")}{metric_card("Pending",len(pending),"open bets","yellow")}</section>"""
    if "signal" in df.columns and not settled.empty:
        grouped=settled.groupby("signal").agg(bets=("signal","count"), wins=("result", lambda s:(s.astype(str).str.upper()=="WIN").sum()), pl=("profit_loss","sum"), stake=("stake","sum")).reset_index()
        grouped["win_rate"]=grouped.apply(lambda r:(r["wins"]/r["bets"]*100) if r["bets"] else 0, axis=1); grouped["roi"]=grouped.apply(lambda r:(r["pl"]/r["stake"]*100) if r["stake"] else 0, axis=1)
        body += '<div class="section-head"><div><h2>Performance by Signal</h2><p>Compact analytics by edge type.</p></div></div><div class="panel">' + table(grouped.sort_values("pl", ascending=False), max_rows=60) + '</div>'
    body += '<div class="section-head"><div><h2>Recent Bet Cards</h2><p>Readable ticket-style view.</p></div></div>' + bet_cards(df, max_cards=80)
    return page("Tracker", body)


# ===================== V19.4 COMPLETE REFINEMENT LAYER =====================
CSS += '''
/* ===== V19.4 COMPLETE REFINEMENT ===== */
.footer::after{content:" · V21.8 advisory cycle · manual approval · no auto-betting"!important;color:rgba(0,200,240,.68)!important}
.v193-page-note{border:1px solid rgba(0,200,240,.14);background:linear-gradient(145deg,rgba(0,200,240,.055),rgba(3,8,15,.96));border-radius:22px;padding:18px;margin:16px 0;color:var(--muted);font-family:var(--font-mono);font-size:11.5px;line-height:1.6}.v193-page-note b{color:var(--text);font-family:var(--font-display);font-size:18px;letter-spacing:-.04em;display:block;margin-bottom:5px}.v193-guardrail{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.v193-guard-card{border:1px solid rgba(255,255,255,.075);background:var(--v19-glass);border-radius:18px;padding:15px;min-height:108px}.v193-guard-card span,.v193-summary-card span,.compact-pass-row span{display:block;color:var(--muted);font-family:var(--font-mono);font-size:9.2px;text-transform:uppercase;letter-spacing:.105em;font-weight:900}.v193-guard-card b,.v193-summary-card b{display:block;margin-top:8px;font-family:var(--font-display);font-size:21px;letter-spacing:-.055em;line-height:1.02}.v193-guard-card p,.v193-summary-card p{margin-top:7px;color:var(--muted);font-family:var(--font-mono);font-size:10px;line-height:1.45}.v193-guard-card.ok{border-color:rgba(5,232,154,.18);background:linear-gradient(145deg,rgba(5,232,154,.055),rgba(3,8,15,.98))}.v193-guard-card.warn{border-color:rgba(245,200,66,.20);background:linear-gradient(145deg,rgba(245,200,66,.06),rgba(3,8,15,.98))}.v193-guard-card.lock{border-color:rgba(248,75,110,.18);background:linear-gradient(145deg,rgba(248,75,110,.055),rgba(3,8,15,.98))}
.action-section-grid{display:grid;grid-template-columns:minmax(0,1.1fr) minmax(320px,.55fr);gap:14px;align-items:start}.compact-pass-list{display:grid;gap:8px}.compact-pass-row{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:center;border:1px solid rgba(255,255,255,.06);background:rgba(2,5,9,.48);border-radius:14px;padding:11px 13px}.compact-pass-row b{font-size:13px;letter-spacing:-.025em}.compact-pass-row em{font-style:normal;color:var(--muted);font-family:var(--font-mono);font-size:9.5px}.action-clean-title,.action-clean-bet{overflow-wrap:anywhere}.action-clean-grid{grid-template-columns:repeat(5,minmax(0,1fr))}.reason-box b{overflow-wrap:anywhere}.approval-rail{display:flex;gap:7px;flex-wrap:wrap;margin-top:12px}.approval-pill{display:inline-flex;border:1px solid rgba(255,255,255,.08);border-radius:999px;padding:5px 9px;font-family:var(--font-mono);font-size:9.5px;font-weight:900;text-transform:uppercase}.approval-pill.ready{color:var(--green);background:rgba(5,232,154,.07);border-color:rgba(5,232,154,.22)}.approval-pill.warn{color:var(--yellow);background:rgba(245,200,66,.07);border-color:rgba(245,200,66,.22)}.approval-pill.locked{color:var(--red);background:rgba(248,75,110,.07);border-color:rgba(248,75,110,.22)}
.v193-summary-grid{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));gap:10px;margin:14px 0}.v193-summary-card{border:1px solid rgba(255,255,255,.075);background:var(--v19-glass);border-radius:18px;padding:15px;min-height:118px}.v193-summary-card.primary{border-color:rgba(0,200,240,.18);background:linear-gradient(145deg,rgba(0,200,240,.06),rgba(3,8,15,.98))}.v193-summary-card.warn{border-color:rgba(245,200,66,.18);background:linear-gradient(145deg,rgba(245,200,66,.055),rgba(3,8,15,.98))}.v193-summary-card.lock{border-color:rgba(248,75,110,.16);background:linear-gradient(145deg,rgba(248,75,110,.05),rgba(3,8,15,.98))}
.hermes-cockpit{display:grid;grid-template-columns:minmax(0,1fr) minmax(350px,.62fr);gap:14px;align-items:start}.hermes-command-card{border:1px solid rgba(0,200,240,.18);border-radius:30px;padding:30px;background:radial-gradient(circle at 92% 0%,rgba(0,200,240,.13),transparent 34%),var(--v19-glass);box-shadow:0 22px 74px rgba(0,0,0,.45)}.hermes-command-card h1{font-family:var(--font-display);font-size:58px;line-height:.9;letter-spacing:-.09em;margin:14px 0}.hermes-queue-list{display:grid;gap:9px}.hermes-queue-row{display:grid;grid-template-columns:96px 1fr auto;gap:10px;align-items:center;border:1px solid rgba(255,255,255,.065);border-radius:14px;background:rgba(2,5,9,.52);padding:12px 13px}.hermes-queue-row span{font-family:var(--font-mono);font-size:9.5px;text-transform:uppercase;color:var(--muted);font-weight:900}.hermes-queue-row b{font-size:13px;letter-spacing:-.025em}.hermes-queue-row em{font-style:normal;color:var(--cyan);font-family:var(--font-mono);font-size:9.5px;font-weight:900}.hermes-status-row{display:grid;grid-template-columns:1fr auto;gap:10px;align-items:center;border:1px solid rgba(255,255,255,.055);border-radius:12px;background:rgba(2,5,9,.46);padding:10px 12px}.hermes-status-row span.ok{color:var(--green)}.hermes-status-row span.warn{color:var(--yellow)}
.menu-group-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.menu-group{border:1px solid rgba(255,255,255,.075);border-radius:24px;background:var(--v19-glass);padding:18px}.menu-group h3{font-size:22px;letter-spacing:-.06em;margin:0 0 5px}.menu-group p{color:var(--muted);font-family:var(--font-mono);font-size:10.5px;margin:0 0 12px}.menu-link-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px}.menu-link{border:1px solid rgba(255,255,255,.06);border-radius:14px;background:rgba(2,5,9,.44);padding:12px;transition:var(--transition)}.menu-link:hover{transform:translateY(-2px);border-color:rgba(0,200,240,.2)}.menu-link span{display:block;color:var(--cyan);font-family:var(--font-mono);font-size:9px;text-transform:uppercase;letter-spacing:.1em;font-weight:900}.menu-link b{display:block;font-size:14px;letter-spacing:-.04em;margin-top:4px}.menu-link em{display:block;font-style:normal;color:var(--muted);font-family:var(--font-mono);font-size:9.5px;margin-top:4px;line-height:1.3}
.bankroll-chart-wrap{min-height:340px}.bankroll-focus-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px}.validation-compact-list{display:grid;gap:8px}.validation-row-lite{display:grid;grid-template-columns:1fr repeat(4,92px);gap:8px;align-items:center;border:1px solid rgba(255,255,255,.055);border-radius:14px;background:rgba(2,5,9,.48);padding:11px 13px}.validation-row-lite span{color:var(--muted);font-family:var(--font-mono);font-size:9.5px;text-transform:uppercase;font-weight:900}.validation-row-lite b{font-size:13px}.validation-row-lite em{font-style:normal;color:var(--green);font-family:var(--font-mono);font-size:10px}.env-panel-split{align-items:start}.table-wrap table{font-variant-numeric:tabular-nums}.web-preview,.panel,.v19-panel{overflow:hidden}
@media(max-width:1100px){.action-section-grid,.hermes-cockpit{grid-template-columns:1fr}.v193-summary-grid{grid-template-columns:repeat(3,minmax(0,1fr))}.v193-guardrail,.bankroll-focus-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.menu-group-grid{grid-template-columns:1fr}}
@media(max-width:720px){.v193-summary-grid,.v193-guardrail,.bankroll-focus-grid,.menu-link-grid{grid-template-columns:1fr}.validation-row-lite,.hermes-queue-row,.compact-pass-row{grid-template-columns:1fr}.action-clean-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.hermes-command-card h1{font-size:40px}.v19-title{font-size:42px!important}.bankroll-chart-wrap{min-height:260px}}
'''

def _v193_pick(row, names, default=""):
    for n in names:
        try:
            val = row.get(n, "")
        except Exception:
            val = ""
        if str(val).strip() not in ["", "nan", "None"]:
            return val
    return default

def _v193_clean(v, default="—"):
    try:
        if pd.isna(v):
            return default
    except Exception:
        pass
    s = str(v).strip()
    if not s or s.lower() in ["nan", "none", "null"]:
        return default
    return s

def _v193_split_actions(df):
    data = _norm(df)
    if data.empty:
        return data, data
    unit_col = "suggestedunits" if "suggestedunits" in data.columns else "suggested_units" if "suggested_units" in data.columns else None
    data = data.copy()
    data["_units"] = data[unit_col].apply(safe_float) if unit_col else 0.0
    data = data.sort_values("_units", ascending=False)
    return data[data["_units"] > 0].copy(), data[data["_units"] <= 0].copy()

def _v193_row_labels(r):
    away = _v193_clean(_v193_pick(r, ["awayteam", "away_team", "away", "visitor", "visitor_team"], ""), "")
    home = _v193_clean(_v193_pick(r, ["hometeam", "home_team", "home"], ""), "")
    game = _v193_clean(_v193_pick(r, ["game", "matchup", "fixture", "event"], ""), "")
    if game == "—" and away and home:
        game = f"{away} @ {home}"
    if game == "—":
        game = "Game pending label"
    bet = _v193_clean(_v193_pick(r, ["recommended_bet", "recommendedbet", "finalsignal", "final_signal", "signal", "bet"], "Review"), "Review")
    market = _v193_clean(_v193_pick(r, ["market", "bet_type", "type", "wager_type", "markettype"], "Derived market"), "Derived market")
    odds_raw = _v193_pick(r, ["odds", "assumedodds", "assumed_odds", "price", "american_odds"], "")
    odds = _v193_clean(odds_raw, "Pending")
    if odds not in ["Pending", "—"]:
        try:
            o = float(odds)
            odds = f"{int(o):+d}" if abs(o) >= 100 else f"{o:.2f}"
        except Exception:
            pass
    return game, bet, market, odds

def _v193_action_cards(data, limit=5, mode="recommended"):
    if data.empty:
        return smart_missing('projections_with_stakes.csv', 'No recommended actions currently clear the staking threshold.' if mode == 'recommended' else 'No pass states to show.')
    cards = []
    for i, (_, r) in enumerate(data.head(limit).iterrows(), start=1):
        game, bet, market, odds = _v193_row_labels(r)
        units = safe_float(r.get("_units", r.get("suggestedunits", r.get("suggested_units", 0))))
        stake = _v193_clean(_v193_pick(r, ["suggestedstake", "suggested_stake", "stake"], "—"))
        edge = _v193_clean(_v193_pick(r, ["edge", "model_edge", "projectededge"], "—"))
        conf = _v193_clean(_v193_pick(r, ["confidence", "confidence_score", "confidencescore"], "—"))
        env = _v193_clean(_v193_pick(r, ["environmentbucket", "environment_bucket", "environmentaction", "env"], "Watch"))
        status = "Approval Required" if units > 0 else "No Play / Pass"
        badge = "green" if units > 0 else "gray"
        risk_state = "Ready" if units > 0 and units <= 2.5 else "Review" if units > 0 else "Pass"
        risk_cls = "ready" if risk_state == "Ready" else "warn" if risk_state == "Review" else "locked"
        why = "Positive unit output from the frozen staking model." if units > 0 else "Below bet threshold or explicitly classified as pass."
        risk = "Standard exposure review" if units <= 2.5 else "Elevated exposure review"
        if units <= 0:
            risk = "No exposure"
        action_label = "Action" if units > 0 else "Pass"
        operator = "Approve / reject manually" if units > 0 else "Respect pass state"
        cards.append(f'''<div class="action-clean-card">
          <div class="action-clean-head"><div><div class="action-rank-clean">#{i:02d} {action_label}</div><div class="action-clean-title">{game}</div></div><span class="badge {badge}">{status}</span></div>
          <div class="action-clean-bet">{bet}</div>
          <div class="action-meta-clean">Market: <strong>{market}</strong> · Stake: <strong>{units:.2f}u</strong> · Amount: <strong>{stake}</strong> · Odds: <strong>{odds}</strong></div>
          <div class="action-clean-grid"><div class="mini"><span>Units</span><b>{units:.2f}</b></div><div class="mini"><span>Edge</span><b>{edge}</b></div><div class="mini"><span>Confidence</span><b>{conf}</b></div><div class="mini"><span>Environment</span><b>{env}</b></div><div class="mini"><span>Approval</span><b>Manual</b></div></div>
          <div class="action-reason-grid"><div class="reason-box"><span>Why this bet</span><b>{why}</b><p>Review context; not an execution command.</p></div><div class="reason-box"><span>Risk context</span><b>{risk}</b><p>Check bankroll, environment, injuries, and stale output status.</p></div><div class="reason-box"><span>Operator action</span><b>{operator}</b><p>Hermes cannot place bets.</p></div></div>
          <div class="approval-rail"><span class="approval-pill {risk_cls}">{risk_state}</span><span class="approval-pill locked">No auto-bet</span><span class="approval-pill warn">Injury check pending</span></div>
        </div>''')
    return '<div class="action-board">' + ''.join(cards) + '</div>'

def _v193_pass_rows(data, limit=12):
    if data.empty:
        return '<div class="missing-smart"><b>No pass states currently visible.</b><br>Pass/no-play review will appear when staking output includes zero-unit rows.</div>'
    rows=[]
    for _, r in data.head(limit).iterrows():
        game, bet, market, odds = _v193_row_labels(r)
        env = _v193_clean(_v193_pick(r, ["environmentbucket", "environment_bucket", "environmentaction", "env"], "Watch"))
        rows.append(f'<div class="compact-pass-row"><div><span>{market} · {env}</span><b>{game}</b><em>{bet}</em></div><span class="badge gray">Pass</span></div>')
    return '<div class="compact-pass-list">' + ''.join(rows) + '</div>'

def action_board(df, limit=12):
    rec, pas = _v193_split_actions(df)
    return _v193_action_cards(rec if not rec.empty else pas, limit=limit, mode="recommended" if not rec.empty else "pass")

def operator_guardrails_panel():
    ss = slate_stats(); bank = bankroll_snapshot()
    exp_cls = "ok" if ss['units'] <= 3 else "warn" if ss['units'] <= 6 else "lock"
    pl_cls = "ok" if bank['pl'] >= 0 else "warn" if bank['pl'] > -5 else "lock"
    return f'''<section><div class="v19-section-head"><div><h2>Operator guardrails</h2><p>One compact risk layer. Full fund details live on Bankroll.</p></div><a class="chip" href="/bankroll">Bankroll</a></div><div class="v193-guardrail"><div class="v193-guard-card {exp_cls}"><span>Slate Exposure</span><b>{ss['units']:.2f}u</b><p>Manual review required above all output.</p></div><div class="v193-guard-card {pl_cls}"><span>Bankroll Pressure</span><b>{bank['pl']:+.2f}u</b><p>Drawdown gates automation confidence.</p></div><div class="v193-guard-card warn"><span>Injury Feed</span><b>Pending</b><p>Blocks full automation until integrated.</p></div><div class="v193-guard-card lock"><span>Automation</span><b>Locked</b><p>No auto-bet. No bypass.</p></div></div></section>'''

def v19_home():
    ss = slate_stats(); bank = bankroll_snapshot()
    return f'''<main class="v19-home"><section class="v19-hero"><div class="v19-hero-grid"><div><div class="v19-eyebrow"><span class="pulse-ring"></span> WNBA Edge Lab</div><h1 class="v19-title">A betting research terminal with agent-grade discipline.</h1><p class="v19-copy">Edge Lab combines projections, environment memory, research validation, bankroll control, and Hermes automation readiness into a public website with a private-grade operator terminal.</p><div class="v19-actions"><a class="btn primary" href="/dashboard">Open Dashboard</a><a class="btn" href="/bankroll">Bankroll Tracker</a><a class="btn" href="/hermes">Hermes Agent</a></div></div><div class="v19-side"><div class="v19-kpi"><span>Slate</span><b>{ss['games']}</b><p>Games currently visible to the model.</p></div><div class="v19-kpi"><span>Actions</span><b>{ss['recommended']}</b><p>Recommended bets awaiting review.</p></div><div class="v19-kpi"><span>Exposure</span><b>{ss['units']:.2f}u</b><p>Current slate exposure.</p></div><div class="v19-kpi"><span>Bankroll P/L</span><b>{bank['pl']:+.2f}u</b><p>Settled tracker performance.</p></div></div></div></section><section><div class="v19-section-head"><div><h2>Four desks. One workflow.</h2><p>Each desk has one job: operate, protect, review, or automate with guardrails.</p></div><span class="chip">V21.8</span></div><div class="v19-grid-4"><a class="v19-card" href="/dashboard"><span>Terminal</span><b>Operator Dashboard</b><p>Mission brief, priority actions, guardrails, and model context.</p></a><a class="v19-card" href="/bankroll"><span>Fund</span><b>Bankroll Control</b><p>Curve, P/L, exposure, drawdown, and risk limits.</p></a><a class="v19-card" href="/actions"><span>Action</span><b>Bet Review Desk</b><p>Recommended actions, pass states, why/risk notes, and approval state.</p></a><a class="v19-card" href="/hermes"><span>Agent</span><b>Hermes Automation</b><p>Observe, warn, recommend, and wait for approval.</p></a></div></section><section><div class="v19-section-head"><div><h2>Today snapshot</h2><p>A quick read on slate size, review queue, bankroll state, and system readiness.</p></div><a class="chip" href="/dashboard">Open terminal</a></div><div class="v19-grid-3"><div class="v19-panel"><div class="mission-row"><span>Mode</span><b>Manual approval</b><em>Locked</em></div><div class="mission-row"><span>Actions</span><b>{ss['recommended']} bets to review</b><em>{ss['units']:.2f}u</em></div><div class="mission-row"><span>Risk</span><b>Hermes cannot execute bets</b><em>Safe</em></div></div><div class="v19-panel">{file_state(PROJECTIONS_CSV, 'Model')}{file_state(PROJECTIONS_STAKES_CSV, 'Staking')}{file_state(MODEL_HEALTH_CSV, 'Health')}</div><div class="v19-panel">{file_state(OUTPUT_DIR / 'environment_memory_latest.csv', 'Memory')}{file_state(OUTPUT_DIR / 'environment_validation_summary.csv', 'Validation')}{file_state(TELEGRAM_TXT, 'Telegram')}</div></div></section></main>'''

def v19_dashboard():
    proj = read_csv(PROJECTIONS_CSV)
    stakes = read_csv(PROJECTIONS_STAKES_CSV)
    rec, _ = _v193_split_actions(stakes)
    display_actions = rec if not rec.empty else _norm(stakes)
    projection_preview = projection_cards(proj.head(4) if hasattr(proj, 'head') else proj)
    return f'''{command_center_hero(proj, stakes)}{v192_command_strip()}<section class="terminal-layout"><div class="terminal-stack">{v192_operator_brief()}<div class="v19-section-head"><div><h2>Top action queue</h2><p>Only the highest-priority review cards belong on Dashboard. Full review is on Actions.</p></div><a class="chip" href="/actions">Open Actions</a></div>{_v193_action_cards(display_actions, limit=3)}<details class="panel"><summary style="cursor:pointer;font-family:var(--font-display);font-size:20px;font-weight:800;letter-spacing:-.05em">Projection context preview</summary><p class="muted" style="margin:10px 0 14px">A compact preview only. Use dedicated lab pages for full diagnostic review.</p>{projection_preview}</details></div><aside class="terminal-stack">{operator_guardrails_panel()}{environment_command_panel()}{model_health_panel()}{hermes_activity_feed()}</aside></section>'''

def actions():
    df = read_csv(PROJECTIONS_STAKES_CSV)
    rec, pas = _v193_split_actions(df)
    ss = slate_stats()
    body = f'''<section class="metrics">{metric_card("Recommended", ss['recommended'], "bets > 0 units")}{metric_card("Total Units", f"{ss['units']:.2f}u", "slate exposure")}{metric_card("Stake", f"{ss['stake']:.2f}", "currency units")}{metric_card("Approval", "Manual", "Hermes locked")}</section><div class="v19-section-head"><div><h2>Actions desk</h2><p>Recommended actions are separated from pass states so the operator flow stays clean.</p></div><span class="chip">Manual Approval</span></div><section class="action-section-grid"><div><div class="v19-section-head" style="margin-top:0"><div><h2>Recommended actions</h2><p>Large cards only for positive-stake recommendations.</p></div></div>{_v193_action_cards(rec, limit=8)}</div><aside><div class="v19-section-head" style="margin-top:0"><div><h2>Pass / no-play review</h2><p>Compact list. Passes should not compete visually with bets.</p></div></div>{_v193_pass_rows(pas, limit=14)}<div class="v193-page-note"><b>Audit path</b>Raw tables stay out of the main action flow. Use Diagnostics, Validation, Tracker, or Telegram for deeper checks.</div></aside></section>'''
    return page("Actions", body)

def v19_bankroll():
    bank = bankroll_snapshot(); ss = slate_stats(); df = load_bets()
    body = f'''<section class="bank-hero"><div class="bank-health"><div class="v19-eyebrow"><span class="pulse-ring"></span> Bankroll Control</div><h1>Fund discipline before bet volume.</h1><p class="v19-copy">Bankroll is the safety layer Hermes must respect. This page focuses on performance, exposure, drawdown, and guardrails — full ticket history stays in Tracker.</p></div><div class="v19-panel"><span class="muted">Current Bankroll</span><div class="bank-number">{bank['current']:.2f}u</div><div class="mission-row"><span>P/L</span><b>{bank['pl']:+.2f}u</b><em>{bank['roi']:+.1f}% ROI</em></div><div class="mission-row"><span>Open Risk</span><b>{ss['units']:.2f}u slate</b><em>{bank['pending']} open</em></div></div></section><section class="bankroll-focus-grid"><div class="bank-card"><span>Settled</span><b>{bank['settled']}</b><p>Graded bets in tracker.</p></div><div class="bank-card"><span>Wins / Losses</span><b>{bank['wins']} / {bank['losses']}</b><p>Closed ticket result count.</p></div><div class="bank-card"><span>Average Stake</span><b>{bank['avg_stake']:.2f}u</b><p>Average settled stake.</p></div><div class="bank-card"><span>Drawdown</span><b>{bank['drawdown']:.2f}u</b><p>Negative P/L pressure if any.</p></div></section>{bankroll_chart_panel(df, bank)}{bank_limit_panel()}<div class="v193-page-note"><b>Full tracker lives elsewhere</b>Bankroll does not duplicate every bet. Use Tracker for the complete bet history and ticket-level audit.</div>'''
    return body

def v19_menu():
    groups = [
      ("Core Desks", "Daily operating surfaces.", [("Dashboard","/dashboard","Mission control"),("Actions","/actions","Bet review"),("Bankroll","/bankroll","Fund control"),("Environment","/environment","Regime desk")]),
      ("Model & Validation", "Model quality, diagnostics, and learning checks.", [("Validation","/validation","CLV/results"),("Diagnostics","/diagnostics","Data integrity"),("Analysis","/analysis","Post-result analysis"),("Teams","/rankings","Team ratings")]),
      ("Research Memory", "Long-term learning and insight context.", [("Research","/research","Charts and metrics"),("Memory","/memory","Daily snapshots"),("Intelligence","/intelligence","Insight engine"),("History","/history","Projection archive")]),
      ("Outputs & Logs", "Operational output and recordkeeping.", [("Tracker","/bets","Full bet log"),("Telegram","/telegram","Message output"),("Hermes","/hermes","Agent cockpit"),("Home","/","Public website")]),
    ]
    sections=[]
    for title, desc, links in groups:
        lhtml=''.join([f'<a class="menu-link" href="{href}"><span>{title}</span><b>{name}</b><em>{note}</em></a>' for name,href,note in links])
        sections.append(f'<section class="menu-group"><h3>{title}</h3><p>{desc}</p><div class="menu-link-grid">{lhtml}</div></section>')
    return f'<div class="v19-section-head"><div><h2>Full lab menu</h2><p>Clean top navigation, grouped access to every deep route.</p></div><span class="chip">V21.8</span></div><div class="menu-group-grid">{"".join(sections)}</div>'

def v19_hermes():
    ss = slate_stats(); bank = bankroll_snapshot()
    checks = [("Research Brain", DASHBOARD_INSIGHTS_TXT.exists() or INSIGHT_REPORT_CSV.exists()), ("Hermes Cycle", DAILY_RESEARCH_SNAPSHOT_JSON.exists()), ("Environment Memory", (OUTPUT_DIR / "environment_memory_latest.csv").exists()), ("Validation Engine", (OUTPUT_DIR / "environment_validation_summary.csv").exists()), ("Hypothesis Registry", (OUTPUT_DIR / "hypothesis_registry.csv").exists()), ("Telegram Output", TELEGRAM_TXT.exists()), ("Injury Feed", False)]
    rows = ''.join([f'<div class="hermes-status-row"><b>{n}</b><span class="{"ok" if ok else "warn"}">{"Online" if ok else "Pending"}</span></div>' for n,ok in checks])
    queue = f'''<div class="hermes-queue-list"><div class="hermes-queue-row"><span>Actions</span><b>{ss['recommended']} recommendations awaiting review</b><em>Manual</em></div><div class="hermes-queue-row"><span>Exposure</span><b>{ss['units']:.2f}u current slate output</b><em>Guarded</em></div><div class="hermes-queue-row"><span>Bankroll</span><b>{bank['pl']:+.2f}u settled P/L</b><em>Observed</em></div><div class="hermes-queue-row"><span>Injuries</span><b>Feed placeholder blocks full automation</b><em>Pending</em></div></div>'''
    return f'''<main class="hermes-product"><section class="hermes-cockpit"><div class="hermes-command-card"><div class="web-eyebrow"><span class="pulse-ring"></span> Hermes Agent OS</div><h1>Automation with brakes, not shortcuts.</h1><p class="v19-copy">Hermes observes the slate, warns on risk, prepares review queues, and waits for approval. It cannot bypass bankroll, validation, injury, or discipline gates.</p><div class="v19-actions"><a class="btn primary" href="/actions">Review Actions</a><a class="btn" href="/bankroll">Bankroll Guardrails</a><a class="btn" href="/dashboard">Open Dashboard</a></div></div><aside class="v19-panel"><div class="v19-section-head" style="margin-top:0"><div><h2>Agent queue</h2><p>What Hermes is watching now.</p></div><span class="chip">Manual</span></div>{queue}</aside></section><section class="v19-workflow"><div class="workflow-step"><em>01</em><b>Observe</b><p>Read projections, staking, model health, research memory, bankroll, and environment state.</p></div><div class="workflow-step"><em>02</em><b>Warn</b><p>Flag missing files, bad regimes, overexposure, stale outputs, injury gaps, and drawdown risk.</p></div><div class="workflow-step"><em>03</em><b>Recommend</b><p>Create a review queue. Recommendations are not execution commands.</p></div><div class="workflow-step"><em>04</em><b>Approve</b><p>Operator approval remains mandatory before Telegram preparation or execution workflows.</p></div></section><section class="hermes-state"><div class="web-preview"><h3>System readiness</h3><p>Component map for the automation path.</p><div class="hermes-status-list">{rows}</div></div><div class="web-preview"><h3>Automation ladder</h3><p>Higher levels remain locked until validation and approval gates are mature.</p><div class="hermes-ladder"><div class="hermes-step active"><span>L0</span><b>Manual dashboard</b><em>Active</em></div><div class="hermes-step active"><span>L1</span><b>Mission brief</b><em>Ready</em></div><div class="hermes-step active"><span>L2</span><b>Alerts and warnings</b><em>Ready</em></div><div class="hermes-step locked"><span>L3</span><b>Suggested actions</b><em>Guarded</em></div><div class="hermes-step locked"><span>L4</span><b>Telegram preparation</b><em>Approval</em></div><div class="hermes-step locked"><span>L5</span><b>Workflow execution</b><em>Locked</em></div><div class="hermes-step locked"><span>L6</span><b>Full automation</b><em>Locked</em></div></div></div></section>{operator_guardrails_panel()}</main>'''

def v193_environment_view():
    env_json = read_json_safe(OUTPUT_DIR / "environment_regime_latest.json")
    buckets = read_csv(OUTPUT_DIR / "environment_bucket_report.csv")
    validation = read_csv(OUTPUT_DIR / "environment_validation_summary.csv")
    memory = read_csv(OUTPUT_DIR / "environment_memory_latest.csv")
    shares = pick_value(env_json, "bucket_shares", "BucketShares", default={})
    if not isinstance(shares, dict):
        shares = {}
    regime = pick_value(env_json, "environment_regime", "Regime", default="LEARNING")
    reason = pick_value(env_json, "reason", "Reason", default="Environment classification is still sample-building.")
    avg_clv = pick_value(env_json, "avg_clv", "AvgCLV", default="—")
    avg_chaos = pick_value(env_json, "avg_chaos", "AvgChaos", default="—")
    avg_trust = pick_value(env_json, "avg_trust", "AvgTrust", default="—")
    no_play = shares.get("neutral_no_play", shares.get("no_play", "—")); extreme = shares.get("extreme_over", "—"); lean = shares.get("lean_over", "—")
    b = normalize(buckets); v = normalize(validation); m = normalize(memory)
    decision = "Observational only" if str(regime).upper() in ["LEARNING", "UNKNOWN", ""] else "Review regime before approval"
    primary_warning = "Sample still building" if b.empty or len(b) < 10 else "Check bucket validation before approval"
    bucket_cols = [c for c in ["game", "environmentbucket", "edge", "confidence", "chaosscore", "trustscore", "environmentaction"] if c in b.columns]
    val_cols = [c for c in ["environmentbucket", "verdict", "sample", "graded", "winrate", "avgclv", "avgchaos", "avgtrust"] if c in v.columns]
    mem_cols = [c for c in ["environmentbucket", "memorystate", "sample", "winrate", "avgclv", "avgedge", "avgconfidence", "avgchaos", "avgtrust"] if c in m.columns]
    body = f'''<div class="env-page-hero"><div class="panel"><div class="command-kicker"><span class="pulse-ring"></span> Environment Center</div><h1 class="env-page-title">Environment intelligence for trust, chaos, and resistance.</h1><p class="env-page-copy">Projection estimates the number. Environment grades the conditions around it. This page is a decision-support layer, not a formula-changing layer.</p><div class="env-grid-clean"><div class="env-tile-clean"><span>Regime</span><b>{regime}</b></div><div class="env-tile-clean"><span>Avg Env CLV</span><b>{avg_clv}</b></div><div class="env-tile-clean"><span>Chaos</span><b>{avg_chaos}</b></div><div class="env-tile-clean"><span>Trust</span><b>{avg_trust}</b></div></div></div><div class="panel"><div class="section-head" style="margin-top:0"><div><h2>Decision summary</h2><p>{reason}</p></div><span class="chip">Observational</span></div><div class="v193-summary-grid"><div class="v193-summary-card primary"><span>Current State</span><b>{regime}</b><p>{decision}</p></div><div class="v193-summary-card warn"><span>Primary Warning</span><b>{primary_warning}</b><p>Do not let environment override staking gates.</p></div><div class="v193-summary-card"><span>No Play Share</span><b>{no_play}</b><p>Neutral/no-play bucket mix.</p></div><div class="v193-summary-card"><span>Extreme Over</span><b>{extreme}</b><p>Most aggressive bucket share.</p></div><div class="v193-summary-card"><span>Lean Over</span><b>{lean}</b><p>Secondary bucket share.</p></div></div></div></div><div class="env-panel-split"><div class="panel"><div class="section-head" style="margin-top:0"><div><h2>Bucket Report</h2><p>Game-level classification. Use as context.</p></div></div>{table(b, cols=bucket_cols, max_rows=10) if not b.empty else smart_missing('environment_bucket_report.csv')}</div><div class="panel"><div class="section-head" style="margin-top:0"><div><h2>Validation Summary</h2><p>Whether bucket labels are earning trust.</p></div></div>{table(v, cols=val_cols, max_rows=8) if not v.empty else smart_missing('environment_validation_summary.csv')}</div></div><div class="panel"><div class="section-head" style="margin-top:0"><div><h2>Environment Memory</h2><p>Longitudinal bucket memory. Observational only.</p></div><span class="chip">No Formula Changes</span></div>{table(m, cols=mem_cols, max_rows=8) if not m.empty else smart_missing('environment_memory_latest.csv')}</div>'''
    return page("Environment", body)

def v193_research_view():
    payload = research_data_payload()
    body = f'''{live_status_strip()}<div class="section-head"><div><h2>Research Desk</h2><p>Decision-oriented learning layer: what changed, what improved, what is still weak, and what Hermes should watch.</p></div><div class="toolbar"><span class="chip">Research</span><span class="chip">Learning</span><span class="chip">Guarded</span></div></div><div class="v193-summary-grid"><div class="v193-summary-card primary"><span>What Changed</span><b>Latest outputs loaded</b><p>Research charts summarize available diagnostics and sample growth.</p></div><div class="v193-summary-card"><span>What Improved</span><b>CLV / health view</b><p>Use validation before trusting new patterns.</p></div><div class="v193-summary-card warn"><span>Still Weak</span><b>Sample sensitivity</b><p>Do not promote small-sample findings into automation.</p></div><div class="v193-summary-card lock"><span>Hermes Watch</span><b>Overfit risk</b><p>Flag patterns that are not validated.</p></div><div class="v193-summary-card"><span>Mode</span><b>Observe</b><p>Research informs, it does not execute.</p></div></div>{research_metrics_html(payload)}{research_charts_html(payload)}'''
    return page("Research", body)

def v193_validation_view():
    try:
        clv_summary = read_csv(SIGNAL_CLV_SUMMARY_CSV); result_summary = read_csv(SIGNAL_RESULTS_SUMMARY_CSV); graded = read_csv(SIGNAL_GRADED_CSV); with_clv = read_csv(SIGNAL_WITH_CLV_CSV)
        if graded.empty and with_clv.empty and clv_summary.empty and result_summary.empty:
            return page("Validation", smart_missing('signal validation outputs', 'Run signal_clv_auto_v1.py and signal_result_grader_v1.py.'))
        active = normalize(graded if not graded.empty else with_clv)
        preview = active.head(12).copy()
        rows=[]
        if not preview.empty:
            for _, r in preview.iterrows():
                game, bet, market, odds = _v193_row_labels(r)
                clv = _v193_clean(_v193_pick(r, ["clv", "closinglinevalue", "closing_line_value", "clv_pct"], "—"))
                res = _v193_clean(_v193_pick(r, ["result", "grade", "outcome"], "Open"))
                conf = _v193_clean(_v193_pick(r, ["confidence", "confidence_score", "confidencescore"], "—"))
                rows.append(f'<div class="validation-row-lite"><div><span>{market}</span><b>{game}</b></div><em>{bet}</em><b>{clv}</b><b>{conf}</b><b>{res}</b></div>')
        body = f'''{live_status_strip()}<div class="section-head"><div><h2>Closed-Loop Validation</h2><p>Summary first. Raw signal dumps stay below the fold.</p></div><div class="toolbar"><span class="chip">CLV</span><span class="chip">Results</span><span class="chip">Learning</span></div></div><div class="validation-note">This page evaluates model signals, not necessarily real bets. It measures whether model quality translates into market and result performance.</div>{validation_health_cards(clv_summary, result_summary, active)}<div class="section-head"><div><h2>Signal preview</h2><p>First 12 signals only. Use summary tables for full audit.</p></div><span class="chip">Trimmed</span></div><div class="validation-compact-list">{"".join(rows) if rows else smart_missing('signal rows')}</div>'''
        body += validation_summary_section("CLV by Final Signal", clv_summary, "FinalSignal")
        body += validation_summary_section("Results by Final Signal", result_summary, "FinalSignal")
        body += '<details class="panel"><summary style="cursor:pointer;font-family:var(--font-display);font-size:20px;font-weight:800;letter-spacing:-.05em">Full signal cards</summary><p class="muted" style="margin:10px 0 14px">Expanded audit view. Kept collapsed for operator clarity.</p>' + validation_signal_cards(active.head(30)) + '</details>'
        return page("Validation", body)
    except Exception as e:
        return page("Validation Error", f'<div class="panel"><h2>Validation page error</h2><pre>{type(e).__name__}: {e}</pre></div>')

# Flask endpoint overrides for V19.4 route refinements
app.view_functions['index'] = lambda: page("Home", v19_home())
app.view_functions['dashboard'] = lambda: page("Dashboard", v19_dashboard())
app.view_functions['bankroll'] = lambda: page("Bankroll", v19_bankroll())
app.view_functions['actions'] = actions
app.view_functions['menu'] = lambda: page("Menu", v19_menu())
app.view_functions['hermes'] = lambda: page("Hermes", v19_hermes())
app.view_functions['environment'] = v193_environment_view
app.view_functions['research'] = v193_research_view
app.view_functions['validation'] = v193_validation_view

# ---- V19.4 hotfix: safe signal/execution endpoint implementations ----
# These wrappers prevent Render import-time failures and keep V19.4 features as
# additive panels on top of the stable V19.3 pages.
def v194_signal_execution_note():
    return '<section class="v19-panel terminal-section"><div class="v19-section-head" style="margin-top:0"><div><h2>Signal → Execution Intelligence</h2><p>Track one model signal separately from multiple execution fills. Bankroll counts real ticket P/L; validation should count the original model signal once.</p></div><span class="chip">V21.8</span></div><div class="v193-summary-grid"><div class="v193-summary-card primary"><span>Model Signal</span><b>One thesis</b><p>Example: Over 169.5 @ 1.91 from the model.</p></div><div class="v193-summary-card"><span>Execution Fills</span><b>Multiple tickets</b><p>Alternative lines and prices belong to execution quality.</p></div><div class="v193-summary-card warn"><span>Correlation</span><b>Grouped exposure</b><p>Multiple tickets on the same game/total should be grouped for risk.</p></div><div class="v193-summary-card"><span>Bankroll</span><b>Real P/L</b><p>Profit is calculated from actual stake and return.</p></div><div class="v193-summary-card lock"><span>Hermes</span><b>Approval only</b><p>No execution without operator approval.</p></div></div></section>'

def v194_bankroll():
    return v19_bankroll() + v194_signal_execution_note()

def v194_actions():
    df = read_csv(PROJECTIONS_STAKES_CSV)
    rec, pas = _v193_split_actions(df)
    ss = slate_stats()
    body = f'''<section class="metrics">{metric_card("Recommended", ss['recommended'], "bets > 0 units")}{metric_card("Total Units", f"{ss['units']:.2f}u", "slate exposure")}{metric_card("Stake", f"{ss['stake']:.2f}", "currency units")}{metric_card("Approval", "Manual", "Hermes locked")}</section><div class="v19-section-head"><div><h2>Actions desk</h2><p>Recommended actions are separated from pass states so the operator flow stays clean.</p></div><span class="chip">Manual Approval</span></div><section class="action-section-grid"><div><div class="v19-section-head" style="margin-top:0"><div><h2>Recommended actions</h2><p>Large cards only for positive-stake recommendations.</p></div></div>{_v193_action_cards(rec, limit=8)}</div><aside><div class="v19-section-head" style="margin-top:0"><div><h2>Pass / no-play review</h2><p>Compact list. Passes should not compete visually with bets.</p></div></div>{_v193_pass_rows(pas, limit=14)}<div class="v193-page-note"><b>Audit path</b>Raw tables stay out of the main action flow. Use Diagnostics, Validation, Tracker, or Telegram for deeper checks.</div></aside></section>'''
    body += v194_signal_execution_note()
    return page("Actions", body)

def v194_hermes():
    ss = slate_stats(); bank = bankroll_snapshot()
    note = v194_signal_execution_note()
    return v19_hermes() + note

def v194_bets_view():
    return bets() + v194_signal_execution_note()

# V19.4 endpoint overrides
app.view_functions['bankroll'] = lambda: page("Bankroll", v194_bankroll())
app.view_functions['actions'] = v194_actions
app.view_functions['hermes'] = lambda: page("Hermes", v194_hermes())
app.view_functions['bets'] = v194_bets_view



# ---- V21.8 advisory display upgrade ----
V21_SUMMARY_JSON = OUTPUT_DIR / "v21_8_advisory_cycle_summary.json"
V21_ADVISORY_SCORES_CSV = OUTPUT_DIR / "model_advisory_scores_v21.csv"
V21_ADVISORY_QUEUE_CSV = OUTPUT_DIR / "hermes_advisory_queue_v21.csv"


def _v21_json(path, default=None):
    default = {} if default is None else default
    try:
        if not Path(path).exists() or Path(path).stat().st_size == 0:
            return default
        return json.loads(Path(path).read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return default


def _v21_clean(value, default="-"):
    if value is None:
        return default
    if isinstance(value, bool):
        return "YES" if value else "NO"
    if isinstance(value, float):
        return f"{value:.2f}"
    text = str(value)
    if text.lower() in ["nan", "none", ""]:
        return default
    return html.escape(text)


def _v21_summary():
    summary = _v21_json(V21_SUMMARY_JSON, {})
    team_n = count_rows(OUTPUT_DIR / "team_features_v21.csv")
    player_n = count_rows(OUTPUT_DIR / "player_features_v21.csv")
    market_n = count_rows(OUTPUT_DIR / "market_features_v21.csv")
    game_n = count_rows(OUTPUT_DIR / "game_model_features_v21.csv")
    advisory_n = count_rows(V21_ADVISORY_SCORES_CSV)
    queue_n = count_rows(V21_ADVISORY_QUEUE_CSV)
    backtest_n = count_rows(OUTPUT_DIR / "model_backtest_v21.csv")
    validated_n = count_rows(OUTPUT_DIR / "validated_model_changes_v21.csv")
    feature_rows = dict(summary.get("feature_rows", {}) or {})
    advisory_rows = dict(summary.get("advisory_rows", {}) or {})
    backtest_rows = dict(summary.get("backtest_rows", {}) or {})
    feature_rows["team_features"] = team_n or feature_rows.get("team_features", 0)
    feature_rows["player_features"] = player_n or feature_rows.get("player_features", 0)
    feature_rows["market_features"] = market_n or feature_rows.get("market_features", 0)
    feature_rows["game_model_features"] = game_n or feature_rows.get("game_model_features", 0)
    advisory_rows["advisory_scores"] = advisory_n or advisory_rows.get("advisory_scores", 0)
    advisory_rows["hermes_advisory_queue"] = queue_n or advisory_rows.get("hermes_advisory_queue", 0)
    backtest_rows["backtest"] = backtest_n or backtest_rows.get("backtest", 0)
    backtest_rows["validated_changes"] = validated_n or backtest_rows.get("validated_changes", 0)
    labels = dict(summary.get("advisory_labels", {}) or {})
    if not labels:
        df = read_csv(V21_ADVISORY_SCORES_CSV)
        if not df.empty:
            norm = normalize(df)
            col = first_existing_col(norm, ["advisory_label", "label", "advisorylabel"])
            if col:
                labels = norm[col].astype(str).str.upper().value_counts().to_dict()
    risks = dict(summary.get("advisory_risk_flags", {}) or {})
    readiness = dict(summary.get("fetch_readiness", {}) or {})
    locks = summary.get("locks", []) or ["ENVIRONMENT_SAMPLE_LOCK", "INJURY_CONFIRMATION_LOCK", "MANUAL_APPROVAL_REQUIRED", "MODEL_SAMPLE_LOCK"]
    if "INJURY_CONFIRMATION_LOCK" not in locks:
        locks = list(locks) + ["INJURY_CONFIRMATION_LOCK"]
    return {
        "status": summary.get("status", "OK" if summary else "READY"),
        "fetch_state": summary.get("fetch_state", "OK_WITH_WARNINGS"),
        "mode": summary.get("mode", "manual_approval"),
        "feature_rows": feature_rows,
        "backtest_rows": backtest_rows,
        "advisory_rows": advisory_rows,
        "advisory_labels": labels,
        "risk_flags": risks,
        "readiness": readiness,
        "locks": locks,
        "approval_queue": summary.get("approval_queue", count_rows(OUTPUT_DIR / "hermes_approval_queue_v20.csv")),
    }


def _v21_metric(label, value, caption="", klass=""):
    return f'<div class="v19-kpi {klass}"><span>{_v21_clean(label)}</span><b>{_v21_clean(value)}</b><p>{_v21_clean(caption)}</p></div>'


def _v21_pairs(title, data, empty="No rows yet"):
    if not data:
        return f'<div class="mission-row"><span>{_v21_clean(title)}</span><b>{_v21_clean(empty)}</b><em>Watch</em></div>'
    rows = []
    for k, v in data.items():
        label = str(k).replace("_", " ").title()[:24]
        rows.append(f'<div class="mission-row"><span>{_v21_clean(label)}</span><b>{_v21_clean(v)}</b><em>V21.8</em></div>')
    return ''.join(rows)


def v21_8_advisory_panel():
    s = _v21_summary()
    f = s["feature_rows"]; b = s["backtest_rows"]; a = s["advisory_rows"]
    labels = s["advisory_labels"]
    risks = s["risk_flags"]
    readiness = s["readiness"]
    odds_ready = readiness.get("odds_ready")
    props_ready = readiness.get("player_props_market_ready")
    odds_caption = "Live odds ready" if odds_ready else "Add ODDS_API_KEY for live odds/props"
    props_caption = "Props market ready" if props_ready else "Props market still guarded/unavailable"
    lock_rows = ''.join(f'<span class="approval-pill locked">{_v21_clean(x)}</span>' for x in s["locks"])
    mode_label = str(s['mode']).replace('_',' ').title()
    return f'''<section class="v19-panel" style="border-color:rgba(0,200,240,.18);background:radial-gradient(circle at 86% 0%,rgba(0,200,240,.08),transparent 34%),var(--v19-glass)">
      <div class="v19-section-head" style="margin-top:0"><div><h2>V21.8 advisory cycle</h2><p>Latest safe-cycle outputs. Advisory only: no auto-betting, no formula replacement, no staking or threshold changes.</p></div><span class="chip">{_v21_clean(s['status'])}</span></div>
      <div class="v19-grid-4">
        {_v21_metric('Mode', mode_label, 'Hermes waits for approval')}
        {_v21_metric('Advisory Scores', a.get('advisory_scores', 0), 'Queue ' + str(a.get('hermes_advisory_queue', 0)))}
        {_v21_metric('Backtest Rows', b.get('backtest', 0), 'Validated/manual-review ' + str(b.get('validated_changes', 0)))}
        {_v21_metric('Feature Rows', 'T{} / P{}'.format(f.get('team_features',0), f.get('player_features',0)), 'Market {} · Games {}'.format(f.get('market_features',0), f.get('game_model_features',0)))}
      </div>
      <div class="v19-grid-3" style="margin-top:12px">
        <div class="v19-panel"><span class="muted">Advisory labels</span>{_v21_pairs('Labels', labels, 'No advisory labels')}</div>
        <div class="v19-panel"><span class="muted">Risk flags</span>{_v21_pairs('Risk', risks, 'No risk flags')}</div>
        <div class="v19-panel"><span class="muted">Market readiness</span><div class="mission-row"><span>Odds</span><b>{_v21_clean(odds_ready)}</b><em>{_v21_clean(odds_caption)}</em></div><div class="mission-row"><span>Props</span><b>{_v21_clean(props_ready)}</b><em>{_v21_clean(props_caption)}</em></div><div class="mission-row"><span>Fetch</span><b>{_v21_clean(s['fetch_state'])}</b><em>Live data</em></div></div>
      </div>
      <div class="approval-rail" style="margin-top:12px">{lock_rows}<span class="approval-pill locked">NO AUTO-BETTING</span><span class="approval-pill warn">NO FORMULA/STAKING/THRESHOLD CHANGE</span></div>
    </section>'''


def v21_8_home():
    ss = slate_stats(); bank = bankroll_snapshot(); s = _v21_summary()
    a = s["advisory_rows"]; b = s["backtest_rows"]
    return f'''<main class="v19-home"><section class="v19-hero"><div class="v19-hero-grid"><div><div class="v19-eyebrow"><span class="pulse-ring"></span> WNBA Edge Lab · V21.8</div><h1 class="v19-title">Advisory cycle live with manual approval discipline.</h1><p class="v19-copy">V21.8 combines official WNBA data, SportsDataverse backfill, feature diagnostics, backtesting, advisory scoring, and Hermes review queues. It is advisory-only: no auto-betting and no formula, staking, or threshold changes.</p><div class="v19-actions"><a class="btn primary" href="/dashboard">Open V21.8 Dashboard</a><a class="btn" href="/actions">Review Actions</a><a class="btn" href="/hermes">Hermes Locks</a></div></div><div class="v19-side"><div class="v19-kpi"><span>Advisory</span><b>{a.get('advisory_scores', ss['recommended'])}</b><p>Scored advisory actions.</p></div><div class="v19-kpi"><span>Approval Queue</span><b>{s.get('approval_queue', 0)}</b><p>Manual approvals required.</p></div><div class="v19-kpi"><span>Backtest</span><b>{b.get('backtest', 0)}</b><p>Validation rows retained.</p></div><div class="v19-kpi"><span>Bankroll P/L</span><b>{bank['pl']:+.2f}u</b><p>Settled tracker performance.</p></div></div></div></section>{v21_8_advisory_panel()}<section><div class="v19-section-head"><div><h2>V21.8 operating desks</h2><p>The public site now reflects the deployed V21.8 advisory workflow.</p></div><span class="chip">V21.8</span></div><div class="v19-grid-4"><a class="v19-card" href="/dashboard"><span>Terminal</span><b>Operator Dashboard</b><p>V21.8 summary, action queue, guardrails, and model context.</p></a><a class="v19-card" href="/actions"><span>Advisory</span><b>Review Desk</b><p>Recommended actions and pass states remain manual review only.</p></a><a class="v19-card" href="/bankroll"><span>Fund</span><b>Bankroll Control</b><p>Exposure and drawdown gates stay separate from model logic.</p></a><a class="v19-card" href="/hermes"><span>Agent</span><b>Hermes Manual Approval</b><p>Observe, warn, recommend, and wait for operator approval.</p></a></div></section></main>'''


def v21_8_dashboard():
    proj = read_csv(PROJECTIONS_CSV)
    stakes = read_csv(PROJECTIONS_STAKES_CSV)
    rec, _ = _v193_split_actions(stakes)
    display_actions = rec if not rec.empty else _norm(stakes)
    projection_preview = projection_cards(proj.head(4) if hasattr(proj, 'head') else proj)
    return f'''{v21_8_advisory_panel()}{command_center_hero(proj, stakes)}{v192_command_strip()}<section class="terminal-layout"><div class="terminal-stack">{v192_operator_brief()}<div class="v19-section-head"><div><h2>Top advisory queue</h2><p>V21.8 actions are recommendations only. Operator approval remains mandatory.</p></div><a class="chip" href="/actions">Open Actions</a></div>{_v193_action_cards(display_actions, limit=3)}<details class="panel"><summary style="cursor:pointer;font-family:var(--font-display);font-size:20px;font-weight:800;letter-spacing:-.05em">Projection context preview</summary><p class="muted" style="margin:10px 0 14px">A compact preview only. Use dedicated lab pages for full diagnostic review.</p>{projection_preview}</details></div><aside class="terminal-stack">{operator_guardrails_panel()}{environment_command_panel()}{model_health_panel()}{hermes_activity_feed()}</aside></section>'''

# V21.8 endpoint display overrides. These are presentation-only and do not touch formulas, staking, thresholds, or execution.
app.view_functions['index'] = lambda: page("Home", v21_8_home())
app.view_functions['dashboard'] = lambda: page("Dashboard", v21_8_dashboard())

if __name__ == "__main__":
    print("Starting WNBA Edge Lab V21.8 advisory dashboard...")
    print("Open http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
