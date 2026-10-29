"""Baselines B0, B1 and B2 plus the DataSage runner, all returning eval.scoring.SystemOutput.

B0  stakeholder baseline (baseline/run_baseline.py): its fixed checks, no cleaning; the requested
    aggregate is computed on the uncleaned data, which is what its revenue_by_category analysis does.
B1  fixed cleaning script, no model: the same cleaning rules on every file, then the structured request.
B2  single model call: the model sees the same profile, sample rows and rules as DataSage and returns
    issues plus pandas code, which is run once with no checks, retries or approval.
"""

from __future__ import annotations

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import pandas as pd

from datasage.agent import DEFAULT_MODEL, make_client, run_agent
from datasage.analyze import run_analysis
from datasage.profile import profile, sample_rows
from datasage.session import load_rules, load_table
from datasage.values import iso_date, loose_number, normalize_label
from eval.oracle import OracleApprover
from eval.scoring import Bundle, SystemOutput

REPO = Path(__file__).resolve().parent.parent


def _stakeholder_module():
    spec = importlib.util.spec_from_file_location("run_baseline", REPO / "baseline" / "run_baseline.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _b0_issues(quality: dict) -> set[tuple[str, str]]:
    issues = {("missing", c) for c in quality["missing_values"]}
    if quality["duplicate_rows"]:
        issues.add(("duplicates", "*"))
    issues |= {("negative", c) for c in quality["negative_values"]}
    issues |= {("invalid_date", c) for c in quality["invalid_dates"]}
    issues |= {("label_variant", c) for c in quality["inconsistent_categories"]}
    return issues


def _answer(df: pd.DataFrame, spec: dict) -> dict | None:
    try:
        return run_analysis(df, spec["group_by"], spec["metric"], spec["agg"], spec.get("filters"))["result"]
    except ValueError:
        return None


def run_b0(bundle: Bundle, task: dict) -> SystemOutput:
    start = time.time()
    module = _stakeholder_module()
    df = module.load_dataset(str(bundle.messy_path))
    quality = module.profile_quality(df)
    answer = _answer(df, task["spec"])
    return SystemOutput(answer=answer, cleaned=df, issues=_b0_issues(quality), completed=answer is not None,
                        seconds=round(time.time() - start, 3), stop_reason="done" if answer is not None else "analysis_failed")


def b1_clean(df: pd.DataFrame) -> tuple[pd.DataFrame, set[tuple[str, str]]]:
    """Fixed rules, applied to every file in the same order."""
    df = df.copy()
    issues: set[tuple[str, str]] = set()
    text_cols = [c for c in df.columns if not pd.api.types.is_numeric_dtype(df[c])]
    for col in text_cols:  # 1-2. trim spaces, merge case variants to the most common form
        values = df[col].dropna().astype(str)
        if (values != values.str.strip()).any():
            issues.add(("label_variant", col))
        df[col] = df[col].map(lambda v: v.strip() if isinstance(v, str) else v)
        counts = df[col].dropna().astype(str).value_counts()
        groups: dict[str, str] = {}
        for value in counts.index:
            groups.setdefault(normalize_label(value), value)
        mapped = df[col].map(lambda v: groups.get(normalize_label(v), v) if isinstance(v, str) else v)
        if (mapped.fillna("") != df[col].fillna("")).any():
            issues.add(("label_variant", col))
        df[col] = mapped
    if df.duplicated().any():  # 3. drop exact duplicates
        issues.add(("duplicates", "*"))
        df = df[~df.duplicated()]
    for col in text_cols:  # 4. mostly-numeric text columns become numbers
        values = df[col].dropna()
        parsed = values.map(loose_number)
        if len(values) and parsed.notna().mean() >= 0.8:
            if any(isinstance(v, str) for v in values):
                issues.add(("text_number", col))
            df[col] = pd.to_numeric(df[col].map(loose_number))
    for col in df.columns:  # 5. invalid dates in date-named columns become missing
        if "date" in str(col).lower():
            bad = df[col].notna() & df[col].map(lambda v: iso_date(v) is None)
            if bad.any():
                issues.add(("invalid_date", col))
            df.loc[bad, col] = pd.NA
    numeric = [c for c in df.columns if pd.api.types.is_numeric_dtype(df[c])]
    negative = (df[numeric] < 0).any(axis=1) if numeric else pd.Series(False, index=df.index)
    for col in numeric:  # 6. drop rows with negative numbers
        if (df[col] < 0).any():
            issues.add(("negative", col))
    df = df[~negative]
    for col in df.columns:
        if df[col].isna().any():
            issues.add(("missing", col))
    return df, issues


def run_b1(bundle: Bundle, task: dict) -> SystemOutput:
    start = time.time()
    raw = pd.read_csv(bundle.messy_path)
    cleaned, issues = b1_clean(raw)
    answer = _answer(cleaned, task["spec"])
    return SystemOutput(answer=answer, cleaned=cleaned, issues=issues, completed=answer is not None,
                        seconds=round(time.time() - start, 3), stop_reason="done" if answer is not None else "analysis_failed")


B2_PROMPT = """You are given a messy table and a question. In ONE reply, return a JSON object with:
  "issues": list of {"type": one of [missing, duplicates, label_variant, invalid_date, text_number, negative, out_of_range, cross_column], "column": column name or "*" for duplicates},
  "code": Python code (pandas imported as pd) that defines
      clean(df) -> DataFrame   (fix the problems that matter for the question; keep the id column)
      answer(df) -> dict       (maps each group label to a number; multi-column group labels are joined with " | ",
                                months are "YYYY-MM", a single overall value uses the key "all"; drop missing group keys)
The table is already loaded as `df`: fully numeric columns are numbers, other columns are text, and missing values are NaN.
Row index = 0-based row position. Return only the JSON object."""

_RUNNER = """
import json, pickle, sys
import pandas as pd
sys.path.insert(0, {repo!r})
from datasage.session import load_table
df = load_table({path!r})
ns = {{"pd": pd}}
exec(compile(open({code!r}).read(), "b2_code", "exec"), ns)
cleaned = ns["clean"](df.copy())
answer = ns["answer"](cleaned)
answer = {{str(k): (None if v is None else float(v)) for k, v in dict(answer).items()}}
pickle.dump({{"cleaned": cleaned, "answer": answer}}, open({out!r}, "wb"))
"""


def _extract_json(text: str) -> dict:
    text = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.S)
    if fenced:
        text = fenced.group(1)
    start, end = text.find("{"), text.rfind("}")
    return json.loads(text[start:end + 1])


