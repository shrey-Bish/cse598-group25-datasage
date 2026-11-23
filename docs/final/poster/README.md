# Poster

`Group25_Poster.pdf` is the print-ready poster: one page, 24 × 36 in portrait, as the course asks. Arsha checks
every number (task A3 in `docs/TEAM_HANDOFF.md`) and Shrey submits it on Canvas by Nov 23, 2:00 PM.

The design started from a Claude Design export (spreadsheet theme) and was then edited by hand: the real
example from the stakeholder's file, our references and citations, the charts rebuilt as HTML tables with bars,
and the app screenshot replaced by a close-up of an approval card.

| File | What it is |
|---|---|
| `Group25_Poster.pdf` | The poster to submit |
| `poster.html` | Its source: one HTML page at 2400 × 3600 px, printed at 96% onto 24 × 36 in. Edit this file |
| `support.js`, `image-slot.js` | Page scripts from the Claude Design export; `poster.html` needs them next to it |
| `figs/app_card.png` | The approval card in the Example section (taken from the running app, 1,208-row sample) |
| `figs/qr_repo.png` | QR code to this repository |
| `make_figs.py` | Rebuilds the QR code and the earlier figures (`fig_accuracy.png`, `fig_parts.png`, `fig_models.png`) from the result files; the current layout draws its charts in HTML instead |
| `previous/` | The earlier poster (`poster_v1.html`, `Group25_Poster_v1.pdf`) and the untouched Claude Design export, for comparison |

Where each number comes from:

| On the poster | Source |
|---|---|
| 95.5% of 200 questions, the 95% range 92.0–98.5, B0/B1/B2 on 200, every ablation row | `eval/results/study_scale_ablations.json`, `docs/final/findings_scale_and_ablations.md` |
| 40 hard questions: B1 10%, B2 55%, DataSage 100% with the grouping fix (90% before) | `eval/results/summary.md` (`sales-hard`, `penguins-hard`), `eval/results/fix_groupby/`, `docs/final/findings_hard.md` sections 3 and 10 |
| 32 models (of 41) with a single-call comparison, a median 19 points (19.4) over a single call | `eval/results/study_models.json`, `docs/final/findings_models.md` |
| Example table and its answers (raw: 4 groups; cleaned: Electronics 2,245, Accessories 830) | `baseline/examples/messy_sales.csv` with `examples/messy_sales_rules.json` |

## Changing it

Edit `poster.html`, then print it again with Chrome (macOS path shown; needs internet for the fonts):

```bash
cd docs/final/poster
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --no-pdf-header-footer \
  --allow-file-access-from-files --virtual-time-budget=10000 \
  --print-to-pdf=Group25_Poster.pdf "file://$PWD/poster.html"
pdfinfo Group25_Poster.pdf | grep "Page size"     # must say 1728 x 2592 pts (24 x 36 in)
```

Check the bottom line ("Thanks to our stakeholder…") is fully visible after any text change: the page has a
fixed height and longer text pushes it under the bottom bar.
