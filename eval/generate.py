"""Build the planted-error benchmark.

For each table we keep the clean version, plant known errors, and record for every planted error
what correct handling looks like (restore, exclude, set missing, keep missing, or drop the copy).
The reference table applies that handling to the clean table, and reference answers are computed on
it with the same analysis function every system uses.

Usage: python -m eval.generate --tables 10 --seed 7
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path

import pandas as pd

from datasage.analyze import run_analysis

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "datasets"

CATALOG = {
    "Electronics": {"Laptop": 900, "Monitor": 300, "Headset": 80, "Webcam": 60, "Tablet": 450},
    "Accessories": {"Mouse": 25, "Keyboard": 50, "Hub": 40, "Cable": 15},
    "Furniture": {"Desk": 350, "Chair": 180, "Lamp": 45},
    "Office Supplies": {"Notebook": 6, "Pen Pack": 12, "Stapler": 18},
}
REGIONS = ["North", "South", "East", "West"]
TYPOS = {
    "Electronics": "Electornics", "Accessories": "Accesories", "Furniture": "Furnture",
    "Office Supplies": "Office Suplies", "North": "Nort", "South": "Suoth", "East": "Eats", "West": "Wst",
    "Adelie": "Adeile", "Gentoo": "Gentto", "Chinstrap": "Chinstarp",
    "Biscoe": "Bisco", "Dream": "Dram", "Torgersen": "Torgerson",
}
BAD_DATES = ["not-a-date", "2026-02-30", "13/45/2026", "TBD", "2026-14-01"]

SALES_TASKS = [
    ("What is the total revenue by category?", {"group_by": ["Category"], "metric": "Revenue", "agg": "sum"}),
    ("How many units were sold in each region?", {"group_by": ["Region"], "metric": "Quantity", "agg": "sum"}),
    ("What is the total revenue per month?", {"group_by": ["Date:month"], "metric": "Revenue", "agg": "sum"}),
    ("What is the average unit price in each category?", {"group_by": ["Category"], "metric": "Price", "agg": "mean"}),
    ("What is the total revenue by region for Electronics?",
     {"group_by": ["Region"], "metric": "Revenue", "agg": "sum", "filters": [{"column": "Category", "value": "Electronics"}]}),
    ("How many orders are there in each category?", {"group_by": ["Category"], "metric": None, "agg": "count"}),
]
PENGUIN_TASKS = [
    ("What is the average body mass for each species?", {"group_by": ["species"], "metric": "body_mass_g", "agg": "mean"}),
    ("How many penguins were measured on each island?", {"group_by": ["island"], "metric": None, "agg": "count"}),
    ("What is the average flipper length for each species?", {"group_by": ["species"], "metric": "flipper_length_mm", "agg": "mean"}),
    ("What is the average body mass for each sex?", {"group_by": ["sex"], "metric": "body_mass_g", "agg": "mean"}),
    ("What is the average bill length by island for Adelie penguins?",
     {"group_by": ["island"], "metric": "bill_length_mm", "agg": "mean", "filters": [{"column": "species", "value": "Adelie"}]}),
    ("What is the total body mass for each species?", {"group_by": ["species"], "metric": "body_mass_g", "agg": "sum"}),
]

SALES_RULES = {
    "Order_ID": "unique order number",
    "Date": {"format": "YYYY-MM-DD"},
    "Category": {"allowed": list(CATALOG)},
    "Region": {"allowed": REGIONS},
    "Quantity": {"min": 1, "note": "units sold; always a positive whole number"},
    "Price": {"min": 0, "note": "unit price in dollars"},
    "Revenue": {"formula": "Revenue = Quantity * Price"},
}
PENGUIN_RULES = {
    "penguin_id": "unique id",
    "species": {"allowed": ["Adelie", "Chinstrap", "Gentoo"]},
    "island": {"allowed": ["Biscoe", "Dream", "Torgersen"]},
    "sex": {"allowed": ["male", "female"], "note": "missing means unknown; do not guess"},
    "bill_length_mm": {"min": 30, "max": 60},
    "flipper_length_mm": {"min": 170, "max": 235},
    "body_mass_g": {"min": 2500, "max": 6500, "unit": "grams"},
}


def clean_sales(rng: random.Random, n: int) -> pd.DataFrame:
    rows = []
    for i in range(n):
        category = rng.choice(list(CATALOG))
        product, price = rng.choice(list(CATALOG[category].items()))
        qty = rng.randint(1, 8)
        rows.append({
            "Order_ID": 2001 + i,
            "Date": f"2026-{rng.randint(1, 6):02d}-{rng.randint(1, 28):02d}",
            "Product": product, "Category": category, "Quantity": qty, "Price": price,
            "Region": rng.choice(REGIONS), "Revenue": qty * price,
        })
    return pd.DataFrame(rows)


def clean_penguins(rng: random.Random, n: int) -> pd.DataFrame:
    source = pd.read_csv(ROOT / "sources" / "penguins.csv").dropna().reset_index(drop=True)
    pick = sorted(rng.sample(range(len(source)), n))
    df = source.loc[pick].reset_index(drop=True)
    df["body_mass_g"] = df["body_mass_g"].astype(int)
    df["flipper_length_mm"] = df["flipper_length_mm"].astype(int)
    df.insert(0, "penguin_id", [f"P{rng.randint(10000, 99999)}{i:02d}" for i in range(len(df))])
    return df


def plant(rng: random.Random, clean: pd.DataFrame, kind: str) -> tuple[pd.DataFrame, list[dict]]:
    """Return the messy table (all text) and the list of planted errors."""
    id_col = "Order_ID" if kind == "sales" else "penguin_id"
    messy = clean.astype(object).copy()
    planted: list[dict] = []
    label_cols = ["Category", "Region"] if kind == "sales" else ["species", "island", "sex"]
    if kind == "sales":
        options = ["duplicates", "label_case", "label_space", "label_typo", "invalid_date", "text_number",
                   "negative", "cross_column", "missing"]
    else:
        options = ["duplicates", "label_case", "label_space", "label_typo", "text_number", "negative",
                   "out_of_range", "missing"]
    chosen = rng.sample(options, rng.randint(4, 6))
    used: set[int] = set()

    def rows(k: int) -> list[int]:
        free = [i for i in range(len(clean)) if i not in used]
        pick = rng.sample(free, k)
        used.update(pick)
        return pick

    def add(kind_: str, column: str, i: int, resolution: str, clean_value, messy_value, subtype=None):
        planted.append({"type": kind_, "subtype": subtype or kind_, "column": column, "id": str(clean.at[i, id_col]),
                        "resolution": resolution, "clean_value": clean_value, "messy_value": messy_value})

    for error in chosen:
        k = rng.randint(1, 3)
        if error in ("label_case", "label_space", "label_typo"):
            column = rng.choice(label_cols)
            for i in rows(k):
                value = str(clean.at[i, column])
                if error == "label_case":
                    new = value.lower() if value != value.lower() else value.upper()
                elif error == "label_space":
                    new = value + " " if rng.random() < 0.5 else " " + value
                else:
                    if value not in TYPOS:
                        continue
                    new = TYPOS[value]
                messy.at[i, column] = new
                add("label_variant", column, i, "restore", value, new, subtype=error)
        elif error == "invalid_date":
            for i in rows(k):
                new = rng.choice(BAD_DATES)
                add("invalid_date", "Date", i, "set_missing", clean.at[i, "Date"], new)
                messy.at[i, "Date"] = new
        elif error == "text_number":
            column = "Price" if kind == "sales" else "body_mass_g"
            for i in rows(k):
                value = clean.at[i, column]
                new = f"${value:,.2f}" if kind == "sales" else f"{int(value):,}"
                if kind == "penguins" and "," not in new:
                    new = f"{int(value):,} g".replace(" g", "")
                messy.at[i, column] = new
                add("text_number", column, i, "restore", float(value), new)
        elif error == "negative":
            column = "Quantity" if kind == "sales" else "flipper_length_mm"
            for i in rows(k):
                messy.at[i, column] = -clean.at[i, column]
                if kind == "sales":
                    messy.at[i, "Revenue"] = -clean.at[i, "Revenue"]
                add("negative", column, i, "exclude", float(clean.at[i, column]), float(messy.at[i, column]))
        elif error == "out_of_range":
            for i in rows(k):
                messy.at[i, "body_mass_g"] = int(clean.at[i, "body_mass_g"]) * 1000
                add("out_of_range", "body_mass_g", i, "exclude", float(clean.at[i, "body_mass_g"]), float(messy.at[i, "body_mass_g"]))
        elif error == "cross_column":
            for i in rows(k):
                wrong = clean.at[i, "Revenue"] * rng.choice([10, 100]) + rng.choice([0, 5])
                messy.at[i, "Revenue"] = wrong
                add("cross_column", "Revenue", i, "restore", float(clean.at[i, "Revenue"]), float(wrong))
        elif error == "missing":
            column = "Region" if kind == "sales" else "sex"
            for i in rows(k):
                add("missing", column, i, "keep_missing", None, "")
                messy.at[i, column] = ""

    if "duplicates" in chosen:
        copies = [i for i in rows(rng.randint(1, 2))]
        parts, cursor = [], 0
        for i in sorted(copies):
            parts.append(messy.iloc[cursor:i + 1])
            parts.append(messy.iloc[[i]])
            cursor = i + 1
            add("duplicates", "*", i, "drop_copy", None, None)
        parts.append(messy.iloc[cursor:])
        messy = pd.concat(parts, ignore_index=True)
    return messy.reset_index(drop=True), planted


def reference_table(clean: pd.DataFrame, planted: list[dict], id_col: str) -> pd.DataFrame:
    ref = clean.copy()
    ref[id_col] = ref[id_col].astype(str)
    ref = ref.astype(object)
    exclude = {p["id"] for p in planted if p["resolution"] == "exclude"}
    for p in planted:
        if p["resolution"] in ("set_missing", "keep_missing"):
            ref.loc[ref[id_col] == p["id"], p["column"]] = pd.NA
    ref = ref[~ref[id_col].isin(exclude)].reset_index(drop=True)
    for col in ref.columns:
        converted = pd.to_numeric(ref[col], errors="coerce")
        if converted.notna().sum() == ref[col].notna().sum() and col != id_col:
            ref[col] = converted
    return ref


def pick_tasks(rng: random.Random, kind: str, planted: list[dict]) -> list[tuple[str, dict]]:
    """Two questions per table, preferring ones whose columns contain planted errors."""
    pool = SALES_TASKS if kind == "sales" else PENGUIN_TASKS
    error_cols = {p["column"] for p in planted} | ({"*"} if any(p["type"] == "duplicates" for p in planted) else set())

    def touches(spec):
        cols = {g.split(":")[0] for g in spec["group_by"]} | {spec["metric"]} | {f["column"] for f in spec.get("filters", [])}
        return bool(cols & error_cols) or "*" in error_cols

    preferred = [t for t in pool if touches(t[1])]
    rng.shuffle(preferred)
    rest = [t for t in pool if t not in preferred]
    rng.shuffle(rest)
    return (preferred + rest)[:2]


def build(kind: str, tables: int, seed: int, split: str = "") -> int:
    rng = random.Random(f"{kind}-{seed}")
    name = f"{kind}{split[:1]}" if split else kind  # held-out tables get ids like salesh_00
    id_col = "Order_ID" if kind == "sales" else "penguin_id"
    rules = SALES_RULES if kind == "sales" else PENGUIN_RULES
    count = 0
    for t in range(tables):
        clean = clean_sales(rng, rng.randint(40, 70)) if kind == "sales" else clean_penguins(rng, rng.randint(40, 70))
        messy, planted = plant(rng, clean, kind)
        ref = reference_table(clean, planted, id_col)
        folder = OUT / (f"{kind}-{split}" if split else kind) / f"{name}_{t:02d}"
        folder.mkdir(parents=True, exist_ok=True)
        messy.to_csv(folder / "messy.csv", index=False)
        clean.to_csv(folder / "clean.csv", index=False)
        ref.to_csv(folder / "reference.csv", index=False)
        (folder / "rules.json").write_text(json.dumps(rules, indent=2))
        (folder / "planted.json").write_text(json.dumps({"id_column": id_col, "errors": planted}, indent=2, default=str))
        tasks = []
        for j, (question, spec) in enumerate(pick_tasks(rng, kind, planted)):
            answer = run_analysis(ref, spec["group_by"], spec["metric"], spec["agg"], spec.get("filters"))["result"]
            tasks.append({"task_id": f"{name}_{t:02d}_q{j}", "question": question, "spec": spec, "reference_answer": answer})
            count += 1
        (folder / "tasks.json").write_text(json.dumps(tasks, indent=2))
    return count


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tables", type=int, default=10)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--split", default="", help="e.g. heldout: writes datasets/<kind>-heldout")
    args = parser.parse_args()
    for kind in ("sales", "penguins"):
        n = build(kind, args.tables, args.seed, args.split)
        print(f"{kind}: {args.tables} tables, {n} tasks -> {OUT / (f'{kind}-{args.split}' if args.split else kind)}")


if __name__ == "__main__":
    main()
