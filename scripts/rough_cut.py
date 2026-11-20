#!/usr/bin/env python3
"""Stage 3 — deterministic rough cut from word timestamps -> projects/<p>/timeline.json + edit_report.md

  .venv/bin/python scripts/rough_cut.py <project> [--order clipA,clipB] [--hook "TEXT"] [--keep-repeats]

Rules (all tunable in styles/design-system.json -> pacing):
  • drops filler words, stutters ("I think I think"), false starts and repeated takes (keeps the LATER take)
  • removes dead air: gaps > maxPauseMs are cut, leaving padBefore/padAfter around words (never clips a word)
  • sentence-final ? ! … keep a short dramatic hold
  • long shots are split at word gaps (~targetShotSec) and alternate punch-in zoom; jump cuts alternate zoom too
  • clip changes get the accent transition + whoosh
The agent (Claude) then applies creative judgment: hook choice/reorder, keywords, B-roll — by editing timeline.json.
"""
from __future__ import annotations

import argparse
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path
from functools import partial

sys.path.insert(0, str(Path(__file__).parent))
from common import die, load_style, project_dir, read_json, write_json  # noqa: E402

HOOK_WORDS = {"secret", "mistake", "never", "stop", "why", "how", "best", "worst", "nobody", "everyone", "truth",
              "wrong", "actually", "free", "fast", "easy", "hard", "only", "biggest", "real", "changed", "you", "your"}


def norm(t: str) -> str:
    return re.sub(r"[^a-z0-9%$']+", "", t.lower())


def load_words(proj: Path, key: str) -> list[dict]:
    tr = read_json(proj / "analysis/transcripts" / f"{key}.json")
    words = []
    for s in tr["segments"]:
        for w in s["words"]:
            if w["end"] > w["start"] and w["word"].strip():
                words.append({"text": w["word"].strip(), "n": norm(w["word"]), "start": w["start"], "end": w["end"],
                              "p": w.get("probability", 1.0), "clip": key, "drop": None})
    return words


def sentences(words: list[dict], gap: float = 0.8) -> list[list[dict]]:
    out, cur = [], []
    for i, w in enumerate(words):
        if cur and w["start"] - cur[-1]["end"] > gap:
            out.append(cur)
            cur = []
        cur.append(w)
        if re.search(r"[.!?…]$", w["text"]):
            out.append(cur)
            cur = []
    if cur:
        out.append(cur)
    return out


FILLER_RE = re.compile(r"^(u+[mh]+|e+r+m*|a+h+|h+m+|m+h*m+|uh+m+)$")


def mark_fillers(words, fillers):
    fs = {norm(f) for f in fillers}
    for w in words:
        if w["n"] in fs or FILLER_RE.match(w["n"] or "x"):
            w["drop"] = "filler"


def mark_stutters(words):
    live = [w for w in words if not w["drop"]]
    for n in (4, 3, 2, 1):
        i = 0
        while i + 2 * n <= len(live):
            a = [w["n"] for w in live[i:i + n]]
            b = [w["n"] for w in live[i + n:i + 2 * n]]
            if a == b and all(a) and not any(w["drop"] for w in live[i:i + 2 * n]):
                for w in live[i:i + n]:
                    w["drop"] = "stutter"
                i += n
            else:
                i += 1


def mark_retakes(sents, threshold=0.62):
    """Earlier sentence ≈ a following one (or is its false-start prefix) -> drop the earlier take."""
    texts = [" ".join(w["n"] for w in s if not w["drop"]) for s in sents]
    for i in range(len(sents)):
        if not texts[i]:
            continue
        for j in (i + 1, i + 2):
            if j >= len(sents) or not texts[j]:
                continue
            a, b = texts[i].split(), texts[j].split()
            ratio = SequenceMatcher(None, a, b).ratio()
            prefix = len(a) >= 2 and len(a) < len(b) and b[: len(a)] == a
            restart = len(a) >= 3 and a[:3] == b[:3] and len(a) <= len(b)
            if ratio >= threshold or prefix or restart:
                for w in sents[i]:
                    w["drop"] = w["drop"] or f"retake(≈{'prefix' if prefix else 'restart' if restart else f'{ratio:.2f}'})"
                break


