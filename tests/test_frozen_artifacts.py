"""The frozen results and demo files still match the code that produced them.

These checks only read the committed files and write only to tmp_path. They make no model calls and need no API
key, and they pass on Windows and Linux: CSVs are compared by content with line endings normalised.
"""

import csv
import io
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

from app.report_view import load_run
from eval import summarize

REPO = Path(__file__).resolve().parent.parent
RESULTS = REPO / "eval" / "results"
DEMO = REPO / "docs" / "final" / "demo"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8").replace("\r\n", "\n")


def _csv_rows(path: Path) -> list[list[str]]:
    return list(csv.reader(io.StringIO(_text(path))))


class _SplitResults:
    """Stands in for summarize.RESULTS: summary.* paths go to `out`, everything else is read from eval/results."""

    def __init__(self, out: Path):
        self.out = out

    def __truediv__(self, name: str) -> Path:
        return (self.out if str(name).startswith("summary.") else RESULTS) / name


def test_results_tables_match_the_summarizer(tmp_path, monkeypatch):
    """eval/results/summary.md, .json and .csv are what `python -m eval.summarize` builds from the per-task files."""
    monkeypatch.setattr(summarize, "RESULTS", _SplitResults(tmp_path))  # main() writes into RESULTS
    summarize.main()

    assert _text(tmp_path / "summary.md") == _text(RESULTS / "summary.md")
    assert json.loads(_text(tmp_path / "summary.json")) == json.loads(_text(RESULTS / "summary.json"))
    assert _csv_rows(tmp_path / "summary.csv") == _csv_rows(RESULTS / "summary.csv")


def test_demo_replay_reproduces_cleaned_csv(tmp_path):
    """The final demo's replay.py, run on a copy of the demo's input, gives the committed cleaned.csv."""
    source = re.search(r"^- Input: `(.+)`$", _text(DEMO / "report.md"), re.M).group(1)
    (tmp_path / source).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy(REPO / source, tmp_path / source)
    shutil.copy(DEMO / "replay.py", tmp_path / "replay.py")

    # replay.py leaves the cleaned table in `df`; write it the way write_outputs() in datasage/report.py does.
    code = "import runpy; runpy.run_path('replay.py')['df'].to_csv('replayed.csv', index_label='row')"
    proc = subprocess.run([sys.executable, "-c", code], cwd=tmp_path, capture_output=True, timeout=60,
                          encoding="utf-8", errors="replace")
    assert proc.returncode == 0, proc.stderr

    assert _csv_rows(tmp_path / "replayed.csv") == _csv_rows(DEMO / "cleaned.csv")


def test_report_view_finds_every_change_in_the_final_demo():
    """load_run and parse_change_log read the final demo folder and every row of its change log."""
    view = load_run(DEMO)
    assert view.report_md is not None
    assert set(view.files) == {"cleaned.csv", "replay.py", "trace.jsonl"}

    # Every fix the run asked for, from its trace: applied ones in version order, then rejected ones, as in report.md.
    events = [json.loads(line) for line in _text(DEMO / "trace.jsonl").splitlines() if line.strip()]
    fixes = [e for e in events if e.get("event") == "tool" and "approval" in (e.get("output") or {})]
    applied = sorted((e for e in fixes if e["output"]["applied"]), key=lambda e: e["output"]["version"])
    rejected = [e for e in fixes if not e["output"]["applied"]]
    expected = [(f"v{e['output']['version']}", e["name"], e["output"]["risk"], e["output"]["approval"], e["args"]["reason"])
                for e in applied] + [("-", e["name"], e["output"]["risk"], "rejected", e["args"]["reason"]) for e in rejected]

    found = [(row["version"], row["fix"], row["risk"], row["approval"], row["reason"]) for row in view.changes]
    assert len(expected) == 4
    assert found == expected
    assert all(row["what_changed"] for row in view.changes)
