# Demo Day plan: poster session, December 2

For: all five of us. Written November 25, 2026.

The poster session is on Wednesday, December 2, during class time. Everyone has to be there in person, and
there is a check-in for attendance. People walk between posters and vote for their favourite, and the Best
Poster Award comes with bonus points. The course is printing the posters: one of us picks ours up at
Monday's lecture (November 30).

Vyshanth agreed this plan at the November 20 review: show a sample file, a plain-English question, one
approval decision and the answer, in about three minutes (`docs/meetings/2026-11-20-review.md`, section 5).

## What to bring

- The printed poster (picked up on November 30).
- One laptop, fully charged, with the charger. Shrey's laptop is the default.
- A phone hotspot in case the room Wi-Fi is slow.
- The backup recording, saved on the laptop itself so it plays without internet.

## Where the demo runs

The live demo runs on the hosted app: https://cse598-group25-datasage.vercel.app. Open it in a browser tab
before the session starts. The **Results** link in the header opens the charts page, which is useful when
someone asks about the numbers.

If the hosted app is slow, run the same app on the laptop instead (needs the repo and the `.env` key):

```bash
cd cse598-group25-datasage
source .venv/bin/activate
python -m app.web.server          # then open http://127.0.0.1:8501
```

On the hosted app an approval card waits 2 minutes and then counts as rejected, and a run stops after
4 minutes. The local app waits 10 minutes. Neither matters for the 8-row demo, which takes about 10 seconds.

## Who does what

A proposal; change it in the group chat if you want.

- **Shrey** drives the laptop and gives the walk-through.
- **Everyone** can give the 30-second pitch below, so the poster is never left empty when Shrey is busy.
- When a question comes up about your own part of the work, take it:
  - Arsha: the acceptance test and Vyshanth's ratings.
  - Maulik: date handling and the refund rule.
  - Vatsal: the repeated runs and the real messy files.
  - Ritik: the cleaning recipes and the stakeholder meetings.

## The 30-second pitch (for people walking past)

> "Messy spreadsheets quietly change answers. A duplicate row or a lowercase label is enough to make a
> total wrong, and nobody notices. DataSage is an LLM agent that checks the file, fixes what it can, asks
> you before any risky change, and then answers your question with a log of every change. On 200
> questions it got 95.5% right. A single LLM call got 46.5%, and DataSage never damaged a valid cell. Want
> to see it on a real file?"

If they say yes, go to the walk-through.

## The 3-minute walk-through

Use the **Sales · 8 rows** sample. It is Vyshanth's own file and the same one in the poster's Example panel,
so people can follow it on the poster while it runs.

**Before you start:** the app is on the start screen, and **Ask me** is selected (it is the default).

**0:00 to 0:30. The problem.** Point at the poster's Example table.

> "This is our stakeholder's sales file. It has eight rows and five problems: order 1004 appears twice,
> 'electronics' and 'accessories' are lowercase, one date says 'not-a-date', and one row sold minus one
> webcam. If you just add up revenue by category, you get four categories instead of two, and Accessories
> is 1,350 because the duplicate is counted twice."

**0:30 to 0:45. Start the run.** Click **Sales · 8 rows**. The run starts at once with the question
"What was total revenue by category?" already filled in.

> "I'm asking it in plain English: what was total revenue by category?"

**0:45 to 1:45. Watch it work and make the approvals.** The *Table* tab shows the file. Problem cells turn
amber as the agent finds them, and fixed cells turn green.

- The lowercase labels are merged on their own. That is a safe fix, so it does not ask.

  > "Fixing the capital letters is safe, so it just does it and records it."

- A card opens under order 1004: remove the duplicate row. Click **Remove**.

  > "Removing a row is risky, so it stops and shows me the exact row first. This one really is a copy, so I
  > say yes."

- A card opens under order 1006, the row with quantity minus one: drop the row. Click **Drop rows**.

  > "Our rules say quantity is at least 1, so this row is wrong. It asks before dropping it. I agree."

