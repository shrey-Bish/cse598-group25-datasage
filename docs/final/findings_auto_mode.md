# Auto approval mode: does it work, and what does it cost?

The browser app has an "Ask me / Auto" switch. In Auto, `BrowserApprover` (app/web/runner.py) approves every
medium or high risk fix at once and sends each approval event with `auto: true`. This note checks that the
switch works (Part 1) and measures what approving everything costs compared with a careful person (Part 2).

Base: branch `shrey/exclude-where` (commit f4be9cb), which adds `examples/demo/` and
`examples/make_demo_files.py`. Model: the app default, qwen3-30b-a3b-instruct-2507.

## Part 1: does Auto mode work?

How it was tested: the server ran on port 8620 and a script drove the HTTP API the way the page does
(`POST /api/runs` with `approve: "auto"`, reading `GET /api/runs/<id>/events`, `POST /api/runs/<id>/cancel`,
then `GET /api/runs/<id>/profile` and the four output files). Uploads were sent as base64 with the rules
text, as `start()` in app.js does. "Wait" below is the time between an approval event and its
`approval_closed` event.

### Expected answers

| Sample | Expected when every fix is approved | Where it comes from |
|---|---|---|
| 8-row `messy_sales.csv` | Electronics 2,245, Accessories 830 | by hand: drop the duplicate row, merge the case variants, drop row 6 (Quantity -1 breaks `min: 1`) |
| `large_sales.csv` (1,208 rows) | Electronics 570,440, Accessories 60,380 | clean rows from `make_large_sales.py` minus the 6 rows with a negative Quantity |
| HR demo (407 rows) | Engineering 130,027.03, Sales 82,280.22, Finance 100,993.24, Operations 62,343.37, Marketing 88,243.24 | `make_demo_files.py` |
| Inventory demo (606 rows) | Phoenix 1,156,928.05, Tempe 936,441.6, Mesa 844,651.2, Tucson 1,286,821.7 | `make_demo_files.py` |

The brief said the 8-row answer with every fix approved is Electronics 2,185. That is the answer when the
exclusion of row 6 is rejected (it is what `docs/final/demo/report.md` shows, where that fix was rejected).
With every fix approved, row 6 (revenue -60) is dropped and Electronics is 2,245. All four Auto runs of the
small sample returned 2,245.

### Checklist

13 Auto runs in total (11 finished, 2 stopped on purpose) plus 1 Ask me run.

| # | Check | Result | Evidence |
|---|---|---|---|
| 1 | Every approval event has `auto: true` | Pass | 37 approval events over the 13 Auto runs, all `auto: true` |
| 2 | No run ever waits for a person | Pass | longest wait from approval to close: 0.035 s (HR, second run); no approval left open |
| 3 | The `done` event arrives | Pass, after a fix | before the fix the event stream never closed (see Bug 1); after it, every run ended with `done` |
| 4a | 8-row sample answer | Pass | run c55af15340: Electronics 2,245, Accessories 830; same answer in runs e664673771, 9a3726cf96 and the Latin-1 run 33de54fe86 |
| 4b | Large sample answer | Pass | runs b578bc2a76, 81afb57482, 7c96f0ecc2: Electronics 570,440, Accessories 60,380 |
| 4c | HR answer | Pass | runs 205cd25e9a and a3190db04a: Engineering 130,027.027, Finance 100,993.2432, Marketing 88,243.2432, Operations 62,343.3735, Sales 82,280.2198 (equal to the expected values at 2 decimals) |
| 4d | Inventory answer | Pass | runs 74a94adcb6 and 98e675530e: Mesa 844,651.2, Phoenix 1,156,928.05, Tempe 936,441.6, Tucson 1,286,821.7 (exact) |
| 5 | Every applied change says "approved automatically" or "safe, applied without asking" | Pass | in all 13 Auto runs every entry in `changes` is applied and has one of those two texts |
| 6 | Data health works after an Auto run | Pass | `health` present in every `done` event: rows before and after, removals by reason, every issue marked `fixed`. For the large and HR samples the "answer before cleaning" shows "metric column ... is text, not numbers", which is the intended message, not a failure |
| 7 | Column profile works after an Auto run | Pass | `GET /api/runs/<id>/profile` returned 200 with columns for every run, including the stopped ones (1,208 to 1,200 rows) |
| 8 | Output files | Pass | `cleaned.csv`, `report.md`, `replay.py`, `trace.jsonl` returned 200 for every run |
| 9 | Stop during an Auto run | Pass | runs d996c4cd31 and 83915b52dc (large sample): Stop sent right after the first auto approval; `done` came with `stop_reason: cancelled`, the stream ended 0.22 s and 0.28 s after the Stop, one step finished after it, no further approvals. The duplicate removal approved before the Stop stays applied and the profile still works |
| 10 | Two browsers at once do not cancel each other | Pass | client ids A and B started together: runs e664673771 and 9a3726cf96 both ended with `finish`, neither was cancelled, both answered 2,245 / 830 |
| 11 | Semicolon-separated Latin-1 CSV in Auto | Pass | the 8-row sample rewritten with `;` and Latin-1, with an accented product ("Caméra"): `/api/inspect` and the run both report separator `;` and encoding cp1252 (a superset of Latin-1 that decodes these bytes the same way); the profile shows "Caméra" correctly; answer 2,245 / 830 (run 33de54fe86) |
| 12 | A later run switched back to "Ask me" still waits | Pass | run 505e8ddeed, same client id as the earlier Auto runs: both approvals had `auto: false` and each waited 20.0 s until the script answered; the log says "you approved" |
| 13 | Large sample stable over 3 runs | Pass | the same answer, the same 4 approvals (drop_duplicates, normalize_labels, exclude_rows, recompute_column) and the same 5 changes in all three runs; times 48.8 s, 49.4 s, 29.6 s |

