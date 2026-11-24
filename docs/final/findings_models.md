# Which model should drive DataSage? Every model on the ASU API, compared

Short answer: keep `qwen3-30b-a3b-instruct-2507` as the default. Across the 43 models that can call tools on
the API, it is one of four models that no other model beats on both accuracy and speed, and it finishes a question in
about half a minute even under heavy load. `qwen3-235b-a22b-instruct-2507` was the only model to answer all 80 questions
correctly, but it took about 7 times as long per question. The biggest surprise is why the other models lose: on the
40 questions where the question's own columns are the whole story, 30 of the 41 fully run models
score 39 or 40 out of 40. Almost all of the spread comes from one habit (whether the model also cleans rows that break
the rules in columns the question does not use), plus a few models that cannot produce valid tool calls at all.

## What we ran

- **Agent.** For each model, `datasage-m3-<model>` is the final system `datasage-m3` with only the model name
  changed: same prompt (V3), same 13 tools, same coverage check, same validator, same oracle approver, temperature 0,
  a budget of 30 tool calls, and a 180 second timeout per model call. We did not set any reasoning effort, so each
  model ran at its API default. `datasage-m3-qwen3-30b` is `datasage-m3` itself, run again alongside the others so
  its latency was measured under the same load; the original Milestone 3 run is shown as a separate row.
- **Single call.** `b2-<model>` is the B2 baseline with that model: one call that sees the same profile, sample rows
  and rules, returns a list of issues plus pandas code, and the code is run once.
- **Questions.** The four standard held-out and test splits: `sales-heldout`, `penguins-heldout`, `sales-test`,
  `penguins-test`, 80 questions in total. We did not run the dev splits; the other studies cover the hard split.
- **Code.** `eval/model_study.py` (probe, aggregation, tables), `eval/model_study_driver.py` (runs all pairs from one
  process), the `MODEL_SYSTEMS` block in `eval/run_eval.py`. Per-task results are in
  `eval/results/<system>/<dataset>/` and the aggregates in `eval/results/study_models.json`.

## Which models we tried

The API lists 54 models. 14 are not chat models (speech, transcription, embedding, image, video and
3D models) and cannot drive an agent. For the chat models we sent two probes each
(`python -m eval.model_study probe`, saved in `eval/results/model_probe.json`): a toy request with one tool, and the
real first DataSage turn (system prompt, all tool schemas, profile and sample rows of a held-out table). Five chat
names are families whose reasoning setting picks between an instruct and a thinking model, so we probed both members
of each (for example `qwen3-30b-a3b-instruct-2507` and `qwen3-30b-a3b-thinking-2507`). That makes 45 chat
endpoints.

| Result | Models |
|---|---|
| Returned valid DataSage tool calls (43) | every model in the tables below |
| `north-mini-code-glm` failed | 400 error: "auto tool choice requires --enable-auto-tool-choice and --tool-call-parser". It is the draft model behind `glm-5-3-spec`, not meant for direct use. |
| `north-mini-code` failed | the toy probe worked after 218 s, but the real DataSage turn returned a 500 Internal Server Error. Not studied. |

Passing the probe did not mean a model could finish the task: `llama4-maverick-17b` passed both probes but in the full
runs it mostly wrote its tool calls as plain text (see failure modes).

Two models could not be run to the end because their servers were saturated: during the study a one-line "Say hi"
request to `qwen3-vl-32b-thinking` and to `mistral-large-4` timed out after 120 s. We stopped them where they were and
report them as partial (`qwen3-vl-32b-thinking` 23 of 80; `mistral-large-4` 54 of 80). Every single-call attempt for them timed out, so they have no single-call
result. 

## Results

Accuracy is the share of the 80 questions answered correctly, with a 95% bootstrap interval (10,000 resamples of the
questions). "Needs exclusion outside question" are the 40 questions whose reference answer requires dropping rows
because of a planted error in a column the question does not use; "Other tasks" are the remaining 40. Seconds and
tokens are per question (median and 90th percentile). Rows with n under 80 are partial.

Table A. Accuracy, single call, scope split, latency and tokens

