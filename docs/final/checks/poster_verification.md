# Poster number check (task A3)

Checked by Arsha Jindal on November 22, 2026, against main at
`265a6c8face078d33f1d67f7b0c700acba303c06`. Every number, percentage, count and factual claim on
`docs/final/poster/Group25_Poster.pdf` (and `poster.html`) was compared with the sources listed in
`docs/final/poster/README.md`. This file only records the check; it does not change the poster.

## Result

Every number matches its source except two claims, which do not match the result files. Both were
**reported to Shrey on Nov 22**:

1. **"Across 41 models, the agent design adds a median 20 points over a single call."** (What we learned,
   third line.) 41 models ran as the planner, but only 32 have a single-call comparison
   (`docs/final/findings_models.md:229`: "For those 32 models the agent is better for 29"). The median gain
   of those 32 is 19.4 points. Suggested wording: "Across 32 models, the agent design adds a median 19
   points over a single call."
2. **"200 unseen questions"** (headline and Results caption). 40 of the 200 are the held-out split, which
   PR #7 says was "read closely during Milestone 2"; that is why the seed-202 test split was made. The
   95.5% does not depend on it: the 120 new questions alone give 97.5%
   (`docs/final/findings_scale_and_ablations.md:60`). Suggested wording: drop "unseen".

## Status on main

Re-checked on November 23, 2026, at main `265a6c8face078d33f1d67f7b0c700acba303c06` (unchanged since
the check):

| Question | Answer | Where |
|---|---|---|
| Does `poster.html` now say "32 models"? | **No.** It still says "Across 41 models, the agent design adds a median 20 points over a single call." | `docs/final/poster/poster.html:232`; the poster README (`docs/final/poster/README.md:26`) also still says "41 models, a median 20 points" |
| Does `poster.html` still say "unseen"? | **Yes**, twice: "95.5% of 200 unseen questions on messy tables right" and "200 unseen questions on sales and penguin tables [3]". | `docs/final/poster/poster.html:72` (headline), `:209` (Results caption) |

## How the numbers were checked

- `python -m eval.study` and `python -m eval.summarize` were rerun on a clean `git archive` copy of that
  commit, never in the repo: `study_scale_ablations.json` came out the same and `summary.md`
  byte-identical.
- Recomputed from the result and data files: the damage over all four runs of the 200 questions; the
  example's raw and cleaned answers, with DataSage's own `run_analysis` and fix functions; the
  approval-card rows from `examples/large_sales.csv`; and the model-study median from
  `eval/results/study_models.json`.

✅ matches · ⚠️ number matches, wording could mislead · ❌ does not match the source (reported to Shrey on Nov 22)