def run_b2(bundle: Bundle, task: dict, model: str = DEFAULT_MODEL, client=None) -> SystemOutput:
    client = client or make_client()
    start = time.time()
    df = load_table(bundle.messy_path)
    user = json.dumps({"question": task["question"], "rules": load_rules(bundle.rules_path),
                       "profile": profile(df), "sample_rows": sample_rows(df)}, default=str)
    try:
        response = client.chat.completions.create(model=model, temperature=0, timeout=180, messages=[
            {"role": "system", "content": B2_PROMPT}, {"role": "user", "content": user}])
    except Exception as err:
        return SystemOutput(answer=None, cleaned=None, completed=False, seconds=round(time.time() - start, 2),
                            stop_reason="api_error", note=str(err)[:200])
    usage = response.usage
    tokens = dict(prompt_tokens=usage.prompt_tokens if usage else 0, completion_tokens=usage.completion_tokens if usage else 0)
    content = response.choices[0].message.content or ""
    try:
        reply = _extract_json(content)
        issues = {(i["type"], i["column"]) for i in reply.get("issues", []) if isinstance(i, dict)}
        code = reply["code"]
    except (ValueError, KeyError, TypeError) as err:
        return SystemOutput(answer=None, cleaned=None, completed=False, seconds=round(time.time() - start, 2),
                            stop_reason="bad_json", note=str(err)[:200], **tokens)

    with tempfile.TemporaryDirectory() as tmp:
        code_path, out_path, runner = Path(tmp, "code.py"), Path(tmp, "out.pkl"), Path(tmp, "runner.py")
        code_path.write_text(code)
        runner.write_text(_RUNNER.format(repo=str(REPO), path=str(bundle.messy_path), code=str(code_path), out=str(out_path)))
        try:
            proc = subprocess.run([sys.executable, str(runner)], capture_output=True, text=True, timeout=60)
        except subprocess.TimeoutExpired:
            return SystemOutput(answer=None, cleaned=None, issues=issues, completed=False,
                                seconds=round(time.time() - start, 2), stop_reason="code_timeout", **tokens)
        if proc.returncode != 0:
            return SystemOutput(answer=None, cleaned=None, issues=issues, completed=False, seconds=round(time.time() - start, 2),
                                stop_reason="code_error", note=proc.stderr.strip().splitlines()[-1][:200] if proc.stderr else "",
                                extra={"code": code}, **tokens)
        data = pd.read_pickle(out_path)
    return SystemOutput(answer=data["answer"], cleaned=data["cleaned"], issues=issues, completed=True,
                        seconds=round(time.time() - start, 2), stop_reason="done", extra={"code": code}, **tokens)


def run_datasage(bundle: Bundle, task: dict, model: str = DEFAULT_MODEL, approver: str = "oracle",
                 use_validator: bool = True, client=None, trace_path=None, prompt_fix: bool = False) -> SystemOutput:
    from datasage.agent import SYSTEM_PROMPT, SYSTEM_PROMPT_V2
    from datasage.approval import AutoApprover, RejectApprover

    chosen = {"oracle": lambda: OracleApprover(bundle), "oracle-strict": lambda: OracleApprover(bundle, strict_exclusion=True),
              "reject": RejectApprover, "auto": AutoApprover}[approver]()
    result = run_agent(bundle.messy_path, task["question"], chosen, rules_path=bundle.rules_path, model=model,
                       client=client, use_validator=use_validator, trace_path=trace_path,
                       system_prompt=SYSTEM_PROMPT_V2 if prompt_fix else SYSTEM_PROMPT)
    return SystemOutput(answer=result.answer, cleaned=result.session.current,
                        issues=set(result.session.issues.keys()), completed=result.finished,
                        tool_calls=result.tool_calls, tool_errors=result.tool_errors,
                        recovered_errors=result.recovered_errors, approvals_asked=result.approvals_asked,
                        seconds=result.seconds, prompt_tokens=result.prompt_tokens,
                        completion_tokens=result.completion_tokens, stop_reason=result.stop_reason,
                        extra={"final_summary": result.final_summary,
                               "changes": [c.to_dict() for c in result.session.changes],
                               "rejected": [{k: v for k, v in r.items() if k != "args"} for r in result.session.rejected],
                               "oracle_decisions": getattr(chosen, "decisions", [])})
