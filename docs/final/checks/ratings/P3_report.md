# DataSage report

- Input: `.arsha-local\vyshanth\packet_2026-11-23\stakeholder_agent_handoff\agent_inputs\procurement_ledger\input.csv`
- Question: What is the average unit cost in each item category?
- Model: `qwen3-30b-a3b-instruct-2507`; stop reason: `finish`; tool calls: 14; approvals asked: 3; time: 13.09s

## Problems found

| Type | Column | Count | Rows (first 10) |
|---|---|---:|---|
| label_variant | Department | 2 | [0, 5] |
| label_variant | Supplier | 1 | [7] |
| text_number | UnitCost | 2 | [2, 19] |
| cross_column | LineTotal | 2 | [11, 30] |
| duplicates | * | 2 | [48, 49] |

## Changes

| Version | Fix | Risk | Approval | What changed | Reason |
|---|---|---|---|---|---|
| v1 | normalize_labels | high | approved | Department: merged 2 label variant(s), 2 cells | merge case and space variants and correct misspelling into allowed labels |
| v2 | normalize_labels | low | auto | Supplier: merged 1 label variant(s), 1 cells | merge case and space variant into allowed label |
| v3 | cast_numeric | low | auto | UnitCost: converted to numbers (50 text values, 0 became missing) | convert text numbers with dollar signs to numeric values |
| v4 | recompute_column | high | approved | LineTotal: recomputed as Quantity * UnitCost on 2 row(s) | fix LineTotal values that do not match Quantity * UnitCost |
| v5 | drop_duplicates | medium | approved | removed 2 exact duplicate row(s) | remove exact duplicate rows, keeping the first occurrence |

## Answer

mean of `UnitCost` by ['ItemCategory'] (rows used: 48, version v5)

| Group | Value |
|---|---:|
| Consumables | 80.10 |
| Equipment | 79.61 |
| Office Supplies | 77.97 |

## Summary

The data had several issues affecting the question: (1) 'Department' had a space variant (' facilities ') and a misspelling ('Finanace'), both corrected via normalize_labels; (2) 'Supplier' had a space variant (' valley components '), corrected via normalize_labels; (3) 'UnitCost' was stored as text with dollar signs, converted to numeric using cast_numeric; (4) two rows had incorrect 'LineTotal' values that did not match Quantity * UnitCost, fixed via recompute_column; (5) two exact duplicate rows were removed. After these fixes, the average unit cost by item category is: Consumables: 80.10, Equipment: 79.61, Office Supplies: 77.97 (rounded to two decimals).
