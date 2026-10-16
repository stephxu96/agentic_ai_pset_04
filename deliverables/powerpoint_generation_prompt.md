# Prompt for a professional PowerPoint generation tool

Create three polished, editable 16:9 PowerPoint presentations to accompany three narrated engineering-intelligence articles. Also generate one voiceover audio track per presentation if your tool supports voice generation. A rendered video is **not** required.

## Source files

The project root is:
`/Users/stephxu/Documents/1.125/ps04/ps04-agentic-cad-journal`

Use these six files as the required inputs. If you are a cloud tool without access to local files, ask me to upload them before generating anything. Do not infer their contents from the filenames.

| Piece | Publication article, with linked references | Video script, with exact narration and visual directions |
| --- | --- | --- |
| 1 | `runs/20261016T164638172713Z/publish/articles/01.md` | `runs/20261016T164638172713Z/video_scripts/01.md` |
| 2 | `runs/20261016T164638172713Z/publish/articles/02.md` | `runs/20261016T164638172713Z/video_scripts/02.md` |
| 3 | `runs/20261016T164638172713Z/publish/articles/03.md` | `runs/20261016T164638172713Z/video_scripts/03.md` |

For deeper editorial context, the same run has `runs/20261016T164638172713Z/briefs.jsonl`. The publication articles and scripts take precedence for this task. They are three **distinct arguments from the same October 16, 2026 run**, not three historical weekly snapshots.

## Deliverables

Produce three separate `.pptx` files: 7 slides for piece 1, 8 for piece 2, and 7 for piece 3. Each script scene maps to exactly one slide, in order. Do not add extra cover or closing slides. Put the scene's **exact narration** in that slide's speaker notes. If supported, generate three separate voiceover files from that narration and align slide changes to the actual audio. Otherwise, provide the decks and per-slide timing cues; do not claim audio was generated.

Keep each presentation between 3 and 5 minutes. The suggested windows below assume about 145 spoken words per minute. Adjust them to the actual synthesized or recorded voice, especially where pauses are needed; keep the scene order and factual meaning unchanged.

| Slide | Piece 1 | Piece 2 | Piece 3 |
| ---: | --- | --- | --- |
| 1 | 00:00–00:33 | 00:00–00:21 | 00:00–00:24 |
| 2 | 00:33–01:10 | 00:21–00:47 | 00:24–00:56 |
| 3 | 01:10–01:40 | 00:47–01:12 | 00:56–01:33 |
| 4 | 01:40–02:07 | 01:12–01:37 | 01:33–02:10 |
| 5 | 02:07–02:47 | 01:37–02:05 | 02:10–02:50 |
| 6 | 02:47–03:40 | 02:05–02:40 | 02:50–03:21 |
| 7 | 03:40–04:13 | 02:40–03:05 | 03:21–03:54 |
| 8 | — | 03:05–03:29 | — |

## Editorial and visual direction

Design for an informed but non-specialist audience interested in AI for CAD, simulation, robotics, and engineering workflows. Make the slides visual companions to the voice, **not transcripts on screen**. Each slide needs one clear visual idea: an accurate workflow diagram, a carefully labeled comparison, a specific test result, or a restrained evidence graphic. Use authentic, licensed source screenshots or editable technical diagrams where useful. Do not fabricate product interfaces, CAD outputs, robot tests, or photographs as if they were evidence. Avoid generic robot imagery and repeated card-grid templates.

Use a consistent, professional editorial system across the three decks, but let each argument look different:

- Piece 1: show the handoffs from natural-language request to FeatureScript and from CAD model to simulation setup. Distinguish product claims from validation evidence.
- Piece 2: make the successful STEP mass checks and the failed or partial native/multibody checks easy to compare. Show the MIT-CDFG survey figures with their caveats. Label podcast-transcript figures as unverified secondary reporting where the script does.
- Piece 3: show the increasing consequence of discovery, simulation preparation, and writing to a PLM system of record. Make the human approval boundary unmistakable. Keep the World Labs–AMD transaction separate from capability evidence.

Use short, precise headlines and minimal on-slide text. The existing scripts contain important distinctions between reported fact, source claim, and editorial inference; preserve them. Preserve all material uncertainty and limitations. Do not strengthen a claim, invent a result, or imply physical validation where only a product description, simulation test, or transcript is available. Put readable source names and dates on the relevant slides and full URLs in speaker notes. The publication articles contain linked references; use them as the citation source.

The decks should remain editable. Use native PowerPoint text, diagrams, tables, and charts where possible. Check every slide for legibility at presentation size, clean alignment, and evidence-to-narration fit. Export a slide contact sheet or PDF preview for review alongside the three `.pptx` files. Do not publish, upload to YouTube, or add article/video URLs on my behalf.
