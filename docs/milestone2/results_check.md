# Milestone 2 independent results check

Reviewer: Maulik Jadav (`maulik-jadav`)  
Date: November 8, 2026 (MST)  
Repository revision checked: `234f04b0af08eb3e19953904e3d89a22c0a7fc15`

## Scope and conclusion

Completed the Milestone 2 results-check task in [TEAM_HANDOFF.md](../TEAM_HANDOFF.md):
regenerated the summaries, checked report Tables 6 to 8, reran B1 in a separate
directory, and read all four failed large-model-with-exclusion-rule sales held-out
traces. The numerical results match. The traces support the report's failure
explanation, with a clarification: the three spelling failures proposed row
exclusion, which the oracle rejected, rather than proposing spelling merges.

No stored evaluation results or report files were edited. No model/API calls were
needed. This check covers the current Milestone 2 assignment; the dates/refunds
implementation and real-file evaluation are listed separately as future work in
the handoff.

## Summary regeneration and report tables

Ran from the repository root with its dependencies installed:

```bash
python -m eval.summarize
git diff --exit-code -- eval/results/summary.md eval/results/summary.csv eval/results/summary.json
```

The diff exited successfully: all three regenerated summary files are identical
to the committed versions. Inspected the ten-page
[report PDF](Group25_DataSage_Milestone2.pdf), pages 5 and 6, and checked the
corresponding DOCX table cells against the regenerated aggregates.

- **Table 6:** all ten system/dataset rows agree with
  [summary.md](../../eval/results/summary.md) for answer accuracy, completion,
  detection precision/recall, errors handled, damage, tool success and median
  approvals. This includes 85%/85% dev accuracy for DataSage 235B and 70%/45% for
  B1. The report abbreviates tokens to thousands and latency to whole seconds
  (or `< 1`); these agree at the displayed precision. For example, sales 235B is
  152.3 s / 56,024 tokens in the summary and 152 s / 56k in the report.
- **Table 7:** all eight rows match for all four accuracy columns and combined
  held-out damage. The 235B exclusion-rule run is 100%/100% on dev and 80%/95%
  on held-out. The 30B exclusion-rule run is 95%/85% and 90%/80%; strict approval
  changes that to 100%/85% and 90%/65%. B2's held-out damage is correctly summed
  as 2 sales + 29 penguins = 31.
- **Table 8:** all six rows match after selecting the **same first ten tasks**
  per dataset. The ordinary 235B rows in `summary.md` aggregate twenty tasks,
  so their 85% accuracy must not be compared directly with this table. Using the
  task IDs present in `datasage-reject` and `datasage-novalidator` (identical
  sets, also the first ten sorted ordinary DataSage task IDs), the ordinary /
  reject-all / no-validator accuracies are 100% / 30% / 100% for sales and
  90% / 0% / 80% for penguins. Each row has ten tasks and zero damage.

No numerical discrepancy was found in Tables 6 to 8. The Table 8 subset is an
important reproduction detail, not a report error.

## Independent B1 rerun

Environment: Python 3.14.3, pandas 3.0.5, macOS arm64; dependencies installed from
`requirements.txt`. Used a previously nonexistent directory so the resumable
runner could not reuse committed results. Extended the requested sales check to
all four splits (80 tasks):

```bash
python -m eval.run_eval --system b1 --dataset sales --results ../results-check/b1-rerun
python -m eval.run_eval --system b1 --dataset penguins --results ../results-check/b1-rerun
python -m eval.run_eval --system b1 --dataset sales-heldout --results ../results-check/b1-rerun
python -m eval.run_eval --system b1 --dataset penguins-heldout --results ../results-check/b1-rerun
```

Results, each out of twenty tasks:

- Sales dev: 14 correct (70%); detection P/R 0.74/0.80; errors handled 80%.
- Penguins dev: 9 correct (45%); detection P/R 1.00/0.81; errors handled 80%.
- Sales held-out: 8 correct (40%); detection P/R 0.79/0.86; errors handled 78%.
- Penguins held-out: 6 correct (30%); detection P/R 1.00/0.75; errors handled 76%.

All eighty tasks completed with zero damaged cells/rows and zero tokens. Compared
the complete task records by filename, including answers, reference answers,
detection counts, corrections and stop reasons. All values match with these
non-score differences:

