# Editorial review: Agentic 3D

Linked from `SUBMISSION.md` ("Editorial Review"). Fill in the brackets with your own judgment; delete the guidance lines when done.

## Files reviewed

- Policy (version 1, used in run 1): `runs/RUN_ID_1/config/editorial_policy.md`
- Policy (version 2, used in run 2): `runs/RUN_ID_2/config/editorial_policy.md`
- Prompts: `runs/RUN_ID_1/prompts/` and `runs/RUN_ID_2/prompts/`
- Decisions reviewed: `runs/RUN_ID_1/decisions.jsonl`

## Accepted items (at least three)

Compare the AI's reason with your own. Say whether you agree and why, and name the evidence you checked (the passage or timestamp).

| Item (`item_id`, source, date) | AI's reason | My judgment | Agree? | Evidence I checked |
| --- | --- | --- | --- | --- |
| [id] | [AI reason] | [your view] | [yes / partly / no] | [passage or timestamp] |
| [id] | | | | |
| [id] | | | | |

## Rejected or deferred items (at least three)

| Item (`item_id`, source, date) | Decision | AI's reason | My judgment | Agree? |
| --- | --- | --- | --- | --- |
| [id] | [reject / defer] | [AI reason] | [your view] | [yes / partly / no] |
| [id] | | | | |
| [id] | | | | |

## Policy revision

**What the review showed:** [the pattern in the AI's decisions that your judgment disagreed with, for example it over-accepted vendor claims or rejected robotics items you wanted as context.]

**Policy before and after:**

| Policy section | Version 1 (before) | Version 2 (after) | Why |
| --- | --- | --- | --- |
| [e.g. Credibility] | [old wording] | [new wording] | [reason] |

**Affected stage outputs:** [which decisions, briefs or drafts changed between run 1 and run 2, with paths, and what changed. If nothing changed in an output, say so.]

## Trace of one published claim

Follow one claim from the published article back to its source.

- Claim: [`piece-claim id` and the statement as published]
- Brief: `runs/RUN_ID/briefs.jsonl` (piece [NN])
- Editorial decision: `runs/RUN_ID/decisions.jsonl` ([item_id], [accept], reason)
- Source version: [`item_id`, `version_id`]
- Exact supporting passage or timestamp: [quote, or segment ID and time]

## Factual corrections

Record each correction you made before approving, why it was needed, and where it came from. If you found none, say what you checked.

| Piece | What was wrong in the draft | Correction | Source |
| --- | --- | --- | --- |
| [NN] | [e.g. a number from an automatic transcript] | [fix] | [passage or timestamp] |

## Remaining limitations

[Claims the evidence does not justify a confident conclusion on; perspectives missing (for example customers and working engineers); coverage gaps; any items older than 30 days that the 45-day window let in.]

## Evidence for final publication approval

- `runs/RUN_ID/review.json` (`review_id`: [id], `passed`: [true])
- `runs/RUN_ID/approval.json` ([decision], reviewer, time)
- What I verified before approving: [one or two sentences]
