# Editorial Policy: Agentic 3D

This policy is supplied to the AI during selection and synthesis. It is snapshotted into each run.

## Core test

A capability claim holds only as far as the check that observed it. A valid solid does not prove a part is manufacturable. A good-looking scene does not prove its dimensions are right. A simulation score does not prove physical transfer. For every claim, ask: what was actually checked, by whom, and under what conditions?

## Relevance

Accept items that help a technical product or engineering leader decide whether to build on a frontier-model capability for 3D modeling, CAD, manufacturing design (design for manufacturing, process planning, quoting, production-ready geometry), or intelligent systems acting in physical space (including robotics). Consider AI-native startup products and releases when there is relevant, checkable evidence, but do not require startup coverage. Prefer items that change what is feasible, what is verified, or what a buyer or builder could check themselves.

Weighting: 3D modeling, CAD, and manufacturing design lead the series, and robotics supports. Accept manufacturing-design items when they involve AI producing or checking geometry, process, cost, or manufacturability decisions; reject generic factory-automation or industry news with no AI design or engineering decision in it. Accept robotics items when they bear on the same questions (geometry, simulation-ready assets, what was actually verified) or are a major development for AI-native startups, and keep robotics in a supporting role within each piece.

## Freshness

- The as-of date is the run's `as_of_date`. The window length comes from `freshness_window_days` in the project config (30 in this project, the assignment's standard). The window runs from the as-of date minus (N - 1) days through the as-of date, in UTC, so 30 days gives as-of minus 29 days through as-of. Every item records its age in days.
- Undated material is never evidence.
- A reposted recording, or an unchanged article with a refreshed date, is not a new development.
- When a recent source discusses an older event, say so and state what is newly reported or learned.

## Credibility

Judge each claim on its own evidence, not on the source's reputation, popularity, or model confidence.

- Rank higher: released code, open and reproducible graders, stated model, settings and conditions, independent replication, disclosed failures and costs.
- Rank lower: vendor-reported benchmark numbers, demos without stated conditions, private graders, single-run results, unstated attempt counts.
- Several outlets repeating one announcement, paper, or press release count as one underlying claim, not corroboration. Items from the same `publisher_id` are not independent.
- A press release, trade coverage, and a founder interview about the same launch are one claim.
- Separate companies are separate claims. When different companies each announce their own product built on the same technology, and each says the technology is worth building on, those are independent claims about different products, even if the argument sounds alike. Count each one as its own voice. Together they show where the market is placing bets. They do not show the technology works; only a check that observed the result can do that.
- Funding news and valuations are never evidence that a technology works.

## Novelty

Prefer new capabilities, new evidence, or new conflicts between results. Reject restatements, rewrites of earlier items, and listicles. Treat a podcast and its YouTube upload as one item.

## Perspective

Aim for a mix of research, commercial announcements (including AI-native startups), and practitioner experience. Name whose perspectives are missing, likely customers and working engineers, rather than implying coverage is complete.

Commercial voices are a required perspective in this publication, not a defect. Vendors, startups and their executives say what the market is building and selling. This is a practitioner publication, not an academic paper: a company's own claim is usable evidence of what the company says and plans, as long as it is dated, quotable, and labeled as that company's claim. Aim for at least one accepted commercial or startup source in each piece when the eligible items include one.

## Uncertainty, conflict, and incentives

- Separate reported facts, source claims, interpretation, and remaining uncertainty. Label each.
- Do not manufacture disagreement. Report tension only when the evidence shows it, for example rankings that change with the scoring metric, or numbers measured on different tasks.
- Treat commercial incentives as context to weigh, not as grounds to dismiss. State when the claimant also built the benchmark.
- Treat unverified claims, including a vendor's, startup's or executive's own performance claims, as attributed source claims. Accept and quote them as "X says". Do not upgrade them to facts, do not count them as independent corroboration, and say what evidence would settle them. A claim being unverified is a reason to label it, not a reason to drop the item.
- Do not defer a commercial item only because its numbers lack a disclosed method, dataset or independent test. Accept it for the narrow scope it supports (what the company says it ships, plans, or measured) and note the limit.
- Defer only items that lack a quotable passage or timestamp, restate an item already accepted, or whose relevance depends on evidence not yet published.
- Automatic transcripts (especially from small speech models) can garble numbers, product names, and technical terms. Treat any figure, name, or quote taken from one as unverified until it is checked against the audio at its timestamp.

## Exclusions

Reject animation and game content, pure image or video generation, datacenter and training infrastructure, investment advice, and funding news used as evidence.

## Voice

Direct, precise, and skeptical without being cynical. Define jargon in a clause. State what the evidence supports and no more. No hype words, no calls to buy or invest. Identify AI-generated presentation where used.

## Startup watch

AI-native startups are optional. When accepted evidence supports a relevant startup development, score it by the same core test and use it where it strengthens the argument: as a feasibility signal in piece 1, a claim to test in piece 2, or a build, buy, or wait consideration in piece 3. Do not add a startup merely to fill a slot, and do not treat its absence as an evidence gap.
