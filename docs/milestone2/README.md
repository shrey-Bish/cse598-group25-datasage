# Milestone 2 folder

This folder holds the Milestone 2 report and the files its figures come from. The evaluation numbers
live in `eval/results/`, not here. Run every command below from the repository root, after the setup
steps in the top-level [README](../../README.md).

## Files

| File or folder | What it is | Backs in the report |
|---|---|---|
| `Group25_DataSage_Milestone2.docx` | The report, edited by hand in Word (no script in the repo writes it) | All sections |
| `Group25_DataSage_Milestone2.pdf` | PDF export of the docx (10 pages) | The submitted copy |
| `architecture.png` | Architecture diagram of the system as built | Figure 1 |
| `architecture.html` | HTML (inline SVG) version of the same diagram, added in the same commit as the PNG | Figure 1 |
| `demo/` | Outputs of the recorded run on the stakeholder's sales file | Section 4 |
| `demo/console.txt` | Terminal log: one line per tool call, the approval decisions, then the stop line | Figure 2 |
| `demo/report.md` | Report from that run: problems found, change log (Changes table), answer, summary | Figure 3 |
| `demo/cleaned.csv` | Cleaned copy (version v3, 7 rows); the first column `row` is the original row id | Section 4, "Result" |
| `demo/replay.py` | Plain pandas script that repeats the applied fixes without the agent | Section 4, "Result" |
| `demo/trace.jsonl` | One JSON record per tool call: name, arguments, ok, output, time | Section 4 |

Figure 4 (Section 5) is a trace excerpt from `eval/results/datasage/sales/traces/sales_05_q0.jsonl`,
and the failure causes in Section 5 come from `python -m eval.failures --system datasage`, which writes
`eval/results/failures_datasage.json`.

## Rerun the demo (Section 4, Figures 2 and 3)

This needs an ASU RC model key in `.env` (see the top-level README). The command is the README's demo
command with the approval mode the README names for the recorded demo:

```bash
python -m datasage --input baseline/examples/messy_sales.csv \
  --rules examples/messy_sales_rules.json \
  --request "What was total revenue by category?" \
  --approve tools --allow drop_duplicates,parse_dates
```

Outputs go to `outputs/run/` (the default of `--out` in `datasage/__main__.py`). The recorded run wrote
to `outputs/demo/` (last line of `demo/console.txt`) and its files were then copied into `demo/` here.
No script does that copy. A new run can differ in wording and timing, because the model is not exactly
repeatable even at temperature 0 (Section 5).

## Regenerate the Section 3 tables

The systems and datasets below are the names listed in the top-level README. Each run writes one JSON
per task to `eval/results/<system>/<dataset>/`, and finished tasks are skipped on a rerun.

```bash
python -m eval.generate --tables 10 --seed 7                      # dev split
python -m eval.generate --tables 10 --seed 101 --split heldout    # held-out split
python -m eval.run_eval --system <system> --dataset <dataset>     # once per pair below
python -m eval.summarize                                          # writes eval/results/summary.md
```

| Table | Systems | Datasets | Where the numbers come from |
|---|---|---|---|
| 3: Datasets | (none) | all four | `eval/generate.py` writes `eval/datasets/<dataset>/<table>/`. Rows: data rows in each `messy.csv`; tasks: entries in `tasks.json`; planted errors: length of the `errors` list in `planted.json` (checked: 96, 95, 108 and 88) |
| 4: Baselines | `b0`, `b1`, `b2` | (none) | Descriptions; code in `baselines/systems.py` (`run_b0`, `run_b1`, `run_b2`) |
| 5: Metrics | (none) | (none) | Definitions in `eval/scoring.py`; totals in `aggregate()` in `eval/summarize.py` |
| 6: Main results, dev | `b0`, `b1`, `b2`, `datasage`, `datasage-small` | `sales`, `penguins` | `summary.md`, sections `sales` and `penguins` |
| 7: Answer accuracy | `b0`, `b1`, `b2`, `datasage`, `datasage-fix`, `datasage-small`, `datasage-small-fix`, `datasage-small-fix-strict` | all four | `summary.md`, column "Answer correct". "Held-out damage" is the Damage of `sales-heldout` plus `penguins-heldout` |
| 8: Ablations | `datasage`, `datasage-reject`, `datasage-novalidator` | `sales`, `penguins` | Reject and no-validator rows: `summary.md` (n = 10). The 235B rows are the first 10 task files in `eval/results/datasage/<dataset>/`, which `summarize.py` does not compute. Command for the 10-task runs: `python -m eval.run_eval --system datasage-reject --dataset sales --limit 10`, and the same for `datasage-novalidator` and for `penguins` |

How `eval/summarize.py` builds `summary.md`: `main()` loops `for dataset in ("sales", "penguins",
"sales-heldout", "penguins-heldout")` and `for system in ORDER`, loads every task JSON with `load(system,
dataset)`, and writes one row per system with `aggregate(rows)`. The columns are `COLUMNS`: Answer correct,
Completed, Detect P, Detect R, Errors handled, Damage, Tool-call OK, Recovery, Approvals (med), Latency s
(med) and Tokens (med). It also writes `summary.csv` and `summary.json`.

`b0` and `b1` need no API key. The other systems call the model service. Do not edit files in
`eval/results/` by hand; the report numbers come from them.
