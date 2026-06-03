# DAILY OPERATIONAL RUNBOOK — WNBA EDGE LAB V21.9

## SECTION 1: DAILY COMMAND SEQUENCE

Run from project folder. All commands listed first, annotations after.

```
cd C:\Users\User\Desktop\WNBA_EDGE_LAB_CLEAN

py run_v21_8_advisory_cycle.py --features
py telegram_wnba_operator_v21_9.py --picks --dry-run
py telegram_wnba_operator_v21_9.py --portfolio --dry-run
py telegram_wnba_operator_v21_9.py --dry-run
py bet_timing_clv_audit_v21_9.py
```

If ACTIONABLE rows > 0 and you intend to bet:

```
py manual_bet_entry_v21_9.py --dry-run --game "AWAY @ HOME" --market "MARKET" --direction SIDE --line N --odds X.XX --stake X.XX --game-start "YYYY-MM-DDTHH:MM:SS+00:00" --signal-time "YYYY-MM-DDTHH:MM:SS+00:00"
```

Then only after explicit approval:

```
py manual_bet_entry_v21_9.py --enter --game "AWAY @ HOME" --market "MARKET" --direction SIDE --line N --odds X.XX --stake X.XX --game-start "YYYY-MM-DDTHH:MM:SS+00:00" --signal-time "YYYY-MM-DDTHH:MM:SS+00:00"
```

Render verification (PowerShell):

```
(Invoke-WebRequest https://wnba-edge-lab.onrender.com/ -UseBasicParsing).StatusCode
(Invoke-WebRequest https://wnba-edge-lab.onrender.com/portfolio -UseBasicParsing).StatusCode
```

Both must return 200.

---

## SECTION 2: COMMAND CLASSIFICATION