### Bugs found and fixed

**Bug 1: the event stream never ended.** `_events` in app/web/server.py sent `Connection: keep-alive`. The
response has no length, and `http.server` treats that header as "keep the socket open for another
request", so after the `done` event the connection stayed open and a client reading the stream never saw
the end. Repro before the fix: start any run, wait for it to finish, then
`curl -m 40 http://127.0.0.1:8620/api/runs/<id>/events` hangs until the 40 s timeout although the run is
done. The page did not notice because it closes its EventSource when `done` arrives, but any other client
(a script, a test, curl) hung, and the server thread stayed busy until the client gave up. Fix: send
`Connection: close`. Test: `test_event_stream_ends_when_the_run_is_done` (fails before the fix with a
timeout, passes after).

**Bug 2: a fix refused because of Stop was logged as "you chose Keep".** In Auto mode a fix is only
refused when the run is stopped (the approver says no at once after a Stop), but the change log said
"you chose Keep, so it is listed as a caveat". The same text was used in Ask me mode for a stopped run and
for an approval nobody answered within 10 minutes. The approver now records why each fix was refused, and
the log says "not applied because the run was stopped" or "no answer within 10 minutes, so it is listed as
a caveat" when that is what happened. `approval_closed` also no longer reports `timed_out: true` for a
Stop. Test: `test_change_log_says_why_a_fix_was_not_applied`. In the two Stop runs above the Stop landed
between model calls, so no fix was refused; the test covers a Stop in the middle of a turn.

All tests pass: `python -m pytest -q tests` reports 71 passed.

## Part 2: what does Auto cost compared with a careful person?

`datasage-m3-auto` (eval/run_eval.py) is `datasage-m3` with `AutoApprover` in place of the oracle approver
(eval/oracle.py), which approves a fix only if it moves the data toward the reference table. It ran on all
six standard splits (120 questions): the four asked for plus the two dev splits. `eval.summarize` only
added rows for the new system. Six sales tasks first ended in connection errors when the laptop crashed;
those six were deleted and run again, and no other result was touched.

### Results

Pooled from the per-task files in `eval/results/datasage-m3/` and `eval/results/datasage-m3-auto/`:

| Tasks | System | Answer correct | Damaged rows / cells | Errors handled | Risky fixes approved | Fixes the oracle refused |
|---|---|---:|---:|---:|---:|---:|
| 4 asked splits (80) | datasage-m3 (oracle approver) | 74 (92.5%) | 0 / 0 | 684 of 752 (91.0%) | 181 of 182 | 1 |
| 4 asked splits (80) | datasage-m3-auto | 75 (93.8%) | 3 / 0 | 683 of 752 (90.8%) | 176 of 176 | would have refused 1 |
| Dev splits (40) | datasage-m3 | 40 (100%) | 0 / 0 | 353 of 382 (92.4%) | 93 of 93 | 0 |
| Dev splits (40) | datasage-m3-auto | 38 (95.0%) | 0 / 0 | 353 of 382 (92.4%) | 93 of 93 | would have refused 0 |
| All six (120) | datasage-m3 | 114 (95.0%) | 0 / 0 | 1,037 of 1,134 (91.4%) | 274 of 275 | 1 |
| All six (120) | datasage-m3-auto | 113 (94.2%) | 3 / 0 | 1,036 of 1,134 (91.4%) | 269 of 269 | would have refused 1 |

Per split (from `eval/results/summary.md`):

| Split | M3 correct | Auto correct | M3 damage | Auto damage | M3 errors handled | Auto errors handled |
|---|---:|---:|---:|---:|---:|---:|
| sales | 100% | 100% | 0 | 0 | 91% | 92% |
| penguins | 100% | 90% | 0 | 0 | 94% | 93% |
| sales-heldout | 100% | 100% | 0 | 0 | 89% | 89% |
| penguins-heldout | 85% | 85% | 0 | 0 | 92% | 91% |
| sales-test | 100% | 100% | 0 | 3 | 91% | 91% |
| penguins-test | 85% | 90% | 0 | 0 | 93% | 93% |

