#!/usr/bin/env python3
"""Create three evidence-grounded briefs from accepted items only."""

import datetime as dt
import difflib
import hashlib
import json
import os
import re
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools"))
from codex_jsonl import CodexError, invoke, write_jsonl  # noqa: E402


class InputError(Exception): pass


class StageError(Exception): pass


def safe_path(rel):
    if not isinstance(rel, str) or not rel or os.path.isabs(rel): raise InputError("expected repository-relative path")
    path = (ROOT / rel).resolve()
    if path != ROOT and ROOT not in path.parents: raise InputError("path escapes the repository: %s" % rel)
    return path


def utc_now(): return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path):
    try: return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc: raise InputError("cannot read %s: %s" % (path, exc))


def read_jsonl_stdin():
    records = []
    for i, line in enumerate(sys.stdin, 1):
        if not line.strip(): continue
        try: rec = json.loads(line)
        except json.JSONDecodeError as exc: raise InputError("stdin line %d is not JSON: %s" % (i, exc))
        if not isinstance(rec, dict): raise InputError("stdin line %d must be a JSON object" % i)
        records.append(rec)
    return records


def evidence_for(item):
    evidence = {key: item.get(key) for key in (
        "item_id", "version_id", "source_id", "publisher_id", "kind", "title", "url", "published_at", "text_path", "segments_path")}
    try:
        text = safe_path(item["text_path"]).read_text(encoding="utf-8")
        if item.get("segments_path"):
            segments = read_json(safe_path(item["segments_path"]))
            # The transcript text duplicates its segments. Supply a bounded,
            # time-distributed set of exact segments so the prompt stays under
            # the Codex input limit while locators still resolve to full assets.
            limit = 300
            if len(segments) > limit:
                indices = [i * (len(segments) - 1) // (limit - 1) for i in range(limit)]
                evidence["segments"] = [segments[i] for i in indices]
            else:
                evidence["segments"] = segments
            evidence["segments_total"] = len(segments)
            evidence["text"] = None
        else:
            # A live page can be very large (the survey is over 800k chars).
            # Keep its lead and explicit truncation metadata for honest use.
            limit = 40000
            evidence["text"] = text[:limit]
            evidence["text_total_chars"] = len(text)
            evidence["segments"] = None
    except (OSError, KeyError) as exc:
        raise InputError("accepted evidence asset is unavailable for %s: %s" % (item.get("item_id"), exc))
    return evidence


def nearby_verbatim_passages(body, attempted):
    words = re.findall(r"[A-Za-z0-9]+", attempted)
    anchors = sorted((word for word in words if len(word) >= 4), key=len, reverse=True)
    lines = [line.strip() for line in body.splitlines() if line.strip()]
    if anchors:
        matching = [line for line in lines if any(anchor.lower() in line.lower() for anchor in anchors)]
        lines = matching or lines
    ranked = sorted(lines, key=lambda line: difflib.SequenceMatcher(
        None, attempted.lower(), line.lower()).ratio(), reverse=True)
    return [line[:180] for line in ranked[:2]]


def validate_plan(rec, accepted_items):
    assignments = rec.get("assignments")
    if not isinstance(assignments, list): return "plan needs an assignments array"
    expected = {(item["item_id"], item["version_id"]): item for item in accepted_items}
    seen, by_piece = set(), {piece: [] for piece in ("01", "02", "03")}
    for assignment in assignments:
        if not isinstance(assignment, dict): return "plan assignment must be an object"
        key = (assignment.get("item_id"), assignment.get("version_id"))
        if key not in expected: return "plan references an item/version outside the accepted set"
        if key in seen: return "plan assigns an accepted item more than once"
        piece_id = assignment.get("lead_piece_id")
        if piece_id not in by_piece: return "lead_piece_id must be 01, 02, or 03"
        seen.add(key)
        by_piece[piece_id].append(expected[key])
    if seen != set(expected): return "plan must assign every accepted item exactly once"
    for piece_id, items in by_piece.items():
        if len(items) < 2: return "piece %s needs at least two exclusive lead items" % piece_id
        if len({item.get("publisher_id") for item in items}) < 3:
            return "piece %s needs at least three independent lead publishers" % piece_id
        if not any(item.get("kind") in ("youtube", "podcast") for item in items):
            return "piece %s needs timestamped media among its leads" % piece_id
    return None


def validate_brief(rec, piece_id, allowed, required_keys=None):
    if rec.get("piece_id") != piece_id: return "brief piece_id must be %s" % piece_id
    for key in ("title", "question", "argument", "synthesis", "limitations"):
        if not isinstance(rec.get(key), str) or not rec[key].strip(): return "brief %s must be nonempty text" % key
    claims = rec.get("claims")
    if not isinstance(claims, list) or not claims: return "brief needs a nonempty claims array"
    publishers, kinds, claim_ids, referenced = set(), set(), set(), set()
    version_by_item = {item_id: version_id for item_id, version_id in allowed}
    for claim in claims:
        if not isinstance(claim, dict): return "claim must be a JSON object"
        cid = claim.get("claim_id")
        if not isinstance(cid, str) or not cid.startswith(piece_id + "-c"): return "claim_id must use the %s-cN pattern" % piece_id
        if cid in claim_ids: return "claim_id must be unique within a brief"
        claim_ids.add(cid)
        if not isinstance(claim.get("statement"), str) or not claim["statement"].strip(): return "claim statement is required"
        if claim.get("type") not in ("reported_fact", "source_claim", "inference"): return "invalid claim type"
        refs = claim.get("evidence")
        if not isinstance(refs, list) or not refs: return "every claim needs evidence"
        claim_publishers = set()
        for ref in refs:
            if not isinstance(ref, dict): return "evidence reference must be an object"
            # A long but truncated hash is a transcription error, not a
            # different source version. Resolve only an unambiguous prefix;
            # the locator is still checked against the full retained asset.
            item_id, supplied_version = ref.get("item_id"), ref.get("version_id")
            expected_version = version_by_item.get(item_id)
            if (isinstance(supplied_version, str) and isinstance(expected_version, str)
                    and len(supplied_version) >= 32 and expected_version.startswith(supplied_version)):
                ref["version_id"] = expected_version
            key = (ref.get("item_id"), ref.get("version_id"))
            if key not in allowed: return "claim references an item/version not accepted for this piece"
            referenced.add(key)
            item = allowed[key]
            publishers.add(item.get("publisher_id")); kinds.add(item.get("kind"))
            claim_publishers.add(item.get("publisher_id"))
            loc = ref.get("locator")
            if not isinstance(loc, dict): return "evidence locator must be an object"
            if loc.get("type") == "text":
                if not isinstance(loc.get("quote"), str) or not loc["quote"].strip(): return "text locator needs an exact quote"
                body = safe_path(item["text_path"]).read_text(encoding="utf-8")
                if loc["quote"] not in body:
                    examples = nearby_verbatim_passages(body, loc["quote"])
                    return "claim %s has a non-verbatim quote for %s: %r; use an exact contiguous substring, for example from these source lines: %s" % (cid, ref.get("item_id"), loc["quote"][:120], json.dumps(examples, ensure_ascii=False))
            elif loc.get("type") == "segment":
                if not item.get("segments_path"): return "segment locator refers to a written item"
                segments = read_json(safe_path(item["segments_path"]))
                if loc.get("segment_id") not in {seg.get("segment_id") for seg in segments if isinstance(seg, dict)}:
                    return "segment locator does not resolve in the selected transcript"
            else: return "locator type must be text or segment"
        if claim["type"] in ("reported_fact", "source_claim") and len(claim_publishers) != 1:
            return "claim %s must cite one producer; split distinct reported facts or source claims" % cid
        if claim["type"] == "inference" and len(claim_publishers) > 2:
            return "claim %s combines more than two producers; split the inference into focused claims" % cid
    if len(publishers) < 3: return "piece needs evidence from at least three independent publishers"
    if "youtube" not in kinds and "podcast" not in kinds: return "piece needs timestamped media evidence"
    if required_keys and not set(required_keys).issubset(referenced):
        return "brief must cite every assigned lead item; missing: %s" % sorted(set(required_keys) - referenced)
    return None


def validate_review(rec, piece_id):
    if rec.get("piece_id") != piece_id: return "review piece_id must be %s" % piece_id
    if not isinstance(rec.get("issues"), list): return "review issues must be an array"
    if any(not isinstance(issue, str) or not issue.strip() for issue in rec["issues"]):
        return "each review issue must be nonempty text"
    if not isinstance(rec.get("ready"), bool): return "review ready must be a boolean"
    if rec["ready"] and rec["issues"]: return "a ready review cannot have unresolved issues"
    return None


def save_iteration(path, value):
    with path.open("x", encoding="utf-8") as fh:
        json.dump(value, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def save_failure(run_path, error):
    logs = run_path / "logs"; logs.mkdir(parents=True, exist_ok=True)
    name = "create-briefs-failed-%s.json" % dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    value = {"stage": "editorial/create_briefs.sh", "status": "failed", "input_count": None, "output_count": 0,
             "started_at": utc_now(), "finished_at": utc_now(), "tools": ["Codex CLI"],
             "model": "default, name not reported", "cost_usd": None, "errors": [error]}
    with (logs / name).open("x", encoding="utf-8") as fh: json.dump(value, fh, ensure_ascii=False); fh.write("\n")


def run(run_dir):
    run_path = safe_path(run_dir)
    decisions = read_jsonl_stdin()
    accepted = [d for d in decisions if d.get("decision") == "accept"]
    policy_source = os.environ.get("BRIEF_POLICY_SOURCE", "run_snapshot")
    if policy_source not in ("run_snapshot", "live"):
        raise InputError("BRIEF_POLICY_SOURCE must be run_snapshot or live")
    config_root = ROOT if policy_source == "live" else run_path
    try:
        eligible_records = [json.loads(line) for line in (run_path / "eligible.jsonl").read_text(encoding="utf-8").splitlines() if line.strip()]
        project = read_json(config_root / "config" / "project.json")
        run_meta = read_json(run_path / "run.json")
        policy = (config_root / "config" / "editorial_policy.md").read_text(encoding="utf-8")
        instructions = (config_root / "prompts" / "create_briefs.md").read_text(encoding="utf-8")
    except (OSError, json.JSONDecodeError) as exc: raise InputError("missing or malformed run input: %s" % exc)
    eligible = {(it.get("item_id"), it.get("version_id")): it for it in eligible_records if isinstance(it, dict)}
    briefs = []
    try:
        iteration_dir = run_path / "brief_iterations" / (dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + "-" + uuid.uuid4().hex[:8])
        iteration_dir.mkdir(parents=True)
        save_iteration(iteration_dir / "policy_source.json", {
            "source": policy_source,
            "project_sha256": hashlib.sha256(json.dumps(project, sort_keys=True).encode("utf-8")).hexdigest(),
            "policy_sha256": hashlib.sha256(policy.encode("utf-8")).hexdigest(),
            "instructions_sha256": hashlib.sha256(instructions.encode("utf-8")).hexdigest(),
            "decisions_sha256": hashlib.sha256(write_jsonl(decisions).encode("utf-8")).hexdigest(),
        })
        podcast_gap = not any(eligible.get((d.get("item_id"), d.get("version_id")), {}).get("kind") == "podcast" for d in accepted)
        accepted_by_key = {(d.get("item_id"), d.get("version_id")): d for d in accepted}
        if len(accepted_by_key) != len(accepted) or any(key not in eligible for key in accepted_by_key):
            raise InputError("accepted decisions must identify distinct versions in eligible.jsonl")
        accepted_items = [eligible[key] for key in accepted_by_key]
        plan_input = []
        for item in accepted_items:
            decision = accepted_by_key[(item["item_id"], item["version_id"])]
            plan_input.append({key: item.get(key) for key in (
                "item_id", "version_id", "source_id", "publisher_id", "kind", "title")})
            plan_input[-1]["suggested_piece_ids"] = decision.get("piece_ids", [])
            plan_input[-1]["selection_reason"] = str(decision.get("reason", ""))[:700]
        plan_prompt = (instructions + "\n\nEDITORIAL POLICY\n" + policy +
                       "\n\nPlan the three pieces before drafting. Assign every accepted item exactly once as a lead. "
                       "The selection piece_ids are suggestions, not fixed assignments. Choose at least two "
                       "exclusive lead items, three independent publishers, and one podcast or YouTube item "
                       "for each piece. Keep the three editorial angles and syntheses distinct. "
                       "Return exactly one strict JSONL object with an assignments array; each assignment "
                       "has item_id, version_id, lead_piece_id (01, 02, or 03). Output no commentary.\n\n"
                       "Accepted items:\n" + write_jsonl(plan_input))
        plan = invoke(run_path, "editorial/create_briefs.sh/plan", plan_prompt,
                      validator=lambda rec, _idx: validate_plan(rec, accepted_items),
                      batch_validator=lambda recs: None if len(recs) == 1 else "expected exactly one plan record",
                      input_count=len(accepted_items))[0]
        save_iteration(iteration_dir / "lead_plan.json", plan)
        planned = {piece: set() for piece in ("01", "02", "03")}
        for assignment in plan["assignments"]:
            planned[assignment["lead_piece_id"]].add((assignment["item_id"], assignment["version_id"]))
        for piece_id in ("01", "02", "03"):
            assigned = planned[piece_id]
            items = [eligible[key] for key in assigned if key in eligible]
            if len(items) != len(assigned): raise InputError("accepted decisions refer to versions missing from eligible.jsonl")
            pubs = {item.get("publisher_id") for item in items}
            if len(pubs) < 3: raise StageError("piece %s has fewer than three accepted independent publishers; cannot create a supported brief" % piece_id)
            evidence = [evidence_for(item) for item in items]
            allowed = {(item["item_id"], item["version_id"]): item for item in items}
            prompt = (instructions + "\n\nEDITORIAL POLICY\n" + policy +
                      "\n\nPROJECT BRIEF\n" + json.dumps({k: project.get(k) for k in ("publication_name", "topic", "audience", "central_question")}, ensure_ascii=False) +
                      "\nAs-of date: " + str(run_meta.get("as_of_date")) +
                      "\nExclusive lead decisions for piece " + piece_id + ":\n" + write_jsonl([accepted_by_key[key] for key in assigned]) +
                      "\nExact retained evidence excerpts for those accepted items (full assets remain available for locator validation; excerpts may be truncated as marked):\n" + write_jsonl(evidence) +
                      "\nCite every lead item at least once. These lead items are not leads in the other pieces. "
                      "Do not collapse this piece into the thesis that a check proves only what it observed. "
                      "Previously completed piece arguments and syntheses (do not repeat them):\n" +
                      json.dumps([{"piece_id": prior["piece_id"], "argument": prior["argument"],
                                   "synthesis": prior["synthesis"]} for prior in briefs], ensure_ascii=False) +
                      "\nCreate only piece " + piece_id + ". Return exactly one strict JSONL object with the brief fields and no commentary.")
            if podcast_gap:
                prompt += "\nThe accepted set contains no podcast evidence. Do not claim otherwise; state this coverage gap in limitations. These briefs are provisional until the series meets the podcast requirement."
            validator = lambda rec, _idx, pid=piece_id, allow=allowed, required=assigned: validate_brief(rec, pid, allow, required)
            one_record = lambda rs: None if len(rs) == 1 else "expected exactly one record"
            draft = invoke(run_path, "editorial/create_briefs.sh/draft-" + piece_id,
                           prompt + "\nThis is the first draft. It will receive a separate evidence audit and revision.",
                           validator=validator, batch_validator=one_record, input_count=len(items))[0]
            save_iteration(iteration_dir / (piece_id + "-draft.json"), draft)
            review_prompt = ("Audit this draft against the supplied editorial policy and exact evidence excerpts. "
                             "Check every claim for support, locator accuracy, independence, overstatement, "
                             "CAD/3D emphasis, startup treatment if present, and meaningful limitations. "
                             "Flag catch-all claims that combine several source observations under one marker; "
                             "require a separate claim for each producer's reported fact and a narrowly worded, "
                             "separately typed inference when connecting evidence. "
                             "Name each concrete problem as a short issue. Return exactly one JSONL object "
                             "with piece_id, ready (boolean), and issues (array of strings). "
                             "Set ready true only when issues is empty. Do not invent missing evidence.\n\n" +
                             prompt + "\n\nDRAFT TO AUDIT\n" + json.dumps(draft, ensure_ascii=False))
            review = invoke(run_path, "editorial/create_briefs.sh/review-" + piece_id, review_prompt,
                            validator=lambda rec, _idx, pid=piece_id: validate_review(rec, pid),
                            batch_validator=one_record, input_count=1)[0]
            save_iteration(iteration_dir / (piece_id + "-review.json"), review)
            revision_prompt = (prompt + "\n\nRevise the following first draft after its independent audit. "
                               "Resolve every review issue where the accepted evidence permits; otherwise name the gap "
                               "in limitations. Preserve only claims with resolvable exact locators. "
                               "Return one complete final brief as strict JSONL, not a patch.\n\nFIRST DRAFT\n" +
                               json.dumps(draft, ensure_ascii=False) + "\n\nAUDIT\n" +
                               json.dumps(review, ensure_ascii=False))
            brief = invoke(run_path, "editorial/create_briefs.sh/revision-" + piece_id, revision_prompt,
                           validator=validator, batch_validator=one_record, input_count=len(items))[0]
            save_iteration(iteration_dir / (piece_id + "-final.json"), brief)
            briefs.append(brief)
    except (InputError, StageError, CodexError) as exc:
        save_failure(run_path, str(exc))
        raise
    sys.stdout.write(write_jsonl(briefs))


if __name__ == "__main__":
    try:
        if len(sys.argv) != 2: raise InputError("usage: create_briefs.sh RUN_DIR")
        run(sys.argv[1])
    except InputError as exc:
        print("editorial/create_briefs.sh: %s" % exc, file=sys.stderr); sys.exit(2)
    except StageError as exc:
        print("editorial/create_briefs.sh: %s" % exc, file=sys.stderr); sys.exit(1)
    except CodexError as exc:
        print("editorial/create_briefs.sh: %s" % exc, file=sys.stderr); sys.exit(1)
