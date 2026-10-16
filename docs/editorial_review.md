# Editorial review: Agentic 3D

Linked from `SUBMISSION.md` ("Editorial Review").

## Files reviewed

- Policy, version 1 (Oct 15 test run): `runs/20261015T202519414242Z/config/editorial_policy.md`
- Policy, version 2 (both live runs): `runs/20261016T153413218193Z/config/editorial_policy.md` and `runs/20261016T164638172713Z/config/editorial_policy.md`
- Prompts: `runs/20261015T202519414242Z/prompts/`, `runs/20261016T153413218193Z/prompts/` and `runs/20261016T164638172713Z/prompts/` (the brief prompt was revised between the two live runs)
- Decisions reviewed: `runs/20261015T202519414242Z/decisions.jsonl` (test run under version 1: 6 accepted, 9 rejected, 4 deferred) and `runs/20261016T164638172713Z/decisions.jsonl` (second live run under version 2: 13 accepted, 7 rejected)

## Accepted items

The AI's reason is quoted from `decisions.jsonl` (first two sentences).

| Item | AI's reason | My judgment | Agree? | Evidence I checked |
| --- | --- | --- | --- | --- |
| `feed:https://www.engineering.com/?p=151563`<br>engineering-com, 2026-09-30<br>*Welcome to the vibe-CAD era* (second live run) | This is a fresh, highly relevant CAD item: an independent engineering publication tested Backflip’s new drawing-, photo-, and video-to-CAD modalities on September 30. The strongest claims were checked rather than merely viewed: the reviewer imported downloaded STEP files into Fusion, applied 1060 aluminum, and found two TooTallToby drawing conversions exactly matched the target mass; it also documents a multibody failure and incomplete feature-tree imports. | Right call: an independent publication ran its own tests and reported failures as well as passes. | yes | "I can verify that Backflip got it exactly correct." (stored article text) |
| `feed:https://www.onshape.com/en/blog/featurescript-mcp-server-use-cases-text-code-cad`<br>onshape, 2026-09-30<br>*5 Ways Teams Can Leverage the Onshape FeatureScript MCP Server* (second live run) | This is a fresh, directly relevant commercial CAD source: Onshape says its FeatureScript MCP Server lets LLMs generate, debug, and refine parametric custom features from natural-language requests, including standards-encoded geometry and analysis integrations. It is quotable and supports an attributed account of what Onshape is building, but the examples are vendor claims; the article does not disclose test cases, success rates, or independent checks of whether generated features preserve manufacturability or analysis validity. | Right call: a relevant commercial source, used only as "Onshape says". | yes | Onshape's Sept. 30 post: the server lets LLMs generate custom features from natural-language requests |
| `podcast:https://physicalaipodcast.co/episodes/010`<br>physical-ai-podcast, 2026-10-10<br>*AI Models Fail 63 of 84 Robot Tasks, Waymo Borrows $5B* (second live run) | This fresh, timestamped episode is relevant robotics context for agentic physical systems: at 00:00:28 it reports that no evaluated model solved 63 of 84 Robo Dojo tasks, and at 00:03:34–00:03:41 it describes task-specific failure differences. The external check confirms the underlying RobotWorld study used executable success checks, retained one outcome per model-task pair, and interaction budgets, so the claim supports a bounded simulation result rather than real-robot reliability. | Right call: relevant robotics context on what a single combined score hides. | yes | Transcript 00:02:47–00:02:51 and 00:03:48–00:03:55 |

Note on the third item: the AI's reason for episode 010 credits the 63-of-84 result to "Robo Dojo". The transcript ties it to the Robot World paper; this is the error I later corrected (see Factual corrections).

## Rejected or deferred items

