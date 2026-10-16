#!/usr/bin/env python3
"""Find and verify RSS/Atom/YouTube feeds for your sources.json. Python 3 standard library only.

Input is a text file with one source per line:

    source_id | publisher_id | kind | url        (kind is feed, podcast or youtube; '#' starts a comment)

For each line the tool fetches the page, finds the feed (a <link rel="alternate"> tag, a feed link, or common
paths such as /feed and /rss.xml), parses it, and reports the feed URL, the latest items, and how many items
fall inside your freshness window. For YouTube channels it resolves the channel ID and the feed URL.

Usage (from the repo root):
    python3 tools/find_feeds.py tools/candidate_sites.txt
    python3 tools/find_feeds.py tools/candidate_sites.txt --as-of 2026-10-15 --window 45 --emit sources_draft.json

The window defaults to freshness_window_days in config/project.json (else 45), and the as-of date to today (UTC).
--emit writes ready-to-merge sources.json entries for the sources it verified. Nothing is changed otherwise.
"""
import argparse
import datetime as dt
import email.utils
import json
import os
import re
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser

UA = "Mozilla/5.0 (compatible; feed-finder/1.0; student project)"
COMMON_PATHS = ["feed", "feed/", "rss", "rss.xml", "feed.xml", "atom.xml", "index.xml",
                "blog/feed", "blog/rss.xml", "blog/feed.xml", "rss/feed.xml", "feeds/posts/default"]
YT_ID_PATTERNS = [r'"channelId":"(UC[\w-]{22})"', r'"externalId":"(UC[\w-]{22})"',
                  r'<meta itemprop="channelId" content="(UC[\w-]{22})"', r'channel/(UC[\w-]{22})']


class FetchError(Exception):
    pass


def fetch(url, timeout=20, insecure=False):
    """Return (final_url, text). Raises FetchError with a readable reason."""
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*"})
    ctx = ssl._create_unverified_context() if insecure else None
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=ctx) as resp:
            raw = resp.read(6_000_000)
            final = resp.geturl()
            charset = resp.headers.get_content_charset() if hasattr(resp.headers, "get_content_charset") else None
    except urllib.error.HTTPError as e:
        raise FetchError(f"HTTP {e.code}")
    except urllib.error.URLError as e:
        reason = str(e.reason)
        if "CERTIFICATE_VERIFY_FAILED" in reason:
            raise FetchError("SSL certificate check failed (on macOS run 'Install Certificates.command' for your "
                             "Python, or retry with --insecure)")
        raise FetchError(reason)
    except (TimeoutError, OSError) as e:
        raise FetchError(str(e))
    return final, raw.decode(charset or "utf-8", errors="replace")


class LinkFinder(HTMLParser):
    def __init__(self):
        super().__init__()
        self.alternates, self.anchors = [], []

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "link" and "alternate" in a.get("rel", "").lower() and a.get("href"):
            t = a.get("type", "").lower()
            if any(w in t for w in ("rss", "atom", "feed", "xml")):
                self.alternates.append(a["href"])
        elif tag == "a" and a.get("href"):
            if re.search(r"(rss|atom|feed)(\.xml|/)?($|\?)|\.rss$", a["href"], re.I):
                self.anchors.append(a["href"])


def looks_like_feed(text):
    head = text.lstrip()[:600].lower()
    return head.startswith("<?xml") and ("<rss" in head or "<feed" in head or "<rdf" in head) or \
        head.startswith(("<rss", "<feed", "<rdf"))


def local(tag):
    return tag.split("}")[-1]


def parse_date(s):
    if not s:
        return None
    s = s.strip()
    try:
        d = email.utils.parsedate_to_datetime(s)
    except (TypeError, ValueError):
        d = None
    if d is None:
        try:
            d = dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
        except ValueError:
            return None
    if d.tzinfo is None:
        d = d.replace(tzinfo=dt.timezone.utc)
    return d.astimezone(dt.timezone.utc)


