# Arsha's worklog

## Purpose

A log of my changes for teammates: which files I added or changed, the functions others can call, and
what you should know before pulling. Newest entry last. The plan for item 7 (Streamlit page and cleaning
recipes) is split with Ritik: I own the report view (`app/report_view.py`, `app/preview_report.py`) and
he owns the recipes module and the main Streamlit page.

## Log

### 2026-11-07: Milestone 2 folder README and the run-folder loader

**Milestone 2 README** (branch `arsha/m2-report-edit`, draft PR #1)
- New `docs/milestone2/README.md`: what each file in `docs/milestone2/` is, which report figure or
  table it backs, how to rerun the demo, and the systems, datasets and `eval/summarize.py` code behind
  each table in Section 3.
- Two items are marked "TBD (Arsha)" because the repo doesn't record them: how Table 3's counts were
  computed, and the command for the 10-task ablation runs in Table 8.

**Report view, loader** (branch `arsha/report-view`)
- New `app/__init__.py` (empty) so `app` is a package. Ritik's scaffold PR adds the same empty file;
  two identical empty files merge without a conflict.
- New `app/report_view.py`:
  - `RunView(run_dir: Path, report_md: str | None, changes: list[dict], files: dict[str, Path])`
  - `load_run(run_dir: Path) -> RunView` reads `report.md` and lists whichever of `cleaned.csv`,
    `replay.py`, `trace.jsonl` and `recipe.json` exist. A missing `report.md` gives `report_md = None`,
    and a missing file is left out of `files`. It never raises, even for a folder that doesn't exist.
- New `tests/test_report_view.py` and the synthetic run folder `tests/fixtures/report_view/run_ok/`
  (made-up inventory data, not the stakeholder's files).

**Before pulling:** nothing in `datasage/`, `eval/` or any existing file changes. The tests need no API
key and no streamlit. Run them from the repo root with `python -m pytest -q tests`, as the README
says. Plain `pytest` doesn't put the repo root on the path, so it can't import `app` (or `datasage`, for
the existing tests).

### 2026-11-07: Change-log parser, Streamlit view and preview page

**Report view** (branch `arsha/report-view`)
- `app/report_view.py` now also has:
  - `parse_change_log(report_md: str) -> list[dict]` reads the table under the "Changes" heading of
    `report.md` into dicts with keys `version`, `fix`, `risk`, `approval`, `what_changed`, `reason`. It
    maps the headers `markdown_report()` writes in `datasage/report.py`. Rejected fixes are kept as
    written there (`version` "-", `approval` "rejected", "(not applied)" at the end of `what_changed`).
    No Changes section gives `[]`. A `|` inside a reason is kept, because report.py doesn't escape it.
    `load_run` fills `RunView.changes` with it.
  - `render_report(run_dir: Path) -> None` shows `report.md` with `st.markdown`, the change log with
    `st.dataframe` and one `st.download_button` per file in `RunView.files`. It is the only function
    that imports streamlit, and only inside the function. It doesn't call `st.set_page_config`; the
    page that calls it does. **Ritik:** this is the function your Streamlit page calls.
- New `app/preview_report.py`: a small page that opens any existing run folder, read only:

  ```bash
  pip install streamlit        # or: pip install -r requirements-ui.txt once Ritik's scaffold is merged
  streamlit run app/preview_report.py                         # the Milestone 2 demo run
  streamlit run app/preview_report.py -- --run outputs/run    # any other run folder
  ```

  It adds the repo root to `sys.path` at the top, because `streamlit run` only adds `app/`.
- Tests (`tests/test_report_view.py`, 12 tests) cover the loader, the parser on the fixture and on a report
  built by the real `markdown_report()`, a fake `streamlit` module that records the calls `render_report`
  makes, a check in a fresh interpreter that importing `app.report_view` doesn't import streamlit, and
  the preview page's arguments.

**Before pulling:** still no change to any existing file. The test suite doesn't need streamlit.

### 2026-11-23: Checks on the frozen results and demo files

**Freeze checks** (branch `arsha/freeze-checks`)
- New `tests/test_frozen_artifacts.py` with three tests. They read only committed files, write only to
  `tmp_path`, make no model calls and need no API key:
  - `test_results_tables_match_the_summarizer` runs `eval.summarize.main()` with its output sent to
    `tmp_path` and compares `summary.md`, `summary.json` and `summary.csv` with the committed ones in
    `eval/results/`.
  - `test_demo_replay_reproduces_cleaned_csv` copies `docs/final/demo/replay.py` and the demo's input
    (`baseline/examples/messy_sales.csv`, taken from the report's Input line) to `tmp_path`, runs the
    script with `sys.executable`, and compares the table with `docs/final/demo/cleaned.csv`.
  - `test_report_view_finds_every_change_in_the_final_demo` loads `docs/final/demo` with `load_run` and
    checks that the change log has the 4 fixes the run's `trace.jsonl` records (2 applied, 2 rejected),
    in the report's order and with the same reasons.
- All three pass on main `265a6c8f`: none of the checked files differs from what its code produces.
- CSVs are compared by content with line endings normalised, because pandas writes `\r\n` on Windows.

```bash
python -m pytest -q tests/test_frozen_artifacts.py
```

**Before pulling:** only a new test file and this entry; no code changes. On Windows the first test is slow
when the 9,557 result files it reads are not in the file cache (25 s or more); with a warm cache the
whole file takes about 8 s.

### 2026-11-23: Acceptance test (A2)

**Acceptance test** (branch `arsha/acceptance-test`)
- New `docs/final/acceptance_test.md`. DataSage (the 30B default) answered 12 questions on three files:
  - Vyshanth's fictional procurement ledger (P1–P5);
  - his fictional support register (S1–S5);
  - the test-split table `sales-test/salest_00` (T1–T2).
- Result: **PASS**, with 12 of 12 answers correct, 0 valid cells changed and 0 valid rows lost.
- New `docs/final/checks/acceptance/procurement_ledger/` and `.../support_register/`: the two input files
  and their rules, published as synthetic data with Vyshanth's permission. His answer keys and reference
  tables are not committed.
- Approvals followed a decision policy, written from his business rules and the table's `rules.json`
  before any run. I approved it. Every decision is listed in the doc.
- Follow-up (same day): the policy and the approver used for the runs are published as
  `docs/final/checks/acceptance/decision_policy.md` and `policy_approver.py`.
  - The approver plugs into DataSage's `Approver.decide` interface and runs DataSage as
    `python -m datasage` does. The doc's "Rerun" section has the exact commands.
  - `tests/test_acceptance_policy.py` (63 tests, no model or API key) checks every policy rule on
    synthetic tables, that decisions are logged, and that the approver finds the repo root.

**Before pulling:** no change to `datasage/`, `app/` or `eval/`. The only code is the approver script in
`docs/final/checks/acceptance/` and its offline test.
