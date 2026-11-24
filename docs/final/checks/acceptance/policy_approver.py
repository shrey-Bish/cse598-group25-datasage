"""Policy approver for the A1/A2 runs: decides each risky DataSage fix from a fixed policy and logs the decision.

The policy is written out in decision_policy.md next to this file. It uses only the stakeholder's business rules
(P and S cases; the lines it cites as "business_rules.md:<line>" are quoted in decision_policy.md) and each test
table's rules.json (T and H cases). Anything the policy does not cover is rejected and logged as "not covered".

It plugs into DataSage through its existing approver interface (datasage/approval.py):

    class Approver:
        def decide(self, tool: str, args: dict, risk: str, preview: dict) -> bool

and runs the agent the way `python -m datasage` does (datasage/__main__.py: run_agent(...) then write_outputs(...)),
with this approver in place of AskApprover. Nothing in datasage/ is changed.

From the repo root (needs the model key, like `python -m datasage`; -X utf8 matters on Windows):
    python -X utf8 docs/final/checks/acceptance/policy_approver.py --case P1 --profile procurement \\
        --input docs/final/checks/acceptance/procurement_ledger/input.csv \\
        --rules docs/final/checks/acceptance/procurement_ledger/rules.json \\
        --request "What is the total procurement spend by department?" --out outputs/acceptance/P1
Profiles: procurement (P), support (S), sales_table (sales tables), penguins_table (penguin tables).
Writes DataSage's usual outputs plus decisions.jsonl (every approval decision) and result.json to --out.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]  # docs/final/checks/acceptance/ -> repo root
sys.path.insert(0, str(REPO))

import pandas as pd  # noqa: E402

from datasage.agent import DEFAULT_MODEL, run_agent  # noqa: E402
from datasage.approval import Approver  # noqa: E402
from datasage.checks import evaluate_expression  # noqa: E402
from datasage.report import write_outputs  # noqa: E402
from datasage.rules import allows_negative_quantities, outside_range  # noqa: E402
from datasage.values import is_missing, iso_date, loose_number, normalize_label  # noqa: E402

NOT_COVERED = "not covered"
BR = "business_rules.md"
OCT28 = "Oct 28 decision: blank unreadable values (M2 report Table 1 row 7)"
_PLAIN_NUMBER = re.compile(r"^[-+]?\d+(\.\d+)?$")

# What each source says, by policy topic. P and S cite business_rules.md lines; T and H cite their rules.json.
PROFILES = {
    "procurement": {
        "named_misspellings": {"Department": {"finanace": "Finance"}},
        "cite": {"labels": f"{BR}:9-11,15", "misspelling": f"{BR}:15", "duplicates": f"{BR}:17", "range": f"{BR}:12",
                 "formula": f"{BR}:13", "unreadable": f"{OCT28}; {BR}:29"},
    },
    "support": {
        "named_misspellings": {"Team": {"operatons": "Operations"}},
        "missing_tokens": {"OpenedDate": {"not-recorded"}},
        "unknown_label_to_missing": {"Channel"},
        "never_fill": True,
        "cite": {"labels": f"{BR}:22-24,27", "misspelling": f"{BR}:27", "duplicates": f"{BR}:28", "range": f"{BR}:25",
                 "missing_date": f"{BR}:26", "unknown_channel": f"{BR}:24,29-30; {OCT28}", "no_guess": f"{BR}:29",
                 "unreadable": f"{OCT28}; {BR}:29"},
    },
    "sales_table": {
        "fuzzy_labels": True,
        "cite": {"labels": "rules.json allowed", "misspelling": "rules.json allowed + policy 2c (nearest label, <= 2 edits)",
                 "duplicates": "rules.json Order_ID 'unique order number'", "range": "rules.json min/max",
                 "formula": "rules.json Revenue formula", "unreadable": OCT28},
    },
    "penguins_table": {
        "fuzzy_labels": True,
        "never_fill": True,
        "cite": {"labels": "rules.json allowed", "misspelling": "rules.json allowed + policy 2c (nearest label, <= 2 edits)",
                 "duplicates": "rules.json penguin_id 'unique id'", "range": "rules.json min/max",
                 "no_guess": "rules.json sex note 'missing means unknown; do not guess'", "unreadable": OCT28},
    },
}


def edit_distance(a: str, b: str) -> int:
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def _squash(text: str) -> str:
    return re.sub(r"\s+", "", str(text))


def _show(value) -> str:
    return repr(value) if isinstance(value, str) else str(_jsonable(value) if hasattr(value, "item") else value)


def _jsonable(value):
    if hasattr(value, "item"):
        return value.item()
    return str(value)


class PolicyApprover(Approver):
    name = "policy"

    def __init__(self, case: str, profile: str, rules_path: str | Path, log_path: Path):
        self.case = case
        self.profile = PROFILES[profile]
        self.rules = json.loads(Path(rules_path).read_text(encoding="utf-8"))
        self.log_path = log_path

    # ---- what the rules say ------------------------------------------------------------------------------------
    def cite(self, topic: str) -> str:
        return self.profile["cite"].get(topic, NOT_COVERED)

    def allowed(self, column: str) -> list[str]:
        spec = self.rules.get(column)
        return list(spec.get("allowed", [])) if isinstance(spec, dict) else []

    def ranges(self) -> dict[str, tuple]:
        return {col: (spec.get("min"), spec.get("max")) for col, spec in self.rules.items()
                if isinstance(spec, dict) and ("min" in spec or "max" in spec)}

    def formula(self) -> tuple[str, str] | None:
        for spec in self.rules.values():
            if isinstance(spec, dict) and "formula" in spec:
                target, rhs = (part.strip() for part in spec["formula"].split("=", 1))
                return target, rhs
        return None

    def out_of_range(self, col: str, value: float) -> bool:
        """DataSage's own range test (datasage/rules.py), so allow_negative_quantities keeps refunds in range."""
        lo, hi = self.ranges().get(col, (None, None))
        refunds = allows_negative_quantities(self.rules, col)
        return bool(outside_range(pd.Series([value]), lo, hi, allow_negative_quantities=refunds).iloc[0])

    def range_broken(self, row) -> str | None:
        """Description of the first value outside its rules range, or None."""
        for col, (lo, hi) in self.ranges().items():
            if col in row.index:
                v = loose_number(row[col])
                if v is not None and self.out_of_range(col, v):
                    return f"{col}={_show(row[col])} outside [{lo}, {hi}]"
        return None

    def near_allowed(self, value: str, column: str) -> list[str]:
        v = normalize_label(value)
        return [a for a in self.allowed(column) if edit_distance(v, normalize_label(a)) <= 2]

    def nearest_allowed(self, value: str, column: str) -> str | None:
        """The allowed label at most 2 edits away and strictly closer than every other allowed label, else None."""
        v = normalize_label(value)
        dist = sorted((edit_distance(v, normalize_label(a)), a) for a in self.allowed(column))
        if not dist or dist[0][0] > 2 or (len(dist) > 1 and dist[1][0] == dist[0][0]):
            return None
        return dist[0][1]

    def column_kind(self, col: str) -> str | None:
        """What the rules say a column holds: 'date' (format), 'label' (allowed) or 'number' (range or formula)."""
        spec = self.rules.get(col)
        if isinstance(spec, dict) and "format" in spec:
            return "date"
        if isinstance(spec, dict) and "allowed" in spec:
            return "label"
        if col in self.ranges():
            return "number"
        formula = self.formula()
        if formula and (col == formula[0] or col in re.findall(r"[A-Za-z_][A-Za-z_0-9]*", formula[1])):
            return "number"
        return None

    def unreadable(self, col: str, kind: str, value) -> bool:
        """Change 2: a cell DataSage may blank. Already-missing cells are not 'unreadable' (nothing to blank)."""
        if is_missing(value):
            return False
        if kind == "number":
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                return False
            return not _PLAIN_NUMBER.match(str(value).strip().replace("$", "").replace(",", ""))
        if kind == "date":
            for order in (None, "dmy", "mdy"):
                try:
                    if iso_date(value, order) is not None:
                        return False
                except ValueError:
                    pass
            return True
        if kind == "label":
            allowed = {normalize_label(a) for a in self.allowed(col)}
            return normalize_label(value) not in allowed and not self.near_allowed(str(value), col)
        return False

    # ---- the interface DataSage calls --------------------------------------------------------------------------
    def decide(self, tool: str, args: dict, risk: str, preview: dict) -> bool:
        handler = getattr(self, f"_{tool}", None)
        if handler is None:
            ok, rule, why = False, NOT_COVERED, f"no policy row for {tool}"
        else:
            try:
                ok, rule, why = handler(args, preview, preview["before"])
            except Exception as err:  # a policy check that cannot be evaluated is not covered
                ok, rule, why = False, NOT_COVERED, f"policy check failed: {err}"
        rows = preview.get("rows_removed") or args.get("rows") or []
        entry = {"case": self.case, "tool": tool, "risk": risk, "column": args.get("column"),
                 "rows": [int(r) for r in rows], "cells_changed": int(preview.get("cells_changed") or 0),
                 "summary": preview.get("summary", ""), "decision": "approved" if ok else "rejected",
                 "rule": rule, "why": why, "args": {k: v for k, v in args.items() if k != "reason"},
                 "agent_reason": args.get("reason", "")}
        with self.log_path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, default=_jsonable) + "\n")
        print(f"    [approval] {tool} ({risk} risk): {entry['summary']} -> {'APPROVED' if ok else 'REJECTED'} "
              f"[{rule}] {why}", flush=True)
        return ok

    # ---- one method per fix tool that can reach the approver (datasage/fixes.py risk_of) ----------------------
    def _normalize_labels(self, args, preview, before):
        col = args["column"]
        allowed = self.allowed(col)
        if not allowed:
            return False, NOT_COVERED, f"{col} has no allowed list in the rules"
        named = self.profile.get("named_misspellings", {}).get(col, {})
        used = set()
        for src, dst in args["mapping"].items():
            if dst not in allowed:
                return False, self.cite("labels"), f"{dst!r} is not an allowed {col} label"
            if normalize_label(src) == normalize_label(dst):
                used.add("labels")
                continue
            if named.get(normalize_label(src)) == dst:
                used.add("misspelling")
                continue
            if self.profile.get("fuzzy_labels") and src not in allowed and self.nearest_allowed(src, col) == dst:
                used.add("misspelling")
                continue
            return False, NOT_COVERED, f"{src!r} -> {dst!r} is not a case/space variant or a misspelling the policy covers"
        return True, "; ".join(self.cite(t) for t in sorted(used)), f"every pair maps to an allowed {col} label"

    def _drop_duplicates(self, args, preview, before):
        removed = preview.get("rows_removed") or []
        dup = before.duplicated(keep="first")
        if removed and all(bool(dup.loc[r]) for r in removed):
            return True, self.cite("duplicates"), f"{len(removed)} removed row(s), each an exact copy of an earlier kept row"
        return False, NOT_COVERED, "a removed row is not an exact copy of an earlier row"

    def _parse_dates(self, args, preview, before):
        return False, NOT_COVERED, (f"converting ambiguous dates needs a day/month order (date_order="
                                    f"{args.get('date_order')!r}); no rule gives one")

    def _blanks_only_unreadable(self, col, kind, rows, before, preview):
        """Shared test for change 2: no row removed, and every cell turned missing is unreadable for its column."""
        if preview.get("rows_removed"):
            return False, NOT_COVERED, "the fix removes rows"
        if kind is None:
            return False, NOT_COVERED, f"the rules don't say what {col} holds (number, date or label)"
        if not rows:
            return False, NOT_COVERED, "no cell would turn missing"
        readable = [(r, before.at[r, col]) for r in rows if not self.unreadable(col, kind, before.at[r, col])]
        if readable:
            r, v = readable[0]
            return False, NOT_COVERED, f"row {r}: {col}={_show(v)} is a readable {kind}; only unreadable cells may be blanked"
        shown = ", ".join(_show(before.at[r, col]) for r in rows[:5])
        return True, self.cite("unreadable"), f"{len(rows)} unreadable {kind}(s) in {col} blanked ({shown}); no row removed"

    def _cast_numeric(self, args, preview, before):
        col = args["column"]
        if self.column_kind(col) != "number":
            return False, NOT_COVERED, f"the rules don't define {col} as a number column"
        after = preview["after"]
        turned = [r for r in before.index if not is_missing(before.at[r, col]) and r in after.index
                  and is_missing(after.at[r, col])]
        return self._blanks_only_unreadable(col, "number", turned, before, preview)

    def _exclude(self, rows, before):
        if not rows:
            return False, NOT_COVERED, "no rows to remove"
        reasons, bad = {}, []
        for r in rows:
            broken = self.range_broken(before.loc[r])
            (reasons.__setitem__(r, broken) if broken else bad.append(r))
        if bad:
            return False, NOT_COVERED, f"row(s) {bad[:10]} break no range rule"
        shown = "; ".join(f"row {r}: {why}" for r, why in list(reasons.items())[:5])
        return True, self.cite("range"), f"every removed row breaks a range rule ({shown})"

    def _exclude_rows(self, args, preview, before):
        return self._exclude([int(r) for r in args.get("rows", [])], before)

    def _exclude_where(self, args, preview, before):
        return self._exclude([int(r) for r in (preview.get("rows_removed") or [])], before)

    def _recompute_column(self, args, preview, before):
        formula = self.formula()
        if formula is None:
            return False, NOT_COVERED, "the rules give no formula"
        target, rhs = formula
        if args["column"] != target or _squash(args["expression"]) != _squash(rhs):
            return False, NOT_COVERED, f"only {target} = {rhs} is covered, not {args['column']} = {args['expression']}"
        rows = [int(r) for r in args.get("rows", [])]
        if not rows:
            return False, NOT_COVERED, "no rows given"
        sub = before.loc[rows]
        inputs = [c for c in re.findall(r"[A-Za-z_][A-Za-z_0-9]*", rhs) if c in before.columns]
        expected = evaluate_expression(sub, rhs)
        for r in rows:
            for c in inputs:
                v = loose_number(sub.at[r, c])
                if v is None or self.out_of_range(c, v):
                    return False, NOT_COVERED, f"row {r}: input {c}={_show(sub.at[r, c])} is not a number within its range, so the formula can't repair it"
            exp = float(expected.loc[r])
            act = loose_number(sub.at[r, target])
            if act is not None and abs(act - exp) <= 0.005 * abs(exp) + 1e-6:  # datasage/checks.py check_cross_column
                return False, NOT_COVERED, f"row {r} already satisfies {target} = {rhs}"
            if self.out_of_range(target, exp):
                return False, NOT_COVERED, f"row {r}: recomputed {target}={exp} would break its range"
        return True, self.cite("formula"), f"{len(rows)} row(s) break {target} = {rhs} and have valid inputs"

    def _set_missing(self, args, preview, before):
        col = args["column"]
        rows = [int(r) for r in args.get("rows", [])]
        if not rows:
            return False, NOT_COVERED, "no rows given"
        if preview.get("rows_removed"):
            return False, NOT_COVERED, "the fix removes rows"
        values = [before.at[r, col] for r in rows]
        tokens = self.profile.get("missing_tokens", {}).get(col)
        if tokens and all(isinstance(v, str) and normalize_label(v) in tokens for v in values):
            return True, self.cite("missing_date"), f"{col} value(s) {values} mean unknown and should be missing"
        turned = [r for r in rows if not is_missing(before.at[r, col])]
        ok, rule, why = self._blanks_only_unreadable(col, self.column_kind(col), turned, before, preview)
        if ok and col in self.profile.get("unknown_label_to_missing", set()):
            rule = self.cite("unknown_channel")
        return ok, rule, why

    def _fill_missing(self, args, preview, before):
        if self.profile.get("never_fill"):
            return False, self.cite("no_guess"), "the rules say not to guess missing values"
        return False, NOT_COVERED, "no rule supplies a fill value"


