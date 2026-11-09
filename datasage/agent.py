"""The DataSage agent loop: one planner model calling tools until it finishes or the budget runs out."""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from .approval import Approver
from .profile import profile, sample_rows
from .session import Session, load_rules, load_table
from .tools import TOOL_SCHEMAS, Dispatcher

LARGE_MODEL = "qwen3-235b-a22b-instruct-2507"
SMALL_MODEL = "qwen3-30b-a3b-instruct-2507"
DEFAULT_MODEL = SMALL_MODEL  # stakeholder decision (Oct 28): small model by default, large model optional

SYSTEM_PROMPT = """You are DataSage, a careful data-quality and analysis agent.
You receive a messy table (CSV/Excel) and a question. Find the data problems that matter for the
question, fix the safe ones with the fix tools, and then answer the question with the analyze tool.

How to work:
- You never see the full table. Use the profile, the sample rows and the check tools.
- If a rules file exists, read it first with lookup_rules and apply its rules (ranges, formulas).
- Check every column the question uses (group-by keys, filter columns, the metric) and also check
  for duplicate rows. Columns the question does not use can be left alone.
- Make one fix per tool call and give a short reason. Fixes run on a copy; the original file never changes.
- Prefer the smallest correct fix. If you are not sure a value is wrong, do not change it; mention it.
- Never invent values: do not fill missing values unless the rules file says what they should be.
- Some fixes need the user's approval. If a fix is rejected, do not retry it.
- All numbers in your answer must come from tool results. Do not do arithmetic yourself.
- When the data the question depends on is clean, call analyze once for the question, then finish
  with a short summary of the problems found, the fixes applied, and any caveats.
Row ids are 0-based row positions in the original file."""

# Milestone 2 fix for the main failure mode (rule-violating rows blanked instead of excluded).
EXCLUSION_RULE = """
- When a row breaks a rule (an impossible or out-of-range value, or a negative value where the rules
  say it must be positive), propose exclude_rows for those rows; the user can reject it. Use
  set_missing only for unreadable values (such as invalid dates) in rows that are otherwise valid."""
SYSTEM_PROMPT_V2 = SYSTEM_PROMPT.replace("\nRow ids are 0-based", EXCLUSION_RULE + "\nRow ids are 0-based")

# Milestone 3 (Section 6, item 2): spelling merges into the rules' allowed labels.
MERGE_RULE = """
- When check_label_variants returns a suggested_fix, call normalize_labels once with that mapping. It
  merges misspellings into the allowed labels; it needs approval. Never exclude a row only because its
  label is misspelled.
- If analyze is refused because problems are still open, fix them (or explain why one stays), then call
  analyze again."""
SYSTEM_PROMPT_V3 = SYSTEM_PROMPT_V2.replace("\nRow ids are 0-based", MERGE_RULE + "\nRow ids are 0-based")

KEEP_RECENT_TURNS = 3  # compact memory: model turns kept verbatim; older ones are replaced by the state summary


@dataclass
class RunResult:
    session: Session
    model: str
    finished: bool
    stop_reason: str
    final_summary: str
    tool_calls: int = 0
    tool_errors: int = 0
    recovered_errors: int = 0
    approvals_asked: int = 0
    coverage_refusals: int = 0
    model_turns: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    seconds: float = 0.0
    trace: list[dict] = field(default_factory=list)

    @property
    def answer(self) -> dict | None:
        return self.session.analyses[-1]["result"] if self.session.analyses else None


def make_client():
    from dotenv import load_dotenv
    from openai import OpenAI

    load_dotenv()
    key = os.environ.get("RC_LLM_API_KEY") or os.environ.get("OPENAI_API_KEY")
    base_url = os.environ.get("RC_LLM_BASE_URL")
    if not key:
        raise RuntimeError("set RC_LLM_API_KEY (and RC_LLM_BASE_URL) in .env")
    return OpenAI(api_key=key, base_url=base_url)


def _first_message(session: Session) -> str:
    return json.dumps({
        "question": session.request,
        "rules_file": "available, call lookup_rules" if session.rules else "none",
        "profile": profile(session.current),
        "sample_rows": sample_rows(session.current),
    }, default=str)


def _clip(text: str, limit: int = 6000) -> str:
    return text if len(text) <= limit else text[:limit] + "...[truncated]"


def build_messages(head: list[dict], turns: list[list[dict]], session: Session, memory: str,
                   keep: int = KEEP_RECENT_TURNS) -> list[dict]:
    """Messages for the next model call.

    full: the whole conversation. compact: the system prompt, the first message plus a state summary
    built by code (checks done, findings, changes, rejected fixes, analyses), and only the last `keep`
    model turns with their tool results. Turns are kept whole, so every tool result follows its call.
    """
    if memory == "full" or len(turns) <= keep:
        return head + [m for turn in turns for m in turn]
    state = json.dumps(session.summary(), default=str)
    note = (f"State of the run so far, built by code ({len(turns) - keep} earlier turns are not shown; this replaces "
            f"them): {state}\nDecide the next step from this state. Do not re-run a check whose latest result is "
            f"on the current version.")
    return head + [m for turn in turns[-keep:] for m in turn] + [{"role": "user", "content": note}]