| Model | n | Agent correct | 95% CI | Single call (B2) | Agent minus B2 | Needs exclusion outside question | Other tasks | Median s | p90 s | Median tokens |
|---|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|
| qwen3-235b-a22b-instruct-2507 | 80 | 100.0% (80) | 100.0 to 100.0 | 52.5% (42/80) | +47.5 | 40/40 | 40/40 | 216 | 307 | 56,402 |
| inkling-small | 80 | 98.8% (79) | 96.2 to 100.0 | 56.2% (45/80) | +42.5 | 39/40 | 40/40 | 45 | 57 | 46,814 |
| qwen3-vl-32b-instruct | 80 | 96.2% (77) | 91.2 to 100.0 | 35.0% (28/80) | +61.3 | 37/40 | 40/40 | 223 | 368 | 57,054 |
| qwen3-30b-a3b-instruct-2507 | 80 | 93.8% (75) | 88.8 to 98.8 | 43.8% (35/80) | +50.0 | 35/40 | 40/40 | 30 | 36 | 59,941 |
| qwen3-coder-30b-a3b-instruct | 80 | 93.8% (75) | 87.5 to 98.8 | 61.3% (49/80) | +32.5 | 35/40 | 40/40 | 101 | 252 | 74,306 |
| qwen35-397b-a17b | 80 | 93.8% (75) | 87.5 to 98.8 | 71.2% (57/80) | +22.5 | 35/40 | 40/40 | 116 | 160 | 49,916 |
| qwen3-30b-a3b-instruct-2507 (original M3 run) | 80 | 92.5% (74) | 86.2 to 97.5 | 43.8% (35/80) | +48.8 | 34/40 | 40/40 | 16 | 21 | 60,166 |
| qwen3-coder-next | 80 | 92.5% (74) | 86.2 to 97.5 | 53.8% (43/80) | +38.8 | 37/40 | 37/40 | 43 | 60 | 74,098 |
| muse-glimmer-30b | 80 | 91.2% (73) | 85.0 to 96.2 | 57.5% (46/80) | +33.8 | 33/40 | 40/40 | 76 | 93 | 82,085 |
| qwen35-122b-a10b | 80 | 90.0% (72) | 82.5 to 96.2 | 58.8% (47/80) | +31.2 | 33/40 | 39/40 | 110 | 166 | 68,534 |
| qwen3-vl-32b-thinking | 23 | 87.0% (20) | 69.6 to 100.0 | n/a | n/a | 4/7 | 16/16 | 379 | 865 | 37,245 |
| gpt-oss-120b | 80 | 83.8% (67) | 75.0 to 91.2 | 60.0% (48/80) | +23.8 | 28/40 | 39/40 | 59 | 95 | 42,975 |
| qwen35-27b | 80 | 83.8% (67) | 75.0 to 91.2 | 62.5% (50/80) | n/a | 28/40 | 39/40 | 69 | 112 | 62,375 |
| qwen36-35b-a3b | 80 | 82.5% (66) | 73.8 to 90.0 | 57.5% (46/80) | +25.0 | 26/40 | 40/40 | 49 | 84 | 42,626 |
| llama4-scout-17b | 80 | 80.0% (64) | 71.2 to 88.8 | 0.0% (0/80) | +80.0 | 27/40 | 37/40 | 15 | 21 | 58,359 |
| beam-1-0 | 80 | 80.0% (64) | 71.2 to 88.8 | 21.2% (17/80) | n/a | 24/40 | 40/40 | 165 | 427 | 27,796 |
| kimi-k2-7-code | 80 | 77.5% (62) | 68.8 to 86.2 | 68.8% (55/80) | +8.8 | 24/40 | 38/40 | 39 | 61 | 26,548 |
| mimo-v2-6-pro | 80 | 77.5% (62) | 68.8 to 86.2 | 71.2% (57/80) | +6.2 | 22/40 | 40/40 | 99 | 256 | 23,939 |
| glm-5-3-flash | 80 | 77.5% (62) | 68.8 to 86.2 | 70.0% (56/80) | +7.5 | 22/40 | 40/40 | 109 | 174 | 18,559 |
| qwen3-235b-a22b-thinking-2507 | 80 | 77.5% (62) | 68.8 to 86.2 | 20.0% (16/80) | n/a | 22/40 | 40/40 | 815 | 1404 | 44,052 |
| glm-5-3-spec | 80 | 76.2% (61) | 66.2 to 85.0 | 68.8% (55/80) | +7.5 | 21/40 | 40/40 | 32 | 47 | 23,900 |
| glm-5-3 | 80 | 76.2% (61) | 66.2 to 85.0 | 66.2% (53/80) | +10.0 | 21/40 | 40/40 | 33 | 56 | 24,272 |
| qwen38-27b | 80 | 76.2% (61) | 67.5 to 85.0 | 65.0% (52/80) | +11.2 | 21/40 | 40/40 | 45 | 98 | 25,775 |
| mimo-v2-6-flash | 80 | 76.2% (61) | 66.2 to 85.0 | 62.5% (50/80) | +13.7 | 21/40 | 40/40 | 46 | 117 | 20,246 |
| qwen36-27b | 80 | 76.2% (61) | 67.5 to 85.0 | 56.2% (45/80) | +20.0 | 21/40 | 40/40 | 61 | 101 | 42,036 |
| qwen-agentworld-35b-a3b | 80 | 76.2% (61) | 67.5 to 85.0 | 45.0% (36/80) | n/a | 21/40 | 40/40 | 586 | 1142 | 55,194 |
| deepseek-v4-1-flash | 80 | 75.0% (60) | 65.0 to 83.8 | 55.0% (44/80) | +20.0 | 20/40 | 40/40 | 69 | 142 | 31,673 |
| qwen3-30b-a3b-thinking-2507 | 80 | 75.0% (60) | 65.0 to 83.8 | 56.2% (45/80) | +18.8 | 20/40 | 40/40 | 121 | 208 | 35,052 |
| granite41-30b | 80 | 72.5% (58) | 62.5 to 82.5 | 46.2% (37/80) | +26.2 | 20/40 | 38/40 | 19 | 28 | 35,192 |
| glm-5-2 | 80 | 72.5% (58) | 62.5 to 82.5 | 65.0% (52/80) | +7.5 | 18/40 | 40/40 | 42 | 76 | 23,136 |
| hemmingway-1-5 | 80 | 72.5% (58) | 62.5 to 82.5 | 48.8% (39/80) | n/a | 18/40 | 40/40 | 355 | 1103 | 24,894 |
| mistral-large-4 | 54 | 72.2% (39) | 59.3 to 83.3 | n/a | n/a | 9/24 | 30/30 | 168 | 667 | 22,719 |
| ornith-1-5-35b-a3b | 80 | 71.2% (57) | 61.3 to 81.2 | 52.5% (42/80) | n/a | 17/40 | 40/40 | 109 | 337 | 33,544 |
| muse-spark-open | 80 | 71.2% (57) | 61.3 to 81.2 | 67.5% (54/80) | +3.7 | 17/40 | 40/40 | 142 | 265 | 35,056 |
| minimax-m3 | 80 | 70.0% (56) | 60.0 to 80.0 | 53.8% (43/80) | +16.2 | 17/40 | 39/40 | 62 | 97 | 26,222 |
| laguna-s-2-1 | 80 | 70.0% (56) | 60.0 to 80.0 | 3.8% (3/80) | n/a | 18/40 | 38/40 | 199 | 540 | 26,772 |
| minimax-m2-7 | 80 | 68.8% (55) | 58.8 to 78.8 | 41.2% (33/80) | n/a | 15/40 | 40/40 | 103 | 257 | 23,942 |
| gemma4-31b-it | 80 | 67.5% (54) | 57.5 to 77.5 | 58.8% (47/80) | +8.8 | 14/40 | 40/40 | 36 | 105 | 33,745 |
| devstral2-123b | 80 | 62.5% (50) | 51.2 to 72.5 | 66.2% (53/80) | -3.7 | 15/40 | 35/40 | 299 | 654 | 37,494 |
| olmo3-32b-instruct | 80 | 58.8% (47) | 47.5 to 70.0 | 3.8% (3/80) | +55.0 | 17/40 | 30/40 | 28 | 43 | 87,740 |
| olmo3-32b-think | 80 | 50.0% (40) | 38.8 to 61.3 | 27.5% (22/80) | n/a | 12/40 | 28/40 | 545 | 1195 | 17,274 |
| olmo3-7b-instruct | 80 | 17.5% (14) | 10.0 to 26.2 | 0.0% (0/80) | +17.5 | 5/40 | 9/40 | 25 | 37 | 128,642 |
| olmo3-7b-think | 80 | 17.5% (14) | 10.0 to 26.2 | 17.5% (14/80) | +0.0 | 2/40 | 12/40 | 542 | 925 | 32,244 |
| llama4-maverick-17b | 80 | 6.2% (5) | 1.2 to 12.5 | 41.2% (33/80) | -35.0 | 1/40 | 4/40 | 35 | 60 | 36,740 |

