import json, sys
B, OUT = sys.argv[1:]; d=json.load(open(f"{B}/scenes.json"))
W={"01":["00:00–00:33","00:33–01:10","01:10–01:40","01:40–02:07","02:07–02:47","02:47–03:40","03:40–04:13"],"02":["00:00–00:21","00:21–00:47","00:47–01:12","01:12–01:37","01:37–02:05","02:05–02:40","02:40–03:05","03:05–03:29"],"03":["00:00–00:24","00:24–00:56","00:56–01:33","01:33–02:10","02:10–02:50","02:50–03:21","03:21–03:54"]}
T={"01":"AI Enters the CAD-to-Simulation Handoff","02":"A CAD File Is Not Yet an Engineering Workflow","03":"Pilot Where Mistakes Are Easy to Undo"}
f=lambda t:"%02d:%04.1f"%(int(t//60),t%60)
L=["# Slide timing cues","","**AI-ASSISTED.**","",
"Times are measured from the voiceover files in `audio/`. The narration is an AI-generated voice: a Chatterbox (open-source) clone of the author's voice, built from a 17-second sample, with a 0.8-second pause after each scene. Each deck auto-advances on these times, and clicking also advances. Slide 1 in each deck is the new title slide with a spoken executive summary; the original timing table did not include it, so the suggested windows apply from slide 2.",""]
for n,sc in d.items():
    tot=sum(s["slide_dur"] for s in sc)
    L+=[f"## Piece {int(n)}: {T[n]}","",f"Audio: `audio/piece{n}_voiceover.m4a` ({f(tot)} total)","","| Slide | Scene | Voiceover cue | Original suggested window | Words |","| ---: | --- | --- | --- | ---: |"]
    L+=[f"| {i+1} | {s['title']} | {f(s['start'])}–{f(s['start']+s['slide_dur'])} | {'new' if i==0 else W[n][i-1]} | {s['words']} |" for i,s in enumerate(sc)]+[""]
open(f"{OUT}/timing_cues.md","w").write("\n".join(L))
