"""Offline tests for tools/find_feeds.py, using local file:// fixtures (no network)."""
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.environ.get("REPO_ROOT") or os.path.dirname(HERE)
TOOLS = os.path.join(REPO, "tools")
sys.path.insert(0, TOOLS)

try:
    import find_feeds as ff
except ImportError:  # tool not copied into this repo
    ff = None

AS_OF = dt.date(2026, 10, 15)

RSS = """<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0" xmlns:itunes="http://www.itunes.com/dtds/podcast-1.0.dtd" xmlns:dc="http://purl.org/dc/elements/1.1/">
<channel><title>Fixture Feed</title>
<item><title>Inside window, newest</title><link>https://example.test/a</link><pubDate>Thu, 08 Oct 2026 12:00:00 GMT</pubDate></item>
<item><title>Inside window, first day of 30</title><link>https://example.test/b</link><pubDate>Wed, 16 Sep 2026 00:00:00 GMT</pubDate></item>
<item><title>Day before the 30-day window</title><link>https://example.test/c</link><pubDate>Tue, 15 Sep 2026 23:59:59 GMT</pubDate></item>
<item><title>Inside a 45-day window only</title><link>https://example.test/d</link><pubDate>Mon, 07 Sep 2026 10:00:00 GMT</pubDate></item>
<item><title>No date</title><link>https://example.test/e</link></item>
</channel></rss>"""

PODCAST = """<?xml version="1.0"?><rss version="2.0"><channel><title>Fixture Pod</title>
<item><title>Episode 2</title><pubDate>Sat, 10 Oct 2026 08:00:00 +0000</pubDate>
<enclosure url="https://example.test/ep2.mp3" type="audio/mpeg" length="1"/></item>
<item><title>Episode 1</title><pubDate>Sat, 03 Oct 2026 08:00:00 +0000</pubDate>
<enclosure url="https://example.test/ep1.mp3" type="audio/mpeg" length="1"/></item></channel></rss>"""

