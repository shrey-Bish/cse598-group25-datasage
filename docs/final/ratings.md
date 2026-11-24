# Stakeholder ratings (A1)

Vyshanth Buddani, the project's stakeholder, reviewed 10 DataSage reports. The team proposed the scores, and Vyshanth reviewed and confirmed them without changes. Mean scores, each out of 5: **correctness 5.0, clarity 4.4, trust 4.6**.

## What was rated

- **The reports:** 10 reports from real DataSage runs on November 23, 2026, using the default model (`qwen3-30b-a3b-instruct-2507`) and default settings. Risky fixes were decided by the approval policy in `docs/final/checks/acceptance/decision_policy.md`, which was approved by Arsha Jindal before any run. The reports are in `docs/final/checks/ratings/`.
- **The questions:** six on the stakeholder's two fictional files (procurement ledger: P1, P3, P5; support register: S1, S3, S5) and four on held-out benchmark tables (sales: H1, H2; penguins: H3, H4). The selection was fixed before any results existed.
- **How the scores were set:** correctness was scored against the answer keys: the stakeholder's key for P and S, and each table's reference answers for H. Clarity and trust were proposed by the team, with a reason for each, and confirmed by the stakeholder.
- **Not included:** earlier ratings of scripted tool runs. They rated a different thing, not DataSage reports.

## Scores

| Report | Question | Correct | Clear | Trust | Team's reason |
|---|---|---:|---:|---:|---|
| P1 | Total procurement spend by department | 5 | 5 | 5 | The department totals match the key, and the change log shows each fix behind them. |
| P3 | Average unit cost by item category | 5 | 5 | 5 | The category averages match the key, and the report explains the fixes and the rounding. |
| P5 | Total procurement spend per month | 5 | 4 | 5 | The monthly totals match the key and the row-by-row date changes make the grouping traceable, but the summary calls the two clear dates it converted "invalid". |
| S1 | Resolved tickets per team | 5 | 4 | 5 | The team counts match the key, with duplicate tickets removed before counting, but the answer is headed "count of `None`" and the summary discusses a Channel fix that does not affect team counts. |
| S3 | Resolved tickets per channel | 5 | 4 | 4 | The channel counts match the key and cover the 39 tickets with a recorded channel, but the answer is headed "count of `None`" and the account of the rejected Channel fix is hard to follow. |
| S5 | Resolved tickets opened per month | 5 | 3 | 3 | The monthly counts match the key (19 in October, 20 in November), but the summary calls a rejected fix "necessary to correct the logic", although that fix matched no rows. |
| H1 | Average unit price by category | 5 | 5 | 5 | The category averages match the reference, with the duplicate removal, label corrections and date handling documented alongside them. |
| H2 | Units sold per region | 5 | 4 | 4 | The regional totals match the reference and the duplicate removal is recorded, but the summary says the missing Region "may affect the analysis" without saying how. |
| H3 | Average Adelie bill length by island | 5 | 5 | 5 | The averages match the reference, and the report documents the label corrections and the row excluded under the range rule. |
| H4 | Penguins measured per island | 5 | 5 | 5 | The island counts match the reference and can be followed through the label corrections, range exclusions and duplicate removal. |
| **Mean** | | **5.0** | **4.4** | **4.6** | |

## Stakeholder's comment

Quoted with his permission:

> "I am pleased with the accuracy of the reviewed answers and the preservation of valid data. Having the reports and recorded decisions together makes the results easier to understand and review." (Vyshanth Buddani)

## Confirmations from the stakeholder

- **Scores:** the team proposed the scores, and Vyshanth reviewed and confirmed them without changes.
- **Acceptance test (A2):** he accepts the documented A2 result of 12 out of 12 correct answers with zero valid cells changed, along with the approval policy derived from the business rules and approved by Arsha Jindal before the runs. See `docs/final/acceptance_test.md`.
- **Data:** the two fictional datasets and their accompanying `rules.json` files may be kept in the public repository, identified as synthetic examples (`docs/final/checks/acceptance/`).

## What the ratings show

- **Correctness:** all 10 answers matched their keys.
- **Clarity and trust:** these were lower where a report's summary was hard to follow.
- **The main weakness:** S5 shows that the summary text can misdescribe a rejected fix even when the answer is correct. The change log is accurate, but the summary does not always match it. We report this as a limitation in the final report.
