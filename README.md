# CSE 598 Group 25: DataSage

Capstone project for CSE 598 Agentic AI (Arizona State University, Fall 2026).

DataSage is an agent that takes a messy CSV or Excel file and a question about it, finds data-quality problems, fixes or flags them (asking the user before any risky change), and then answers the question on the cleaned data with a report of every change it made.

- **Stakeholder:** Vyshanth Buddani. Original proposal and baseline: https://github.com/VB914/DataSage
- **Team (Group 25):** Shrey Bishnoi, other members to be added

## Repository layout

```text
baseline/   the stakeholder's rule-based baseline, copied unchanged from VB914/DataSage (commit 4b1df80)
eval/       evaluation data and scripts; eval/probes/ holds small hand-made files with known issues
docs/       milestone reports
```

The agent code will live in a `datasage/` package once Phase 2 starts.

## Run the baseline

The baseline needs Python 3.11 or newer, because pandas 3 does not support older versions.

```bash
cd baseline
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run_baseline.py --input examples/messy_sales.csv --analysis revenue_by_category
python smoke_test.py
```

## Team workflow

- Commit under your own GitHub account. Individual grades use commit and pull request authorship.
- Work on a branch and open a pull request into `main`. Ask one teammate to review before merging.
- Never commit API keys. Put them in a local `.env` file, which git already ignores.
- Keep any stakeholder data that is not public out of this repository.
