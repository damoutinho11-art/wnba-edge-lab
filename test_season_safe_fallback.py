#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Regression tests for season-safe teamgamelogs cache fallback.
Tests the _filter_fallback_by_season helper and candidate loop behavior.
"""

import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# Ensure project root is on path
sys.path.insert(0, str(Path(__file__).parent))

import pandas as pd

# Import the module under test
import ultimate_fetcher_v21_4_1 as fetcher


def make_df(season_fetched=None, season_id=None, num_rows=3):
    """Create a test DataFrame with optional season columns."""
    data = {
        "GAME_ID": [f"game_{i}" for i in range(num_rows)],
        "TEAM": ["A", "B", "C"][:num_rows],
        "PTS": [80, 90, 85][:num_rows],
    }
    if season_fetched is not None:
        data["SeasonFetched"] = [str(season_fetched)] * num_rows
    if season_id is not None:
        data["SEASON_ID"] = [str(season_id)] * num_rows
    return pd.DataFrame(data)


def test_row_level_mismatch_rejected():
    """SeasonFetched=2026, SEASON_ID=22026, requesting 2025 -> empty."""
    df = make_df(season_fetched=2026, season_id=22026)
    result = fetcher._filter_fallback_by_season(
        df, season=2025,
        source="official_teamgamelogs_base",
        fallback_path=Path("official_team_game_logs_2026.csv")
    )
    assert result.empty, f"Expected empty, got {len(result)} rows"
    print("test_row_level_mismatch_rejected PASSED")


def test_row_level_exact_match_seasonfetched():
    """SeasonFetched=2025, requesting 2025 -> rows returned."""
    df = make_df(season_fetched=2025)
    result = fetcher._filter_fallback_by_season(
        df, season=2025,
        source="official_teamgamelogs_base",
        fallback_path=Path("official_team_game_logs_2026.csv")
    )
    assert len(result) == 3, f"Expected 3 rows, got {len(result)}"
    print("test_row_level_exact_match_seasonfetched PASSED")


def test_row_level_exact_match_season_id():
    """SEASON_ID=22025 (2202+season), requesting 2025 -> rows returned."""
    df = make_df(season_id=22025)
    result = fetcher._filter_fallback_by_season(
        df, season=2025,
        source="official_teamgamelogs_base",
        fallback_path=Path("official_team_game_logs_2026.csv")
    )
    assert len(result) == 3, f"Expected 3 rows, got {len(result)}"
    print("test_row_level_exact_match_season_id PASSED")


def test_row_level_both_columns_match():
    """Both SeasonFetched=2025 and SEASON_ID=22025 -> rows returned."""
    df = make_df(season_fetched=2025, season_id=22025)
    result = fetcher._filter_fallback_by_season(
        df, season=2025,
        source="official_teamgamelogs_base",
        fallback_path=Path("official_team_game_logs_2026.csv")
    )
    assert len(result) == 3, f"Expected 3 rows, got {len(result)}"
    print("test_row_level_both_columns_match PASSED")


def test_row_level_seasonfetched_mismatch_then_season_id_empty():
    """SeasonFetched mismatch filters to empty before SEASON_ID check."""
    df = make_df(season_fetched=2026, season_id=22025)
    result = fetcher._filter_fallback_by_season(
        df, season=2025,
        source="official_teamgamelogs_base",
        fallback_path=Path("any.csv")
    )
    assert result.empty, f"Expected empty after SeasonFetched filter, got {len(result)}"
    print("test_row_level_seasonfetched_mismatch_then_season_id_empty PASSED")


def test_path_proof_accepts_exact_filename():
    """No row columns, official_teamgamelogs_base, filename has exactly requested season."""
    df = make_df()  # no season columns
    result = fetcher._filter_fallback_by_season(
        df, season=2025,
        source="official_teamgamelogs_base",
        fallback_path=Path("official_team_game_logs_2025.csv")
    )
    assert len(result) == 3, f"Expected 3 rows, got {len(result)}"
    print("test_path_proof_accepts_exact_filename PASSED")


def test_path_proof_rejects_wrong_season():
    """No row columns, official_teamgamelogs_base, filename has different season."""
    df = make_df()
    result = fetcher._filter_fallback_by_season(
        df, season=2025,
        source="official_teamgamelogs_base",
        fallback_path=Path("official_team_game_logs_2026.csv")
    )
    assert result.empty, f"Expected empty for wrong season, got {len(result)}"
    print("test_path_proof_rejects_wrong_season PASSED")


def test_path_proof_rejects_mixed_seasons():
    """Filename with 2025 and 2026 -> rejected for 2025."""
    df = make_df()
    result = fetcher._filter_fallback_by_season(
        df, season=2025,
        source="official_teamgamelogs_base",
        fallback_path=Path("official_team_game_logs_2025_2026.csv")
    )
    assert result.empty, f"Expected empty for mixed seasons, got {len(result)}"
    print("test_path_proof_rejects_mixed_seasons PASSED")


def test_path_proof_rejects_20250():
    """Filename with 20250 (5 digits) -> rejected for 2025."""
    df = make_df()
    result = fetcher._filter_fallback_by_season(
        df, season=2025,
        source="official_teamgamelogs_base",
        fallback_path=Path("official_team_game_logs_20250.csv")
    )
    assert result.empty, f"Expected empty for 20250, got {len(result)}"
    print("test_path_proof_rejects_20250 PASSED")


def test_path_proof_rejects_12025():
    """Filename with 12025 -> rejected for 2025."""
    df = make_df()
    result = fetcher._filter_fallback_by_season(
        df, season=2025,
        source="official_teamgamelogs_base",
        fallback_path=Path("official_team_game_logs_12025.csv")
    )
    assert result.empty, f"Expected empty for 12025, got {len(result)}"
    print("test_path_proof_rejects_12025 PASSED")


def test_path_proof_rejects_no_season_token():
    """Filename with no 4-digit year -> rejected for 2025."""
    df = make_df()
    result = fetcher._filter_fallback_by_season(
        df, season=2025,
        source="official_teamgamelogs_base",
        fallback_path=Path("official_team_game_logs.csv")
    )
    assert result.empty, f"Expected empty for no season token, got {len(result)}"
    print("test_path_proof_rejects_no_season_token PASSED")


def test_path_proof_none_path_rejected():
    """fallback_path=None -> rejected."""
    df = make_df()
    result = fetcher._filter_fallback_by_season(
        df, season=2025,
        source="official_teamgamelogs_base",
        fallback_path=None
    )
    assert result.empty, f"Expected empty for None path, got {len(result)}"
    print("test_path_proof_none_path_rejected PASSED")


def test_non_teamgamelogs_preserves_old_behavior():
    """Non-teamgamelogs source with no row columns returns unchanged."""
    df = make_df()
    result = fetcher._filter_fallback_by_season(
        df, season=2025,
        source="official_playergamelogs_base",
        fallback_path=Path("some_file.csv")
    )
    assert len(result) == 3, f"Expected 3 rows unchanged, got {len(result)}"
    print("test_non_teamgamelogs_preserves_old_behavior PASSED")


def test_non_teamgamelogs_with_row_columns_filters():
    """Non-teamgamelogs with row columns still filters exactly."""
    df = make_df(season_fetched=2026)
    result = fetcher._filter_fallback_by_season(
        df, season=2025,
        source="official_playergamelogs_base",
        fallback_path=Path("some_file.csv")
    )
    assert result.empty, f"Expected empty for row-level mismatch, got {len(result)}"
    print("test_non_teamgamelogs_with_row_columns_filters PASSED")


def test_invalid_cache_skipped_uses_output_fallback():
    """First candidate has 2026 rows, season=2025 -> skip, use output fallback."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        cache_dir = tmp / "wnba_cache_v21"
        cache20_dir = tmp / "wnba_cache_v20"
        out_dir = tmp / "wnba_outputs"
        cache_dir.mkdir()
        cache20_dir.mkdir()
        out_dir.mkdir()

        # Create a 2026 cache file (should be rejected for 2025)
        bad_cache = cache20_dir / "official_team_game_logs_2026.csv"
        df_2026 = make_df(season_fetched=2026, season_id=22026)
        df_2026.to_csv(bad_cache, index=False)

        # Create output fallback with 2025 data
        output_fallback = out_dir / "official_mobile_teamgamelogs_v21.csv"
        df_2025 = make_df(season_fetched=2025, season_id=22025)
        df_2025.to_csv(output_fallback, index=False)

        # Patch module paths and functions
        with patch("ultimate_fetcher_v21_4_1.CACHE", cache_dir), \
             patch("ultimate_fetcher_v21_4_1.CACHE20", cache20_dir), \
             patch("ultimate_fetcher_v21_4_1.OUT", out_dir), \
             patch("ultimate_fetcher_v21_4_1.stats_get", return_value=(None, "timeout")), \
             patch("ultimate_fetcher_v21_4_1.save_df") as mock_save_df:

            # Mock _load_teamgamelogs_output_fallback to return our 2025 df
            with patch("ultimate_fetcher_v21_4_1._load_teamgamelogs_output_fallback",
                      return_value=df_2025) as mock_output_fb:

                cand_out = cache_dir / "mobile_teamgamelogs_2025.csv"
                cand_fb1 = cache_dir / "official_wnba_team_boxscores_traditional_2025.csv"
                cand_fb2 = bad_cache
                cand_fb3 = cache20_dir / "teamgamelogs_traditional_2026.csv"

                rec, df = fetcher.official_fetch_table(
                    "official_teamgamelogs_base", "leaguegamelog",
                    fetcher.leaguegamelog_params(2025, "T"), 2025,
                    cand_out, [cand_fb1, cand_fb2, cand_fb3],
                    timeout=1, retries=1
                )

                # Verify OUTPUT_FALLBACK_USED
                assert rec.state == "OUTPUT_FALLBACK_USED", f"Expected OUTPUT_FALLBACK_USED, got {rec.state}"
                assert len(df) == 3, f"Expected 3 rows from output fallback, got {len(df)}"
                assert rec.fallback_path == str(output_fallback), f"Wrong fallback_path: {rec.fallback_path}"

                # Verify save_df was NOT called for OUTPUT_FALLBACK_USED path
                for call in mock_save_df.call_args_list:
                    args, kwargs = call
                    if len(args) > 0:
                        path = args[0]
                        if path == cand_out:
                            assert False, "save_df called on per-season cache for OUTPUT_FALLBACK_USED"
                print("test_invalid_cache_skipped_uses_output_fallback PASSED")


