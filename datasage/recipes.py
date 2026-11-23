"""Cleaning recipes: the fixes approved in one DataSage run, saved so they can be replayed on a new file.

A recipe is a JSON file. It records the raw input the run cleaned and the rules file it used (by file
name and SHA-256, never a local path), the column schema of that raw input, and one step per fix with
the risk and approval it had in that run. Column types are recorded as "number" or "text", the two
kinds `load_table` produces.

This module only imports from datasage/; it never changes the agent, the tools or the fixes. Every call
into datasage/ goes through the adapter functions below (named `_ds_*`).
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import NamedTuple

import pandas as pd

from . import session as _ds_session

RECIPE_VERSION = 1


# Adapter: the only code in this module that calls datasage/. If a signature there changes, only these
# functions need to change.

def _ds_load_table(path: str | Path) -> pd.DataFrame:
    return _ds_session.load_table(path)


@dataclass
class Source:
    name: str     # file name of the table the run cleaned (no directory, so recipes can be shared)
    sha256: str
    rows: int


@dataclass
class Schema:
    columns: list[str]       # in file order
    dtypes: dict[str, str]   # column -> "number" or "text"
    fingerprint: str         # see schema_fingerprint


@dataclass
class RulesRef:
    name: str     # file name of the rules file (no directory)
    sha256: str


@dataclass
class Step:
    fix: str           # a name in datasage.fixes.FIXES, e.g. "normalize_labels"
    args: dict         # the fix's arguments without "reason"
    risk: str          # risk in the original run: "low", "medium" or "high"
    approved_by: str   # approval in the original run's change log: "auto" (low risk) or "approved"
    portable: bool     # True if the fix works on whole columns, so it can be replayed on a new file


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


@dataclass(kw_only=True)
class Recipe:
    recipe_version: int = RECIPE_VERSION
    created_at: str = field(default_factory=_now)
    source: Source
    schema: Schema
    rules: RulesRef | None = None   # None when the run had no rules file
    steps: list[Step] = field(default_factory=list)


def file_sha256(path: str | Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def column_kinds(df: pd.DataFrame) -> dict[str, str]:
    return {str(c): "number" if pd.api.types.is_numeric_dtype(df[c]) else "text" for c in df.columns}


def _fingerprint(dtypes: dict[str, str]) -> str:
    return hashlib.sha256(json.dumps(sorted(dtypes.items())).encode()).hexdigest()


def schema_fingerprint(df: pd.DataFrame) -> str:
    """SHA-256 of the column names and kinds. Column order does not change it."""
    return _fingerprint(column_kinds(df))


def schema_of(df: pd.DataFrame) -> Schema:
    kinds = column_kinds(df)
    return Schema(columns=list(kinds), dtypes=kinds, fingerprint=_fingerprint(kinds))


def describe_input(path: str | Path) -> tuple[Source, Schema]:
    """Source and schema of a raw input file, read with load_table exactly as a DataSage run reads it.

    Pass the original input, never a run's cleaned.csv: the schema must describe what the next raw
    file will look like before any fix runs.
    """
    path = Path(path)
    df = _ds_load_table(path)
    return Source(name=path.name, sha256=file_sha256(path), rows=len(df)), schema_of(df)


class SchemaCheck(NamedTuple):
    """How a new table's columns compare with the recipe's schema. Unpacks as (missing, extra, type_changed)."""

    missing: list[str]                        # recipe columns the table lacks: replay refuses
    extra: list[str]                          # table columns the recipe does not know: a warning
    type_changed: dict[str, tuple[str, str]]  # column -> (kind in the recipe, kind in the table): a warning

    @property
    def ok(self) -> bool:
        """True when replay may go ahead: every recipe column is present."""
        return not self.missing

    def warnings(self) -> list[str]:
        out = [f"extra column '{c}' is not in the recipe; it is left as it is" for c in self.extra]
        out += [f"column '{c}' was {old} in the recipe's input and is {new} here" for c, (old, new) in self.type_changed.items()]
        return out


def check_schema(recipe: Recipe, df: pd.DataFrame) -> SchemaCheck:
    """Compare a table (as read by load_table) with the recipe's schema. Column order does not matter."""
    kinds = column_kinds(df)
    expected = recipe.schema.dtypes
    missing = [c for c in recipe.schema.columns if c not in kinds]
    extra = [c for c in kinds if c not in expected]
    type_changed = {c: (expected[c], kinds[c]) for c in recipe.schema.columns if c in kinds and kinds[c] != expected[c]}
    return SchemaCheck(missing, extra, type_changed)


def rules_ref(path: str | Path | None) -> RulesRef | None:
    if not path:
        return None
    path = Path(path)
    return RulesRef(name=path.name, sha256=file_sha256(path))


def save_recipe(recipe: Recipe, path: str | Path) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(asdict(recipe), indent=2) + "\n")
    return path


def load_recipe(path: str | Path) -> Recipe:
    path = Path(path)
    data = json.loads(path.read_text())
    version = data.get("recipe_version") if isinstance(data, dict) else None
    if version != RECIPE_VERSION:
        raise ValueError(f"{path}: recipe_version {version!r} is not supported (expected {RECIPE_VERSION})")
    try:
        return Recipe(
            recipe_version=version,
            created_at=data["created_at"],
            source=Source(**data["source"]),
            schema=Schema(**data["schema"]),
            rules=RulesRef(**data["rules"]) if data["rules"] is not None else None,
            steps=[Step(**step) for step in data["steps"]],
        )
    except (KeyError, TypeError) as err:
        raise ValueError(f"{path} is not a valid recipe: {type(err).__name__}: {err}") from None
