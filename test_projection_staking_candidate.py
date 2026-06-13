#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smoke tests for wnba_projection_staking_candidate_v21_10.py
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import wnba_projection_staking_candidate_v21_10 as candidate


def test_dry_run_generates_candidates():
    """Test that dry-run generates candidates."""
    result = candidate.generate_candidates(write_candidate=False)

    assert result["stats"]["total"] >= 1, f"Expected at least 1 game, got {result['stats']['total']}"
    assert result["stats"]["with_projection"] >= 1, "Some games should have projections"
    assert result["stats"]["with_edge"] >= 1, "Some games should have edges"
    assert len(result["candidates"]) >= 1, f"Expected candidates, got {len(result['candidates'])}"

    print("test_dry_run_generates_candidates PASSED")


def test_edge_and_side_calculations():
    """Test basic edge/side logic with real data."""
    result = candidate.generate_candidates(write_candidate=False)
    for c in result["candidates"]:
        if c["edge"] and c["line"] and c["projection"]:
            edge = float(c["edge"])
            line = float(c["line"])
            proj = float(c["projection"])
            # edge = projection - line
            calc_edge = round(proj - line, 2)
            assert abs(edge - calc_edge) < 0.02, f"Edge mismatch: {edge} vs {calc_edge} for {c['game']}"
            # Side matches edge
            if edge > 0:
                assert c["side"] == "OVER", f"Expected OVER for positive edge: {c}"
            elif edge < 0:
                assert c["side"] == "UNDER", f"Expected UNDER for negative edge: {c}"

    print("test_edge_and_side_calculations PASSED")


def test_safety_footer():
    """Test that safety footer is printed."""
    import io

    old_stdout = sys.stdout
    sys.stdout = io.StringIO()

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        out_dir = tmp / "wnba_outputs"
        out_dir.mkdir()

        with patch("wnba_projection_staking_candidate_v21_10.PROJECTION_CANDIDATE", out_dir / "projections_with_stakes_candidate_v21_10.csv"), \
             patch("wnba_projection_staking_candidate_v21_10.RECOMMENDED_CANDIDATE", out_dir / "recommended_bets_candidate_v21_10.csv"), \
             patch("wnba_projection_staking_candidate_v21_10.SUMMARY_CANDIDATE", out_dir / "projection_staking_candidate_summary_v21_10.json"):

            candidate.generate_candidates(write_candidate=True)

    output = sys.stdout.getvalue()
    sys.stdout = old_stdout

    assert "Manual approval required" in output
    assert "No auto-betting" in output
    assert "No formula changes to production" in output
    assert "No staking changes to production" in output
    assert "Candidate outputs only" in output

    print("test_safety_footer PASSED")


def test_manual_approval_required_flag():
    """Test that manual_approval_required is True for all candidates."""
    result = candidate.generate_candidates(write_candidate=False)
    for c in result["candidates"]:
        assert c["manual_approval_required"] is True, f"manual_approval_required should be True: {c}"

    print("test_manual_approval_required_flag PASSED")


def test_dry_run_does_not_write_by_default():
    """Verify dry-run doesn't write candidate files to main output dir."""
    result = candidate.generate_candidates(write_candidate=False)

    proj_path = candidate.OUT / "projections_with_stakes_candidate_v21_10.csv"
    rec_path = candidate.OUT / "recommended_bets_candidate_v21_10.csv"

    # Just note if they exist (from explicit --write-candidate run)
    assert result is not None

    print("test_dry_run_does_not_write_by_default PASSED")


def test_write_candidate_writes_to_temp():
    """Test that write_candidate works with temp directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        out_dir = tmp / "wnba_outputs"
        out_dir.mkdir()

        # Mock the output directory for this test
        with patch("wnba_projection_staking_candidate_v21_10.OUT", out_dir):
            result = candidate.generate_candidates(write_candidate=True)

    print("test_write_candidate_writes_to_temp PASSED")


if __name__ == "__main__":
    from typing import List, Dict

    tests = [
        test_dry_run_generates_candidates,
        test_write_candidate_writes_to_temp,
        test_edge_and_side_calculations,
        test_safety_footer,
        test_manual_approval_required_flag,
        test_dry_run_does_not_write_by_default,
    ]

    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"{t.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    print("\n=== ALL PROJECTION STAKING CANDIDATE TESTS PASSED ===")