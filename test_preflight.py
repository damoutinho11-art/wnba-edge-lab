#!/usr/bin/env python3
import csv
# -*- coding: utf-8 -*-
"""
Regression tests for wnba_daily_preflight_v21_9.py
Focused on state classification and final verdict logic.
"""

import sys
import tempfile
import json
from pathlib import Path
from unittest.mock import patch, MagicMock

sys.path.insert(0, str(Path(__file__).parent))
import wnba_daily_preflight_v21_9 as preflight


def test_classify_source_state():
    """Test state classification helper."""
    assert preflight.classify_source_state("LIVE_FETCH_OK") == "GOOD"
    assert preflight.classify_source_state("CACHE_FALLBACK_USED") == "DEGRADED"
    assert preflight.classify_source_state("OUTPUT_FALLBACK_USED") == "DEGRADED"
    assert preflight.classify_source_state("FETCH_FAILED_NO_CACHE") == "BLOCKER"
    assert preflight.classify_source_state("FETCHED_ASSETS_UNPARSED") == "UNKNOWN"
    assert preflight.classify_source_state("SKIPPED") == "UNKNOWN"
    print("test_classify_source_state PASSED")


def test_final_verdict_pass():
    """Final verdict PASS when all fetch GOOD, no blockers."""
    audits = {
        "fetch": {
            "present": True,
            "blocker_sources": [],
            "degraded_sources": [],
        },
        "queue": {"present": True, "actionable": 0},
        "portfolio": {"open_exposure": 0},
    }
    verdict = preflight.final_verdict(audits)
    assert verdict == "PREFLIGHT_PASS_SAFE_FOR_MANUAL_REVIEW", f"Got {verdict}"
    print("test_final_verdict_pass PASSED")


def test_final_verdict_blocker_fetch_failed():
    """Final verdict BLOCKER when FETCH_FAILED_NO_CACHE present."""
    audits = {
        "fetch": {
            "present": True,
            "blocker_sources": ["official_teamgamelogs_base"],
            "degraded_sources": [],
        },
        "queue": {"present": True, "actionable": 0},
        "portfolio": {"open_exposure": 0},
    }
    verdict = preflight.final_verdict(audits)
    assert verdict == "PREFLIGHT_BLOCKED_UNSAFE_OR_STALE", f"Got {verdict}"
    print("test_final_verdict_blocker_fetch_failed PASSED")


def test_final_verdict_blocker_missing_status():
    """Final verdict BLOCKER when fetch status file missing."""
    audits = {
        "fetch": {"present": False},
        "queue": {"present": True, "actionable": 0},
        "portfolio": {"open_exposure": 0},
    }
    verdict = preflight.final_verdict(audits)
    assert verdict == "PREFLIGHT_BLOCKED_UNSAFE_OR_STALE", f"Got {verdict}"
    print("test_final_verdict_blocker_missing_status PASSED")


def test_final_verdict_warn_degraded():
    """Final verdict WARN when degraded sources present (no blockers)."""
    audits = {
        "fetch": {
            "present": True,
            "blocker_sources": [],
            "degraded_sources": ["official_teamgamelogs_base"],
        },
        "queue": {"present": True, "actionable": 0},
        "portfolio": {"open_exposure": 0},
    }
    verdict = preflight.final_verdict(audits)
    assert verdict == "PREFLIGHT_WARN_DEGRADED_DATA", f"Got {verdict}"
    print("test_final_verdict_warn_degraded PASSED")


def test_final_verdict_warn_with_actionable():
    """WARN for degraded even with ACTIONABLE > 0 (not pass)."""
    audits = {
        "fetch": {
            "present": True,
            "blocker_sources": [],
            "degraded_sources": ["official_teamgamelogs_base"],
        },
        "queue": {"present": True, "actionable": 3},
        "portfolio": {"open_exposure": 0},
    }
    verdict = preflight.final_verdict(audits)
    assert verdict == "PREFLIGHT_WARN_DEGRADED_DATA", f"Got {verdict}"
    print("test_final_verdict_warn_with_actionable PASSED")


def test_audit_fetch_structure():
    """Test audit_fetch reads status correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        status_file = tmp / "ultimate_fetch_status_v21_4.json"
        status_data = {
            "created_at_utc": "2026-06-12T14:25:36Z",
            "overall_state": "OK",
            "readiness": {
                "official_playergamelogs_ready": True,
                "official_teamgamelogs_ready": True,
                "official_team_dash_ready": True,
                "official_player_dash_ready": True,
                "odds_ready": True,
                "sportsdataverse_ready": True,
                "player_props_market_ready": False,
                "player_props_settlement_ready": True,
            },
            "records": [
                {"source": "official_teamgamelogs_base", "season": "2025", "state": "OUTPUT_FALLBACK_USED"},
                {"source": "official_teamgamelogs_base", "season": "2026", "state": "CACHE_FALLBACK_USED"},
                {"source": "official_playergamelogs_base", "season": "2025", "state": "LIVE_FETCH_OK"},
            ],
            "state_counts": {"LIVE_FETCH_OK": 1, "CACHE_FALLBACK_USED": 1, "OUTPUT_FALLBACK_USED": 1},
            "warnings_count": 0,
            "warnings_high": 0,
        }
        status_file.write_text(json.dumps(status_data))

        with patch("wnba_daily_preflight_v21_9.FETCH_STATUS", status_file):
            result = preflight.audit_fetch()

    assert result["present"] is True
    assert result["source_states"]["official_teamgamelogs_base"]["2025"] == "OUTPUT_FALLBACK_USED"
    assert result["source_states"]["official_teamgamelogs_base"]["2026"] == "CACHE_FALLBACK_USED"
    assert result["source_states"]["official_playergamelogs_base"]["2025"] == "LIVE_FETCH_OK"
    assert "official_teamgamelogs_base" in result["degraded_sources"]
    assert result["blocker_sources"] == []
    assert result["readiness"]["official_teamgamelogs_ready"] is True
    assert result["readiness"]["player_props_market_ready"] is False
    print("test_audit_fetch_structure PASSED")


def test_audit_fetch_blocker():
    """Test audit_fetch detects FETCH_FAILED_NO_CACHE as blocker."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        status_file = tmp / "ultimate_fetch_status_v21_4.json"
        status_data = {
            "records": [
                {"source": "official_teamgamelogs_base", "season": "2025", "state": "FETCH_FAILED_NO_CACHE"},
            ],
        }
        status_file.write_text(json.dumps(status_data))

        with patch("wnba_daily_preflight_v21_9.FETCH_STATUS", status_file):
            result = preflight.audit_fetch()

    assert "official_teamgamelogs_base" in result["blocker_sources"]
    print("test_audit_fetch_blocker PASSED")