| Item | Decision | AI's reason | My judgment | Agree? |
| --- | --- | --- | --- | --- |
| `podcast:https://physicalaipodcast.co/episodes/009`<br>physical-ai-podcast, 2026-10-03<br>*Atlas Loses Its Pinky, Only One Humanoid in Eight Walks* (test run) | defer | The dated excerpt raises relevant physical-AI questions about hand design, world-action-model generalization, and human control in a factory demo, but these are currently unsupported podcast assertions. No primary sources, experimental conditions, audio timestamps, or reproducible checks are supplied, and the transcript may garble technical details; defer until those claims can be traced to observed evidence. | Should have been accepted: the transcript had quotable, timestamped passages (07:28–07:35). Accept it with an automatic-transcript caveat. This led to the deferral change in version 2. | no |
| `youtube:Lnex2Q9bpvQ`<br>ptc, 2026-10-15<br>*Add Custom Features in Onshape 🛠️* (test run) | reject | The item explains an existing Onshape custom-feature workflow, including published Feature Studios and examples such as threads and laser-cut preparation, but does not identify a new release or newly observed evidence. Its generic claim that custom features can speed workflows has no measured conditions or comparison. | Explains an existing workflow; no new release or new evidence. | yes |
| `youtube:O8rLfw06qOo`<br>autodesk, 2026-10-15<br>*Nearly 5x Faster Machining: Inside Uni-Fab* (second live run) | reject | Although fresh, quotable, and relevant to manufacturing software, this Autodesk customer video describes conventional Fusion CAD/CAM workflow rather than a frontier AI capability for 3D modeling, manufacturing design, or physical-space systems. Uni-Fab reports reducing one part's runtime from three and a half hours to 45 minutes with 3D toolpaths and two setups (00:01:28–00:01:39), but the video supplies no AI-generated or AI-checked engineering decision and no disclosed conditions or independent check for the vendor-adjacent performance claim. | Conventional CAD/CAM; the "5x faster" claim involves no AI design decision. | yes |
| `podcast:a4ae7f12-bc4d-11f1-bf0c-1fda5ade33f6`<br>twiml, 2026-09-29<br>*From Math Olympiads to Navier-Stokes: How Fast Is AI Progressing? with* (second live run) | reject | Although fresh and timestamped, this episode concerns general AI progress in mathematics rather than 3D modeling, CAD, manufacturing-design decisions, or robotics tied to geometry, simulation-ready assets, or verification. Its discussion of Navier–Stokes is also an attributed, automatically transcribed account of reported work (for example 00:32:43–00:33:40), not evidence that establishes a relevant physical-space capability under stated checks and conditions. | General AI progress in mathematics; outside the topic. | yes |

Note on the first item: episode 009 was deferred in the Oct 15 test run and accepted in both live runs after the policy change below.

## Policy revision

**What the review showed:** My first topic was too narrow, and manufacturing news moves slowly, so the Oct 15 test run had little to work with. It deferred timestamped podcasts with quotable passages (episode 009 among them) and treated vendors' own claims as too weak to use. I asked what actually matters to the audience: what vendors are shipping, labeled as their claims, and manufacturing-design decisions where AI produces or checks geometry, process or cost. I widened the scope and changed the sources (added `engineering-com-ai`, `onshape-blog`, `twiml-ai-podcast`, `world-labs`; removed `cadalyst`, `xometry-blog`, `yt-onshape`), and kept the assignment's standard 30-day window.

**Policy before and after** (full diff: `diff runs/20261015T202519414242Z/config/editorial_policy.md runs/20261016T164638172713Z/config/editorial_policy.md`):