def main() -> None:
    parser = argparse.ArgumentParser(description="Run DataSage with the policy approver.")
    parser.add_argument("--case", required=True)
    parser.add_argument("--profile", required=True, choices=sorted(PROFILES))
    parser.add_argument("--input", required=True)
    parser.add_argument("--rules", required=True)
    parser.add_argument("--request", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-tool-calls", type=int, default=30)
    args = parser.parse_args()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    log = out / "decisions.jsonl"
    log.unlink(missing_ok=True)  # a retry starts a fresh log for this case
    approver = PolicyApprover(args.case, args.profile, args.rules, log)
    result = run_agent(args.input, args.request, approver, rules_path=args.rules, model=args.model,
                       max_tool_calls=args.max_tool_calls, verbose=True)
    write_outputs(result, out)
    summary = {"case": args.case, "question": args.request, "input": args.input, "rules": args.rules,
               "model": result.model, "stop_reason": result.stop_reason, "finished": result.finished,
               "answer": result.answer, "tool_calls": result.tool_calls, "tool_errors": result.tool_errors,
               "approvals_asked": result.approvals_asked, "seconds": result.seconds,
               "prompt_tokens": result.prompt_tokens, "completion_tokens": result.completion_tokens}
    (out / "result.json").write_text(json.dumps(summary, indent=2, default=_jsonable), encoding="utf-8")
    print(f"\nstop: {result.stop_reason} | tool calls: {result.tool_calls} | errors: {result.tool_errors} | "
          f"approvals asked: {result.approvals_asked} | {result.seconds}s | tokens: {result.prompt_tokens}+{result.completion_tokens}")
    print(f"answer: {result.answer}")
    print(f"outputs written to {out}/")


if __name__ == "__main__":
    main()
