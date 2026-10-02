from pathlib import Path
import subprocess
import sys


PROJECT_ROOT = Path(__file__).resolve().parent
CSV_INPUT = PROJECT_ROOT / "examples" / "messy_sales.csv"
EXCEL_INPUT = PROJECT_ROOT / "examples" / "messy_sales.xlsx"
OUTPUT_DIR = PROJECT_ROOT / "outputs"


def run_command(arguments):
    """Run the baseline and return the completed process."""
    return subprocess.run(
        [sys.executable] + arguments,
        cwd=PROJECT_ROOT,
        capture_output=True,
        text=True,
    )


def check_csv_baseline():
    """Verify that the CSV baseline runs successfully."""
    result = run_command(
        [
            "run_baseline.py",
            "--input",
            str(CSV_INPUT),
            "--analysis",
            "revenue_by_category",
            "--output",
            str(OUTPUT_DIR / "smoke_csv_report.md"),
        ]
    )

    assert result.returncode == 0, result.stderr
    assert "Rows: 8" in result.stdout
    assert "Columns: 8" in result.stdout
    assert "'Region': 1" in result.stdout
    assert "Duplicate rows: 1" in result.stdout
    assert "'Quantity': 1" in result.stdout
    assert "'Revenue': 1" in result.stdout
    assert "'not-a-date'" in result.stdout
    assert "Electronics: $2,060.00" in result.stdout
    assert "Accessories: $1,350.00" in result.stdout
    assert (OUTPUT_DIR / "smoke_csv_report.md").exists()

    print("PASS: CSV baseline")


def check_excel_baseline():
    """Verify that the Excel baseline runs successfully."""
    result = run_command(
        [
            "run_baseline.py",
            "--input",
            str(EXCEL_INPUT),
            "--analysis",
            "revenue_by_category",
            "--output",
            str(OUTPUT_DIR / "smoke_excel_report.md"),
        ]
    )

    assert result.returncode == 0, result.stderr
    assert "Rows: 8" in result.stdout
    assert "Columns: 8" in result.stdout
    assert "Duplicate rows: 1" in result.stdout
    assert "'not-a-date'" in result.stdout
    assert "Electronics: $2,060.00" in result.stdout
    assert "Accessories: $1,350.00" in result.stdout
    assert (OUTPUT_DIR / "smoke_excel_report.md").exists()

    print("PASS: Excel baseline")


def check_missing_input():
    """Verify that a missing input file causes a failure."""
    missing_input = PROJECT_ROOT / "examples" / "does_not_exist.csv"

    result = run_command(
        [
            "run_baseline.py",
            "--input",
            str(missing_input),
        ]
    )

    assert result.returncode != 0
    assert "Input file not found" in result.stderr

    print("PASS: Missing input handling")


def main():
    check_csv_baseline()
    check_excel_baseline()
    check_missing_input()

    print("All DataSage baseline smoke tests passed.")


if __name__ == "__main__":
    main()