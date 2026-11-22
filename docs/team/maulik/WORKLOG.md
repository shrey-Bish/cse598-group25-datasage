# Maulik work log

## M1 — date handling (November 22, 2026)

- Normalize clear dates and ISO timestamps, including the Chicago inspection extract, without timezone shifts.
- Blank unreadable dates automatically at low risk; keep ambiguous values until an explicit day/month order is approved.
- Expose ambiguous interpretations in date checks and pause browser Auto mode for their conversion.
- Record every changed date cell in the change log and report; generated replay code reproduces the exact changes.
- Add parser, coverage, approval, audit, replay and Chicago regression tests. Update the previous risk expectation for unreadable dates to the M1 policy.
- Validation: `python -m pytest -q tests` passes all 150 tests, including local browser-server tests; `git diff --check` passes. The Chicago fixture retains all rows and every populated inspection date.

## M2 — refund rule (November 22, 2026)

- Add the `allow_negative_quantities` boolean, with a per-column setting and a scoped top-level shorthand for Quantity/Qty.
- Use the same refund exemption in numeric checks, explicit range checks, coverage checks, bulk range fixes and validation.
- Keep the lower bound for nonnegative values and all upper bounds; do not relax unrelated column rules.
- Keep refund-only ranges without asking or recording a no-op version. Preserve the policy in range-fix audit records and replay code.
- Add tests for enabled, disabled, omitted and malformed settings, text refunds, more than ten refunds, upper/lower bounds, coverage, validation and replay. Document the rules format in README.
- Validation: the combined M1+M2 tree passes all 162 tests (`python -m pytest -q tests`), including browser-server tests. Replay tests also cover formatted text and reject scientific-notation strings consistently with the checks. `git diff --check` passes.
