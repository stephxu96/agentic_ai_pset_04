import sys, re, glob, os, html, markdown
src, out = sys.argv[1], sys.argv[2]
SUB = {"01": "Two software makers say their AI tools can do this. Neither has shown that the results are correct.",
       "02": "The file had the right weight in two tests. But it could not be fully edited, it built only one of seven parts, and the tests never checked whether a factory could make it.",
       "03": "Let AI help people find files first. Keep a person in charge before it changes the company's official parts records."}
def btn(i, label): return f'<button data-t="{i}" class="cp">{label}</button>'
for p in sorted(glob.glob(f"{src}/*.md")):
    md = open(p, encoding="utf-8").read()
    title = re.match(r"#\s+(.+)", md).group(1).strip()
    body = re.sub(r"\A#\s+.+\n+", "", md, count=1)          # title goes in Substack's own field
    body = re.sub(r"(?m)^(Watch the video version: )(https?://\S+)$", r"\1[\2](\2)", body)
    h = markdown.markdown(body, extensions=["extra", "sane_lists"])
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(title)}</title>
<style>body{{max-width:700px;margin:40px auto;padding:0 16px;font:18px/1.6 Georgia,serif;color:#1a1a1a;background:#fff}}
.howto{{font:14px/1.5 system-ui,sans-serif;background:#f3f4f6;border:1px solid #d1d5db;padding:12px 16px;margin-bottom:32px}}
a{{color:#1f5a99}} .howto p{{margin:6px 0 10px}} button.cp{{font:600 13px system-ui;padding:3px 10px;margin-left:6px;cursor:pointer}} h2{{font-family:system-ui,sans-serif}}</style></head><body>
<div class="howto"><p><b>Title</b> {btn("t","Copy")}<br><span id="t">{html.escape(title)}</span></p><p><b>Subtitle</b> {btn("s","Copy")}<br><span id="s">{html.escape(SUB[os.path.basename(p)[:2]])}</span></p><p><b>Body</b> {btn("article","Copy article")} <span id="msg"></span><br>Paste each into its own field in Substack with ⌘V.</p></div>
<hr>
<div id="article">{h}</div>
<script>document.querySelectorAll("button.cp").forEach(function(b){{b.onclick=function(){{var r=document.createRange();r.selectNodeContents(document.getElementById(b.dataset.t));var sel=getSelection();sel.removeAllRanges();sel.addRange(r);var ok=document.execCommand("copy");sel.removeAllRanges();document.getElementById("msg").textContent=ok?("Copied "+(b.dataset.t=="article"?"body":b.dataset.t=="t"?"title":"subtitle")+"."):"Copy failed: select the text and press \u2318C.";}};}});</script></body></html>"""
    n = os.path.basename(p)[:2]; f = f"{out}/{n}.html"
    open(f, "w", encoding="utf-8").write(page); print(f, "|", title, "| links:", h.count("<a "))
