# Ritik's worklog

## Purpose

A log of what I change in this repository, written for teammates: what changed, which files and
interfaces each change touches, and what to know before pulling it. Newest entry first.

## Log

### November 22, 2026: recipe build and replay (`ritik/recipes-replay`)

Task R1 in `docs/TEAM_HANDOFF.md` (item 7). What changed (`datasage/recipes.py` grows; no other file in
`datasage/` is edited):

- `check_schema(recipe, df)` (R6) compares a table's columns and kinds with the recipe. A missing column
  stops a replay; an extra column or a changed kind is a warning.
- `build_recipe(run_dir, input_path, rules_path=None, no_rules=False)` (R7) builds a recipe from a run
  folder. A fix becomes a step only when its trace record says it was applied and the Changes row with the
  same version has the same fix, risk and approval. It stops when the two don't pair up, when the input's
  name differs from the report's Input line, or when the rules file doesn't match what the run's
  `lookup_rules` returned. `parse_changes` reads the Changes table by header name and stops where the table
  ends, so the "Date changes in v{N}" lists below it are not read as rows.
- `apply_recipe(recipe, input_path, out_dir)` (R8) replays the column-level fixes (`trim_whitespace`,
  `normalize_labels`, `parse_dates`, `cast_numeric`) on a new file without the model. Each one is dry-run,
  its risk is recomputed with `risk_of` on the new file, and it is applied only if it is low risk and the
  validator accepts it. Everything else goes to "needs review". It then re-runs the checks for the recipe's
  columns, writes `cleaned.csv` and `recipe_run.md`, and never changes the input.
- `python -m datasage.recipes save ...` and `python -m datasage.recipes apply ...` (R9): the command line.
- `tests/test_recipes.py` and `tests/fixtures/recipes/`: synthetic fixtures; test runs go through the real
  agent loop with a scripted client in place of the model. The handoff's "done when" test builds a recipe
  from `docs/final/demo` and replays it on `examples/demo/monthly/orders_2026-09.csv`, reading both only.

Interfaces: `datasage/recipes.py` calls `checks`, `fixes`, `session`, `tools` and `validator` only through
its `_ds_*` adapter functions, and none of them changed. It reads the trace records and the Changes table
as `agent.py` and `report.py` write them today, including `parse_dates`' `date_order` and the date-change
lists from M1.

Before pulling: nothing new to install. Good to know:

- Steps keep `parse_dates`' `date_order` as the trace recorded it. Without it, `parse_dates` leaves
  ambiguous dates alone, so a replay can apply it and lists any ambiguous date as an issue left; with it,
  a file with an ambiguous date sends the step to review.
- A recipe names its rules file but does not contain it, so a replay does not re-run the checks that need
  rules (allowed labels, ranges, refunds).
- Item 7's page is Shrey's browser app (`app/web/`); my Streamlit page is dropped. Nothing in `app/web/`
  uses recipes yet.

### November 22, 2026: notes from the November 20 review (`ritik/nov20-review-notes`)

Task R2 in `docs/TEAM_HANDOFF.md`. What changed (one new file, plus this entry):

- `docs/meetings/2026-11-20-review.md`: my notes from the November 20 Zoom review with Vyshanth,
  following the October 28 notes: the agenda, what we presented, his feedback on each agenda item, the
  three decisions (keep checking only the question's columns, keep the recorded results, keep the
  current interface and default model) and the action items.

The notes add no new results. Each figure in "What we presented" names the file on `main` it comes
from (`docs/TEAM_HANDOFF.md`, `eval/results/summary.md`, `docs/final/findings_scale_and_ablations.md`,
`docs/final/findings_hard.md`).

Interfaces: none; documentation only.

Before pulling: nothing to do. I am sending the notes to Vyshanth to confirm; any corrections he sends
will come as a follow-up commit.

### November 7, 2026: item 7 scaffold (`ritik/item7-scaffold`)

What changed (all new files; no existing file is edited):

- `docs/design/item7_recipes_ui.md`: the item 7 design note. It covers file ownership, the
  report-view contract Arsha and I code against, the recipe file format, how a recipe is built from a
  run and replayed on a new file, and two questions for Shrey about browser approvals. Each section
  says whether that part is implemented or planned.
- `app/__init__.py`: empty. It makes `app/` a package, so Arsha's `app/report_view.py` and the later
  Streamlit page can be imported as `app.report_view` and so on.
- `requirements-ui.txt`: `-r requirements.txt` plus `streamlit==1.66.1`. `requirements.txt` is
  unchanged.

Interfaces: nothing in `datasage/` changed. The report-view contract (`RunView`, `load_run`,
`parse_change_log`, `render_report`) is defined in the design note; Arsha owns that code.

Before pulling:

- Streamlit is only needed for the page: `pip install -r requirements-ui.txt`. The tests run without it.
- If you created `app/__init__.py` on your own branch, keep it empty; two empty files merge without a
  conflict.
- Streamlit is pinned to 1.66.1 (October 21) rather than 1.67.0, which was two days old on
  November 7. Both install alongside pandas 3.0.5.
