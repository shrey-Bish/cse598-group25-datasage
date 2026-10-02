# DataSage

DataSage is a capstone project for CSE 598: Agentic AI. The project explores an agentic system for data quality, cleaning, validation, and user-requested analysis of structured datasets.

This repository contains the initial runnable baseline for the project. The baseline currently supports CSV and Excel (`.xlsx`) files. It performs deterministic data-quality checks and a fixed revenue-by-category analysis.

## Current Baseline

The baseline currently:

- loads CSV and Excel datasets;
- reports dataset dimensions and column names;
- detects missing values;
- detects exact duplicate rows;
- detects negative numeric values;
- detects malformed values in date/time columns;
- detects case-insensitive categorical inconsistencies;
- performs a revenue-by-category analysis; and
- saves the results as a Markdown report.

The baseline intentionally does **not** automatically clean or modify the input dataset. It also does not yet perform autonomous planning, tool selection, retrieval-augmented generation (RAG), iterative error recovery, or arbitrary natural-language analysis. These capabilities are planned for later project phases.

## Repository Structure

```text
DataSage/
|-- examples/
|   |-- messy_sales.csv
|   `-- messy_sales.xlsx
|-- outputs/
|   |-- baseline_report.md
|   |-- excel_baseline_report.md
|   |-- smoke_csv_report.md
|   `-- smoke_excel_report.md
|-- screenshots/
|   `-- baseline_success.png
|-- .gitignore
|-- README.md
|-- requirements.txt
|-- run_baseline.py
`-- smoke_test.py
```

## Requirements

The baseline was developed and tested with:

- Python 3.14.7
- pandas 3.0.5
- openpyxl 3.1.5

No API keys or external services are required for the current baseline.

## Setup

### 1. Clone the repository

```bash
git clone https://github.com/VB914/DataSage.git
cd DataSage
```

### 2. Create a virtual environment

On Windows Command Prompt:

```cmd
python -m venv .venv
.venv\Scripts\activate
```

### 3. Install dependencies

```cmd
python -m pip install -r requirements.txt
```

## Run the Baseline

The example input datasets are located in the `examples/` directory.

### CSV example

```cmd
python run_baseline.py --input examples\messy_sales.csv --analysis revenue_by_category
```

### Excel example

```cmd
python run_baseline.py --input examples\messy_sales.xlsx --analysis revenue_by_category --output outputs\excel_baseline_report.md
```

If `--output` is not specified, the generated report is saved to:

```text
outputs/baseline_report.md
```

## Input

The current baseline accepts:

- `.csv` files
- `.xlsx` files

The included test dataset contains intentionally introduced data-quality problems, including:

- a missing region value;
- an exact duplicate row;
- negative quantity and revenue values;
- an invalid date value; and
- inconsistent capitalization in categorical labels.

## Output

The baseline prints the detected data-quality issues and analysis results to the terminal.

It also generates a Markdown report in the `outputs/` directory. The default output file is:

```text
outputs/baseline_report.md
```

The report contains:

- dataset dimensions and column names;
- detected data-quality issues;
- invalid date values;
- inconsistent categorical labels; and
- revenue totals grouped by category.

## Test Case

The repository includes a small synthetic sales dataset for testing the baseline:

```text
examples/messy_sales.csv
```

The dataset contains 8 rows and 8 columns and intentionally includes several data-quality problems.

For this test case, the expected baseline behavior is to:

1. load the dataset successfully;
2. identify one missing `Region` value;
3. identify one exact duplicate row;
4. identify one negative `Quantity` value;
5. identify one negative `Revenue` value;
6. identify `not-a-date` as an invalid value in the `Date` column;
7. identify inconsistent capitalization in the `Category` column; and
8. calculate revenue totals grouped by the original category labels.

Run the test case with:

```cmd
python run_baseline.py --input examples\messy_sales.csv --analysis revenue_by_category
```

The baseline should produce revenue totals including:

```text
Electronics: $2,060.00
Accessories: $1,350.00
electronics: $125.00
accessories: $80.00
```

A screenshot of a successful baseline run is available at:

```text
screenshots/baseline_success.png
```

## Smoke Tests

The repository also includes `smoke_test.py` to verify the main baseline workflow automatically.

Run:

```cmd
python smoke_test.py
```

A successful run should report:

```text
PASS: CSV baseline
PASS: Excel baseline
PASS: Missing input handling
All DataSage baseline smoke tests passed.
```

The smoke tests verify that:

- the CSV baseline executes successfully;
- the Excel baseline executes successfully;
- expected quality issues are detected;
- expected analysis results are produced;
- Markdown reports are generated; and
- a missing input file causes the baseline to fail rather than silently continue.

## Known Limitations

The current baseline is intentionally simple and serves as a starting point for the semester project.

Current limitations include:

- quality checks are deterministic and predefined;
- detected problems are reported but not automatically corrected;
- the analysis operates on the original data even when quality problems are detected;
- differently capitalized category labels remain separate during analysis;
- only one predefined analysis (`revenue_by_category`) is currently supported;
- the baseline does not accept arbitrary natural-language analysis questions;
- it does not autonomously choose tools or cleaning strategies;
- it does not retrieve domain-specific rules or data definitions;
- it does not validate proposed corrections or retry failed actions; and
- input support is currently limited to CSV and Excel files.

These limitations provide the starting point for evaluating future versions of DataSage.

## Future Project Direction

The current implementation is a minimal baseline rather than the final agentic system. The semester project will investigate how DataSage can evolve from predefined quality checks and analysis into a more autonomous and reliable data workflow.

Planned directions include:

- allowing the system to reason about detected data-quality problems and propose appropriate cleaning actions;
- distinguishing between safe automatic corrections and ambiguous cases that require user approval;
- executing approved cleaning operations and validating the resulting dataset before analysis;
- accepting user-requested analysis instead of relying only on a predefined analysis;
- using Python data-analysis tools to execute calculations and generate evidence-backed results;
- adding iterative tool use so the system can inspect results, detect failures, revise its plan, and retry when appropriate;
- retrieving domain-specific data definitions, schemas, or rules when a cleaning or analysis decision requires information that is not available in the dataset itself;
- evaluating whether retrieval-augmented generation (RAG) improves decisions on tasks that require this external domain knowledge; and
- exploring additional structured data sources, such as JSON or SQL databases, after the core CSV/Excel workflow is reliable.

The future system will be evaluated against this baseline using controlled datasets with known quality problems and analysis tasks with verifiable answers. Evaluation will consider factors such as issue-detection accuracy, correction accuracy, analysis correctness, task completion, reliability, tool failures, and the system's ability to avoid unsupported or unsafe modifications.