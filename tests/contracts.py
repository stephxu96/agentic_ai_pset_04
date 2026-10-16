"""Record contracts from ARCHITECTURE.md, as plain validators.

Each validator returns a list of problem strings (empty list = valid).
Standard library only.
"""
import re

KINDS = {"feed", "youtube", "podcast"}
CHANGES = {"new", "changed", "unchanged"}
DECISIONS = {"accept", "reject", "defer"}
CLAIM_TYPES = {"reported_fact", "source_claim", "inference"}
EXCLUSION_REASONS = {"outside_window", "unknown_date", "future_date", "invalid_date", "inactive_source"}
PIECE_IDS = ["01", "02", "03"]
STATUSES = {"failed", "awaiting_review", "ready_for_production"}

ISO_UTC = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|\+00:00)$")


def is_str(x):
    return isinstance(x, str)


def nonempty_str(x):
    return isinstance(x, str) and x.strip() != ""


def is_iso_utc(x):
    return isinstance(x, str) and bool(ISO_UTC.match(x))


def is_number(x):
    return isinstance(x, (int, float)) and not isinstance(x, bool)


def _need(rec, fields, where, problems):
    if not isinstance(rec, dict):
        problems.append(f"{where}: record is not a JSON object")
        return False
    ok = True
    for f in fields:
        if f not in rec:
            problems.append(f"{where}: missing required field '{f}'")
            ok = False
    return ok


CANDIDATE_FIELDS = [
    "item_id", "source_id", "publisher_id", "kind", "title", "url",
    "published_at", "retrieved_at", "media_url",
]


def validate_candidate(rec, where="candidate"):
    p = []
    if not _need(rec, CANDIDATE_FIELDS, where, p):
        return p
    for f in ("item_id", "source_id", "publisher_id", "title", "url"):
        if not nonempty_str(rec[f]):
            p.append(f"{where}: '{f}' must be a nonempty string")
    if rec["kind"] not in KINDS:
        p.append(f"{where}: kind '{rec['kind']}' not in {sorted(KINDS)}")
    if rec["published_at"] is not None and not is_iso_utc(rec["published_at"]):
        p.append(f"{where}: published_at must be null or an ISO 8601 UTC string, got {rec['published_at']!r}")
    if not is_iso_utc(rec["retrieved_at"]):
        p.append(f"{where}: retrieved_at must be an ISO 8601 UTC string, got {rec['retrieved_at']!r}")
    if rec["media_url"] is not None and not is_str(rec["media_url"]):
        p.append(f"{where}: media_url must be null or a string")
    return p


def validate_item(rec, where="item"):
    p = validate_candidate(rec, where)
    if not isinstance(rec, dict):
        return p
    for f in ("version_id", "text_path", "segments_path"):
        if f not in rec:
            p.append(f"{where}: missing required field '{f}'")
    if p:
        return p
    if not nonempty_str(rec["version_id"]):
        p.append(f"{where}: version_id must be a nonempty string")
    if not nonempty_str(rec["text_path"]):
        p.append(f"{where}: text_path must be a nonempty string")
    if rec["kind"] == "feed" and rec["segments_path"] is not None:
        p.append(f"{where}: written items must have segments_path null")
    if rec["kind"] in ("youtube", "podcast") and not nonempty_str(rec["segments_path"]):
        p.append(f"{where}: audio/video items must have a segments_path")
    return p


def validate_exclusion(rec, where="exclusion"):
    p = []
    if not _need(rec, ["item_id", "version_id", "reason", "detail"], where, p):
        return p
    if rec["reason"] not in EXCLUSION_REASONS:
        p.append(f"{where}: reason '{rec['reason']}' not in {sorted(EXCLUSION_REASONS)}")
    if not is_str(rec["detail"]):
        p.append(f"{where}: detail must be a string")
    return p


def validate_change(rec, where="change"):
    p = []
    if not _need(rec, ["item_id", "version_id", "change"], where, p):
        return p
    if rec["change"] not in CHANGES:
        p.append(f"{where}: change '{rec['change']}' not in {sorted(CHANGES)}")
    return p


def validate_decision(rec, where="decision"):
    p = []
    if not _need(rec, ["item_id", "version_id", "decision", "reason", "piece_ids"], where, p):
        return p
    if rec["decision"] not in DECISIONS:
        p.append(f"{where}: decision '{rec['decision']}' not in {sorted(DECISIONS)}")
    if not nonempty_str(rec["reason"]):
        p.append(f"{where}: reason must be a nonempty string")
    if not isinstance(rec["piece_ids"], list):
        p.append(f"{where}: piece_ids must be an array")
        return p
    for pid in rec["piece_ids"]:
        if pid not in PIECE_IDS:
            p.append(f"{where}: piece id {pid!r} not in {PIECE_IDS}")
    if rec["decision"] == "accept" and not rec["piece_ids"]:
        p.append(f"{where}: accepted item has no piece_ids")
    if rec["decision"] in ("reject", "defer") and rec["piece_ids"]:
        p.append(f"{where}: rejected/deferred item must have empty piece_ids")
    return p


