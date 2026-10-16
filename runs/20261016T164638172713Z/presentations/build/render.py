import fitz, sys, os, glob
src, out = sys.argv[1], sys.argv[2]; os.makedirs(out, exist_ok=True)
for p in sorted(glob.glob(src+"/*.pdf")):
    n=os.path.basename(p)[5:7]; doc=fitz.open(p); print(p, doc.page_count)
    for i,pg in enumerate(doc): pg.get_pixmap(dpi=110).save(f"{out}/p{n}_s{i+1}.png")
