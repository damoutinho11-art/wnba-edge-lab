from __future__ import annotations

import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

ROOT = Path(__file__).resolve().parent
OUTPUT_DIR = ROOT / "wnba_outputs"

OUT_AUDIT_CSV = OUTPUT_DIR / "model_audit_v20.csv"
OUT_SUMMARY_JSON = OUTPUT_DIR / "model_audit_summary_v20.json"
OUT_RECOMMENDATIONS_TXT = OUTPUT_DIR / "model_upgrade_recommendations_v20.txt"

FILES = {
    "projections": OUTPUT_DIR / "projections.csv",
    "projections_with_stakes": OUTPUT_DIR / "projections_with_stakes.csv",
    "recommended_bets": OUTPUT_DIR / "recommended_bets.csv",
    "model_health": OUTPUT_DIR / "model_health_report.csv",
    "signal_clv_summary": OUTPUT_DIR / "signal_clv_summary.csv",
    "signal_results_summary": OUTPUT_DIR / "signal_results_summary.csv",
    "signal_tracker_graded": OUTPUT_DIR / "signal_tracker_graded.csv",
    "environment_validation": OUTPUT_DIR / "environment_validation_summary.csv",
    "environment_bucket": OUTPUT_DIR / "environment_bucket_report.csv",
    "signal_execution_groups": OUTPUT_DIR / "signal_execution_groups_v20.csv",
    "signal_execution_summary": OUTPUT_DIR / "signal_execution_summary_v20.csv",
    "hermes_state": OUTPUT_DIR / "hermes_state_v20.json",
    "bet_tracker": ROOT / "bet_tracker.csv",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except Exception:
        return pd.DataFrame()


def safe_read_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def norm_cols(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]
    return out


def first_existing(df: pd.DataFrame, names: List[str]) -> Optional[str]:
    if df.empty:
        return None
    lower_map = {str(c).lower(): c for c in df.columns}
    for name in names:
        if name in df.columns:
            return name
        if name.lower() in lower_map:
            return lower_map[name.lower()]
    return None


def num_series(df: pd.DataFrame, names: List[str]) -> pd.Series:
    col = first_existing(df, names)
    if col is None:
        return pd.Series(dtype="float64")
    return pd.to_numeric(df[col], errors="coerce")


def text_series(df: pd.DataFrame, names: List[str]) -> pd.Series:
    col = first_existing(df, names)
    if col is None:
        return pd.Series(dtype="object")
    return df[col].astype(str)


def value_from_metric_df(df: pd.DataFrame, metric_name: str) -> Optional[float]:
    if df.empty or "Metric" not in df.columns or "Value" not in df.columns:
        return None
    sub = df[df["Metric"].astype(str).str.lower() == metric_name.lower()]
    if sub.empty:
        return None
    return pd.to_numeric(sub["Value"], errors="coerce").dropna().head(1).iloc[0] if not pd.to_numeric(sub["Value"], errors="coerce").dropna().empty else None


def add_row(rows: List[Dict[str, Any]], area: str, metric: str, value: Any, status: str, severity: str, recommendation: str, details: str = "") -> None:
    rows.append({
        "RunTimestamp": now_iso(),
        "Area": area,
        "Metric": metric,
        "Value": value,
        "Status": status,
        "Severity": severity,
        "Recommendation": recommendation,
        "Details": details,
    })


def status_by_threshold(value: Optional[float], good: float, warn: float, higher_is_better: bool = True) -> Tuple[str, str]:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return "UNKNOWN", "MEDIUM"
    if higher_is_better:
        if value >= good:
            return "GOOD", "LOW"
        if value >= warn:
            return "WATCH", "MEDIUM"
        return "WEAK", "HIGH"
    else:
        if value <= good:
            return "GOOD", "LOW"
        if value <= warn:
            return "WATCH", "MEDIUM"
        return "WEAK", "HIGH"


def audit_files(rows: List[Dict[str, Any]], loaded: Dict[str, pd.DataFrame], jsons: Dict[str, Dict[str, Any]]) -> None:
    missing = []
    for name, path in FILES.items():
        if name == "hermes_state":
            ok = bool(jsons.get(name))
        else:
            ok = path.exists() and not loaded.get(name, pd.DataFrame()).empty
        if not ok:
            missing.append(name)
    add_row(
        rows,
        "Data Integrity",
        "Required files available",
        f"{len(FILES) - len(missing)}/{len(FILES)}",
        "GOOD" if not missing else "WATCH",
        "LOW" if not missing else "MEDIUM",
        "Keep all V20 support outputs generated before dashboard/Hermes review.",
        "Missing or unreadable: " + (", ".join(missing) if missing else "none"),
    )


def audit_projection_layer(rows: List[Dict[str, Any]], projections: pd.DataFrame, recs: pd.DataFrame, staked: pd.DataFrame) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    if projections.empty:
        add_row(rows, "Projection Layer", "Projection rows", 0, "WEAK", "HIGH", "Run core projection engine before audit.")
        return summary

    slate_count = len(projections)
    edge = num_series(projections, ["edge", "Edge"])
    confidence = num_series(projections, ["confidence", "Confidence"])
    signal = text_series(projections, ["FinalSignalNormalized", "signal", "Signal"])
    market_line = num_series(projections, ["market_line", "MarketLine", "LineAtSignal"])
    projection = num_series(projections, ["projection", "Projection"])

    action_count = len(recs) if not recs.empty else 0
    pass_count = int(signal.str.upper().str.contains("PASS", na=False).sum()) if not signal.empty else 0
    avg_abs_edge = float(edge.abs().mean()) if not edge.dropna().empty else None
    max_abs_edge = float(edge.abs().max()) if not edge.dropna().empty else None
    avg_conf = float(confidence.mean()) if not confidence.dropna().empty else None
    projection_spread = float((projection - market_line).abs().mean()) if not projection.dropna().empty and not market_line.dropna().empty else None

    summary.update({
        "slate_games": slate_count,
        "recommended_actions": action_count,
        "pass_count": pass_count,
        "avg_abs_edge": avg_abs_edge,
        "max_abs_edge": max_abs_edge,
        "avg_confidence": avg_conf,
        "avg_projection_market_gap": projection_spread,
    })

    add_row(rows, "Projection Layer", "Slate games", slate_count, "GOOD" if slate_count > 0 else "WEAK", "LOW" if slate_count > 0 else "HIGH", "Maintain slate coverage and verify all scheduled games appear.")
    add_row(rows, "Projection Layer", "Recommended actions", action_count, "GOOD" if action_count <= max(1, slate_count // 2) else "WATCH", "LOW" if action_count <= max(1, slate_count // 2) else "MEDIUM", "Avoid bet volume expansion until CLV/sample improves.")
    s, sev = status_by_threshold(avg_conf, 60, 45, True)
    add_row(rows, "Projection Layer", "Average confidence", round(avg_conf, 2) if avg_conf is not None else "unknown", s, sev, "Improve confidence calibration with injury/minutes/rest/market features.")
    s, sev = status_by_threshold(avg_abs_edge, 3.0, 1.5, True)
    add_row(rows, "Projection Layer", "Average absolute edge", round(avg_abs_edge, 2) if avg_abs_edge is not None else "unknown", s, sev, "Use edge distribution to identify whether the model is too flat or too aggressive.")

    if not staked.empty:
        units = num_series(staked, ["SuggestedUnits", "SuggestedUnitsRaw"])
        slate_cap = text_series(staked, ["SlateCapApplied"])
        total_units = float(units.sum()) if not units.dropna().empty else 0.0
        cap_applied = int(slate_cap.str.lower().isin(["true", "1", "yes"]).sum()) if not slate_cap.empty else 0
        summary["suggested_total_units"] = total_units
        summary["slate_cap_applied_count"] = cap_applied
        add_row(rows, "Staking Layer", "Suggested total units", round(total_units, 3), "GOOD" if total_units <= 2.5 else "WATCH", "LOW" if total_units <= 2.5 else "MEDIUM", "Keep slate-level exposure capped until sample reliability improves.")
        add_row(rows, "Staking Layer", "Slate cap applied", cap_applied, "GOOD" if cap_applied == 0 else "WATCH", "LOW" if cap_applied == 0 else "MEDIUM", "Slate cap is a safety feature; if it triggers often, tune upstream bet volume/edge thresholds.")

    return summary


def audit_health_and_validation(rows: List[Dict[str, Any]], health: pd.DataFrame, clv: pd.DataFrame, results: pd.DataFrame, graded: pd.DataFrame) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    if not health.empty:
        h = health.iloc[0].to_dict()
        score = pd.to_numeric(pd.Series([h.get("ModelHealthScore")]), errors="coerce").iloc[0]
        avg_clv = pd.to_numeric(pd.Series([h.get("AvgCLV")]), errors="coerce").iloc[0]
        beat_close = pd.to_numeric(pd.Series([h.get("BeatCloseRate")]), errors="coerce").iloc[0]
        winrate = pd.to_numeric(pd.Series([h.get("SignalWinRate")]), errors="coerce").iloc[0]
        graded_n = pd.to_numeric(pd.Series([h.get("GradedSignals")]), errors="coerce").iloc[0]
        sample_n = pd.to_numeric(pd.Series([h.get("SampleSize")]), errors="coerce").iloc[0]
        label = str(h.get("HealthLabel", "UNKNOWN"))
        summary.update({"health_score": float(score) if not pd.isna(score) else None, "health_label": label, "avg_clv": float(avg_clv) if not pd.isna(avg_clv) else None, "beat_close_rate": float(beat_close) if not pd.isna(beat_close) else None, "signal_win_rate": float(winrate) if not pd.isna(winrate) else None, "graded_signals": int(graded_n) if not pd.isna(graded_n) else 0, "sample_size": int(sample_n) if not pd.isna(sample_n) else 0})
        s, sev = status_by_threshold(score if not pd.isna(score) else None, 70, 50, True)
        add_row(rows, "Model Health", "Health score", round(float(score), 2) if not pd.isna(score) else "unknown", s, sev, "Keep formula frozen while adding audit-only features until sample is reliable.", f"Health label: {label}")
        s, sev = status_by_threshold(sample_n if not pd.isna(sample_n) else None, 50, 20, True)
        add_row(rows, "Model Health", "Sample size", int(sample_n) if not pd.isna(sample_n) else "unknown", s, sev, "Do not promote automation level while model sample is low.")
        s, sev = status_by_threshold(beat_close if not pd.isna(beat_close) else None, 52, 40, True)
        add_row(rows, "CLV", "Beat-close rate", round(float(beat_close), 2) if not pd.isna(beat_close) else "unknown", s, sev, "Prioritize CLV improvement before increasing stake aggression.")
        s, sev = status_by_threshold(avg_clv if not pd.isna(avg_clv) else None, 0.25, 0.0, True)
        add_row(rows, "CLV", "Average CLV points", round(float(avg_clv), 3) if not pd.isna(avg_clv) else "unknown", s, sev, "Track CLV by market, team, environment, and signal grade.")
        s, sev = status_by_threshold(winrate if not pd.isna(winrate) else None, 55, 50, True)
        add_row(rows, "Results", "Signal win rate", round(float(winrate), 2) if not pd.isna(winrate) else "unknown", s, sev, "Treat win rate as secondary to CLV until larger sample exists.")
    else:
        add_row(rows, "Model Health", "Health report", "missing", "WEAK", "HIGH", "Run model_health_engine before V20 audit.")

    if not clv.empty:
        overall = clv[clv["Group"].astype(str).str.lower().eq("overall")] if "Group" in clv.columns else pd.DataFrame()
        if not overall.empty:
            r = overall.iloc[0]
            add_row(rows, "CLV", "Signals with CLV", int(pd.to_numeric(pd.Series([r.get("SignalsWithCLV")]), errors="coerce").fillna(0).iloc[0]), "GOOD", "LOW", "Continue expanding closing-line tracking coverage.")
    if not graded.empty:
        result_status = text_series(graded, ["ResultStatus"])
        final_signal = text_series(graded, ["FinalSignal"])
        open_count = int(result_status.str.upper().eq("OPEN").sum()) if not result_status.empty else 0
        graded_count = int(result_status.str.upper().eq("GRADED").sum()) if not result_status.empty else 0
        pass_count = int(final_signal.str.upper().eq("PASS").sum()) if not final_signal.empty else 0
        add_row(rows, "Signal Tracker", "Open signals", open_count, "WATCH" if open_count else "GOOD", "MEDIUM" if open_count else "LOW", "Open signals are expected in active slates; ensure they do not pollute graded model quality.")
        add_row(rows, "Signal Tracker", "PASS signals tracked", pass_count, "GOOD", "LOW", "Keep PASS decisions tracked for discipline analysis, but separate them from bet-action performance.")
    return summary


def audit_environment(rows: List[Dict[str, Any]], env_val: pd.DataFrame, env_bucket: pd.DataFrame) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    if env_val.empty:
        add_row(rows, "Environment", "Environment validation", "missing", "WATCH", "MEDIUM", "Run environment validation before trusting bucket-level rules.")
        return summary
    sample = num_series(env_val, ["Sample"])
    graded = num_series(env_val, ["GradedSample"])
    avg_sample = float(sample.sum()) if not sample.dropna().empty else 0.0
    graded_total = float(graded.sum()) if not graded.dropna().empty else 0.0
    low_sample = 0
    if "Verdict" in env_val.columns:
        low_sample = int(env_val["Verdict"].astype(str).str.upper().str.contains("LOW SAMPLE", na=False).sum())
    summary.update({"environment_buckets": len(env_val), "environment_total_sample": avg_sample, "environment_graded_sample": graded_total, "environment_low_sample_buckets": low_sample})
    s, sev = status_by_threshold(graded_total, 20, 5, True)
    add_row(rows, "Environment", "Graded environment sample", int(graded_total), s, sev, "Keep environment as advisory until graded sample grows.")
    add_row(rows, "Environment", "Low-sample buckets", low_sample, "WATCH" if low_sample else "GOOD", "MEDIUM" if low_sample else "LOW", "Do not let bucket labels increase stake size until validation clears sample gate.")
    if not env_bucket.empty:
        buckets = text_series(env_bucket, ["EnvironmentBucket"])
        no_play = int(buckets.str.upper().str.contains("NO PLAY", na=False).sum()) if not buckets.empty else 0
        extreme = int(buckets.str.upper().str.contains("EXTREME", na=False).sum()) if not buckets.empty else 0
        summary.update({"current_no_play_games": no_play, "current_extreme_bucket_games": extreme})
        add_row(rows, "Environment", "Current no-play bucket games", no_play, "GOOD" if no_play >= 0 else "UNKNOWN", "LOW", "Use no-play bucket as a warning layer, not an auto-decision layer.")
        add_row(rows, "Environment", "Current extreme bucket games", extreme, "WATCH" if extreme else "GOOD", "MEDIUM" if extreme else "LOW", "Extreme bucket should require extra CLV/injury confirmation before approval.")
    return summary


def audit_execution_layer(rows: List[Dict[str, Any]], groups: pd.DataFrame, summary_df: pd.DataFrame, bet_tracker: pd.DataFrame) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    if groups.empty:
        add_row(rows, "Execution", "Signal execution groups", "missing", "WATCH", "MEDIUM", "Run signal_execution_bridge_v20.py before audit.")
        return summary
    tickets = num_series(groups, ["ExecutionTickets"])
    profit = num_series(groups, ["NetProfit"])
    stake = num_series(groups, ["TotalStake"])
    roi = num_series(groups, ["ROI_Percent"])
    exposure = text_series(groups, ["ExposureLabel"])
    source = text_series(groups, ["ModelSource"])
    total_groups = len(groups)
    total_tickets = int(tickets.sum()) if not tickets.dropna().empty else total_groups
    net_profit = float(profit.sum()) if not profit.dropna().empty else 0.0
    total_stake = float(stake.sum()) if not stake.dropna().empty else 0.0
    grouped = int((tickets.fillna(1) > 1).sum()) if not tickets.empty else 0
    unmatched = int(source.str.lower().eq("unmatched").sum()) if not source.empty else 0
    corr = int(exposure.str.upper().str.contains("CORRELATED|LADDER|GROUP", na=False).sum()) if not exposure.empty else 0
    avg_roi = float(roi.mean()) if not roi.dropna().empty else None
    summary.update({"execution_groups": total_groups, "execution_tickets": total_tickets, "execution_net_profit": net_profit, "execution_total_stake": total_stake, "multi_fill_groups": grouped, "unmatched_execution_groups": unmatched, "correlated_exposure_groups": corr, "avg_execution_roi_percent": avg_roi})
    add_row(rows, "Execution", "Signal execution groups", total_groups, "GOOD", "LOW", "Use grouped accounting for validation and bankroll intelligence.")
    add_row(rows, "Execution", "Execution tickets", total_tickets, "GOOD", "LOW", "Ticket count belongs to execution/bankroll, not model-signal count.")
    add_row(rows, "Execution", "Net execution P/L", round(net_profit, 3), "GOOD" if net_profit >= 0 else "WATCH", "LOW" if net_profit >= 0 else "MEDIUM", "Separate profitability from model validation because execution fills can differ from model line.")
    add_row(rows, "Execution", "Multi-fill signal groups", grouped, "WATCH" if grouped else "GOOD", "MEDIUM" if grouped else "LOW", "Multi-fill groups are acceptable when line shopping is intentional; Hermes should flag correlated exposure.")
    add_row(rows, "Execution", "Unmatched execution groups", unmatched, "WATCH" if unmatched else "GOOD", "MEDIUM" if unmatched else "LOW", "Add signal_id/correlation_group to bet tracker so all fills link to model signals.")
    if not bet_tracker.empty:
        status = text_series(bet_tracker, ["Status"])
        open_bets = int(status.str.upper().eq("OPEN").sum()) if not status.empty else 0
        add_row(rows, "Bankroll", "Open tracked bets", open_bets, "WATCH" if open_bets else "GOOD", "MEDIUM" if open_bets else "LOW", "Open bets should feed exposure limits and Hermes approval locks.")
    return summary


def audit_hermes(rows: List[Dict[str, Any]], state: Dict[str, Any]) -> Dict[str, Any]:
    summary: Dict[str, Any] = {}
    if not state:
        add_row(rows, "Hermes", "Hermes state", "missing", "WEAK", "HIGH", "Run hermes_state_builder_v20.py before agent integration.")
        return summary
    auto = state.get("automation", {}) if isinstance(state.get("automation"), dict) else {}
    approval = state.get("approval_queue", {}) if isinstance(state.get("approval_queue"), dict) else {}
    warnings = state.get("warnings", {}) if isinstance(state.get("warnings"), dict) else {}
    mode = auto.get("mode", state.get("mode", "unknown"))
    locks = auto.get("active_locks", []) or state.get("locks", []) or []
    approval_count = approval.get("count", 0) if isinstance(approval, dict) else 0
    warning_count = warnings.get("count", 0) if isinstance(warnings, dict) else 0
    high_count = warnings.get("high", 0) if isinstance(warnings, dict) else 0
    summary.update({"hermes_mode": mode, "hermes_locks": locks, "approval_queue_count": approval_count, "warning_count": warning_count, "high_warning_count": high_count})
    add_row(rows, "Hermes", "Automation mode", mode, "GOOD" if str(mode).lower() == "manual_approval" else "WATCH", "LOW" if str(mode).lower() == "manual_approval" else "HIGH", "Keep Hermes in manual approval until model/environment/injury gates are validated.")
    add_row(rows, "Hermes", "Approval queue", approval_count, "WATCH" if approval_count else "GOOD", "MEDIUM" if approval_count else "LOW", "Operator must approve/reject each queued action before Telegram or execution workflow.")
    add_row(rows, "Hermes", "Active locks", ", ".join(map(str, locks)) if locks else "none", "WATCH" if locks else "GOOD", "MEDIUM" if locks else "LOW", "Locks should block automation, not dashboard visibility.")
    add_row(rows, "Hermes", "High warnings", high_count, "WEAK" if high_count else "GOOD", "HIGH" if high_count else "LOW", "High warnings should prevent approvals until resolved.")
    return summary


def build_recommendations(summary: Dict[str, Any], audit_rows: List[Dict[str, Any]]) -> str:
    lines: List[str] = []
    lines.append("WNBA EDGE LAB — V20 MODEL UPGRADE RECOMMENDATIONS")
    lines.append("Generated: " + now_iso())
    lines.append("")
    lines.append("Priority 1 — Signal IDs and execution linking")
    lines.append("- Add signal_id to projections_with_stakes.csv, recommended_bets.csv, bet_tracker.csv, signal_tracker files, and Hermes approval queue.")
    lines.append("- Treat model quality as 1 signal, while bankroll quality tracks all execution fills.")
    lines.append("- Add correlation_group and execution_group_id to every ticket.")
    lines.append("")
    lines.append("Priority 2 — CLV coverage and market movement")
    lines.append("- Capture open/current/close totals and odds for every model signal.")
    lines.append("- Track CLV in points and odds separately.")
    lines.append("- Add CLV by signal grade, environment bucket, team pair, and market.")
    lines.append("")
    lines.append("Priority 3 — Injury and minutes features")
    lines.append("- Add injury_status, starter_out_count, questionable_count, minutes_missing_estimate, usage_missing_estimate, and injury_uncertainty_score.")
    lines.append("- Hermes should lock approval when injury uncertainty is high or injury feed is stale.")
    lines.append("")
    lines.append("Priority 4 — Rest/travel and schedule features")
    lines.append("- Add days_rest, back_to_back, third_game_in_four, road_trip_game_number, home_stand, and travel_distance_proxy.")
    lines.append("- Audit totals performance by rest/travel regime.")
    lines.append("")
    lines.append("Priority 5 — Environment validation gate")
    lines.append("- Keep environment advisory while sample is low.")
    lines.append("- Do not increase stake from environment labels until bucket-level graded sample is strong.")
    lines.append("")
    lines.append("Priority 6 — Model formula discipline")
    lines.append("- Do not change staking thresholds or projection formula yet.")
    lines.append("- Build features and audits beside the current model, validate, then promote changes only after evidence.")
    lines.append("")
    high_or_medium = [r for r in audit_rows if str(r.get("Severity", "")).upper() in {"HIGH", "MEDIUM"}]
    lines.append("Current audit watch items:")
    if high_or_medium:
        for r in high_or_medium[:20]:
            lines.append(f"- [{r.get('Severity')}] {r.get('Area')} / {r.get('Metric')}: {r.get('Value')} -> {r.get('Recommendation')}")
    else:
        lines.append("- No medium/high watch items detected.")
    lines.append("")
    lines.append("Hermes rule:")
    lines.append("- Manual approval remains mandatory. No auto-betting, no auto-Telegram send, no bypassing bankroll/model/environment/injury locks.")
    return "\n".join(lines) + "\n"


def run() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    loaded = {name: norm_cols(safe_read_csv(path)) for name, path in FILES.items() if name != "hermes_state"}
    jsons = {"hermes_state": safe_read_json(FILES["hermes_state"])}

    rows: List[Dict[str, Any]] = []
    summary: Dict[str, Any] = {"updated_at": now_iso(), "status": "OK"}

    audit_files(rows, loaded, jsons)
    summary["projection_layer"] = audit_projection_layer(rows, loaded.get("projections", pd.DataFrame()), loaded.get("recommended_bets", pd.DataFrame()), loaded.get("projections_with_stakes", pd.DataFrame()))
    summary["health_validation"] = audit_health_and_validation(rows, loaded.get("model_health", pd.DataFrame()), loaded.get("signal_clv_summary", pd.DataFrame()), loaded.get("signal_results_summary", pd.DataFrame()), loaded.get("signal_tracker_graded", pd.DataFrame()))
    summary["environment"] = audit_environment(rows, loaded.get("environment_validation", pd.DataFrame()), loaded.get("environment_bucket", pd.DataFrame()))
    summary["execution"] = audit_execution_layer(rows, loaded.get("signal_execution_groups", pd.DataFrame()), loaded.get("signal_execution_summary", pd.DataFrame()), loaded.get("bet_tracker", pd.DataFrame()))
    summary["hermes"] = audit_hermes(rows, jsons.get("hermes_state", {}))

    audit_df = pd.DataFrame(rows)
    if not audit_df.empty:
        severity_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        audit_df["SeverityRank"] = audit_df["Severity"].map(severity_order).fillna(9)
        audit_df = audit_df.sort_values(["SeverityRank", "Area", "Metric"]).drop(columns=["SeverityRank"])
    audit_df.to_csv(OUT_AUDIT_CSV, index=False)

    counts = audit_df["Severity"].value_counts().to_dict() if not audit_df.empty else {}
    status_counts = audit_df["Status"].value_counts().to_dict() if not audit_df.empty else {}
    summary["audit_rows"] = int(len(audit_df))
    summary["severity_counts"] = {str(k): int(v) for k, v in counts.items()}
    summary["status_counts"] = {str(k): int(v) for k, v in status_counts.items()}
    summary["outputs"] = {
        "audit_csv": str(OUT_AUDIT_CSV),
        "summary_json": str(OUT_SUMMARY_JSON),
        "recommendations_txt": str(OUT_RECOMMENDATIONS_TXT),
    }
    OUT_SUMMARY_JSON.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    OUT_RECOMMENDATIONS_TXT.write_text(build_recommendations(summary, rows), encoding="utf-8")

    high = int(counts.get("HIGH", 0))
    med = int(counts.get("MEDIUM", 0))
    print("OK: V20 Model Audit complete")
    print(f"Audit:   {OUT_AUDIT_CSV}")
    print(f"Summary: {OUT_SUMMARY_JSON}")
    print(f"Recs:    {OUT_RECOMMENDATIONS_TXT}")
    print(f"Rows:    {len(audit_df)}")
    print(f"Watch:   {high} high / {med} medium")
    try:
        h = summary.get("health_validation", {})
        p = summary.get("projection_layer", {})
        e = summary.get("execution", {})
        print(f"Health:  {h.get('health_label', 'unknown')} score={h.get('health_score', 'unknown')}")
        print(f"Slate:   {p.get('slate_games', 'unknown')} games / {p.get('recommended_actions', 'unknown')} actions")
        print(f"Exec:    {e.get('execution_groups', 'unknown')} groups / P/L={e.get('execution_net_profit', 'unknown')}")
    except Exception:
        pass
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
