"""data/store.sh: init, upsert, list, get; duplicates, versions, history, exit codes."""
import hashlib
import json
import os
import unittest

import contracts
from harness import read_file, PipelineTest, ts, days_before, AS_OF


def tree_state(root):
    state = {}
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d != ".git"]
        for fn in filenames:
            p = os.path.join(dirpath, fn)
            try:
                state[os.path.relpath(p, root)] = hashlib.sha256(read_file(p, "rb")).hexdigest()
            except OSError:
                pass
    return state


class TestStore(PipelineTest):
    REQUIRES = ["data/store.sh"]

    def setUp(self):
        super().setUp()
        self.rd = self.sb.make_run()

    def items(self, *keys, **kw):
        return [self.sb.make_item(k, "feed", f"pub-{k}", **kw) for k in keys]

    # ---- init ------------------------------------------------------------
    def test_init_succeeds_creates_storage_and_prints_no_records(self):
        p = self.sb.store("init")
        self.assert_exit(p, 0)
        self.assertEqual(p.stdout.strip(), "", "init must emit no record output")
        self.assertTrue(self.sb.exists("data/evidence"), "init should create data/evidence/")

    def test_init_is_idempotent(self):
        self.assert_exit(self.sb.store("init"), 0)
        self.assert_exit(self.sb.store("init"), 0, "second init")

    def test_init_does_not_erase_existing_evidence(self):
        self.sb.store("init")
        self.sb.upsert(self.rd, self.items("a"))
        self.assert_exit(self.sb.store("init"), 0)
        p = self.sb.store("list")
        self.assert_exit(p, 0)
        self.assertEqual([r["item_id"] for r in self.jsonl(p)], ["feed:a"])

    # ---- upsert ------------------------------------------------------------
    def test_first_upsert_emits_one_new_record_per_input_in_order(self):
        its = self.items("c", "a", "b")
        p = self.sb.upsert(self.rd, its)
        recs = self.jsonl(p)
        self.assertEqual(len(recs), 3, "one change record per input record")
        self.assert_valid(contracts.validate_change, recs, "change")
        self.assertEqual([r["item_id"] for r in recs], [i["item_id"] for i in its], "input order must be preserved")
        self.assertEqual({r["change"] for r in recs}, {"new"})
        self.assertEqual([r["version_id"] for r in recs], [i["version_id"] for i in its])

    def test_replaying_identical_input_is_unchanged_and_creates_no_duplicates(self):
        its = self.items("a", "b", "c")
        self.sb.upsert(self.rd, its)
        recs = self.jsonl(self.sb.upsert(self.rd, its))
        self.assertEqual({r["change"] for r in recs}, {"unchanged"})
        listed = self.jsonl(self.sb.store("list"))
        self.assertEqual(len(listed), 3, "replay must not create duplicate items")

    def test_duplicate_within_one_ingestion_is_new_only_once(self):
        a, b = self.items("a", "b")
        recs = self.jsonl(self.sb.upsert(self.rd, [a, a, b]))
        self.assertEqual(len(recs), 3)
        self.assertEqual(recs[0]["change"], "new")
        self.assertEqual(recs[1]["change"], "unchanged", "only the first occurrence can be new or changed")
        self.assertEqual(recs[2]["change"], "new")
        self.assertEqual(len(self.jsonl(self.sb.store("list"))), 2)

    def test_new_version_of_existing_item_is_changed_and_history_is_kept(self):
        v1 = self.sb.make_item("a", "feed", "pub-a", text="First version of the article text.")
        v2 = self.sb.make_item("a", "feed", "pub-a", text="Second version with a substantive correction.")
        self.assertNotEqual(v1["version_id"], v2["version_id"])
        self.sb.upsert(self.rd, [v1])
        recs = self.jsonl(self.sb.upsert(self.rd, [v2]))
        self.assertEqual(recs[0]["change"], "changed")
        self.assertEqual(recs[0]["version_id"], v2["version_id"])
        listed = self.jsonl(self.sb.store("list"))
        self.assertEqual(len(listed), 1, "list gives one record per item_id")
        self.assertEqual(listed[0]["version_id"], v2["version_id"], "list must return the latest version")
        latest = self.jsonl(self.sb.store("get", "feed:a"))
        self.assertEqual(latest[0]["version_id"], v2["version_id"])
        old = self.jsonl(self.sb.store("get", "feed:a", v1["version_id"]))
        self.assertEqual(old[0]["version_id"], v1["version_id"], "earlier versions must stay retrievable")

    def test_retrieval_timestamp_alone_does_not_create_a_version(self):
        base = self.sb.make_item("a", "feed", "pub-a", retrieved=f"{AS_OF}T08:00:00Z")
        later = dict(base, retrieved_at=f"{AS_OF}T20:00:00Z")
        self.sb.upsert(self.rd, [base])
        recs = self.jsonl(self.sb.upsert(self.rd, [later]))
        self.assertEqual(recs[0]["change"], "unchanged", "a new retrieval time alone is not a content change")

    def test_upsert_requires_run_dir_argument(self):
        p = self.sb.store("upsert", stdin="")
        self.assert_exit(p, 2, "missing RUN_DIR is an invalid argument")

    def test_unknown_subcommand_is_exit_2(self):
        self.assert_exit(self.sb.store("frobnicate"), 2)

    def test_no_subcommand_is_exit_2(self):
        self.assert_exit(self.sb.store(), 2)

    def test_malformed_json_input_is_exit_2(self):
        p = self.sb.store("upsert", self.rd, stdin="this is not json\n")
        self.assert_exit(p, 2, "malformed input")

    def test_record_missing_required_field_is_exit_2(self):
        bad = self.items("a")[0]
        del bad["item_id"]
        p = self.sb.store("upsert", self.rd, stdin=json.dumps(bad) + "\n")
        self.assert_exit(p, 2, "item without item_id is malformed")

    def test_upsert_writes_a_receipt_and_keeps_earlier_ones(self):
        its = self.items("a")
        self.sb.upsert(self.rd, its)
        self.sb.upsert(self.rd, its)
        logs = [f for f in os.listdir(self.sb.path(self.rd + "/logs")) if not f.startswith(".")]
        self.assertGreaterEqual(len(logs), 2, "each invocation writes a uniquely named receipt; reruns keep earlier ones")
        rec = json.loads(self.sb.read(self.rd + "/logs/" + sorted(logs)[0]))
        missing = contracts.receipt_missing_concepts(rec)
        self.assertFalse(missing, f"receipt is missing: {missing}")

    def test_only_writes_under_data_evidence_assets_and_the_run_dir(self):
        self.sb.store("init")
        before = tree_state(self.sb.root)
        self.sb.upsert(self.rd, self.items("a", "b"))
        after = tree_state(self.sb.root)
        changed = [p for p in after if before.get(p) != after[p]]
        allowed = ("data/evidence", "data/assets", "runs/")
        stray = [p for p in changed if not p.startswith(allowed)]
        self.assertFalse(stray, f"store.sh wrote files outside its area: {stray}")

    # ---- list --------------------------------------------------------------
    def test_list_on_empty_store_is_exit_0_with_no_records(self):
        self.sb.store("init")
        p = self.sb.store("list")
        self.assert_exit(p, 0)
        self.assertEqual(self.jsonl(p), [])

    def test_list_includes_old_material_for_the_filter_to_assess(self):
        old = self.sb.make_item("old", "feed", "pub-o", published=ts(days_before(AS_OF, 90)))
        new = self.sb.make_item("new", "feed", "pub-n")
        self.sb.upsert(self.rd, [old, new])
        listed = self.jsonl(self.sb.store("list"))
        self.assertEqual({r["item_id"] for r in listed}, {"feed:old", "feed:new"})

    def test_list_emits_valid_item_records(self):
        its = [self.sb.make_item("a", "feed", "pub-a"), self.sb.make_item("y", "youtube", "pub-y"),
               self.sb.make_item("p", "podcast", "pub-p")]
        self.sb.upsert(self.rd, its)
        self.assert_valid(contracts.validate_item, self.jsonl(self.sb.store("list")), "item")

    def test_unknown_publication_date_is_preserved_as_null(self):
        it = self.sb.make_item("a", "feed", "pub-a")
        it["published_at"] = None
        self.sb.upsert(self.rd, [it])
        listed = self.jsonl(self.sb.store("list"))
        self.assertIsNone(listed[0]["published_at"], "unknown dates must stay null, never invented")

    # ---- get ---------------------------------------------------------------
    def test_get_missing_item_is_exit_1_with_diagnostic(self):
        self.sb.store("init")
        p = self.sb.store("get", "feed:nope")
        self.assert_exit(p, 1, "absent item")
        self.assertTrue(p.stderr.strip(), "should print a diagnostic to stderr")
        self.assertEqual(p.stdout.strip(), "")

    def test_get_missing_version_is_exit_1(self):
        self.sb.upsert(self.rd, self.items("a"))
        self.assert_exit(self.sb.store("get", "feed:a", "no-such-version"), 1)

    def test_get_emits_exactly_one_item_record(self):
        its = self.items("a", "b")
        self.sb.upsert(self.rd, its)
        recs = self.jsonl(self.sb.store("get", "feed:b"))
        self.assertEqual(len(recs), 1)
        self.assert_valid(contracts.validate_item, recs, "item")
        self.assertEqual(recs[0]["item_id"], "feed:b")


if __name__ == "__main__":
    unittest.main()
