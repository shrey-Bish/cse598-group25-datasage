"""Approval gate. Low-risk fixes are applied directly; medium and high risk fixes go to an approver.

Approvers: a person at the terminal (`AskApprover`), scripted answers for demos (`ScriptedApprover`),
fixed policies (`AutoApprover`, `RejectApprover`), and the evaluation oracle (in eval/oracle.py).
"""

from __future__ import annotations

import sys


class Approver:
    name = "approver"

    def decide(self, tool: str, args: dict, risk: str, preview: dict) -> bool:  # pragma: no cover
        raise NotImplementedError


class AutoApprover(Approver):
    name = "auto-approve"

    def decide(self, tool, args, risk, preview):
        return True


class RejectApprover(Approver):
    name = "reject-all"

    def decide(self, tool, args, risk, preview):
        return False


class ScriptedApprover(Approver):
    """Answers approvals from a list (used to record repeatable demos)."""

    name = "scripted"

    def __init__(self, answers: list[bool]):
        self.answers = list(answers)

    def decide(self, tool, args, risk, preview):
        answer = self.answers.pop(0) if self.answers else False
        print(f"    [approval] {tool} ({risk} risk): {preview['summary']} -> {'APPROVED' if answer else 'REJECTED'}")
        return answer


class ToolPolicyApprover(Approver):
    """Approves risky fixes of the listed tool types and rejects the rest (repeatable demos)."""

    name = "tool-policy"

    def __init__(self, allowed: list[str]):
        self.allowed = set(allowed)

    def decide(self, tool, args, risk, preview):
        answer = tool in self.allowed
        print(f"    [approval] {tool} ({risk} risk): {preview['summary']} -> {'APPROVED' if answer else 'REJECTED'}")
        return answer


class AskApprover(Approver):
    name = "user"

    def decide(self, tool, args, risk, preview):
        print(f"\n  DataSage wants to apply a {risk}-risk fix:")
        print(f"    {tool}: {preview['summary']}")
        print(f"    reason: {args.get('reason', '')}")
        if preview.get("rows_removed"):
            print(f"    rows removed: {preview['rows_removed'][:20]}")
        sys.stdout.write("  Approve? [y/N] ")
        sys.stdout.flush()
        answer = sys.stdin.readline().strip().lower()
        return answer in ("y", "yes")