| Policy section | Version 1 (before) | Version 2 (after) | Why |
| --- | --- | --- | --- |
| Relevance | 3D modeling, CAD, or intelligent physical systems; "Include AI-native startup products" | Adds manufacturing design (design for manufacturing, process planning, quoting, production-ready geometry); startups considered only "when there is relevant, checkable evidence" | The first topic was too narrow; manufacturing-design decisions matter to this audience. |
| Weighting | 3D modeling and CAD lead, robotics supports | Manufacturing design added to the lead; generic factory-automation news with no AI design decision is rejected | Manufacturing design leads alongside CAD, but generic factory news with no AI decision stays out. |
| Freshness | 45-day window (test run) | The assignment's standard 30-day window | Kept the assignment's standard 30-day window for the live runs. |
| Credibility | "Treat unsupported claims as source claims" | Commercial voices are "a required perspective": a company's own claim is usable evidence of what it says and plans, if dated, quotable and labeled | What vendors ship matters to the audience; label their claims instead of dropping them. |
| Credibility | Separate companies not addressed | Separate companies announcing their own products are separate claims; together they show where the market is betting, not that the technology works | Several companies building on the same technology shows where the market is betting; each counts as its own claim. |
| Deferral | "Defer, do not reject, items that look promising but lack a checkable passage or timestamp" | Defer only items with no quotable passage or timestamp, duplicates, or relevance depending on unpublished evidence; do not defer a commercial item only because its numbers lack a disclosed method | The test run deferred useful, quotable podcasts such as episode 009. |
| Startup watch | Each piece features one or two AI-native startups | Startups optional; do not add one to fill a slot | There was not enough startup evidence to feature one in every piece. |

Configuration changed with it (`config/project.json`): manufacturing design added to the topic, audience and central question; `freshness_window_days` 45 to 30; `max_items_per_source` 3 to 2.

**Affected stage outputs:**

- `decisions.jsonl`: the test run deferred four podcast episodes (Physical AI Podcast episodes 008, 009 and 010, and Changelog's NVIDIA episode). Both live runs accepted all four and deferred nothing.
- `briefs.jsonl`, `articles/`, `video_scripts/`: the test run stopped at the brief stage (a Codex CLI error, since fixed). The first live run produced three briefs, articles and scripts, but all three pieces made one argument. After I revised the brief prompt to keep the pieces distinct, the second live run produced three different arguments from the same evidence.
- Commercial sources: the live runs accepted Autodesk (via Engineering.com), SimScale, two Onshape posts and World Labs, each labeled as the company's own claim in the drafts.

## Trace of one published claim

Claim `02-c1`, traced from the published sentence to the exact source passage in `SUBMISSION.md` → Evidence and Runs → "Trace of one published claim".

## Factual corrections

From `runs/20261016T164638172713Z/human_corrections.md`. The original drafts are in `docs/original_drafts_20261016T164638172713Z/`.

| Piece | What was wrong in the draft | Correction | Source |
| --- | --- | --- | --- |
| 02 | "63 RoboDojo tasks went unsolved by all evaluated models" | "five frontier models ... 84 Robot World tasks ... 63 of those tasks went unsolved by any of them" (brief claim 02-c8, article, script) | Episode 010 transcript, segments s0004–s0005: the result belongs to the Robot World paper |
| 02 | "No accepted YouTube evidence is supplied here." | Removed | Pipeline wording, not a reader-facing limitation |
| 03 | Title "Pilot the Periphery Before Trusting the Record" | Retitled (published as "CAD Engineering Teams Should Try AI First Where Mistakes Are Easy to Fix") | Vague title |
| 01 | The main insight connected two publishers but had no inference claim | Added inference claim 01-c7 | Reuses the verified quotes for 01-c1 and 01-c4 |

Before publication I also rewrote all three articles under my writing rules, keeping every citation, number and attribution, and checked the published wording against the sources.

## Remaining limitations

- Onshape, SimScale, NVIDIA and Autodesk are describing their own products; no source gives independent customer results.
- The Backflip evidence is one publication's tests on three simplified drawings; nothing covers tolerances, assemblies, manufacturing or inspection.
- Podcast figures come from automatic transcripts and were not checked against the underlying studies or audio.
- Missing perspectives: customers and working engineers.

## Evidence for final publication approval

- `runs/20261016T164638172713Z/review.json`: `review_id` `ae074c7b7e194db08599ce0784d7a474290db17e287d404c570e245c9c9ea809`, `passed: true`, no issues.
- `runs/20261016T164638172713Z/approval.json`: `decision: approve`, reviewer Steph Xu, 2026-10-16T23:33:25Z, matching `review_id`. `bash run.sh --package` then built `package/`, and the run's status is `ready_for_production`.
- What I verified before approving: I read all three articles and scripts against the stored sources and transcripts, made the corrections above, and checked that every published number and citation matches its source.
