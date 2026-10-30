# Team handoff: Milestone 2 and after

For: Arsha, Ritik, Maulik and Vatsal. Last updated October 30, 2026.

DataSage works end to end, the Milestone 2 evaluation is done, and the report draft is in the repo. Every
commit so far is Shrey's, and individual grades draw on commit and PR authorship. So each of us needs to
open at least one pull request with real work for Milestone 2. **Please open your PR by November 5** so
Shrey can merge it and rebuild the report before the November 8 deadline.

## Where things stand

| What | Where |
|---|---|
| Milestone 2 report (10 pages) | `docs/milestone2/Group25_DataSage_Milestone2.docx` and `.pdf` |
| Demo run on Vyshanth's sales file | `docs/milestone2/demo/` (console log, report, cleaned file, replay script, trace) |
| Architecture diagram | `docs/milestone2/architecture.png` |
| All evaluation results | `eval/results/summary.md` (tables), `eval/results/<system>/<dataset>/` (one JSON per task, plus traces) |
| The agent | `datasage/` (`agent.py` is the loop, `tools.py` the tool calls, `fixes.py` and `checks.py` the work) |
| Baselines B0, B1, B2 | `baselines/systems.py` |
| Benchmark and scoring | `eval/generate.py`, `eval/scoring.py`, `eval/oracle.py`, `eval/run_eval.py` |

Headline results (share of questions answered correctly):

| System | Sales dev | Penguins dev | Sales held-out | Penguins held-out |
|---|---|---|---|---|
| B1 fixed script | 70% | 45% | 40% | 30% |
| B2 single model call | 30% | 45% | 85% | 35% |
| DataSage, large model | 85% | 85% | 80% | 45% |
| DataSage, large model + exclusion rule | 100% | 100% | 80% | 95% |

Vyshanth reviewed the system in writing on October 28 and agreed the final scope: small model as the
default, automatic handling of clear date formats, a rules key for refunds, and no near-duplicates or code
sandbox. He rates 10 reports in the week of November 16 to 20, and the next review is November 20, 2026,
2:00 PM MST on Zoom.

## Setup (about 5 minutes)

Python 3.11 or newer.

```bash
git clone https://github.com/shrey-Bish/cse598-group25-datasage.git
cd cse598-group25-datasage
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python -m pytest -q tests                          # 13 tests, no API key needed
python -m eval.run_eval --system b1 --dataset sales --results /tmp/b1_check   # no API key needed
python -m eval.summarize                           # prints the results tables
```

Running DataSage itself needs an ASU RC model key in a `.env` file (copy `.env.example`). Use your own key,
or ask Shrey for his privately. The Milestone 2 tasks below do not need one, except the demo command in
Vatsal's setup test.

## How to commit and open a PR

Do this once in the repo folder, with the email on **your** GitHub account (otherwise the commits are not
credited to you):

```bash
git config user.name "Your Name"
git config user.email "the-email-on-your-github-account"
```

For each piece of work:

```bash
git checkout main
git pull
git checkout -b yourname/short-topic
# ...make your changes...
git add <the files you changed>
git commit -m "Say what you did, in a full sentence"
git push -u origin yourname/short-topic
```

Then open a pull request into `main` on GitHub and ask Shrey to review it. Commits that only sit on a
side branch do not show in the main history or on the contribution graph, so the PR needs to be merged.

Rules:

- Never commit `.env` or any API key. The repo is public.
- Do not add Vyshanth's two sample files to the repo unless he says yes. He allowed sending them to the
  ASU model service, not publishing them.
- Do not edit files in `eval/results/` by hand. They are produced by `eval/run_eval.py` and the report
  numbers come from them.
- Small, clear commits are better than one large one.

## Milestone 2 tasks (PR by November 5)

| Who | Branch | Task | Done when |
|---|---|---|---|
| Arsha | `arsha/m2-report-edit` | Final edit of the report: proofread `docs/milestone2/Group25_DataSage_Milestone2.docx`, check every figure and table is referred to in the text and that it stays at 10 pages, then export the PDF again. Add `docs/milestone2/README.md`, a one-page index of the Milestone 2 deliverables (report, demo folder, results summary, and the command behind each table in Section 3). | Edited docx and pdf plus the README are in the PR. |
| Ritik | `ritik/m2-meeting-notes` | Meeting records: `docs/meetings/2026-10-19.md` (date, 2:00 to 2:45 PM MST on Zoom, all six attendees, the plan and design we walked through, Vyshanth's feedback) and `docs/meetings/2026-10-28-review.md` (his written review and each decision: default model, dates, refunds, scope, targets, ratings week, next review). | Both files are in the PR and match Section 1 of the report. |
| Maulik | `maulik/m2-results-check` | Independent check of the results: run `python -m eval.summarize` and confirm Tables 6 to 8 in the report match `eval/results/summary.md`; re-run B1 into a separate folder (command in Setup) and confirm the scores match; read 3 or 4 traces in `eval/results/datasage-fix/sales-heldout/traces/` and confirm the failure causes in the report (for example, misspellings found but not merged). Write it up in `docs/milestone2/results_check.md`. | The write-up lists what matched and anything that did not. |
| Vatsal | `vatsal/m2-setup-check` | Fresh-setup test: clone the repo on your own machine, follow only the README (setup, tests, demo command) and fix anything unclear or wrong in it. Add `docs/milestone2/checklist.md`, mapping every item in the Milestone 2 template to the report section, table or file that covers it. | README fixes and the checklist are in the PR. |

When your PR is merged, Shrey updates the submission commit and adds your PR link to Section 7 of the report.

## After Milestone 2 (final report)

These are the owners from Section 6 of the report.

| # | Work | Owner |
|---|---|---|
| 1 | Small model as the default, under 60 s per question | Shrey |
| 2 | Coverage check before `analyze`, and proposing merges for misspelled labels | Shrey |
| 3 | Automatic date-format conversion (ask only on ambiguous dates) and an `allow_negative_quantities` rules key | Maulik |
| 4 | Evaluation on real messy files, including Vyshanth's two once he agrees | Maulik, Vatsal |
| 5 | Repeated runs (3 runs on the held-out tasks, report mean and range) | Arsha |
| 6 | Vyshanth's ratings of 10 reports and the acceptance test (3 files, at least 90% accuracy, no corrupted data) | Arsha |
| 7 | Streamlit demo page and reusable cleaning recipes | Ritik, Arsha |
| 8 | November 20 review, final report, presentation and Demo Day | All |

Questions about the code: ask Shrey, or open a GitHub issue so the answer stays with the repo.
