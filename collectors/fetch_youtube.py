#!/usr/bin/env python3
"""Discover YouTube videos from channel or playlist Atom feeds."""

import datetime as dt
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CHANNEL_ID = re.compile(r"(?:channel/|\"channelId\":\"|\"externalId\":\")(UC[\w-]{22})")
VIDEO_ID = re.compile(r"[A-Za-z0-9_-]{11}")


class ConfigError(Exception): pass


class SourceNotFound(RuntimeError): pass


def local(tag): return tag.rsplit("}", 1)[-1].lower()


def utc_now(): return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def repo_path(rel):
    if not isinstance(rel, str) or not rel or os.path.isabs(rel): raise ConfigError("RUN_DIR must be repository-relative")
    path = (ROOT / rel).resolve()
    if path != ROOT and ROOT not in path.parents: raise ConfigError("RUN_DIR escapes the repository")
    return path


def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0 (compatible; MIT-1.125-pipeline/1.0)"})
    try:
        with urllib.request.urlopen(req, timeout=20) as response: return response.read(10_000_000).decode("utf-8", "replace")
    except urllib.error.HTTPError as exc:
        if exc.code == 404: raise SourceNotFound("could not fetch %s: HTTP 404 Not Found" % url) from exc
        raise RuntimeError("could not fetch %s: %s" % (url, exc)) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc: raise RuntimeError("could not fetch %s: %s" % (url, exc)) from exc


def feed_url_for(source):
    url = source["url"]
    if url.startswith("file://"):
        return url
    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qs(parsed.query)
    if query.get("list"):
        return "https://www.youtube.com/feeds/videos.xml?playlist_id=" + urllib.parse.quote(query["list"][0])
    match = re.search(r"/channel/(UC[\w-]{22})", parsed.path)
    if match:
        return "https://www.youtube.com/feeds/videos.xml?channel_id=" + match.group(1)
    if re.search(r"/watch$|youtu\.be/", url):
        return None
    html = fetch(url)
    match = CHANNEL_ID.search(html)
    if not match:
        raise RuntimeError("could not find a channel ID in the YouTube page")
    return "https://www.youtube.com/feeds/videos.xml?channel_id=" + match.group(1)


def parse_atom(text, source):
    try: root = ET.fromstring(text)
    except ET.ParseError as exc: raise ValueError("invalid YouTube Atom feed: %s" % exc)
    if local(root.tag) != "feed": raise ValueError("expected an Atom feed")
    items = []
    for entry in root:
        if local(entry.tag) != "entry": continue
        data = {"title": "", "video_id": "", "url": "", "published_at": None}
        for child in entry:
            name, value = local(child.tag), (child.text or "").strip()
            if name == "title": data["title"] = value
            elif name == "videoid": data["video_id"] = value
            elif name == "id" and not data["video_id"]:
                match = re.search(r"(?:video:|v=)([A-Za-z0-9_-]{11})", value)
                if match: data["video_id"] = match.group(1)
            elif name == "link" and child.attrib.get("rel", "alternate") == "alternate":
                data["url"] = child.attrib.get("href", "")
            elif name == "published": data["published_at"] = value
        if data["video_id"] and not data["url"]:
            data["url"] = "https://www.youtube.com/watch?v=" + data["video_id"]
        if data["video_id"]:
            items.append(data)
    return items


def fallback_channel_listing(source, cap):
    """Recover dated channel uploads when YouTube's Atom endpoint returns 404."""
    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError("yt-dlp is required for the configured channel fallback") from exc
    channel_id = urllib.parse.parse_qs(urllib.parse.urlsplit(source["url"]).query).get("channel_id", [None])[0]
    if not channel_id or not re.fullmatch(r"UC[\w-]{22}", channel_id):
        raise RuntimeError("channel fallback needs a channel_id Atom URL")
    seen, rows = set(), []
    options = {"quiet": True, "no_warnings": True, "skip_download": True,
               "extract_flat": "in_playlist", "playlistend": cap, "cachedir": False}
    try:
        with yt_dlp.YoutubeDL(options) as ydl:
            for tab in ("videos", "shorts"):
                listing = ydl.extract_info("https://www.youtube.com/channel/%s/%s" % (channel_id, tab), download=False)
                for entry in (listing or {}).get("entries") or []:
                    if not isinstance(entry, dict): continue
                    video_id = entry.get("id")
                    if not isinstance(video_id, str) or not VIDEO_ID.fullmatch(video_id) or video_id in seen: continue
                    seen.add(video_id)
                    info = ydl.extract_info("https://www.youtube.com/watch?v=" + video_id, download=False)
                    if not isinstance(info, dict) or info.get("channel_id") != channel_id:
                        continue
                    stamp = info.get("timestamp")
                    if isinstance(stamp, (int, float)):
                        published = dt.datetime.fromtimestamp(stamp, dt.timezone.utc).isoformat()
                    else:
                        date = info.get("upload_date")
                        try: published = dt.datetime.strptime(date, "%Y%m%d").replace(tzinfo=dt.timezone.utc).isoformat()
                        except (TypeError, ValueError): continue
                    rows.append({"video_id": video_id, "url": info.get("webpage_url") or "https://www.youtube.com/watch?v=" + video_id,
                                 "title": info.get("title") or entry.get("title") or video_id, "published_at": published})
    except Exception as exc:
        raise RuntimeError("channel listing fallback failed for %s: %s" % (source["source_id"], exc)) from exc
    if not rows:
        raise RuntimeError("channel listing fallback returned no dated videos for %s" % source["source_id"])
    return rows


