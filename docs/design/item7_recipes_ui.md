# Item 7 design: cleaning recipes and the Streamlit page

Ritik Agarwal, November 7, 2026. Reviewer: Arsha Jindal (comments on the PR only).

## Goal

**Status:** recipes are built (format, build, replay and a command line); the page is Shrey's browser app.

Item 7 (Milestone 2 report, Table 9) covers two deliverables Vyshanth agreed to on October 28:
cleaning recipes that replay a run's approved fixes on next month's file without the model, and a
Streamlit demo page. Done when both are shown at Demo Day with the replay script.

## File ownership

**Status:** as proposed in the Nov 6 sprint plan, except that Ritik's three `app/` files were not built (see
"The Streamlit page").

One owner per file; ask the owner for changes. In `datasage/`, item 7 only adds `recipes.py`.

- Ritik: `datasage/recipes.py`, `tests/test_recipes.py`, `tests/fixtures/recipes/`; after Nov 8,
  `app/browser_approver.py`, `app/run_controller.py`, `app/streamlit_app.py`.
- Arsha: `app/report_view.py`, `app/preview_report.py`, `tests/test_report_view.py`,
  `tests/fixtures/report_view/`.

## Contract: the report view

**Status:** implemented by Arsha in `app/report_view.py` (PR #2, merged).

```python
# app/report_view.py  (owner: Arsha; Ritik's Streamlit page will import render_report)
from dataclasses import dataclass
from pathlib import Path

@dataclass
class RunView:
    run_dir: Path
    report_md: str | None      # text of report.md, or None if the file is missing
    changes: list[dict]        # one dict per change-log row: version, fix, risk, approval, what_changed, reason
    files: dict[str, Path]     # whichever exist: cleaned.csv, replay.py, trace.jsonl, recipe.json

def load_run(run_dir: Path) -> RunView: ...
def parse_change_log(report_md: str) -> list[dict]: ...
def render_report(run_dir: Path) -> None: ...   # imports streamlit inside the function
```

- A run folder holds what `write_outputs` (`datasage/report.py`) writes, plus `recipe.json` if a
  recipe was saved. Missing files are left out of `files`; nothing raises.
- **Parse the Changes table by header name**, not by position. **The Reason column can contain `|`**
  (`report.py` doesn't escape it); it is the last column, so join any extra cells back into it.
  Rejected fixes (Version `-`) stay as rows.
- Only `render_report` imports Streamlit. Nothing writes to the run folder.

## Recipe file

**Status:** implemented in R5 (PR #5, merged).

A JSON file with `recipe_version` 1; `created_at` (UTC); `source`: `name`, `sha256` and `rows` of the
raw input, read with `load_table` (never `cleaned.csv`); `schema`: `columns`, `dtypes` (`number` or
`text`) and an order-independent `fingerprint`; `rules`: `name` and `sha256`, or `null`; and
`steps` in version order, each with `fix`, `args` (without `reason`), `risk`, `approved_by` (`auto` or
`approved`) and `portable`. Files are recorded by name, never by a local path.

## Building a recipe: `build_recipe(run_dir, input_path, rules_path=None, no_rules=False)`

**Status:** implemented in R7 on `ritik/recipes-replay`; `no_rules=True` confirms a run without a rules file
when its trace has no `lookup_rules` record.

- A fix is a step only if its trace record has `output.applied: true` and the Changes row
  `v{output.version}` has the same Fix, Risk and Approval. Rejected fixes never match.
- It stops with an error if trace records and change-log rows don't pair up or disagree, two applied
  records share a version, the input's file name differs from the report's Input line, or
  `rules_path` doesn't match the trace: it differs from what `lookup_rules` recorded, there is no such
  record, or it is missing while the run had rules ("no rules file was given" means none). The input's
  row count is not checked: the run folder doesn't record it.
- Portable: `trim_whitespace`, `normalize_labels`, `parse_dates`, `cast_numeric`. The rest use old
  row ids, remove rows, or (`fill_missing`) add values nobody approved.

## Replaying a recipe: `apply_recipe(recipe, input_path, out_dir)`

**Status:** implemented in R6 (schema check) and R8 (replay) on `ritik/recipes-replay`, with the command line
`python -m datasage.recipes save` / `apply` (R9).

1. Load the new file with `load_table`; it is never changed. A missing recipe column: refuse. An
   extra column or a changed type: a warning.
2. Portable steps, in order: dry-run on the new file (`normalize_labels` keeps only labels present),
   recompute the risk with `risk_of`, and apply only `low` steps, each checked by the validator. A
   `medium` or `high` step goes to "needs review", even if it was approved before. Other steps are
   only listed under "needs review", never replayed by old row numbers.
3. Re-run the checks on the recipe's columns; write `cleaned.csv` and `recipe_run.md`. All calls into
   `datasage/` go through `_ds_*` adapter functions in `recipes.py`.

## The Streamlit page

**Status:** replaced by Shrey's browser app (`app/web/`, PRs #10-#19); not built. The plan below is kept
for the record.

`run_controller.py` runs the agent in a background thread, `browser_approver.py` (an `Approver`
subclass) waits for the page's answer, and `streamlit_app.py` calls `render_report`. `agent.py`
doesn't change: `run_agent` takes the approver as an argument. Questions for Shrey:

1. Can `run_agent` run in a worker thread while `Approver.decide()` waits for the browser, and will
   `decide` and its `preview` keys stay as they are?
2. If the page closes while an approval waits, should `decide()` time out and return `False`?
