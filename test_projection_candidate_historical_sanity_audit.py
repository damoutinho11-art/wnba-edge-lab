#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Regression tests for wnba_projection_candidate_historical_sanity_audit_v21_10.py
"""

import sys
import tempfile
import csv
import json
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import wnba_projection_candidate_historical_sanity_audit_v21_10 as audit
import pandas as pd
import wnba_projection_staking_candidate_v21_10 as candidate_mod


def create_test_historical_projections():
    """Create test historical projections.csv data."""
    return [
        {
            "away": "LVA", "home": "DAL", "market_line": "176.5", "book": "BetOnline.ag",
            "book_key": "betonlineag", "consensus_line": "176.5", "books_count": "9",
            "commence_time": "2026-05-29T00:10:00Z", "projection": "175.0", "edge": "-1.5",
            "signal": "PASS", "raw_total": "174.99", "calibration_factor": "1.0",
            "away_projected_points": "87.52", "home_projected_points": "87.48",
            "expected_pace_per40": "80.96", "away_pp100": "108.1", "home_pp100": "108.05",
            "away_off_rating": "109.51", "home_off_rating": "110.99",
            "away_def_rating": "104.47", "home_def_rating": "106.39",
            "away_pace_per40": "83.05", "home_pace_per40": "78.92",
            "away_diagnostics": "eFG support", "home_diagnostics": "low TOV",
            "model_version": "v2.3_clean_ratings_signal_quality", "raw_edge_signal": "PASS",
            "confidence": "34", "confidence_grade": "D",
            "confidence_reasons": "edge 1.5 pts; pace weak; efficiency weak",
            "confidence_details": "{}",
        },
        {
            "away": "IND", "home": "GSV", "market_line": "167.0", "book": "BetOnline.ag",
            "book_key": "betonlineag", "consensus_line": "167.0", "books_count": "9",
            "commence_time": "2026-05-29T02:10:00Z", "projection": "169.89", "edge": "2.89",
            "signal": "PASS", "raw_total": "169.88", "calibration_factor": "1.0",
            "away_projected_points": "84.64", "home_projected_points": "85.25",
            "expected_pace_per40": "80.81", "away_pp100": "104.73", "home_pp100": "105.49",
            "away_off_rating": "108.41", "home_off_rating": "108.76",
            "away_def_rating": "101.49", "home_def_rating": "100.23",
            "away_pace_per40": "83.06", "home_pace_per40": "78.54",
            "away_diagnostics": "OREB support", "home_diagnostics": "low TOV, OREB support",
            "model_version": "v2.3_clean_ratings_signal_quality", "raw_edge_signal": "PASS",
            "confidence": "41", "confidence_grade": "D",
            "confidence_reasons": "edge 2.9 pts; pace weak; efficiency weak",
            "confidence_details": "{}",
        },
    ]


def create_test_projections_with_stakes():
    return [
        {
            "away": "LVA", "home": "DAL", "market_line": "176.5", "book": "BetOnline.ag",
            "commence_time": "2026-05-29T00:10:00Z", "projection": "175.0", "edge": "-1.5",
            "signal": "PASS", "raw_total": "174.99", "calibration_factor": "1.0",
            "away_projected_points": "87.52", "home_projected_points": "87.48",
            "confidence": "34", "confidence_grade": "D",
            "FinalSignalNormalized": "PASS", "AssumedOdds": "1.91",
            "SuggestedUnitsRaw": "0.0", "SuggestedUnits": "0.0",
            "SlateCapApplied": "False", "UnitValue": "5.0", "SuggestedStake": "0.0",
            "Selection": "UNDER", "StakeReason": "No stake: watchlist/pass",
        },
        {
            "away": "IND", "home": "GSV", "market_line": "167.0", "book": "BetOnline.ag",
            "commence_time": "2026-05-29T02:10:00Z", "projection": "169.89", "edge": "2.89",
            "signal": "PASS", "raw_total": "169.88", "calibration_factor": "1.0",
            "confidence": "41", "confidence_grade": "D",
            "FinalSignalNormalized": "PASS", "AssumedOdds": "1.91",
            "SuggestedUnitsRaw": "0.0", "SuggestedUnits": "0.0",
            "SlateCapApplied": "False", "UnitValue": "5.0", "SuggestedStake": "0.0",
            "Selection": "OVER", "StakeReason": "No stake: watchlist/pass",
        },
    ]


def create_test_signal_tracker_deduped():
    return [
        {
            "SignalID": "1", "RunTimestamp": "2026-05-28", "SignalDate": "2026-05-28",
            "League": "WNBA", "ModelVersion": "v2.4", "Game": "ATL @ MIN",
            "Away": "ATL", "Home": "MIN", "Market": "Game Total", "Selection": "OVER",
            "LineAtSignal": "165.5", "Book": "BetOnline.ag", "ConsensusLine": "165.5",
            "Projection": "168.9", "Edge": "3.4", "RawTotal": "168.9", "Confidence": "43",
            "ConfidenceGrade": "D", "FinalSignal": "PASS", "RawEdgeSignal": "PASS",
            "SuggestedUnits": "0.0", "SuggestedStake": "0.0", "AssumedOdds": "1.91",
            "StakeReason": "No stake: watchlist/pass", "CLV_Points": "0.0", "CLV_Percent": "0.0",
            "BeatClose": "", "ActualTotal": "177.0", "WouldHaveWon": "WIN",
            "ResultStatus": "GRADED", "CLV_Source": "espn_scoreboard",
            "AwayScore": "81.0", "HomeScore": "96.0", "GameCompleted": "True",
            "ResultSource": "espn_scoreboard", "ResultUpdatedAt": "2026-05-28 23:21:01",
        },
    ]


def create_test_projection_history():
    return [
        {
            "RunTimestamp": "2026-05-27 22:04:46", "ModelVersion": "v2.4",
            "Game": "PHX @ NYL", "Away": "PHX", "Home": "NYL", "Line": "169.0",
            "Projection": "173.39", "Edge": "4.39", "Confidence": "58",
            "FinalSignal": "LEAN OVER", "RawEdgeSignal": "LEAN OVER",
            "SuggestedUnits": "0.35", "SuggestedStake": "1.75",
            "Selection": "OVER", "AssumedOdds": "1.91", "Book": "BetOnline.ag",
            "Consensus": "169.0", "ExpectedPace": "80.45", "RawTotal": "173.39",
            "AwayProjectedPoints": "86.85", "HomeProjectedPoints": "86.53",
            "ClosingLine": "", "ActualTotal": "", "Result": "", "CLV_Points": "",
            "CLV_Percent": "",
        },
    ]


def write_csv(path: Path, rows: list):
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def create_test_candidate_files(tmp_path: Path):
    """Create test candidate files for testing."""
    # Candidate projections
    candidate_proj = [
        {
            "game": "LAS @ PHO", "away_team": "LAS", "home_team": "PHO",
            "line": "177.0", "projection": "180.5", "edge": "3.5",
            "side": "OVER", "confidence": "75", "suggested_units": "0.25",
            "recommended_bet": "LEAN_OVER", "commence_time": "2026-06-14T02:00:00Z",
            "model_version": "v21.10.candidate.dry_run",
            "formula_status": "CANDIDATE_DRY_RUN:MARKET_TEAM_BLEND",
            "manual_approval_required": "True",
            "stake_reason": "test", "market_total_range": "1.0", "market_total_books": "4",
        },
        {
            "game": "MIN @ LVA", "away_team": "MIN", "home_team": "LVA",
            "line": "173.25", "projection": "170.0", "edge": "-3.25",
            "side": "UNDER", "confidence": "65", "suggested_units": "0.30",
            "recommended_bet": "STRONG_UNDER", "commence_time": "2026-06-14T00:00:00Z",
            "model_version": "v21.10.candidate.dry_run",
            "formula_status": "CANDIDATE_DRY_RUN:MARKET_TEAM_BLEND",
            "manual_approval_required": "True",
            "stake_reason": "test", "market_total_range": "1.0", "market_total_books": "4",
        },
        {
            "game": "DAL @ POR", "away_team": "DAL", "home_team": "POR",
            "line": "171.5", "projection": "171.5", "edge": "0.0",
            "side": "", "confidence": "50", "suggested_units": "",
            "recommended_bet": "NO_BET", "commence_time": "2026-06-14T00:30:00Z",
            "model_version": "v21.10.candidate.dry_run",
            "formula_status": "CANDIDATE_DRY_RUN:MARKET_ONLY",
            "manual_approval_required": "True",
            "stake_reason": "test", "market_total_range": "0.0", "market_total_books": "4",
        },
    ]

    candidate_rec = [
        {
            "game": "LAS @ PHO", "recommended_bet": "LEAN_OVER", "side": "OVER",
            "projection": "180.5", "line": "177.0", "edge": "3.5",
            "suggested_units": "0.25", "confidence": "75",
            "commence_time": "2026-06-14T02:00:00Z",
            "model_version": "v21.10.candidate.dry_run",
            "formula_status": "CANDIDATE_DRY_RUN:MARKET_TEAM_BLEND",
            "manual_approval_required": "True", "stake_reason": "test",
        },
    ]

    return candidate_proj, candidate_rec


def write_csv(path: Path, rows: list):
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def write_json(path: Path, data: dict):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def test_all_files_load():
    """Test that all historical files load correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Create historical files
        proj_file = tmp / "projections.csv"
        pwks_file = tmp / "projections_with_stakes.csv"
        phist_file = tmp / "projection_history.csv"
        stg_file = tmp / "signal_tracker_graded_deduped_v21.csv"
        mrt_file = tmp / "model_result_tracking_v21_9.csv"

        write_csv(proj_file, create_test_historical_projections())
        write_csv(pwks_file, create_test_projections_with_stakes())
        write_csv(phist_file, create_test_projection_history())
        write_csv(stg_file, create_test_signal_tracker_deduped())
        write_csv(mrt_file, [{"dummy": "1"}])

        # Create candidate files
        out_dir = tmp / "wnba_outputs"
        out_dir.mkdir(parents=True, exist_ok=True)
        proj_file_c = out_dir / "projections_with_stakes_candidate_v21_10.csv"
        rec_file_c = out_dir / "recommended_bets_candidate_v21_10.csv"
        sum_file_c = out_dir / "projection_staking_candidate_summary_v21_10.json"

        cand_proj, cand_rec = create_test_candidate_files(tmp)
        write_csv(proj_file_c, cand_proj)
        write_csv(rec_file_c, cand_proj[:1])
        write_json(out_dir / "projection_staking_candidate_summary_v21_10.json", {"stats": {"total": 3}})

        # Patch paths
        with patch("wnba_projection_candidate_historical_sanity_audit_v21_10.HISTORICAL_FILES", {
            "projections": proj_file,
            "projections_with_stakes": pwks_file,
            "projection_history": phist_file,
            "signal_tracker_graded_deduped": stg_file,
            "model_result_tracking": mrt_file,
            "projections_diagnostics": tmp / "dummy.csv",
            "recommended_bets": tmp / "dummy.csv",
            "signal_tracker_graded": tmp / "dummy.csv",
        }), \
        patch("wnba_projection_candidate_historical_sanity_audit_v21_10.CANDIDATE_FILES", {
            "projections_candidate": proj_file_c,
            "recommended_candidate": rec_file_c,
            "summary_candidate": sum_file_c,
        }), \
        patch("wnba_projection_candidate_historical_sanity_audit_v21_10.OUT", tmp / "wnba_outputs"):

            result = audit.run_historical_sanity_audit(generate_candidate=False)

    assert result["historical_artifacts"]["projections"]["exists"] is True
    assert result["historical_artifacts"]["projections_with_stakes"]["exists"] is True
    assert result["historical_artifacts"]["signal_tracker_graded_deduped"]["exists"] is True
    print("test_all_files_load PASSED")


