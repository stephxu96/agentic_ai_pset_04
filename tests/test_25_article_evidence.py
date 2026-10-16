"""Article inputs keep cited context without flooding the model with long pages."""

import importlib.util
import pathlib
import unittest


MODULE_PATH = pathlib.Path(__file__).resolve().parents[1] / "content" / "write_articles.py"
SPEC = importlib.util.spec_from_file_location("write_articles_under_test", MODULE_PATH)
articles = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(articles)


class TestCitedArticleEvidence(unittest.TestCase):
    def test_long_written_source_keeps_exact_distant_quote(self):
        body = "lead " + ("x" * 200_000) + "Exact cited result" + ("y" * 200_000)
        excerpt = articles.cited_text_excerpt(body, ["Exact cited result"])
        self.assertIn("lead", excerpt)
        self.assertIn("Exact cited result", excerpt)
        self.assertIn("uncited source text omitted", excerpt)
        self.assertLess(len(excerpt), 7_000)

    def test_missing_written_quote_is_an_error(self):
        with self.assertRaises(articles.InputError):
            articles.cited_text_excerpt("retained version", ["invented quote"])

    def test_media_keeps_cited_segment_and_neighbors(self):
        segments = [{"segment_id": "s%04d" % n, "text": str(n)} for n in range(100)]
        excerpt = articles.cited_segments(segments, {"s0050"})
        self.assertEqual([x["segment_id"] for x in excerpt],
                         ["s0048", "s0049", "s0050", "s0051", "s0052"])
        with self.assertRaises(articles.InputError):
            articles.cited_segments(segments, {"s0100"})


if __name__ == "__main__":
    unittest.main()