def parse_feed(text):
    """Return {'title': str, 'items': [{'title','link','date','audio'}]} or None if it is not a feed."""
    try:
        root = ET.fromstring(text.lstrip())
    except ET.ParseError:
        return None
    kind = local(root.tag)
    title, items = "", []
    if kind == "rss" or kind == "RDF":
        for el in root.iter():
            n = local(el.tag)
            if n == "channel":
                for c in el:
                    if local(c.tag) == "title":
                        title = (c.text or "").strip()
                        break
            if n == "item":
                it = {"title": "", "link": "", "date": None, "audio": False}
                for c in el:
                    cn = local(c.tag)
                    if cn == "title":
                        it["title"] = (c.text or "").strip()
                    elif cn == "link" and not it["link"]:
                        it["link"] = (c.text or "").strip()
                    elif cn in ("pubDate", "date", "published", "updated") and it["date"] is None:
                        it["date"] = parse_date(c.text)
                    elif cn == "enclosure" and "audio" in (c.get("type") or "").lower():
                        it["audio"] = True
                items.append(it)
    elif kind == "feed":
        for c in root:
            if local(c.tag) == "title":
                title = (c.text or "").strip()
        for el in root:
            if local(el.tag) != "entry":
                continue
            it = {"title": "", "link": "", "date": None, "audio": False}
            for c in el:
                cn = local(c.tag)
                if cn == "title":
                    it["title"] = (c.text or "").strip()
                elif cn == "link":
                    rel = c.get("rel", "alternate")
                    if rel == "alternate" and not it["link"]:
                        it["link"] = c.get("href", "")
                    elif rel == "enclosure" and "audio" in (c.get("type") or "").lower():
                        it["audio"] = True
                elif cn in ("published", "updated") and (it["date"] is None or cn == "published"):
                    it["date"] = parse_date(c.text)
            items.append(it)
    else:
        return None
    return {"title": title, "items": items}


def youtube_feed_from_html(html):
    for pat in YT_ID_PATTERNS:
        m = re.search(pat, html)
        if m:
            return f"https://www.youtube.com/feeds/videos.xml?channel_id={m.group(1)}"
    return None


def youtube_feed_for_url(url, timeout, insecure):
    """Return (feed_url, notes)."""
    p = urllib.parse.urlparse(url)
    q = urllib.parse.parse_qs(p.query)
    if "list" in q:
        return f"https://www.youtube.com/feeds/videos.xml?playlist_id={q['list'][0]}", []
    m = re.search(r"/channel/(UC[\w-]{22})", p.path)
    if m:
        return f"https://www.youtube.com/feeds/videos.xml?channel_id={m.group(1)}", []
    _, html = fetch(url, timeout, insecure)
    feed = youtube_feed_from_html(html)
    return feed, ([] if feed else ["could not find a channel ID in the page (YouTube may have shown a consent page)"])


def candidate_feed_urls(page_url, html):
    base_urls, found = [], []
    lf = LinkFinder()
    try:
        lf.feed(html)
    except Exception:  # malformed HTML
        pass
    for h in lf.alternates + lf.anchors:
        u = urllib.parse.urljoin(page_url, h)
        if u not in found:
            found.append(u)
    p = urllib.parse.urlparse(page_url)
    roots = []
    folder = page_url.rsplit("/", 1)[0] + "/" if p.path and not p.path.endswith("/") else page_url
    if folder not in roots:
        roots.append(folder)
    origin = f"{p.scheme}://{p.netloc}/" if p.netloc else folder
    if origin not in roots:
        roots.append(origin)
    probes = []
    for r in roots:
        for path in COMMON_PATHS:
            u = urllib.parse.urljoin(r, path)
            if u not in found and u not in probes:
                probes.append(u)
    if p.netloc.endswith(".github.io"):
        owner = p.netloc.split(".")[0]
        parts = [s for s in p.path.split("/") if s]
        if parts:
            repo = f"https://github.com/{owner}/{parts[0]}"
            probes = [repo + "/releases.atom", repo + "/commits/main.atom"] + probes
    return found, probes


def inspect_source(entry, as_of, window_days, timeout=20, insecure=False, max_probes=14):
    start = as_of - dt.timedelta(days=window_days - 1)
    res = {"source_id": entry["source_id"], "publisher_id": entry["publisher_id"], "kind": entry["kind"],
           "input_url": entry["url"], "status": "error", "feed_url": None, "title": "", "total": 0,
           "in_window": 0, "undated": 0, "latest": [], "detected_kind": None, "notes": []}
    try:
        if entry["kind"] == "youtube":
            feed_url, notes = youtube_feed_for_url(entry["url"], timeout, insecure)
            res["notes"] += notes
            candidates, probes = ([feed_url] if feed_url else []), []
        else:
            final, html = fetch(entry["url"], timeout, insecure)
            if looks_like_feed(html):
                candidates, probes = [final], []
            else:
                candidates, probes = candidate_feed_urls(final, html)
                if not candidates:
                    res["notes"].append("no feed link in the page; probing common paths")
    except FetchError as e:
        res["notes"].append(f"could not fetch the page: {e}")
        return res
    tried = 0
    for url in candidates + probes:
        if url in probes:
            if tried >= max_probes:
                break
            tried += 1
        try:
            _, text = fetch(url, timeout, insecure)
        except FetchError:
            continue
        feed = parse_feed(text) if looks_like_feed(text) else None
        if not feed or not feed["items"]:
            continue
        items = feed["items"]
        dated = [i for i in items if i["date"]]
        dated.sort(key=lambda i: i["date"], reverse=True)
        res.update(status="ok", feed_url=url, title=feed["title"], total=len(items),
                   undated=len(items) - len(dated),
                   in_window=sum(1 for i in dated if start <= i["date"].date() <= as_of),
                   latest=[{"date": i["date"].date().isoformat(), "title": i["title"][:90], "audio": i["audio"]}
                           for i in dated[:3]])
        res["detected_kind"] = "podcast" if any(i["audio"] for i in items) else ("youtube" if "youtube.com/feeds" in url else "feed")
        if "github.com" in url:
            res["notes"].append("GitHub Atom feed: items are releases or commits, useful as a freshness signal, not as articles")
        if entry["kind"] != "youtube" and res["detected_kind"] not in (entry["kind"],):
            res["notes"].append(f"you listed kind '{entry['kind']}' but the feed looks like '{res['detected_kind']}'")
        if res["in_window"] == 0:
            res["notes"].append("no items inside the window")
        return res
    res["status"] = "no_feed"
    res["notes"].append("no working feed found; check the site in a browser or use its YouTube/Apple Podcasts page")
    return res