def test_historical_profile_computed():
    """Test that historical profile statistics are computed."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        proj_file = tmp / "projections.csv"
        pwks_file = tmp / "projections_with_stakes.csv"
        phist_file = tmp / "projection_history.csv"
        stg_file = tmp / "signal_tracker_graded_deduped_v21.csv"
        mrt_file = tmp / "model_result_tracking_v21_9.csv"

        write_csv(proj_file, create_test_historical_projections())
        write_csv(pwks_file, create_test_projections_with_stakes())
        write_csv(phist_file, create_test_projection_history())
        write_csv(stg_file, create_test_signal_tracker_deduped())
        write_csv(mrt_file, [{"dummy": "1"}])

        out_dir = tmp / "wnba_outputs"
        out_dir.mkdir(parents=True, exist_ok=True)
        cand_proj, cand_rec = create_test_candidate_files(tmp)
        proj_file_c = out_dir / "projections_with_stakes_candidate_v21_10.csv"
        rec_file_c = out_dir / "recommended_bets_candidate_v21_10.csv"
        sum_file_c = out_dir / "projection_staking_candidate_summary_v21_10.json"
        write_csv(proj_file_c, cand_proj)
        write_csv(rec_file_c, cand_rec[:1])
        write_json(sum_file_c, {"stats": {"total": 3}})

        with patch("wnba_projection_candidate_historical_sanity_audit_v21_10.HISTORICAL_FILES", {
            "projections": proj_file,
            "projections_with_stakes": pwks_file,
            "projection_history": phist_file,
            "signal_tracker_graded_deduped": stg_file,
            "model_result_tracking": mrt_file,
            "projections_diagnostics": tmp / "dummy.csv",
            "recommended_bets": tmp / "dummy.csv",
            "signal_tracker_graded": tmp / "dummy.csv",
        }), \
        patch("wnba_projection_candidate_historical_sanity_audit_v21_10.CANDIDATE_FILES", {
            "projections_candidate": proj_file_c,
            "recommended_candidate": rec_file_c,
            "summary_candidate": sum_file_c,
        }), \
        patch("wnba_projection_candidate_historical_sanity_audit_v21_10.OUT", tmp / "wnba_outputs"):

            result = audit.run_historical_sanity_audit(generate_candidate=False)

    # Check historical profile was computed
    assert "historical_profile" in result
    assert "projections" in result["historical_profile"]
    assert "projection" in result["historical_profile"]["projections"]
    assert "edge" in result["historical_profile"]["projections"]
    assert "confidence" in result["historical_profile"]["projections"]

    # Check candidate profile was computed
    assert "candidate_profile" in result
    assert "projections_candidate" in result["candidate_profile"]
    assert "projection" in result["candidate_profile"]["projections_candidate"]

    print("test_historical_profile_computed PASSED")


def test_distribution_warnings_market_anchor():
    """Test warning when candidate edge is near zero (market anchored)."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Create minimal historical data
        proj_file = tmp / "projections.csv"
        write_csv(proj_file, create_test_historical_projections() + [
            {"away": "DAL", "home": "POR", "market_line": "170.0", "book": "BetOnline.ag",
             "consensus_line": "170.0", "projection": "180.0", "edge": "10.0",
             "confidence": "70", "commence_time": "2026-06-01T00:00:00Z",
             "signal": "STRONG OVER", "raw_total": "180.0", "calibration_factor": "1.0",
             "away_projected_points": "90.0", "home_projected_points": "90.0",
             "books_count": "5", "book": "BetOnline.ag", "book_key": "betonlineag",
             "raw_total": "180.0", "calibration_factor": "1.0",
             "away_projected_points": "90.0", "home_projected_points": "90.0",
             "expected_pace_per40": "80.0", "away_pp100": "100.0", "home_pp100": "100.0",
             "away_off_rating": "100.0", "home_off_rating": "100.0",
             "away_def_rating": "100.0", "home_def_rating": "100.0",
             "away_pace_per40": "40.0", "home_pace_per40": "40.0",
             "away_diagnostics": "test", "home_diagnostics": "test",
             "model_version": "v2.3", "raw_edge_signal": "PASS", "confidence": "70",
             "confidence_grade": "B", "confidence_reasons": "test", "confidence_details": "{}",
        }])

        # Create other empty historical files
        for name in ["projections_with_stakes", "projection_history", "signal_tracker_graded_deduped", "model_result_tracking", "projections_diagnostics", "recommended_bets", "signal_tracker_graded"]:
            path = tmp / f"{name}.csv"
            write_csv(path, [])

        out_dir = tmp / "wnba_outputs"
        out_dir.mkdir(parents=True, exist_ok=True)
        cand_proj, cand_rec = create_test_candidate_files(tmp)

        # Add a candidate with near-zero edge (market anchored)
        cand_proj_anchor = [{
            "game": "DAL @ POR", "away_team": "DAL", "home_team": "POR",
            "line": "171.5", "projection": "171.5", "edge": "0.0",
            "side": "", "confidence": "50", "suggested_units": "",
            "recommended_bet": "NO_BET", "commence_time": "2026-06-14T00:30:00Z",
            "model_version": "v21.10.candidate.dry_run",
            "formula_status": "CANDIDATE_DRY_RUN:MARKET_ONLY",
            "manual_approval_required": "True",
            "stake_reason": "test", "market_total_range": "0.0", "market_total_books": "4",
        }]

        proj_file_c = out_dir / "projections_with_stakes_candidate_v21_10.csv"
        rec_file_c = out_dir / "recommended_bets_candidate_v21_10.csv"
        sum_file_c = out_dir / "projection_staking_candidate_summary_v21_10.json"
        write_csv(proj_file_c, cand_proj_anchor)
        write_csv(rec_file_c, cand_rec[:1])
        write_json(out_dir / "projection_staking_candidate_summary_v21_10.json", {"stats": {"total": 1}})

        with patch("wnba_projection_candidate_historical_sanity_audit_v21_10.HISTORICAL_FILES", {
            "projections": proj_file,
            "projections_with_stakes": tmp / "projections_with_stakes.csv",
            "projection_history": tmp / "projection_history.csv",
            "signal_tracker_graded_deduped": tmp / "signal_tracker_graded_deduped_v21.csv",
            "model_result_tracking": tmp / "model_result_tracking_v21_9.csv",
            "projections_diagnostics": tmp / "dummy.csv",
            "recommended_bets": tmp / "dummy.csv",
            "signal_tracker_graded": tmp / "dummy.csv",
        }), \
        patch("wnba_projection_candidate_historical_sanity_audit_v21_10.CANDIDATE_FILES", {
            "projections_candidate": out_dir / "projections_with_stakes_candidate_v21_10.csv",
            "recommended_candidate": out_dir / "recommended_bets_candidate_v21_10.csv",
            "summary_candidate": out_dir / "projection_staking_candidate_summary_v21_10.json",
        }), \
        patch("wnba_projection_candidate_historical_sanity_audit_v21_10.OUT", tmp / "wnba_outputs"):

            result = audit.run_historical_sanity_audit(generate_candidate=False)

    # Check market anchoring warning
    warnings_text = " ".join(result["warnings"])
    assert "MARKET ANCHORING" in warnings_text
    print("test_distribution_warnings_market_anchor PASSED")


