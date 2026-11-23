# Acceptance test (A2)

**Result: PASS.** DataSage answered **12 of 12** questions correctly (100.0%) and changed **0** valid cells (0 valid rows lost). The criterion agreed with the stakeholder on Oct 28 (`docs/meetings/2026-10-28-review.md`, success criteria) is "3 test files reach at least 90% answer accuracy with no valid data corrupted"; for 12 questions that means at least 11 correct and 0 damaged cells.

## Setup

- **Date and code:** November 23, 2026; `main` at `443b5c2bdfa9a3215cff9f5521de29d92c18ae27`.
- **Model and settings:** `qwen3-30b-a3b-instruct-2507` (DataSage's default), at most 30 tool calls, validator and coverage check on (the `run_agent` defaults). Each question is a separate run from the original file.
- **Files** (three, as the team handoff's A2 row asks):
  - Procurement ledger (fictional records from Vyshanth Buddani, published here as synthetic data with his permission): `docs/final/checks/acceptance/procurement_ledger/input.csv` (50 rows, sha256 `dff820348b3abd16…`) and `rules.json`; questions P1–P5.
  - Support register (fictional records from Vyshanth Buddani, published here as synthetic data with his permission): `docs/final/checks/acceptance/support_register/input.csv` (42 rows, sha256 `a2d86381b5dd0c76…`) and `rules.json`; questions S1–S5.
  - Test-split table `sales-test/salest_00`: `eval/datasets/sales-test/salest_00/messy.csv` with its `rules.json`; questions T1 and T2 are `salest_00_q0` and `salest_00_q1` from its `tasks.json`. It is the first table of the sales test split.
- **Expected answers:** P and S from Vyshanth's answer key (not published); T from the table's `reference_answer` values.
- **Scoring:** an answer is correct with the same groups and every value within 0.5% (0.01 minimum), `answers_match` as used by `eval/scoring.py`. Damaged cells are valid cells changed compared with the reference table: for T, `eval.scoring.score` on the run's `cleaned.csv` (planted-error cells excluded); for P and S the same count against Vyshanth's reference table, where a valid cell is an input cell that already equals the reference.
- Approvals: a decision policy derived from the stakeholder's business rules before any run and approved by Arsha Jindal (Nov 23, 2026); it was applied to every proposed fix, and each decision is listed below.
- The P and S answer keys were viewed during preparation, before the policy was written; the policy's conditions use only the proposed fix and the rules, never answer values.
- **Windows:** the runs used `python -X utf8` (UTF-8 mode); without it, writing `report.md` can fail on Windows' default cp1252 encoding.

## Results by file

| File | Questions | Correct | Damaged cells | Valid rows lost |
|---|---|---:|---:|---:|
| Procurement ledger | P1–P5 | 5 / 5 | 0 | 0 |
| Support register | S1–S5 | 5 / 5 | 0 | 0 |
| Test-split table `sales-test/salest_00` | T1–T2 | 2 / 2 | 0 | 0 |
| **Total** | | **12 / 12** | **0** | **0** |

## Questions

| # | Question | Expected | DataSage answer | Correct | Approvals asked / approved / rejected | Damaged cells |
|---|---|---|---|---|---|---:|
| P1 | What is the total procurement spend by department? | Facilities: 5,811.45; Finance: 6,290.9; Research: 10,043; Technology: 5,623.65 | Facilities: 5,811.45; Finance: 6,290.9; Research: 10,043; Technology: 5,623.65 | yes | 3 / 3 / 0 | 0 |
| P2 | What is the total procurement spend by supplier? | Cedar Office: 11,728.2; Mesa Equipment: 8,881.5; Valley Components: 7,159.3 | Cedar Office: 11,728.2; Mesa Equipment: 8,881.5; Valley Components: 7,159.3 | yes | 3 / 3 / 0 | 0 |
| P3 | What is the average unit cost in each item category? | Consumables: 80.0969; Equipment: 79.6094; Office Supplies: 77.9656 | Consumables: 80.0969; Equipment: 79.6094; Office Supplies: 77.9656 | yes | 3 / 3 / 0 | 0 |
| P4 | How many units were purchased in each item category? | Consumables: 128; Equipment: 123; Office Supplies: 122 | Consumables: 128; Equipment: 123; Office Supplies: 122 | yes | 3 / 3 / 0 | 0 |
| P5 | What is the total procurement spend per month? | 2026-09: 7,662.4; 2026-10: 9,122.3; 2026-11: 10,984.3 | 2026-09: 7,662.4; 2026-10: 9,122.3; 2026-11: 10,984.3 | yes | 3 / 3 / 0 | 0 |
| S1 | How many resolved tickets belong to each team? | Accounts: 13; Applications: 14; Operations: 13 | Accounts: 13; Applications: 14; Operations: 13 | yes | 3 / 2 / 1 | 0 |
| S2 | What is the average resolution time in minutes for each priority? | High: 1,275.8571; Low: 1,202.5385; Normal: 1,215.5385 | High: 1,275.8571; Low: 1,202.5385; Normal: 1,215.5385 | yes | 3 / 2 / 1 | 0 |
| S3 | How many resolved tickets arrived through each channel? | Email: 14; Phone: 13; Portal: 12 | Email: 14; Phone: 13; Portal: 12 | yes | 3 / 2 / 1 | 0 |
| S4 | For High-priority tickets, what is the average resolution time in minutes by team? | Accounts: 1,634.6; Applications: 1,254; Operations: 854.75 | Accounts: 1,634.6; Applications: 1,254; Operations: 854.75 | yes | 3 / 2 / 1 | 0 |
| S5 | How many resolved tickets were opened in each month? | 2026-10: 19; 2026-11: 20 | 2026-10: 19; 2026-11: 20 | yes | 4 / 2 / 2 | 0 |
| T1 | What is the average unit price in each category? | Accessories: 37.1429; Electronics: 369; Furniture: 169.1667; Office Supplies: 13.6364 | Accessories: 37.1429; Electronics: 369; Furniture: 169.1667; Office Supplies: 13.6364 | yes | 1 / 1 / 0 | 0 |
| T2 | What is the total revenue per month? | 2026-01: 5,335; 2026-02: 6,462; 2026-03: 6,058; 2026-04: 1,694; 2026-05: 4,619; 2026-06: 879 | 2026-01: 5,335; 2026-02: 6,462; 2026-03: 6,058; 2026-04: 1,694; 2026-05: 4,619; 2026-06: 879 | yes | 1 / 1 / 0 | 0 |

## Approval decisions

33 risky fixes were proposed across the 12 runs: 27 approved and 6 rejected (6 of them as not covered by the policy). Low-risk fixes (trimming spaces, case-only label merges, clear dates, number casts that lose no value) are applied by DataSage without asking and appear as `auto` in each report.

**Policy** (one row per fix that can need approval; anything not covered is rejected):

| Fix | Approved only if | Source |
|---|---|---|
| `normalize_labels` | every pair maps to an allowed label and is a case/space variant, a misspelling the business rules name (P/S), or for the test table the nearest allowed label within 2 edits and strictly closer than any other | business rules; `rules.json` allowed lists |
| `drop_duplicates` | every removed row is an exact copy of a kept row | business rules; unique order id |
| `parse_dates` with a day/month order | never: no rule gives one | business rules; `rules.json` format |
| `cast_numeric` / `set_missing` | no row removed and every cell turned missing is unreadable for its column (not a number after removing `$` and commas; not a date; not an allowed label and more than 2 edits from all of them); readable values are never blanked | stakeholder decision of Oct 28 (Milestone 2 report, Table 1, row 7); business rules |
| `exclude_rows` / `exclude_where` | every removed row has a number outside a rules range (negative quantities count as in range when `allow_negative_quantities` is set) | business rules; `rules.json` min/max |
| `recompute_column` | it is the rules' formula, each row breaks it, and its inputs are in range | business rules; `rules.json` formula |
| `fill_missing` | never: the rules say not to guess | business rules |

**Decision log** (every decision, in order, as the approver logged it). Rows are DataSage's row ids (0-based positions in the input file). `business_rules.md:n` is line n of the stakeholder's business rules, quoted below; `rules.json` is the test table's rules file.

| Case | Fix | Column | Rows / cells | Decision | Rule | Why |
|---|---|---|---|---|---|---|
| P1 | `drop_duplicates` |  | rows [48, 49] | approved | business_rules.md:17 | 2 removed row(s), each an exact copy of an earlier kept row |
| P1 | `normalize_labels` | Department | 2 cells | approved | business_rules.md:9-11,15; business_rules.md:15 | every pair maps to an allowed Department label |
| P1 | `recompute_column` | LineTotal | rows [11, 30], 2 cells | approved | business_rules.md:13 | 2 row(s) break LineTotal = Quantity * UnitCost and have valid inputs |
| P2 | `drop_duplicates` |  | rows [48, 49] | approved | business_rules.md:17 | 2 removed row(s), each an exact copy of an earlier kept row |
| P2 | `normalize_labels` | Department | 2 cells | approved | business_rules.md:9-11,15; business_rules.md:15 | every pair maps to an allowed Department label |
| P2 | `recompute_column` | LineTotal | rows [11, 30], 2 cells | approved | business_rules.md:13 | 2 row(s) break LineTotal = Quantity * UnitCost and have valid inputs |
| P3 | `normalize_labels` | Department | 2 cells | approved | business_rules.md:9-11,15; business_rules.md:15 | every pair maps to an allowed Department label |
| P3 | `recompute_column` | LineTotal | rows [11, 30], 2 cells | approved | business_rules.md:13 | 2 row(s) break LineTotal = Quantity * UnitCost and have valid inputs |
| P3 | `drop_duplicates` |  | rows [48, 49] | approved | business_rules.md:17 | 2 removed row(s), each an exact copy of an earlier kept row |
| P4 | `drop_duplicates` |  | rows [48, 49] | approved | business_rules.md:17 | 2 removed row(s), each an exact copy of an earlier kept row |
| P4 | `normalize_labels` | Department | 2 cells | approved | business_rules.md:9-11,15; business_rules.md:15 | every pair maps to an allowed Department label |
| P4 | `recompute_column` | LineTotal | rows [11, 30], 2 cells | approved | business_rules.md:13 | 2 row(s) break LineTotal = Quantity * UnitCost and have valid inputs |
| P5 | `drop_duplicates` |  | rows [48, 49] | approved | business_rules.md:17 | 2 removed row(s), each an exact copy of an earlier kept row |
| P5 | `normalize_labels` | Department | 2 cells | approved | business_rules.md:9-11,15; business_rules.md:15 | every pair maps to an allowed Department label |
| P5 | `recompute_column` | LineTotal | rows [11, 30], 2 cells | approved | business_rules.md:13 | 2 row(s) break LineTotal = Quantity * UnitCost and have valid inputs |
| S1 | `drop_duplicates` |  | rows [40, 41] | approved | business_rules.md:28 | 2 removed row(s), each an exact copy of an earlier kept row |
| S1 | `normalize_labels` | Team | 2 cells | approved | business_rules.md:22-24,27; business_rules.md:27 | every pair maps to an allowed Team label |
| S1 | `set_missing` | Channel | rows [9] | rejected | not covered | no cell would turn missing |
| S2 | `drop_duplicates` |  | rows [40, 41] | approved | business_rules.md:28 | 2 removed row(s), each an exact copy of an earlier kept row |
| S2 | `normalize_labels` | Team | 2 cells | approved | business_rules.md:22-24,27; business_rules.md:27 | every pair maps to an allowed Team label |
| S2 | `set_missing` | Channel | rows [9] | rejected | not covered | no cell would turn missing |
| S3 | `normalize_labels` | Team | 2 cells | approved | business_rules.md:22-24,27; business_rules.md:27 | every pair maps to an allowed Team label |
| S3 | `drop_duplicates` |  | rows [40, 41] | approved | business_rules.md:28 | 2 removed row(s), each an exact copy of an earlier kept row |
| S3 | `set_missing` | Channel | rows [9] | rejected | not covered | no cell would turn missing |
| S4 | `drop_duplicates` |  | rows [40, 41] | approved | business_rules.md:28 | 2 removed row(s), each an exact copy of an earlier kept row |
| S4 | `normalize_labels` | Team | 2 cells | approved | business_rules.md:22-24,27; business_rules.md:27 | every pair maps to an allowed Team label |
| S4 | `set_missing` | Channel | rows [9] | rejected | not covered | no cell would turn missing |
| S5 | `drop_duplicates` |  | rows [40, 41] | approved | business_rules.md:28 | 2 removed row(s), each an exact copy of an earlier kept row |
| S5 | `normalize_labels` | Team | 2 cells | approved | business_rules.md:22-24,27; business_rules.md:27 | every pair maps to an allowed Team label |
| S5 | `set_missing` | Channel | rows [9] | rejected | not covered | no cell would turn missing |
| S5 | `exclude_where` | ResolutionMinutes |  | rejected | not covered | no rows to remove |
| T1 | `normalize_labels` | Region | 2 cells | approved | rules.json allowed; rules.json allowed + policy 2c (nearest label, <= 2 edits) | every pair maps to an allowed Region label |
| T2 | `normalize_labels` | Region | 2 cells | approved | rules.json allowed; rules.json allowed + policy 2c (nearest label, <= 2 edits) | every pair maps to an allowed Region label |

**Business rules cited** (the stakeholder's wording, by line):

- 9: Departments: Facilities, Finance, Research, Technology.
- 10: Suppliers: Cedar Office, Mesa Equipment, Valley Components.
- 11: Item categories: Consumables, Equipment, Office Supplies.
- 13: `LineTotal = Quantity * UnitCost` for each line. Amounts are USD.
- 15: Leading/trailing spaces and case variants refer to the same canonical label. `Finanace` refers to `Finance`.
- 17: Exact duplicate rows are repeated copies of the same order line; keep one copy.
- 22: Teams: Accounts, Applications, Operations.
- 23: Priorities: High, Normal, Low.
- 24: Channels: Email, Phone, Portal.
- 27: Leading/trailing spaces and case variants refer to the same canonical label. `Operatons` refers to `Operations`.
- 28: Exact duplicate rows are repeated copies of the same ticket; keep one copy.

Every rejection was a fix that would have changed nothing: the agent asked to blank a Channel cell that was already empty, or to exclude rows when none were outside the range. The data was the same either way.

## Commands

Every command from the run log, in order, with its exit code. They were run from the repository root by `run_cases.py`. `policy_approver.py` runs DataSage exactly as `python -m datasage` does (`run_agent`, then `write_outputs`), with the policy as the approver through DataSage's `Approver.decide` interface; no DataSage code was changed. Both scripts are in the approver's local workspace (`.arsha-local/`), not in this repository. The packet paths under `.arsha-local/` hold the same input files published above (same sha256). H1–H4 are A1 (ratings) runs, not part of this test.

```text
2026-11-23T14:11:38  P1  attempt 1  .venv\Scripts\python.exe -X utf8 .arsha-local\vyshanth\policy_approver.py --case P1 --profile procurement --input .arsha-local\vyshanth\packet_2026-11-23\stakeholder_agent_handoff\agent_inputs\procurement_ledger\input.csv --rules .arsha-local\vyshanth\packet_2026-11-23\stakeholder_agent_handoff\agent_inputs\procurement_ledger\rules.json --request "What is the total procurement spend by department?" --out .arsha-local\runs\P1
2026-11-23T14:12:02  P1  attempt 1  exit 0
2026-11-23T14:12:08  P2  attempt 1  .venv\Scripts\python.exe -X utf8 .arsha-local\vyshanth\policy_approver.py --case P2 --profile procurement --input .arsha-local\vyshanth\packet_2026-11-23\stakeholder_agent_handoff\agent_inputs\procurement_ledger\input.csv --rules .arsha-local\vyshanth\packet_2026-11-23\stakeholder_agent_handoff\agent_inputs\procurement_ledger\rules.json --request "What is the total procurement spend by supplier?" --out .arsha-local\runs\P2
2026-11-23T14:12:28  P2  attempt 1  exit 0
2026-11-23T14:12:28  P3  attempt 1  .venv\Scripts\python.exe -X utf8 .arsha-local\vyshanth\policy_approver.py --case P3 --profile procurement --input .arsha-local\vyshanth\packet_2026-11-23\stakeholder_agent_handoff\agent_inputs\procurement_ledger\input.csv --rules .arsha-local\vyshanth\packet_2026-11-23\stakeholder_agent_handoff\agent_inputs\procurement_ledger\rules.json --request "What is the average unit cost in each item category?" --out .arsha-local\runs\P3
2026-11-23T14:12:48  P3  attempt 1  exit 0
2026-11-23T14:12:48  P4  attempt 1  .venv\Scripts\python.exe -X utf8 .arsha-local\vyshanth\policy_approver.py --case P4 --profile procurement --input .arsha-local\vyshanth\packet_2026-11-23\stakeholder_agent_handoff\agent_inputs\procurement_ledger\input.csv --rules .arsha-local\vyshanth\packet_2026-11-23\stakeholder_agent_handoff\agent_inputs\procurement_ledger\rules.json --request "How many units were purchased in each item category?" --out .arsha-local\runs\P4
2026-11-23T14:13:13  P4  attempt 1  exit 0
2026-11-23T14:13:13  P5  attempt 1  .venv\Scripts\python.exe -X utf8 .arsha-local\vyshanth\policy_approver.py --case P5 --profile procurement --input .arsha-local\vyshanth\packet_2026-11-23\stakeholder_agent_handoff\agent_inputs\procurement_ledger\input.csv --rules .arsha-local\vyshanth\packet_2026-11-23\stakeholder_agent_handoff\agent_inputs\procurement_ledger\rules.json --request "What is the total procurement spend per month?" --out .arsha-local\runs\P5
2026-11-23T14:13:39  P5  attempt 1  exit 0
2026-11-23T14:13:39  S1  attempt 1  .venv\Scripts\python.exe -X utf8 .arsha-local\vyshanth\policy_approver.py --case S1 --profile support --input .arsha-local\vyshanth\packet_2026-11-23\stakeholder_agent_handoff\agent_inputs\support_register\input.csv --rules .arsha-local\vyshanth\packet_2026-11-23\stakeholder_agent_handoff\agent_inputs\support_register\rules.json --request "How many resolved tickets belong to each team?" --out .arsha-local\runs\S1
2026-11-23T14:14:00  S1  attempt 1  exit 0
2026-11-23T14:14:00  S2  attempt 1  .venv\Scripts\python.exe -X utf8 .arsha-local\vyshanth\policy_approver.py --case S2 --profile support --input .arsha-local\vyshanth\packet_2026-11-23\stakeholder_agent_handoff\agent_inputs\support_register\input.csv --rules .arsha-local\vyshanth\packet_2026-11-23\stakeholder_agent_handoff\agent_inputs\support_register\rules.json --request "What is the average resolution time in minutes for each priority?" --out .arsha-local\runs\S2
2026-11-23T14:14:26  S2  attempt 1  exit 0
2026-11-23T14:14:26  S3  attempt 1  .venv\Scripts\python.exe -X utf8 .arsha-local\vyshanth\policy_approver.py --case S3 --profile support --input .arsha-local\vyshanth\packet_2026-11-23\stakeholder_agent_handoff\agent_inputs\support_register\input.csv --rules .arsha-local\vyshanth\packet_2026-11-23\stakeholder_agent_handoff\agent_inputs\support_register\rules.json --request "How many resolved tickets arrived through each channel?" --out .arsha-local\runs\S3
2026-11-23T14:14:46  S3  attempt 1  exit 0
2026-11-23T14:14:46  S4  attempt 1  .venv\Scripts\python.exe -X utf8 .arsha-local\vyshanth\policy_approver.py --case S4 --profile support --input .arsha-local\vyshanth\packet_2026-11-23\stakeholder_agent_handoff\agent_inputs\support_register\input.csv --rules .arsha-local\vyshanth\packet_2026-11-23\stakeholder_agent_handoff\agent_inputs\support_register\rules.json --request "For High-priority tickets, what is the average resolution time in minutes by team?" --out .arsha-local\runs\S4
2026-11-23T14:15:07  S4  attempt 1  exit 0
2026-11-23T14:15:07  S5  attempt 1  .venv\Scripts\python.exe -X utf8 .arsha-local\vyshanth\policy_approver.py --case S5 --profile support --input .arsha-local\vyshanth\packet_2026-11-23\stakeholder_agent_handoff\agent_inputs\support_register\input.csv --rules .arsha-local\vyshanth\packet_2026-11-23\stakeholder_agent_handoff\agent_inputs\support_register\rules.json --request "How many resolved tickets were opened in each month?" --out .arsha-local\runs\S5
2026-11-23T14:15:38  S5  attempt 1  exit 0
2026-11-23T14:15:38  T1  attempt 1  .venv\Scripts\python.exe -X utf8 .arsha-local\vyshanth\policy_approver.py --case T1 --profile sales_table --input eval\datasets\sales-test\salest_00\messy.csv --rules eval\datasets\sales-test\salest_00\rules.json --request "What is the average unit price in each category?" --out .arsha-local\runs\T1
2026-11-23T14:15:56  T1  attempt 1  exit 0
2026-11-23T14:15:56  T2  attempt 1  .venv\Scripts\python.exe -X utf8 .arsha-local\vyshanth\policy_approver.py --case T2 --profile sales_table --input eval\datasets\sales-test\salest_00\messy.csv --rules eval\datasets\sales-test\salest_00\rules.json --request "What is the total revenue per month?" --out .arsha-local\runs\T2
2026-11-23T14:16:11  T2  attempt 1  exit 0
2026-11-23T14:16:11  H1  attempt 1  .venv\Scripts\python.exe -X utf8 .arsha-local\vyshanth\policy_approver.py --case H1 --profile sales_table --input eval\datasets\sales-heldout\salesh_00\messy.csv --rules eval\datasets\sales-heldout\salesh_00\rules.json --request "What is the average unit price in each category?" --out .arsha-local\runs\H1
2026-11-23T14:16:29  H1  attempt 1  exit 0
2026-11-23T14:16:29  H2  attempt 1  .venv\Scripts\python.exe -X utf8 .arsha-local\vyshanth\policy_approver.py --case H2 --profile sales_table --input eval\datasets\sales-heldout\salesh_01\messy.csv --rules eval\datasets\sales-heldout\salesh_01\rules.json --request "How many units were sold in each region?" --out .arsha-local\runs\H2
2026-11-23T14:16:48  H2  attempt 1  exit 0
2026-11-23T14:16:48  H3  attempt 1  .venv\Scripts\python.exe -X utf8 .arsha-local\vyshanth\policy_approver.py --case H3 --profile penguins_table --input eval\datasets\penguins-heldout\penguinsh_00\messy.csv --rules eval\datasets\penguins-heldout\penguinsh_00\rules.json --request "What is the average bill length by island for Adelie penguins?" --out .arsha-local\runs\H3
2026-11-23T14:17:07  H3  attempt 1  exit 0
2026-11-23T14:17:07  H4  attempt 1  .venv\Scripts\python.exe -X utf8 .arsha-local\vyshanth\policy_approver.py --case H4 --profile penguins_table --input eval\datasets\penguins-heldout\penguinsh_01\messy.csv --rules eval\datasets\penguins-heldout\penguinsh_01\rules.json --request "How many penguins were measured on each island?" --out .arsha-local\runs\H4
2026-11-23T14:17:24  H4  attempt 1  exit 0
```
