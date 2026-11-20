#!/usr/bin/env python3
"""Stage 4 — render a project with Remotion, master audio, write subtitles, run QA.

  .venv/bin/python scripts/render.py <project>                 # full render -> exports/<project>/<project>-vN.mp4
  .venv/bin/python scripts/render.py <project> --frames 0-89   # partial render for quick checks (not versioned)
  .venv/bin/python scripts/render.py <project> --still 45,120  # PNG stills of given frames (fast visual check)
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import ENGINE, EXPORTS, die, load_style, project_dir, read_json, run, write_json  # noqa: E402


def output_words(tl: dict, fps: int) -> list[dict]:
    """Mirror of engine/src/Edit.tsx outputWords (seconds)."""
    out, frm = [], 0
    for seg in tl["segments"]:
        dur = max(1, round((seg["srcOut"] - seg["srcIn"]) * fps))
        t0, t1 = frm / fps, (frm + dur) / fps
        for w in seg.get("words", []):
            if w["end"] <= seg["srcIn"] or w["start"] >= seg["srcOut"]:
                continue
            out.append({"text": w["text"], "start": max(t0, t0 + w["start"] - seg["srcIn"]), "end": min(t1, t0 + w["end"] - seg["srcIn"])})
        frm += dur
    for w in tl.get("extraWords", []) or []:
        out.append({"text": w["text"], "start": w["startMs"] / 1000, "end": w["endMs"] / 1000})
    return sorted(out, key=lambda w: w["start"])


def total_frames(tl: dict, fps: int) -> int:
    return sum(max(1, round((s["srcOut"] - s["srcIn"]) * fps)) for s in tl["segments"])


def ts(t: float, sep=",") -> str:
    h, rem = divmod(max(0.0, t), 3600)
    m, s = divmod(rem, 60)
    return f"{int(h):02d}:{int(m):02d}:{int(s):02d}{sep}{int(round((s - int(s)) * 1000)):03d}"


def write_subs(words: list[dict], base: Path, max_words=7, max_gap=0.6) -> None:
    cues, cur = [], []
    for w in words:
        if cur and (len(cur) >= max_words or w["start"] - cur[-1]["end"] > max_gap or re.search(r"[.!?]$", cur[-1]["text"])):
            cues.append(cur)
            cur = []
        cur.append(w)
    if cur:
        cues.append(cur)
    srt, vtt = [], ["WEBVTT", ""]
    for i, c in enumerate(cues, 1):
        text = " ".join(w["text"].strip() for w in c)
        srt += [str(i), f"{ts(c[0]['start'])} --> {ts(c[-1]['end'])}", text, ""]
        vtt += [f"{ts(c[0]['start'], '.')} --> {ts(c[-1]['end'], '.')}", text, ""]
    base.with_suffix(".srt").write_text("\n".join(srt))
    base.with_suffix(".vtt").write_text("\n".join(vtt))


def master_audio(src: Path, dst: Path, lufs: float = -14.0, tp: float = -1.0) -> dict:
    """Two-pass EBU R128 loudnorm (linear) — video stream copied untouched."""
    meas = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(src), "-af", f"loudnorm=I={lufs}:TP={tp}:LRA=11:print_format=json", "-f", "null", "-"],
                          capture_output=True, text=True).stderr
    m = json.loads(meas[meas.rfind("{"): meas.rfind("}") + 1])
    af = (f"loudnorm=I={lufs}:TP={tp}:LRA=11:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}:"
          f"measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    run(["ffmpeg", "-y", "-v", "error", "-i", str(src), "-c:v", "copy", "-af", af, "-ar", "48000", "-c:a", "aac", "-b:a", "320k", "-movflags", "+faststart", str(dst)])
    return m


def remotion(args: list[str]) -> None:
    run(["npx", "remotion", *args], cwd=ENGINE)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--frames", help="frame range e.g. 0-89 (partial, unversioned)")
    ap.add_argument("--still", help="comma-separated frames to export as PNG")
    ap.add_argument("--crf", type=int, default=16)
    ap.add_argument("--lufs", type=float, default=-14.0)
    ap.add_argument("--no-qa", action="store_true")
    a = ap.parse_args()

    proj = project_dir(a.project)
    tl = read_json(proj / "timeline.json")
    style = load_style(proj)
    fps = style["canvas"]["fps"]
    props = proj / "renders/props.json"
    write_json(props, {"timeline": tl, "style": style})
    common = ["--props", str(props), "--public-dir", str(proj / "public"), "--log", "error"]

    if a.still:
        for f in a.still.split(","):
            out = proj / "renders" / f"still-{int(f):05d}.png"
            remotion(["still", "src/index.ts", "Edit", str(out), "--frame", f, *common])
            print(f"✓ {out}")
        return

    if a.frames:
        out = proj / "renders" / f"partial-{a.frames}.mp4"
        remotion(["render", "src/index.ts", "Edit", str(out), "--frames", a.frames, "--crf", str(a.crf), *common])
        print(f"✓ {out}")
        return

    exp = EXPORTS / a.project
    exp.mkdir(parents=True, exist_ok=True)
    n = 1 + max([int(m.group(1)) for p in exp.glob(f"{a.project}-v*.mp4") if (m := re.search(r"-v(\d+)\.mp4$", p.name))] or [0])
    base = exp / f"{a.project}-v{n}"
    raw = proj / "renders" / f"raw-v{n}.mp4"
    print(f"→ rendering {total_frames(tl, fps)} frames ({total_frames(tl, fps) / fps:.1f}s) → {base}.mp4")
    remotion(["render", "src/index.ts", "Edit", str(raw), "--codec", "h264", "--crf", str(a.crf),
              "--audio-codec", "aac", "--audio-bitrate", "320k", "--pixel-format", "yuv420p", *common])
    m = master_audio(raw, base.with_suffix(".mp4"), a.lufs)
    print(f"✓ mastered audio: {m['input_i']} LUFS → {a.lufs} LUFS")
    raw.unlink(missing_ok=True)
    write_subs(output_words(tl, fps), base)
    shutil.copy2(proj / "timeline.json", base.with_suffix(".timeline.json"))
    print(f"✓ {base}.mp4\n✓ {base}.srt / .vtt\n✓ {base}.timeline.json (editable source snapshot)")
    if not a.no_qa:
        sys.exit(subprocess.call([sys.executable, str(Path(__file__).parent / "qa.py"), str(base.with_suffix(".mp4")), "--project", a.project]))


if __name__ == "__main__":
    main()
