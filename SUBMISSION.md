# Problem Set 4 Student Submission

Complete this document with your project details and links. Keep the course instructions in [README.md](README.md) and the required contracts in [ARCHITECTURE.md](ARCHITECTURE.md).

**Student:** Steph Xu  
**GitHub repository:** https://github.com/stephxu96/agentic_ai_pset_04

## Topic and Audience

- **Publication name:** Agentic 3D
- **Topic:** Frontier AI for 3D modeling, CAD, and manufacturing design (design for manufacturing, process planning, quoting, and production-ready geometry), plus intelligent systems that act in physical space, including robotics. AI-native startups are covered when there is substantive evidence.
- **Audience and assumed knowledge:** Technical product managers and engineering leaders deciding where to build on frontier models for spatial, geometric, and manufacturing-design work. They understand LLMs and basic 3D and CAD concepts (parametric vs. mesh, simulation) but do not follow benchmarks or demos daily.
- **Central question:** Which spatial, geometric, and manufacturing-design capabilities moved from demo toward dependable this month, and does the evidence behind each claim match what it claims? When relevant AI-native startups appear, what are they shipping?
- **Scope and exclusions:** 3D modeling, CAD, and manufacturing design lead the series; robotics supports it. Excluded: animation and game content, pure image or video generation, datacenter and training infrastructure, investment advice, and funding news used as evidence (see [`config/editorial_policy.md`](config/editorial_policy.md)).
- **Reason for readers to return:** Each issue applies one test to the month's announcements: what was actually checked, by whom, and under what conditions. Readers get a short, sourced verdict on which claims hold up, without following every demo themselves.

## Published Series