def read_candidates(path):
    out = []
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f, 1):
            line = line.split("#", 1)[0].strip()
            if not line:
                continue
            parts = [p.strip() for p in line.split("|")]
            if len(parts) != 4 or parts[2] not in ("feed", "podcast", "youtube"):
                sys.stderr.write(f"line {n}: expected 'source_id | publisher_id | kind | url', got: {line}\n")
                continue
            out.append({"source_id": parts[0], "publisher_id": parts[1], "kind": parts[2], "url": parts[3]})
    return out


def default_window(repo_root):
    try:
        with open(os.path.join(repo_root, "config", "project.json"), encoding="utf-8") as f:
            return int(json.load(f).get("freshness_window_days", 45))
    except (OSError, ValueError, json.JSONDecodeError):
        return 45


def main():
    ap = argparse.ArgumentParser(description="Find and verify feeds for sources.json")
    ap.add_argument("candidates", help="text file: source_id | publisher_id | kind | url")
    ap.add_argument("--as-of", help="YYYY-MM-DD (default: today, UTC)")
    ap.add_argument("--window", type=int, help="window length in days (default: project.json or 45)")
    ap.add_argument("--emit", metavar="PATH", help="write verified sources.json entries to PATH")
    ap.add_argument("--json", action="store_true", help="print raw results as JSON")
    ap.add_argument("--timeout", type=int, default=20)
    ap.add_argument("--insecure", action="store_true", help="skip SSL certificate verification")
    a = ap.parse_args()
    repo = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    as_of = dt.date.fromisoformat(a.as_of) if a.as_of else dt.datetime.now(dt.timezone.utc).date()
    window = a.window or default_window(repo)
    start = as_of - dt.timedelta(days=window - 1)
    entries = read_candidates(a.candidates)
    results = []
    if not a.json:
        print(f"Window: {start} .. {as_of} ({window} days)\n")
    for e in entries:
        r = inspect_source(e, as_of, window, a.timeout, a.insecure)
        results.append(r)
        if a.json:
            continue
        mark = {"ok": "OK  ", "no_feed": "MISS", "error": "FAIL"}[r["status"]]
        print(f"[{mark}] {r['source_id']}  ({r['kind']}, publisher {r['publisher_id']})")
        print(f"       input: {r['input_url']}")
        if r["feed_url"]:
            print(f"       feed:  {r['feed_url']}   \"{r['title'][:60]}\"")
            print(f"       items: {r['total']} total, {r['in_window']} in window, {r['undated']} undated")
            for it in r["latest"]:
                print(f"       latest {it['date']}  {it['title']}{'  [audio]' if it['audio'] else ''}")
        for n in r["notes"]:
            print(f"       note:  {n}")
        print()
    if a.json:
        print(json.dumps(results, indent=2))
    ok = [r for r in results if r["status"] == "ok"]
    if not a.json:
        print(f"{len(ok)} of {len(results)} sources verified; "
              f"{sum(1 for r in ok if r['in_window'])} have items inside the window.")
        missed = [r["source_id"] for r in results if r["status"] != "ok"]
        if missed:
            print("Still to resolve by hand: " + ", ".join(missed))
    if a.emit:
        out = [{"source_id": r["source_id"], "publisher_id": r["publisher_id"],
                "kind": r["kind"] if r["kind"] == "youtube" else (r["detected_kind"] or r["kind"]),
                "url": r["feed_url"],
                "note": f"Verified {as_of}: {r['in_window']} item(s) in the {window}-day window; latest "
                        f"{r['latest'][0]['date'] if r['latest'] else 'n/a'}."} for r in ok]
        with open(a.emit, "w", encoding="utf-8") as f:
            json.dump(out, f, indent=2)
            f.write("\n")
        print(f"Wrote {len(out)} entries to {a.emit}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
