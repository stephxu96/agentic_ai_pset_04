#!/usr/bin/env python3
"""Discover dated podcast episodes and their audio enclosures from RSS/Atom."""

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


class ConfigError(Exception):
    pass


def local(tag): return tag.rsplit("}", 1)[-1].lower()


def utc_now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def run_path(rel):
    if not isinstance(rel, str) or not rel or os.path.isabs(rel): raise ConfigError("RUN_DIR must be repository-relative")
    path = (ROOT / rel).resolve()
    if path != ROOT and ROOT not in path.parents: raise ConfigError("RUN_DIR escapes the repository")
    return path


def date_value(value):
    if not value: return None
    try: value = email.utils.parsedate_to_datetime(value.strip())
    except (TypeError, ValueError, OverflowError):
        try:
            raw = value.strip()
            value = dt.datetime.fromisoformat(raw[:-1] + "+00:00" if raw.endswith("Z") else raw)
        except (TypeError, ValueError, OverflowError): return None
    if value.tzinfo is None: value = value.replace(tzinfo=dt.timezone.utc)
    return value.astimezone(dt.timezone.utc)


def parse_feed(payload, base_url):
    try: root = ET.fromstring(payload)
    except ET.ParseError as exc: raise ValueError("invalid podcast feed: %s" % exc)
    entries = []
    if local(root.tag) in ("rss", "rdf"):
        channel = next((n for n in root.iter() if local(n.tag) == "channel"), root)
        nodes = [n for n in channel if local(n.tag) == "item"]
        for node in nodes:
            row = {"title": "", "guid": "", "url": "", "date": None}
            for child in node:
                name, val = local(child.tag), (child.text or "").strip()
                if name == "title": row["title"] = val
                elif name in ("guid", "id"): row["guid"] = val
                elif name in ("pubdate", "published", "updated", "date") and row["date"] is None: row["date"] = date_value(val)
                elif name == "enclosure" and "audio" in (child.attrib.get("type") or "audio").lower():
                    row["url"] = urllib.parse.urljoin(base_url, child.attrib.get("url", ""))
            if row["url"]: entries.append(row)
    elif local(root.tag) == "feed":
        for node in root:
            if local(node.tag) != "entry": continue
            row = {"title": "", "guid": "", "url": "", "date": None}
            for child in node:
                name, val = local(child.tag), (child.text or "").strip()
                if name == "title": row["title"] = val
                elif name == "id": row["guid"] = val
                elif name in ("published", "updated") and row["date"] is None: row["date"] = date_value(val)
                elif name == "link" and child.attrib.get("rel") == "enclosure":
                    row["url"] = urllib.parse.urljoin(base_url, child.attrib.get("href", ""))
            if row["url"]: entries.append(row)
    else: raise ValueError("expected RSS or Atom podcast feed")
    return entries


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "MIT-1.125-intelligence-pipeline/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=20) as response: return response.read(10_000_000)
    except (urllib.error.URLError, TimeoutError, OSError) as exc: raise RuntimeError("could not fetch %s: %s" % (url, exc))


def get_config(path):
    try:
        project = json.loads((path / "config/project.json").read_text(encoding="utf-8"))
        sources = json.loads((path / "config/sources.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc: raise ConfigError("cannot read run config snapshot: %s" % exc)
    cap = project.get("max_items_per_source", 3) if isinstance(project, dict) else None
    if isinstance(cap, bool) or not isinstance(cap, int) or cap < 1: raise ConfigError("max_items_per_source must be positive")
    if not isinstance(sources, list): raise ConfigError("sources snapshot must be an array")
    selected = []
    for index, src in enumerate(sources):
        if not isinstance(src, dict): raise ConfigError("source %d must be an object" % index)
        if src.get("kind") != "podcast": continue
        for key in ("source_id", "publisher_id", "url"):
            if not isinstance(src.get(key), str) or not src[key]: raise ConfigError("podcast source %d requires %s" % (index, key))
        selected.append(src)
    return selected, cap


def save_receipt(path, started, input_count, output, errors, caps):
    logs = path / "logs"; logs.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    rec = {"stage": "collectors/fetch_podcasts.sh", "status": "failed" if errors else "completed",
           "input_count": input_count, "output_count": len(output), "started_at": started, "finished_at": utc_now(),
           "tools": ["Python standard library", "urllib", "ElementTree"], "cost_usd": None,
           "cap_truncations": caps, "errors": errors}
    with (logs / ("fetch-podcasts-%s-%d.json" % (stamp, os.getpid()))).open("x", encoding="utf-8") as f:
        json.dump(rec, f, ensure_ascii=False, sort_keys=True); f.write("\n")


def main(argv):
    if len(argv) != 1: raise ConfigError("usage: fetch_podcasts.sh RUN_DIR")
    path = run_path(argv[0]); started = utc_now(); sources, cap = get_config(path)
    output, errors, caps = [], [], []
    for src in sources:
        try:
            entries = parse_feed(fetch(src["url"]), src["url"])
            entries.sort(key=lambda x: x["date"] or dt.datetime.min.replace(tzinfo=dt.timezone.utc), reverse=True)
            if len(entries) > cap: caps.append({"source_id": src["source_id"], "items_omitted": len(entries) - cap})
            for row in entries[:cap]:
                identity = row["guid"] or row["url"]
                output.append({"item_id": "podcast:" + identity, "source_id": src["source_id"],
                    "publisher_id": src["publisher_id"], "kind": "podcast", "title": row["title"] or row["url"],
                    "url": row["url"], "published_at": row["date"].isoformat().replace("+00:00", "Z") if row["date"] else None,
                    "retrieved_at": utc_now(), "media_url": row["url"]})
        except (RuntimeError, ValueError) as exc: errors.append({"source_id": src["source_id"], "error": str(exc)})
    save_receipt(path, started, len(sources), output, errors, caps)
    for rec in output: print(json.dumps(rec, ensure_ascii=False, separators=(",", ":")))
    return 1 if errors else 0


if __name__ == "__main__":
    try: sys.exit(main(sys.argv[1:]))
    except ConfigError as exc:
        print("collectors/fetch_podcasts.sh: %s" % exc, file=sys.stderr); sys.exit(2)
