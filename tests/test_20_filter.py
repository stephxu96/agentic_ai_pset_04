"""processing/filter_items.sh: the date window, exclusion reasons, and the configurable window length."""
import datetime as dt
import os
import unittest

import contracts
from harness import PipelineTest, to_jsonl, d, ts, days_before, AS_OF


class TestFilter(PipelineTest):
    REQUIRES = ["processing/filter_items.sh"]

    def run_filter(self, items, window=30, as_of=AS_OF, run_id="run-f"):
        rd = self.sb.make_run(run_id, as_of=as_of, window=window)
        p = self.sb.run("processing/filter_items.sh", [rd], stdin=to_jsonl(items))
        eligible = self.jsonl(p) if p.returncode == 0 else []
        excl = []
        if self.sb.exists(rd + "/exclusions.jsonl"):
            excl = self.sb.read_jsonl(rd + "/exclusions.jsonl")
        return rd, p, eligible, excl

    def item(self, key, published, kind="feed"):
        return self.sb.make_item(key, kind, f"pub-{key}", published=published, assets=False)

    def reasons(self, excl):
        return {e["item_id"]: e["reason"] for e in excl}

    # ---- the 30-day window ---------------------------------------------------
    def test_window_is_inclusive_as_of_minus_29_through_as_of(self):
        start = days_before(AS_OF, 29)
        items = [
            self.item("start-day-first-second", ts(start, 0, 0, 0)),
            self.item("as-of-last-second", ts(AS_OF, 23, 59, 59)),
            self.item("as-of-midday", ts(AS_OF, 12)),
            self.item("day-before-start", ts(days_before(AS_OF, 30), 23, 59, 59)),
            self.item("day-after-as-of", ts(d(AS_OF) + dt.timedelta(days=1), 0, 0, 0)),
        ]
        rd, p, eligible, excl = self.run_filter(items)
        self.assert_exit(p, 0)
        self.assertEqual(sorted(e["item_id"] for e in eligible),
                         ["feed:as-of-last-second", "feed:as-of-midday", "feed:start-day-first-second"],
                         "30 calendar dates in UTC: as-of minus 29 days through as-of, inclusive")
        r = self.reasons(excl)
        self.assertEqual(r.get("feed:day-before-start"), "outside_window")
        self.assertEqual(r.get("feed:day-after-as-of"), "future_date")

    def test_window_uses_the_runs_as_of_date_not_todays_date(self):
        items = [self.item("in", ts("2026-03-01")), self.item("out", ts("2026-01-01"))]
        _, p, eligible, excl = self.run_filter(items, as_of="2026-03-10", run_id="run-old")
        self.assert_exit(p, 0)
        self.assertEqual([e["item_id"] for e in eligible], ["feed:in"],
                         "the window must be computed from run.json's as_of_date")
        self.assertEqual(self.reasons(excl), {"feed:out": "outside_window"})

    def test_unknown_and_invalid_dates_are_excluded_with_reasons(self):
        items = [self.item("none", None), self.item("garbage", "not-a-date"),
                 self.item("impossible", "2026-13-45T00:00:00Z"), self.item("ok", ts(days_before(AS_OF, 3)))]
        _, p, eligible, excl = self.run_filter(items)
        self.assert_exit(p, 0, "bad dates are exclusions, not failures")
        self.assertEqual([e["item_id"] for e in eligible], ["feed:ok"])
        r = self.reasons(excl)
        self.assertEqual(r.get("feed:none"), "unknown_date")
        self.assertEqual(r.get("feed:garbage"), "invalid_date")
        self.assertEqual(r.get("feed:impossible"), "invalid_date")

    def test_retrieval_date_does_not_make_old_material_eligible(self):
        old = self.item("old", ts(days_before(AS_OF, 100)))
        old["retrieved_at"] = f"{AS_OF}T10:00:00Z"
        _, p, eligible, excl = self.run_filter([old])
        self.assertEqual(eligible, [])
        self.assertEqual(self.reasons(excl), {"feed:old": "outside_window"})

    def test_previously_seen_in_window_material_stays_eligible(self):
        seen = self.item("seen", ts(days_before(AS_OF, 4)))
        seen["retrieved_at"] = ts(days_before(AS_OF, 3))  # retrieved in an earlier run
        _, p, eligible, _ = self.run_filter([seen])
        self.assertEqual([e["item_id"] for e in eligible], ["feed:seen"],
                         "unchanged material is not excluded merely for being unchanged")

    # ---- the configurable window ----------------------------------------------
    def test_window_length_comes_from_the_run_config_snapshot_45_days(self):
        items = [
            self.item("d44", ts(days_before(AS_OF, 44))),
            self.item("d45", ts(days_before(AS_OF, 45))),
            self.item("d35", ts(days_before(AS_OF, 35))),
        ]
        _, p, eligible, excl = self.run_filter(items, window=45)
        self.assert_exit(p, 0)
        self.assertEqual(sorted(e["item_id"] for e in eligible), ["feed:d35", "feed:d44"],
                         "with freshness_window_days=45 the window is as-of minus 44 days through as-of")
        self.assertEqual(self.reasons(excl), {"feed:d45": "outside_window"})

    def test_same_item_is_excluded_under_30_but_eligible_under_45(self):
        it = self.item("d35", ts(days_before(AS_OF, 35)))
        _, _, el30, ex30 = self.run_filter([it], window=30, run_id="run-30")
        _, _, el45, ex45 = self.run_filter([it], window=45, run_id="run-45")
        self.assertEqual((len(el30), len(ex30)), (0, 1))
        self.assertEqual((len(el45), len(ex45)), (1, 0))

    # ---- partition and record shape --------------------------------------------
    def test_every_input_is_either_eligible_or_excluded_never_both(self):
        items = [self.item("a", ts(days_before(AS_OF, 1))), self.item("b", ts(days_before(AS_OF, 50))),
                 self.item("c", None), self.item("d", ts(days_before(AS_OF, 10)), kind="podcast")]
        _, p, eligible, excl = self.run_filter(items)
        ids_in = {i["item_id"] for i in items}
        ids_el = {e["item_id"] for e in eligible}
        ids_ex = {e["item_id"] for e in excl}
        self.assertEqual(ids_el | ids_ex, ids_in)
        self.assertEqual(ids_el & ids_ex, set())

    def test_eligible_records_pass_through_unchanged(self):
        it = self.item("a", ts(days_before(AS_OF, 2)))
        _, _, eligible, _ = self.run_filter([it])
        self.assertEqual(eligible, [it], "the filter is mechanical; it must not alter item records")

    def test_exclusion_records_have_required_fields(self):
        items = [self.item("a", ts(days_before(AS_OF, 99))), self.item("b", None)]
        _, _, _, excl = self.run_filter(items)
        self.assertEqual(len(excl), 2)
        self.assert_valid(contracts.validate_exclusion, excl, "exclusion")
        for e in excl:
            self.assertTrue(e["detail"].strip(), "detail should say why (dates involved)")

    def test_exclusions_file_exists_even_when_nothing_is_excluded(self):
        rd, p, eligible, excl = self.run_filter([self.item("a", ts(days_before(AS_OF, 1)))])
        self.assert_exit(p, 0)
        self.assertTrue(self.sb.exists(rd + "/exclusions.jsonl"),
                        "write exclusions.jsonl even when empty, so 'none excluded' is a recorded result")
        self.assertEqual(excl, [])

    def test_empty_input_is_a_successful_empty_result(self):
        rd, p, eligible, excl = self.run_filter([])
        self.assert_exit(p, 0)
        self.assertEqual((eligible, excl), ([], []))

    def test_rerunning_does_not_duplicate_exclusion_records(self):
        items = [self.item("a", ts(days_before(AS_OF, 99)))]
        rd, _, _, _ = self.run_filter(items)
        self.sb.run("processing/filter_items.sh", [rd], stdin=to_jsonl(items))
        self.assertEqual(len(self.sb.read_jsonl(rd + "/exclusions.jsonl")), 1)

    # ---- failure behavior and receipts ------------------------------------------
    def test_missing_run_dir_argument_is_exit_2(self):
        self.assert_exit(self.sb.run("processing/filter_items.sh", [], stdin=""), 2)

    def test_run_json_without_as_of_date_is_exit_2(self):
        rd = self.sb.make_run("run-bad")
        self.sb.write_json(rd + "/run.json", {"run_id": "run-bad", "mode": "live"})
        p = self.sb.run("processing/filter_items.sh", [rd], stdin="")
        self.assert_exit(p, 2, "invalid configuration")

    def test_malformed_input_is_exit_2(self):
        rd = self.sb.make_run("run-m")
        p = self.sb.run("processing/filter_items.sh", [rd], stdin="definitely not json\n")
        self.assert_exit(p, 2)

    def test_receipts_are_written_and_preserved_on_rerun(self):
        items = [self.item("a", ts(days_before(AS_OF, 1)))]
        rd, _, _, _ = self.run_filter(items)
        self.sb.run("processing/filter_items.sh", [rd], stdin=to_jsonl(items))
        logs = sorted(f for f in os.listdir(self.sb.path(rd + "/logs")) if not f.startswith("."))
        self.assertGreaterEqual(len(logs), 2, "uniquely named receipt per invocation; earlier ones preserved")
        missing = contracts.receipt_missing_concepts(self.sb.read_json(rd + "/logs/" + logs[0]))
        self.assertFalse(missing, f"receipt is missing: {missing}")


if __name__ == "__main__":
    unittest.main()
