"""Session state for one DataSage run.

The original table is kept read-only. Every fix creates a new version, so any change can be rolled
back and every cell in the final table can be traced to a logged change.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd

from .values import MISSING_TOKENS, plain_number


def load_table(path: str | Path) -> pd.DataFrame:
    """Load CSV or XLSX as text, mark missing tokens as NaN, and convert only fully numeric columns.

    The index is the 0-based row position in the source file and is kept through every change,
    so row ids in checks, fixes and reports always refer to the original rows.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        df = pd.read_csv(path, dtype=str, keep_default_na=False)
    elif suffix == ".xlsx":
        df = pd.read_excel(path, dtype=str, keep_default_na=False)
    else:
        raise ValueError(f"unsupported file type {suffix}; use .csv or .xlsx")

    df = df.apply(lambda col: col.map(lambda v: pd.NA if str(v).strip().lower() in MISSING_TOKENS else v))
    for column in df.columns:
        values = df[column].dropna()
        if len(values) and all(plain_number(v) is not None for v in values):
            df[column] = pd.to_numeric(df[column])
    df.index = pd.RangeIndex(len(df))
    return df


def load_rules(path: str | Path | None) -> dict:
    if not path:
        return {}
    return json.loads(Path(path).read_text())


@dataclass
class Change:
    version: int
    tool: str
    args: dict
    reason: str
    risk: str
    approval: str  # "auto" (low risk), "approved", or "rejected"
    rows_removed: list[int] = field(default_factory=list)
    cells_changed: int = 0
    summary: str = ""
    code: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class Session:
    def __init__(self, df: pd.DataFrame, source: str, request: str, rules: dict | None = None):
        self.source = source
        self.request = request
        self.rules = rules or {}
        self.original = df.copy()
        self.versions: list[pd.DataFrame] = [df.copy()]
        self.changes: list[Change] = []
        self.rejected: list[dict] = []
        self.issues: dict[tuple[str, str], dict] = {}
        self.analyses: list[dict] = []

    @property
    def current(self) -> pd.DataFrame:
        return self.versions[-1]

    @property
    def version(self) -> int:
        return len(self.versions) - 1

    def commit(self, new_df: pd.DataFrame, change: Change) -> None:
        self.versions.append(new_df.copy())
        self.changes.append(change)

    def rollback(self) -> None:
        if len(self.versions) > 1:
            self.versions.pop()
            self.changes.pop()

    def record_issue(self, issue_type: str, column: str, count: int, details: dict) -> None:
        if count > 0:
            self.issues[(issue_type, column)] = {"type": issue_type, "column": column, "count": count, **details}

    def summary(self) -> dict:
        """Compact state summary. Not yet sent to the model, which currently sees the chat history."""
        df = self.current
        return {
            "version": self.version,
            "rows": len(df),
            "changes": [f"v{c.version} {c.tool}({c.summary}) [{c.approval}]" for c in self.changes],
            "rejected_fixes": [r["tool"] for r in self.rejected],
            "open_issue_types": sorted({f"{t}:{c}" for t, c in self.issues}),
        }
