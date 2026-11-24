"""Fill docs/final/findings_models.md from eval/model_study_findings.txt and eval/results/study_models.json, so every
number in the write-up comes from the result files. Usage: python -m eval.model_study_doc (after aggregate)."""
import glob, json, os, statistics, subprocess, sys

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = sys.executable
os.chdir(REPO)
tmpl = open(os.path.join(REPO, "eval", "model_study_findings.txt")).read()
d = json.load(open("eval/results/study_models.json"))
probe = json.load(open("eval/results/model_probe.json"))
M, S = d["models"], d["summary"]


def A(s):
    return M[s]["agent"]["heldout_test"]


def B(s):
    return M[s]["single_call"]["heldout_test"]


def beh(s):
    return M[s]["agent"]["behaviour"]


def acc(s):
    a = A(s)
    return f"{100 * a['accuracy']:.1f}% ({a['correct']} of {a['tasks']})"


SATURATED = ("qwen3-vl-32b-think", "mistral-large-4")
def timeouts_left_sentence():
    left = {}
    for path in glob.glob("eval/results/*/*/*.json"):
        system = path.split("/")[2]
        if not (system.startswith("b2-") or system.startswith("datasage-m3-")):
            continue
        r = json.load(open(path))
        if r["stop_reason"].startswith("api_error") or r["stop_reason"] == "code_timeout":
            left[system] = left.get(system, 0) + 1
    if not left:
        return "No result in the tables ended in an API error or timeout."
    return ("Results that still ended in an API timeout or code timeout after the retry (counted as wrong): "
            + ", ".join(f"`{k}` {v}" for k, v in sorted(left.items())) + ".")


full = [s for s in M if A(s) and A(s)["tasks"] == 80 and not s.endswith("-original")]
partial = [s for s in M if A(s) and A(s)["tasks"] < 80]
tool_ok = [s for s in full if (A(s)["tool_error_rate"] or 0) < 0.05 and A(s)["completion"] >= 0.9]
outs = sorted(M[s]["agent"]["scope_split"]["needs_exclusion_outside_question"]["correct"] for s in tool_ok)
think = [("qwen3-30b", "qwen3-30b-think"), ("qwen3-235b", "qwen3-235b-think"), ("qwen3-vl-32b", "qwen3-vl-32b-think")]
think_pairs = "; ".join(f"`{M[i]['model']}` {acc(i)} against `{M[t]['model']}` {acc(t)}" for i, t in think)
think_out = ", ".join(f"{M[t]['model']} {100 * beh(t)['tasks_checking_a_column_the_question_does_not_use']:.0f}% against "
                      f"{100 * beh(i)['tasks_checking_a_column_the_question_does_not_use']:.0f}% for its instruct twin"
                      for i, t in think)
gains = [(M[s]["agent_minus_single_call"], s) for s in full if "agent_minus_single_call" in M[s]]
pos = [g for g, _ in gains if g > 0]
gmed = statistics.median(g for g, _ in gains)
gain_sentence = (f"The column is filled only where the single call answered all 80 questions with no API timeout "
                 f"(a timeout counts as a wrong answer, which would flatter the agent). For those {len(gains)} models "
                 f"the agent is better for "
                 f"{len(pos)}, by a median of {100 * gmed:.1f} points (from {100 * min(g for g, _ in gains):+.1f} to "
                 f"{100 * max(g for g, _ in gains):+.1f}).")


def b2_damage(s):
    rows = [json.load(open(p)) for p in glob.glob(f"eval/results/b2-{s}/*-*/*.json")
            if p.split("/")[-2] in ("sales-heldout", "penguins-heldout", "sales-test", "penguins-test")]
    return sum(r["damaged_rows"] + r["damaged_cells"] for r in rows)


