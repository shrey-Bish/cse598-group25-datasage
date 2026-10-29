# Replays the DataSage cleaning steps without the agent.
import pandas as pd
df = pd.read_csv('baseline/examples/messy_sales.csv', dtype=str, keep_default_na=False)
df = df.replace({'': pd.NA, 'NA': pd.NA, 'N/A': pd.NA, 'n/a': pd.NA, 'null': pd.NA, 'None': pd.NA})
for col in df.columns:  # same rule as DataSage: convert only columns that are entirely plain numbers
    as_num = pd.to_numeric(df[col], errors='coerce')
    if as_num.notna().sum() == df[col].notna().sum():
        df[col] = as_num
# v1 drop_duplicates (approved): One exact duplicate row found (row 4), which can skew revenue totals. Removing duplicate.
df = df.drop_duplicates(keep='first')
# v2 normalize_labels (auto): Standardizing category labels to match allowed values in rules. Variants differ only by case, so low risk.
df['Category'] = df['Category'].replace({'electronics': 'Electronics', 'accessories': 'Accessories'})
# v3 parse_dates (approved): One invalid date 'not-a-date' (row 5) found. Setting invalid dates to missing to comply with rules. This row will still be included in revenue by category as Date is not used in the question.
df['Date'] = pd.to_datetime(df['Date'], format='%Y-%m-%d', errors='coerce').dt.strftime('%Y-%m-%d')
