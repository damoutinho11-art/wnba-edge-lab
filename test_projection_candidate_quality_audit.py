#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Smoke tests for wnba_projection_candidate_quality_audit_v21_10.py
"""

import sys
import tempfile
import csv
import json
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
import wnba_projection_candidate_quality_audit_v21_10 as audit
import wnba_projection_staking_candidate_v21_10 as candidate
import pandas as pd


def read_csv(path: Path) -> list:
    if not path.exists():
        return []
    try:
        with path.open(newline="", encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))
    except Exception:
        return []


def read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


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


def create_test_candidate_projections():
    return [
        {
            "game": "LAS @ PHO",
            "away_team": "LAS",
            "home_team": "PHO",
            "line": "177.0",
            "projection": "180.5",
            "edge": "3.5",
            "side": "OVER",
            "confidence": "75",
            "suggested_units": "0.25",
            "recommended_bet": "LEAN_OVER",
            "commence_time": "2026-06-14T02:00:00Z",
            "model_version": "v21.10.candidate.dry_run",
            "formula_status": "CANDIDATE_DRY_RUN:MARKET_TEAM_BLEND",
            "manual_approval_required": "True",
            "stake_reason": "test",
            "market_total_range": "1.0",
            "market_total_books": "4",
        },
        {
            "game": "MIN @ LVA",
            "away_team": "MIN",
            "home_team": "LVA",
            "line": "173.25",
            "projection": "170.0",
            "edge": "-3.25",
            "side": "UNDER",
            "confidence": "65",
            "suggested_units": "0.30",
            "recommended_bet": "STRONG_UNDER",
            "commence_time": "2026-06-14T00:00:00Z",
            "model_version": "v21.10.candidate.dry_run",
            "formula_status": "CANDIDATE_DRY_RUN:MARKET_TEAM_BLEND",
            "manual_approval_required": "True",
            "stake_reason": "test",
            "market_total_range": "1.0",
            "market_total_books": "4",
        },
        {
            "game": "DAL @ POR",
            "away_team": "DAL",
            "home_team": "POR",
            "line": "171.5",
            "projection": "175.0",
            "edge": "3.5",
            "side": "OVER",
            "confidence": "65",
            "suggested_units": "0.20",
            "recommended_bet": "LEAN_OVER",
            "commence_time": "2026-06-14T00:30:00Z",
            "model_version": "v21.10.candidate.dry_run",
            "formula_status": "CANDIDATE_DRY_RUN:MARKET_ONLY",
            "manual_approval_required": "True",
            "stake_reason": "test",
            "market_total_range": "0.0",
            "market_total_books": "4",
        },
    ]


def create_test_candidate_recommended():
    return [
        {
            "game": "LAS @ PHO",
            "recommended_bet": "LEAN_OVER",
            "side": "OVER",
            "projection": "180.5",
            "line": "177.0",
            "edge": "3.5",
            "suggested_units": "0.25",
            "confidence": "75",
            "commence_time": "2026-06-14T02:00:00Z",
            "model_version": "v21.10.candidate.dry_run",
            "formula_status": "CANDIDATE_DRY_RUN:MARKET_TEAM_BLEND",
            "manual_approval_required": "True",
            "stake_reason": "test",
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


def test_all_pass():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        out_dir = tmp / "wnba_outputs"
        out_dir.mkdir()

        proj_file = out_dir / "projections_with_stakes_candidate_v21_10.csv"
        rec_file = out_dir / "recommended_bets_candidate_v21_10.csv"
        summary_file = out_dir / "projection_staking_candidate_summary_v21_10.json"

        write_csv(proj_file, create_test_candidate_projections())
        write_csv(rec_file, create_test_candidate_recommended())
        summary_file.write_text(json.dumps({"stats": {"total": 3}}, indent=2))

        with patch("wnba_projection_candidate_quality_audit_v21_10.PROJ_CANDIDATE", proj_file), \
             patch("wnba_projection_candidate_quality_audit_v21_10.REC_CANDIDATE", rec_file), \
             patch("wnba_projection_candidate_quality_audit_v21_10.SUMMARY_CANDIDATE", summary_file), \
             patch("wnba_projection_candidate_quality_audit_v21_10.OUT", out_dir):

            result = audit.audit_candidates(
                pd.read_csv(proj_file),
                pd.read_csv(rec_file),
                json.loads(summary_file.read_text())
            )

    assert result["verdict"] == "CANDIDATE_AUDIT_PASS_RESEARCH_ONLY", f"Got {result['verdict']}"
    assert len(result["errors"]) == 0
    print("test_all_pass PASSED")


def test_warning_market_dependence():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        out_dir = tmp / "wnba_outputs"
        out_dir.mkdir()

        proj_rows = create_test_candidate_projections()
        proj_rows[2]["projection"] = "171.5"
        proj_rows[2]["edge"] = "0.0"

        proj_file = out_dir / "projections_with_stakes_candidate_v21_10.csv"
        rec_file = out_dir / "recommended_bets_candidate_v21_10.csv"
        summary_file = out_dir / "projection_staking_candidate_summary_v21_10.json"

        write_csv(proj_file, proj_rows)
        # Need to add a recommended row for the third game
        rec_rows = create_test_candidate_recommended()
        rec_rows.append({
            "game": "DAL @ POR",
            "recommended_bet": "NO_BET",
            "side": "",
            "projection": "171.5",
            "line": "171.5",
            "edge": "0.0",
            "suggested_units": "",
            "confidence": "50",
            "commence_time": "2026-06-14T00:30:00Z",
            "model_version": "v21.10.candidate.dry_run",
            "formula_status": "CANDIDATE_DRY_RUN:MARKET_ONLY",
            "manual_approval_required": "True",
            "stake_reason": "test",
        })

        proj_file = out_dir / "projections_with_stakes_candidate_v21_10.csv"
        rec_file = out_dir / "recommended_bets_candidate_v21_10.csv"
        summary_file = out_dir / "projection_staking_candidate_summary_v21_10.json"

        write_csv(proj_file, proj_rows)
        write_csv(rec_file, create_test_candidate_recommended())
        summary_file.write_text(json.dumps({"stats": {"total": 3}}, indent=2))

        with patch("wnba_projection_candidate_quality_audit_v21_10.PROJ_CANDIDATE", proj_file), \
             patch("wnba_projection_candidate_quality_audit_v21_10.REC_CANDIDATE", rec_file), \
             patch("wnba_projection_candidate_quality_audit_v21_10.SUMMARY_CANDIDATE", summary_file), \
             patch("wnba_projection_candidate_quality_audit_v21_10.OUT", out_dir):

            result = audit.audit_candidates(
                pd.read_csv(proj_file),
                pd.read_csv(rec_file),
                json.loads(summary_file.read_text())
            )

    assert result["verdict"] == "CANDIDATE_AUDIT_WARN_RESEARCH_ONLY", f"Got {result['verdict']}"
    assert any("Market dependence" in w for w in result["warnings"])
    print("test_warning_market_dependence PASSED")


def test_warning_units_sanity():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        out_dir = tmp / "wnba_outputs"
        out_dir.mkdir()

        proj_rows = create_test_candidate_projections()
        proj_rows[0]["confidence"] = "30"

        proj_file = out_dir / "projections_with_stakes_candidate_v21_10.csv"
        rec_file = out_dir / "recommended_bets_candidate_v21_10.csv"
        summary_file = out_dir / "projection_staking_candidate_summary_v21_10.json"

        write_csv(proj_file, proj_rows)
        write_csv(out_dir / "recommended_bets_candidate_v21_10.csv", create_test_candidate_recommended())
        write_json(out_dir / "projection_staking_candidate_summary_v21_10.json", {"stats": {"total": 3}})

        with patch("wnba_projection_candidate_quality_audit_v21_10.PROJ_CANDIDATE", proj_file), \
             patch("wnba_projection_candidate_quality_audit_v21_10.REC_CANDIDATE", out_dir / "recommended_bets_candidate_v21_10.csv"), \
             patch("wnba_projection_candidate_quality_audit_v21_10.SUMMARY_CANDIDATE", out_dir / "projection_staking_candidate_summary_v21_10.json"), \
             patch("wnba_projection_candidate_quality_audit_v21_10.OUT", out_dir):

            result = audit.audit_candidates(
                pd.read_csv(proj_file),
                pd.read_csv(out_dir / "recommended_bets_candidate_v21_10.csv"),
                json.loads((out_dir / "projection_staking_candidate_summary_v21_10.json").read_text())
            )

    assert result["verdict"] == "CANDIDATE_AUDIT_WARN_RESEARCH_ONLY", f"Got {result['verdict']}"
    assert any("Units sanity" in w for w in result["warnings"])
    print("test_warning_units_sanity PASSED")


def test_fail_missing_formula_status():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        out_dir = tmp / "wnba_outputs"
        out_dir.mkdir()

        proj_rows = create_test_candidate_projections()
        proj_rows[0]["formula_status"] = "PRODUCTION"

        proj_file = out_dir / "projections_with_stakes_candidate_v21_10.csv"
        rec_file = out_dir / "recommended_bets_candidate_v21_10.csv"
        summary_file = out_dir / "projection_staking_candidate_summary_v21_10.json"

        write_csv(proj_file, proj_rows)
        write_csv(out_dir / "recommended_bets_candidate_v21_10.csv", create_test_candidate_recommended())
        write_json(out_dir / "projection_staking_candidate_summary_v21_10.json", {"stats": {"total": 3}})

        with patch("wnba_projection_candidate_quality_audit_v21_10.PROJ_CANDIDATE", proj_file), \
             patch("wnba_projection_candidate_quality_audit_v21_10.REC_CANDIDATE", out_dir / "recommended_bets_candidate_v21_10.csv"), \
             patch("wnba_projection_candidate_quality_audit_v21_10.SUMMARY_CANDIDATE", out_dir / "projection_staking_candidate_summary_v21_10.json"), \
             patch("wnba_projection_candidate_quality_audit_v21_10.OUT", out_dir):

            result = audit.audit_candidates(
                pd.read_csv(proj_file),
                pd.read_csv(out_dir / "recommended_bets_candidate_v21_10.csv"),
                json.loads((out_dir / "projection_staking_candidate_summary_v21_10.json").read_text())
            )

    assert result["verdict"] == "CANDIDATE_AUDIT_FAIL_BLOCKED", f"Got {result['verdict']}"
    assert any("CANDIDATE_DRY_RUN" in e for e in result["errors"])
    print("test_fail_missing_formula_status PASSED")


def test_fail_missing_manual_approval():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        out_dir = tmp / "wnba_outputs"
        out_dir.mkdir()

        proj_rows = create_test_candidate_projections()
        proj_rows[0]["manual_approval_required"] = "False"

        proj_file = out_dir / "projections_with_stakes_candidate_v21_10.csv"
        rec_file = out_dir / "recommended_bets_candidate_v21_10.csv"
        summary_file = out_dir / "projection_staking_candidate_summary_v21_10.json"

        write_csv(proj_file, proj_rows)
        write_csv(out_dir / "recommended_bets_candidate_v21_10.csv", create_test_candidate_recommended())
        write_json(out_dir / "projection_staking_candidate_summary_v21_10.json", {"stats": {"total": 3}})

        with patch("wnba_projection_candidate_quality_audit_v21_10.PROJ_CANDIDATE", proj_file), \
             patch("wnba_projection_candidate_quality_audit_v21_10.REC_CANDIDATE", out_dir / "recommended_bets_candidate_v21_10.csv"), \
             patch("wnba_projection_candidate_quality_audit_v21_10.SUMMARY_CANDIDATE", out_dir / "projection_staking_candidate_summary_v21_10.json"), \
             patch("wnba_projection_candidate_quality_audit_v21_10.OUT", out_dir):

            result = audit.audit_candidates(
                pd.read_csv(proj_file),
                pd.read_csv(out_dir / "recommended_bets_candidate_v21_10.csv"),
                json.loads((out_dir / "projection_staking_candidate_summary_v21_10.json").read_text())
            )

    assert result["verdict"] == "CANDIDATE_AUDIT_FAIL_BLOCKED", f"Got {result['verdict']}"
    assert any("Manual approval required" in e for e in result["errors"])
    print("test_fail_missing_manual_approval PASSED")


def test_edge_math_verification():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        out_dir = tmp / "wnba_outputs"
        out_dir.mkdir()

        proj_rows = create_test_candidate_projections()
        proj_rows[0]["edge"] = "1.0"

        proj_file = out_dir / "projections_with_stakes_candidate_v21_10.csv"
        rec_file = out_dir / "recommended_bets_candidate_v21_10.csv"
        summary_file = out_dir / "projection_staking_candidate_summary_v21_10.json"

        write_csv(proj_file, proj_rows)
        write_csv(out_dir / "recommended_bets_candidate_v21_10.csv", create_test_candidate_recommended())
        write_json(out_dir / "projection_staking_candidate_summary_v21_10.json", {"stats": {"total": 3}})

        with patch("wnba_projection_candidate_quality_audit_v21_10.PROJ_CANDIDATE", proj_file), \
             patch("wnba_projection_candidate_quality_audit_v21_10.REC_CANDIDATE", out_dir / "recommended_bets_candidate_v21_10.csv"), \
             patch("wnba_projection_candidate_quality_audit_v21_10.SUMMARY_CANDIDATE", out_dir / "projection_staking_candidate_summary_v21_10.json"), \
             patch("wnba_projection_candidate_quality_audit_v21_10.OUT", out_dir):

            result = audit.audit_candidates(
                pd.read_csv(proj_file),
                pd.read_csv(out_dir / "recommended_bets_candidate_v21_10.csv"),
                json.loads((out_dir / "projection_staking_candidate_summary_v21_10.json").read_text())
            )

    assert result["verdict"] == "CANDIDATE_AUDIT_WARN_RESEARCH_ONLY", f"Got {result['verdict']}"
    assert any("Edge math" in w for w in result["warnings"])
    print("test_edge_math_verification PASSED")


def test_side_consistency():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        out_dir = tmp / "wnba_outputs"
        out_dir.mkdir()

        proj_rows = create_test_candidate_projections()
        proj_rows[0]["side"] = "UNDER"

        proj_file = out_dir / "projections_with_stakes_candidate_v21_10.csv"
        rec_file = out_dir / "recommended_bets_candidate_v21_10.csv"
        summary_file = out_dir / "projection_staking_candidate_summary_v21_10.json"

        write_csv(proj_file, proj_rows)
        write_csv(out_dir / "recommended_bets_candidate_v21_10.csv", create_test_candidate_recommended())
        write_json(out_dir / "projection_staking_candidate_summary_v21_10.json", {"stats": {"total": 3}})

        with patch("wnba_projection_candidate_quality_audit_v21_10.PROJ_CANDIDATE", proj_file), \
             patch("wnba_projection_candidate_quality_audit_v21_10.REC_CANDIDATE", out_dir / "recommended_bets_candidate_v21_10.csv"), \
             patch("wnba_projection_candidate_quality_audit_v21_10.SUMMARY_CANDIDATE", out_dir / "projection_staking_candidate_summary_v21_10.json"), \
             patch("wnba_projection_candidate_quality_audit_v21_10.OUT", out_dir):

            result = audit.audit_candidates(
                pd.read_csv(proj_file),
                pd.read_csv(out_dir / "recommended_bets_candidate_v21_10.csv"),
                json.loads((out_dir / "projection_staking_candidate_summary_v21_10.json").read_text())
            )

    assert result["verdict"] == "CANDIDATE_AUDIT_WARN_RESEARCH_ONLY", f"Got {result['verdict']}"
    assert any("Side mismatch" in w for w in result["warnings"])
    print("test_side_consistency PASSED")


def test_confidence_sanity():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        out_dir = tmp / "wnba_outputs"
        out_dir.mkdir()

        proj_rows = create_test_candidate_projections()
        proj_rows[0]["confidence"] = "150"

        proj_file = out_dir / "projections_with_stakes_candidate_v21_10.csv"
        rec_file = out_dir / "recommended_bets_candidate_v21_10.csv"
        summary_file = out_dir / "projection_staking_candidate_summary_v21_10.json"

        write_csv(proj_file, proj_rows)
        write_csv(out_dir / "recommended_bets_candidate_v21_10.csv", create_test_candidate_recommended())
        write_json(out_dir / "projection_staking_candidate_summary_v21_10.json", {"stats": {"total": 3}})

        with patch("wnba_projection_candidate_quality_audit_v21_10.PROJ_CANDIDATE", proj_file), \
             patch("wnba_projection_candidate_quality_audit_v21_10.REC_CANDIDATE", out_dir / "recommended_bets_candidate_v21_10.csv"), \
             patch("wnba_projection_candidate_quality_audit_v21_10.SUMMARY_CANDIDATE", out_dir / "projection_staking_candidate_summary_v21_10.json"), \
             patch("wnba_projection_candidate_quality_audit_v21_10.OUT", out_dir):

            result = audit.audit_candidates(
                pd.read_csv(proj_file),
                pd.read_csv(out_dir / "recommended_bets_candidate_v21_10.csv"),
                json.loads((out_dir / "projection_staking_candidate_summary_v21_10.json").read_text())
            )

    assert result["verdict"] == "CANDIDATE_AUDIT_WARN_RESEARCH_ONLY", f"Got {result['verdict']}"
    assert any("Confidence sanity" in w for w in result["warnings"])
    print("test_confidence_sanity PASSED")


def test_units_cap():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        out_dir = tmp / "wnba_outputs"
        out_dir.mkdir()

        proj_rows = create_test_candidate_projections()
        proj_rows[0]["suggested_units"] = "0.75"

        proj_file = out_dir / "projections_with_stakes_candidate_v21_10.csv"
        rec_file = out_dir / "recommended_bets_candidate_v21_10.csv"
        summary_file = out_dir / "projection_staking_candidate_summary_v21_10.json"

        write_csv(proj_file, proj_rows)
        write_csv(out_dir / "recommended_bets_candidate_v21_10.csv", create_test_candidate_recommended())
        write_json(out_dir / "projection_staking_candidate_summary_v21_10.json", {"stats": {"total": 3}})

        with patch("wnba_projection_candidate_quality_audit_v21_10.PROJ_CANDIDATE", proj_file), \
             patch("wnba_projection_candidate_quality_audit_v21_10.REC_CANDIDATE", out_dir / "recommended_bets_candidate_v21_10.csv"), \
             patch("wnba_projection_candidate_quality_audit_v21_10.SUMMARY_CANDIDATE", out_dir / "projection_staking_candidate_summary_v21_10.json"), \
             patch("wnba_projection_candidate_quality_audit_v21_10.OUT", out_dir):

            result = audit.audit_candidates(
                pd.read_csv(proj_file),
                pd.read_csv(out_dir / "recommended_bets_candidate_v21_10.csv"),
                json.loads((out_dir / "projection_staking_candidate_summary_v21_10.json").read_text())
            )

    assert result["verdict"] == "CANDIDATE_AUDIT_WARN_RESEARCH_ONLY", f"Got {result['verdict']}"
    assert any("Units sanity" in w and "0.5" in w for w in result["warnings"])
    print("test_units_cap PASSED")


if __name__ == "__main__":
    tests = [
        test_all_pass,
        test_warning_market_dependence,
        test_warning_units_sanity,
        test_fail_missing_formula_status,
        test_fail_missing_manual_approval,
        test_edge_math_verification,
        test_side_consistency,
        test_confidence_sanity,
        test_units_cap,
    ]

    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"{t.__name__} FAILED: {e}")
            import traceback
            traceback.print_exc()
            sys.exit(1)

    print("\n=== ALL PROJECTION CANDIDATE QUALITY AUDIT TESTS PASSED ===")