def run_agent(path: str | Path, request: str, approver: Approver, *, rules_path=None, model: str = DEFAULT_MODEL,
              client=None, max_tool_calls: int = 30, use_validator: bool = True, verbose: bool = False,
              trace_path: str | Path | None = None, system_prompt: str = SYSTEM_PROMPT_V3, memory: str = "full",
              coverage: bool = True) -> RunResult:
    client = client or make_client()
    session = Session(load_table(path), source=str(path), request=request, rules=load_rules(rules_path))
    dispatcher = Dispatcher(session, approver, use_validator=use_validator, coverage=coverage)
    head = [{"role": "system", "content": system_prompt}, {"role": "user", "content": _first_message(session)}]
    turns: list[list[dict]] = []
    result = RunResult(session=session, model=model, finished=False, stop_reason="", final_summary="")
    start = time.time()
    nudges = 0
    last_failed = False

    def log(event: dict) -> None:
        event["t"] = round(time.time() - start, 2)
        result.trace.append(event)
        if verbose:
            _print_event(event)

    while True:
        if result.tool_calls >= max_tool_calls:
            result.stop_reason = "tool_budget_exhausted"
            break
        messages = build_messages(head, turns, session, memory)
        try:
            response = client.chat.completions.create(model=model, messages=messages, tools=TOOL_SCHEMAS,
                                                      tool_choice="auto", temperature=0, timeout=180)
        except Exception as err:  # network or API errors end the run with a partial result
            result.stop_reason = f"api_error: {type(err).__name__}: {str(err)[:200]}"
            log({"event": "api_error", "error": result.stop_reason})
            break
        result.model_turns += 1
        if response.usage:
            result.prompt_tokens += response.usage.prompt_tokens or 0
            result.completion_tokens += response.usage.completion_tokens or 0
        message = response.choices[0].message
        calls = message.tool_calls or []
        turn = [{"role": "assistant", "content": message.content or "",
                 **({"tool_calls": [c.model_dump() for c in calls]} if calls else {})}]
        turns.append(turn)

        if not calls:
            if session.analyses:
                result.final_summary = message.content or ""
                result.finished, result.stop_reason = True, "answered_without_finish"
                break
            nudges += 1
            if nudges > 2:
                result.stop_reason = "no_tool_calls"
                break
            turn.append({"role": "user", "content": "Use the tools: check and fix the relevant columns, call analyze for the question, then finish."})
            log({"event": "nudge", "text": (message.content or "")[:300]})
            continue

        for call in calls:
            result.tool_calls += 1
            name, raw = call.function.name, call.function.arguments
            output, ok = dispatcher.call(name, raw)
            if not ok:
                result.tool_errors += 1
            elif last_failed:
                result.recovered_errors += 1
            last_failed = not ok
            log({"event": "tool", "name": name, "args": _safe_json(raw), "ok": ok, "output": output})
            turn.append({"role": "tool", "tool_call_id": call.id, "content": _clip(json.dumps(output, default=str))})
            if dispatcher.finished:
                break
        if dispatcher.finished:
            result.finished, result.stop_reason = True, "finish"
            result.final_summary = dispatcher.final_summary
            break

    result.approvals_asked = dispatcher.approvals_asked
    result.coverage_refusals = dispatcher.coverage_refusals
    result.seconds = round(time.time() - start, 2)
    if trace_path:
        Path(trace_path).parent.mkdir(parents=True, exist_ok=True)
        with open(trace_path, "w") as fh:
            for event in result.trace:
                fh.write(json.dumps(event, default=str) + "\n")
    return result


def _safe_json(raw: str):
    try:
        return json.loads(raw or "{}")
    except json.JSONDecodeError:
        return raw


def _print_event(event: dict) -> None:
    if event["event"] != "tool":
        print(f"[{event['t']:6.1f}s] {event['event']}: {event.get('text') or event.get('error')}")
        return
    out = event["output"]
    status = "ok" if event["ok"] else "ERROR"
    brief = out.get("error") or out.get("summary") or out.get("message") or ""
    if not brief and "count" in out:
        brief = f"count={out['count']} rows={out.get('rows')}"
    if not brief and "result" in out:
        brief = f"result={out['result']}"
    if event["name"] == "check_numeric":
        brief = f"text_numbers={out['text_numbers']['count']} negatives={out['negatives']['count']} not_numbers={out['not_numbers']['count']}"
    if event["name"] == "check_label_variants":
        brief = f"case/space={out['case_or_space_variants']} misspellings={out['possible_misspellings']}"
    args = json.dumps(event["args"])[:110]
    print(f"[{event['t']:6.1f}s] {event['name']}({args}) -> {status} {str(brief)[:160]}")
