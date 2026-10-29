"""Classify why DataSage got a task wrong, from its trace and the planted errors.

Usage: python -m eval.failures --system datasage
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CHECK_FOR = {
    "duplicates": {"check_duplicates"},
    "label_variant": {"check_label_variants"},
    "invalid_date": {"check_dates"},
    "text_number": {"check_numeric"},
    "negative": {"check_numeric", "check_out_of_range"},
    "out_of_range": {"check_out_of_range"},
    "cross_column": {"check_cross_column"},
    "missing": {"check_missing"},
}


def _on_column(args, column: str) -> bool:
    if column == "*" or not isinstance(args, dict) or "column" not in args:
        return True
    return args["column"] == column


def diagnose(result: dict, trace: list[dict], planted: list[dict]) -> list[str]:
    calls = [e for e in trace if e.get("event") == "tool"]
    names = [e["name"] for e in calls]
    fixed = [e for e in calls if e["ok"] and isinstance(e["output"], dict) and e["output"].get("applied")]
    reasons = []
    exclude_rows_planted = [p for p in planted if p["resolution"] == "exclude"]
    if exclude_rows_planted:
        if any(e["name"] == "set_missing" for e in fixed) and not any(e["name"] == "exclude_rows" for e in fixed):
            reasons.append("rule-violating rows blanked with set_missing instead of excluded")
        elif not any(e["name"] in ("exclude_rows", "set_missing") for e in fixed):
            reasons.append("rule-violating rows left in the table")
    for p in planted:
        needed = CHECK_FOR[p["type"]]
        if not needed & set(names):
            reasons.append(f"never ran a check for {p['type']}")
        elif not any(e["name"] in needed and _on_column(e["args"], p["column"]) for e in calls):
            reasons.append(f"checked {p['type']} on other columns but not the one with the error")
    if "lookup_rules" not in names:
        reasons.append("did not read the rules file")
    if any(e["name"] == "fill_missing" for e in fixed):
        reasons.append("filled missing values")
    if result["stop_reason"] != "finish":
        reasons.append(f"stopped early: {result['stop_reason']}")
    return list(dict.fromkeys(reasons)) or ["other (see trace)"]


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--system", default="datasage")
    args = parser.parse_args()
    counts: Counter = Counter()
    rows = []
    for path in sorted((ROOT / "results" / args.system).glob("*/*.json")):
        result = json.loads(path.read_text())
        if result["analysis_correct"]:
            continue
        dataset = path.parent.name
        table = result["task_id"].rsplit("_", 1)[0]
        planted = json.loads((ROOT / "datasets" / dataset / table / "planted.json").read_text())["errors"]
        trace_path = path.parent / "traces" / f"{result['task_id']}.jsonl"
        trace = [json.loads(line) for line in trace_path.read_text().splitlines()] if trace_path.exists() else []
        reasons = diagnose(result, trace, planted)
        counts.update(reasons)
        rows.append((result["task_id"], reasons))
    for task, reasons in rows:
        print(f"{task}: {'; '.join(reasons)}")
    print("\nCounts:")
    for reason, n in counts.most_common():
        print(f"  {n:2d}  {reason}")
    out = ROOT / "results" / f"failures_{args.system}.json"
    out.write_text(json.dumps({"tasks": rows, "counts": counts.most_common()}, indent=2))


if __name__ == "__main__":
    main()
