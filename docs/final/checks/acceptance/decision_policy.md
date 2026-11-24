# Decision policy for the acceptance-test runs (approved by Arsha Jindal, Nov 23, 2026)

This policy decided every risky fix in the acceptance test (`docs/final/acceptance_test.md`) and in the A1 runs.
It was written before any run and implemented in `policy_approver.py` next to this file.

## Sources
- P and S cases: the stakeholder's business rules for the two fictional files ("BR:<line>"). The lines the
  policy cites are quoted at the end. The same allowed lists and minimums are in each file's `rules.json`
  in this folder.
- T and H cases: that table's `rules.json`.
  - Sales: Order_ID "unique order number"; Category/Region allowed; Quantity min 1; Price min 0;
    "Revenue = Quantity * Price".
  - Penguins: penguin_id "unique id"; species/island/sex allowed; sex "missing means unknown; do not
    guess"; numeric min/max.
- Added by change 2: the stakeholder's Oct 28 decision. Milestone 2 report, Table 1, row 7 (also
  `docs/meetings/2026-10-28-review.md:40`) reads: "Blank unreadable dates and convert clear date formats
  automatically; ask only on ambiguous dates." It is applied the same way to numbers and labels.

## Which decisions reach the approver
DataSage's code sets each fix's risk (`datasage/fixes.py`, `risk_of`: "Risk tier decided by code from the fix
type and its actual effect, never by the model"). Low-risk fixes are applied automatically
(`datasage/tools.py`: `if risk == "low": approval = "auto"`). Only medium- and high-risk fixes reach
`approver.decide(name, args, risk, preview)`. The preview is `{"summary", "rows_removed", "cells_changed",
"before", "after", ...}`. Applied automatically, never decided here:
- `trim_whitespace`: always low;
- `normalize_labels`: low when every pair differs only by case or spaces;
- `parse_dates`: low unless ambiguous dates are converted;
- `cast_numeric`: low unless values become missing.

## Definitions
- **Range break:** a number outside the rules' `min`/`max`. The test is DataSage's own (`datasage/rules.py`
  `outside_range` with `allows_negative_quantities`), so when a rules file sets `allow_negative_quantities`,
  negative quantities are in range.
- **Unreadable cell** (change 2). Cells already missing are never "unreadable". The column's kind comes
  from its rules: `format` means date, `allowed` means label, and min/max or a formula means number.
  - Number: not a number after removing `$` and commas (and surrounding spaces).
  - Date: no reading at all; `datasage.values.iso_date` with no order, `dmy` or `mdy` all fail.
    Ambiguous dates are readable.
  - Label: not an allowed label, not a case/space variant of one, and more than 2 edits
    (case-insensitive) from every allowed label. So a possible misspelling is never blanked.

## Policy: one row per fix tool in `datasage/fixes.py` FIXES

| # | Fix tool | Reaches approver when (`risk_of`) | APPROVE only if | Otherwise | Rule |
|---|---|---|---|---|---|
| 1 | `trim_whitespace` | never (always low) | n/a | not covered (if ever asked) | |
| 2 | `normalize_labels` | a pair is not a case/space variant (high) | every pair maps to a label in the column's `allowed` list **and** each pair is (a) a case/space variant, or (b) P/S: a misspelling the rules name (`Finanace`→`Finance`, `Operatons`→`Operations`), or (c) T/H: the target is the nearest allowed label, at most 2 edits away and **strictly closer than every other** allowed label | reject. P/S stay strict: only the named misspellings | (a) BR:15, BR:27; (b) BR:15, BR:27; (c) rules.json `allowed`, change 1 |
| 3 | `drop_duplicates` | always (medium) | every removed row is an exact copy of an earlier kept row | reject | P BR:17; S BR:28; T/H the unique Order_ID / penguin_id |
| 4 | `parse_dates` | ambiguous dates converted with a chosen day/month order (medium) | never | reject, **not covered**: no source gives a day/month order | BR:14 ("clear" dates only); BR:26; rules.json `format`; Oct 28 "ask only on ambiguous dates" |
| 5 | `cast_numeric` | some values would become missing (medium) | the column is a number column in the rules, no row is removed, and **every** cell it turns missing is an unreadable number | reject (not covered) | Oct 28 decision; BR:29 (blanking keeps the record and guesses nothing); `$`/commas are formatting: BR:16, BR:25 |
| 6 | `exclude_rows` | always (high) | **every** removed row has a range break | reject: rows removed only for missing or unknown values, labels, formula mismatches or permitted negative quantities are not covered | P BR:12; S BR:25; T/H rules.json min/max; `allow_negative_quantities` (change 3); S BR:29 "retain the record" |
| 7 | `exclude_where` | always (high) | same row-by-row test as 6, on the rows it would actually remove | reject | as 6 |
| 8 | `recompute_column` | always (high) | the column and expression are the rules' formula (P `LineTotal = Quantity * UnitCost`; T/H sales `Revenue = Quantity * Price`; spaces ignored), every listed row currently breaks it (DataSage's tolerance, 0.5% + 1e-6, `check_cross_column`), its inputs are numbers within range, and the result is within range | reject; S and penguins have no formula: not covered | P BR:13; T/H rules.json `formula` |
| 9 | `set_missing` | always (high) | no row is removed and **every** cell it turns missing is unreadable for its column (definition above); S `OpenedDate` = `not-recorded` is covered explicitly by BR:26. **Readable values are never blanked, including rule-breaking ones** | reject: not covered | Oct 28 decision; BR:29; S: BR:26, BR:24, BR:29-30 |
| 10 | `fill_missing` | always (high) | never | reject | S BR:29 "Do not guess"; penguins sex "do not guess"; P/sales: no fill value given, so not covered |
| — | any other tool | | never | reject, **not covered** | |

