import argparse
from pathlib import Path

import pandas as pd


def load_dataset(input_path: str) -> pd.DataFrame:
    """Load a CSV or Excel dataset into a pandas DataFrame."""
    path = Path(input_path)

    if not path.exists():
        raise FileNotFoundError(f"Input file not found: {path}")

    suffix = path.suffix.lower()

    if suffix == ".csv":
        return pd.read_csv(path)

    if suffix == ".xlsx":
        return pd.read_excel(path)

    raise ValueError(
        f"Unsupported file type: {suffix}. "
        "Supported formats are .csv and .xlsx."
    )


def profile_quality(df: pd.DataFrame) -> dict:
    """Run deterministic data-quality checks."""
    results = {}

    # Check for missing values in each column.
    missing = df.isna().sum()
    results["missing_values"] = {
        column: int(count)
        for column, count in missing.items()
        if count > 0
    }

    # Check for exact duplicate rows.
    results["duplicate_rows"] = int(df.duplicated().sum())

    # Check for negative values in numeric columns.
    negative_values = {}

    for column in df.select_dtypes(include="number").columns:
        count = int((df[column] < 0).sum())

        if count > 0:
            negative_values[column] = count

    results["negative_values"] = negative_values

    # Check for invalid date values in columns whose names suggest dates.
    invalid_dates = {}

    for column in df.columns:
        column_name = str(column).lower()

        if "date" in column_name or "time" in column_name:
            non_missing = df[column].notna()
            converted = pd.to_datetime(df[column], errors="coerce")

            invalid_mask = converted.isna() & non_missing
            invalid_count = int(invalid_mask.sum())

            if invalid_count > 0:
                invalid_values = (
                    df.loc[invalid_mask, column]
                    .astype(str)
                    .tolist()
                )

                invalid_dates[column] = {
                    "count": invalid_count,
                    "values": invalid_values,
                }

    results["invalid_dates"] = invalid_dates

    # Check for case-insensitive duplicate category labels.
    inconsistent_categories = {}

    for column in df.select_dtypes(include="str").columns:
        grouped = {}

        for original_value in df[column].dropna().astype(str):
            cleaned_value = original_value.strip()
            normalized_value = cleaned_value.lower()

            grouped.setdefault(normalized_value, set()).add(cleaned_value)

        conflicts = {
            key: sorted(values)
            for key, values in grouped.items()
            if len(values) > 1
        }

        if conflicts:
            inconsistent_categories[column] = conflicts

    results["inconsistent_categories"] = inconsistent_categories

    return results


def analyze_revenue_by_category(df: pd.DataFrame) -> pd.Series:
    """Calculate total revenue grouped by product category."""
    required_columns = {"Category", "Revenue"}

    missing_columns = required_columns - set(df.columns)

    if missing_columns:
        raise ValueError(
            "Revenue-by-category analysis requires these columns: "
            f"{sorted(required_columns)}. "
            f"Missing: {sorted(missing_columns)}"
        )

    revenue_by_category = (
        df.groupby("Category", dropna=False)["Revenue"]
        .sum()
        .sort_values(ascending=False)
    )

    return revenue_by_category


def build_report(
    input_path: str,
    df: pd.DataFrame,
    quality: dict,
    revenue_by_category: pd.Series,
) -> str:
    """Create a Markdown report containing quality and analysis results."""
    lines = []

    lines.append("# DataSage Baseline Report")
    lines.append("")
    lines.append(f"**Input:** `{input_path}`")
    lines.append("")
    lines.append("## Dataset Summary")
    lines.append("")
    lines.append(f"- Rows: {len(df)}")
    lines.append(f"- Columns: {len(df.columns)}")
    lines.append(f"- Column names: {', '.join(df.columns.astype(str))}")
    lines.append("")

    lines.append("## Data Quality Summary")
    lines.append("")

    if quality["missing_values"]:
        lines.append("### Missing Values")
        lines.append("")

        for column, count in quality["missing_values"].items():
            lines.append(f"- `{column}`: {count}")

        lines.append("")
    else:
        lines.append("- No missing values detected.")
        lines.append("")

    lines.append(
        f"- Duplicate rows: {quality['duplicate_rows']}"
    )

    if quality["negative_values"]:
        lines.append("- Negative numeric values:")
        for column, count in quality["negative_values"].items():
            lines.append(f"  - `{column}`: {count}")
    else:
        lines.append("- Negative numeric values: none detected.")

    lines.append("")

    if quality["invalid_dates"]:
        lines.append("### Invalid Dates")
        lines.append("")

        for column, details in quality["invalid_dates"].items():
            lines.append(
                f"- `{column}`: {details['count']} invalid value(s)"
            )
            lines.append(
                f"  - Values: {details['values']}"
            )

        lines.append("")
    else:
        lines.append("- Invalid dates: none detected.")
        lines.append("")

    if quality["inconsistent_categories"]:
        lines.append("### Inconsistent Categorical Labels")
        lines.append("")

        for column, conflicts in quality[
            "inconsistent_categories"
        ].items():
            lines.append(f"- `{column}`:")

            for normalized, values in conflicts.items():
                formatted_values = ", ".join(
                    f"`{value}`" for value in values
                )
                lines.append(
                    f"  - {formatted_values} "
                    f"normalize to `{normalized}`"
                )

        lines.append("")
    else:
        lines.append(
            "- No case-insensitive categorical inconsistencies detected."
        )
        lines.append("")

    lines.append("## Revenue by Category")
    lines.append("")
    lines.append("| Category | Revenue |")
    lines.append("|---|---:|")

    for category, revenue in revenue_by_category.items():
        lines.append(f"| {category} | ${revenue:,.2f} |")

    lines.append("")
    lines.append(
        "This baseline reports quality issues but does not "
        "automatically clean the input dataset."
    )
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="DataSage baseline for data quality and analysis."
    )

    parser.add_argument(
        "--input",
        required=True,
        help="Path to a CSV or XLSX dataset.",
    )

    parser.add_argument(
        "--analysis",
        choices=["revenue_by_category"],
        default="revenue_by_category",
        help="Analysis to run on the input dataset.",
    )

    parser.add_argument(
        "--output",
        default="outputs/baseline_report.md",
        help="Path for the generated Markdown report.",
    )

    args = parser.parse_args()

    df = load_dataset(args.input)

    print(f"Loaded dataset successfully: {args.input}")
    print(f"Rows: {len(df)}")
    print(f"Columns: {len(df.columns)}")
    print(f"Column names: {df.columns.tolist()}")

    quality = profile_quality(df)

    print("\nData Quality Summary")
    print("--------------------")
    print(f"Missing values: {quality['missing_values']}")
    print(f"Duplicate rows: {quality['duplicate_rows']}")
    print(f"Negative values: {quality['negative_values']}")
    print(f"Invalid dates: {quality['invalid_dates']}")
    print(
        f"Inconsistent categories: "
        f"{quality['inconsistent_categories']}"
    )

    if args.analysis == "revenue_by_category":
        revenue_by_category = analyze_revenue_by_category(df)

        print("\nRevenue by Category")
        print("-------------------")

        for category, revenue in revenue_by_category.items():
            print(f"{category}: ${revenue:,.2f}")

    else:
        raise ValueError(f"Unsupported analysis: {args.analysis}")

    report = build_report(
        input_path=args.input,
        df=df,
        quality=quality,
        revenue_by_category=revenue_by_category,
    )

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report, encoding="utf-8")

    print(f"\nReport written to: {output_path}")


if __name__ == "__main__":
    main()