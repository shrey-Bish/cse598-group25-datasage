# Ritik's worklog

## Purpose

A log of what I change in this repository, written for teammates: what changed, which files and
interfaces each change touches, and what to know before pulling it. Newest entry first.

## Log

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
