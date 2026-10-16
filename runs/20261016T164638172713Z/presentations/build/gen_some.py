# Usage: gen_some.py B voice.wav n:i [n:i ...]  (i = 1-based slide index in scenes_v2.json)
import sys, json, re, torch, torchaudio
from chatterbox.tts import ChatterboxTTS
B, VOICE, jobs = sys.argv[1], sys.argv[2], sys.argv[3:]
model = ChatterboxTTS.from_pretrained(device="cpu"); sr = model.sr
PRON=[(r"MIT-CDFG","M.I.T. C.D.F.G."),(r"\bLLM\b","L.L.M."),(r"\bMCP\b","M.C.P."),(r"\bPLM\b","P.L.M."),(r"\bAMD\b","A.M.D."),(r"Engineering\.com","Engineering dot com"),(r"\bSTEP\b","step")]
def say(t):
    for a,b in PRON: t=re.sub(a,b,t)
    return model.generate(t, audio_prompt_path=VOICE, exaggeration=0.45, cfg_weight=0.5).cpu()
def chunks(p, maxw=40):
    out=[]; cur=""
    for s in re.split(r"(?<=[.?!;])\s+", p.strip()):
        if cur and len((cur+" "+s).split())>maxw: out.append(cur); cur=s
        else: cur=(cur+" "+s).strip()
    return out+([cur] if cur else [])
d=json.load(open(f"{B}/scenes_v2.json"))
for j in jobs:
    n,i=j.split(":"); sc=d[n][int(i)-1]; parts=[]
    for pi,par in enumerate(sc["narration"].split("\n\n")):
        if pi: parts.append(torch.zeros(1,int(sr*0.45)))
        for ci,c in enumerate(chunks(par)):
            if ci: parts.append(torch.zeros(1,int(sr*0.25)))
            parts.append(say(c))
    w=torch.cat(parts,1); torchaudio.save(f"{B}/audio_cb/{n}_{i}.wav", w, sr); print(j, round(w.shape[1]/sr,1), flush=True)