def load_config(path):
    try:
        project = json.loads((path / "config/project.json").read_text(encoding="utf-8"))
        sources = json.loads((path / "config/sources.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc: raise ConfigError("cannot read run config snapshot: %s" % exc)
    if not isinstance(project, dict) or not isinstance(sources, list): raise ConfigError("invalid project or source snapshot shape")
    cap = project.get("max_items_per_source", 3)
    if isinstance(cap, bool) or not isinstance(cap, int) or cap < 1: raise ConfigError("max_items_per_source must be positive")
    selected = []
    for i, src in enumerate(sources):
        if not isinstance(src, dict): raise ConfigError("source %d must be an object" % i)
        if src.get("kind") != "youtube": continue
        if not all(isinstance(src.get(k), str) and src[k] for k in ("source_id", "publisher_id", "url")):
            raise ConfigError("youtube source %d needs source_id, publisher_id, and url" % i)
        selected.append(src)
    return selected, cap


def save_receipt(path, started, input_count, output, errors, warnings, caps):
    logs = path / "logs"; logs.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    rec = {"stage": "collectors/fetch_youtube.sh", "status": "failed" if errors else "completed",
           "input_count": input_count, "output_count": len(output), "started_at": started, "finished_at": utc_now(),
           "tools": ["Python standard library", "YouTube Atom feed"], "cost_usd": None,
           "cap_truncations": caps, "errors": errors, "warnings": warnings}
    with (logs / ("fetch-youtube-%s-%d.json" % (stamp, os.getpid()))).open("x", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, sort_keys=True); fh.write("\n")


def main(argv):
    if len(argv) != 1: raise ConfigError("usage: fetch_youtube.sh RUN_DIR")
    path = repo_path(argv[0]); started = utc_now(); sources, cap = load_config(path)
    output, errors, warnings, caps = [], [], [], []
    for source in sources:
        try:
            feed_url = feed_url_for(source)
            if feed_url is None:
                # A configured individual video has no channel Atom listing; keep its native ID and metadata.
                parsed = urllib.parse.urlsplit(source["url"])
                vid = urllib.parse.parse_qs(parsed.query).get("v", [parsed.path.rstrip("/").split("/")[-1]])[0]
                if not VIDEO_ID.fullmatch(vid): raise ValueError("individual video URL has no valid video ID")
                rows = [{"video_id": vid, "url": "https://www.youtube.com/watch?v=" + vid,
                         "title": source.get("title", vid), "published_at": source.get("published_at")}]
            else:
                try:
                    rows = parse_atom(fetch(feed_url), source)
                except SourceNotFound as exc:
                    if not source.get("fallback_channel_listing"):
                        raise
                    rows = fallback_channel_listing(source, cap)
                    warnings.append({"source_id": source["source_id"], "warning": str(exc) + "; recovered from dated channel listing"})
            rows.sort(key=lambda r: r.get("published_at") or "", reverse=True)
            if len(rows) > cap: caps.append({"source_id": source["source_id"], "items_omitted": len(rows) - cap})
            for row in rows[:cap]:
                video_id = row["video_id"]
                output.append({"item_id": "youtube:" + video_id, "source_id": source["source_id"],
                    "publisher_id": source["publisher_id"], "kind": "youtube", "title": row.get("title") or video_id,
                    "url": row.get("url") or "https://www.youtube.com/watch?v=" + video_id,
                    "published_at": row.get("published_at"), "retrieved_at": utc_now(), "media_url": None})
        except SourceNotFound as exc:
            detail = {"source_id": source["source_id"], "warning": str(exc)}
            if source.get("warn_on_404") is True:
                warnings.append(detail)
                print("fetch_youtube: warning: %s: %s" % (source["source_id"], exc), file=sys.stderr)
            else:
                errors.append({"source_id": source["source_id"], "error": str(exc)})
        except (RuntimeError, ValueError) as exc: errors.append({"source_id": source["source_id"], "error": str(exc)})
    save_receipt(path, started, len(sources), output, errors, warnings, caps)
    for rec in output: print(json.dumps(rec, ensure_ascii=False, separators=(",", ":")))
    return 1 if errors else 0


if __name__ == "__main__":
    try: sys.exit(main(sys.argv[1:]))
    except ConfigError as exc:
        print("collectors/fetch_youtube.sh: %s" % exc, file=sys.stderr); sys.exit(2)
