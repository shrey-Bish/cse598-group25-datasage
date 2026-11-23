# Recipe test fixtures

Synthetic files for `tests/test_recipes.py`; no real data.

- `sales_jan.csv`: the raw input of a scripted run. It has a trailing space in Region, a case variant and a
  misspelling in Category, an ISO timestamp, an ambiguous day-first date (`03/01/2026`) and an unreadable
  date, prices stored as text, a duplicate row, and a blank and a negative Quantity.
- `sales_rules.json`: the rules file for that run.
- `sales_run.json`: the run's tool calls and approval answers. The tests play them through the real agent
  loop with a scripted client in place of the model (`_make_run`), then write the run folder with
  `write_outputs`. The run applies 8 fixes and rejects one (`exclude_rows`).
- `sales_feb.csv`: a later file with the same columns, for replaying the recipe. It has similar problems,
  including an ambiguous date (`05/02/2026`).