Table B. Cleaning quality and tool use

| Model | Completed | Detect P | Detect R | Errors handled | Damage | Tool errors / calls | Recovered | Error loops | Approvals (med) | Checked a column outside the question | Stop reasons |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| qwen3-235b-a22b-instruct-2507 | 100.0% | 0.88 | 0.82 | 95.6% | 0 | 0/914 (0.0%) | 0 | 0 | 2.0 | 98.8% | finish 80 |
| inkling-small | 100.0% | 0.92 | 0.81 | 92.7% | 0 | 5/899 (0.6%) | 5 | 0 | 2.0 | 92.5% | finish 80 |
| qwen3-vl-32b-instruct | 100.0% | 0.89 | 0.80 | 90.3% | 0 | 0/927 (0.0%) | 0 | 0 | 2.0 | 90.0% | finish 79, answered_without_finish 1 |
| qwen3-30b-a3b-instruct-2507 | 100.0% | 0.86 | 0.78 | 90.0% | 0 | 0/973 (0.0%) | 0 | 0 | 2.0 | 93.8% | finish 80 |
| qwen3-coder-30b-a3b-instruct | 100.0% | 0.87 | 0.83 | 94.1% | 0 | 14/1056 (1.3%) | 14 | 0 | 2.0 | 97.5% | finish 78, answered_without_finish 2 |
| qwen35-397b-a17b | 100.0% | 0.86 | 0.70 | 93.6% | 0 | 0/890 (0.0%) | 0 | 0 | 2.0 | 87.5% | finish 80 |
| qwen3-30b-a3b-instruct-2507 (original M3 run) | 100.0% | 0.86 | 0.78 | 91.0% | 0 | 0/987 (0.0%) | 0 | 0 | 2.0 | 93.8% | finish 80 |
| qwen3-coder-next | 100.0% | 0.87 | 0.88 | 90.3% | 0 | 0/1055 (0.0%) | 0 | 0 | 2.0 | 96.2% | finish 80 |
| muse-glimmer-30b | 100.0% | 0.87 | 0.87 | 95.2% | 0 | 0/1159 (0.0%) | 0 | 0 | 2.0 | 98.8% | finish 80 |
| qwen35-122b-a10b | 100.0% | 0.83 | 0.64 | 88.2% | 0 | 0/924 (0.0%) | 0 | 0 | 2.0 | 83.8% | finish 80 |
| qwen3-vl-32b-thinking | 100.0% | 0.92 | 0.37 | 61.0% | 0 | 0/156 (0.0%) | 0 | 0 | 1 | 39.1% | finish 23 |
| gpt-oss-120b | 100.0% | 0.92 | 0.64 | 81.2% | 0 | 44/801 (5.5%) | 16 | 10 | 2.0 | 77.5% | answered_without_finish 80 |
| qwen35-27b | 100.0% | 0.86 | 0.65 | 76.5% | 0 | 0/905 (0.0%) | 0 | 0 | 2.0 | 76.2% | finish 80 |
| qwen36-35b-a3b | 100.0% | 0.84 | 0.68 | 85.9% | 0 | 2/866 (0.2%) | 1 | 0 | 2.0 | 93.8% | finish 80 |
| llama4-scout-17b | 97.5% | 0.84 | 0.64 | 82.7% | 0 | 28/890 (3.1%) | 20 | 1 | 2.0 | 88.8% | finish 78, no_tool_calls 2 |
| beam-1-0 | 100.0% | 0.87 | 0.65 | 73.1% | 0 | 0/1056 (0.0%) | 0 | 0 | 2.0 | 56.2% | finish 80 |
| kimi-k2-7-code | 100.0% | 0.86 | 0.58 | 71.7% | 0 | 3/816 (0.4%) | 3 | 0 | 2.0 | 60.0% | finish 80 |
| mimo-v2-6-pro | 100.0% | 0.88 | 0.49 | 65.2% | 0 | 4/756 (0.5%) | 4 | 0 | 2.0 | 27.5% | finish 49, answered_without_finish 31 |
| glm-5-3-flash | 100.0% | 0.93 | 0.45 | 67.2% | 0 | 1/630 (0.2%) | 1 | 0 | 2.0 | 22.5% | finish 80 |
| qwen3-235b-a22b-thinking-2507 | 100.0% | 0.90 | 0.39 | 65.6% | 0 | 0/614 (0.0%) | 0 | 0 | 2.0 | 30.0% | finish 80 |
| glm-5-3-spec | 100.0% | 0.89 | 0.44 | 65.6% | 0 | 1/667 (0.1%) | 1 | 0 | 2.0 | 27.5% | finish 80 |
| glm-5-3 | 100.0% | 0.89 | 0.46 | 66.6% | 0 | 2/678 (0.3%) | 2 | 0 | 2.0 | 27.5% | finish 80 |
| qwen38-27b | 100.0% | 0.88 | 0.50 | 64.9% | 0 | 0/739 (0.0%) | 0 | 0 | 1.0 | 32.5% | finish 80 |
| mimo-v2-6-flash | 100.0% | 0.88 | 0.47 | 64.2% | 0 | 1/774 (0.1%) | 1 | 0 | 1.5 | 22.5% | finish 71, answered_without_finish 9 |
| qwen36-27b | 100.0% | 0.86 | 0.52 | 68.9% | 0 | 11/721 (1.5%) | 11 | 0 | 2.0 | 48.8% | finish 80 |
| qwen-agentworld-35b-a3b | 100.0% | 0.80 | 0.43 | 78.5% | 0 | 0/641 (0.0%) | 0 | 0 | 2.0 | 70.0% | finish 51, answered_without_finish 29 |
| deepseek-v4-1-flash | 100.0% | 0.90 | 0.52 | 65.6% | 0 | 0/832 (0.0%) | 0 | 0 | 2.0 | 45.0% | finish 79, answered_without_finish 1 |
| qwen3-30b-a3b-thinking-2507 | 100.0% | 0.88 | 0.19 | 64.5% | 0 | 0/436 (0.0%) | 0 | 0 | 2.0 | 13.8% | answered_without_finish 73, finish 7 |
| granite41-30b | 100.0% | 0.84 | 0.40 | 68.0% | 0 | 0/619 (0.0%) | 0 | 0 | 2.0 | 46.2% | finish 73, answered_without_finish 7 |
| glm-5-2 | 100.0% | 0.87 | 0.49 | 65.7% | 0 | 5/740 (0.7%) | 5 | 0 | 2.0 | 33.8% | finish 80 |
| hemmingway-1-5 | 100.0% | 0.91 | 0.47 | 63.4% | 0 | 0/707 (0.0%) | 0 | 0 | 1.0 | 22.5% | finish 78, answered_without_finish 2 |
| mistral-large-4 | 100.0% | 0.87 | 0.49 | 61.0% | 0 | 2/543 (0.4%) | 2 | 0 | 1.0 | 29.6% | finish 54 |
| ornith-1-5-35b-a3b | 98.8% | 0.87 | 0.57 | 63.6% | 0 | 10/787 (1.3%) | 10 | 0 | 1.0 | 53.8% | finish 61, answered_without_finish 18, tool_budget_exhausted 1 |
| muse-spark-open | 100.0% | 0.86 | 0.60 | 65.0% | 0 | 1/1029 (0.1%) | 1 | 0 | 1.0 | 55.0% | finish 79, answered_without_finish 1 |
| minimax-m3 | 100.0% | 0.92 | 0.61 | 73.0% | 0 | 1/723 (0.1%) | 1 | 0 | 2.0 | 61.3% | finish 80 |
| laguna-s-2-1 | 100.0% | 0.90 | 0.52 | 64.1% | 0 | 1/699 (0.1%) | 1 | 0 | 1.0 | 28.7% | answered_without_finish 58, finish 22 |
| minimax-m2-7 | 100.0% | 0.90 | 0.49 | 64.9% | 0 | 7/658 (1.1%) | 7 | 0 | 2.0 | 36.2% | finish 80 |
| gemma4-31b-it | 98.8% | 0.92 | 0.44 | 62.9% | 0 | 67/751 (8.9%) | 30 | 2 | 1.0 | 18.8% | finish 79, tool_budget_exhausted 1 |
| devstral2-123b | 100.0% | 0.91 | 0.46 | 60.5% | 0 | 0/725 (0.0%) | 0 | 0 | 1.0 | 27.5% | finish 75, answered_without_finish 5 |
| olmo3-32b-instruct | 91.2% | 0.79 | 0.83 | 84.0% | 0 | 175/1484 (11.8%) | 72 | 13 | 3.0 | 98.8% | finish 48, answered_without_finish 25, tool_budget_exhausted 6, no_tool_calls 1 |
| olmo3-32b-think | 93.8% | 0.87 | 0.29 | 56.2% | 0 | 37/578 (6.4%) | 30 | 2 | 1.0 | 11.2% | finish 75, no_tool_calls 5 |
| olmo3-7b-instruct | 32.5% | 0.80 | 0.70 | 73.9% | 0 | 662/1929 (34.3%) | 238 | 87 | 2.0 | 98.8% | tool_budget_exhausted 29, no_tool_calls 25, answered_without_finish 22, finish 4 |
| olmo3-7b-think | 35.0% | 0.82 | 0.20 | 46.1% | 0 | 280/1084 (25.8%) | 183 | 14 | 1.0 | 22.5% | no_tool_calls 28, finish 27, tool_budget_exhausted 24, answered_without_finish 1 |
| llama4-maverick-17b | 10.0% | 0.88 | 0.32 | 40.8% | 0 | 3/363 (0.8%) | 1 | 0 | 0.0 | 26.2% | no_tool_calls 72, finish 8 |

