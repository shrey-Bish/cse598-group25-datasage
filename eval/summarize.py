"""Aggregate per-task results into the results table (Markdown, CSV and JSON).

Usage: python -m eval.summarize
"""

from __future__ import annotations

import csv
import json
import statistics
from pathlib import Path

ROOT = Path(__file__).resolve().parent
RESULTS = ROOT / "results"
ORDER = ["b0", "b1", "b2", "datasage", "datasage-small", "datasage-reject", "datasage-novalidator",
         "datasage-fix", "datasage-fix-strict", "datasage-small-fix", "datasage-small-fix-strict"]
LABELS = {
    "b0": "B0 stakeholder baseline", "b1": "B1 fixed script", "b2": "B2 single LLM call",
    "datasage": "DataSage (235B)", "datasage-small": "DataSage (30B)",
    "datasage-reject": "DataSage, all risky fixes rejected", "datasage-novalidator": "DataSage, no validator",
    "datasage-fix": "DataSage (235B) + exclusion rule", "datasage-fix-strict": "DataSage (235B) + rule, strict approver",
    "datasage-small-fix": "DataSage (30B) + exclusion rule", "datasage-small-fix-strict": "DataSage (30B) + rule, strict approver",
}


def load(system: str, dataset: str) -> list[dict]:
    folder = RESULTS / system / dataset
    return [json.loads(p.read_text()) for p in sorted(folder.glob("*.json"))] if folder.exists() else []


def aggregate(rows: list[dict]) -> dict:
    n = len(rows)
    tp = sum(r["detect_tp"] for r in rows)
    fp = sum(r["detect_fp"] for r in rows)
    fn = sum(r["detect_fn"] for r in rows)
    cleaned = [r for r in rows if r.get("cleaned_available")]
    planted = sum(r["planted"] for r in cleaned)
    calls = sum(r["tool_calls"] for r in rows)
    errors = sum(r["tool_errors"] for r in rows)
    agent = calls > 0
    damage = [r["damaged_rows"] + r["damaged_cells"] for r in rows]
    return {
        "tasks": n,
        "analysis_accuracy": sum(r["analysis_correct"] for r in rows) / n,
        "completion": sum(r["completed"] for r in rows) / n,
        "detect_precision": tp / (tp + fp) if tp + fp else 0.0,
        "detect_recall": tp / (tp + fn) if tp + fn else 0.0,
        "correction_accuracy": sum(r["corrections"] for r in cleaned) / planted if planted else 0.0,
        "damaged_cells_rows": sum(damage),
        "tasks_with_damage": sum(d > 0 for d in damage) / n,
        "tool_call_success": (1 - errors / calls) if agent else None,
        "recovery": (sum(r["recovered_errors"] for r in rows) / errors) if errors else None,
        "approvals_median": statistics.median(r["approvals_asked"] for r in rows) if agent else None,
        "latency_median_s": statistics.median(r["seconds"] for r in rows),
        "tokens_median": statistics.median(r["tokens"] for r in rows),
    }


def fmt(value, kind: str) -> str:
    if value is None:
        return "n/a"
    if kind == "pct":
        return f"{100 * value:.0f}%"
    if kind == "f2":
        return f"{value:.2f}"
    if kind == "int":
        return f"{value:,.0f}"
    return f"{value:.1f}"


COLUMNS = [
    ("analysis_accuracy", "Answer correct", "pct"), ("completion", "Completed", "pct"),
    ("detect_precision", "Detect P", "f2"), ("detect_recall", "Detect R", "f2"),
    ("correction_accuracy", "Errors handled", "pct"), ("damaged_cells_rows", "Damage", "int"),
    ("tool_call_success", "Tool-call OK", "pct"), ("recovery", "Recovery", "pct"),
    ("approvals_median", "Approvals (med)", "f1"), ("latency_median_s", "Latency s (med)", "f1"),
    ("tokens_median", "Tokens (med)", "int"),
]


def main() -> None:
    table: dict = {}
    lines = []
    for dataset in ("sales", "penguins", "sales-heldout", "penguins-heldout"):
        if not any((RESULTS / system / dataset).exists() for system in ORDER):
            continue
        lines += [f"## {dataset}", "", "| System | n | " + " | ".join(c[1] for c in COLUMNS) + " |",
                  "|---|---:|" + "---:|" * len(COLUMNS)]
        for system in ORDER:
            rows = load(system, dataset)
            if not rows:
                continue
            agg = aggregate(rows)
            table.setdefault(dataset, {})[system] = agg
            lines.append(f"| {LABELS[system]} | {agg['tasks']} | " + " | ".join(fmt(agg[k], kind) for k, _, kind in COLUMNS) + " |")
        lines.append("")
    (RESULTS / "summary.md").write_text("\n".join(lines))
    (RESULTS / "summary.json").write_text(json.dumps(table, indent=2))
    with open(RESULTS / "summary.csv", "w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["dataset", "system"] + [k for k, _, _ in COLUMNS] + ["tasks"])
        for dataset, systems in table.items():
            for system, agg in systems.items():
                writer.writerow([dataset, system] + [agg[k] for k, _, _ in COLUMNS] + [agg["tasks"]])
    print("\n".join(lines))


if __name__ == "__main__":
    main()