def keep_ranges(words, pace) -> list[list[dict]]:
    """Group kept words into continuous runs; a dropped word or long gap forces a cut."""
    runs, cur, prev_kept_idx = [], [], None
    max_gap = pace["maxPauseMs"] / 1000
    for i, w in enumerate(words):
        if w["drop"]:
            continue
        if cur:
            gap = w["start"] - cur[-1]["end"]
            dropped_between = any(words[k]["drop"] for k in range(prev_kept_idx + 1, i))
            if gap > max_gap or dropped_between:
                runs.append(cur)
                cur = []
        cur.append(w)
        prev_kept_idx = i
    if cur:
        runs.append(cur)
    return runs


def run_bounds(run, words, pace, clip_dur):
    pb, pa = pace["padBeforeMs"] / 1000, pace["padAfterMs"] / 1000
    first, last = run[0], run[-1]
    i0, i1 = words.index(first), words.index(last)
    hold = 0.32 if re.search(r"[?!…]$|\.\.\.$", last["text"]) else pa
    lo = words[i0 - 1]["end"] if i0 > 0 else 0.0
    hi = words[i1 + 1]["start"] if i1 + 1 < len(words) else clip_dur
    start = max(lo + 0.02 if i0 > 0 else 0.0, first["start"] - pb)
    end = min(hi - 0.02 if i1 + 1 < len(words) else clip_dur, last["end"] + hold)
    return round(max(0.0, start), 3), round(max(start + 0.05, end), 3)


def split_long(run, start, end, target):
    """Split a continuous run at word gaps near multiples of target seconds -> [(start,end,words)]."""
    if end - start < target * 1.6 or len(run) < 4:
        return [(start, end, run)]
    pieces, s, bucket = [], start, []
    for k, w in enumerate(run):
        bucket.append(w)
        nxt = run[k + 1] if k + 1 < len(run) else None
        if nxt and (w["end"] - s) >= target and (end - w["end"]) >= target * 0.6:
            cut = round((w["end"] + nxt["start"]) / 2, 3)
            pieces.append((s, cut, bucket))
            s, bucket = cut, []
    pieces.append((s, end, bucket))
    return pieces


def hook_score(sent):
    ws = [w for w in sent if not w["drop"]]
    if not ws:
        return -99
    text = " ".join(w["text"] for w in ws)
    sc = 0.0
    sc += 2 if "?" in text else 0
    sc += 1.5 if re.search(r"\d", text) else 0
    sc += sum(1 for w in ws if w["n"] in HOOK_WORDS) * 0.8
    sc += 1 if 5 <= len(ws) <= 16 else -1
    sc += sum(w["p"] for w in ws) / len(ws)
    return round(sc, 2)


