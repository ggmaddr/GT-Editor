#!/usr/bin/env python3
"""Stage 2 — word-level transcription with OpenAI Whisper (local, free).

  .venv/bin/python scripts/transcribe.py <project> [--model turbo] [--language en]
  .venv/bin/python scripts/transcribe.py --file path/to/video.mp4 --out out.json   # standalone (references)

Writes analysis/transcripts/<clip>.json: {text, language, segments:[{start,end,text,words:[{word,start,end,probability}]}]}
"""
from __future__ import annotations

import argparse
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from common import project_dir, read_json, write_json  # noqa: E402

warnings.filterwarnings("ignore")
_model = None


def load(model_name: str):
    global _model
    if _model is None:
        import whisper

        # MPS is unreliable for Whisper's sparse ops; CPU on Apple Silicon is fast enough for short-form.
        _model = whisper.load_model(model_name, device="cpu")
    return _model


def transcribe(path: Path, model_name: str, language: str | None) -> dict:
    model = load(model_name)
    r = model.transcribe(str(path), word_timestamps=True, language=language, fp16=False, verbose=False,
                         condition_on_previous_text=False,  # reduces hallucinated repeats across takes
                         initial_prompt="Umm, let me think like, hmm... Okay, here's what I'm, like, thinking.")  # keeps fillers
    segs = [{"start": round(s["start"], 3), "end": round(s["end"], 3), "text": s["text"].strip(),
             "no_speech_prob": round(s.get("no_speech_prob", 0), 3),
             "words": [{"word": w["word"], "start": round(w["start"], 3), "end": round(w["end"], 3),
                        "probability": round(w.get("probability", 0), 3)} for w in s.get("words", [])]}
            for s in r["segments"]]
    return {"text": r["text"].strip(), "language": r.get("language"), "model": model_name, "segments": segs}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("project", nargs="?")
    ap.add_argument("--model", default="turbo", help="tiny|base|small|medium|large-v3|turbo")
    ap.add_argument("--language", default=None)
    ap.add_argument("--file")
    ap.add_argument("--out")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    if a.file:
        res = transcribe(Path(a.file), a.model, a.language)
        write_json(Path(a.out or Path(a.file).with_suffix(".transcript.json")), res)
        print(res["text"][:400])
        return
    proj = project_dir(a.project)
    probe = read_json(proj / "analysis/probe.json")
    for key, info in probe.items():
        out = proj / "analysis/transcripts" / f"{key}.json"
        if out.exists() and not a.force:
            print(f"• {key}: cached")
            continue
        print(f"→ transcribing {key} ({info['duration']:.1f}s, model={a.model}) ...", flush=True)
        res = transcribe(proj / "public" / info["media"], a.model, a.language)
        write_json(out, res)
        nwords = sum(len(s["words"]) for s in res["segments"])
        print(f"  ✓ {nwords} words: {res['text'][:120]}{'…' if len(res['text']) > 120 else ''}")


if __name__ == "__main__":
    main()
