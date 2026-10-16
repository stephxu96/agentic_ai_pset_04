import zipfile, json, sys, re, shutil, os
SP=sys.argv[1]; d=json.load(open(f"{SP}/scenes.json"))
for f in sys.argv[2:]:
    n=re.search(r"piece(\d\d)_",f).group(1); sc=d[n]
    tmp=f+".tmp"
    with zipfile.ZipFile(f) as zi, zipfile.ZipFile(tmp,"w",zipfile.ZIP_DEFLATED) as zo:
        for it in zi.infolist():
            data=zi.read(it.filename)
            m=re.fullmatch(r"ppt/slides/slide(\d+)\.xml",it.filename)
            if m:
                i=int(m.group(1))-1; ms=int(round(sc[i]["slide_dur"]*1000))
                x=data.decode()
                x=re.sub(r"<p:transition\b.*?(/>|</p:transition>)","",x,flags=re.S)
                tr=f'<p:transition spd="med" advClick="1" advTm="{ms}"><p:fade/></p:transition>'
                assert "</p:clrMapOvr>" in x
                x=x.replace("</p:clrMapOvr>","</p:clrMapOvr>"+tr,1)
                data=x.encode()
            zo.writestr(it,data)
    os.replace(tmp,f); print("timed",f)
