#!/usr/bin/env python3
"""Stage 1 — ingest + analyze source footage (never modifies originals).

  .venv/bin/python scripts/prep.py <project> [clip ...]      # default: every video in "raw footage/"

For each clip: ffprobe -> CFR 30fps H.264 intermediate (short GOP, frame-accurate for Remotion),
dialogue cleanup (high-pass, light FFT denoise, loudness normalize to -16 LUFS),
face-based focal point for 9:16 reframing. Writes analysis/probe.json + analysis/framing.json.
"""
from __future__ import annotations

import argparse
import re
import statistics
import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import RAW, VIDEO_EXT, die, project_dir, read_json, run, summarize_probe, write_json  # noqa: E402


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", Path(name).stem.lower()).strip("-") or "clip"


def transcode(src: Path, dst: Path, fps: int, has_audio: bool, clean: bool) -> None:
    af = "highpass=f=80,afftdn=nf=-30:tn=1,loudnorm=I=-16:TP=-1.5:LRA=11" if clean else "loudnorm=I=-16:TP=-1.5:LRA=11"
    cmd = ["ffmpeg", "-y", "-v", "error", "-stats", "-i", str(src)]
    if not has_audio:  # Remotion expects an audio track for consistent mixing
        cmd += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo", "-shortest"]
    cmd += ["-map", "0:v:0", "-map", "0:a:0" if has_audio else "1:a:0",
            "-vf", f"fps={fps},scale='min(iw,2160)':-2,format=yuv420p",
            "-c:v", "libx264", "-preset", "veryfast", "-crf", "17", "-g", str(fps // 2), "-bf", "0",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"]
    if has_audio:
        cmd += ["-af", af]
    cmd += ["-movflags", "+faststart", str(dst)]
    run(cmd)


def face_focus(path: Path, duration: float) -> dict:
    """Median face centre over ~24 sampled frames (Haar cascade; fast, offline)."""
    import cv2

    cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
    cap = cv2.VideoCapture(str(path))
    xs, ys, hits, n = [], [], 0, 24
    for i in range(n):
        cap.set(cv2.CAP_PROP_POS_MSEC, (duration * (i + 0.5) / n) * 1000)
        ok, frame = cap.read()
        if not ok:
            continue
        H, W = frame.shape[:2]
        gray = cv2.cvtColor(cv2.resize(frame, (W // 2, H // 2)), cv2.COLOR_BGR2GRAY)
        faces = cascade.detectMultiScale(gray, 1.1, 6, minSize=(40, 40))
        if len(faces):
            x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
            xs.append((x + w / 2) * 2 / W)
            ys.append((y + h / 2) * 2 / H)
            hits += 1
    cap.release()
    if not hits:
        return {"focusX": 0.5, "focusY": 0.4, "faces": 0, "note": "no face found; centred"}
    # place the face slightly above centre in the vertical frame (eyes on upper third)
    return {"focusX": round(statistics.median(xs), 3), "focusY": round(min(0.6, statistics.median(ys) + 0.08), 3),
            "faces": hits, "samples": n}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("clips", nargs="*", help="files in raw footage/ (default: all)")
    ap.add_argument("--fps", type=int, default=30)
    ap.add_argument("--no-clean", action="store_true", help="skip denoise (keep loudness normalization)")
    args = ap.parse_args()

    proj = project_dir(args.project, create=True)
    clips = [RAW / c for c in args.clips] if args.clips else sorted(p for p in RAW.iterdir() if p.suffix.lower() in VIDEO_EXT)
    if not clips:
        die(f'no footage found in "{RAW}". Drop clips there (originals are never modified).')

    probe_path, framing_path = proj / "analysis/probe.json", proj / "analysis/framing.json"
    probe = read_json(probe_path) if probe_path.exists() else {}
    framing = read_json(framing_path) if framing_path.exists() else {}
    for src in clips:
        if not src.exists():
            die(f"missing: {src}")
        info = summarize_probe(src)
        key = slug(src.name)
        dst = proj / "public/media" / f"{key}.mp4"
        print(f"→ {src.name}: {info.get('width')}x{info.get('height')} @ {info.get('fps')}fps"
              f"{' VFR' if info.get('vfr') else ''}, {info['duration']:.1f}s, audio={'yes' if info['has_audio'] else 'NO'}")
        if not dst.exists() or dst.stat().st_mtime < src.stat().st_mtime:
            transcode(src, dst, args.fps, info["has_audio"], not args.no_clean)
        out = summarize_probe(dst)
        info.update(key=key, source=str(src.relative_to(RAW.parent)), media=f"media/{dst.name}",
                    width=out["width"], height=out["height"], duration=out["duration"], src_width=info.get("width"))
        probe[key] = info
        framing[key] = face_focus(dst, out["duration"])
        print(f"  ✓ {info['media']}  focus={framing[key]['focusX']},{framing[key]['focusY']} (faces in {framing[key]['faces']} samples)")
    write_json(probe_path, probe)
    write_json(framing_path, framing)
    print(f"✓ probe → {probe_path}\n✓ framing → {framing_path}")


if __name__ == "__main__":
    main()
