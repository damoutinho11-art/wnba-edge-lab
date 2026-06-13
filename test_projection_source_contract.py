#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Regression tests for wnba_projection_source_contract_v21_9.py
"""

import sys
import tempfile
import csv
import json
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import wnba_projection_source_contract_v21_9 as contract


def create_test_projections():
    """Create minimal valid projections_with_stakes.csv rows."""
    return [
        {
            "game": "LAS @ PHO",
            "away_team": "LAS",
            "home_team": "PHO",
            "line": "177.0",
            "projection": "180.5",
            "edge": "3.5",
            "side": "OVER",
            "confidence": "65",
            "suggested_units": "0.35",
            "recommended_bet": "PASS",
            "commence_time": "2026-06-14T02:00:00Z",
        },
        {
            "game": "MIN @ LVA",
            "away_team": "MIN",
            "home_team": "LVA",
            "line": "173.25",
            "projection": "170.0",
            "edge": "-3.25",
            "side": "UNDER",
            "confidence": "55",
            "suggested_units": "0.25",
            "recommended_bet": "PASS",
            "commence_time": "2026-06-14T00:00:00Z",
        },
    ]


def create_test_recommended():
    """Create minimal valid recommended_bets.csv rows."""
    return [
        {
            "game": "LAS @ PHO",
            "recommended_bet": "PASS",
            "side": "OVER",
            "projection": "180.5",
            "line": "177.0",
            "edge": "3.5",
            "suggested_units": "0.35",
            "confidence": "65",
            "commence_time": "2026-06-14T02:00:00Z",
        },
    ]


def create_test_gmf():
    """Create game_model_features rows with fresh games."""
    return [
        {
            "game": "LAS @ PHO",
            "away_team": "LAS",
            "home_team": "PHO",
            "line": "177.0",
        },
        {
            "game": "MIN @ LVA",
            "away_team": "MIN",
            "home_team": "LVA",
            "line": "173.25",
        },
        {
            "game": "DAL @ POR",
            "away_team": "DAL",
            "home_team": "POR",
            "line": "171.5",
        },
    ]


def write_csv(path: Path, rows: List[Dict], fieldnames: List[str] = None):
    if fieldnames is None and rows:
        fieldnames = list(rows[0].keys())
    if fieldnames is None:
        fieldnames = ["game"]  # dummy header for empty files
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        if rows:
            writer.writerows(rows)


def test_missing_files():
    """Test that missing files -> PROJECTION_SOURCE_MISSING."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        # All files missing
        with patch("wnba_projection_source_contract_v21_9.FILES_TO_CHECK", {
            "projections_with_stakes": tmp / "projections_with_stakes.csv",
            "recommended_bets": tmp / "recommended_bets.csv",
            "game_model_features": tmp / "game_model_features_v21.csv",
            "hermes_advisory_queue": tmp / "hermes_advisory_queue_v21.csv",
        }):
            result = contract.run_contract_check()

    assert result["verdict"] == "PROJECTION_SOURCE_MISSING", f"Got {result['verdict']}"
    print("test_missing_files PASSED")


def test_stale_files():
    """Test that stale dates -> PROJECTION_SOURCE_STALE."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        proj_csv = tmp / "projections_with_stakes.csv"
        recs_csv = tmp / "recommended_bets.csv"
        gmf_csv = tmp / "game_model_features_v21.csv"
        queue_csv = tmp / "hermes_advisory_queue_v21.csv"

        # Stale dates (May 2026)
        proj_rows = create_test_projections()
        for r in proj_rows:
            r["commence_time"] = "2026-05-29T23:30:00Z"
        write_csv(proj_csv, proj_rows)

        recs_rows = create_test_recommended()
        for r in recs_rows:
            r["commence_time"] = "2026-05-29T23:30:00Z"
        write_csv(recs_csv, recs_rows)

        # Fresh GMF
        gmf_rows = create_test_gmf()
        write_csv(gmf_csv, gmf_rows)
        write_csv(queue_csv, [])

        with patch("wnba_projection_source_contract_v21_9.FILES_TO_CHECK", {
            "projections_with_stakes": proj_csv,
            "recommended_bets": recs_csv,
            "game_model_features": gmf_csv,
            "hermes_advisory_queue": queue_csv,
        }):
            result = contract.run_contract_check()

    assert result["verdict"] == "PROJECTION_SOURCE_STALE", f"Got {result['verdict']}"
    assert "stale" in " ".join(result["reasons"]).lower()
    print("test_stale_files PASSED")


def test_schema_invalid():
    """Test that missing required columns -> PROJECTION_SOURCE_SCHEMA_INVALID."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        proj_csv = tmp / "projections_with_stakes.csv"
        recs_csv = tmp / "recommended_bets.csv"
        gmf_csv = tmp / "game_model_features_v21.csv"
        queue_csv = tmp / "hermes_advisory_queue_v21.csv"

        # Missing required columns (no edge, no side)
        proj_rows = [
            {"game": "LAS @ PHO", "away_team": "LAS", "home_team": "PHO", "line": "177.0", "projection": "180.5"}
        ]
        write_csv(proj_csv, proj_rows)

        recs_rows = create_test_recommended()
        write_csv(recs_csv, recs_rows)

        gmf_rows = create_test_gmf()
        write_csv(gmf_csv, gmf_rows)
        write_csv(queue_csv, [])

        with patch("wnba_projection_source_contract_v21_9.FILES_TO_CHECK", {
            "projections_with_stakes": proj_csv,
            "recommended_bets": recs_csv,
            "game_model_features": gmf_csv,
            "hermes_advisory_queue": queue_csv,
        }):
            result = contract.run_contract_check()

    assert result["verdict"] == "PROJECTION_SOURCE_SCHEMA_INVALID", f"Got {result['verdict']}"
    assert "edge" in result["schema"]["projections_with_stakes"]["missing"]
    assert "side" in result["schema"]["projections_with_stakes"]["missing"]
    print("test_schema_invalid PASSED")


