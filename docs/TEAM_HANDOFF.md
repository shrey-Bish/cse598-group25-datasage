# Team handoff: final stretch

For: Arsha, Ritik, Maulik and Vatsal. Last updated November 22, 2026.

Milestone 2 is submitted, items 1 and 2 of Section 6 are merged (PR #7), and the browser app for the demo
(item 7's page) is done (PRs #10 to #19). All four research studies have landed (PRs #21 to #26). The rest of the work is split below. Individual grades draw on commit
and PR authorship, so **each task should end in its own merged PR** under your own GitHub account.

**Open tasks on November 22** (done tasks are removed from this doc; they are in git history and `docs/final/`):

| Task | Status |
|---|---|
| A3 poster check (Arsha) | Open: check the redesigned poster and sign off to Shrey by Nov 22; Shrey submits Nov 23, 2 PM |
| A1 ratings, A2 acceptance test (Arsha) | Not on `main` yet (`docs/final/ratings.md`, `docs/final/acceptance_test.md`) |
| R1 recipe replay, R2 Nov 20 review notes (Ritik) | Not on `main` yet (`tests/test_recipes.py` replay test, `docs/meetings/2026-11-20-review.md`) |
| M3 regression run (Maulik) | Ready to start: M1 and M2 are merged (PRs #38, #39). Needs the ASU API key in `.env` (see Setup) |

**For the final report (found by V2, `docs/final/real_files.md`):**

- **One inspection, several rows.** On the NYC file one inspection is one row per violation, and the agent
  counted rows, not inspections (mean scores too high). This is a known limitation for the final report,
  not a task: DataSage has no "count distinct" step.

**New since the November 16 version of this doc (please skim before starting):**

- **Browser app** (`python -m app.web.server`, then http://127.0.0.1:8501): pick *Ask me* or *Auto* on the
  start screen, drop one file or several with the same columns (CSV or Excel, any common separator or
  encoding), and watch the table get cleaned. Risky fixes wait on a card under the affected row with a
  Details view of the exact rows. Tabs: Table, Answer, Data health. Each output file has View and Download.
  Samples: sales (8 and 1,208 rows), 3 monthly files, HR, inventory.
- **Hosted app:** https://cse598-group25-datasage.vercel.app runs the same app on Vercel (each run over one
  WebSocket; 4-minute limit per run). Merging to `main` redeploys it. See README, "The hosted version".
- **Analysis pages:** `/results` (evaluation dashboard over all splits and systems) and a column profile
  for each run.
- **Agent changes:** `exclude_where` drops every row outside a range rule, however many (checks list only
  10 row ids); extra tool arguments no longer fail a call; the coverage check now also requires the
  metric's formula check. A no-regression re-run on held-out and test after these changes gave 74/80,
  the same as recorded.
- **Testing:** 112 unit tests run on GitHub for every PR (CI). `python scripts/smoke_e2e.py` is an
  end-to-end check with the real model (123 checks, a few minutes). There is also a Dockerfile.
- **Research studies, all merged** (write-ups in `docs/final/findings_*.md`, charts on the app's `/results` page):
  - *Scale and ablations* (`findings_scale_and_ablations.md`): 95.5% of 200 unseen questions (95% range 92.0 to
    98.5; 4 runs between 94.0% and 96.0%), against 49.0% for B1 and 46.5% for B2. Turning parts off: no approvals
    12.0%, short memory 86.0%, no coverage check 91.5%; the validator and the merge rule showed no clear effect.
  - *Hard benchmark* (`findings_hard.md`): tables of 343 to 1,935 rows. DataSage 30B 90.0% (seed 404: 85.0%),
    235B 97.5%, B1 10.0%, B2 55.0% with 637 damaged cells. DataSage damaged none and fixed all 1,750 errors
    the questions depended on.
  - *Auto mode* (`findings_auto_mode.md`): 113/120 right against 114/120 with a careful approver. Auto now
    pauses and asks before dropping rows that are blank only in the risky column.
  - *Model comparison* (`findings_models.md`): 41 models fully run as the planner. The 30B default ranks 4th
    (93.8%) and is among the fastest; with DataSage around it a model answers a median 20 points more than
    in one call. No model damaged clean data; the weakest fail on tool-call format.
- **Two things for the Nov 20 review** (see R2): 36 of the 39 misses over 4 runs of the 200 questions are rows breaking a
  rule in a column the question does not use (60.9% right on those questions, 99.6% on the rest), which
  is the question-columns-only scope Vyshanth chose. On the hard split, every Qwen miss came from
  `analyze` grouping by the column it also filters on. That is now fixed in code (`datasage/analyze.py`):
  the 30B model gets 80 of 80 on both hard seeds, up from 70 (`findings_hard.md`, section 10).

## Dates

| Date | What |
|---|---|
| Nov 16 to 20 | Vyshanth rates 10 DataSage reports (ratings week) |
| **Nov 20, 2:00 PM MST, Zoom** | Review with Vyshanth |
| **Nov 23, 2:00 PM (hard)** | Poster PDF due on Canvas (24 × 36 in portrait, `Group25_Poster.pdf`). No printing if late |
| Nov 27 | All code PRs open, so there is time to merge and re-run before the final report |
| **Dec 2, class time** | Poster session in person. Everyone attends |
| TBD (check Canvas) | Final report |

## Where things stand

| What | Where |
|---|---|
| The agent (30B model is now the default) | `datasage/` (`agent.py` loop, `tools.py` dispatcher and coverage check, `checks.py`, `fixes.py`) |
| Baselines B0, B1, B2 | `baselines/systems.py` |
| Benchmark, scoring, runner | `eval/generate.py`, `eval/scoring.py`, `eval/oracle.py`, `eval/run_eval.py` |
| All results | `eval/results/summary.md`; final system is `datasage-m3` |
| Report view (Arsha) and recipe format (Ritik) | `app/report_view.py`, `app/preview_report.py`, `datasage/recipes.py` |
| Item 7 design note | `docs/design/item7_recipes_ui.md` |
| Poster (print-ready PDF and source) | `docs/final/poster/`: `poster.html` is the source (redesigned Nov 18 from a Claude Design export), `Group25_Poster.pdf` the export; the README lists the source of every number. The earlier version is in `previous/`. |
| Demo run with the 30B default | `docs/final/demo/` (13 s, same answer as the Milestone 2 demo) |
| Hosted app (Vercel) | https://cse598-group25-datasage.vercel.app, from `app/web/hosted.py`; redeploys on every merge to `main` |
| Browser app (item 7 page) | `app/web/`; run `python -m app.web.server` and open http://127.0.0.1:8501 (README, "Run DataSage in the browser") |
| Evaluation dashboard, column profile, file viewer | `/results`, `/profile?run=<id>`, `/view?run=<id>` in the app (`app/web/analysis.py`, `app/web/static/`) |
| Demo tables with known answers | `examples/large_sales.csv`, `examples/demo/` (HR, inventory, 3 monthly files); `python examples/make_demo_files.py` prints the right answers |
| End-to-end check with the real model | `python scripts/smoke_e2e.py` |
| Research findings | `docs/final/findings_hard.md`, `findings_auto_mode.md`, `findings_scale_and_ablations.md`, `findings_models.md` |

Final system (`datasage-m3`, Qwen3-30B), share of questions answered correctly on the original held-out and
test splits (the 200-question and hard numbers are in the bullets above and on the poster):

| System | Held-out (40) | Test (40) | Damaged cells | Seconds per question |
|---|---|---|---|---|
| B1 fixed script | 35.0% | 45.0% | 0 | < 1 |
| B2 single model call | 60.0% | 47.5% | 35 | about 32 |
| DataSage 30B (final) | 92.5% | 92.5% | 0 | about 17 |

All 6 misses here, and 36 of the 39 over 4 runs of the 200 questions, are rows that break a rule in a column the question
doesn't use. Vyshanth chose to check only the question's columns, so we raise this at the Nov 20 review
rather than change it.

## Your tasks

Every task ends in a PR into `main`. Put a short note of what you did in `docs/team/<you>/WORKLOG.md`.

### Arsha

| # | Task | Done when | Due |
|---|---|---|---|
| A1 | **Ratings packet (item 6).** Run DataSage on 10 questions (the browser app in *Ask me* mode is easiest; each run's report has a View and Download button): Vyshanth's two files plus questions from the held-out tables. Send him the 10 `report.md` files and a short form (correct? clear? would you trust it? each 1 to 5, plus a comment). Collect his answers. | His ratings are summarised in `docs/final/ratings.md` (scores and quotes, no copy of his files). | Send Nov 17, collect Nov 20 |
| A2 | **Acceptance test (item 6).** 3 files (Vyshanth's two plus one test-split table), each with questions and expected answers. Pass = at least 90% correct and no valid cell changed. | `docs/final/acceptance_test.md` with the command, each question, expected and actual answer, pass or fail. | Nov 25 |
| A3 | **Poster check.** The poster was redesigned on Nov 18 (`docs/final/poster/Group25_Poster.pdf`; the earlier version is in `previous/`). Check every number on it against the sources listed in `docs/final/poster/README.md`, including the example table's answers and the six references. Collect team edits, make them in `poster.html`, re-export (steps in `docs/final/poster/README.md`) and check it is still one 24 × 36 in page. Then message Shrey "poster verified". **Shrey submits it on Canvas.** | Your sign-off to Shrey, and a PR with any corrections. | Sign off by Nov 22 |

### Ritik

| # | Task | Done when | Due |
|---|---|---|---|
| R1 | **Recipe replay (item 7).** Build a recipe from a run's approved fixes and replay it on a new file without the model, as planned in the design note. | Tests in `tests/test_recipes.py` show a recipe from one table replayed on another table with the same columns. | Nov 25 |
| R2 | **Nov 20 review.** Send Vyshanth an agenda by Nov 19: results, the out-of-question-column misses (ask whether to check all columns with a rule), the hard-split grouping fix (merged; 80/80 on hard), ratings, demo plan. Take notes. | `docs/meetings/2026-11-20-review.md`, same format as the Oct 28 notes. | Nov 20 |

### Maulik

| # | Task | Done when | Due |
|---|---|---|---|
| M3 | **No-regression run.** M1 and M2 are merged (PRs #38, #39). Re-run `datasage-m3` on held-out and test into a new results folder and compare with the current numbers (the baseline to beat: 74/80 on Nov 16, 0 damaged cells, 0 tool errors). Also run `python scripts/smoke_e2e.py`. Expect the hard split's planted `06/15/2026` dates (15, all in tables without a date question) to be converted now instead of blanked: that changes errors-handled counts there, not answers, and the benchmark arguably mislabels them. | A short write-up in `docs/final/regression_check.md`; any drop explained from the traces. | Nov 27 |

### Vatsal

No open tasks: V1 (PR #35) and V2 (PR #36) are done.

### Shrey

Owns the browser app (`app/web/`), the research studies (`docs/final/findings_*.md`), **submits the poster on Canvas** after Arsha's sign-off (by Nov 23, 2 PM), and the Demo Day plan (a 3-minute walk-through for the poster session plus a backup screen recording, in `docs/final/demo_script.md`, by Nov 30). Also reviews and merges every PR and assembles the final report. Each of you writes the final-report paragraph for your own tasks.

## Setup (about 5 minutes)

Python 3.11 or newer.

```bash
git clone https://github.com/shrey-Bish/cse598-group25-datasage.git
cd cse598-group25-datasage
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q tests                          # 112 tests, no API key needed
python -m eval.summarize                           # prints the results tables
python -m app.web.server                           # the browser app at http://127.0.0.1:8501 (needs the key)
```

Running DataSage needs an ASU RC model key and `RC_LLM_BASE_URL` in a `.env` file (copy `.env.example`; the
app now refuses to start without the base URL rather than fall back to OpenAI). Use your own key. A1, A2, M3,
V1 and V2 need one; check your quota before starting V1, which makes the most calls. When running many
questions, raise `--workers` rather than starting many processes at once: one laptop crashed under ~100
parallel Python processes.

## How to commit and open a PR

Do this once in the repo folder, with the email on **your** GitHub account (otherwise the commits are not
credited to you):

```bash
git config user.name "Your Name"
git config user.email "the-email-on-your-github-account"
```

For each task:

```bash
git checkout main
git pull
git checkout -b yourname/short-topic
# ...make your changes...
git add <the files you changed>
git commit -m "Say what you did, in a full sentence"
git push -u origin yourname/short-topic
```

Then open a pull request into `main` and ask Shrey to review it.

Rules:

- Never commit `.env` or any API key. The repo is public.
- Never commit Vyshanth's two sample files or their outputs. He allowed sending them to the ASU model
  service, not publishing them. Summaries and scores are fine.
- Do not edit files in `eval/results/` by hand. They come from `eval/run_eval.py`.
- Small, clear commits are better than one large one.

Questions about the code: ask Shrey, or open a GitHub issue so the answer stays with the repo.
