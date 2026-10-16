#!/usr/bin/env python3
"""Discover RSS and Atom written items from the run's source snapshot."""

import datetime as dt
import email.utils
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USER_AGENT = "MIT-1.125-intelligence-pipeline/1.0"


class ConfigError(Exception):
    pass


def local(tag):
    return tag.rsplit("}", 1)[-1].lower()


def utc_now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_path(rel):
    if not isinstance(rel, str) or not rel or os.path.isabs(rel):
        raise ConfigError("RUN_DIR must be a repository-relative path")
    path = (ROOT / rel).resolve()
    if path != ROOT and ROOT not in path.parents:
        raise ConfigError("RUN_DIR must stay within the repository")
    return path


def parse_date(value):
    if not value:
        return None
    try:
        parsed = email.utils.parsedate_to_datetime(value.strip())
    except (TypeError, ValueError, OverflowError):
        parsed = None
    if parsed is None:
        try:
            raw = value.strip()
            parsed = dt.datetime.fromisoformat(raw[:-1] + "+00:00" if raw.endswith("Z") else raw)
        except (TypeError, ValueError, OverflowError):
            return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=dt.timezone.utc)
    return parsed.astimezone(dt.timezone.utc)


def canonical_url(url):
    parts = urllib.parse.urlsplit(url)
    query = [(k, v) for k, v in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
             if not k.lower().startswith("utm_") and k.lower() not in ("fbclid", "gclid")]
    path = parts.path or "/"
    return urllib.parse.urlunsplit((parts.scheme.lower(), parts.netloc.lower(), path,
                                    urllib.parse.urlencode(query), ""))


def parse_feed(payload, feed_url):
    try:
        # Some valid publisher feeds prepend whitespace before the XML declaration.
        root = ET.fromstring(payload.lstrip())
    except ET.ParseError as exc:
        raise ValueError("not a valid RSS/Atom document: %s" % exc)
    root_kind = local(root.tag)
    entries = []
    if root_kind in ("rss", "rdf"):
        channel = next((e for e in root.iter() if local(e.tag) == "channel"), root)
        for node in channel:
            if local(node.tag) != "item":
                continue
            row = {"title": "", "url": "", "native_id": "", "published_at": None}
            for child in node:
                name = local(child.tag)
                val = (child.text or "").strip()
                if name == "title": row["title"] = val
                elif name == "link": row["url"] = val
                elif name in ("guid", "id"): row["native_id"] = val
                elif name in ("pubdate", "published", "updated", "date") and row["published_at"] is None:
                    date = parse_date(val)
                    row["published_at"] = date
            if row["url"]:
                row["url"] = urllib.parse.urljoin(feed_url, row["url"])
                entries.append(row)
    elif root_kind == "feed":
        for node in root:
            if local(node.tag) != "entry":
                continue
            row = {"title": "", "url": "", "native_id": "", "published_at": None}
            for child in node:
                name = local(child.tag)
                val = (child.text or "").strip()
                if name == "title": row["title"] = val
                elif name == "id": row["native_id"] = val
                elif name == "link":
                    rel = child.attrib.get("rel", "alternate")
                    if rel == "alternate" and not row["url"]:
                        row["url"] = urllib.parse.urljoin(feed_url, child.attrib.get("href", ""))
                elif name in ("published", "updated") and row["published_at"] is None:
                    row["published_at"] = parse_date(val)
            if row["url"]:
                entries.append(row)
    else:
        raise ValueError("expected RSS or Atom feed, got %s" % root_kind)
    return entries


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/rss+xml, application/atom+xml, application/xml, text/xml, */*"})
    try:
        with urllib.request.urlopen(req, timeout=20) as response:
            return response.read(10_000_000)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError("could not fetch %s: %s" % (url, exc))


def load_sources(run_path):
    try:
        project = json.loads((run_path / "config" / "project.json").read_text(encoding="utf-8"))
        sources = json.loads((run_path / "config" / "sources.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigError("cannot read run config snapshot: %s" % exc)
    if not isinstance(sources, list) or not isinstance(project, dict):
        raise ConfigError("source snapshot must be an array and project snapshot an object")
    cap = project.get("max_items_per_source", 3)
    if isinstance(cap, bool) or not isinstance(cap, int) or cap < 1:
        raise ConfigError("max_items_per_source must be a positive integer")
    rows = []
    for i, src in enumerate(sources):
        if not isinstance(src, dict) or not all(isinstance(src.get(k), str) and src[k] for k in ("source_id", "publisher_id", "url")):
            raise ConfigError("source %d requires source_id, publisher_id, and url" % i)
        if src.get("kind") == "feed":
            rows.append(src)
    return rows, cap


def main(argv):
    if len(argv) != 1:
        raise ConfigError("usage: fetch_feeds.sh RUN_DIR")
    run_path = repo_path(argv[0])
    started = utc_now()
    output, errors, capped_sources = [], [], []
    sources, cap = load_sources(run_path)
    for src in sources:
        try:
            entries = parse_feed(fetch(src["url"]), src["url"])
            entries.sort(key=lambda row: row["published_at"] or dt.datetime.min.replace(tzinfo=dt.timezone.utc), reverse=True)
            if len(entries) > cap:
                capped_sources.append({"source_id": src["source_id"], "items_omitted": len(entries) - cap})
            for row in entries[:cap]:
                native = row["native_id"] or canonical_url(row["url"])
                output.append({"item_id": "feed:" + native, "source_id": src["source_id"],
                               "publisher_id": src["publisher_id"], "kind": "feed", "title": row["title"] or row["url"],
                               "url": canonical_url(row["url"]),
                               "published_at": row["published_at"].isoformat().replace("+00:00", "Z") if row["published_at"] else None,
                               "retrieved_at": utc_now(), "media_url": None})
        except (RuntimeError, ValueError) as exc:
            errors.append({"source_id": src["source_id"], "error": str(exc)})
    save_receipt(run_path, started, len(sources), output, errors, capped_sources)
    for candidate in output:
        print(json.dumps(candidate, ensure_ascii=False, separators=(",", ":")))
    return 1 if errors else 0


def save_receipt(run_path, started, input_count, output, errors, capped):
    logs = run_path / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    rec = {"stage": "collectors/fetch_feeds.sh", "status": "failed" if errors else "completed",
           "input_count": input_count, "output_count": len(output), "started_at": started, "finished_at": utc_now(),
           "tools": ["Python standard library", "urllib", "ElementTree"], "cost_usd": None,
           "cap_truncations": capped, "errors": errors}
    with (logs / ("fetch-feeds-%s-%d.json" % (stamp, os.getpid()))).open("x", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, sort_keys=True)
        fh.write("\n")


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except ConfigError as exc:
        print("collectors/fetch_feeds.sh: %s" % exc, file=sys.stderr)
        sys.exit(2)
