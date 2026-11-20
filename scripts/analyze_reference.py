#!/usr/bin/env python3
"""Reference-video analysis -> measured editing characteristics (no guessing).

  .venv/bin/python scripts/analyze_reference.py references/clip.mp4 [more files...]
  .venv/bin/python scripts/analyze_reference.py --download "<url>"   # ONLY when the user confirms they're authorized
                                                                      # and the platform permits it (yt-dlp)

Outputs references/_analysis/<slug>/:
  analysis.json  — cuts, shot-length stats, hook density, WPM, pause tightness, loudness, music-bed
                   estimate, colour palette, on-screen-text vertical positions, zoom/motion energy
  summary.md     — human-readable digest
  cuts.jpg       — frame after every detected cut (labelled)      } the agent MUST look at these to judge
  hook.jpg       — 0–5 s at 0.5 s steps                           } typography, captions, transitions, B-roll
  transcript.json
Reference media is analysed for *principles* only — never reuse its footage, music, or branding.
"""
from __future__ import annotations

import argparse
import re
import statistics as st
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import REFS, die, summarize_probe, write_json  # noqa: E402
from qa import contact_sheet  # noqa: E402


def slug(p: Path) -> str:
    return re.sub(r"[^a-z0-9]+", "-", p.stem.lower()).strip("-")[:60]


def download(url: str) -> Path:
    out = REFS / "_downloads"
    out.mkdir(parents=True, exist_ok=True)
    r = subprocess.run(["yt-dlp", "--no-playlist", "-f", "bv*[height<=1920]+ba/b", "--merge-output-format", "mp4",
                        "-o", str(out / "%(uploader)s-%(id)s.%(ext)s"), "--print", "after_move:filepath", url],
                       capture_output=True, text=True)
    if r.returncode != 0:
        die(f"download failed (report this limitation, do not invent an analysis):\n{r.stderr[-800:]}")
    return Path(r.stdout.strip().splitlines()[-1])


def scene_cuts(path: Path, thresh: float) -> list[float]:
    err = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-an", "-vf",
                          f"scdet=threshold={thresh}", "-f", "null", "-"], capture_output=True, text=True).stderr
    cuts = []
    for t in (float(x) for x in re.findall(r"lavfi\.scd\.time: ([\d.]+)", err)):
        if not cuts or t - cuts[-1] > 0.2:  # merge double-detections
            cuts.append(round(t, 3))
    return cuts


def pct(xs, q):
    xs = sorted(xs)
    return xs[min(len(xs) - 1, int(q * len(xs)))] if xs else None


def audio_profile(path: Path, words: list[dict]) -> dict:
    import numpy as np

    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(path), "-ac", "1", "-ar", "16000", "-f", "s16le", "-"], capture_output=True).stdout
    if not raw:
        return {"has_audio": False}
    a = np.frombuffer(raw, np.int16).astype(np.float32) / 32768
    def rms_db(seg):
        return float(20 * np.log10(np.sqrt(np.mean(seg ** 2)) + 1e-9)) if len(seg) else None
    speech = np.concatenate([a[int(w["start"] * 16000): int(w["end"] * 16000)] for w in words]) if words else a[:0]
    gaps = [a[int(p["end"] * 16000) + 800: int(n["start"] * 16000) - 800] for p, n in zip(words, words[1:]) if n["start"] - p["end"] > 0.25]
    gap_audio = np.concatenate(gaps) if gaps else a[:0]
    s_db, g_db = rms_db(speech), rms_db(gap_audio)
    eb = subprocess.run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-af", "ebur128=peak=true", "-f", "null", "-"], capture_output=True, text=True).stderr
    I = re.findall(r"I:\s+(-?[\d.]+) LUFS", eb)
    res = {"has_audio": True, "integrated_lufs": float(I[-1]) if I else None, "speech_rms_db": s_db, "gap_rms_db": g_db}
    if s_db is not None and g_db is not None:
        diff = s_db - g_db
        res["speech_to_gap_db"] = round(diff, 1)
        res["music_bed_likely"] = diff < 22  # quiet gaps (>~25 dB below speech) => no bed
    return res


