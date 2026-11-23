# No-regression check after M1 and M2

M1 (PR #38) changed how dates are read and fixed: clear dates and ISO timestamps are now converted to
`YYYY-MM-DD` automatically, unreadable ones are blanked, and ambiguous ones such as `03/04/2026` wait for
approval. M2 (PR #39) added the `allow_negative_quantities` rule for refunds. Both change the agent's
tools and prompt, so the final system was run again on the same questions as the Milestone 3 baseline.

## Held-out and test questions

`datasage-m3` (Qwen3-30B) on `sales-heldout`, `penguins-heldout`, `sales-test` and `penguins-test`, 80
questions, after both merges. Results are in `eval/results/regression_m1m2/datasage-m3/`; the baseline is
the recorded run in `eval/results/datasage-m3/`.

```bash
for d in sales-heldout penguins-heldout sales-test penguins-test; do
  python -m eval.run_eval --system datasage-m3 --dataset $d --workers 6 --results eval/results/regression_m1m2
done
```

| | Baseline (Nov 16) | After M1 and M2 |
|---|---:|---:|
| Right answers | 74 / 80 | 74 / 80 |
| Damaged cells | 0 | 0 |
| Tool errors | 0 | 0 |
| Runs ending in `finish` | 80 | 80 |
| Approvals asked | 182 | 176 |
| Planted errors corrected | 684 | 685 |
| Median seconds per question | 16.3 | 18.5 |

No regression. Two questions changed outcome, in opposite directions, and neither involves the new code
(the penguin tables have no date column and no refund rule):

- `penguinsh_04_q1` (total body mass by species) is now wrong. The agent skipped `drop_duplicates` this
  time, so one Adelie row was counted twice: Adelie is 112,600 against 108,975, exactly that row's 3,625 g.
- `penguinst_06_q1` (penguins measured on each island) is now right; the agent excluded one more
  rule-breaking row than in the baseline.

This is the same run-to-run variation the scale study measured (four runs of 200 questions between 94.0%
and 96.0%). The other five wrong answers are the same questions as in the baseline, all with the known
cause: rows that break a rule in a column the question does not use.

The new date code was exercised: `check_dates` and `parse_dates` ran 12 times each in the sales questions,
and all 7 questions grouped by month are right.

## Hard split

Not re-run here. M1 now reads 15 planted "bad" dates on the hard split as real dates: all are
`06/15/2026` (6 in `sales-hard`, 9 in `sales-hard2`), which is a valid date the generator lists as bad
(`BAD_DATES` in `eval/generate_hard.py`). None of those tables has a date question, so no answer changes;
only the errors-handled count for those distractor cells does.

## End-to-end smoke test (`python scripts/smoke_e2e.py`)

Two runs after the merges: 121 of 123 checks passed both times. Both failures were the inventory sample in Auto mode:
the answer was low in every warehouse, and one approval was not automatic.

The cause was not M1 or M2. Auto mode's safety pause (`auto_needs_person` in `app/web/runner.py`, added in
PR #22) held the `exclude_where` that drops the 18 rows with negative Units, because only 10 of those rows
were recorded as problems: a check lists at most 10 row ids. The smoke test does not answer a paused card,
so the fix was not applied and the negative rows stayed in. The same sequence pauses on the code from before
M1 and M2. The command line, which has no pause, gave the right answer in 5 of 5 repeats.

Fix (in the same PR as this note): `exclude_where` is no longer paused, because every row it drops is outside
a range rule; the pause stays for `exclude_rows` dropping rows whose only problem is a blank value, which is
what the Auto-mode study found. A test covers the 18-row case.

After the fix: **123 of 123 checks pass**, including the inventory sample in Auto mode with the right answer.