dmg = ", ".join(f"{b2_damage(s)} for `{M[s]['model']}`" for s in ["qwen3-30b", "qwen3-235b", "glm-5-3", "gpt-oss-120b"])
reruns = json.load(open("eval/results/model_study_reruns.json"))["removed"]
partial_note = "; ".join(f"`{M[s]['model']}` {A(s)['tasks']} of 80" for s in partial)
k = lambda s, key: beh(s)["tool_error_kinds"].get(key, 0)
INV = "invalid arguments (schema or JSON)"
vals = {
    "N_MODELS": len(M) - 1, "N_FULL": len(full), "N_NEAR_PERFECT": len(S["models_with_80_tasks_at_least_39_of_40_on_other_tasks"]),
    "N_LISTED": probe["listed_models"], "N_NOT_CHAT": len(probe["not_chat"]), "N_PROBED": len(probe["probes"]),
    "N_PASS": sum(p["real_pass"] for p in probe["probes"]),
    "SAT_NOTE": "; ".join(f"`{M[x]['model']}` {A(x)['tasks']} of 80" for x in SATURATED),
    "OTHER_PARTIAL": ("Also partial when the study ended: " + "; ".join(
        f"`{M[x]['model']}` {A(x)['tasks']} of 80" for x in partial if x not in SATURATED) + ".")
    if any(x not in SATURATED for x in partial) else "",
    "X235": f"{A('qwen3-235b')['seconds_median'] / A('qwen3-30b')['seconds_median']:.0f}",
    "XINK": f"{A('inkling-small')['seconds_median'] / A('qwen3-30b')['seconds_median']:.1f}",
    "SCOUT_GAP": f"{100 * (A('qwen3-30b')['accuracy'] - A('llama4-scout')['accuracy']):.1f}",
    "INK_GAP": f"{100 * (A('inkling-small')['accuracy'] - A('qwen3-30b')['accuracy']):.1f}",
    "Q235_ACC": acc("qwen3-235b"),
    "OUT_TOP": f"{outs[-1]}/40", "OUT_LOW": f"{outs[0]}/40",
    "N_SPEARMAN": S["spearman_accuracy_vs_checking_outside_question_columns"]["models"],
    "RHO": f"{S['spearman_accuracy_vs_checking_outside_question_columns']['rho']:.2f}",
    "THINK_PAIRS": think_pairs, "THINK_OUTSIDE": think_out,
    "MAV_NOTOOL": A("llama4-maverick")["stop_reasons"].get("no_tool_calls", 0), "MAV_NUDGES": beh("llama4-maverick")["nudges"],
    "O7_ERR": A("olmo3-7b")["tool_errors"], "O7_CALLS": A("olmo3-7b")["tool_calls"], "O7_INV": k("olmo3-7b", INV),
    "O7_LOOPS": beh("olmo3-7b")["error_loops"], "O7_BUDGET": A("olmo3-7b")["stop_reasons"].get("tool_budget_exhausted", 0),
    "O32_INV": k("olmo3-32b", INV), "O32_AWF": A("olmo3-32b")["stop_reasons"].get("answered_without_finish", 0),
    "GEM_INV": k("gemma4-31b", INV), "GPT_AWF": A("gpt-oss-120b")["stop_reasons"].get("answered_without_finish", 0),
    "GPT_INV": k("gpt-oss-120b", INV), "SCOUT_ERR": A("llama4-scout")["tool_errors"], "SCOUT_REC": A("llama4-scout")["recovered_errors"],
    "Q30_SEC": f"{A('qwen3-30b')['seconds_median']:.0f}",
    "PARETO_S": ", ".join(f"`{M[s]['model']}` ({100 * A(s)['accuracy']:.1f}%, {A(s)['seconds_median']:.0f} s)" for s in S["pareto_accuracy_vs_median_seconds"]),
    "RHO_S": f"{S['spearman_accuracy_vs_median_seconds']:.2f}",
    "PARETO_T": ", ".join(f"`{M[s]['model']}` ({100 * A(s)['accuracy']:.1f}%, {A(s)['tokens_median']:,.0f} tokens)" for s in S["pareto_accuracy_vs_median_tokens"]),
    "TURNS": "; ".join(f"`{M[s]['model']}` {A(s)['tool_calls_median']:.0f} calls in {A(s)['model_turns_median']:.0f} turns, "
                       f"{A(s)['tokens_median']:,.0f} tokens" for s in ["glm-5-3", "mimo-v2-6-pro", "qwen3-30b", "qwen3-235b"]),
    "GLM_SPEC": acc("glm-5-3-spec"), "GLM": acc("glm-5-3"),
    "GAIN_SENTENCE": gain_sentence, "B2_DAMAGE_EXAMPLES": dmg,
    "Q30_ACC": acc("qwen3-30b"), "Q30O_ACC": acc("qwen3-30b-original"), "Q30_CALLS": A("qwen3-30b")["tool_calls"],
    "INK_ACC": acc("inkling-small"),
    "Q30_B2": f"{100 * B('qwen3-30b')['accuracy']:.1f}% ({B('qwen3-30b')['correct']} of {B('qwen3-30b')['tasks']})",
    "Q30_ACC_N": f"{A('qwen3-30b')['correct']} of 80", "Q30O_ACC_N": f"{A('qwen3-30b-original')['correct']} of 80",
    "N_RERUN": sum("Connection error" in r["reason"] for r in reruns),
    "N_API_TO": sum("timed out" in r["reason"] for r in reruns),
    "N_API_TO_B2": sum("timed out" in r["reason"] and r["system"].startswith("b2-") for r in reruns),
    "N_CODE_TO": sum(r["reason"].startswith("code_timeout") for r in reruns),
    "TIMEOUTS_LEFT": timeouts_left_sentence(),
    "B2_PARTIAL": ("Single calls not run to the end (the slowest reasoning models often needed more than the 180 s "
                   "timeout per attempt): " + "; ".join(
                       f"`{M[x]['model']}` {B(x)['tasks']} of 80" for x in M if B(x) and B(x)['tasks'] < 80)
                   + ". For these the Agent minus B2 column is left empty.")
    if any(B(x) and B(x)["tasks"] < 80 for x in M) else
    "Apart from the two saturated models, every single-call run has all 80 questions.",
    "B2_SLOW": "; ".join(f"`{M[x]['model']}` {B(x)['stop_reasons'].get('api_error', 0)} of 80"
                         for x in M if B(x) and B(x)["stop_reasons"].get("api_error", 0) >= 20),
    "PARTIAL_LIMIT": ("Partial models: " + partial_note + ". Their accuracy is over the questions they finished, which "
                      "are not a random sample (the earlier, mostly sales, splits finished first).") if partial else
                     "Every model in the tables ran all 80 questions.",
}
# shared failures on penguins-heldout (Finding 1)
COMMON = ["glm-5-3", "glm-5-3-flash", "glm-5-2", "deepseek-v4-1-flash", "mimo-v2-6-pro", "mimo-v2-6-flash",
          "muse-spark-open", "granite41-30b", "hemmingway-1-5", "ornith-1-5-35b", "qwen3-30b-think", "gemma4-31b"]