"Would have refused" was measured by replaying each Auto run's fix calls from its trace on the messy table
(every replayed fix applied exactly as in the original run) and asking the oracle about each risky one.

Latency is not compared: the Auto runs shared the API with other jobs, and an automatic approval takes no
time, so the higher Auto medians in summary.md (for example 41.8 s against 16.6 s on penguins) reflect API
load, not the mode.

### Every task where the outcome differs

| Task | M3 | Auto | Cause, from the traces |
|---|---|---|---|
| salest_00_q1 (total revenue per month) | correct, 0 damage | correct, 3 damaged rows, errors handled 8 to 5 | **Caused by Auto.** After `parse_dates` blanked 3 unreadable dates, the agent called `check_missing` on Date and then `exclude_rows` on rows [5, 6, 44]. Auto approved it; the oracle refuses it ("removes row 5 (id 2006) that should be kept"). The reference keeps those orders with a blank date. The answer stayed right only because rows with no month do not count in a per-month total |
| penguins_08_q0 (count per island) | correct | wrong (Biscoe 28 and Torgersen 11 instead of 27 and 10) | Not caused by Auto. The Auto run never checked the range of body_mass_g, so rows 11 and 28 (outside 2,500 to 6,500 g) stayed. All 3 risky fixes it did make are ones the oracle approves too. The M3 run checked body_mass_g and dropped those rows |
| penguins_08_q1 (Adelie bill length by island) | correct | wrong (Torgersen 37.9455 instead of 37.53) | Not caused by Auto. The same skipped body_mass_g range check on the same table |
| penguinst_06_q1 (count per island) | wrong (Torgersen 5) | correct (Torgersen 4) | Not caused by Auto. This time the Auto run checked body_mass_g and dropped row 0, a fix the oracle also approves; the M3 run never checked that column |
| salest_04_q0 (Electronics revenue by region) | correct | correct | Same answer, but worth noting: in the M3 run the agent proposed `exclude_rows` on rows [29, 44, 67], whose only problem was a blank Region, and the oracle refused it ("removes row 29 (id 2029) that should be kept"). The Auto run happened not to propose it. Had it, Auto would have approved it and damaged 3 rows |

So in 120 tasks, Auto changed one result because of what it approved (salest_00_q1: 3 rows wrongly
dropped, answer still right). The three accuracy changes come from the 30B model choosing different checks
from one run to the next, not from approvals: the oracle would have approved every fix in those runs.

Caveat: the `datasage-m3` results were produced on 2026-11-09. Since then the agent code gained
exclude_where, tolerant tool arguments and browser-related changes (f4be9cb and earlier commits), and the
model is not deterministic, so small differences between the two systems can come from either.

## Recommendation

- **Auto is safe enough for the kinds of files in this benchmark.** The agent proposed 269 risky fixes in
  the Auto runs and the careful approver would have refused 1 of them (0.4%). Accuracy (113 of 120 against
  114 of 120) and errors handled (91.4% for both) are the same within run-to-run noise. Auto fits a first
  look at a file, demos, and files whose rules file already says what to drop.
- **Use Ask me when the cleaned table itself will be kept or shared**, not just the answer. The one real
  cost of Auto showed up as damage to the cleaned table (3 rows dropped) while the answer stayed correct,
  so a person checking only the answer would not see it.
- **One fix type should not be auto-approved: `exclude_rows` on rows whose only problem is a blank or
  unreadable value.** Both refusals among 544 risky proposals (269 in the Auto runs, 275 in the M3 runs)
  were this exact pattern: dropping rows because Date or Region was missing, when the right action is to
  keep the row with a blank cell. Rows that break a rule in the rules file (a range, a formula) were always
  dropped correctly. A simple guard: in Auto, still ask (or refuse) when `exclude_rows` targets rows that
  were flagged only by `check_missing` or `check_dates`.
- **`fill_missing` was never proposed in these 120 tasks**, so there is no evidence about it. It guesses
  values, which the oracle always refuses, so it should also stay out of Auto until it is measured.
- Auto also approves fixes on columns the question does not use (one small-sample run blanked an
  unreadable Date that the revenue question never reads). That is harmless for the answer but changes the
  cleaned table, which supports the advice above.

## Follow-up (done)

The recommendation is now built into the app's Auto mode (`auto_needs_person` in `app/web/runner.py`): a row
drop by row id (`exclude_rows`) is not auto-approved when any dropped row has no recorded problem or
only blank or unreadable values (missing, invalid date). `exclude_where` is not paused: it removes only rows
outside a range rule, so every row it drops breaks a rule (until Nov 22 it was paused too, which wrongly
stopped Auto whenever it dropped more rows than the check had listed, see `docs/final/regression_check.md`). Auto pauses, says why on the card, and waits for
Keep or Apply. Rows that break a rule (negative, out of range, formula mismatch) are still dropped at once.
This would have stopped the one bad auto-approval found above (`salest_00_q1`).