1. `seconds` varies with the machine/run. Fresh median times were 0.0275, 0.0215,
   0.0230 and 0.0225 seconds in the split order above, all consistent with `< 1 s`.
2. Fresh records contain `extra: {}`, absent from the stored B1 records. This
   empty metadata field does not affect scoring.

To repeat the per-task comparison after running the commands above (choose a
fresh output directory for another independent run):

```bash
python - <<'PY'
import json
from pathlib import Path

for split in ("sales", "penguins", "sales-heldout", "penguins-heldout"):
    stored = {p.name: json.loads(p.read_text())
              for p in (Path("eval/results/b1") / split).glob("*.json")}
    fresh = {p.name: json.loads(p.read_text())
             for p in (Path("../results-check/b1-rerun/b1") / split).glob("*.json")}
    assert stored.keys() == fresh.keys() and len(fresh) == 20
    for name in stored:
        old, new = stored[name].copy(), fresh[name].copy()
        old.pop("seconds")
        new.pop("seconds")
        old.setdefault("extra", {})
        assert old == new, (split, name)
    print(split, "20/20 task records match, excluding runtime and empty metadata")
PY
```

## Trace inspection: four held-out sales failures

Read each complete JSONL trace and its sibling scored JSON under
[`eval/results/datasage-fix/sales-heldout/`](../../eval/results/datasage-fix/sales-heldout/).
These are exactly the four incorrect tasks in this split (16/20 correct = 80%).
Call numbers below are one-based tool-event positions in each trace.

- **[`salesh_01_q1`](../../eval/results/datasage-fix/sales-heldout/traces/salesh_01_q1.jsonl):**
  call 3 finds `Furnture` and `Accesories`. Call 7 merges only space variants;
  its recheck still lists both misspellings. Call 8 proposes excluding the typo
  rows and is rejected. Call 9 counts the separate typo groups: `Furniture: 12`
  plus `Furnture: 2` instead of 14, and `Accessories: 20` plus `Accesories: 1`
  instead of 21. The run finishes after ten calls. Additional observation:
  the final prose states the merged reference counts even though `analyze`
  returned split groups; the scored structured answer correctly remains wrong.
- **[`salesh_06_q0`](../../eval/results/datasage-fix/sales-heldout/traces/salesh_06_q0.jsonl):**
  call 3 identifies `Nort`, `Suoth` and `Wst`. Call 7 merges only `north`/`east`;
  call 10 proposes exclusion and is rejected. Call 11 sums Quantity with the
  typo groups intact: North 38 + Nort 2, South 52 + Suoth 1, West 57 + Wst 5,
  instead of North 40, South 53, West 62. Finished after twelve calls.
- **[`salesh_06_q1`](../../eval/results/datasage-fix/sales-heldout/traces/salesh_06_q1.jsonl):**
  calls 3 and 11 identify the same region misspellings; call 7 again merges
  only case variants. Call 12's exclusion proposal is rejected. Call 13 sums
  Electronics revenue into separate groups: North 360 + Nort 600 instead of
  960, and West 1,500 + Wst 2,250 instead of 3,750. Finished after fourteen calls.
- **[`salesh_03_q0`](../../eval/results/datasage-fix/sales-heldout/traces/salesh_03_q0.jsonl):**
  after reading rules and checking Category, calls 3 through 30 repeat
  `check_label_variants(Region)` with the same `Suoth -> South` suggestion.
  No fix or `analyze` call occurs. The scored record has `answer: null`,
  `completed: false`, and `stop_reason: tool_budget_exhausted` after thirty
  calls. This directly confirms the report's fourth failure cause.

All four scored records report zero damaged cells and zero damaged rows. The
report's Section 3.5 explanation is supported: three failures leave detected
spellings unmerged and one exhausts its budget. Clarification for review: the
oracle rejected an unsuitable **deletion** in the three spelling cases; it was
never asked to approve a spelling merge. The evidence points to fix selection,
rather than a failed detector or a rejected correct merge.

## Limits and review follow-up

Only deterministic B1 was rerun. Existing model scores and traces were audited;
this is not an independent rerun of the model systems or a repeated-run estimate.
The report already identifies single-run noise as a limitation. Shrey can use
this check when updating the submission and contribution links; no table-value
correction is needed, and the deletion-versus-merge clarification above may help
describe the remaining planning issue precisely.
