# Team Game Logs Fallback — Season-Safe Operations Note

**Applies to:** `ultimate_fetcher_v21_4_1.py` source `official_teamgamelogs_base`  
**Related commits:** `3da77da` (fallback fix), `f5764b8` (regression tests)  
**Test coverage:** `test_season_safe_fallback.py`

---

## 1. Source States & Meaning

| State | Meaning |
|-------|---------|
| `LIVE_FETCH_OK` | Official WNBA mobile endpoint (`stats.wnba.com`) returned rows **for the exact requested season**. No fallback used. |
| `CACHE_FALLBACK_USED` | Live fetch failed/empty. A cache candidate was accepted **only after season validation** (row-level or filename proof). `fallback_path` identifies the candidate. |
| `OUTPUT_FALLBACK_USED` | Live fetch failed **and no valid season-safe cache candidate** was available. The combined output file (`wnba_outputs/official_mobile_teamgamelogs_v21.csv`) was read, filtered to the requested season, and used **read-only**. No per-season cache is written. |
| `FETCH_FAILED_NO_CACHE` | Live fetch failed, no valid cache candidate, and output fallback empty/unavailable. No data for this source/season. |

---

## 2. Season-Safe Invariant (Non-Negotiable)

> **`official_teamgamelogs_base` must never satisfy a 2025 request with a 2026-only fallback.**

### Row-level proof wins
If the candidate DataFrame has `SeasonFetched` **or** `SEASON_ID` columns:
- Exact equality filter is applied (`SeasonFetched == str(season)` and `SEASON_ID == f"2{season}"`).
- Result is returned **even if empty** → candidate is **rejected**.
- Filename/path proof **cannot rescue** a row-level mismatch.

### Filename proof (only when no row-level season columns)
For `official_teamgamelogs_base` with **no** `SeasonFetched` and **no** `SEASON_ID`:
- Filename must contain **exactly one** discrete `20xx` token matching the requested season.
- Regex: `tokens = set(re.findall(r"(?<!\d)(20\d{2})(?!\d)", fallback_path.name))`
- Accept **only if** `tokens == {str(season)}`.

| Filename | season=2025 | Reason |
|---|---|---|
| `official_team_game_logs_2025.csv` | ✅ Accept | tokens == {'2025'} |
| `official_team_game_logs_2026.csv` | ❌ Reject | tokens == {'2026'} |
| `official_team_game_logs_2025_2026.csv` | ❌ Reject | tokens == {'2025','2026'} (mixed) |
| `official_team_game_logs_20250.csv` | ❌ Reject | tokens == {'20250'} (5 digits) |
| `official_team_game_logs_12025.csv` | ❌ Reject | tokens == {'12025'} (5 digits) |
| `official_team_game_logs.csv` | ❌ Reject | tokens == set() (no token) |

### Other sources
Non-teamgamelogs sources with no row-level season columns preserve old behavior (return unchanged). If row columns exist, they are filtered exactly.

---

## 3. Candidate Loop Behavior

`official_fetch_table()` iterates candidates in order: `[out_path] + fallbacks`.

For each candidate:
1. Skip if missing/empty.
2. Read CSV, normalize columns.
3. Call `_filter_fallback_by_season(df, season, source, fallback_path=candidate)`.
4. If filtered result non-empty → accept, save to `out_path` if missing, return `CACHE_FALLBACK_USED`.
5. If filtered result empty → **continue to next candidate**.
6. If read error → store `last_error`, continue.

**Only after ALL candidates exhausted:**
- If `source == "official_teamgamelogs_base"` → try `_load_teamgamelogs_output_fallback(season)`.
- If that returns data → return `OUTPUT_FALLBACK_USED`.
- Else → `FETCH_FAILED_NO_CACHE`.

**Key invariant:** `save_df(out_path, ...)` is **never called** for `OUTPUT_FALLBACK_USED`. The per-season cache remains unwritten.

---

## 4. Operational Interpretation

| State | Action |
|---|---|
| `LIVE_FETCH_OK` | ✅ Normal. No action needed. |
| `CACHE_FALLBACK_USED` | ✅ Acceptable. Cache was season-validated. Monitor if repeated across cycles. |
| `OUTPUT_FALLBACK_USED` | ⚠️ Degraded but **acceptable for advisory/safety operation** when season-filtered. **Not** an automatic failure. Must be visible in `ultimate_fetch_status_v21_4.json` review. If repeated for multiple cycles → investigate official endpoint health and cache freshness. |
| `FETCH_FAILED_NO_CACHE` | 🔴 Critical. No data for this source/season. Advisory cycle will be missing team game logs. Must investigate. |

