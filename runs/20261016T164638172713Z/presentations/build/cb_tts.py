# Usage: cb_tts.py SP [voice.wav|-] [pieces...|test]
import sys, json, re, time, torch, torchaudio
from chatterbox.tts import ChatterboxTTS
SP, VOICE = sys.argv[1], sys.argv[2]; which = sys.argv[3:] or ["01","02","03"]
import os; dev = os.environ.get("CB_DEV") or ("mps" if torch.backends.mps.is_available() else "cpu")
model = ChatterboxTTS.from_pretrained(device=dev)
prompt = None if VOICE == "-" else VOICE
PRON=[(r"MIT-CDFG","M.I.T. C.D.F.G."),(r"\bLLM\b","L.L.M."),(r"\bMCP\b","M.C.P."),(r"\bPLM\b","P.L.M."),(r"\bAMD\b","A.M.D."),(r"Engineering\.com","Engineering dot com"),(r"\bSTEP\b","step")]
def say(text):
    for a,b in PRON: text=re.sub(a,b,text)
    return model.generate(text, audio_prompt_path=prompt, exaggeration=0.45, cfg_weight=0.5)
def chunks(par, maxw=40):
    sents=re.split(r"(?<=[.?!])\s+", par.strip()); out=[]; cur=""
    for s in sents:
        if cur and len((cur+" "+s).split())>maxw: out.append(cur); cur=s
        else: cur=(cur+" "+s).strip()
    if cur: out.append(cur)
    return out
sr=model.sr; gap=lambda s: torch.zeros(1,int(sr*s))
if which==["test"]:
    t=time.time(); w=say("Onshape says its FeatureScript MCP Server connects large language models to Onshape. A completed run is not evidence of a valid analysis.")
    torchaudio.save(f"{SP}/cb_test.wav", w.cpu(), sr); print("test secs", w.shape[1]/sr, "took", time.time()-t); sys.exit()
d=json.load(open(f"{SP}/scenes.json"))
for n in which:
    for i,sc in enumerate(d[n],1):
        parts=[]
        for pi,par in enumerate(sc["narration"].split("\n\n")):
            if pi: parts.append(gap(0.45))
            for ci,c in enumerate(chunks(par)):
                if ci: parts.append(gap(0.25))
                parts.append(say(c).cpu())
        w=torch.cat(parts,dim=1); torchaudio.save(f"{SP}/audio_cb/{n}_{i}.wav", w, sr)
        print(n,i,round(w.shape[1]/sr,1),flush=True)
