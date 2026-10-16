import json, subprocess, sys, glob, os, pymupdf
P = sys.argv[1]; B = f"{P}/build"; d = json.load(open(f"{B}/scenes.json"))
for n, sc in d.items():
    pdf = glob.glob(f"{P}/preview/piece{n}_*.pdf")[0]; doc = pymupdf.open(pdf)
    assert doc.page_count == len(sc)
    audio = f"{P}/audio/piece{n}_voiceover.m4a"
    total = float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",audio]))
    lst = open(f"{B}/frames/{n}.txt", "w")
    for i, pg in enumerate(doc):
        img = f"{B}/frames/p{n}_{i+1}.png"
        pg.get_pixmap(matrix=pymupdf.Matrix(1920/pg.rect.width, 1080/pg.rect.height)).save(img)
        start = sc[i]["start"]; end = sc[i+1]["start"] if i+1 < len(sc) else total
        lst.write(f"file '{img}'\nduration {end-start:.3f}\n")
    lst.write(f"file '{img}'\n"); lst.close()
    out = f"{P}/video/piece{n}.mp4"
    subprocess.run(["ffmpeg","-y","-v","error","-f","concat","-safe","0","-i",f"{B}/frames/{n}.txt","-i",audio,
        "-vf","scale=1920:1080,format=yuv420p","-r","30","-c:v","libx264","-preset","medium","-crf","18","-tune","stillimage",
        "-c:a","aac","-b:a","160k","-t",f"{total:.3f}","-movflags","+faststart",
        "-metadata","comment=AI-ASSISTED: AI-generated slides and AI-cloned narration.",out], check=True)
    v = float(subprocess.check_output(["ffprobe","-v","error","-show_entries","format=duration","-of","csv=p=0",out]))
    print(f"piece{n}.mp4  {v:.1f}s  (audio {total:.1f}s)")
