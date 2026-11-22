# CSE 598 Group 25: DataSage

Capstone project for CSE 598 Agentic AI (Arizona State University, Fall 2026).

DataSage is an agent that takes a messy CSV or Excel file and a question about it, finds data-quality problems, fixes or flags them (asking the user before any risky change), and then answers the question on the cleaned data with a report of every change it made.

**Try it online:** https://cse598-group25-datasage.vercel.app (the browser app below, hosted on Vercel; pick a sample and press Run).

**Stakeholder:** Vyshanth Buddani ([@VB914](https://github.com/VB914)). Original proposal and baseline: https://github.com/VB914/DataSage

## Results at a glance

| | Right answers | Damaged cells |
|---|---|---|
| **DataSage (Qwen3-30B, the default)** on 200 unseen questions | **95.5%** (95% range 92.0 to 98.5; 4 runs: 94.0 to 96.0) | **0** |
| One LLM call, no tools | 46.5% | 119 |
| A fixed cleaning script | 49.0% | 0 |
| The stakeholder's rule-based script | 6.0% | 0 |
| DataSage on the hard split (343 to 1,935 rows) | 90.0%, and 100% (80 of 80 over two seeds) after the grouping fix | 0 |

- Turning parts off on the same 200 questions: no approvals 12.0%, short memory 86.0%, no coverage check 91.5%;
  the validator and the prompt's merge rule showed no measurable effect.
- Almost every remaining miss is a row that breaks a rule in a column the question does not use (the
  question-columns-only scope chosen with the stakeholder).
- *Auto* approval mode costs about one question in 120 against a careful approver.
- Swapping the planner across 41 models on the ASU API: with DataSage around it, a model answers a median
  20 points more than in one call; the Qwen3-30B default ranks 4th (93.8%) and is among the fastest.
  No model damaged clean data; the weakest fail because they cannot produce valid tool calls.

Write-ups: [scale, variance and ablations](docs/final/findings_scale_and_ablations.md) ·
[hard benchmark](docs/final/findings_hard.md) · [Auto mode](docs/final/findings_auto_mode.md) · [model comparison](docs/final/findings_models.md).
The browser app's **Results** page (`/results`) shows the same numbers as charts.

## Team (Group 25)

| Name | GitHub |
|---|---|
| Shrey Bishnoi | [@shrey-Bish](https://github.com/shrey-Bish) |
| Ritik Agarwal | [@ritwiz06](https://github.com/ritwiz06) |
| Arsha Jindal | [@Arshajindal](https://github.com/Arshajindal) |
| Maulik Jadav | [@maulik-jadav](https://github.com/maulik-jadav) |
| Vatsal Nirmal | [@vatsal-prog](https://github.com/vatsal-prog) |

Team tasks, setup and how to open a pull request: [docs/TEAM_HANDOFF.md](docs/TEAM_HANDOFF.md).

## Repository layout

```text
app/web/      the browser app (python -m app.web.server)
datasage/     the agent: session state, profiler, checks, fixes, approval gate, validator,
              analysis, tool schemas and dispatcher, agent loop, report and replay script
baselines/    B0 (stakeholder baseline wrapper), B1 (fixed cleaning script), B2 (single model call),
              and the DataSage runner used by the evaluation
baseline/     the stakeholder's rule-based baseline, copied unchanged from VB914/DataSage (commit 4b1df80)
eval/         benchmark generator, scoring, approval oracle, evaluation runner, results
  sources/    public source data (Palmer Penguins, CC0) and its license note
  datasets/   generated tables: messy.csv, clean.csv, reference.csv, planted.json, rules.json, tasks.json
  results/    one JSON per task per system, traces, and summary.md / summary.csv
examples/     rules file for the stakeholder's messy_sales.csv, and a 1,208-row demo table with its generator
tests/        unit tests for the deterministic parts (no model calls)
docs/         milestone reports; docs/milestone2/demo/ holds the recorded demo run
```

## Setup

Python 3.11 or newer is required (pandas 3 does not support older versions).

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env    # then put your ASU RC LLM key in .env
python -m pytest -q tests
```

An end-to-end check with the real model (needs the `.env` key, a few minutes): `python scripts/smoke_e2e.py`
drives the browser app through every sample in Auto and Ask mode, uploads (CSV dialects, Excel sheets,
several files), Stop, downloads, the file viewer and profile, replay.py and the command line.

The tests also run on GitHub for every pull request (`.github/workflows/tests.yml`); they need no API key.

The agent calls an OpenAI-compatible endpoint. We use ASU Research Computing
(`RC_LLM_BASE_URL=https://openai.rc.asu.edu/v1`) with `qwen3-30b-a3b-instruct-2507` (the default since
Milestone 3, about 15 s per question) and `qwen3-235b-a22b-instruct-2507` (pass `--model` to use it).
`.env` is ignored by git.

## Run DataSage

```bash
python -m datasage --input baseline/examples/messy_sales.csv \
  --rules examples/messy_sales_rules.json \
  --request "What was total revenue by category?"
```

Several files with the same columns (for example monthly exports) can be given together:
`--input jan.csv feb.csv mar.csv`. They are stacked into one table with a `source_file` column, so a
question can be answered across all of them or per file ("What was total revenue in each monthly file?").
Columns are matched by name (order and case can differ); files with different columns are refused with a
list of what is missing or extra.

Input files: CSV (the separator `,` `;` tab or `|` and the encoding UTF-8, Windows-1252 or Latin-1 are
detected) or Excel `.xlsx` (`--sheet NAME` picks a sheet; default the first). The replay script reads the
file the same way.

By default each medium or high risk fix is shown at the terminal and needs `y` to be applied. Other
modes: `--approve auto`, `--approve reject`, and `--approve tools --allow drop_duplicates,parse_dates`
(approve only those fix types, used for the recorded demo). Outputs go to `outputs/run/`:
`report.md`, `cleaned.csv` (the original file is never changed), `replay.py` (plain pandas), and
`trace.jsonl` (every tool call).

### Date handling

`parse_dates` automatically converts clear dates and ISO timestamps (for example
`2024-06-03T00:00:00.000` or `2024-06-03 14:05`) to `YYYY-MM-DD`, preserving the written calendar
day without changing timezones. Year-first slash/dot dates and numeric day/month dates with only
one valid interpretation are also clear. Unreadable or impossible dates become missing; rows are
kept. These changes are low risk and each changed cell is recorded in the report and change log.

Ambiguous numeric dates such as `03/04/2026` stay unchanged by default. A `parse_dates` call with
`date_order: "dmy"` or `"mdy"` proposes an interpretation and requires approval (Auto mode also
pauses for a person). DataSage does not infer the order from nearby dates or silently guess a locale.

## Run DataSage in the browser

```bash
python -m app.web.server          # then open http://127.0.0.1:8501
```

Drop a CSV or Excel file (and optionally a JSON rules file), type a question and press Run, or pick one
of the samples: Vyshanth's 8-row `messy_sales.csv`; `examples/large_sales.csv` (1,208 rows, about 50 planted
problems; `python examples/make_large_sales.py`); the same orders as three monthly files
(`examples/demo/monthly/`, stacked into one table); an HR table (407 rows, average salary by department) and
an inventory table (606 rows, stock value by warehouse, with 18 rule-breaking rows), both made by
`python examples/make_demo_files.py`, which also prints the right answers. You can also pick or drop
several files with the same columns at once.

- **Ask me or Auto.** Chosen on the start screen: *Ask me* (default) stops at every risky fix; *Auto*
  applies every fix without asking, shows each one briefly, and still logs it as approved automatically.
  During a run the mode is locked and shown in the header; *New run* goes back to change it.
- **Three tabs.** *Table* is the live run on one screen; *Answer* opens by itself when the run ends; *Data
  health* shows what the run found and did.
- **Live table.** The first 40 rows show at once; any row with a problem, anywhere in the file, slides in
  as the agent finds it. Problem cells are amber, fixed cells green, removed rows fold away, and rejected
  fixes stay marked as caveats.
- **Approvals on the row.** Each risky fix opens a card under the affected row, saying what it will do and
  showing the exact rows: removed rows in full, or each changed cell as old → new. Click a row number to
  jump to it. Keep or Apply decides it.
- **Answer.** The result counts up, with every change and who approved it, the agent's summary as short
  bullets, and the four output files, each with a line on what it is for. **View** opens any of them in a
  new tab (the table, the report rendered, the replay script, the step log as a timeline) with its own
  Download button; earlier runs stay viewable after a server restart.
- **Data health.** After the run: rows before and after, every problem found by column (fixed, kept as a
  caveat, or not needed for the question), and the answer before cleaning next to the answer after.

With Docker instead: `docker build -t datasage .` then `docker run --rm -p 8501:8501 --env-file .env datasage`.

Two more pages: **Results** (`/results`, linked in the header) is the evaluation dashboard: accuracy per
system and split, accuracy against speed, detection, damage, the Milestone 2 to 3 progression, ablations
and the remaining failure causes, all read from `eval/results/`. **Column profile** (`/profile?run=<id>`,
linked under "Your files" after a run) compares every column before and after cleaning.

It needs the same `.env` key as the command line and nothing else (standard library only). Uploads and
outputs go to `outputs/web/<run id>/`. Options: `--port`, `--model`, `--host` (default 127.0.0.1, so only
your machine can open it). An approval left unanswered for 10 minutes, or a run replaced by a new one,
counts as rejected.

### The hosted version (Vercel)

https://cse598-group25-datasage.vercel.app runs the same pages and agent from `app/web/hosted.py` (FastAPI).
A serverless host keeps nothing between requests and may send each one to a different machine, so the
hosted app carries each run over **one WebSocket**: the upload, every step, each approval and Stop, and at
the end the output files and column profile. The page keeps those in the browser, so View, Download and
the profile tab work from that browser. Differences from the local app: a run stops after 4 minutes
(the free plan ends a connection at 5), an approval waits 2 minutes, and uploads should stay under about
10 MB. To try it locally: `uvicorn app.web.hosted:app --port 8600`.

Deploys: the Vercel project is connected to this repository, so a merge to `main` redeploys production
and other branches get preview deployments. Settings live in the Vercel project, not in the repo:
`RC_LLM_API_KEY` and `RC_LLM_BASE_URL` (required), and optionally `DATASAGE_MODEL`, `DATASAGE_RUN_LIMIT`,
`DATASAGE_APPROVAL_TIMEOUT`. `pyproject.toml` names the entry point and `.vercelignore` keeps `.env`,
traces and other large folders out of the deployment.

## Reproduce the evaluation

```bash
python -m eval.generate --tables 10 --seed 7          # dev split: 20 sales + 20 penguin tasks
python -m eval.generate --tables 10 --seed 101 --split heldout   # held-out split (sales-heldout, penguins-heldout)
python -m eval.generate --tables 10 --seed 202 --split test      # test split made for Milestone 3 (sales-test, penguins-test)
python -m eval.generate_hard --tables 10 --seed 303   # hard split: sales-hard, penguins-hard (300-2,000 rows, see docs/final/findings_hard.md)
python -m eval.generate_hard --tables 10 --seed 404 --split hard2   # second hard seed: sales-hard2, penguins-hard2
python -m eval.analyze_hard                           # hard split aggregates -> eval/results/hard_analysis.json
python -m eval.run_eval --system b0 --dataset sales   # repeat for each system and dataset
python -m eval.run_eval --system datasage --dataset penguins --workers 4
python -m eval.run_eval --system datasage-reject --dataset sales --limit 10   # Table 8 ablations: first 10 tasks;
python -m eval.run_eval --system datasage-novalidator --dataset sales --limit 10   # repeat both for penguins
python -m eval.summarize                              # writes eval/results/summary.md
python -m eval.failures --system datasage             # likely cause of each wrong task, from its trace
```

Scale and ablation study of the final system (`docs/final/findings_scale_and_ablations.md`):

```bash
python -m eval.generate --tables 10 --seed 303 --split s303      # also 404 and 505: sales-s303, penguins-s303, ...
python -m eval.run_eval --system datasage-m3 --dataset sales-s303 --workers 6
python -m eval.run_eval --system datasage-m3 --dataset sales-test --results eval/results/repeats/rep1   # repeat runs
python -m eval.run_eval --system datasage-m3-nocoverage --dataset sales-s303   # ablations, see below
python -m eval.study      # CIs, paired tests, root causes -> eval/results/study_scale_ablations.json
```

Ablations of `datasage-m3`: `datasage-m3-nocoverage` (no coverage check), `datasage-m3-novalidator`,
`datasage-m3-nomerge` (prompt without the merge rule), `datasage-m3-compact` (compact memory) and
`datasage-m3-reject` (every risky fix rejected).

Table 3 (rows, tasks and planted errors) is counted from the generated files: rows in each table's
`messy.csv`, tasks in `tasks.json`, and planted errors in the `errors` list of `planted.json`, under
`eval/datasets/<dataset>/`. Table 8's ordinary 235B rows are the same first 10 task files from
`eval/results/datasage/`, not the 20-task averages in `summary.md`.

Systems: `b0`, `b1`, `b2`, `datasage`, `datasage-small`, `datasage-reject`, `datasage-novalidator`, and the
Milestone 2 fix variants `datasage-fix`, `datasage-small-fix`, `datasage-small-fix-strict` (exclusion rule in the
prompt; `-strict` also uses a stricter approval oracle). Milestone 3: `datasage-m3` is the default agent (30B,
coverage check before `analyze`, spelling merges into the rules' allowed labels); `datasage-m3-compact` is the
same with compact memory, and `datasage-m3-large` uses the 235B model. Later studies added `datasage-m3-auto`
(every risky fix approved, like the app's Auto mode), `datasage-m3-gptoss` (gpt-oss-120b as the planner) and
the ablations above; the model comparison adds `datasage-m3-<model>` and `b2-<model>` for 44 models. Datasets: `sales`, `penguins`, `sales-heldout`, `penguins-heldout`, `sales-test`,
`penguins-test`, `sales-s303` / `-s404` / `-s505` and the penguin twins, `sales-hard`, `penguins-hard`,
`sales-hard2`, `penguins-hard2`. Results are cached per task, so an
interrupted run can be restarted.

Model comparison (`docs/final/findings_models.md`): the final system and the B2 baseline with each chat model on
the ASU API as the planner, on the 80 held-out and test questions.

```bash
python -m eval.model_study probe                   # which models return valid tool calls -> eval/results/model_probe.json
python -m eval.model_study_driver agent 48 6       # all unfinished datasage-m3-<model> pairs from one process
python -m eval.model_study_driver b2 4 6           # the same for b2-<model>
python -m eval.model_study aggregate               # -> eval/results/study_models.json
python -m eval.model_study_doc                     # fills docs/final/findings_models.md from the results
```

## Run the stakeholder baseline on its own

```bash
cd baseline
python run_baseline.py --input examples/messy_sales.csv --analysis revenue_by_category
python smoke_test.py
```

## Team workflow

- Commit under your own GitHub account. Individual grades use commit and pull request authorship.
- Work on a branch and open a pull request into `main`. Ask one teammate to review before merging.
- Never commit API keys. Put them in a local `.env` file, which git already ignores.
- Keep any stakeholder data that is not public out of this repository.