P/S check for change 2: the business rules don't say otherwise. BR:14-16 and BR:25 describe readable
formats; BR:26 says `not-recorded` should be missing; BR:29 says do not guess and retain the record. The
named misspellings (BR:15, BR:27) are within 1 edit, so they count as readable and are never blanked.

## Changes approved by Arsha, Nov 23
These were made to the first draft before any run.
1. **T/H misspellings (row 2c):** approve when the nearest allowed label (case-insensitive edit distance) is
   at most 2 edits away and strictly closer than every other allowed label. For example, "Wst" is 1 edit
   from West and 2 from East, so it merges into West. P/S stay strict: only the named misspellings.
2. **Unreadable values (rows 5 and 9):**
   - Approve `cast_numeric` or `set_missing` when every cell it turns missing is unreadable for its
     column and no row is removed. "Unreadable" is defined above.
   - Still reject `set_missing` on any readable value, including rule-breaking ones.
   - `fill_missing` stays rejected.
   - For P/S this applies only where the business rules don't say otherwise; they don't.
   - Sources: the Oct 28 decision (Milestone 2 report, Table 1, row 7) and BR:29.
3. **Ranges (rows 6-7):** if a rules file sets `allow_negative_quantities`, negative quantities are in range,
   so excluding rows only for being negative is rejected.
4. **acceptance_test.md, under Setup:** "The P and S answer keys were viewed during preparation, before the
   policy was written; the policy's conditions use only the proposed fix and the rules, never answer values."

## Logging
Every decision is one JSON line in `<out>/decisions.jsonl`, where `<out>` is the run's `--out` folder:
`case, tool, risk, column, rows, cells_changed, summary, decision, rule, why, args, agent_reason`.
"not covered" rejections carry `rule: "not covered"`. Auto-applied low-risk fixes appear in each report's
Changes table as `auto`.

## How it plugs in (no change to datasage/)
- `--approve tools --allow ...` is too coarse: `ToolPolicyApprover.decide` is `answer = tool in
  self.allowed`.
- `policy_approver.py` subclasses DataSage's interface
  (`class Approver: def decide(self, tool: str, args: dict, risk: str, preview: dict) -> bool`). It runs
  the agent as `datasage/__main__.py` does (`run_agent(source, request, approver, rules_path=...,
  model=DEFAULT_MODEL, max_tool_calls=30, verbose=True)` then `write_outputs(result, out)`).
- Model: `DEFAULT_MODEL = SMALL_MODEL = "qwen3-30b-a3b-instruct-2507"`.
- Profiles: `procurement` (P), `support` (S), `sales_table` (T1, T2, H1, H2), `penguins_table` (H3, H4).
- To rerun, see the "Rerun" section of `docs/final/acceptance_test.md`.

## Tests
`tests/test_acceptance_policy.py` checks the policy offline, with no model calls and no API key:
- 60 synthetic cases, every one giving the expected decision: 32 for the first draft and 28 for the
  four changes;
- each decision is logged with the fields above;
- the approver finds the repository root from this folder.

## Disclosure
The stakeholder's reference tables and answer keys were not opened before the runs. The P and S expected
answers had been viewed during preparation, before this policy was written. No condition above uses an
answer value.

## Business rules cited (the stakeholder's wording, by line)
Procurement ledger:
- 9: Departments: Facilities, Finance, Research, Technology.
- 10: Suppliers: Cedar Office, Mesa Equipment, Valley Components.
- 11: Item categories: Consumables, Equipment, Office Supplies.
- 12: Quantity must be at least 1. UnitCost and LineTotal must be nonnegative.
- 13: `LineTotal = Quantity * UnitCost` for each line. Amounts are USD.
- 14: Dates should be normalized to `YYYY-MM-DD`; clear slash-separated dates and ISO timestamps retain their written calendar date.
- 15: Leading/trailing spaces and case variants refer to the same canonical label. `Finanace` refers to `Finance`.
- 16: Currency symbols and thousands separators are formatting, not changes in value.
- 17: Exact duplicate rows are repeated copies of the same order line; keep one copy.

Support register:
- 22: Teams: Accounts, Applications, Operations.
- 23: Priorities: High, Normal, Low.
- 24: Channels: Email, Phone, Portal.
- 25: ResolutionMinutes is a nonnegative duration in minutes. Commas may be thousands separators.
- 26: Dates should be normalized to `YYYY-MM-DD`. `not-recorded` means the date is unknown and should be missing.
- 27: Leading/trailing spaces and case variants refer to the same canonical label. `Operatons` refers to `Operations`.
- 28: Exact duplicate rows are repeated copies of the same ticket; keep one copy.
- 29: Do not guess an unknown channel or date. Omit a missing grouping key only from the analysis that groups on that field; retain the record for other questions.
- 30: not quoted. It states the ticket totals that follow from line 29, which are answer values.