def validate_evidence_ref(ev, where="evidence"):
    p = []
    if not _need(ev, ["item_id", "version_id", "locator"], where, p):
        return p
    loc = ev["locator"]
    if not isinstance(loc, dict):
        return p + [f"{where}: locator must be an object"]
    if loc.get("type") == "text":
        if not nonempty_str(loc.get("quote")):
            p.append(f"{where}: text locator needs a nonempty exact 'quote'")
    elif loc.get("type") == "segment":
        if not nonempty_str(loc.get("segment_id")):
            p.append(f"{where}: segment locator needs a 'segment_id'")
    else:
        p.append(f"{where}: locator.type must be 'text' or 'segment'")
    return p


def validate_brief(rec, where="brief"):
    p = []
    fields = ["piece_id", "title", "question", "argument", "synthesis", "limitations", "claims"]
    if not _need(rec, fields, where, p):
        return p
    if rec["piece_id"] not in PIECE_IDS:
        p.append(f"{where}: piece_id {rec['piece_id']!r} not in {PIECE_IDS}")
    for f in ("title", "question", "argument", "synthesis", "limitations"):
        if not nonempty_str(rec[f]):
            p.append(f"{where}: '{f}' must be a nonempty string")
    claims = rec["claims"]
    if not isinstance(claims, list) or not claims:
        return p + [f"{where}: claims must be a nonempty array"]
    seen = set()
    for i, c in enumerate(claims):
        w = f"{where}.claims[{i}]"
        if not _need(c, ["claim_id", "statement", "type", "evidence"], w, p):
            continue
        if not nonempty_str(c["claim_id"]):
            p.append(f"{w}: claim_id must be a nonempty string")
        elif c["claim_id"] in seen:
            p.append(f"{w}: duplicate claim_id {c['claim_id']}")
        seen.add(c["claim_id"])
        if not nonempty_str(c["statement"]):
            p.append(f"{w}: statement must be a nonempty string")
        if c["type"] not in CLAIM_TYPES:
            p.append(f"{w}: type '{c['type']}' not in {sorted(CLAIM_TYPES)}")
        if not isinstance(c["evidence"], list) or not c["evidence"]:
            p.append(f"{w}: every claim must have a nonempty evidence array")
        else:
            for j, ev in enumerate(c["evidence"]):
                p.extend(validate_evidence_ref(ev, f"{w}.evidence[{j}]"))
    return p


def validate_manifest(rec, where="manifest"):
    p = []
    if not _need(rec, ["piece_id", "path", "claim_ids"], where, p):
        return p
    if rec["piece_id"] not in PIECE_IDS:
        p.append(f"{where}: piece_id {rec['piece_id']!r} not in {PIECE_IDS}")
    if not nonempty_str(rec["path"]):
        p.append(f"{where}: path must be a nonempty string")
    if not isinstance(rec["claim_ids"], list):
        p.append(f"{where}: claim_ids must be an array")
    return p


def validate_segments(arr, where="segments"):
    p = []
    if not isinstance(arr, list) or not arr:
        return [f"{where}: must be a nonempty array of segments"]
    for i, s in enumerate(arr):
        w = f"{where}[{i}]"
        if not _need(s, ["segment_id", "start_seconds", "end_seconds", "text"], w, p):
            continue
        if not nonempty_str(s["segment_id"]):
            p.append(f"{w}: segment_id must be a nonempty string")
        if not is_number(s["start_seconds"]) or not is_number(s["end_seconds"]):
            p.append(f"{w}: start_seconds and end_seconds must be numbers")
        elif s["end_seconds"] < s["start_seconds"]:
            p.append(f"{w}: end_seconds is before start_seconds")
        if not is_str(s["text"]):
            p.append(f"{w}: text must be a string")
    return p


# Receipts: the spec lists concepts, not exact key names, so match loosely.
RECEIPT_CONCEPTS = {
    "stage": ["stage"],
    "status": ["status"],
    "input count": ["input"],
    "output count": ["output"],
    "start time": ["start"],
    "finish time": ["finish", "end", "complet"],
    "tools or models": ["tool", "model"],
    "cost in USD": ["cost"],
}


def receipt_missing_concepts(rec):
    """Return the receipt concepts for which no key (at any depth) matches."""
    keys = []

    def walk(o):
        if isinstance(o, dict):
            for k, v in o.items():
                keys.append(str(k).lower())
                walk(v)
        elif isinstance(o, list):
            for v in o:
                walk(v)

    walk(rec)
    missing = []
    for concept, needles in RECEIPT_CONCEPTS.items():
        if not any(any(n in k for n in needles) for k in keys):
            missing.append(concept)
    return missing


def find_key(obj, name):
    """Recursively find the first value stored under key `name`. Returns (found, value)."""
    if isinstance(obj, dict):
        if name in obj:
            return True, obj[name]
        for v in obj.values():
            ok, val = find_key(v, name)
            if ok:
                return True, val
    elif isinstance(obj, list):
        for v in obj:
            ok, val = find_key(v, name)
            if ok:
                return True, val
    return False, None
