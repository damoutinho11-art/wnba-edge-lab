# WNBA Edge Lab Safe Automation Policy

This repository may automate the research/model pipeline only.

Allowed automation:
- data fetches
- feature building
- diagnostics
- model audits
- model upgrade recommendations
- backtests
- advisory scoring
- result/CLV tracking
- dashboard output refreshes

Disallowed automation:
- placing bets
- auto-approving Hermes actions
- changing staking rules
- changing thresholds
- replacing formulas
- submitting wagers to any sportsbook or external betting service

Required locks:
- `NO_AUTO_BETTING`
- `MANUAL_APPROVAL_REQUIRED`
- `NO_FORMULA_REPLACEMENT`
- `NO_STAKING_CHANGES`
- `NO_THRESHOLD_CHANGES`

The user remains responsible for any betting decision outside this system.