def test_valid_fresh_schema():
    """Test valid fresh schema -> PROJECTION_SOURCE_READY."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        proj_csv = tmp / "projections_with_stakes.csv"
        recs_csv = tmp / "recommended_bets.csv"
        gmf_csv = tmp / "game_model_features_v21.csv"
        queue_csv = tmp / "hermes_advisory_queue_v21.csv"

        # All fresh games covered
        proj_rows = create_test_projections()
        write_csv(proj_csv, proj_rows)

        recs_rows = create_test_recommended()
        write_csv(recs_csv, recs_rows)

        # GMF matches exactly
        gmf_rows = create_test_gmf()[:2]  # Only LAS@PHO and MIN@LVA
        write_csv(gmf_csv, gmf_rows)
        write_csv(queue_csv, [])

        with patch("wnba_projection_source_contract_v21_9.FILES_TO_CHECK", {
            "projections_with_stakes": proj_csv,
            "recommended_bets": recs_csv,
            "game_model_features": gmf_csv,
            "hermes_advisory_queue": queue_csv,
        }):
            result = contract.run_contract_check()

    assert result["verdict"] == "PROJECTION_SOURCE_READY", f"Got {result['verdict']}"
    assert len(result["schema"]["projections_with_stakes"]["missing"]) == 0
    assert len(result["schema"]["recommended_bets"]["missing"]) == 0
    print("test_valid_fresh_schema PASSED")


def test_missing_fresh_games_detected():
    """Test that missing fresh games are detected."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        proj_csv = tmp / "projections_with_stakes.csv"
        recs_csv = tmp / "recommended_bets.csv"
        gmf_csv = tmp / "game_model_features_v21.csv"
        queue_csv = tmp / "hermes_advisory_queue_v21.csv"

        # Only 2 of 3 fresh games covered
        proj_rows = create_test_projections()
        write_csv(proj_csv, proj_rows)

        recs_rows = create_test_recommended()
        write_csv(recs_csv, recs_rows)

        # 3 fresh games but only 2 in projections
        gmf_rows = create_test_gmf()
        write_csv(gmf_csv, gmf_rows)
        write_csv(queue_csv, [])

        with patch("wnba_projection_source_contract_v21_9.FILES_TO_CHECK", {
            "projections_with_stakes": proj_csv,
            "recommended_bets": recs_csv,
            "game_model_features": gmf_csv,
            "hermes_advisory_queue": queue_csv,
        }):
            result = contract.run_contract_check()

    assert result["verdict"] == "PROJECTION_SOURCE_INCOMPLETE", f"Got {result['verdict']}"
    assert "DAL @ POR" in result["coverage"]["missing_games"]
    print("test_missing_fresh_games_detected PASSED")


def test_safety_footer():
    """Test that safety footer is included in output."""
    import io

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        proj_csv = tmp / "projections_with_stakes.csv"
        recs_csv = tmp / "recommended_bets.csv"
        gmf_csv = tmp / "game_model_features_v21.csv"
        queue_csv = tmp / "hermes_advisory_queue_v21.csv"

        proj_rows = create_test_projections()
        write_csv(proj_csv, proj_rows)

        recs_rows = create_test_recommended()
        write_csv(recs_csv, recs_rows)

        gmf_rows = create_test_gmf()
        write_csv(gmf_csv, gmf_rows)
        write_csv(queue_csv, [])

        old_stdout = sys.stdout
        sys.stdout = io.StringIO()

        with patch("wnba_projection_source_contract_v21_9.FILES_TO_CHECK", {
            "projections_with_stakes": proj_csv,
            "recommended_bets": recs_csv,
            "game_model_features": gmf_csv,
            "hermes_advisory_queue": queue_csv,
        }):
            contract.run_contract_check()

        output = sys.stdout.getvalue()
        sys.stdout = old_stdout

    assert "Manual approval required" in output
    assert "No auto-betting" in output
    assert "No formula changes" in output
    assert "No staking changes" in output
    assert "No threshold changes" in output
    print("test_safety_footer PASSED")


def test_no_writes_by_default():
    """Test that no files are written by default."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        proj_csv = tmp / "projections_with_stakes.csv"
        recs_csv = tmp / "recommended_bets.csv"
        gmf_csv = tmp / "game_model_features_v21.csv"
        queue_csv = tmp / "hermes_advisory_queue_v21.csv"

        proj_rows = create_test_projections()
        write_csv(proj_csv, proj_rows)

        recs_rows = create_test_recommended()
        write_csv(recs_csv, recs_rows)

        gmf_rows = create_test_gmf()
        write_csv(gmf_csv, gmf_rows)
        write_csv(queue_csv, [])

        with patch("wnba_projection_source_contract_v21_9.FILES_TO_CHECK", {
            "projections_with_stakes": proj_csv,
            "recommended_bets": recs_csv,
            "game_model_features": gmf_csv,
            "hermes_advisory_queue": queue_csv,
        }):
            result = contract.run_contract_check()

    # No output file should be created
    output_files = list(tmp.glob("*.json"))
    assert len(output_files) == 0, f"Unexpected output files: {output_files}"
    print("test_no_writes_by_default PASSED")


if __name__ == "__main__":
    from typing import List, Dict

    tests = [
        test_missing_files,
        test_stale_files,
        test_schema_invalid,
        test_valid_fresh_schema,
        test_missing_fresh_games_detected,
        test_safety_footer,
        test_no_writes_by_default,
    ]

    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"{t.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    print("\n=== ALL PROJECTION SOURCE CONTRACT TESTS PASSED ===")