## Finding 1: one habit explains most of the spread

The planted errors include rows that break a rule in a column the question never mentions: a negative flipper length
when the question counts penguins per island, or a 5,050,000 g body mass when the question asks for bill length. The
reference answers drop those rows, because a record with an impossible value is not trusted. Our prompt says "Check
every column the question uses ... Columns the question does not use can be left alone", and the coverage check only
looks at the question's columns. Models differ in how literally they read that line.

- On the 40 questions that do not need such an exclusion, 30 of the 41 fully run models score 39 or
  40 out of 40 (see the "Other tasks" column).
- On the 40 that do, scores range from 40/40 down to 15/40 for models that call tools reliably (under 5% tool errors, at least 90% of questions completed).
- Across those 34 models, accuracy and "share of questions where the agent ran a check
  on a column the question does not use" have a Spearman correlation of 0.69.
- On `penguins-heldout`, 12 models (`glm-5-3`, `glm-5-3-flash`, `glm-5-2`, `deepseek-v4-1-flash`, `mimo-v2-6-pro`, `mimo-v2-6-flash`, `muse-spark-open`, `granite41-30b`, `hemmingway-1-5`, `ornith-1-5-35b-a3b`, `qwen3-30b-a3b-thinking-2507`, `gemma4-31b-it`) got the same 13 questions wrong, and
  13 of those 13 need rows excluded because of `flipper_length_mm` or `body_mass_g` while the
  question uses neither. On those same questions `qwen3-30b-a3b-instruct-2507` got 10 of 13, `inkling-small`
  12 of 13 and `qwen3-235b-a22b-instruct-2507` 13 of 13 right.

