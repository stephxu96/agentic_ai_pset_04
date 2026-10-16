# Human corrections to run 20261016T164638172713Z

Applied 2026-10-16 at Steph Xu's instruction, after reading the drafts against the stored transcripts. Originals are in `docs/original_drafts_20261016T164638172713Z/`.

| Piece | Change | Why |
| --- | --- | --- |
| 02 (article, script, brief claim 02-c8) | "63 RoboDojo tasks went unsolved by all evaluated models" became "five frontier models ... 84 Robot World tasks ... 63 of those tasks went unsolved by any of them" | Factual error. In the episode 010 transcript (segments s0004-s0005), the 63 of 84 result belongs to the Robot World paper. RoboDojo is a different benchmark mentioned elsewhere in the episode. |
| 02 (article) | Removed "No accepted YouTube evidence is supplied here." | Pipeline-internal wording, not a reader-facing limitation. |
| 03 (article, script) | Title "Pilot the Periphery Before Trusting the Record" became "Pilot Where Mistakes Are Easy to Undo" | Vague title. |
| 01 (brief, article, script) | Added inference claim 01-c7 (Onshape and SimScale place AI at different engineering handoffs) and its marker | The piece's main insight connects two publishers and had no explicit inference claim. Evidence reuses the quotes already verified for 01-c1 and 01-c4. |
| All | `review/check_content.py` and `tests/validate_run.py` now count article body (no references or claim markers) and video narration only | The old counts included references, markers and the Visual and Source-on-screen lines, producing false length warnings. Original narration was 610, 484 and 566 words (about 4.1, 3.2 and 3.8 minutes), inside the 3-5 minute target. |
| All | `tools/make_publish_copies.py` writes `publish/articles/NN.md` with claim markers turned into numbered inline source links | Substack readers need links, not claim IDs. Reviewed drafts are unchanged. |

Still to verify by ear before publishing: every cited audio or video timestamp (transcripts are automatic and can be wrong).