- Sometimes it also asks to blank the bad date in order 1005. Click **Keep as is**.

  > "This one doesn't affect revenue, so I'll keep it. It stays in the report as a caveat."

**1:45 to 2:30. The answer.** The *Answer* tab opens by itself when the run ends.

> "Electronics 2,245 and Accessories 830. Two categories, no double counting, and the minus-one row is
> gone. That matches the poster. Every change is listed here with who approved it."

Expected answer: **Electronics 2,245, Accessories 830** (checked on November 25: two runs on the 30B model,
both gave this answer in about 10 seconds with 2 approvals asked). If you click Keep on the minus-one row
instead, Electronics is 2,185. That is fine too: say the row was kept and is listed as a caveat.

**2:30 to 3:00. Trust and replay.** Click **View** on `report.md`, then on `replay.py`.

> "The original file is never changed. You get the cleaned file, a report of every change, and a plain
> pandas script that repeats the same cleaning without the AI. So you can check it, or run it again on
> next month's file."

Then, if there's time, open the *Data health* tab ("the answer before cleaning next to the answer
after").

## Four more scenarios to run

Use these after the main walk-through, or instead of it for someone who has already seen it. Two use
different files and two ask a different question of the same 8-row file. All four were run on
November 25 with the 30B model and gave the answers below, each in 11 to 14 seconds. Use *Ask me* mode
and make the decisions listed, so the answers match.

### Scenario 1: a different file (HR, 407 rows)

- **How:** click *New run*, then **HR · 407 rows**. The question fills in: "What is the average salary by
  department?"
- **What it finds:** 7 duplicate rows, 14 department names spelled or capitalised wrongly, salaries written
  as text ("$65,000"), and 4 salaries above the $400,000 limit (an extra zero, such as 735000).
- **Cards and decisions:** **Remove** the duplicates, **Merge** the department names, **Drop rows** for the
  4 salaries over the limit. The text salaries are converted on their own (a safe fix).
- **Expected answer:** Engineering 130,027.03, Finance 100,993.24, Marketing 88,243.24, Operations
  62,343.37, Sales 82,280.22.
- **What to say:** "Four people have an extra zero on their salary. Leave them in and the Operations average
  jumps. It asks before dropping them, and it shows me exactly which ones."

### Scenario 2: a different file (inventory, 606 rows)

- **How:** click *New run*, then **Inventory · 606 rows**. The question: "What is the total stock value by
  warehouse?"
- **What it finds:** 6 duplicate rows, 12 warehouse names spelled wrongly, 18 rows with negative units on
  hand, and 5 rows where Stock_Value is 100 times too big (it should be Units × Unit_Cost).
- **Cards and decisions:** **Remove** the duplicates, **Merge** the warehouse names, **Drop rows** for the
  18 negative-unit rows, **Recompute** the 5 wrong stock values.
- **Expected answer:** Mesa 844,651.20, Phoenix 1,156,928.05, Tempe 936,441.60, Tucson 1,286,821.70.
- **What to say:** "Here it uses the formula in the rules file to catch five values that are 100 times too
  big, and fixes them from the other two columns instead of deleting the rows."

### Scenario 3: a different question (units by region, 8-row file)

- **How:** right after a run on **Sales · 8 rows**, click *New run*. The 8-row file stays selected. Replace
  the text in the question box with "What was the total quantity sold in each region?" and press **Run**.
  (Clicking the sample button again would start at once with the usual question.)
- **Cards and decisions:** **Remove** the duplicate (order 1004), **Drop rows** for the minus-one row
  (order 1006). It may also ask to blank the empty Region in order 1007: click **Keep as is**.
- **Expected answer:** East 5, North 4, South 2, West 5.
- **What to say:** "Now the question uses Region, so it checks Region. Order 1007 has no region, so its
  2 units can't go in any group. The report says it used 5 rows and lists that row, so nothing disappears
  silently."

