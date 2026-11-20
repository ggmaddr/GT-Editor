# AI Video Editor — workspace guide

Local, free pipeline that turns raw talking-head footage into edited vertical shorts in the user's
learned style. Claude is the editor: scripts do the measurable work, Claude makes the creative calls
by editing `timeline.json`, then renders and verifies.

## Layout
```
raw footage/        user's originals — READ-ONLY. Never modify, move, or delete.
references/         reference videos (user-supplied) + _analysis/<slug>/ (measurements, contact sheets)
styles/             my-style.md (profile + evidence + learned prefs), design-system.json (values engine reads),
                    assets/sfx (self-synthesised kit), assets/music (user-licensed tracks only)
projects/<name>/    timeline.json (EDITABLE SOURCE OF TRUTH), style.override.json (optional),
                    edit_report.md, analysis/{probe,framing}.json + transcripts/, public/ (Remotion public dir:
                    media/ CFR intermediates, assets/), renders/ (scratch: props, stills, partials)
exports/<name>/     <name>-vN.mp4 (+ .srt .vtt .timeline.json snapshot .qa.json .contact.jpg)
engine/             Remotion project (primary composition engine). src/{Edit,Shot,Captions,Overlays}.tsx
motion/<name>/      HyperFrames projects for standalone motion-graphic inserts (rendered → webm alpha)
scripts/            pipeline (Python in .venv, run with .venv/bin/python)
.claude/skills/     remotion-* and hyperframes* (vendor), plus edit-video, learn-style, revise-video, video-qa
```

## Engines — who does what (no duplication)
- **Remotion** = the edit. Data-driven: `Edit` composition renders `timeline.json` + merged style
  (segments with source-time words → captions; overlays/SFX anchored to segments via `seg`).
- **HyperFrames** = optional self-contained motion graphics (title cards, charts, explainers) authored
  as HTML/GSAP in `motion/`, rendered `--format webm` (alpha) and placed as an overlay of
  `type: "clip"` in the timeline. Run its CLI only via `scripts/hf` (telemetry disabled).
- **FFmpeg** = ingest/transcode, audio cleanup, loudness mastering, QA. **Whisper** = word timestamps.
  **yt-dlp** = reference download *only* when the user confirms authorization and the platform permits it.

## Pipeline
Steps, in order (prep: CFR 30fps intermediates, dialogue cleanup, face focus; rough_cut → timeline.json +
edit_report.md; then Claude's creative pass on timeline.json; stills for fast visual checks; full render →
exports/<p>/<p>-vN.* + QA). Usage examples for humans are in README.md.

```bash
scripts/doctor.sh --fix
.venv/bin/python scripts/prep.py <p> [clips…]
.venv/bin/python scripts/transcribe.py <p> --model turbo
.venv/bin/python scripts/rough_cut.py <p> --order a,b --hook "…"
.venv/bin/python scripts/render.py <p> --still 0,90
.venv/bin/python scripts/render.py <p>
.venv/bin/python scripts/qa.py exports/<p>/<p>-vN.mp4 --project <p>
.venv/bin/python scripts/analyze_reference.py references/x.mp4 --threshold 8
cd engine && npx remotion studio --public-dir ../projects/<p>/public --props ../projects/<p>/renders/props.json
scripts/selftest.sh
```

Docs rule: never put inline `#` comments inside bash code blocks (they break copy-paste); explain in prose
above the block, and chain setup steps with `&&` into one line where practical.

## timeline.json essentials (types: engine/src/types.ts)
- `segments[]` play in order. `srcIn/srcOut` source seconds; `zoom` (1 = cover), `focusX/Y` 0–1 for 9:16
  reframing, `drift`, `transitionIn` cut|whip|zoom|flash|fade, `words[]` in SOURCE seconds.
  Reorder/trim/delete segments freely — captions follow automatically.
- `overlays[]`: hookTitle | keyword | broll(full|card) | lowerThird | clip; `start/end` seconds, relative to
  segment `seg` if given (survives re-cuts). `sfx[]`: `{seg?, at, src}`. `music`: `{src, volume, duckTo}`.
- Word `emphasis: true` → secondary accent colour in captions.
- `rough_cut.py` overwrites timeline.json (backup → timeline.prev.json). After a creative pass, edit
  timeline.json directly instead of re-running it.

## Editing standards
- 1080×1920, 30 fps, H.264 yuv420p, AAC 48 kHz 320k, −14 LUFS integrated, true peak ≤ −1 dBTP.
- Never clip a word: cuts sit in word gaps with padding; keep the speaker's meaning; when removing a
  retake keep the later (corrected) take unless it's worse — read edit_report.md.
- Text inside the safe zone in design-system.json (platform UI: right rail, bottom caption/CTA area).
- Effects must serve the story: no zoom/SFX on every word; accent transitions mark topic changes.
- Music/SFX/B-roll: user-provided, self-generated, or properly licensed only. Disclose any paid service.
- Style values come from `styles/design-system.json`; project tweaks go in `projects/<p>/style.override.json`.

## Verification (never claim success without it)
After every render: `qa.py` must PASS (codec/res/fps/duration/black frames/loudness/peaks/safe zone),
then **look at** the `.contact.jpg` and stills at every changed moment (captions clipped? overlap with face?
wrong framing? black/frozen frames?). Fix and re-render before presenting.

## Learning loop
Accepted feedback → append to "Learned preferences" in `styles/my-style.md` and update
`design-system.json` when the preference is general (project-only tweaks → style.override.json).

## Gotchas
- Whisper runs on CPU (MPS unreliable for it); `turbo` model ≈ 3–4 s per 10 s of audio on M4 Max.
- OpenCV pinned <5 (Haar cascade). zod must stay at the version `npx remotion versions` asks for.
- Remotion licence: free for individuals and companies ≤3 people; larger for-profit orgs need a company
  licence (remotion.pro). Check before commercial use.
- Fonts load from Google Fonts at render time (network needed); add fonts in engine/src/fonts.ts.
