import sys, glob, os
from PIL import Image, ImageDraw, ImageFont
png, out = sys.argv[1], sys.argv[2]
titles={"01":"Piece 1 — AI Enters the CAD-to-Simulation Handoff","02":"Piece 2 — A CAD File Is Not Yet an Engineering Workflow","03":"Piece 3 — Pilot Where Mistakes Are Easy to Undo"}
f=ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf",26); fb=ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial Bold.ttf",34)
for n,t in titles.items():
    ims=[Image.open(p) for p in sorted(glob.glob(f"{png}/p{n}_s*.png"),key=lambda p:int(p.split("_s")[1][:-4]))]
    tw=720; th=int(tw*ims[0].height/ims[0].width); cols=2; rows=(len(ims)+1)//2; pad=30
    sheet=Image.new("RGB",(cols*tw+(cols+1)*pad, rows*(th+50)+pad+110),"white"); d=ImageDraw.Draw(sheet)
    d.text((pad,25),t,fill=(20,30,40),font=fb); d.text((pad,68),"AI-ASSISTED · slide contact sheet",fill=(90,100,110),font=f)
    for i,im in enumerate(ims):
        x=pad+(i%cols)*(tw+pad); y=110+(i//cols)*(th+50)
        sheet.paste(im.resize((tw,th)),(x,y+34)); d.text((x,y+2),f"Slide {i+1}",fill=(60,70,80),font=f)
        d.rectangle([x-1,y+33,x+tw,y+34+th],outline=(200,205,210))
    sheet.save(f"{out}/piece{n}_contact_sheet.png"); print(f"{out}/piece{n}_contact_sheet.png")
