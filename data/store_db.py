#!/usr/bin/env python3
"""SQLite implementation for the data/store.sh evidence-store interface."""

import datetime as dt
import json
import os
import sqlite3
import sys
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DB_DIR = ROOT / "data" / "evidence"
DB_PATH = DB_DIR / "index.sqlite3"

ITEM_FIELDS = {
    "item_id": str,
    "source_id": str,
    "publisher_id": str,
    "kind": str,
    "title": str,
    "url": str,
    "published_at": (str, type(None)),
    "retrieved_at": str,
    "media_url": (str, type(None)),
    "version_id": str,
    "text_path": str,
    "segments_path": (str, type(None)),
}


class InputError(Exception):
    pass


def utc_now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def connect():
    DB_DIR.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(str(DB_PATH)
    )
    db.execute("PRAGMA foreign_keys = ON")
    return db


def initialize(db):
    db.executescript(
        """
        CREATE TABLE IF NOT EXISTS versions (
            item_id TEXT NOT NULL,
            version_id TEXT NOT NULL,
            payload TEXT NOT NULL,
            first_seen_at TEXT NOT NULL,
            PRIMARY KEY (item_id, version_id)
        );
        CREATE TABLE IF NOT EXISTS current_items (
            item_id TEXT PRIMARY KEY,
            version_id TEXT NOT NULL,
            FOREIGN KEY (item_id, version_id)
                REFERENCES versions(item_id, version_id)
        );
        CREATE TABLE IF NOT EXISTS observations (
            item_id TEXT NOT NULL,
            version_id TEXT NOT NULL,
            run_dir TEXT NOT NULL,
            observed_at TEXT NOT NULL,
            PRIMARY KEY (item_id, version_id, run_dir),
            FOREIGN KEY (item_id, version_id)
                REFERENCES versions(item_id, version_id)
        );
        """
    )
    db.commit()


def valid_item(item, line_number):
    if not isinstance(item, dict):
        raise InputError("line %d: item must be a JSON object" % line_number)
    for key, expected in ITEM_FIELDS.items():
        if key not in item:
            raise InputError("line %d: missing required field %s" % (line_number, key))
        if not isinstance(item[key], expected):
            raise InputError("line %d: invalid type for %s" % (line_number, key))
    if item["kind"] not in ("feed", "youtube", "podcast"):
        raise InputError("line %d: kind must be feed, youtube, or podcast" % line_number)
    if not item["item_id"] or not item["version_id"]:
        raise InputError("line %d: item_id and version_id must be nonempty" % line_number)
    return item


def read_items():
    items = []
    for number, line in enumerate(sys.stdin, 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise InputError("line %d: malformed JSON: %s" % (number, exc))
        items.append(valid_item(item, number))
    return items


def write_receipt(run_dir, status, input_count, output_count, started, error=None):
    logs = ROOT / run_dir / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    path = logs / ("store-%s-%d.json" % (stamp, os.getpid()))
    receipt = {
        "stage": "data/store.sh upsert",
        "status": status,
        "input_count": input_count,
        "output_count": output_count,
        "started_at": started,
        "finished_at": utc_now(),
        "tools": ["Python standard library", "SQLite"],
        "cost_usd": None,
    }
    if error:
        receipt["errors"] = [error]
    with path.open("x", encoding="utf-8") as fh:
        json.dump(receipt, fh, ensure_ascii=False, sort_keys=True)
        fh.write("\n")


def upsert(run_dir):
    started = utc_now()
    items = read_items()  # Validate the complete stream before modifying persistent state.
    if not run_dir or os.path.isabs(run_dir):
        raise InputError("RUN_DIR must be a nonempty repository-relative path")
    run_path = (ROOT / run_dir).resolve()
    if ROOT not in run_path.parents and run_path != ROOT:
        raise InputError("RUN_DIR must stay within the repository")
    changes = []
    try:
        with connect() as db:
            initialize(db)
            for item in items:
                item_id = item["item_id"]
                version_id = item["version_id"]
                payload = json.dumps(item, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                row = db.execute(
                    "SELECT version_id FROM current_items WHERE item_id = ?", (item_id,)
                ).fetchone()
                previous = row[0] if row else None
                if previous is None:
                    change = "new"
                elif previous == version_id:
                    change = "unchanged"
                else:
                    change = "changed"
                db.execute(
                    "INSERT OR IGNORE INTO versions(item_id, version_id, payload, first_seen_at) VALUES (?, ?, ?, ?)",
                    (item_id, version_id, payload, utc_now()),
                )
                # Keep the first version payload intact; only the current pointer changes on a new version.
                db.execute(
                    "INSERT INTO current_items(item_id, version_id) VALUES (?, ?) "
                    "ON CONFLICT(item_id) DO UPDATE SET version_id = excluded.version_id",
                    (item_id, version_id),
                )
                db.execute(
                    "INSERT OR IGNORE INTO observations(item_id, version_id, run_dir, observed_at) VALUES (?, ?, ?, ?)",
                    (item_id, version_id, run_dir, utc_now()),
                )
                changes.append({"item_id": item_id, "version_id": version_id, "change": change})
        for record in changes:
            print(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
    except sqlite3.Error as exc:
        write_receipt(run_dir, "failed", len(items), 0, started, str(exc))
        raise
    write_receipt(run_dir, "completed", len(items), len(changes), started)


def emit(rows):
    for row in rows:
        print(row[0])


def list_items():
    if not DB_PATH.exists():
        return
    with connect() as db:
        initialize(db)
        rows = db.execute(
            "SELECT v.payload FROM current_items c JOIN versions v "
            "ON v.item_id = c.item_id AND v.version_id = c.version_id ORDER BY c.item_id"
        ).fetchall()
    emit(rows)


def get_item(item_id, version_id=None):
    if not DB_PATH.exists():
        raise LookupError("item not found: %s" % item_id)
    with connect() as db:
        initialize(db)
        if version_id is None:
            row = db.execute(
                "SELECT v.payload FROM current_items c JOIN versions v "
                "ON v.item_id = c.item_id AND v.version_id = c.version_id WHERE c.item_id = ?",
                (item_id,),
            ).fetchone()
        else:
            row = db.execute(
                "SELECT payload FROM versions WHERE item_id = ? AND version_id = ?",
                (item_id, version_id),
            ).fetchone()
    if row is None:
        raise LookupError("item or version not found: %s%s" % (item_id, " / " + version_id if version_id else ""))
    emit([row])


def main(argv):
    if not argv:
        raise InputError("usage: store.sh init | upsert RUN_DIR | list | get ITEM_ID [VERSION_ID]")
    command = argv[0]
    if command == "init" and len(argv) == 1:
        with connect() as db:
            initialize(db)
        return 0
    if command == "upsert" and len(argv) == 2:
        upsert(argv[1])
        return 0
    if command == "list" and len(argv) == 1:
        list_items()
        return 0
    if command == "get" and len(argv) in (2, 3):
        get_item(argv[1], argv[2] if len(argv) == 3 else None)
        return 0
    raise InputError("invalid arguments; usage: store.sh init | upsert RUN_DIR | list | get ITEM_ID [VERSION_ID]")


if __name__ == "__main__":
    try:
        sys.exit(main(sys.argv[1:]))
    except InputError as exc:
        print("data/store.sh: %s" % exc, file=sys.stderr)
        sys.exit(2)
    except LookupError as exc:
        print("data/store.sh: %s" % exc, file=sys.stderr)
        sys.exit(1)
    except (OSError, sqlite3.Error) as exc:
        print("data/store.sh: storage operation failed: %s" % exc, file=sys.stderr)
        sys.exit(1)