ATOM = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"><title>Fixture Atom</title>
<entry><title>Atom one</title><link rel="alternate" href="https://example.test/atom1"/>
<published>2026-10-12T09:30:00Z</published><updated>2026-10-13T09:30:00Z</updated></entry>
<entry><title>Atom two</title><link rel="alternate" href="https://example.test/atom2"/>
<updated>2026-08-01T00:00:00+00:00</updated></entry></feed>"""


def page(link_tag=""):
    return f"<html><head><title>x</title>{link_tag}</head><body><p>hello</p></body></html>"


@unittest.skipIf(ff is None, "tools/find_feeds.py not present")
class TestFeedFinder(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.mkdtemp(prefix="feedfinder-")

        def write(rel, text):
            p = os.path.join(cls.tmp, rel)
            os.makedirs(os.path.dirname(p), exist_ok=True)
            with open(p, "w", encoding="utf-8") as f:
                f.write(text)
            return "file://" + p

        cls.u = {
            "linked": write("linked/index.html", page('<link rel="alternate" type="application/rss+xml" href="feed.xml">')),
            "atom": write("atom/index.html", page('<link rel="alternate" type="application/atom+xml" href="atom.xml">')),
            "podcast": write("podcast/index.html", page('<link rel="alternate" type="application/rss+xml" href="pod.xml">')),
            "probe": write("probe/index.html", page()),
            "nofeed": write("nofeed/index.html", page()),
            "direct": write("direct/feed.xml", RSS),
        }
        write("linked/feed.xml", RSS)
        write("atom/atom.xml", ATOM)
        write("podcast/pod.xml", PODCAST)
        write("probe/feed.xml", RSS)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def inspect(self, key, kind="feed", window=30):
        entry = {"source_id": key, "publisher_id": f"pub-{key}", "kind": kind, "url": self.u[key]}
        return ff.inspect_source(entry, AS_OF, window)

    def test_finds_feed_from_link_rel_alternate(self):
        r = self.inspect("linked")
        self.assertEqual(r["status"], "ok")
        self.assertTrue(r["feed_url"].endswith("/linked/feed.xml"))
        self.assertEqual(r["title"], "Fixture Feed")
        self.assertEqual(r["total"], 5)

    def test_window_30_counts_the_boundary_day_but_not_the_day_before(self):
        r = self.inspect("linked", window=30)
        self.assertEqual(r["in_window"], 2, "Oct 8 and Sept 16 are in 30 days ending Oct 15; Sept 15 is not")
        self.assertEqual(r["undated"], 1)

    def test_window_45_adds_the_september_items(self):
        r = self.inspect("linked", window=45)
        self.assertEqual(r["in_window"], 4, "45 days ending Oct 15 starts Sept 1")

    def test_latest_items_are_sorted_newest_first_with_dates(self):
        r = self.inspect("linked")
        dates = [i["date"] for i in r["latest"]]
        self.assertEqual(dates, sorted(dates, reverse=True))
        self.assertEqual(dates[0], "2026-10-08")

    def test_finds_atom_feed_and_uses_published_over_updated(self):
        r = self.inspect("atom")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["latest"][0]["date"], "2026-10-12")
        self.assertEqual(r["in_window"], 1)

    def test_detects_podcast_from_audio_enclosures(self):
        r = self.inspect("podcast", kind="podcast")
        self.assertEqual(r["detected_kind"], "podcast")
        self.assertTrue(r["latest"][0]["audio"])
        self.assertFalse(any("looks like" in n for n in r["notes"]), "kind matches the feed, so no kind warning")

    def test_warns_when_listed_kind_does_not_match_the_feed(self):
        r = self.inspect("podcast", kind="feed")
        self.assertTrue(any("looks like 'podcast'" in n for n in r["notes"]))

    def test_probes_common_paths_when_the_page_has_no_feed_link(self):
        r = self.inspect("probe")
        self.assertEqual(r["status"], "ok")
        self.assertTrue(r["feed_url"].endswith("/probe/feed.xml"))
        self.assertTrue(any("probing" in n for n in r["notes"]))

    def test_accepts_a_direct_feed_url(self):
        r = self.inspect("direct")
        self.assertEqual(r["status"], "ok")
        self.assertEqual(r["feed_url"], self.u["direct"])

    def test_reports_no_feed_without_inventing_one(self):
        r = self.inspect("nofeed")
        self.assertEqual(r["status"], "no_feed")
        self.assertIsNone(r["feed_url"])

    def test_reports_a_fetch_error_for_a_missing_page(self):
        entry = {"source_id": "gone", "publisher_id": "p", "kind": "feed", "url": "file:///definitely/not/here.html"}
        r = ff.inspect_source(entry, AS_OF, 30)
        self.assertEqual(r["status"], "error")
        self.assertTrue(any("could not fetch" in n for n in r["notes"]))

    def test_parse_feed_rejects_html_and_garbage(self):
        self.assertIsNone(ff.parse_feed("<html><body>hi</body></html>"))
        self.assertIsNone(ff.parse_feed("not xml at all"))
        self.assertFalse(ff.looks_like_feed("<html><head></head></html>"))

    # ---- YouTube (no network) -------------------------------------------------
    def test_youtube_channel_id_from_page_html(self):
        cid = "UC" + "a" * 22
        for html in (f'..."channelId":"{cid}"...', f'<meta itemprop="channelId" content="{cid}">',
                     f'..."externalId":"{cid}"...'):
            self.assertEqual(ff.youtube_feed_from_html(html),
                             f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}")
        self.assertIsNone(ff.youtube_feed_from_html("<html>no id here</html>"))

    def test_youtube_channel_and_playlist_urls_resolve_without_fetching(self):
        cid = "UC" + "b" * 22
        url, _ = ff.youtube_feed_for_url(f"https://www.youtube.com/channel/{cid}", 5, False)
        self.assertEqual(url, f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}")
        url, _ = ff.youtube_feed_for_url("https://www.youtube.com/playlist?list=PLabc123", 5, False)
        self.assertEqual(url, "https://www.youtube.com/feeds/videos.xml?playlist_id=PLabc123")

    def test_youtube_atom_feed_parses_video_dates(self):
        atom = """<feed xmlns="http://www.w3.org/2005/Atom" xmlns:yt="http://www.youtube.com/xml/schemas/2015">
        <title>Chan</title><entry><title>Vid</title><link rel="alternate" href="https://www.youtube.com/watch?v=x"/>
        <published>2026-10-01T10:00:00+00:00</published></entry></feed>"""
        f = ff.parse_feed(atom)
        self.assertEqual(f["items"][0]["date"].date().isoformat(), "2026-10-01")

    # ---- heuristics and input file ----------------------------------------------
    def test_github_pages_sites_also_probe_the_repos_atom_feeds(self):
        _, probes = ff.candidate_feed_urls("https://mit-cdfg.github.io/Survey-AI-for-3D-modeling-Robotics/", page())
        self.assertIn("https://github.com/mit-cdfg/Survey-AI-for-3D-modeling-Robotics/releases.atom", probes)

    def test_read_candidates_skips_comments_and_reports_bad_lines(self):
        p = os.path.join(self.tmp, "cands.txt")
        with open(p, "w") as f:
            f.write("# comment\n\na | pub-a | feed | https://x.test/  # trailing\nbad line\nb | pub-b | rss | https://y.test\n")
        got = ff.read_candidates(p)
        self.assertEqual(got, [{"source_id": "a", "publisher_id": "pub-a", "kind": "feed", "url": "https://x.test/"}])

    def test_cli_emits_verified_entries_for_sources_json(self):
        cands = os.path.join(self.tmp, "cli.txt")
        out = os.path.join(self.tmp, "draft.json")
        with open(cands, "w") as f:
            f.write(f"good | pub-good | feed | {self.u['linked']}\n")
            f.write(f"pod | pub-pod | podcast | {self.u['podcast']}\n")
            f.write(f"bad | pub-bad | feed | {self.u['nofeed']}\n")
        r = subprocess.run([sys.executable, os.path.join(TOOLS, "find_feeds.py"), cands, "--as-of", "2026-10-15",
                            "--window", "30", "--emit", out], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stderr)
        with open(out, encoding="utf-8") as fh:
            data = json.load(fh)
        self.assertEqual([d["source_id"] for d in data], ["good", "pod"], "only verified sources are emitted")
        self.assertEqual(data[1]["kind"], "podcast")
        self.assertTrue(all(d["url"].startswith("file://") for d in data))
        self.assertIn("Still to resolve by hand: bad", r.stdout)
        self.assertIn("2 of 3 sources verified", r.stdout)


if __name__ == "__main__":
    unittest.main()