def emphasis(text: str) -> bool:
    return bool(re.search(r"\d|%|\$", text))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project")
    ap.add_argument("--order", help="comma-separated clip keys (default: probe order = filename order)")
    ap.add_argument("--hook", help="hook title text (default: best-scoring short sentence, trimmed)")
    ap.add_argument("--keep-repeats", action="store_true")
    a = ap.parse_args()

    proj = project_dir(a.project)
    style = load_style(proj)
    pace, zoomcfg, trans = style["pacing"], style["zoom"], style["transitions"]
    probe, framing = read_json(proj / "analysis/probe.json"), read_json(proj / "analysis/framing.json")
    order = a.order.split(",") if a.order else list(probe.keys())

    all_sents, per_clip = [], {}
    for key in order:
        if not (proj / "analysis/transcripts" / f"{key}.json").exists():
            die(f"no transcript for {key}; run transcribe.py first")
        words = load_words(proj, key)
        mark_fillers(words, pace["fillers"])
        mark_stutters(words)
        sents = sentences(words)
        per_clip[key] = (words, sents)
        all_sents += sents
    if not a.keep_repeats:
        mark_retakes(all_sents)  # across clips too: a re-recorded line in a later clip wins

    segments, sfx, report, n = [], [], [], 0
    src_total = sum(probe[k]["duration"] for k in order)
    for ci, key in enumerate(order):
        words, sents = per_clip[key]
        info, fr = probe[key], framing[key]
        for r in keep_ranges(words, pace):
            s, e = run_bounds(r, words, pace, info["duration"])
            for pi, (ps, pe, pw) in enumerate(split_long(r, s, e, pace["targetShotSec"])):
                n += 1
                first_of_clip = ci > 0 and not any(sg["src"] == info["media"] for sg in segments)
                zoom = zoomcfg["hookScale"] if n == 1 else (zoomcfg["punchInScale"] if (n % 2 == 0 and zoomcfg["alternatePunchIns"]) else 1.0)
                seg = {"id": f"s{n:02d}", "src": info["media"], "srcIn": ps, "srcOut": pe,
                       "srcW": info["width"], "srcH": info["height"], "zoom": zoom,
                       "focusX": fr["focusX"], "focusY": fr["focusY"], "drift": n == 1,
                       "transitionIn": trans["accent"] if first_of_clip else trans["default"],
                       "note": "split (continuous)" if pi else "",
                       "words": [{"text": w["text"], "start": w["start"], "end": w["end"], **({"emphasis": True} if emphasis(w["text"]) else {})} for w in pw]}
                segments.append(seg)
                if first_of_clip:
                    sfx.append({"seg": seg["id"], "at": 0, "src": "assets/sfx/whoosh.wav"})
        for st in sents:
            line = " ".join((f"~~{w['text']}~~" if w["drop"] else w["text"]) for w in st)
            reasons = sorted({w["drop"] for w in st if w["drop"]})
            report.append((key, st[0]["start"], line, reasons, hook_score(st)))

    if not segments:
        die("no speech kept — check transcripts")
    out_dur = sum(sg["srcOut"] - sg["srcIn"] for sg in segments)

    # hook title
    best = sorted(report, key=lambda r: -r[4])
    hook_text = a.hook
    if not hook_text:
        first_words = [w["text"] for w in segments[0]["words"]]
        hook_text = " ".join(first_words[:6]).rstrip(",.") if first_words else ""
    overlays = []
    if style["titles"]["hookTitle"] and hook_text:
        overlays.append({"id": "hook", "type": "hookTitle", "seg": "s01", "start": 0, "end": style["titles"]["hookDurationSec"],
                         "text": hook_text.upper(), "highlight": []})
        sfx.append({"seg": "s01", "at": 0, "src": "assets/sfx/pop.wav"})

    tl = {"version": 1, "title": a.project, "segments": segments, "overlays": overlays, "sfx": sfx, "music": None}
    music_dir = proj / "public/assets/music"
    tracks = sorted(music_dir.glob("*.mp3")) + sorted(music_dir.glob("*.wav")) + sorted(music_dir.glob("*.m4a"))
    if tracks:
        tl["music"] = {"src": f"assets/music/{tracks[0].name}"}
    tlp = proj / "timeline.json"
    if tlp.exists():
        (proj / "timeline.prev.json").write_text(tlp.read_text())
    write_json(tlp, tl)

    dropped = [w for k in order for w in per_clip[k][0] if w["drop"]]
    md = [f"# Edit report — {a.project}", "",
          f"- Source: {src_total:.1f}s across {len(order)} clip(s) → rough cut **{out_dur:.1f}s** ({len(segments)} shots, avg {out_dur / len(segments):.2f}s)",
          f"- Removed: {len([w for w in dropped if w['drop'] == 'filler'])} fillers, {len([w for w in dropped if w['drop'] == 'stutter'])} stutter words, "
          f"{len([w for w in dropped if str(w['drop']).startswith('retake')])} words in retakes/false starts, {src_total - out_dur:.1f}s total",
          f"- Hook title: \"{hook_text}\"", f"- Music: {tl['music']['src'] if tl['music'] else 'none (add licensed track to public/assets/music/)'}", "",
          "## Hook candidates (heuristic score — agent makes the final call)", ""]
    md += [f"- **{sc}** `{k}@{t:.1f}s` {line}" for k, t, line, _, sc in best[:5]]
    md += ["", "## Transcript (~~struck~~ = removed)", ""]
    md += [f"- `{k}@{t:6.1f}s` {line}" + (f"  ← {', '.join(rs)}" if rs else "") for k, t, line, rs, _ in report]
    (proj / "edit_report.md").write_text("\n".join(md) + "\n")
    print("\n".join(md[:7]))
    print(f"✓ {tlp}\n✓ {proj / 'edit_report.md'}")


print = partial(print, flush=True)  # noqa: A001

if __name__ == "__main__":
    main()