| Piece | Title | Substack article | YouTube video |
| --- | --- | --- | --- |
| 1 | AI Now Writes Design Features and Sets Up Physics Tests | [Article](https://stepuni.substack.com/p/ai-now-writes-design-features-and) | [Video](https://www.youtube.com/watch?v=pICJnOCUzMc) |
| 2 | An AI-Made Design File Is Not a Finished Design | [Article](https://stepuni.substack.com/p/an-ai-made-design-file-is-not-a-finished) | [Video](https://www.youtube.com/watch?v=IdhPfQE0yzY) |
| 3 | CAD Engineering Teams Should Try AI First Where Mistakes Are Easy to Fix | [Article](https://stepuni.substack.com/p/start-where-ai-mistakes-are-easy) | [Video](https://www.youtube.com/watch?v=06Vi4mkEthE) |

**Separate technical demonstration video:** Add link

## Setup and Execution

Document the required tools and versions, installation commands, model or provider choices, and configuration steps. List credential environment variable names without including secret values. Explain how to populate the project configuration, source list, editorial policy, and prompts.

After implementation, the required entry commands are:

```bash
bash run.sh
bash run.sh --package runs/RUN_ID
```

Replace `RUN_ID` with an actual run directory. Add any setup or stage-replay commands a reviewer needs.

### Freshness window

This project uses the assignment's standard 30-day publication window (`freshness_window_days: 30` in `config/project.json`). The pipeline calculates the inclusive window from the run's configuration snapshot and records each item's age in days.

## Architecture and Manual Handoffs

![Agentic 3D pipeline architecture](docs/architecture/architecture_overview.png)

`bash run.sh` snapshots the configuration and prompts into `runs/RUN_ID/`, then runs two workflows: `collect_sources.sh` (collect, extract, store, filter) and `create_series.sh` (select, brief, write, check). Codex CLI is called only in selection, briefs, articles and video scripts (marked CODEX). Evidence lives in `data/`: the SQLite index behind `data/store.sh`, versioned text and transcript segments in `data/assets/`, and local media in `data/media/`. Every stage output and model attempt is saved in the run folder. Publishing starts only after a human approval that matches the content review.

The four phases in detail:

#### 1. Entry point

![Phase 1: entry point](docs/architecture/architecture_1_entry_point.png)

#### 2. Collect sources

![Phase 2: collect sources](docs/architecture/architecture_2_collect_sources.png)

#### 3. Create series

![Phase 3: create series](docs/architecture/architecture_3_create_series.png)

#### 4. Human review and publication

![Phase 4: human review and publication](docs/architecture/architecture_4_review_and_publication.png)

Interactive versions: open [`docs/architecture/architecture_overview.html`](docs/architecture/architecture_overview.html) and [`docs/architecture/architecture_phases.html`](docs/architecture/architecture_phases.html) in a browser.


Add a diagram of your implemented pipeline and explain any additional components or helpers. Show where models are called and where evidence is stored.

### Manual handoffs

| Step | Input files | What happens | Output |
| --- | --- | --- | --- |
| 1. Editorial review | `runs/RUN_ID/articles/NN.md`, `video_scripts/NN.md`, `briefs.jsonl`, stored transcripts | I read the drafts against the stored sources and correct errors. Originals are kept in `docs/original_drafts_RUN_ID/`. | Corrected drafts; `runs/RUN_ID/human_corrections.md` |
| 2. Video production | `runs/RUN_ID/video_scripts/NN.md` (narration, visual directions, sources) | One PowerPoint deck per piece, one slide per scene, with the narration and source URLs in the speaker notes. Each deck opens with a title slide and a spoken executive summary. The voiceover is generated with Chatterbox (Resemble AI's open-source text-to-speech) as a clone of my voice from a 17-second recording, run locally. ffmpeg combines the slides and voiceover into a 1080p MP4. Each video says its narration is AI-generated. | `runs/RUN_ID/presentations/`: decks, `audio/`, `video/`, `preview/`, `timing_cues.md` |
| 3. Substack | `runs/RUN_ID/publish/articles/NN.md` (from `tools/make_publish_copies.py`, which turns claim markers into source links) | I edit each article under my writing rules, then paste it into Substack from `publish/substack/NN.html`. | Three article URLs (above) |
| 4. YouTube | `presentations/video/pieceNN.mp4`; the "Video description" section of `video_scripts/NN.md` | I upload each video and paste the description, which holds the article link and source references. | Three video URLs (above) |

## Evidence and Runs

Link to the retained evidence, editorial decisions, briefs, content checks, and intermediate artifacts needed to inspect the complete workflow. Keep referenced text and transcript files accessible. Explain how to retrieve media omitted from the repository.

| Run | Actual date | Run artifacts and logs | Elapsed time | Approximate cost |
| --- | --- | --- | --- | --- |
| First live run | To complete | Add path or link | To complete | To complete |
| Second live run | To complete | Add path or link | To complete | To complete |

Explain what changed between runs. Identify unknown or estimated costs. Provide the records demonstrating duplicate handling, the date-window checks, and collection failure or recovery. Label any fixture replay or simulated failure.

Trace one published claim to its brief, editorial decision, source version, and exact supporting passage or timestamp.

## Editorial Review

Link to the editorial policy and prompts used. Provide your review of at least three accepted and three rejected or deferred items, comparing the AI's reasons with your own judgment.

Show the policy before and after your revision, the affected stage outputs, and what changed. Record factual corrections, remaining limitations, and the evidence for your final publication approval.

### Human touch: my writing rules

Every article is drafted under my personal writing rules, set out in [`prompts/write_articles.md`](prompts/write_articles.md) under "The author's writing rules". They are inspired by George Orwell's six rules in "Politics and the English Language" (1946), adapted for technical writing about engineering evidence:

| My rule | Orwell's rule |
| --- | --- |
| Omit unnecessary words. | "If it is possible to cut a word out, always cut it out." |
| Prefer simple, precise language over needlessly complex wording. | "Never use a long word where a short one will do." |
| Use active voice when it makes the actor and action clearer. | "Never use the passive where you can use the active." |
| Use technical terms only when necessary; define them for the intended audience. | "Never use a foreign phrase, a scientific word, or a jargon word if you can think of an everyday English equivalent." |
| Avoid clichés and decorative metaphors that do not advance the argument. | "Never use a metaphor, simile, or other figure of speech which you are used to seeing in print." |
| Break these rules when doing so improves precision, clarity, or disciplinary fit. | "Break any of these rules sooner than say anything outright barbarous." |

My main change from Orwell is the exception. His sixth rule allows breaking the others only to avoid barbarous phrasing; mine also allows it for precision and disciplinary fit. For example, "boundary conditions" and "mesh" stay because this audience uses them.

## Reflection

Explain one insight the system produced, one editorial failure or limitation, and the next improvement you would make. Discuss one architectural tradeoff and why your choice fits this project.
