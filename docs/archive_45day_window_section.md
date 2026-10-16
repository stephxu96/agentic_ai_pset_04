# Freshness window (paste under "Evidence and Runs", with the date-window checks)

Keep the written approval in the repo (a saved email or message) so a grader can see it.

**Approved adjustment to the assignment:** The README sets a 30-day freshness window for substantive source material. This project's live runs use a **45-day** window (`freshness_window_days: 45` in `config/project.json`). Course staff approved this: **[NAME, DATE, and where the approval is recorded, e.g. a saved message in docs/window_approval.md or a Canvas link]**.

**Why I chose 45 days:**
[Write your real reason here, in your own words. Use only reasons that are true. Observations from my source check on Oct 14, 2026 that you may cite if they match your thinking:]
- The a16z Show episode on World Labs and 3D AI aired Sept 13, 2026, two days outside a 30-day window for an Oct 14 as-of date.
- The Lex Fridman Podcast releases about twice a month, and its latest episode at that date (Sept 17) was off-topic.
- Autodesk University 2026 coverage (Sept 15-17) leaves a 30-day window within days of the run date, before a second run.

**What I did to keep the effect visible and bounded:**
- The window length is read from each run's config snapshot and recorded in `run.json` and the filter receipt.
- Each item records its age in days, so items older than 30 days are identifiable.
- The `filter_items.sh` component prints a warning when a live run uses a window other than 30 days.
- **Effect on the minimums:** [After your runs, state whether the 12 items / 6 independent sources / 2 per input type are met using only items within 30 days. If not, say how many depend on items 31-45 days old.]

**Records:** exclusion records for `outside_window` items are in `runs/RUN_ID/exclusions.jsonl` for both live runs. [Add the path or link to any replay run that used a different window.]
