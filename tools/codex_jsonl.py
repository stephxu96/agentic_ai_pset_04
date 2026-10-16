#!/usr/bin/env python3
"""Invoke Codex CLI, retain raw attempts, and accept only validated strict JSONL."""

import datetime as dt
import json
import os
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class CodexError(Exception):
    pass


def utc_now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def strict_jsonl(text, validator=None):
    records = []
    lines = text.splitlines()
    if not lines or not any(line.strip() for line in lines):
        raise ValueError("response is empty")
    for number, line in enumerate(lines, 1):
        if not line.strip():
            raise ValueError("blank line at %d; strict JSONL permits no empty records" % number)
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError("line %d is not JSON: %s" % (number, exc))
        if not isinstance(record, dict):
            raise ValueError("line %d must be a JSON object" % number)
        if validator:
            problem = validator(record, len(records))
            if problem:
                raise ValueError(problem)
        records.append(record)
    return records


def _strings_with_key(obj, sought):
    found = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key == sought and isinstance(value, str) and value:
                found.append(value)
            found.extend(_strings_with_key(value, sought))
    elif isinstance(obj, list):
        for value in obj:
            found.extend(_strings_with_key(value, sought))
    return found


def write_json(path, value):
    with path.open("x", encoding="utf-8") as fh:
        json.dump(value, fh, ensure_ascii=False, sort_keys=True)
        fh.write("\n")


def invoke(run_path, stage, prompt, validator=None, batch_validator=None, input_count=None):
    logs = run_path / "logs"
    logs.mkdir(parents=True, exist_ok=True)
    started = utc_now()
    stem = "%s-%s" % (stage.replace("/", "-").replace(".", "-"), uuid.uuid4().hex)
    binary = os.environ.get("CODEX_BIN", "codex")
    last_error = ""
    model_name = None
    valid_records = None
    attempts = []
    for attempt in (1, 2):
        valid_records = None
        full_prompt = prompt
        if attempt == 2:
            full_prompt += "\n\nRETRY: Your prior response did not pass strict JSONL validation: %s. " \
                           "Return the complete corrected response now. Output only JSONL, one JSON object per line." % last_error
        with tempfile.TemporaryDirectory(prefix="pipeline-codex-") as temp:
            response_path = Path(temp) / "last-message.txt"
            command = [binary, "exec", "--cd", str(ROOT), "--ephemeral", "--sandbox", "read-only",
                       "--json", "--output-last-message", str(response_path), "-"]
            if not (ROOT / ".git").exists():
                command.insert(2, "--skip-git-repo-check")
            try:
                proc = subprocess.run(command, input=full_prompt, capture_output=True, text=True,
                                      cwd=str(ROOT), timeout=1800)
            except (OSError, subprocess.TimeoutExpired) as exc:
                proc = None
                error = "Codex invocation failed: %s" % exc
                event_text, error_text, final_text = "", str(exc), ""
            else:
                event_text, error_text = proc.stdout, proc.stderr
                final_text = response_path.read_text(encoding="utf-8", errors="replace") if response_path.exists() else ""
                if proc.returncode != 0:
                    error = "Codex exited %d: %s" % (proc.returncode, error_text.strip()[-1000:])
                else:
                    error = ""
            attempts.append({"attempt": attempt, "exit_code": proc.returncode if proc else None})
            for suffix, content in (("events.jsonl", event_text), ("response.txt", final_text), ("stderr.txt", error_text)):
                (logs / (stem + "-attempt-%d.%s" % (attempt, suffix))).write_text(content, encoding="utf-8")
            for line in event_text.splitlines():
                try:
                    event = json.loads(line)
                except json.JSONDecodeError:
                    continue
                names = _strings_with_key(event, "model")
                if names:
                    model_name = names[-1]
            if not error:
                try:
                    valid_records = strict_jsonl(final_text, validator)
                    if batch_validator:
                        problem = batch_validator(valid_records)
                        if problem:
                            raise ValueError(problem)
                except ValueError as exc:
                    error = str(exc)
                    valid_records = None
            if not error:
                break
            last_error = error

    finished = utc_now()
    receipt = {"stage": stage, "status": "completed" if valid_records is not None else "failed",
               "input_count": input_count, "output_count": len(valid_records) if valid_records is not None else 0,
               "started_at": started, "finished_at": finished,
               "tools": ["Codex CLI"], "model": model_name or "default, name not reported",
               "cost_usd": None, "attempts": attempts}
    if valid_records is None:
        receipt["errors"] = [last_error]
    write_json(logs / (stem + "-receipt.json"), receipt)
    if valid_records is None:
        raise CodexError("%s failed after one retry: %s" % (stage, last_error))
    return valid_records


def read_jsonl(path):
    rows = []
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError("%s:%d: %s" % (path, number, exc))
        if not isinstance(value, dict):
            raise ValueError("%s:%d must be a JSON object" % (path, number))
        rows.append(value)
    return rows


def write_jsonl(records):
    return "".join(json.dumps(rec, ensure_ascii=False, separators=(",", ":")) + "\n" for rec in records)


if __name__ == "__main__":
    print("codex_jsonl.py is a library for the editorial and content stages", file=sys.stderr)
    sys.exit(2)
