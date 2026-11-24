# Team handoff: final stretch

For: Arsha, Ritik, Maulik and Vatsal. Last updated November 23, 2026.

Milestone 2 is submitted, items 1 and 2 of Section 6 are merged (PR #7), and the browser app for the demo
(item 7's page) is done (PRs #10 to #19). All four research studies have landed (PRs #21 to #26). The rest of the work is split below. Individual grades draw on commit
and PR authorship, so **each task should end in its own merged PR** under your own GitHub account.

**All teammate tasks are done (November 23).** What is left (done tasks are removed from this doc; they are in
git history and `docs/final/`):

| Task | Status |
|---|---|
| Demo Day plan (Shrey) | `docs/final/demo_script.md`, by Nov 30 |
| Final report (Shrey assembles) | Each of you writes the paragraph for your own tasks when Shrey asks |

**Done on November 23:** the poster is submitted on Canvas. Arsha's check (A3, PR #47) found two claims
that did not match the results; both were fixed in PR #49 before submitting ("Across 32 models … a median
19 points"; "200 questions", no longer "unseen"). Arsha also added tests that check the frozen results,
demo replay and report view still match their code (PR #48), and Ritik noted the later owner changes in
the Oct 28 meeting notes (PR #46).

**Done later on November 23:** the acceptance test (A2, PR #51) passed: 12 of 12 questions correct and
0 valid cells changed, on the default 30B model (`docs/final/acceptance_test.md`). The approval policy and the
script that ran it are published with offline tests (PR #53), so anyone with a key can rerun it. Vyshanth's
ratings (A1, PR #54, `docs/final/ratings.md`): correctness 5.0, clarity 4.4, trust 4.6 out of 5, on 10 reports.
The team proposed the scores and he confirmed them without changes. He also allowed his two fictional files to
stay in the repo as synthetic examples (`docs/final/checks/acceptance/`).

- **For the final report (found by A1):** a report's summary can misdescribe a rejected fix even when the
  answer is right (S5); the change log itself is accurate.

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
- **Testing:** 191 unit tests run on GitHub for every PR (CI). `python scripts/smoke_e2e.py` is an
  end-to-end check with the real model (123 checks, a few minutes). There is also a Dockerfile.
- **Research studies, all merged** (write-ups in `docs/final/findings_*.md`, charts on the app's `/results` page):
  - *Scale and ablations* (`findings_scale_and_ablations.md`): 95.5% of 200 questions (95% range 92.0 to
    98.5; 4 runs between 94.0% and 96.0%), against 49.0% for B1 and 46.5% for B2. Turning parts off: no approvals
    12.0%, short memory 86.0%, no coverage check 91.5%; the validator and the merge rule showed no clear effect.
  - *Hard benchmark* (`findings_hard.md`): tables of 343 to 1,935 rows. DataSage 30B 90.0% (seed 404: 85.0%),
    235B 97.5%, B1 10.0%, B2 55.0% with 637 damaged cells. DataSage damaged none and fixed all 1,750 errors
    the questions depended on.
  - *Auto mode* (`findings_auto_mode.md`): 113/120 right against 114/120 with a careful approver. Auto now
    pauses and asks before dropping rows that are blank only in the risky column.
  - *Model comparison* (`findings_models.md`): 41 models fully run as the planner. The 30B default ranks 4th
    (93.8%) and is among the fastest. For the 32 models with a complete single-call comparison, DataSage
    answers a median 19 points (19.4) more than one call. No model damaged clean data; the weakest fail on tool-call format.
- **Decided at the Nov 20 review** (`docs/meetings/2026-11-20-review.md`): keep checking only the question's columns, keep the recorded results, keep the 30B default. Background: 36 of the 39 misses over 4 runs of the 200 questions are rows breaking a
  rule in a column the question does not use (60.9% right on those questions, 99.6% on the rest), which
  is the question-columns-only scope Vyshanth chose. On the hard split, every Qwen miss came from
  `analyze` grouping by the column it also filters on. That is now fixed in code (`datasage/analyze.py`):
  the 30B model gets 80 of 80 on both hard seeds, up from 70 (`findings_hard.md`, section 10).

## Dates

| Date | What |
|---|---|
| Nov 16 to 20 | Vyshanth rates 10 DataSage reports (ratings week) |
| **Nov 20, 2:00 PM MST, Zoom** | Review with Vyshanth |
| ~~Nov 23, 2:00 PM~~ | Poster PDF submitted on Canvas (Nov 23, after the fixes in PR #49) |
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
| Poster (print-ready PDF and source) | `docs/final/poster/`: `poster.html` is the source (redesigned Nov 18 from a Claude Design export), `Group25_Poster.pdf` the submitted export; the README lists the source of every number, and `docs/final/checks/poster_verification.md` records Arsha's check. The earlier version is in `previous/`. |
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
doesn't use. Vyshanth chose to check only the question's columns and confirmed it at the Nov 20 review, so the final
version keeps that scope and the report states it.

## Your tasks

Every task ends in a PR into `main`. Put a short note of what you did in `docs/team/<you>/WORKLOG.md`.

### Arsha

No open tasks: A1 ratings (PR #54), A2 acceptance test (PRs #51, #53), A3 poster check (PR #47) and the
frozen-results tests (PR #48) are done.

### Ritik

No open tasks: R1 recipe replay (PR #44, `python -m datasage.recipes save|apply`) and R2 review notes (PR #43) are done.

### Maulik

No open tasks: M1 (PR #38) and M2 (PR #39) are done. M3 was done by Shrey (`docs/final/regression_check.md`).

### Vatsal

No open tasks: V1 (PR #35) and V2 (PR #36) are done.

### Shrey

Owns the browser app (`app/web/`), the research studies (`docs/final/findings_*.md`), and the Demo Day plan (a 3-minute walk-through for the poster session plus a backup screen recording, in `docs/final/demo_script.md`, by Nov 30). Also reviews and merges every PR and assembles the final report. Each of you writes the final-report paragraph for your own tasks.

## Setup (about 5 minutes)

Python 3.11 or newer.

```bash
git clone https://github.com/shrey-Bish/cse598-group25-datasage.git
cd cse598-group25-datasage
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q tests                          # 254 tests, no API key needed
python -m eval.summarize                           # prints the results tables
python -m app.web.server                           # the browser app at http://127.0.0.1:8501 (needs the key)
```

Running DataSage needs an ASU RC model key and `RC_LLM_BASE_URL` in a `.env` file (copy `.env.example`; the
app now refuses to start without the base URL rather than fall back to OpenAI). Use your own key. Rerunning
the studies or the acceptance test needs one; check your quota first. When running many
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
- Vyshanth's two fictional files and their rules are in `docs/final/checks/acceptance/` with his permission
  (Nov 23). His answer keys and reference tables stay private: never commit them.
- Do not edit files in `eval/results/` by hand. They come from `eval/run_eval.py`.
- Small, clear commits are better than one large one.

Questions about the code: ask Shrey, or open a GitHub issue so the answer stays with the repo.