def test_valid_2026_fallback_accepted():
    """Valid 2026 cache file accepted for season=2026."""
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)
        cache_dir = tmp / "wnba_cache_v21"
        cache20_dir = tmp / "wnba_cache_v20"
        out_dir = tmp / "wnba_outputs"
        cache_dir.mkdir()
        cache20_dir.mkdir()
        out_dir.mkdir()

        # Create a valid 2026 cache file
        good_cache = cache20_dir / "official_team_game_logs_2026.csv"
        df_2026 = make_df(season_fetched=2026, season_id=22026)
        df_2026.to_csv(good_cache, index=False)

        with patch("ultimate_fetcher_v21_4_1.CACHE", cache_dir), \
             patch("ultimate_fetcher_v21_4_1.CACHE20", cache20_dir), \
             patch("ultimate_fetcher_v21_4_1.OUT", out_dir), \
             patch("ultimate_fetcher_v21_4_1.stats_get", return_value=(None, "timeout")), \
             patch("ultimate_fetcher_v21_4_1._load_teamgamelogs_output_fallback",
                  return_value=pd.DataFrame()) as mock_output_fb, \
             patch("ultimate_fetcher_v21_4_1.save_df") as mock_save_df:

            cand_out = cache_dir / "mobile_teamgamelogs_2026.csv"
            cand_fb1 = cache_dir / "official_wnba_team_boxscores_traditional_2026.csv"
            cand_fb2 = good_cache
            cand_fb3 = cache20_dir / "teamgamelogs_traditional_2026.csv"

            rec, df = fetcher.official_fetch_table(
                "official_teamgamelogs_base", "leaguegamelog",
                fetcher.leaguegamelog_params(2026, "T"), 2026,
                cand_out, [cand_fb1, cand_fb2, cand_fb3],
                timeout=1, retries=1
            )

            assert rec.state == "CACHE_FALLBACK_USED", f"Expected CACHE_FALLBACK_USED, got {rec.state}"
            assert len(df) == 3, f"Expected 3 rows, got {len(df)}"
            assert rec.fallback_path == str(good_cache), f"Expected fallback_path={good_cache}, got {rec.fallback_path}"
            print("test_valid_2026_fallback_accepted PASSED")


if __name__ == "__main__":
    tests = [
        test_row_level_mismatch_rejected,
        test_row_level_exact_match_seasonfetched,
        test_row_level_exact_match_season_id,
        test_row_level_both_columns_match,
        test_row_level_seasonfetched_mismatch_then_season_id_empty,
        test_path_proof_accepts_exact_filename,
        test_path_proof_rejects_wrong_season,
        test_path_proof_rejects_mixed_seasons,
        test_path_proof_rejects_20250,
        test_path_proof_rejects_12025,
        test_path_proof_rejects_no_season_token,
        test_path_proof_none_path_rejected,
        test_non_teamgamelogs_preserves_old_behavior,
        test_non_teamgamelogs_with_row_columns_filters,
        test_invalid_cache_skipped_uses_output_fallback,
        test_valid_2026_fallback_accepted,
    ]
    for t in tests:
        try:
            t()
        except Exception as e:
            print(f"{t.__name__} FAILED: {e}")
            sys.exit(1)
    print("\n=== ALL TESTS PASSED ===")