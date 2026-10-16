#!/usr/bin/env python3
"""Extract written evidence and timestamped media transcripts from candidates."""

import datetime as dt
import hashlib
import html
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.error
import urllib.request
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_DURATION_SECONDS = 90 * 60


class InputError(Exception):
    pass


def utc_now():
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def safe_path(rel):
    if not isinstance(rel, str) or not rel or os.path.isabs(rel):
        raise InputError("expected a repository-relative path")
    path = (ROOT / rel).resolve()
    if path != ROOT and ROOT not in path.parents:
        raise InputError("path escapes the repository: %s" % rel)
    return path


def parse_input():
    rows = []
    required = ("item_id", "source_id", "publisher_id", "kind", "title", "url", "published_at", "retrieved_at", "media_url")
    for n, line in enumerate(sys.stdin, 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise InputError("line %d: malformed JSON: %s" % (n, exc))
        if not isinstance(item, dict) or any(k not in item for k in required):
            raise InputError("line %d: candidate is missing required fields" % n)
        if item.get("kind") not in ("feed", "youtube", "podcast"):
            raise InputError("line %d: unsupported candidate kind" % n)
        for key in required:
            if key != "published_at" and key != "media_url" and not isinstance(item.get(key), str):
                raise InputError("line %d: %s must be a string" % (n, key))
        rows.append(item)
    return rows


class MainText(HTMLParser):
    """A standard-library article/main extractor; ignores navigation and boilerplate tags."""
    SKIP = {"script", "style", "nav", "header", "footer", "aside", "form", "noscript", "svg"}
    BLOCKS = {"article", "main"}

    def __init__(self):
        HTMLParser.__init__(self, convert_charrefs=True)
        self.skip_depth = 0
        self.main_depth = 0
        self.blocks = []
        self.current = []
        self.all_text = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        if tag in self.SKIP:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag in self.BLOCKS:
            self.main_depth += 1
        if tag in ("p", "h1", "h2", "h3", "li", "blockquote"):
            self.current.append("\n")

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag in self.SKIP and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if tag in self.BLOCKS and self.main_depth:
            self.main_depth -= 1
        if tag in ("p", "h1", "h2", "h3", "li", "blockquote"):
            self.current.append("\n")

    def handle_data(self, data):
        if self.skip_depth:
            return
        value = re.sub(r"\s+", " ", data).strip()
        if not value:
            return
        self.all_text.append(value)
        if self.main_depth:
            self.blocks.append(value)

    def result(self):
        selected = self.blocks if self.blocks else self.all_text
        return re.sub(r"\n{3,}", "\n\n", "\n".join(selected)).strip()


def html_text(payload):
    parser = MainText()
    parser.feed(payload.decode("utf-8", "replace"))
    parser.close()
    text = parser.result()
    if len(text) < 80:
        raise RuntimeError("page extraction produced too little substantive text")
    return text


def fetch_page(url):
    req = urllib.request.Request(url, headers={"User-Agent": "MIT-1.125-intelligence-pipeline/1.0", "Accept": "text/html,application/xhtml+xml"})
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            payload = response.read(12_000_000)
            content_type = response.headers.get("Content-Type", "").lower()
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError("could not retrieve written source: %s" % exc)
    if "html" not in content_type and not payload.lstrip().startswith((b"<!DOCTYPE html", b"<html", b"<article", b"<main")):
        # Some static fixtures omit a Content-Type; XML feeds are not usable source text here.
        raise RuntimeError("retrieved page is not HTML")
    return html_text(payload)


def media_metadata(url):
    binary = os.environ.get("YT_DLP_BIN") or str(ROOT / ".venv" / "bin" / "yt-dlp")
    if not os.path.isfile(binary) or not os.access(binary, os.X_OK):
        binary = "yt-dlp"
    try:
        proc = subprocess.run([binary, "--no-warnings", "--no-playlist", "--dump-single-json", "--skip-download", url],
                              cwd=str(ROOT), capture_output=True, text=True, timeout=180)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("yt-dlp metadata lookup failed: %s" % exc)
    if proc.returncode != 0:
        raise RuntimeError("yt-dlp metadata lookup failed: %s" % proc.stderr.strip()[-500:])
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        raise RuntimeError("yt-dlp returned invalid metadata JSON")


def parse_vtt(path):
    text = path.read_text(encoding="utf-8", errors="replace")
    segments, last_text = [], None
    lines = text.replace("\r", "").split("\n")
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        if "-->" not in line:
            i += 1
            continue
        match = re.match(r"([0-9:.]+)\s+-->\s+([0-9:.]+)", line)
        i += 1
        parts = []
        while i < len(lines) and lines[i].strip():
            raw = re.sub(r"<[^>]+>", "", lines[i]).strip()
            raw = html.unescape(raw)
            if raw and raw != last_text:
                parts.append(raw)
                last_text = raw
            i += 1
        if match and parts:
            segments.append({"segment_id": "s%04d" % (len(segments) + 1),
                             "start_seconds": vtt_seconds(match.group(1)),
                             "end_seconds": vtt_seconds(match.group(2)), "text": " ".join(parts)})
        i += 1
    if not segments:
        raise RuntimeError("caption file contained no timestamped text")
    return segments


def vtt_seconds(raw):
    parts = raw.replace(",", ".").split(":")
    seconds = float(parts[-1])
    if len(parts) > 1: seconds += int(parts[-2]) * 60
    if len(parts) > 2: seconds += int(parts[-3]) * 3600
    return seconds


def yt_dlp_binary():
    binary = os.environ.get("YT_DLP_BIN") or str(ROOT / ".venv" / "bin" / "yt-dlp")
    return binary if os.path.isfile(binary) and os.access(binary, os.X_OK) else "yt-dlp"


def download_media(url, item_id):
    media_root = ROOT / "data" / "media"
    media_root.mkdir(parents=True, exist_ok=True)
    key = hashlib.sha256((item_id + "\0" + url).encode("utf-8")).hexdigest()
    output = media_root / (key + ".%(ext)s")
    proc = subprocess.run([yt_dlp_binary(), "--no-warnings", "--no-playlist", "-f", "bestaudio/best",
                           "-o", str(output), url], cwd=str(ROOT), capture_output=True, text=True, timeout=7200)
    if proc.returncode != 0:
        raise RuntimeError("media download failed: %s" % proc.stderr.strip()[-500:])
    found = sorted(media_root.glob(key + ".*"))
    if not found:
        raise RuntimeError("yt-dlp completed without a media file")
    return found[0]


def captions(url, item_id):
    with tempfile.TemporaryDirectory(prefix="pipeline-captions-") as temp:
        output = os.path.join(temp, "caption.%(ext)s")
        proc = subprocess.run([yt_dlp_binary(), "--no-warnings", "--no-playlist", "--skip-download",
                               "--write-subs", "--write-auto-subs", "--sub-langs", "en.*,en",
                               "--sub-format", "vtt", "-o", output, url],
                              cwd=str(ROOT), capture_output=True, text=True, timeout=600)
        files = sorted(Path(temp).glob("*.vtt"))
        if proc.returncode == 0 and files:
            return parse_vtt(files[0])
    return None


def transcribe(media_path, model_name):
    try:
        probe = subprocess.run(
            ["ffprobe", "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(media_path)],
            capture_output=True, text=True, timeout=30)
        if probe.returncode == 0 and float(probe.stdout.strip()) > MAX_DURATION_SECONDS:
            return None, float(probe.stdout.strip())
    except (OSError, subprocess.TimeoutExpired, ValueError):
        pass
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError("faster-whisper is not installed; install requirements.txt")
    try:
        model = WhisperModel(model_name, device="cpu", compute_type="int8")
        segments_iter, info = model.transcribe(str(media_path), vad_filter=True)
        if info.duration and info.duration > MAX_DURATION_SECONDS:
            return None, info.duration
        segments = []
        for index, segment in enumerate(segments_iter, 1):
            value = segment.text.strip()
            if value:
                segments.append({"segment_id": "s%04d" % index, "start_seconds": float(segment.start),
                                 "end_seconds": float(segment.end), "text": value})
    except Exception as exc:
        raise RuntimeError("faster-whisper transcription failed: %s" % exc)
    if not segments:
        raise RuntimeError("transcription produced no timestamped text")
    return segments, info.duration


def store_item(item_id, version_id=None):
    cmd = ["bash", "data/store.sh", "get", item_id]
    if version_id:
        cmd.append(version_id)
    proc = subprocess.run(cmd, cwd=str(ROOT), capture_output=True, text=True)
    if proc.returncode != 0:
        return None
    try: return json.loads(proc.stdout)
    except json.JSONDecodeError: return None


def cached_item(candidate):
    old = store_item(candidate["item_id"])
    if not old:
        return None
    stable = ("source_id", "publisher_id", "kind", "title", "url", "published_at", "media_url")
    if all(old.get(k) == candidate.get(k) for k in stable):
        text_path = safe_path(old.get("text_path"))
        if text_path.is_file() and (old.get("kind") == "feed" or safe_path(old.get("segments_path")).is_file()):
            reused = dict(old)
            reused["retrieved_at"] = candidate["retrieved_at"]
            return reused
    return None


def extract(candidate, whisper_model):
    cached = cached_item(candidate)
    if cached:
        return cached, "unchanged_cache", None
    segments = None
    reason = None
    if candidate["kind"] == "feed":
        if isinstance(candidate.get("content"), str) and len(candidate["content"].strip()) >= 80:
            text = candidate["content"].strip()
        else:
            text = fetch_page(candidate["url"])
    else:
        media_url = candidate.get("media_url") or candidate["url"]
        metadata = media_metadata(media_url)
        duration = metadata.get("duration")
        if isinstance(duration, (int, float)) and duration > MAX_DURATION_SECONDS:
            return None, "skipped_too_long", "duration %.1f seconds exceeds 90 minutes" % duration
        if candidate["kind"] == "youtube":
            try:
                segments = captions(candidate["url"], candidate["item_id"])
            except (RuntimeError, OSError):
                segments = None
        if segments is None:
            media_path = download_media(media_url, candidate["item_id"])
            segments, duration = transcribe(media_path, whisper_model)
            if segments is None:
                return None, "skipped_too_long", "transcribed duration exceeds 90 minutes"
        text = "\n".join(s["text"] for s in segments).strip()
        if len(text) < 20:
            raise RuntimeError("transcript is too short to retain as evidence")

    version_data = {"title": candidate["title"], "url": candidate["url"],
                    "published_at": candidate["published_at"], "text": text, "segments": segments}
    canonical = json.dumps(version_data, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    version_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    safe_id = re.sub(r"[^A-Za-z0-9._-]+", "_", candidate["item_id"]).strip("._") or "item"
    asset_dir = ROOT / "data" / "assets" / safe_id
    asset_dir.mkdir(parents=True, exist_ok=True)
    text_rel = "data/assets/%s/%s.txt" % (safe_id, version_id)
    text_path = safe_path(text_rel)
    text_bytes = (text.rstrip() + "\n").encode("utf-8")
    if text_path.exists() and text_path.read_bytes() != text_bytes:
        raise RuntimeError("version hash collision at %s" % text_rel)
    if not text_path.exists(): text_path.write_bytes(text_bytes)
    segments_rel = None
    if segments is not None:
        segments_rel = "data/assets/%s/%s.segments.json" % (safe_id, version_id)
        segment_path = safe_path(segments_rel)
        segment_bytes = (json.dumps(segments, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
        if segment_path.exists() and segment_path.read_bytes() != segment_bytes:
            raise RuntimeError("version hash collision at %s" % segments_rel)
        if not segment_path.exists(): segment_path.write_bytes(segment_bytes)
    item = dict(candidate)
    item.update({"version_id": version_id, "text_path": text_rel, "segments_path": segments_rel})
    return item, None, None


def load_model(run_path):
    try:
        project = json.loads((run_path / "config" / "project.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise InputError("cannot read run config snapshot: %s" % exc)
    if not isinstance(project, dict):
        raise InputError("project config snapshot must be an object")
    return project.get("whisper_model", "tiny")


def write_receipt(run_path, started, inputs, output, failures, skips):
    logs = run_path / "logs"; logs.mkdir(parents=True, exist_ok=True)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    rec = {"stage": "processing/extract_content.sh", "status": "failed" if failures else "completed",
           "input_count": len(inputs), "output_count": len(output), "started_at": started,
           "finished_at": utc_now(), "tools": ["Python standard library", "yt-dlp", "faster-whisper"],
           "cost_usd": None, "item_errors": failures, "skipped_too_long": skips}
    with (logs / ("extract-content-%s-%d.json" % (stamp, os.getpid()))).open("x", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, sort_keys=True); fh.write("\n")


def main(argv):
    if len(argv) != 1: raise InputError("usage: extract_content.sh RUN_DIR")
    run_path = safe_path(argv[0]); started = utc_now(); candidates = parse_input(); model_name = load_model(run_path)
    output, failures, skips = [], [], []
    for candidate in candidates:
        try:
            item, reason, detail = extract(candidate, model_name)
            if reason == "skipped_too_long":
                skips.append({"item_id": candidate["item_id"], "reason": reason, "detail": detail})
            else:
                output.append(item)
        except (RuntimeError, OSError, ValueError) as exc:
            failures.append({"item_id": candidate.get("item_id"), "reason": "extraction_failed", "detail": str(exc)})
    write_receipt(run_path, started, candidates, output, failures, skips)
    for item in output: print(json.dumps(item, ensure_ascii=False, separators=(",", ":")))
    return 1 if failures else 0


if __name__ == "__main__":
    try: sys.exit(main(sys.argv[1:]))
    except InputError as exc:
        print("processing/extract_content.sh: %s" % exc, file=sys.stderr); sys.exit(2)
    except OSError as exc:
        print("processing/extract_content.sh: extraction stage failed: %s" % exc, file=sys.stderr); sys.exit(1)
