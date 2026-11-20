# AI Video Editor

Local, free pipeline that turns raw talking-head footage into edited vertical shorts (1080×1920, 30 fps, H.264) in your own learned style.
Remotion renders the edit, HyperFrames makes optional motion-graphic inserts, FFmpeg handles media/audio, Whisper transcribes, yt-dlp fetches authorised references.

## Quick setup (macOS)

Install everything, then verify:

```bash
brew install ffmpeg yt-dlp uv node@22 && uv venv .venv --python 3.12 && uv pip install --python .venv/bin/python -r requirements.txt && (cd engine && npm ci) && scripts/make_sfx.sh && scripts/doctor.sh
```

Run the end-to-end self-test (synthetic footage → rendered short in `exports/_selftest/`):

```bash
scripts/selftest.sh
```

If anything is missing later:

```bash
scripts/doctor.sh --fix
```

## Easiest way: ask Claude Code

Open Claude Code in this folder and say what you want. The project skills handle the rest.

| You say | Skill used |
|---|---|
| "Learn my style from these references" | `learn-style` |
| "Edit the footage in raw footage" | `edit-video` |
| "Make the hook bigger" / "faster pacing" | `revise-video` |
| "Check the render" | `video-qa` |

## Manual guide

All commands run from the repo root. Replace `my-video` with your project name.

### 1. Add footage

Copy clips into `raw footage/`. Originals are never modified.

### 2. Analyse, transcribe, rough cut

```bash
P=my-video && .venv/bin/python scripts/prep.py $P && .venv/bin/python scripts/transcribe.py $P && .venv/bin/python scripts/rough_cut.py $P
```

Read `projects/my-video/edit_report.md` to see what was cut (fillers, stutters, retakes, dead air) and the ranked hook candidates.

To use only some clips, or set their order:

```bash
.venv/bin/python scripts/prep.py my-video clip1.mov clip2.mov && .venv/bin/python scripts/rough_cut.py my-video --order clip2,clip1
```

To set the on-screen hook title:

```bash
.venv/bin/python scripts/rough_cut.py my-video --hook "STOP DOING THIS"
```

### 3. Edit the timeline (optional)

Edit `projects/my-video/timeline.json` by hand: reorder, trim (`srcIn`/`srcOut`), change `zoom`, `transitionIn`, add overlays, mark words `emphasis: true`. Captions follow the segments automatically. Field reference: `engine/src/types.ts`.

Re-running `rough_cut.py` overwrites manual edits (backup saved to `timeline.prev.json`).

### 4. Preview stills

Render specific frames as PNG into `projects/my-video/renders/`:

```bash
.venv/bin/python scripts/render.py my-video --still 0,90,300
```

### 5. Render

Full render with audio mastering, subtitles and QA:

```bash
.venv/bin/python scripts/render.py my-video
```

Output in `exports/my-video/`: `my-video-vN.mp4`, `.srt`, `.vtt`, `.timeline.json` (snapshot), `.qa.json`, `.contact.jpg` (frames at every cut, check it).

Re-run QA on any file:

```bash
.venv/bin/python scripts/qa.py exports/my-video/my-video-v1.mp4 --project my-video
```

### 6. Live preview in Remotion Studio

Needs one render first (it writes `renders/props.json`):

```bash
cd engine && npx remotion studio --public-dir ../projects/my-video/public --props ../projects/my-video/renders/props.json
```

### Music, B-roll, SFX

- Music: drop a licensed track into `projects/my-video/public/assets/music/` before `rough_cut.py`. It is ducked under speech.
- B-roll: put files in `projects/my-video/public/assets/broll/` and add a `broll` overlay in `timeline.json`.
- SFX: self-made kit in `styles/assets/sfx/` (whoosh, pop, riser, click, hit), copied into each project.

### Motion-graphic insert (HyperFrames)

Create a project, edit its `index.html`, then check and render with transparency:

```bash
scripts/hf init motion/my-card --skip-skills
```

```bash
cd motion/my-card && ../../scripts/hf check && ../../scripts/hf render --format webm -o card.webm && cp card.webm ../../projects/my-video/public/assets/broll/
```

Then add to `timeline.json` overlays: `{"id": "card", "type": "clip", "seg": "s05", "start": 0, "end": 2.5, "src": "assets/broll/card.webm"}`.

### Learn style from references

Analyse local reference videos:

```bash
.venv/bin/python scripts/analyze_reference.py references/ref1.mp4 references/ref2.mp4
```

Download first (only if you are authorised and the platform allows it):

```bash
.venv/bin/python scripts/analyze_reference.py --download "https://example.com/video"
```

Results in `references/_analysis/<name>/`: `summary.md`, `analysis.json`, `cuts.jpg`, `hook.jpg`. Use them to update `styles/design-system.json` (values the engine reads) and `styles/my-style.md` (why, with evidence), or ask Claude to do it.

## Style

- `styles/design-system.json`: captions, fonts, colours, pacing, zoom, transitions, audio levels. Applies to all projects.
- `projects/<name>/style.override.json`: same keys, overrides for one project only.

## Layout

| Folder | Contents |
|---|---|
| `raw footage/` | your originals (read-only) |
| `references/` | reference videos and their analysis |
| `projects/<name>/` | `timeline.json` (editable source), analysis, media |
| `exports/<name>/` | rendered versions, subtitles, QA reports |
| `styles/` | style profile, design system, SFX |
| `engine/` | Remotion project |
| `motion/` | HyperFrames inserts |
| `scripts/` | pipeline |

## Notes

- Remotion is free for individuals and companies of up to 3 people; larger companies need a licence for commercial use.
- Whisper models download on first use (~1.5 GB for `turbo`). Fonts load from Google Fonts at render time.
- Delivery spec: H.264 yuv420p, AAC 320k, −14 LUFS, true peak ≤ −1 dBTP.