Trace evidence, `penguinsh_01_q0` ("How many penguins were measured on each island?", reference Biscoe 38, Dream 12,
Torgersen 7). `glm-5-3` read the rules, fixed the island spellings, dropped the 2 duplicates, called `analyze` and got
Biscoe 39, Dream 14, Torgersen 7. Its summary says: "Caveats (not relevant to this count, left untouched): 3 negative
flipper_length_mm values (rows 5, 23, 53) violate the 170-235 mm range". It saw the problem and chose not to act,
exactly as the prompt allows. `qwen3-30b-a3b-instruct-2507`, `qwen3-235b-a22b-instruct-2507` and `inkling-small` all
ran `check_out_of_range` on `flipper_length_mm` and proposed `exclude_rows` for rows 5, 23 and 53, which gives the
reference answer.

The thinking variants show the same effect most clearly. With the same weights family, the thinking model is more
literal and scores lower: `qwen3-30b-a3b-instruct-2507` 93.8% (75 of 80) against `qwen3-30b-a3b-thinking-2507` 75.0% (60 of 80); `qwen3-235b-a22b-instruct-2507` 100.0% (80 of 80) against `qwen3-235b-a22b-thinking-2507` 77.5% (62 of 80); `qwen3-vl-32b-instruct` 96.2% (77 of 80) against `qwen3-vl-32b-thinking` 87.0% (20 of 23). The thinking variants checked a column outside the question in far fewer
questions (qwen3-30b-a3b-thinking-2507 14% against 94% for its instruct twin, qwen3-235b-a22b-thinking-2507 30% against 99% for its instruct twin, qwen3-vl-32b-thinking 39% against 90% for its instruct twin).

