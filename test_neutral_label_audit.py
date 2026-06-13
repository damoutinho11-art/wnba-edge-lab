#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Regression tests for wnba_neutral_label_audit_v21_9.py
"""

import sys
import tempfile
import csv
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent))
import wnba_neutral_label_audit_v21_9 as audit


def create_test_scores():
    """Create test advisory score rows."""
    base_time = "2026-06-13T09:03:53.834931+00:00"
    return [
        {
            "created_at_utc": base_time,
            "source": "game_model_features_v21",
            "game": "LAS @ PHO",
            "away_team": "LAS",
            "home_team": "PHO",
            "side": "",
            "line": "177.0",
            "projection": "",
            "edge": "",
            "units": "",
            "game_start_utc": "",
            "game_date": "2026-06-13",
            "timing_source": "schedule_date_lookup",
            "model_edge_score": "0.0",
            "recent_scoring_score": "0.0",
            "dashboard_scoring_score": "0.0",
            "rotation_concentration_score": "0.0",
            "rotation_risk_penalty": "0.0",
            "bench_depth_score": "0.0",
            "dreb_environment_score": "0.0",
            "market_range_penalty": "0.0",
            "market_range": "",
            "advisory_score": "0.25",
            "advisory_label": "NEUTRAL",
            "risk_flags": "NO_SIDE, LOW_MODEL_EDGE",
            "manual_review_priority": "1.0",
        },
        {
            "created_at_utc": base_time,
            "source": "hermes_approval_queue_v20",
            "game": "LAS @ WAS",
            "away_team": "LAS",
            "home_team": "WAS",
            "side": "OVER",
            "line": "",
            "projection": "175.52",
            "edge": "6.52",
            "units": "0.75",
            "game_start_utc": "2026-05-29T23:30:00+00:00",
            "game_date": "2026-05-29",
            "timing_source": "commence_time",
            "model_edge_score": "65.2",
            "recent_scoring_score": "0",
            "dashboard_scoring_score": "0",
            "rotation_concentration_score": "3.87",
            "rotation_risk_penalty": "0.0",
            "bench_depth_score": "-1.87",
            "dreb_environment_score": "-0.97",
            "market_range_penalty": "0.0",
            "market_range": "",
            "advisory_score": "19.69",
            "advisory_label": "NEUTRAL",
            "risk_flags": "NO_LINE",
            "manual_review_priority": "1.0",
        },
        {
            "created_at_utc": base_time,
            "source": "projections_with_stakes",
            "game": "ATL @ PDX",
            "away_team": "ATL",
            "home_team": "PDX",
            "side": "OVER",
            "line": "",
            "projection": "169.84",
            "edge": "5.34",
            "units": "",
            "game_start_utc": "2026-05-30T02:00:00+00:00",
            "game_date": "2026-05-30",
            "timing_source": "commence_time",
            "model_edge_score": "53.4",
            "recent_scoring_score": "0",
            "dashboard_scoring_score": "0",
            "rotation_concentration_score": "-1.39",
            "rotation_risk_penalty": "0",
            "bench_depth_score": "3.39",
            "dreb_environment_score": "-1.03",
            "market_range_penalty": "0",
            "market_range": "",
            "advisory_score": "16.04",
            "advisory_label": "NEUTRAL",
            "risk_flags": "NO_LINE",
            "manual_review_priority": "2.0",
        },
    ]


def test_all_neutral_verdict():
    """Test that all-NEUTRAL rows give correct verdict."""
    rows = create_test_scores()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        scores_csv = tmp / "model_advisory_scores_v21.csv"
        
        with scores_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        
        with patch("wnba_neutral_label_audit_v21_9.ADVISORY_SCORES", scores_csv), \
             patch("wnba_neutral_label_audit_v21_9.ADVISORY_QUEUE", tmp / "empty.csv"), \
             patch("wnba_neutral_label_audit_v21_9.ADVISORY_SUMMARY", tmp / "empty.json"), \
             patch("wnba_neutral_label_audit_v21_9.GAME_FEATURES", tmp / "empty.csv"):
            result = audit.run_audit()
    
    assert result["verdict"] == "NEUTRAL_AUDIT_ALL_NEUTRAL", f"Got {result['verdict']}"
    assert result["neutral_count"] == 3
    assert result["non_neutral_count"] == 0
    print("test_all_neutral_verdict PASSED")


def test_mixed_label_verdict():
    """Test mixed labels give correct verdict."""
    rows = create_test_scores()
    # Modify one row to have LEAN_SUPPORT label
    rows[0]["advisory_label"] = "LEAN_SUPPORT"
    rows[0]["advisory_score"] = "30.0"
    rows[0]["model_edge_score"] = "30.0"
    
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        scores_csv = tmp / "model_advisory_scores_v21.csv"
        
        with scores_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        
        with patch("wnba_neutral_label_audit_v21_9.ADVISORY_SCORES", scores_csv), \
             patch("wnba_neutral_label_audit_v21_9.ADVISORY_QUEUE", tmp / "empty.csv"), \
             patch("wnba_neutral_label_audit_v21_9.ADVISORY_SUMMARY", tmp / "empty.json"), \
             patch("wnba_neutral_label_audit_v21_9.GAME_FEATURES", tmp / "empty.csv"):
            result = audit.run_audit()
    
    assert result["verdict"] == "NEUTRAL_AUDIT_MIXED_LABELS", f"Got {result['verdict']}"
    assert result["neutral_count"] == 2
    assert result["non_neutral_count"] == 1
    print("test_mixed_label_verdict PASSED")


def test_blocked_no_scores():
    """Test blocked verdict when no scores."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        scores_csv = tmp / "model_advisory_scores_v21.csv"
        scores_csv.write_text("")  # empty file
        
        with patch("wnba_neutral_label_audit_v21_9.ADVISORY_SCORES", scores_csv), \
             patch("wnba_neutral_label_audit_v21_9.ADVISORY_QUEUE", tmp / "empty.csv"), \
             patch("wnba_neutral_label_audit_v21_9.ADVISORY_SUMMARY", tmp / "empty.json"), \
             patch("wnba_neutral_label_audit_v21_9.GAME_FEATURES", tmp / "empty.csv"):
            result = audit.run_audit()
    
    assert result["verdict"] == "NEUTRAL_AUDIT_BLOCKED_NO_SCORES"
    print("test_blocked_no_scores PASSED")


