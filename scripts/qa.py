#!/usr/bin/env python3
"""Stage 5 — automated QA of a rendered video. Exit code 1 if any ERROR.

  .venv/bin/python scripts/qa.py exports/<p>/<p>-v1.mp4 [--project <p>]

Checks: container/codec/resolution/fps/pix_fmt, duration vs timeline, black frames, frozen video,
loudness + true peak + clipping, long silences, caption page width vs safe zone (estimate).
Writes <video>.qa.json and <video>.contact.jpg (frames at every cut + caption/hook samples, labelled)
— the agent must LOOK at the contact sheet before presenting the draft.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import load_style, project_dir, read_json, summarize_probe, write_json  # noqa: E402


def ff_filter(path: Path, vf: str | None = None, af: str | None = None) -> str:
    cmd = ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path)]
    cmd += ["-vf", vf, "-an"] if vf else ["-af", af, "-vn"]
    cmd += ["-f", "null", "-"]
    return subprocess.run(cmd, capture_output=True, text=True).stderr


def contact_sheet(video: Path, times: list[tuple[float, str]], out: Path, cols=6, w=270) -> None:
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(str(video))
    tiles = []
    for t, label in times:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, fr = cap.read()
        if not ok:
            continue
        h = int(fr.shape[0] * w / fr.shape[1])
        fr = cv2.resize(fr, (w, h))
        cv2.rectangle(fr, (0, h - 26), (w, h), (0, 0, 0), -1)
        cv2.putText(fr, f"{t:5.2f}s {label}"[:34], (4, h - 8), cv2.FONT_HERSHEY_SIMPLEX, 0.42, (255, 255, 255), 1, cv2.LINE_AA)
        tiles.append(fr)
    cap.release()
    if not tiles:
        return
    h = tiles[0].shape[0]
    while len(tiles) % cols:
        tiles.append(np.zeros((h, w, 3), np.uint8))
    rows = [np.hstack(tiles[i:i + cols]) for i in range(0, len(tiles), cols)]
    cv2.imwrite(str(out), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 85])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("video")
    ap.add_argument("--project")
    ap.add_argument("--width", type=int, default=1080)
    ap.add_argument("--height", type=int, default=1920)
    ap.add_argument("--fps", type=float, default=30)
    a = ap.parse_args()
    v = Path(a.video)
    errors, warns, info = [], [], {}

    p = summarize_probe(v)
    info["probe"] = p
    if p.get("vcodec") != "h264":
        errors.append(f"video codec {p.get('vcodec')} != h264")
    if (p.get("width"), p.get("height")) != (a.width, a.height):
        errors.append(f"resolution {p.get('width')}x{p.get('height')} != {a.width}x{a.height}")
    if abs(p.get("fps", 0) - a.fps) > 0.01:
        errors.append(f"fps {p.get('fps')} != {a.fps}")
    if p.get("pix_fmt") != "yuv420p":
        errors.append(f"pix_fmt {p.get('pix_fmt')} (needs yuv420p for social platforms)")
    if not p.get("has_audio"):
        errors.append("no audio stream")

    tl, cut_times, words = None, [], []
    if a.project:
        proj = project_dir(a.project)
        tl_path = v.with_suffix(".timeline.json")
        tl = read_json(tl_path if tl_path.exists() else proj / "timeline.json")
        style = load_style(proj)
        fps = style["canvas"]["fps"]
        frm = 0
        for s in tl["segments"]:
            cut_times.append((frm / fps, s["id"]))
            frm += max(1, round((s["srcOut"] - s["srcIn"]) * fps))
        expected = frm / fps
        info["expected_duration"] = expected
        if abs(p["duration"] - expected) > 0.1:
            errors.append(f"duration {p['duration']:.2f}s vs timeline {expected:.2f}s")
        # caption width estimate (heavy uppercase font ≈ 0.68em per char)
        from render import output_words

        words = output_words(tl, fps)
        c = style["captions"]
        safe_w = style["canvas"]["width"] - style["safeZone"]["left"] - style["safeZone"]["right"]
        per_line = int(safe_w / (c["fontSize"] * 0.68 * c.get("activeScale", 1)))
        long_words = sorted({w["text"] for w in words if len(w["text"].strip()) > per_line})
        if long_words:
            warns.append(f"words wider than caption safe area at fontSize {c['fontSize']}: {long_words[:5]}")
        sz = style["safeZone"]
        y = style["canvas"]["height"] * c["yPercent"] / 100
        if not (sz["top"] < y < style["canvas"]["height"] - sz["bottom"]):
            errors.append(f"caption centre y={y:.0f}px is outside platform safe zone")

    # black frames
    bl = re.findall(r"black_start:([\d.]+) black_end:([\d.]+)", ff_filter(v, vf="blackdetect=d=0.08:pix_th=0.08"))
    info["black"] = bl
    if bl:
        errors.append(f"black frames at {[(float(s), float(e)) for s, e in bl][:5]}")
    # frozen video (a decode failure shows up as a long freeze)
    fz = re.findall(r"freeze_start: ([\d.]+)[\s\S]*?freeze_duration: ([\d.]+)", ff_filter(v, vf="freezedetect=n=0.001:d=2.5"))
    if fz:
        warns.append(f"frozen video segments (start, dur): {fz[:5]}")
    # loudness / peaks
    eb = ff_filter(v, af="ebur128=peak=true")
    I = re.findall(r"I:\s+(-?[\d.]+) LUFS", eb)
    TP = re.findall(r"Peak:\s+(-?[\d.]+) dBFS", eb)
    info["lufs"] = float(I[-1]) if I else None
    info["true_peak"] = float(TP[-1]) if TP else None
    if info["lufs"] is not None and not (-16.5 <= info["lufs"] <= -12.5):
        warns.append(f"integrated loudness {info['lufs']} LUFS (target -14)")
    if info["true_peak"] is not None and info["true_peak"] > -0.5:
        errors.append(f"true peak {info['true_peak']} dBFS — risk of clipping")
    st = ff_filter(v, af="astats=metadata=0:measure_overall=Peak_level+Number_of_Peaks:measure_perchannel=0")
    pk = re.findall(r"Peak level dB:\s+(-?[\d.inf]+)", st)
    info["sample_peak_db"] = pk[-1] if pk else None
    sil = re.findall(r"silence_start: ([\d.]+)[\s\S]*?silence_duration: ([\d.]+)", ff_filter(v, af="silencedetect=n=-45dB:d=1.0"))
    if sil:
        warns.append(f"silences ≥1s (start, dur): {sil[:5]}")

    # contact sheet: each cut (+3 frames), plus mid-points of a few caption words
    times = [(min(t + 0.1, p["duration"] - 0.05), sid) for t, sid in cut_times] or [(p["duration"] * i / 12, "") for i in range(12)]
    times += [((w["start"] + w["end"]) / 2, f"cap:{w['text'][:10]}") for w in words[:: max(1, len(words) // 6)]][:6]
    times.append((p["duration"] - 0.1, "last"))
    sheet = v.with_suffix(".contact.jpg")
    contact_sheet(v, sorted(times), sheet)

    report = {"video": str(v), "errors": errors, "warnings": warns, **info, "contact_sheet": str(sheet)}
    write_json(v.with_suffix(".qa.json"), report)
    print(f"QA {v.name}: {p.get('width')}x{p.get('height')} {p.get('fps')}fps {p.get('vcodec')} {p['duration']:.2f}s | "
          f"{info['lufs']} LUFS, TP {info['true_peak']} dBFS")
    for e in errors:
        print(f"  ✗ ERROR {e}")
    for w in warns:
        print(f"  ! WARN  {w}")
    print(f"  contact sheet → {sheet}  (inspect visually)")
    print("  ✓ PASS" if not errors else "  ✗ FAIL")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