This is partly a benchmark convention and partly a real design gap. A data analyst would usually drop a record with an
impossible value even if the question does not use that column, and our generator encodes that choice, but the prompt
never says so. The Qwen3 instruct models (which the Milestone 3 prompt was tuned on) happen to do it anyway.

## Finding 2: tool-call reliability separates the bottom of the table

| Model | What goes wrong | Evidence |
|---|---|---|
| `llama4-maverick-17b` | Writes tool calls as text in Llama's own format, which the server does not parse into `tool_calls`. After three nudges the run stops. | 72 of 80 questions end with `no_tool_calls`; 155 nudges. Example turn text: `...I'll check for non-numeric values and out-of-range values.[check_numeric(column="Price")]`. |
| `olmo3-7b-instruct` | Invalid arguments, then repeats them. | 662 tool errors in 1929 calls, 578 of them invalid arguments; 87 runs of three or more failed calls in a row; 29 questions hit the 30-call budget. Example: `analyze` with `"filters": {}` (a dict, schema says list), retried with `{"filter": null}`. |
| `olmo3-32b-instruct` | Adds a `reason` field to checks and to `analyze`, which the schema forbids. | 147 invalid-argument errors; it recovers often (Recovered column) but 25 questions end without calling `finish`. |
| `olmo3-7b-think`, `olmo3-32b-think` | Call `finish` before `analyze`, skip checks, give up. | `finish before analyze` errors; low Detect R. |
| `gemma4-31b-it` | Template tokens leak into arguments, and it invents an `operator` field for filters. | 44 invalid-argument errors, for example `"mapping": {"<\|\"\|>female ...` with the `reason` key swallowed. |
| `gpt-oss-120b` | Never calls `finish` (it answers in plain text after `analyze`), adds `operator` to filters, and sometimes skips the rules file. | All 80 runs end as `answered_without_finish`; 41 invalid-argument errors. The answer still counts because `analyze` ran. |
| `llama4-scout-17b` | Mostly fine; some bad expressions in `check_cross_column` and a few skipped checks. | 28 tool errors, 20 recovered. |
| `qwen36-27b` | Passes the string `"None"` as a number. | `check_out_of_range` with `"maximum": "None"`. |
| `qwen3-30b-a3b-thinking-2507`, `laguna-s-2-1`, `mimo-v2-6-pro`, `qwen-agentworld-35b-a3b`, `ornith-1-5-35b-a3b` | Answer in text instead of calling `finish`. | see the Stop reasons column. The answer is still scored, so this costs little, but the run has no final summary. |

The scaffold absorbs most of these errors. Every bad call comes back to the model as a readable error, and the
"Recovered" column shows how often the next call succeeded. Only models that loop on the same mistake (OLMo3 7B) or
never produce a parsable call (Llama 4 Maverick) fail outright. No model damaged a single clean cell (Damage is 0 in every agent row): the dry run, validator and approval gate held for every model, however badly it planned.

## Accuracy against latency and tokens

Latency was measured while a few hundred requests from this study (and from the other studies sharing the key) were
in flight, so absolute seconds are inflated and depend on how busy each model's server was; the same 30B agent took a
median of 16 s in the original Milestone 3 run and 30 s here. Use the seconds to compare models within this
table, not against earlier runs.

- **Speed.** The models that no other model beats on both accuracy and median seconds are: `llama4-scout-17b` (80.0%, 15 s), `qwen3-30b-a3b-instruct-2507` (93.8%, 30 s), `inkling-small` (98.8%, 45 s), `qwen3-235b-a22b-instruct-2507` (100.0%, 216 s). Llama 4 Scout
  is fastest but 13.7 points behind Qwen3-30B; Qwen3-30B is near the top; Inkling-Small gains 5.0 points
  for about 1.5 times the time; Qwen3-235B is perfect but about 7 times slower than Qwen3-30B. Across all fully run models, accuracy and median
  seconds have a Spearman correlation of only 0.02: slower, bigger and reasoning models are not more accurate here.
- **Tokens.** The token front is `olmo3-32b-think` (50.0%, 17,274 tokens), `glm-5-3-flash` (77.5%, 18,559 tokens), `beam-1-0` (80.0%, 27,796 tokens), `qwen36-35b-a3b` (82.5%, 42,626 tokens), `gpt-oss-120b` (83.8%, 42,975 tokens), `inkling-small` (98.8%, 46,814 tokens), `qwen3-235b-a22b-instruct-2507` (100.0%, 56,402 tokens). Because the agent resends the whole conversation on every turn, tokens
  depend mostly on the number of turns. Reasoning models put several tool calls in one turn, so they use fewer turns
  and fewer tokens (medians per question: `glm-5-3` 8 calls in 5 turns, 24,272 tokens; `mimo-v2-6-pro` 9 calls in 5 turns, 23,939 tokens; `qwen3-30b-a3b-instruct-2507` 12 calls in 12 turns, 59,941 tokens; `qwen3-235b-a22b-instruct-2507` 11 calls in 11 turns, 56,402 tokens), but they are on the wrong side of the scope habit, so the saving
  does not buy accuracy.
- **Speculative decoding.** `glm-5-3-spec` (GLM-5.3 checking drafts from a small model) gave the same accuracy as
  `glm-5-3` (76.2% (61 of 80) against 76.2% (61 of 80)) with a median of 32 s against 33 s under load, so it neither
  helps nor hurts here.

## What DataSage adds over a single call

The "Agent minus B2" column compares each model's agent with the same model's single call on the same 80 questions.
The column is filled only where the single call answered all 80 questions with no API timeout (a timeout counts as a wrong answer, which would flatter the agent). For those 32 models the agent is better for 29, by a median of 19.4 points (from -35.0 to +80.0). The single call also damages clean data: the B2 rows above do not show it, but summing
`damaged_rows + damaged_cells` gives 353 for `qwen3-30b-a3b-instruct-2507`, 70 for `qwen3-235b-a22b-instruct-2507`, 174 for `glm-5-3`, 24 for `gpt-oss-120b`, while every agent row has 0.

Some reasoning models write such long single replies that most of their single calls ran past the 180 s
per-call timeout even after retries (`qwen3-235b-a22b-thinking-2507` 59 of 80; `beam-1-0` 54 of 80; `laguna-s-2-1` 75 of 80 timed out). Their single-call scores mostly measure speed, so we leave
their gain out. The agent never hit this limit for these models, because each of its calls is short.

Models that do worse as agents than as a single call: `llama4-maverick-17b` (-35.0 points), `devstral2-123b` (-3.7 points). Maverick's tool calls are not parsed, so the agent
cannot act, while as a single call it simply writes code. Devstral is a coding model that is good at writing one pandas
script but cleans narrowly when it has to plan with tools. `llama4-scout-17b` is the opposite case: as a single
call it scores 0 of 80 because its reply never parses as JSON (for example "Expecting ',' delimiter"), while as an
agent it reaches 80.0% (64 of 80). Structured tool calls remove a whole class of formatting failure.

## Which model should be the default

Keep `qwen3-30b-a3b-instruct-2507`.

1. It is on the accuracy against latency front and near the top in accuracy (93.8% (75 of 80) in this run, 92.5% (74 of 80) in the
   original Milestone 3 run). Paired on the same questions, the models above it are not clearly better on 80
   questions: `qwen3-235b-a22b-instruct-2507` got 5 questions right that Qwen3-30B missed and missed 0 that it got right (exact McNemar p = 0.06); `qwen3-vl-32b-instruct` got 4 questions right that Qwen3-30B missed and missed 2 that it got right (exact McNemar p = 0.69); `inkling-small` got 4 questions right that Qwen3-30B missed and missed 0 that it got right (exact McNemar p = 0.12).
2. It had zero tool errors in 973 calls and finished every question with `finish`.
3. It has the lowest median latency of the 9 fully run models at 90% or above, which matters for an interactive
   tool where the user approves fixes.

Alternatives: `qwen3-235b-a22b-instruct-2507` when accuracy matters more than waiting (100.0% (80 of 80) here, about 7
times slower), and `inkling-small` as the best non-Qwen model (98.8% (79 of 80) at about 1.5 times the latency). We would not pick a
thinking model: they are slower and, with the current prompt, less accurate.

Caveat on fairness: the Milestone 3 prompt changes were made by reading the 30B model's failures on the dev split, so
the prompt may suit the Qwen3 instruct family better than other families. Finding 1 suggests a single prompt line would
change the ranking of many models.

## What this says about agent design

- **The scaffolding makes small models competitive.** A 3B-active model with tools, checks, a validator and a coverage
  check beats the single call of every model (the best complete single-call run is `qwen35-397b-a17b` with 71.2%) and matches 100B to
  1T parameter models that run the same scaffold. The single call of the same 30B model gets 43.8% (35 of 80).
- **Scaffolding cannot fix a model that cannot speak the tool format.** Tool-call validity is the first thing to
  check when choosing a model; the probe found two broken endpoints, but the full runs found one more (Maverick) and
  two that are unusable in practice (OLMo3 7B, both thinking and instruct).
- **Instructions matter more than model size once tool calls work.** On the questions where the prompt is
  unambiguous, almost every model is near perfect. The remaining errors come from an unstated rule about rows that
  break rules in other columns. Two fixes would remove most of the gap: say in the prompt that rows breaking any rule
  should be proposed for exclusion (the user can still reject it), and let the coverage check run the rule checks on
  every column with a rule, not only the question's columns.
- **Safety held for every model.** No model damaged clean data. Weak models fail by stopping, not by corrupting.

## Limits of this study

- One run per model at temperature 0. The 30B agent scored 75 of 80 in this run and 74 of 80 originally on the
  same 80 questions, so differences of one or two questions are noise.
- Latency was measured under heavy concurrent load (see above), and the laptop running the study crashed once.
  Results that failed for reasons outside the model were deleted and run again: 472 that ended in a client-side
  connection error (the crash), 258 model calls that timed out while the study itself was overloading that
  model's server (256 of them single calls), and 42 single-call scripts that passed their 60 s limit
  while about 100 study processes were starving the laptop's CPU just before the crash. Timeouts were retried once at
  lower load and a second timeout was kept as the result. Every deleted result is listed in
  `eval/results/model_study_reruns.json`. Results that still ended in an API timeout or code timeout after the retry (counted as wrong): `b2-beam-1-0` 54, `b2-hemmingway-1-5` 1, `b2-laguna-s-2-1` 75, `b2-minimax-m2-7` 10, `b2-olmo3-32b-think` 10, `b2-ornith-1-5-35b` 6, `b2-qwen-agentworld-35b` 7, `b2-qwen3-235b-think` 59, `b2-qwen35-27b` 5.
- Partial models: `qwen3-vl-32b-thinking` 23 of 80; `mistral-large-4` 54 of 80. Their accuracy is over the questions they finished, which are not a random sample (the earlier, mostly sales, splits finished first).
- Apart from the two saturated models, every single-call run has all 80 questions.
- Only the 80 held-out and test questions; dev splits not run. The approver is the evaluation oracle, not a person.

## Reproduce

```bash
python -m eval.model_study probe                     # writes eval/results/model_probe.json
python -m eval.model_study_driver agent 48 6          # every datasage-m3-<model> on the four splits, one process
python -m eval.model_study_driver b2 12 6             # every b2-<model>
python -m eval.model_study_driver clean --timeouts    # delete connection errors and timeouts, then run both again
python -m eval.model_study aggregate                  # writes eval/results/study_models.json
python -m eval.model_study table                      # prints the two tables above
python -m eval.model_study_doc                        # fills this file from the template and the results
python -m eval.summarize
```
