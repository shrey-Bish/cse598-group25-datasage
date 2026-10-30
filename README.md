# CSE 598 Group 25: DataSage

Capstone project for CSE 598 Agentic AI (Arizona State University, Fall 2026).

DataSage is an agent that takes a messy CSV or Excel file and a question about it, finds data-quality problems, fixes or flags them (asking the user before any risky change), and then answers the question on the cleaned data with a report of every change it made.

**Stakeholder:** Vyshanth Buddani ([@VB914](https://github.com/VB914)). Original proposal and baseline: https://github.com/VB914/DataSage

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
datasage/     the agent: session state, profiler, checks, fixes, approval gate, validator,
              analysis, tool schemas and dispatcher, agent loop, report and replay script
baselines/    B0 (stakeholder baseline wrapper), B1 (fixed cleaning script), B2 (single model call),
              and the DataSage runner used by the evaluation
baseline/     the stakeholder's rule-based baseline, copied unchanged from VB914/DataSage (commit 4b1df80)
eval/         benchmark generator, scoring, approval oracle, evaluation runner, results
  sources/    public source data (Palmer Penguins, CC0) and its license note
  datasets/   generated tables: messy.csv, clean.csv, reference.csv, planted.json, rules.json, tasks.json
  results/    one JSON per task per system, traces, and summary.md / summary.csv
examples/     rules file for the stakeholder's messy_sales.csv
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

The agent calls an OpenAI-compatible endpoint. We use ASU Research Computing
(`RC_LLM_BASE_URL=https://openai.rc.asu.edu/v1`) with `qwen3-235b-a22b-instruct-2507` (default) and
`qwen3-30b-a3b-instruct-2507` (small model). `.env` is ignored by git.

## Run DataSage

```bash
python -m datasage --input baseline/examples/messy_sales.csv \
  --rules examples/messy_sales_rules.json \
  --request "What was total revenue by category?"
```

By default each medium or high risk fix is shown at the terminal and needs `y` to be applied. Other
modes: `--approve auto`, `--approve reject`, and `--approve tools --allow drop_duplicates,parse_dates`
(approve only those fix types, used for the recorded demo). Outputs go to `outputs/run/`:
`report.md`, `cleaned.csv` (the original file is never changed), `replay.py` (plain pandas), and
`trace.jsonl` (every tool call).

## Reproduce the evaluation

```bash
python -m eval.generate --tables 10 --seed 7          # dev split: 20 sales + 20 penguin tasks
python -m eval.generate --tables 10 --seed 101 --split heldout   # held-out split (sales-heldout, penguins-heldout)
python -m eval.run_eval --system b0 --dataset sales   # repeat for each system and dataset
python -m eval.run_eval --system datasage --dataset penguins --workers 4
python -m eval.summarize                              # writes eval/results/summary.md
python -m eval.failures --system datasage             # likely cause of each wrong task, from its trace
```

Systems: `b0`, `b1`, `b2`, `datasage`, `datasage-small`, `datasage-reject`, `datasage-novalidator`, and the
Milestone 2 fix variants `datasage-fix`, `datasage-small-fix`, `datasage-small-fix-strict` (exclusion rule in the
prompt; `-strict` also uses a stricter approval oracle). Datasets: `sales`, `penguins`, `sales-heldout`,
`penguins-heldout`. Results are cached per task, so an interrupted run can be restarted.

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
