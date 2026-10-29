"""Run systems over the benchmark and save one JSON result per task (resumable).

Usage:
  python -m eval.run_eval --system datasage --dataset sales --workers 4
  python -m eval.run_eval --system b2 --dataset penguins
Systems: b0, b1, b2, datasage, datasage-small, datasage-reject, datasage-novalidator,
         datasage-fix, datasage-fix-strict, datasage-small-fix, datasage-small-fix-strict
Datasets: sales, penguins (dev) and sales-heldout, penguins-heldout
"""

from __future__ import annotations

import argparse
import json
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from baselines import systems
from datasage.agent import make_client
from eval.scoring import SystemOutput, all_bundles, score

ROOT = Path(__file__).resolve().parent
SMALL_MODEL = "qwen3-30b-a3b-instruct-2507"

SYSTEMS = {
    "b0": lambda b, t, c, trace: systems.run_b0(b, t),
    "b1": lambda b, t, c, trace: systems.run_b1(b, t),
    "b2": lambda b, t, c, trace: systems.run_b2(b, t, client=c),
    "datasage": lambda b, t, c, trace: systems.run_datasage(b, t, client=c, trace_path=trace),
    "datasage-small": lambda b, t, c, trace: systems.run_datasage(b, t, model=SMALL_MODEL, client=c, trace_path=trace),
    "datasage-reject": lambda b, t, c, trace: systems.run_datasage(b, t, approver="reject", client=c, trace_path=trace),
    "datasage-novalidator": lambda b, t, c, trace: systems.run_datasage(b, t, use_validator=False, client=c, trace_path=trace),
    # Milestone 2 failure-analysis fix: exclusion rule in the prompt, with the normal or the strict oracle.
    "datasage-fix": lambda b, t, c, trace: systems.run_datasage(b, t, prompt_fix=True, client=c, trace_path=trace),
    "datasage-fix-strict": lambda b, t, c, trace: systems.run_datasage(b, t, prompt_fix=True, approver="oracle-strict",
                                                                     client=c, trace_path=trace),
    "datasage-small-fix": lambda b, t, c, trace: systems.run_datasage(b, t, model=SMALL_MODEL, prompt_fix=True,
                                                                    client=c, trace_path=trace),
    "datasage-small-fix-strict": lambda b, t, c, trace: systems.run_datasage(b, t, model=SMALL_MODEL, prompt_fix=True,
                                                                           approver="oracle-strict", client=c, trace_path=trace),
}


def run(system: str, dataset: str, workers: int, limit: int | None, results_dir: Path, only: set[str] | None = None) -> None:
    out_dir = results_dir / system / dataset
    out_dir.mkdir(parents=True, exist_ok=True)
    jobs = [(b, t) for b in all_bundles(dataset) for t in b.tasks if not only or t["task_id"] in only][:limit]
    client = make_client() if system not in ("b0", "b1") else None

    def one(bundle, task):
        path = out_dir / f"{task['task_id']}.json"
        if path.exists():
            return task["task_id"], "cached"
        trace = out_dir / "traces" / f"{task['task_id']}.jsonl"
        try:
            output = SYSTEMS[system](bundle, task, client, trace)
        except Exception as err:  # a crash counts as an incomplete task, not a pipeline failure
            output = SystemOutput(answer=None, cleaned=None, completed=False, stop_reason="crash",
                                  note=f"{type(err).__name__}: {err}"[:300])
            (out_dir / f"{task['task_id']}.error.txt").write_text(traceback.format_exc())
        result = score(bundle, task, output)
        result.update(system=system, dataset=dataset, question=task["question"], reference_answer=task["reference_answer"],
                      issues_reported=sorted(map(list, output.issues)))
        path.write_text(json.dumps(result, indent=2, default=str))
        return task["task_id"], "ok" if result["analysis_correct"] else f"wrong ({result['stop_reason']})"

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(one, b, t) for b, t in jobs]
        for done, future in enumerate(as_completed(futures), 1):
            task_id, status = future.result()
            print(f"[{system}/{dataset}] {done}/{len(jobs)} {task_id}: {status}", flush=True)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--system", required=True, choices=list(SYSTEMS))
    parser.add_argument("--dataset", required=True, choices=["sales", "penguins", "sales-heldout", "penguins-heldout"])
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--only", default="", help="comma list of task ids to run")
    parser.add_argument("--results", default=str(ROOT / "results"))
    args = parser.parse_args()
    only = {t.strip() for t in args.only.split(",") if t.strip()}
    run(args.system, args.dataset, args.workers, args.limit, Path(args.results), only)


if __name__ == "__main__":
    main()
