"""Session state for one DataSage run.

The original table is kept read-only. Every fix creates a new version, so any change can be rolled
back and every cell in the final table can be traced to a logged change.
"""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from pathlib import Path

import pandas as pd

from .values import MISSING_TOKENS, plain_number


ENCODINGS = ("utf-8-sig", "cp1252", "latin-1")  # latin-1 accepts any bytes, so it is the last resort
SEPARATORS = ",;\t|"


def detect_csv(path: str | Path) -> dict:
    """Text encoding and column separator of a CSV file, from its first 64 KB."""
    with open(path, "rb") as fh:
        raw = fh.read(65536)
    truncated = len(raw) == 65536
    encoding, text = "latin-1", raw.decode("latin-1")
    for enc in ENCODINGS:
        try:
            text = raw.decode(enc)
            encoding = enc
            break
        except UnicodeDecodeError as err:
            if enc == "utf-8-sig" and truncated and err.start >= len(raw) - 3:  # a character cut at the 64 KB boundary
                text, encoding = raw[:err.start].decode(enc), enc
                break
    lines = [ln for ln in text.splitlines()[:50] if ln.strip()]
    sep = ","
    if lines:
        try:
            sep = csv.Sniffer().sniff("\n".join(lines), delimiters=SEPARATORS).delimiter
        except csv.Error:
            counts = {s: lines[0].count(s) for s in SEPARATORS}
            sep = max(counts, key=counts.get) if max(counts.values()) else ","
        if sep != "," and lines[0].count(sep) == 0 and lines[0].count(",") > 0:
            sep = ","
    return {"encoding": encoding, "sep": sep}


def excel_sheets(path: str | Path) -> list[str]:
    with pd.ExcelFile(path) as book:
        return [str(s) for s in book.sheet_names]


def load_table(path: str | Path, sheet: str | int | None = None) -> pd.DataFrame:
    """Load CSV or XLSX as text, mark missing tokens as NaN, and convert only fully numeric columns.

    CSV: the encoding (UTF-8, Windows-1252 or Latin-1) and the separator (, ; tab |) are detected.
    XLSX: `sheet` picks a sheet by name or position (default: the first). How the file was read is kept
    in `df.attrs["read"]`, so the replay script can read it the same way.
    The index is the 0-based row position in the source file and is kept through every change,
    so row ids in checks, fixes and reports always refer to the original rows.
    """
    path = Path(path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        read = detect_csv(path)
        df = pd.read_csv(path, dtype=str, keep_default_na=False, sep=read["sep"], encoding=read["encoding"])
    elif suffix == ".xlsx":
        read = {"sheet": sheet if sheet is not None else 0}
        df = pd.read_excel(path, sheet_name=read["sheet"], dtype=str, keep_default_na=False)
    else:
        raise ValueError(f"unsupported file type {suffix}; use .csv or .xlsx")

    df = df.apply(lambda col: col.map(lambda v: pd.NA if str(v).strip().lower() in MISSING_TOKENS else v))
    for column in df.columns:
        values = df[column].dropna()
        if len(values) and all(plain_number(v) is not None for v in values):
            df[column] = pd.to_numeric(df[column])
    df.index = pd.RangeIndex(len(df))
    df.attrs["read"] = read
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
    cell_changes: list[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


class Session:
    def __init__(self, df: pd.DataFrame, source: str, request: str, rules: dict | None = None):
        self.source = source
        self.request = request
        self.rules = rules or {}
        self.read = dict(df.attrs.get("read", {}))  # how the file was read (separator, encoding, sheet)
        self.original = df.copy()
        self.versions: list[pd.DataFrame] = [df.copy()]
        self.changes: list[Change] = []
        self.rejected: list[dict] = []
        self.issues: dict[tuple[str, str], dict] = {}
        self.analyses: list[dict] = []
        self.checks_run: list[dict] = []  # {"tool", "column", "version", "by"}; by = "model" or "coverage"

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

    def checked(self, tool: str, column: str | None = None) -> bool:
        return any(c["tool"] == tool and (column is None or c["column"] == column) for c in self.checks_run)

    def summary(self) -> dict:
        """Compact state summary. In compact memory mode the model sees this instead of old tool results."""
        df = self.current
        latest: dict[str, str] = {}  # latest result of each distinct check call
        for c in self.checks_run:
            args = ", ".join(f"{k}={v}" for k, v in (c.get("args") or {}).items() if v is not None)
            latest[f"{c['tool']}({args})"] = f"on v{c['version']}: {c.get('found', '?')}"
        return {
            "current_version": self.version,
            "rows": len(df),
            "checks_done_latest_result": latest,
            "changes_applied": [f"v{c.version} {c.tool}: {c.summary} [{c.approval}]" for c in self.changes],
            "rejected_fixes_do_not_retry": [f"{r['tool']}: {r['summary']}" for r in self.rejected],
            "analyses": [{k: a.get(k) for k in ("group_by", "metric", "agg", "rows_used", "result")} for a in self.analyses],
        }