def test_min_max_mean_edge_summary():
    """Test min/max/mean edge score summary."""
    rows = create_test_scores()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        scores_csv = tmp / "model_advisory_scores_v21.csv"
        
        with scores_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        
        with patch("wnba_neutral_label_audit_v21_9.ADVISORY_SCORES", scores_csv), \
             patch("wnba_neutral_label_audit_v21_9.ADVISORY_QUEUE", tmp / "empty.csv"), \
             patch("wnba_neutral_label_audit_v21_9.ADVISORY_SUMMARY", tmp / "empty.json"), \
             patch("wnba_neutral_label_audit_v21_9.GAME_FEATURES", tmp / "empty.csv"):
            result = audit.run_audit()
    
    es = result["edge_score_stats"]
    assert "min" in es and "max" in es and "mean" in es
    assert es["min"] == 0.0
    assert es["max"] == 65.2
    print("test_min_max_mean_edge_summary PASSED")


def test_missing_fields_counted():
    """Test that missing fields are counted correctly."""
    rows = create_test_scores()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        scores_csv = tmp / "model_advisory_scores_v21.csv"
        
        with scores_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        
        with patch("wnba_neutral_label_audit_v21_9.ADVISORY_SCORES", scores_csv), \
             patch("wnba_neutral_label_audit_v21_9.ADVISORY_QUEUE", tmp / "empty.csv"), \
             patch("wnba_neutral_label_audit_v21_9.ADVISORY_SUMMARY", tmp / "empty.json"), \
             patch("wnba_neutral_label_audit_v21_9.GAME_FEATURES", tmp / "empty.csv"):
            result = audit.run_audit()
    
    mf = result["missing_fields"]
    assert mf["side"] >= 1  # at least one missing side
    assert mf["line"] >= 2  # at least two missing lines
    assert mf["projection"] >= 1
    assert mf["edge"] >= 1
    print("test_missing_fields_counted PASSED")


def test_safety_footer_included():
    """Test that safety footer is in output."""
    rows = create_test_scores()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        scores_csv = tmp / "model_advisory_scores_v21.csv"
        
        with scores_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        
        with patch("wnba_neutral_label_audit_v21_9.ADVISORY_SCORES", scores_csv), \
             patch("wnba_neutral_label_audit_v21_9.ADVISORY_QUEUE", tmp / "empty.csv"), \
             patch("wnba_neutral_label_audit_v21_9.ADVISORY_SUMMARY", tmp / "empty.json"), \
             patch("wnba_neutral_label_audit_v21_9.GAME_FEATURES", tmp / "empty.csv"):
            result = audit.run_audit()
    
    # Capture stdout
    import io
    import sys
    old_stdout = sys.stdout
    sys.stdout = io.StringIO()
    audit.run_audit()
    output = sys.stdout.getvalue()
    sys.stdout = old_stdout
    
    assert "Manual approval required" in output
    assert "No auto-betting" in output
    assert "No formula changes" in output
    assert "No staking changes" in output
    assert "No threshold changes" in output
    print("test_safety_footer_included PASSED")


def test_no_writes_by_default():
    """Test that no files are written by default."""
    rows = create_test_scores()
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        scores_csv = tmp / "model_advisory_scores_v21.csv"
        
        with scores_csv.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)
        
        with patch("wnba_neutral_label_audit_v21_9.ADVISORY_SCORES", scores_csv), \
             patch("wnba_neutral_label_audit_v21_9.ADVISORY_QUEUE", tmp / "empty.csv"), \
             patch("wnba_neutral_label_audit_v21_9.ADVISORY_SUMMARY", tmp / "empty.json"), \
             patch("wnba_neutral_label_audit_v21_9.GAME_FEATURES", tmp / "empty.csv"):
            result = audit.run_audit()
    
    # No output file should be created
    output_files = list(tmp.glob("*.json"))
    assert len(output_files) == 0, f"Unexpected output files: {output_files}"
    print("test_no_writes_by_default PASSED")


if __name__ == "__main__":
    import io
    import sys
    import tempfile
    from pathlib import Path
    import csv
    import json
    
    tests = [
        test_all_neutral_verdict,
        test_mixed_label_verdict,
        test_blocked_no_scores,
        test_min_max_mean_edge_summary,
        test_missing_fields_counted,
        test_safety_footer_included,
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
    
    print("\n=== ALL NEUTRAL LABEL AUDIT TESTS PASSED ===")