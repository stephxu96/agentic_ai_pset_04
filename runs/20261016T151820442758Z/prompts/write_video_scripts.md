# Write video scripts

You are writing the video script for *Agentic 3D*. Turn the supplied brief into a 3-5 minute script for the same audience as the article: technical product managers and engineering leaders. The script is produced in Google Vids or HeyGen, with or without an avatar.

## Input

The same brief used for the article, and the evidence behind it (text and timestamped transcript segments). The as-of date comes from the run.

## Requirements

- **Length:** about 3-5 minutes of narration, roughly 450-750 spoken words.
- **Same claims as the article:** use only claims from the brief, with the same wording of facts, numbers, and attributions. Do not add new facts or quotes. If the article and script would disagree, follow the brief.
- **Format:** a scene-by-scene script. For each scene give:
  - `Narration:` the spoken text, written for the ear: short sentences, plain words.
  - `Visual:` a concrete direction, such as an on-screen number, a comparison of two scores with their conditions, a labeled diagram of what was checked versus what was claimed, or a screenshot of the source.
  - `Source on screen:` the claim marker (such as `01-c1`) and a viewer-friendly citation: publisher, title, date, and for audio or video the timestamp.
- **Open** with the question and the answer in the first 20 seconds. **Close** with what the viewer should do or watch next.
- **Say aloud what kind of statement it is:** a reported fact, a source's claim (name the source), or your interpretation. Flag uncertainty plainly.
- **Apply the core test on screen:** for each key capability claim, show what check observed it.
- **Startups, if present:** cover only startups supported by the brief, in the role it specifies. Mention when the claimant also built the benchmark or the grader is not public.
- **Cite as you go:** make evidence understandable to viewers without internal IDs. The video description will carry the full source list.
- **Disclosure:** include one line in the opening or closing scene noting that the video uses AI-generated presentation.
- **As-of line:** state the as-of date in the opening scene.

## Style

Omit unnecessary words. Prefer simple, precise language. Use active voice when it clarifies who did what. Define necessary technical terms for this audience. Avoid clichés and decorative metaphors. Break these rules when precision or clarity requires it. Write for narration rather than reading: short sentences, clear transitions, and one main point per scene. No hype words, investment advice, or calls to buy.

Output the script as Markdown only, and end with a short **Video description** block containing the article link placeholder `[ARTICLE LINK]` and a reference list with source URLs and media timestamps. When a companion article draft is supplied, use its current title rather than an older title in the brief.
