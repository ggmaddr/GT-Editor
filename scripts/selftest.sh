#!/usr/bin/env bash
# End-to-end toolchain check on synthetic footage (macOS `say` voice + test pattern).
# Exercises: prep -> transcribe -> rough_cut -> render (Remotion) -> master -> QA. Never touches raw footage/.
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"; cd "$ROOT"
SRC="$ROOT/projects/_selftest/source"; mkdir -p "$SRC"
PY="$ROOT/.venv/bin/python"
if [ ! -f "$SRC/take1.mov" ]; then
  say -v Samantha -r 175 -o "$SRC/a1.aiff" "Here is the biggest mistake people make with video editing. [[slnc 1400]] Um, [[slnc 500]] they they keep every single pause. [[slnc 1200]] Three seconds of silence kills your retention."
  say -v Samantha -r 175 -o "$SRC/a2.aiff" "So here is what to do. [[slnc 900]] Cut the dead air, [[slnc 300]] cut the dead air and keep the energy high. [[slnc 1000]] Try it on your next video."
  for i in 1 2; do
    d=$(ffprobe -v error -show_entries format=duration -of csv=p=0 "$SRC/a$i.aiff")
    pat=$([ $i = 1 ] && echo testsrc2 || echo smptehdbars)
    ffmpeg -y -v error -f lavfi -i "$pat=s=1920x1080:r=30000/1001:d=$d" -i "$SRC/a$i.aiff" -c:v libx264 -pix_fmt yuv420p -c:a aac -shortest "$SRC/take$i.mov"
  done
fi
"$PY" scripts/prep.py _selftest "$SRC/take1.mov" "$SRC/take2.mov"
"$PY" scripts/transcribe.py _selftest --model "${WHISPER_MODEL:-turbo}"
"$PY" scripts/rough_cut.py _selftest
"$PY" scripts/render.py _selftest