def visual_profile(path: Path, dur: float) -> dict:
    import cv2
    import numpy as np

    cap = cv2.VideoCapture(str(path))
    n = max(8, min(60, int(dur)))
    pixels, bright, sat, text_y, motion, prev = [], [], [], [], [], None
    for i in range(n):
        cap.set(cv2.CAP_PROP_POS_MSEC, dur * 1000 * (i + 0.5) / n)
        ok, fr = cap.read()
        if not ok:
            continue
        H, W = fr.shape[:2]
        small = cv2.resize(fr, (96, int(96 * H / W)))
        pixels.append(small.reshape(-1, 3))
        hsv = cv2.cvtColor(small, cv2.COLOR_BGR2HSV)
        bright.append(hsv[..., 2].mean() / 255)
        sat.append(hsv[..., 1].mean() / 255)
        g = cv2.cvtColor(cv2.resize(fr, (360, int(360 * H / W))), cv2.COLOR_BGR2GRAY)
        if prev is not None:
            motion.append(float(np.mean(cv2.absdiff(g, prev))))
        prev = g
        # text-like regions: morphological gradient + horizontal closing (heuristic, no OCR)
        grad = cv2.morphologyEx(g, cv2.MORPH_GRADIENT, cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3)))
        _, bw = cv2.threshold(grad, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
        bw = cv2.morphologyEx(bw, cv2.MORPH_CLOSE, cv2.getStructuringElement(cv2.MORPH_RECT, (15, 3)))
        cnts, _ = cv2.findContours(bw, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        gh, gw = g.shape
        for c in cnts:
            x, y, w, h = cv2.boundingRect(c)
            fill = cv2.contourArea(c) / max(1, w * h)
            if w > gw * 0.25 and 0.015 * gh < h < 0.12 * gh and w / h > 2.5 and fill > 0.45:
                text_y.append((y + h / 2) / gh)
    cap.release()
    px = np.vstack(pixels).astype(np.float32)
    _, labels, centers = cv2.kmeans(px, 6, None, (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 20, 1.0), 3, cv2.KMEANS_PP_CENTERS)
    counts = np.bincount(labels.flatten(), minlength=6)
    palette = [{"hex": "#%02X%02X%02X" % tuple(int(v) for v in centers[i][::-1]), "share": round(float(counts[i] / counts.sum()), 3)}
               for i in np.argsort(-counts)]
    bands = {f"{b * 10}-{b * 10 + 10}%": 0 for b in range(10)}
    for y in text_y:
        b = min(9, int(y * 10))
        bands[f"{b * 10}-{b * 10 + 10}%"] += 1
    return {"palette": palette, "mean_brightness": round(st.mean(bright), 3), "mean_saturation": round(st.mean(sat), 3),
            "motion_energy_mean": round(st.mean(motion), 2) if motion else None,
            "text_region_y_bands": bands, "text_frames_ratio": round(len(set(text_y)) / n, 2) if text_y else 0.0,
            "note_text": "text_region_y_bands is a heuristic (edge density), confirm on cuts.jpg/hook.jpg"}


def analyze(path: Path, thresh: float, model: str) -> Path:
    from transcribe import transcribe

    out = REFS / "_analysis" / slug(path)
    out.mkdir(parents=True, exist_ok=True)
    info = summarize_probe(path)
    dur = info["duration"]
    print(f"→ {path.name}: {info.get('width')}x{info.get('height')} {info.get('fps')}fps {dur:.1f}s")
    cuts = [c for c in scene_cuts(path, thresh) if 0.15 < c < dur - 0.15]
    bounds = [0.0] + cuts + [dur]
    shots = [round(b - a, 3) for a, b in zip(bounds, bounds[1:]) if b - a > 0.05]

    tr_path = out / "transcript.json"
    if tr_path.exists():
        import json
        tr = json.loads(tr_path.read_text())
    else:
        tr = transcribe(path, model, None)
        write_json(tr_path, tr)
    words = [w for s in tr["segments"] for w in s["words"]]
    speech_time = sum(w["end"] - w["start"] for w in words)
    gaps = [n["start"] - p["end"] for p, n in zip(words, words[1:])]
    hook_words = [w["word"].strip() for w in words if w["start"] < 3.0]

    res = {
        "file": str(path), "probe": info,
        "cuts": {"threshold": thresh, "times": cuts, "count": len(cuts), "per_minute": round(len(cuts) / dur * 60, 1),
                 "in_first_3s": sum(1 for c in cuts if c < 3), "in_first_5s": sum(1 for c in cuts if c < 5)},
        "shot_length_s": {"mean": round(st.mean(shots), 2), "median": round(st.median(shots), 2), "p10": pct(shots, 0.1),
                          "p90": pct(shots, 0.9), "min": min(shots), "max": max(shots), "all": shots},
        "speech": {"words": len(words), "wpm": round(len(words) / (dur / 60), 1) if dur else None,
                   "speech_ratio": round(speech_time / dur, 2) if dur else None,
                   "median_gap_ms": round(st.median(gaps) * 1000) if gaps else None,
                   "gaps_over_300ms_pct": round(100 * sum(g > 0.3 for g in gaps) / len(gaps), 1) if gaps else None,
                   "first_word_at_s": round(words[0]["start"], 2) if words else None,
                   "hook_first_3s": " ".join(hook_words), "full_text": tr["text"]},
        "audio": audio_profile(path, [{"start": w["start"], "end": w["end"]} for w in words]),
        "visual": visual_profile(path, dur),
    }
    write_json(out / "analysis.json", res)
    contact_sheet(path, [(min(c + 0.07, dur - 0.05), f"cut {i + 1}") for i, c in enumerate(cuts[:47])] + [(0.05, "start")], out / "cuts.jpg", cols=8, w=200)
    contact_sheet(path, [(t / 2, "hook") for t in range(0, 11)], out / "hook.jpg", cols=6, w=240)
    s, sp, au, vi = res["shot_length_s"], res["speech"], res["audio"], res["visual"]
    md = f"""# Reference analysis — {path.name}

| Metric | Value |
|---|---|
| Format | {info.get('width')}x{info.get('height')} @ {info.get('fps')} fps, {dur:.1f}s |
| Cuts | {res['cuts']['count']} ({res['cuts']['per_minute']}/min), {res['cuts']['in_first_3s']} in first 3 s |
| Shot length | median {s['median']}s, mean {s['mean']}s, p10 {s['p10']}s, p90 {s['p90']}s |
| Speech | {sp['wpm']} WPM, speech ratio {sp['speech_ratio']}, first word at {sp['first_word_at_s']}s |
| Pause tightness | median gap {sp['median_gap_ms']} ms, {sp['gaps_over_300ms_pct']}% gaps > 300 ms |
| Loudness | {au.get('integrated_lufs')} LUFS; speech-to-gap {au.get('speech_to_gap_db')} dB → music bed likely: {au.get('music_bed_likely')} |
| Look | brightness {vi['mean_brightness']}, saturation {vi['mean_saturation']}, motion energy {vi['motion_energy_mean']} |
| Palette | {' '.join(p['hex'] + f"({p['share']})" for p in vi['palette'])} |
| Text y-bands (heuristic) | {', '.join(f'{k}:{v}' for k, v in vi['text_region_y_bands'].items() if v)} |

**Hook (first 3 s):** {sp['hook_first_3s']}

Visual review required: `cuts.jpg`, `hook.jpg` (typography, caption style/placement, transitions, B-roll, graphics).
"""
    (out / "summary.md").write_text(md)
    print(md)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="*")
    ap.add_argument("--download", action="append", default=[], help="URL to fetch with yt-dlp (authorized use only)")
    ap.add_argument("--threshold", type=float, default=10, help="scdet sensitivity 0-100 (lower = more cuts; 6-8 catches subtle punch-ins)")
    ap.add_argument("--model", default="turbo")
    a = ap.parse_args()
    paths = [Path(f) for f in a.files] + [download(u) for u in a.download]
    if not paths:
        die("give reference files (put them in references/) or --download URL")
    for p in paths:
        if not p.exists():
            die(f"missing {p}")
        print(f"✓ {analyze(p, a.threshold, a.model)}")


if __name__ == "__main__":
    main()
