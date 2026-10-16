import json, subprocess, sys
SP, OUT = sys.argv[1], sys.argv[2]; d=json.load(open(f"{SP}/scenes.json")); GAP=0.8
dur=lambda f: float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",f]))
subprocess.run(["ffmpeg","-y","-v","error","-f","lavfi","-i","anullsrc=r=24000:cl=mono","-t",str(GAP),f"{SP}/audio_cb/gap.wav"],check=True)
for n,sc in d.items():
    lst=open(f"{SP}/audio_cb/{n}.txt","w"); t=0
    for i,s in enumerate(sc,1):
        f=f"{SP}/audio_cb/{n}_{i}.wav"; s["dur"]=dur(f); wps=s["words"]/s["dur"]
        flag="  <-- CHECK" if not 1.9<=wps<=3.3 else ""
        print(f"{n} scene {i}: {s['dur']:.1f}s, {wps:.2f} words/s{flag}")
        s["start"]=t; s["slide_dur"]=s["dur"]+GAP; t+=s["slide_dur"]
        lst.write(f"file '{f}'\nfile '{SP}/audio_cb/gap.wav'\n")
    lst.close()
    subprocess.run(["ffmpeg","-y","-v","error","-f","concat","-safe","0","-i",f"{SP}/audio_cb/{n}.txt","-af","loudnorm=I=-16:TP=-1.5","-ar","44100","-ac","1","-c:a","aac","-b:a","160k",f"{OUT}/audio/piece{n}_voiceover.m4a"],check=True)
    print(n,"total %.1fs"%t)
json.dump(d,open(f"{SP}/scenes.json","w"),indent=1,ensure_ascii=False)
