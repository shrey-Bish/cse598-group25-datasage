# Probe files

Small hand-made files with known problems, used to check what a system catches.

## hidden_issues.csv

Five rows with four planted problems:

| Row (Order_ID) | Planted problem | Caught by baseline (4b1df80)? |
|---|---|---|
| 2002 | `Category` has a trailing space: `"Electronics "` | No. Labels are stripped before comparing, so it is not flagged, but the analysis still reports it as a separate category. |
| 2003 | Invalid date `13/31/2026` in a column named `Day` | No. Only columns whose names contain "date" or "time" are checked. |
| 2003 | `Revenue` is 999 but `Quantity x Price` is 150 | No. There is no cross-column check. |
| 2005 | `Region` is `N/A` | Yes, pandas reads `N/A` as missing. |

Baseline revenue output on this file: Electronics $2,120, Accessories $1,599, `Electronics ` $125.
On the cleaned data it should be Electronics $2,245 and Accessories $750 (using Quantity x Price for row 2003).