def test_audit_queue():
    """Test audit_queue parses actionability correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        queue_file = tmp / "hermes_advisory_queue_v21.csv"
        rows = [
            {"queue_actionability": "ACTIONABLE", "risk_flags": "", "is_stale": "false"},
            {"queue_actionability": "HIDDEN_STALE", "risk_flags": "", "is_stale": "true"},
            {"queue_actionability": "HIDDEN_STALE", "risk_flags": "NO_LINE", "is_stale": "true"},
            {"queue_actionability": "HIDDEN_NO_LINE", "risk_flags": "NO_LINE", "is_stale": "false"},
            {"queue_actionability": "", "risk_flags": "", "is_stale": "false"},
        ]
        with queue_file.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=rows[0].keys())
            writer.writeheader()
            writer.writerows(rows)

        with patch("wnba_daily_preflight_v21_9.HERMES_ADVISORY", queue_file):
            result = preflight.audit_queue()

    assert result["present"] is True
    assert result["total_rows"] == 5
    assert result["actionable"] == 1
    assert result["hidden_total"] == 4
    assert result["hidden_counts"]["HIDDEN_STALE"] == 2
    assert result["hidden_counts"]["HIDDEN_NO_LINE"] == 1
    assert result["hidden_counts"]["no_field"] == 1
    assert result["no_line_count"] == 2
    assert result["stale_count"] == 2
    print("test_audit_queue PASSED")


def test_audit_portfolio():
    """Test audit_portfolio computes exposure correctly."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        bet_file = tmp / "bet_tracker.csv"
        queue_file = tmp / "hermes_advisory_queue_v21.csv"

        bets = [
            {"Status": "OPEN", "Stake": "1.5"},
            {"Status": "SETTLED", "Stake": "1.0"},
            {"Status": "", "Stake": "0.5"},  # UNKNOWN -> open
        ]
        with bet_file.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=bets[0].keys())
            writer.writeheader()
            writer.writerows(bets)

        queue_rows = [
            {"queue_actionability": "ACTIONABLE", "units": "0.75"},
            {"queue_actionability": "ACTIONABLE", "units": "0.5"},
            {"queue_actionability": "HIDDEN_STALE", "units": "1.0"},
        ]
        with queue_file.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=queue_rows[0].keys())
            writer.writeheader()
            writer.writerows(queue_rows)

        with patch("wnba_daily_preflight_v21_9.BET_TRACKER", bet_file), \
             patch("wnba_daily_preflight_v21_9.HERMES_ADVISORY", queue_file):
            result = preflight.audit_portfolio()

    assert result["open_bets"] == 2  # OPEN + empty status
    assert result["open_exposure"] == 2.0  # 1.5 + 0.5
    assert result["proposed_count"] == 2
    assert result["proposed_exposure"] == 1.25  # 0.75 + 0.5
    assert result["combined_exposure"] == 3.25
    print("test_audit_portfolio PASSED")


def test_git_status_clean_when_only_runtime():
    """git status reports clean when only runtime dirs are dirty."""
    with tempfile.TemporaryDirectory() as tmpdir:
        # Create a fake git repo
        subprocess_result = MagicMock()
        subprocess_result.stdout = "?? wnba_outputs/test.csv\n?? wnba_cache_v21/test.csv\n"
        with patch("subprocess.run", return_value=subprocess_result):
            is_clean, dirty = preflight.run_git_status()
        assert is_clean is True
        assert len(dirty) == 2  # Still lists them but they're expected

    # Real dirty file should make it not clean
    with patch("subprocess.run", return_value=MagicMock(stdout="M  some_code.py\n")):
        is_clean, dirty = preflight.run_git_status()
        assert is_clean is False
        assert "some_code.py" in dirty[0]
    print("test_git_status_clean_when_only_runtime PASSED")


if __name__ == "__main__":
    import subprocess
    tests = [
        test_classify_source_state,
        test_final_verdict_pass,
        test_final_verdict_blocker_fetch_failed,
        test_final_verdict_blocker_missing_status,
        test_final_verdict_warn_degraded,
        test_final_verdict_warn_with_actionable,
        test_audit_fetch_structure,
        test_audit_fetch_blocker,
        test_audit_queue,
        test_audit_portfolio,
        test_git_status_clean_when_only_runtime,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"{t.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)
    print("\n=== ALL PREFLIGHT TESTS PASSED ===")