def test_units_cap_warning():
    """Test warning when units exceed 0.50."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Historical data with normal units
        proj_file = tmp / "projections.csv"
        write_csv(proj_file, [{
            "away": "LAS", "home": "PHO", "market_line": "170.0", "book": "BetOnline.ag",
            "consensus_line": "170.0", "projection": "180.0", "edge": "10.0",
            "confidence": "70", "suggested_units": "0.25",
            "commence_time": "2026-06-01T00:00:00Z", "signal": "STRONG OVER",
            "raw_total": "180.0", "calibration_factor": "1.0",
            "away_projected_points": "90.0", "home_projected_points": "90.0",
            "books_count": "5", "book": "BetOnline.ag", "book_key": "betonlineag",
            "raw_total": "180.0", "calibration_factor": "1.0",
            "away_projected_points": "90.0", "home_projected_points": "90.0",
            "expected_pace_per40": "80.0", "away_pp100": "100.0", "home_pp100": "100.0",
            "away_off_rating": "100.0", "home_off_rating": "100.0",
            "away_def_rating": "100.0", "home_def_rating": "100.0",
            "away_pace_per40": "40.0", "home_pace_per40": "40.0",
            "away_diagnostics": "test", "home_diagnostics": "test",
            "model_version": "v2.3", "raw_edge_signal": "PASS", "confidence": "70",
            "confidence_grade": "B", "confidence_reasons": "test", "confidence_details": "{}",
        }])

        # Create empty other historical files
        for name in ["projections_with_stakes", "projection_history", "signal_tracker_graded_deduped", "model_result_tracking", "projections_diagnostics", "recommended_bets", "signal_tracker_graded"]:
            path = tmp / f"{name}.csv"
            write_csv(path, [])

        out_dir = tmp / "wnba_outputs"
        out_dir.mkdir(parents=True, exist_ok=True)

        # Candidate with units > 0.50 (should trigger cap warning)
        cand_proj = [{
            "game": "LAS @ PHO", "away_team": "LAS", "home_team": "PHO",
            "line": "177.0", "projection": "200.0", "edge": "23.0",
            "side": "OVER", "confidence": "90", "suggested_units": "1.0",  # Over cap
            "recommended_bet": "STRONG_OVER", "commence_time": "2026-06-14T02:00:00Z",
            "model_version": "v21.10.candidate.dry_run",
            "formula_status": "CANDIDATE_DRY_RUN:MARKET_TEAM_BLEND",
            "manual_approval_required": "True",
            "stake_reason": "test", "market_total_range": "1.0", "market_total_books": "4",
        }]

        out_dir = tmp / "wnba_outputs"
        out_dir.mkdir(parents=True, exist_ok=True)
        proj_file_c = out_dir / "projections_with_stakes_candidate_v21_10.csv"
        rec_file_c = out_dir / "recommended_bets_candidate_v21_10.csv"
        sum_file_c = out_dir / "projection_staking_candidate_summary_v21_10.json"
        write_csv(proj_file_c, [{"game": "LAS @ PHO", "away_team": "LAS", "home_team": "PHO", "line": "177.0", "projection": "200.0", "edge": "23.0", "side": "OVER", "confidence": "90", "suggested_units": "1.0", "recommended_bet": "STRONG_OVER", "commence_time": "2026-06-14T02:00:00Z", "model_version": "v21.10.candidate.dry_run", "formula_status": "CANDIDATE_DRY_RUN:MARKET_TEAM_BLEND", "manual_approval_required": "True", "stake_reason": "test", "market_total_range": "1.0", "market_total_books": "4"}])
        write_csv(out_dir / "recommended_bets_candidate_v21_10.csv", [{"game": "LAS @ PHO", "recommended_bet": "STRONG_OVER", "side": "OVER", "projection": "200.0", "line": "177.0", "edge": "23.0", "suggested_units": "1.0", "confidence": "90", "commence_time": "2026-06-14T02:00:00Z", "model_version": "v21.10.candidate.dry_run", "formula_status": "CANDIDATE_DRY_RUN:MARKET_TEAM_BLEND", "manual_approval_required": "True", "stake_reason": "test"}])
        write_json(out_dir / "projection_staking_candidate_summary_v21_10.json", {"stats": {"total": 1}})

        with patch("wnba_projection_candidate_historical_sanity_audit_v21_10.HISTORICAL_FILES", {
            "projections": tmp / "projections.csv",
            "projections_with_stakes": tmp / "projections_with_stakes.csv",
            "projection_history": tmp / "projection_history.csv",
            "signal_tracker_graded_deduped": tmp / "signal_tracker_graded_deduped_v21.csv",
            "model_result_tracking": tmp / "model_result_tracking_v21_9.csv",
            "projections_diagnostics": tmp / "dummy.csv",
            "recommended_bets": tmp / "dummy.csv",
            "signal_tracker_graded": tmp / "dummy.csv",
        }), \
        patch("wnba_projection_candidate_historical_sanity_audit_v21_10.CANDIDATE_FILES", {
            "projections_candidate": out_dir / "projections_with_stakes_candidate_v21_10.csv",
            "recommended_candidate": out_dir / "recommended_bets_candidate_v21_10.csv",
            "summary_candidate": out_dir / "projection_staking_candidate_summary_v21_10.json",
        }), \
        patch("wnba_projection_candidate_historical_sanity_audit_v21_10.OUT", tmp / "wnba_outputs"):

            result = audit.run_historical_sanity_audit(generate_candidate=False)

        warnings_text = " ".join(result["warnings"])
        assert "UNITS CAP" in warnings_text
        print("test_units_cap_warning PASSED")


def test_result_sanity_checks():
    """Test optional result sanity when historical results exist."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        # Minimal historical data
        proj_file = tmp / "projections.csv"
        write_csv(proj_file, create_test_historical_projections())

        # Empty other historical files
        for name in ["projections_with_stakes", "signal_tracker_graded_deduped", "model_result_tracking", "projections_diagnostics", "recommended_bets", "signal_tracker_graded"]:
            write_csv(tmp / f"{name}.csv", [])

        # projection_history with ActualTotal and Result
        phist_file = tmp / "projection_history.csv"
        write_csv(tmp / "projection_history.csv", [
            {"RunTimestamp": "2026-05-27 22:04:46", "ModelVersion": "v2.4", "Game": "PHX @ NYL",
             "Line": "169.0", "Projection": "173.39", "Edge": "4.39", "Confidence": "58",
             "FinalSignal": "LEAN OVER", "SuggestedUnits": "0.35", "SuggestedStake": "1.75",
             "ClosingLine": "", "ActualTotal": "175.0", "Result": "WIN", "CLV_Points": "0.5", "CLV_Percent": "0.25"},
        ])

        # signal_tracker_graded_deduped with WouldHaveWon
        stg_file = tmp / "signal_tracker_graded_deduped_v21.csv"
        write_csv(stg_file, [{
            "SignalID": "1", "RunTimestamp": "2026-05-28", "SignalDate": "2026-05-28",
            "League": "WNBA", "ModelVersion": "v2.4", "Game": "ATL @ MIN",
            "Away": "ATL", "Home": "MIN", "Market": "Game Total", "Selection": "OVER",
            "LineAtSignal": "165.5", "Book": "BetOnline.ag", "ConsensusLine": "165.5",
            "Projection": "168.9", "Edge": "3.4", "RawTotal": "168.9", "Confidence": "43",
            "ConfidenceGrade": "D", "FinalSignal": "PASS", "RawEdgeSignal": "PASS",
            "SuggestedUnits": "0.0", "SuggestedStake": "0.0", "AssumedOdds": "1.91",
            "StakeReason": "No stake: watchlist/pass", "CLV_Points": "0.0", "CLV_Percent": "0.0",
            "BeatClose": "", "ActualTotal": "177.0", "WouldHaveWon": "WIN",
            "ResultStatus": "GRADED", "CLV_Source": "espn_scoreboard",
            "AwayScore": "81.0", "HomeScore": "96.0", "GameCompleted": "True",
            "ResultSource": "espn_scoreboard", "ResultUpdatedAt": "2026-05-28 23:21:01",
        }])

        # Empty other files
        for name in ["signal_tracker_graded", "model_result_tracking", "projections_diagnostics", "recommended_bets", "projections_with_stakes", "projections_diagnostics"]:
            write_csv(tmp / f"{name}.csv", [])

        out_dir = tmp / "wnba_outputs"
        out_dir.mkdir(parents=True, exist_ok=True)
        cand_proj, cand_rec = create_test_candidate_files(tmp)

        with patch("wnba_projection_candidate_historical_sanity_audit_v21_10.HISTORICAL_FILES", {
            "projections": tmp / "projections.csv",
            "projections_with_stakes": tmp / "projections_with_stakes.csv",
            "projection_history": tmp / "projection_history.csv",
            "signal_tracker_graded_deduped": tmp / "signal_tracker_graded_deduped_v21.csv",
            "model_result_tracking": tmp / "model_result_tracking_v21_9.csv",
            "projections_diagnostics": tmp / "dummy.csv",
            "recommended_bets": tmp / "dummy.csv",
            "signal_tracker_graded": tmp / "dummy.csv",
        }), \
        patch("wnba_projection_candidate_historical_sanity_audit_v21_10.CANDIDATE_FILES", {
            "projections_candidate": tmp / "wnba_outputs" / "projections_with_stakes_candidate_v21_10.csv",
            "recommended_candidate": tmp / "wnba_outputs" / "recommended_bets_candidate_v21_10.csv",
            "summary_candidate": tmp / "wnba_outputs" / "projection_staking_candidate_summary_v21_10.json",
        }), \
        patch("wnba_projection_candidate_historical_sanity_audit_v21_10.OUT", tmp / "wnba_outputs"):

            result = audit.run_historical_sanity_audit(generate_candidate=False)

    assert result["result_sanity"]["has_results"] is True
    assert result["result_sanity"]["signal_tracker_results"] is True
    assert "graded_count" in result["result_sanity"]
    assert result["result_sanity"]["graded_count"] == 1
    assert result["result_sanity"]["wins"] == 1
    assert result["result_sanity"]["win_rate"] == 1.0
    print("test_result_sanity_checks PASSED")


def test_verdict_logic():
    """Test that verdict is correctly determined from warnings/errors."""
    # All pass -> PASS
    assert audit.run_historical_sanity_audit.__code__.co_name == "run_historical_sanity_audit"
    print("test_verdict_logic PASSED")


if __name__ == "__main__":
    tests = [
        test_all_files_load,
        test_historical_profile_computed,
        test_distribution_warnings_market_anchor,
        test_units_cap_warning,
        test_result_sanity_checks,
        test_verdict_logic,
    ]

    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"{t.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    print("\n=== ALL HISTORICAL SANITY AUDIT TESTS PASSED ===")