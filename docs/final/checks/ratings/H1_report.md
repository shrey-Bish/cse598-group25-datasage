# DataSage report

- Input: `eval\datasets\sales-heldout\salesh_00\messy.csv`
- Question: What is the average unit price in each category?
- Model: `qwen3-30b-a3b-instruct-2507`; stop reason: `finish`; tool calls: 13; approvals asked: 2; time: 12.53s

## Problems found

| Type | Column | Count | Rows (first 10) |
|---|---|---:|---|
| duplicates | * | 1 | [4] |
| label_variant | Category | 3 | [5, 25, 55] |
| invalid_date | Date | 2 | [14, 19] |

## Changes

| Version | Fix | Risk | Approval | What changed | Reason |
|---|---|---|---|---|---|
| v1 | drop_duplicates | medium | approved | removed 1 exact duplicate row(s) | Found one exact duplicate row (row 4) that is a copy of row 3; removing the duplicate to avoid double-counting. |
| v2 | normalize_labels | high | approved | Category: merged 2 label variant(s), 3 cells | Merge misspelled variants into correct labels: 'Accesories' → 'Accessories', 'Office Suplies' → 'Office Supplies'. |
| v3 | parse_dates | low | auto | Date: converted 0 date(s), 2 invalid date(s) set to missing; 0 ambiguous date(s) left unchanged | Automatically normalize valid ISO dates (YYYY-MM-DD) and blank invalid ones like '2026-02-30' and '2026-14-01'. |

### Date changes in v3

- Row 14, `Date`: "2026-02-30" → missing.
- Row 19, `Date`: "2026-14-01" → missing.

## Answer

mean of `Price` by ['Category'] (rows used: 67, version v3)

| Group | Value |
|---|---:|
| Accessories | 35.65 |
| Electronics | 259.23 |
| Furniture | 251.94 |
| Office Supplies | 9.23 |

## Summary

The data had three main issues: (1) one exact duplicate row (row 4) was removed; (2) two misspelled category labels ('Accesories' and 'Office Suplies') were normalized to 'Accessories' and 'Office Supplies'; (3) two invalid dates ('2026-02-30' and '2026-14-01') were set to missing. All other columns were valid. The average unit price by category is: Accessories: $35.65, Electronics: $259.23, Furniture: $251.94, Office Supplies: $9.23.
