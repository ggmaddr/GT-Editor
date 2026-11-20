#!/usr/bin/env bash
# Synthesizes an ORIGINAL sound-effect kit with FFmpeg (no third-party samples -> no licensing issues).
set -euo pipefail
OUT="$(cd "$(dirname "$0")/.." && pwd)/styles/assets/sfx"; mkdir -p "$OUT"
f() { ffmpeg -y -v error "$@"; }
# whoosh: pink noise, swelled envelope, band-limited
f -f lavfi -i "anoisesrc=d=0.5:c=pink:r=48000:a=0.9" -af "highpass=f=250,lowpass=f=4500,volume='pow(sin(PI*t/0.5),3)':eval=frame,afade=t=out:st=0.4:d=0.1,aformat=channel_layouts=stereo" "$OUT/whoosh.wav"
# pop: fast downward pitch blip
f -f lavfi -i "aevalsrc='0.9*sin(2*PI*(1100-700*t/0.09)*t)*exp(-t*38)':s=48000:d=0.14" -af "aformat=channel_layouts=stereo" "$OUT/pop.wav"
# riser: accelerating sine sweep + airy noise, 1.2 s
f -f lavfi -i "aevalsrc='0.35*sin(2*PI*(180+900*t*t)*t)*(t/1.2)':s=48000:d=1.2" -f lavfi -i "anoisesrc=d=1.2:c=white:r=48000:a=0.25" \
  -filter_complex "[1]highpass=f=3000,volume='t/1.2':eval=frame[n];[0][n]amix=inputs=2:normalize=0,afade=t=out:st=1.1:d=0.1,aformat=channel_layouts=stereo" "$OUT/riser.wav"
# click: tiny filtered transient (UI / text appear)
f -f lavfi -i "anoisesrc=d=0.03:c=white:r=48000:a=0.8" -af "highpass=f=2000,afade=t=out:st=0:d=0.03,aformat=channel_layouts=stereo" "$OUT/click.wav"
# hit: low thump for emphasis
f -f lavfi -i "aevalsrc='1.0*sin(2*PI*(90-40*t)*t)*exp(-t*9)':s=48000:d=0.45" -af "aformat=channel_layouts=stereo" "$OUT/hit.wav"
ls -1 "$OUT"