| Command | Type | Writes |
|---|---|---|
| `run_v21_8_advisory_cycle.py --features` | ARTIFACT REFRESH | wnba_outputs/*.csv, *.json. No bet_tracker write. No betting. |
| `telegram_wnba_operator_v21_9.py --picks --dry-run` | READ-ONLY | None |
| `telegram_wnba_operator_v21_9.py --portfolio --dry-run` | READ-ONLY | None |
| `telegram_wnba_operator_v21_9.py --dry-run` | READ-ONLY | None |
| `bet_timing_clv_audit_v21_9.py` | ARTIFACT REFRESH (audit only) | wnba_outputs/bet_timing_clv_audit_*.csv, *_summary_*.json, *_report_*.txt. No bet_tracker write. |
| `manual_bet_entry_v21_9.py --dry-run` | READ-ONLY | None |
| `manual_bet_entry_v21_9.py --enter ...` | WRITE | bet_tracker.csv (appends one row) |
| `py -m py_compile` any core file | READ-ONLY | None |

---

## SECTION 3: CURRENT BASELINE EXPECTED OUTPUTS

These are the expected outputs as of the last verified run. The hidden-row count and open-exposure values will change as games are scheduled and settled. Treat these as the current baseline, not permanent invariants.

**--picks --dry-run:**
```
No actionable model picks after source freshness/risk filtering.
Manual approval required · No auto-betting · No formula changes.
Hidden non-actionable rows: 8 (HIDDEN_STALE: 8).
```

**--portfolio --dry-run:**
```
Open exposure: 0.00u (0 bets)
Proposed ACTIONABLE: 0 (0 rows)
Combined: 0.00u open + proposed
Reference cap: not configured (display only)
Manual approval required · No auto-betting · No formula changes
```

**--dry-run (full):**
```
Cycle: OK
Odds: OK_WITH_WARNINGS
Formula Gate: EVIDENCE_COLLECTION_ONLY
Open Bets: (none)
Model Health: n/a
Safety Footer: all 5 gates present
```

**bet_timing_clv_audit:**
```
Settled: 38 | Win rate: 60.5% | Net P/L: +0.71u | ROI: +18.7%
Line CLV: avg=-0.45 pos=3 flat=27 neg=8
Price CLV: avg=+0.66% known=34 unknown=4
```

---

## SECTION 4: STOP CONDITIONS

STOP and do not proceed if ANY of the following:

1. `run_v21_8_advisory_cycle.py` produces a traceback or non-zero exit code.
2. `--picks --dry-run` shows ACTIONABLE rows but Manual Approval Checklist is not complete.
3. `--portfolio --dry-run` shows open exposure > 0 and you have not verified the open bets are expected.
4. `--dry-run` shows Formula Gate != EVIDENCE_COLLECTION_ONLY.
5. `--dry-run` shows any safety gate missing (NO_AUTO_BETTING, NO_FORMULA_REPLACEMENT, NO_STAKING_CHANGES, NO_THRESHOLD_CHANGES, MANUAL_APPROVAL_REQUIRED).
6. Render /portfolio returns 404 after 3 retries spaced 2 minutes apart.
7. `bet_timing_clv_audit_v21_9.py` produces errors or the summary JSON shows unexpected data (e.g., settled count differs from expected, indicating bet_tracker corruption).
8. `py -m py_compile` fails on any of the 4 core files (app.py, site_state_v21_9.py, telegram_wnba_operator_v21_9.py, manual_bet_entry_v21_9.py).
9. Any command produces output you cannot explain. Stop. Investigate. Ask.

---

## SECTION 5: MANUAL APPROVAL CHECKLIST (before ANY bet entry)

Complete every item. Do not skip. No exceptions.

```
[ ] 1. --picks --dry-run shows ACTIONABLE rows > 0
[ ] 2. Each ACTIONABLE row has queue_actionability=ACTIONABLE
       (not HIDDEN_STALE, not ADVISORY_ONLY_MANUAL_REVIEW)
[ ] 3. Each ACTIONABLE row has a valid game_start_utc (not empty, not in the past)
[ ] 4. Each ACTIONABLE row has a valid line (not NO_LINE)
[ ] 5. Each ACTIONABLE row has advisory_label != NEUTRAL
[ ] 6. Each ACTIONABLE row has is_stale=false
[ ] 7. --portfolio --dry-run: combined exposure (open + proposed) is within
       your personal risk tolerance
[ ] 8. Game date verified against schedule (exact date + away + home match)
[ ] 9. Line and odds verified as current (not stale market data)
[ ] 10. manual_bet_entry --dry-run executed and row verified correct
[ ] 11. Timing fields populated: --game-start and --signal-time in ISO 8601 UTC
[ ] 12. Explicit operator approval given (verbal or written confirmation)
```

Only after all 12 boxes are ticked do you run `--enter`.

If any checkbox cannot be ticked: DO NOT BET. Investigate.

---

## SECTION 6: TELEGRAM OPERATOR CHECKLIST

```
[ ] 1. Run --dry-run and verify output
[ ] 2. Formula Gate = EVIDENCE_COLLECTION_ONLY
[ ] 3. All 5 safety gates present in footer
[ ] 4. If ACTIONABLE rows exist: risk warning included in message
[ ] 5. If 0 ACTIONABLE rows: message says "No actionable picks"
[ ] 6. Never imply auto-betting or auto-execution
[ ] 7. Never omit "Manual approval required"
```

---

## SECTION 7: RENDER VERIFICATION CHECKLIST

```
[ ] 1. https://wnba-edge-lab.onrender.com/ returns 200
[ ] 2. https://wnba-edge-lab.onrender.com/portfolio returns 200
[ ] 3. Main page: 0 open bets, hidden rows count, safety gates visible
[ ] 4. Portfolio page: Open exposure, Proposed ACTIONABLE, Hidden count correct
[ ] 5. Portfolio page: "DISPLAY ONLY. No auto-betting." visible
[ ] 6. All 8 approval pills visible:
       ENVIRONMENT_SAMPLE_LOCK, INJURY_CONFIRMATION_LOCK,
       MANUAL_APPROVAL_REQUIRED, MODEL_SAMPLE_LOCK, NO_AUTO_BETTING,
       NO_FORMULA_REPLACEMENT, NO_STAKING_CHANGES, NO_THRESHOLD_CHANGES
[ ] 7. No JavaScript errors in browser console
```

PowerShell one-liners:

```
(Invoke-WebRequest https://wnba-edge-lab.onrender.com/ -UseBasicParsing).StatusCode
(Invoke-WebRequest https://wnba-edge-lab.onrender.com/portfolio -UseBasicParsing).StatusCode
```

---

## SECTION 8: END-OF-DAY / POST-GAME TRACKING CHECKLIST

Run after all WNBA games for the day have settled:

```
[ ] 1. Run morning refresh (run_v21_8_advisory_cycle.py --features)
[ ] 2. --picks --dry-run: verify queue updated, stale rows reclassified if needed
[ ] 3. --portfolio --dry-run: verify open exposure reflects any new settlements
[ ] 4. bet_timing_clv_audit_v21_9.py: verify settled count increased
[ ] 5. Review CLV summary: positive/negative CLV on today's settled bets
[ ] 6. Settlement update method is unverified. Do not directly edit
       bet_tracker.csv unless using an approved backup + validation procedure.
[ ] 7. Full --dry-run: verify end-of-day state is consistent
[ ] 8. Render pages still return 200
[ ] 9. Note any anomalies in a daily log (text file, not code)
```

---

## SECTION 9: SAFETY INVARIANTS

- No auto-betting. Ever.
- No formula changes without Hermes approval.
- No staking changes without explicit operator approval.
- No threshold changes without explicit operator approval.
- No queue/actionability logic changes without explicit operator approval.
- Hidden/non-actionable rows never contribute to proposed exposure.
- 0 ACTIONABLE rows = 0 proposed queue exposure.
- Reference cap is display-only, never enforced.
- Formula Gate must remain EVIDENCE_COLLECTION_ONLY.
- Settlement update method is unverified. Do not directly edit bet_tracker.csv unless using an approved backup + validation procedure.

---

## SECTION 10: TROUBLESHOOTING

| Symptom | Action |
|---|---|
| Render /portfolio 404 | Wait 3 min, retry. If persistent after 3 attempts, manual redeploy on Render dashboard. |
| Advisory cycle traceback | Check wnba_outputs/ for partial writes. Do not proceed past Step A. |
| bet_tracker.csv corruption | Restore from latest backup in project root. Validate with py_compile after any edit. |
| Compile error after edit | Revert edit immediately. Re-run py_compile before any other action. |
| Unexpected --dry-run output | Stop. Compare against Section 3 baseline. Investigate discrepancies. |

---

## SECTION 11: UNCERTAINTIES

1. **Advisory cycle runtime**: `run_v21_8_advisory_cycle.py --features` was still running after 2+ minutes in testing. Expected total duration is unverified — may be 5-15 min depending on data fetch. Monitor output.

2. **teamgamelogs readiness**: Render page shows "official teamgamelogs ready: NO". Impact on advisory quality is unverified — the advisory cycle may produce fewer or lower-quality signals without team game logs.

3. **player props market readiness**: Render page shows "player props market ready: NO". Player prop bets should be treated as higher-risk until this source is restored.

4. **timing_instrumentation readiness**: CLV audit summary shows `timing_readiness_pct: 0.0`. No settled bets have EntryTimeUTC, GameStartTimeUTC, or ClosingTimeUTC populated. Timing-based CLV analysis (minutes before tip, late bet detection) is not yet active. All new bets should populate `--game-start` and `--signal-time` to enable this.

5. **Dual queue files**: Two queue files exist — `hermes_manual_market_queue_v21_9.csv` (8 rows, no queue_actionability column) and `hermes_advisory_queue_v21.csv` (8 rows, all HIDDEN_STALE, with queue_actionability). The telegram operator reads from the advisory queue. How the advisory cycle merges these two sources is unverified.

6. **Ladder patterns (historical)**: CLV audit identified 2 ladder patterns in settled bets (LAS OVER Alt Game Total 2026-05-30, LVA/GSV OVER Game Total 2026-05-31). No action needed today. Be aware the system flags ladders as concentration risk for future bet entry.
