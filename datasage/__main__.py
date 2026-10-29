"""Command line: python -m datasage --input FILE --request "..." [--rules rules.json] [--approve ask]"""

from __future__ import annotations

import argparse

from .agent import DEFAULT_MODEL, run_agent
from .approval import AskApprover, AutoApprover, RejectApprover, ScriptedApprover, ToolPolicyApprover
from .report import write_outputs


def main() -> None:
    parser = argparse.ArgumentParser(prog="datasage", description="Clean a messy table and answer a question about it.")
    parser.add_argument("--input", required=True, help="CSV or XLSX file")
    parser.add_argument("--request", required=True, help="question in plain English")
    parser.add_argument("--rules", help="optional JSON rules file (column meanings, ranges, formulas)")
    parser.add_argument("--approve", default="ask", choices=["ask", "auto", "reject", "script", "tools"],
                        help="how risky fixes are approved (default: ask at the terminal)")
    parser.add_argument("--answers", default="", help="for --approve script: comma list like y,n,y")
    parser.add_argument("--allow", default="", help="for --approve tools: fix types to approve, e.g. drop_duplicates,parse_dates")
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--max-tool-calls", type=int, default=30)
    parser.add_argument("--out", default="outputs/run", help="folder for report.md, cleaned.csv, replay.py, trace.jsonl")
    args = parser.parse_args()

    if args.approve == "tools":
        approver = ToolPolicyApprover([t.strip() for t in args.allow.split(",") if t.strip()])
    elif args.approve == "script":
        approver = ScriptedApprover([a.strip().lower() in ("y", "yes") for a in args.answers.split(",") if a.strip()])
    else:
        approver = {"ask": AskApprover, "auto": AutoApprover, "reject": RejectApprover}[args.approve]()
    result = run_agent(args.input, args.request, approver, rules_path=args.rules, model=args.model,
                       max_tool_calls=args.max_tool_calls, verbose=True)
    out = write_outputs(result, args.out)
    print(f"\nstop: {result.stop_reason} | tool calls: {result.tool_calls} | errors: {result.tool_errors} | "
          f"approvals asked: {result.approvals_asked} | {result.seconds}s | tokens: {result.prompt_tokens}+{result.completion_tokens}")
    print(f"answer: {result.answer}")
    print(f"outputs written to {out}/")


if __name__ == "__main__":
    main()
