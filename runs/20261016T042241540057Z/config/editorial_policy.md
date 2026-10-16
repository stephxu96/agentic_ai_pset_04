# Editorial Policy: Agentic 3D

This policy is supplied to the AI during selection and synthesis. It is snapshotted into each run.

## Core test

A capability claim holds only as far as the check that observed it. A valid solid does not prove a part is manufacturable. A good-looking scene does not prove its dimensions are right. A simulation score does not prove physical transfer. For every claim, ask: what was actually checked, by whom, and under what conditions?

## Relevance

Accept items that help a technical product or engineering leader decide whether to build on a frontier-model capability for 3D modeling, CAD, or intelligent systems acting in physical space (including robotics). Consider AI-native startup products and releases when there is relevant, checkable evidence, but do not require startup coverage. Prefer items that change what is feasible, what is verified, or what a buyer or builder could check themselves.

Weighting: 3D modeling and CAD lead the series, and robotics supports. Accept robotics items when they bear on the same questions (geometry, simulation-ready assets, what was actually verified) or are a major development for AI-native startups, and keep robotics in a supporting role within each piece.

## Freshness

- The as-of date is the run's `as_of_date`. The window length comes from `freshness_window_days` in the project config (45 in this project; the assignment's standard is 30, and course staff approved this adjustment, as documented in SUBMISSION.md). The window runs from the as-of date minus (N - 1) days through the as-of date, in UTC, so 45 days gives as-of minus 44 days through as-of. Every item records its age in days so material older than 30 days stays identifiable.
- Undated material is never evidence.
- A reposted recording, or an unchanged article with a refreshed date, is not a new development.
- When a recent source discusses an older event, say so and state what is newly reported or learned.

## Credibility

Judge each claim on its own evidence, not on the source's reputation, popularity, or model confidence.

- Rank higher: released code, open and reproducible graders, stated model, settings and conditions, independent replication, disclosed failures and costs.
- Rank lower: vendor-reported benchmark numbers, demos without stated conditions, private graders, single-run results, unstated attempt counts.
- Several outlets repeating one announcement, paper, or press release count as one underlying claim, not corroboration. Items from the same `publisher_id` are not independent.
- A press release, trade coverage, and a founder interview about the same launch are one claim.
- Funding news and valuations are never evidence that a technology works.

## Novelty

Prefer new capabilities, new evidence, or new conflicts between results. Reject restatements, rewrites of earlier items, and listicles. Treat a podcast and its YouTube upload as one item.

## Perspective

Aim for a mix of research, commercial announcements (including AI-native startups), and practitioner experience. Name whose perspectives are missing, likely customers and working engineers, rather than implying coverage is complete.

## Uncertainty, conflict, and incentives

- Separate reported facts, source claims, interpretation, and remaining uncertainty. Label each.
- Do not manufacture disagreement. Report tension only when the evidence shows it, for example rankings that change with the scoring metric, or numbers measured on different tasks.
- Treat commercial incentives as context to weigh, not as grounds to dismiss. State when the claimant also built the benchmark.
- Treat unsupported claims as source claims. Do not upgrade them to facts, and say what evidence would settle them.
- Defer, do not reject, items that look promising but lack a checkable passage or timestamp.
- Automatic transcripts (especially from small speech models) can garble numbers, product names, and technical terms. Treat any figure, name, or quote taken from one as unverified until it is checked against the audio at its timestamp.

## Exclusions

Reject animation and game content, pure image or video generation, datacenter and training infrastructure, investment advice, and funding news used as evidence.

## Voice

Direct, precise, and skeptical without being cynical. Define jargon in a clause. State what the evidence supports and no more. No hype words, no calls to buy or invest. Identify AI-generated presentation where used.

## Startup watch

AI-native startups are optional. When accepted evidence supports a relevant startup development, score it by the same core test and use it where it strengthens the argument: as a feasibility signal in piece 1, a claim to test in piece 2, or a build, buy, or wait consideration in piece 3. Do not add a startup merely to fill a slot, and do not treat its absence as an evidence gap.
