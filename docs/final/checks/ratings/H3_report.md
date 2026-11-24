# DataSage report

- Input: `eval\datasets\penguins-heldout\penguinsh_00\messy.csv`
- Question: What is the average bill length by island for Adelie penguins?
- Model: `qwen3-30b-a3b-instruct-2507`; stop reason: `finish`; tool calls: 10; approvals asked: 2; time: 12.89s

## Problems found

| Type | Column | Count | Rows (first 10) |
|---|---|---:|---|
| label_variant | island | 2 | [12, 38] |
| text_number | body_mass_g | 1 | [44] |
| out_of_range | body_mass_g | 1 | [10] |

## Changes

| Version | Fix | Risk | Approval | What changed | Reason |
|---|---|---|---|---|---|
| v1 | normalize_labels | high | approved | island: merged 2 label variant(s), 2 cells | merge misspellings into allowed labels: 'Bisco' is a misspelling of 'Biscoe', 'Torgerson' is a misspelling of 'Torgersen' |
| v2 | cast_numeric | low | auto | body_mass_g: converted to numbers (53 text values, 0 became missing) | value '5,500' in row 44 is a number written with a comma; convert to numeric |
| v3 | exclude_rows | high | approved | excluded 1 row(s): [10] | body_mass_g value 4000000 is outside allowed range [2500, 6500] and likely a data entry error |

## Answer

mean of `bill_length_mm` by ['island'] (rows used: 23, version v3)

| Group | Value |
|---|---:|
| Biscoe | 38.58 |
| Dream | 39.49 |
| Torgersen | 38.34 |

## Summary

The data had two issues: (1) 'Bisco' and 'Torgerson' in the 'island' column were misspellings of 'Biscoe' and 'Torgersen', which were corrected using normalize_labels; (2) a body mass value of 4,000,000 grams in row 10 was outside the allowed range [2500, 6500] grams and was excluded as a likely data entry error. After these fixes, the average bill length for Adelie penguins by island is: Biscoe: 38.58 mm, Dream: 39.49 mm, Torgersen: 38.34 mm.
