#!/usr/bin/env python3
"""Write publish-ready article copies where claim markers become inline source links.

Usage: tools/make_publish_copies.py RUN_DIR
Reads RUN_DIR/articles/NN.md, maps each claim marker to the URL in that article's References
block, and writes RUN_DIR/publish/articles/NN.md. The reviewed drafts are not changed.
"""
import re
import sys
from pathlib import Path

MARK = r"[\[`]*\b(\d\d-c\d+)\b[\]`]*"


def convert(text):
    body, _, refs = text.partition("\n## References")
    urls = {}
    for line in refs.splitlines():
        m = re.search(r"(https?://\S+)", line)
        if not m:
            continue
        for tag in re.findall(r"\b\d\d-c\d+\b", line.split("http")[0]):
            urls.setdefault(tag, m.group(1).rstrip(").,"))
    labels = {}

    def link(m):
        tag = m.group(1)
        if tag not in urls:
            return ""  # inference markers have no single source URL
        n = labels.setdefault(urls[tag], len(labels) + 1)
        return "[[%d]](%s)" % (n, urls[tag])

    # Replace markers outside the References section only.
    body = re.sub(r"[\[`]+" + r"(\d\d-c\d+)" + r"[\]`]+", link, body)
    body = re.sub(r" +(?=[.,;])", "", re.sub(r"  +", " ", body))
    out_refs = []
    for line in refs.splitlines():
        m = re.search(r"(https?://\S+)", line)
        if not m:
            continue
        url = m.group(1).rstrip(").,")
        entry = line[line.find("\u201c"):] if "\u201c" in line else line
        out_refs.append((labels.get(url, 99), "[%s] %s" % (labels.get(url, "-"), entry.strip())))
    refs = "\n".join("- " + r for _, r in sorted(out_refs, key=lambda x: x[0]))
    return body.rstrip() + "\n\n## References\n\n" + refs + "\n"


def main(argv):
    if len(argv) != 1:
        sys.exit("usage: make_publish_copies.py RUN_DIR")
    run = Path(argv[0])
    out = run / "publish" / "articles"
    out.mkdir(parents=True, exist_ok=True)
    for pid in ("01", "02", "03"):
        text = (run / "articles" / ("%s.md" % pid)).read_text(encoding="utf-8")
        (out / ("%s.md" % pid)).write_text(convert(text), encoding="utf-8")
        print(out / ("%s.md" % pid))


if __name__ == "__main__":
    main(sys.argv[1:])