def wrong(system, split="penguins-heldout"):
    return {Path(p).stem for p in glob.glob(f"eval/results/{system}/{split}/*.json") if not json.load(open(p))["analysis_correct"]}


from pathlib import Path  # noqa: E402
common = set.intersection(*(wrong(f"datasage-m3-{m}") for m in COMMON))
outside = set(d["tasks_needing_exclusion_outside_question_columns"])
right_on = lambda m: f"{len(common - wrong(f'datasage-m3-{m}'))} of {len(common)}"
neg = [(g, s) for g, s in gains if g < 0]
high = [s for s in full if A(s)["accuracy"] >= 0.9]
fastest_high = min(high, key=lambda s: A(s)["seconds_median"])
assert fastest_high == "qwen3-30b", fastest_high
above = [s for s in full + partial if A(s)["accuracy"] > A("qwen3-30b")["accuracy"]]


def per_task(system):
    return {Path(p).stem: json.load(open(p))["analysis_correct"]
            for split in ("sales-heldout", "penguins-heldout", "sales-test", "penguins-test")
            for p in glob.glob(f"eval/results/{system}/{split}/*.json")}


def mcnemar(x, y):
    """Exact two-sided McNemar test on the questions both systems answered."""
    from math import comb
    a, b = per_task(x), per_task(y)
    shared = a.keys() & b.keys()
    only_x = sum(a[t] and not b[t] for t in shared)
    only_y = sum(b[t] and not a[t] for t in shared)
    n = only_x + only_y
    p = min(1.0, 2 * sum(comb(n, i) for i in range(min(only_x, only_y) + 1)) / 2 ** n) if n else 1.0
    return only_x, only_y, p


paired = [(s, *mcnemar("datasage-m3-qwen3-30b", M[s]["agent_system"])) for s in above]
damages = [A(s)["damaged_cells_rows"] for s in M if A(s)]
complete_b2 = [s for s in M if B(s) and B(s)["tasks"] == 80]
best_b2 = max(complete_b2, key=lambda s: B(s)["accuracy"])
assert B(best_b2)["accuracy"] < A("qwen3-30b")["accuracy"]
vals.update({
    "COMMON_N": len(COMMON), "COMMON_MODELS": ", ".join(f"`{M[m]['model']}`" for m in COMMON),
    "COMMON_TASKS": len(common), "COMMON_OUT": len(common & outside),
    "COMMON_Q30": right_on("qwen3-30b"), "COMMON_INK": right_on("inkling-small"), "COMMON_Q235": right_on("qwen3-235b"),
    "GLM_SPEC_S": f"{A('glm-5-3-spec')['seconds_median']:.0f}", "GLM_S": f"{A('glm-5-3')['seconds_median']:.0f}",
    "DAMAGE_SENTENCE": ("Damage is 0 in every agent row" if not any(damages) else f"total agent damage {sum(damages)}"),
    "NEG_GAIN": ", ".join(f"`{M[s]['model']}` ({100 * g:+.1f} points)" for g, s in sorted(neg)) or "none",
    "SCOUT_B2": f"{B('llama4-scout')['correct']} of {B('llama4-scout')['tasks']}", "SCOUT_ACC": acc("llama4-scout"),
    "N_HIGH": len(high),
    "PAIRED": "; ".join(f"`{M[s]['model']}` got {oy} questions right that Qwen3-30B missed and missed {ox} that it got "
                        f"right (exact McNemar p = {pv:.2f})" for s, ox, oy, pv in paired),
    "BEST_B2": f"`{M[best_b2]['model']}` with {100 * B(best_b2)['accuracy']:.1f}%",
})
out = tmpl
for key, value in vals.items():
    out = out.replace("{" + key + "}", str(value))
tables = subprocess.run([PY, "-m", "eval.model_study", "table"], capture_output=True, text=True, check=True).stdout
out = out.replace("<!-- TABLES -->", tables.strip())
left = [w for w in out.split("{")[1:] if w.split("}")[0].isupper()]
assert not left, left
open("docs/final/findings_models.md", "w").write(out)
print("written", len(out), "chars")