### What `OUTPUT_FALLBACK_USED` Does **Not** Authorize
- ❌ Betting
- ❌ Model threshold changes
- ❌ Staking changes
- ❌ Formula changes
- ❌ Queue/actionability changes

---

## 5. Safety Invariants (Remain Unchanged)

- ✅ Manual approval required for every bet
- ✅ No auto-betting
- ✅ No formula changes without Hermes approval
- ✅ No staking changes without explicit operator approval
- ✅ No threshold changes without explicit operator approval
- ✅ No queue/actionability logic changes without explicit operator approval
- ✅ Formula Gate must remain `EVIDENCE_COLLECTION_ONLY`
- ✅ Hidden/non-actionable rows never contribute to proposed exposure
- ✅ Reference cap is display-only, never enforced

---

## 6. Regression Test Coverage

File: `test_season_safe_fallback.py` (run with `python3 test_season_safe_fallback.py`)

| Test | Verifies |
|---|---|
| `test_row_level_mismatch_rejected` | 2026 row-data rejected for 2025 request |
| `test_row_level_exact_match_seasonfetched` | 2025 `SeasonFetched` accepted |
| `test_row_level_exact_match_season_id` | 2025 `SEASON_ID`=22025 accepted |
| `test_row_level_both_columns_match` | Both columns present + matching = accepted |
| `test_row_level_seasonfetched_mismatch_then_season_id_empty` | `SeasonFetched` filters to empty before `SEASON_ID` check |
| `test_path_proof_accepts_exact_filename` | Exact-season filename accepted (no row cols) |
| `test_path_proof_rejects_wrong_season` | Wrong-season filename rejected |
| `test_path_proof_rejects_mixed_seasons` | `2025_2026` rejected |
| `test_path_proof_rejects_20250` | `20250` false token rejected |
| `test_path_proof_rejects_12025` | `12025` false token rejected |
| `test_path_proof_rejects_no_season_token` | No 4-digit token rejected |
| `test_path_proof_none_path_rejected` | `fallback_path=None` rejected |
| `test_non_teamgamelogs_preserves_old_behavior` | Non-TG sources unchanged when no row cols |
| `test_non_teamgamelogs_with_row_columns_filters` | Non-TG with row cols filtered exactly |
| `test_invalid_cache_skipped_uses_output_fallback` | Bad cache skipped → `OUTPUT_FALLBACK_USED`; `save_df` not called on out_path |
| `test_valid_2026_fallback_accepted` | Valid 2026 cache → `CACHE_FALLBACK_USED`; `fallback_path` = candidate |

---

## 7. Status Review Checklist

When reviewing `wnba_outputs/ultimate_fetch_status_v21_4.json` (or `data_source_health_v21.json`):

```
(Get-Content -Raw .\wnba_outputs\ultimate_fetch_status_v21_4.json | ConvertFrom-Json).records |
  Where-Object { $_.source -eq 'official_teamgamelogs_base' } |
  Select-Object source,season,state,rows,path,fallback_path,error |
  Format-List
```

Verify:
- [ ] `state` is one of the four documented states
- [ ] If `OUTPUT_FALLBACK_USED`: `rows` > 0, `fallback_path` ends with `official_mobile_teamgamelogs_v21.csv`
- [ ] If `CACHE_FALLBACK_USED`: `fallback_path` points to a cache file with matching season
- [ ] If `FETCH_FAILED_NO_CACHE`: investigate immediately
- [ ] No `2026` rows in `2025` result (season contamination = regression)

---

## 8. Quick Reference: Reproduction of 2025 Contamination (Fixed)

**Before fix (`c556acd`):**  
`official_teamgamelogs_base` 2025 used `wnba_cache_v20/official_team_game_logs_2026.csv` (126 rows) because `first_existing()` picked it by path alone.

**After fix (`3da77da`):**  
Same file is rejected — row-level `SeasonFetched`=2026 filters to empty → candidate skipped → output fallback used → 572 rows from combined output filtered to 2025.

**Validation command:**

```bash
py ultimate_fetcher_v21_4_1.py --seasons 2025,2026 --timeout 1 --retries 1 --skip-sdv
```

Expected:
- 2025: `OUTPUT_FALLBACK_USED` rows=572
- 2026: `CACHE_FALLBACK_USED` rows=126 (or `OUTPUT_FALLBACK_USED` rows=126 if valid 2026 cache missing)

---

*Last updated: v21.4 fetcher with season-safe fallback. Docs-only patch.*