### Scenario 4: a different question (average price, 8-row file)

- **How:** same as Scenario 3, with the question "What was the average price in each category?"
- **Cards and decisions:** **Remove** the duplicate, **Drop rows** for the minus-one row.
- **Expected answer:** Electronics 335, Accessories 130.
- **What to say:** "Same file, different question. The duplicate Monitor would pull the Accessories average
  up to about 217, and the lowercase labels would split each category in two. After cleaning it's 130."

If a visitor asks their own question, type it in the same way. Questions about totals, counts or averages
by one column work best, since those are what DataSage was built and tested for.

## If someone wants more

- **The numbers:** open the **Results** page. Point at the ablation chart: with approvals turned off,
  accuracy falls from 95.5% to 12.0%, so asking the user is what holds the system up.
- **A bigger file:** run **Sales · 1,208 rows** in **Auto** mode (click *New run*, choose Auto). It applies
  every fix without asking, and the run takes longer, so start it and keep talking.
- **Their own file:** they can drop any CSV or Excel file on the start screen. Warn them that the hosted
  app is public, so they should not use private data.

## If something goes wrong

| What happens | What to do |
|---|---|
| The hosted app is slow or won't load | Switch to the local app (commands above) on the hotspot |
| The model service is down or errors (ASU RC) | Play the backup recording |
| The run asks something unexpected | Read the card out loud, decide like a user would, and explain why. That is the point of the approval gate |
| The answer is different from 2,245 / 830 | Open the report and walk through the changes; say which approval made the difference |
| Nothing works | Show the recorded run in `docs/final/demo/` (`report.md`, `console.txt`) and the poster's Example panel |

## The backup recording

Record it by **November 30**, on the hosted app, following the walk-through above. On a Mac, press
Cmd+Shift+5 and pick "Record Selected Portion" around the browser window.

- Keep it under 3 minutes, with no sound (the room will be loud; we talk over it).
- Save it on the demo laptop and in the team's shared folder. Do not commit it to the repo (video files are
  large).
- Check that it shows both approval cards and the final answer.

## Questions people may ask

- **"Why not just ask ChatGPT?"** We tested that (one LLM call with no tools): 46.5% right, and it changed
  119 valid cells. DataSage got 95.5% and changed none.
- **"Which model?"** Qwen3-30B on ASU's Research Computing service, about 15 seconds a question. We
  tried 41 models as the planner. For the 32 that we could also test as a single call, the agent design
  added a median of 19 points.
- **"Does it work on big files?"** On 40 hard questions with 343 to 1,935 rows it got 90%, and 100% after
  we fixed a grouping bug.
- **"What does it get wrong?"** Almost every miss is a row that breaks a rule in a column the question
  does not use. Our stakeholder chose to check only the question's columns, so those rows stay. Also, the
  written summary can sometimes describe a rejected fix wrongly, though the change log is always right.
- **"Did a real user try it?"** Yes. Our stakeholder's acceptance test: 12 of 12 questions right on his two
  files and a test table, with no valid cell changed. He rated 10 reports: correctness 5.0, clarity 4.4,
  trust 4.6 out of 5.
- **"What is the agent pattern?"** A ReAct-style loop: the LLM picks the next check or fix as a tool call,
  pandas runs it, and a validator and coverage check run before it answers.

## Checklist

- [ ] November 30, Monday lecture: pick up the printed poster.
- [ ] By November 30: backup recording made and copied to the laptop and the shared folder.
- [ ] December 1: one full rehearsal of the walk-through, timed.
- [ ] December 2, morning: open the hosted app and run the 8-row sample once, to check the model service
      and the key quota.
- [ ] December 2: everyone checks in at the session.

## Not known yet

- How long the session lasts, and whether judges visit on a schedule.
- Whether there is power or Wi-Fi at each poster.
