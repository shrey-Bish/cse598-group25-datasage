"""Approval oracle used in automated runs, standing in for the user.

It approves a risky fix only if every removed row and every changed cell moves the data toward the
reference table (rows that should be excluded, duplicate copies, cells restored to their correct
value). Anything else, such as guessing missing values or merging two real labels, is rejected.
"""

from __future__ import annotations

from datasage.approval import Approver
from datasage.values import comparable

from .scoring import Bundle, id_key


class OracleApprover(Approver):
    name = "oracle"

    def __init__(self, bundle: Bundle, strict_exclusion: bool = False):
        # strict_exclusion: also reject edits to rows that should be excluded (a user whose policy is
        # "drop rows that break a rule" would refuse to keep them with one cell blanked).
        self.strict_exclusion = strict_exclusion
        self.id_col = bundle.id_col
        self.exclude = {p["id"] for p in bundle.planted if p["resolution"] == "exclude"}
        self.reference = {id_key(r[self.id_col]): r for _, r in bundle.reference.iterrows()}
        self.decisions: list[dict] = []

    def decide(self, tool, args, risk, preview):
        before, after = preview["before"], preview["after"]
        ok, why = self._judge(before, after)
        self.decisions.append({"tool": tool, "risk": risk, "approved": ok, "why": why})
        return ok

    def _judge(self, before, after) -> tuple[bool, str]:
        removed = before.index.difference(after.index)
        kept_ids = {id_key(v) for v in after[self.id_col]}
        for row in removed:
            key = id_key(before.at[row, self.id_col])
            if key in self.exclude:
                continue
            if key in kept_ids:  # a duplicate copy whose original is still present
                continue
            return False, f"removes row {row} (id {key}) that should be kept"
        common = after.index.intersection(before.index)
        for col in after.columns:
            for row in common:
                old, new = comparable(before.at[row, col]), comparable(after.at[row, col])
                if old == new:
                    continue
                key = id_key(before.at[row, self.id_col])
                if key in self.exclude and self.strict_exclusion:
                    return False, f"edits row {row} (id {key}), which should be excluded instead"
                if key in self.exclude or key not in self.reference:
                    continue
                if new != comparable(self.reference[key].get(col)):
                    return False, f"changes row {row} column {col} to {new!r}, expected {self.reference[key].get(col)!r}"
        return True, "moves data toward the reference"
