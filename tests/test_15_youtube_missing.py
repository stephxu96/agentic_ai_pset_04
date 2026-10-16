"""A known optional channel 404 is visible but does not fail collection."""

import contextlib
import importlib.util
import io
import json
import pathlib
import tempfile
import unittest
import urllib.error
from unittest import mock


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "collectors" / "fetch_youtube.py"
SPEC = importlib.util.spec_from_file_location("fetch_youtube_under_test", MODULE_PATH)
youtube = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(youtube)


class TestOptionalMissingYoutubeSource(unittest.TestCase):
    def run_collector(self, optional, failure):
        with tempfile.TemporaryDirectory() as folder:
            run = pathlib.Path(folder)
            (run / "config").mkdir()
            (run / "config" / "project.json").write_text('{"max_items_per_source":3}', encoding="utf-8")
            (run / "config" / "sources.json").write_text(json.dumps([{
                "source_id": "onshape", "publisher_id": "onshape", "kind": "youtube",
                "url": "https://www.youtube.com/feeds/videos.xml?channel_id=UCTvd5lUSLtTH8Qcd7Pl1nQg",
                "warn_on_404": optional,
            }]), encoding="utf-8")
            stdout, stderr = io.StringIO(), io.StringIO()
            with mock.patch.object(youtube, "repo_path", return_value=run), \
                    mock.patch.object(youtube, "fetch", side_effect=failure), \
                    contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
                code = youtube.main(["runs/example"])
            receipts = list((run / "logs").glob("fetch-youtube-*.json"))
            self.assertEqual(len(receipts), 1)
            return code, json.loads(receipts[0].read_text(encoding="utf-8")), stdout.getvalue(), stderr.getvalue()

    def test_optional_404_is_a_visible_warning(self):
        code, receipt, stdout, stderr = self.run_collector(True, youtube.SourceNotFound("HTTP 404 Not Found"))
        self.assertEqual(code, 0)
        self.assertEqual(receipt["status"], "completed")
        self.assertEqual(receipt["errors"], [])
        self.assertEqual(receipt["warnings"][0]["source_id"], "onshape")
        self.assertEqual(receipt["output_count"], 0)
        self.assertEqual(stdout, "")
        self.assertIn("warning", stderr)

    def test_required_404_still_fails(self):
        code, receipt, _, stderr = self.run_collector(False, youtube.SourceNotFound("HTTP 404 Not Found"))
        self.assertEqual(code, 1)
        self.assertEqual(receipt["status"], "failed")
        self.assertEqual(receipt["warnings"], [])
        self.assertEqual(receipt["errors"][0]["source_id"], "onshape")
        self.assertEqual(stderr, "")

    def test_optional_source_other_failure_still_fails(self):
        code, receipt, _, _ = self.run_collector(True, RuntimeError("HTTP 503"))
        self.assertEqual(code, 1)
        self.assertEqual(receipt["errors"][0]["source_id"], "onshape")
        self.assertEqual(receipt["warnings"], [])

    def test_actual_http_404_maps_to_missing_source(self):
        error = urllib.error.HTTPError("https://www.youtube.com/feed", 404, "Not Found", {}, None)
        with mock.patch.object(youtube.urllib.request, "urlopen", side_effect=error):
            with self.assertRaises(youtube.SourceNotFound):
                youtube.fetch("https://www.youtube.com/feed")


if __name__ == "__main__":
    unittest.main()