| # | Poster text | Poster value | Source | Source value | Match |
|---|---|---|---|---|---|
| 1 | Headline: DataSage on 200 questions | 95.5% | `findings_scale_and_ablations.md:58`; `study_scale_ablations.json` (191/200) | 95.5% | ✅ |
| 2 | Headline: single LLM call | 46.5% | `findings_scale_and_ablations.md:57` (93/200) | 46.5% | ✅ |
| 3 | Headline: "never damaged a valid cell", box "0" | 0 | `findings_scale_and_ablations.md:97`; per-task files of run 0 and repeats 1 to 3 | 0 in all 800 runs | ✅ |
| 4 | "200 **unseen** questions" (headline, Results caption) | — | PR #7: the held-out split was "read closely during Milestone 2" | 40 of the 200 are held-out | ❌ |
| 5 | Example table, 8 rows × 5 columns | as shown | `baseline/examples/messy_sales.csv:2-9` | equal | ✅ |
| 6 | Example flags (dup, bad date, Qty < 1, 2 label merges) | as shown | `examples/messy_sales_rules.json`; `docs/final/demo/report.md:22-25` | equal | ✅ |
| 7 | Raw file, 4 groups | 2,060 / 125 / 1,350 / 80 | `run_analysis` on the raw file | 2060 / 125 / 1350 / 80 | ✅ |
| 8 | After approvals | Electronics 2,245, Accessories 830 | fix functions + `run_analysis`, all three risky fixes approved | 2245 / 830 | ✅ (the recorded demos rejected the drop: 2,185) |
| 9 | Approval card: 6 rows, rows #15 #151 #236 #326 #654 | as shown | `examples/large_sales.csv:17,153,238,328,656,993` | equal | ✅ (1,208-row sample, not the 8-row file) |
| 10 | B0 / B1 / B2 on 200 | 6.0% / 49.0% / 46.5% | `findings_scale_and_ablations.md:55-57` | equal | ✅ |
| 11 | B1 / B2 on 40 hard | 10% / 55% | `findings_hard.md:80-81`; `eval/results/summary.md:531-532, 541-542` | 10.0% / 55.0% | ✅ (B2 is the 235B model) |
| 12 | DataSage, Qwen3-30B, on 40 hard | 100%\* (90% before) | `findings_hard.md:82, 331` | 90.0% → 40/40 | ✅ ⚠️ fix found on these questions |
| 13 | Model size | Qwen3-30B | `datasage/agent.py:17-18` (`DEFAULT_MODEL = SMALL_MODEL`) | qwen3-30b-a3b-instruct-2507 | ✅ |
| 14 | Hard table sizes | 343–1,935 rows | `findings_hard.md:32` | 343–1,935 | ✅ |
| 15 | "95% range 92.0–98.5 [6]" | 92.0–98.5 | `findings_scale_and_ablations.md:39, 58` | 95% bootstrap CI | ✅ ⚠️ a CI, not the run-to-run range (94.0–96.0) |
| 16 | Ablations | 95.5 / 12.0 / 86.0 / 91.5 / 96.5 / 97.0% | `findings_scale_and_ablations.md:97-102` | equal | ✅ |
| 17 | Effect labels | matters a lot … no clear effect | `findings_scale_and_ablations.md:116-120, 138-147` | consistent | ✅ ⚠️ "No approvals" = every risky fix rejected |
| 18 | Bar widths | — | `poster.html` `width:` values | equal to the printed numbers | ✅ |
| 19 | "Across **41** models … a median **20** points over a single call" | 41, 20 | `findings_models.md:229`; `eval/results/study_models.json` | 32 models compared with a single call; median gain 19.4 | ❌ |
| 20 | Main limitation | — | `findings_scale_and_ablations.md:163` | 36 of 39 wrong runs | ✅ |
| 21 | References 1–6, all cited in the text | — | publisher and arXiv records; `baseline/SOURCE.md` | match | ✅ |
| 22 | Repo URL and QR | github.com/shrey-Bish/cse598-group25-datasage | `make_figs.py:120` | same URL | ✅ (QR to scan by phone) |
| 23 | Format | 1 page | `pdfinfo` | 1728 × 2592 pt (24 × 36 in) | ✅ |

**Why the median is 19, not 20.** In `eval/results/study_models.json`, 41 models answered all 80
questions as the planner, and 32 of them have an `agent_minus_single_call` gain. The two middle gains are
18.75 and 20.0 points, so the median is 19.4. `eval/model_study_doc.py:58` takes
`sorted(gains)[len(gains) // 2]`, which for an even count is the upper middle value, 20.0;
`statistics.median` gives 19.4.

## Wording suggestions (not mismatches)

- **"No approvals 12.0%"** is the run where every medium- or high-risk fix is rejected. In a "turn one
  part off" table it can read as "no approval step", that is, auto-apply. A clearer label: "Every risky
  fix refused".
- **"95% range 92.0–98.5"** is a bootstrap confidence interval, not the run-to-run range (94.0–96.0).
  "95% CI" is accurate and shorter.
- **Hard 100%\*:** the grouping fix was found by analysing failures on these same hard questions
  (`findings_hard.md` sections 5 and 8). The footnote discloses "90% before".
- **Approval card:** the screenshot is from the 1,208-row sample, not the 8-row example beside it. Its
  numbers match that file.
- **B2's model:** B2 is the 235B model on both the 200 and the hard set. The poster doesn't say so.
- **QR code:** generated from the repo URL (`make_figs.py:120`) but not decoded here; scan it once with a
  phone.
