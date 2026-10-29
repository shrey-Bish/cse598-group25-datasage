"""Load benchmark tables and score one system output against the planted errors and reference."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from datasage.analyze import answers_match
from datasage.values import comparable, is_missing

ROOT = Path(__file__).resolve().parent


def id_key(value) -> str:
    v = comparable(value)
    if isinstance(v, float) and v.is_integer():
        return str(int(v))
    return str(v)


@dataclass
class Bundle:
    folder: Path
    messy_path: Path
    rules_path: Path
    id_col: str
    planted: list[dict]
    reference: pd.DataFrame
    tasks: list[dict]

    @property
    def truth_issues(self) -> set[tuple[str, str]]:
        return {(p["type"], p["column"]) for p in self.planted}

    @property
    def planted_cells(self) -> set[tuple[str, str]]:
        return {(p["id"], p["column"]) for p in self.planted if p["column"] != "*"}


def load_bundle(folder: str | Path) -> Bundle:
    folder = Path(folder)
    planted = json.loads((folder / "planted.json").read_text())
    reference = pd.read_csv(folder / "reference.csv", dtype=str, keep_default_na=False).replace({"": pd.NA})
    return Bundle(folder, folder / "messy.csv", folder / "rules.json", planted["id_column"], planted["errors"],
                  reference, json.loads((folder / "tasks.json").read_text()))


def all_bundles(dataset: str) -> list[Bundle]:
    return [load_bundle(p) for p in sorted((ROOT / "datasets" / dataset).iterdir()) if p.is_dir()]


def _by_id(df: pd.DataFrame, id_col: str) -> dict[str, list[dict]]:
    out: dict[str, list[dict]] = {}
    for _, row in df.iterrows():
        out.setdefault(id_key(row[id_col]), []).append(row.to_dict())
    return out


@dataclass
class SystemOutput:
    answer: dict | None
    cleaned: pd.DataFrame | None
    issues: set[tuple[str, str]] = field(default_factory=set)
    completed: bool = True
    tool_calls: int = 0
    tool_errors: int = 0
    recovered_errors: int = 0
    approvals_asked: int = 0
    seconds: float = 0.0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    stop_reason: str = ""
    note: str = ""
    extra: dict = field(default_factory=dict)


def score(bundle: Bundle, task: dict, out: SystemOutput) -> dict:
    truth = bundle.truth_issues
    reported = {(t, c) for t, c in out.issues}
    tp = len(reported & truth)
    result = {
        "task_id": task["task_id"],
        "analysis_correct": bool(out.completed and answers_match(out.answer, task["reference_answer"])),
        "completed": bool(out.completed and out.answer is not None),
        "detect_tp": tp, "detect_fp": len(reported - truth), "detect_fn": len(truth - reported),
        "tool_calls": out.tool_calls, "tool_errors": out.tool_errors, "recovered_errors": out.recovered_errors,
        "approvals_asked": out.approvals_asked, "seconds": out.seconds,
        "tokens": out.prompt_tokens + out.completion_tokens, "stop_reason": out.stop_reason, "note": out.note,
        "answer": out.answer, "extra": out.extra,
    }

    planted_total = len(bundle.planted)
    if out.cleaned is None:
        result.update(corrections=0, planted=planted_total, damaged_rows=0, damaged_cells=0, cleaned_available=False)
        return result

    got = _by_id(out.cleaned, bundle.id_col)
    ref = _by_id(bundle.reference, bundle.id_col)
    correct = 0
    for p in bundle.planted:
        rows = got.get(p["id"], [])
        res = p["resolution"]
        if res == "drop_copy":
            ok = len(rows) == 1
        elif res == "exclude":
            ok = len(rows) == 0
        elif res == "restore":
            ok = bool(rows) and comparable(rows[0].get(p["column"])) == comparable(p["clean_value"])
        else:  # set_missing / keep_missing
            ok = bool(rows) and is_missing(rows[0].get(p["column"]))
        correct += ok

    damaged_rows = damaged_cells = 0
    planted_cells = bundle.planted_cells
    shared_cols = [c for c in bundle.reference.columns if c in out.cleaned.columns]
    for key, ref_rows in ref.items():
        rows = got.get(key)
        if not rows:
            damaged_rows += 1
            continue
        for col in shared_cols:
            if (key, col) in planted_cells:
                continue
            if comparable(rows[0].get(col)) != comparable(ref_rows[0].get(col)):
                damaged_cells += 1
    result.update(corrections=correct, planted=planted_total, damaged_rows=damaged_rows,
                  damaged_cells=damaged_cells, cleaned_available=True)
    return result
