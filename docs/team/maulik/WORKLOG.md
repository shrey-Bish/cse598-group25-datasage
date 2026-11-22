# Maulik work log

## M1 — date handling (November 22, 2026)

- Normalize clear dates and ISO timestamps, including the Chicago inspection extract, without timezone shifts.
- Blank unreadable dates automatically at low risk; keep ambiguous values until an explicit day/month order is approved.
- Expose ambiguous interpretations in date checks and pause browser Auto mode for their conversion.
- Record every changed date cell in the change log and report; generated replay code reproduces the exact changes.
- Add parser, coverage, approval, audit, replay and Chicago regression tests. Update the previous risk expectation for unreadable dates to the M1 policy.
- Validation: `python -m pytest -q tests` passes all 150 tests, including local browser-server tests; `git diff --check` passes. The Chicago fixture retains all rows and every populated inspection date.
