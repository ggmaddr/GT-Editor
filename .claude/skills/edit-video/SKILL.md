---
name: edit-video
description: Edit raw talking-head footage in "raw footage/" into a styled vertical short (1080x1920, 30fps, H.264) using the local pipeline — analyse, transcribe, rough cut, creative pass, render, QA. Use when the user says "edit my footage", "make a short from these clips", or drops new clips.
---

# Edit video (Phase 3)

Read `CLAUDE.md` (workspace root) and `styles/my-style.md` first. Run everything from the workspace root.
Pick a short kebab-case project name (ask only if the footage gives no hint). Never modify `raw footage/`.

1. **Analyse** — `.venv/bin/python scripts/prep.py <p> [clips…]`. Report resolution/fps/VFR/audio per clip.
   Check `analysis/framing.json`: `faces: 0` on real footage → look at a frame and set focusX/Y by hand.
2. **Transcribe** — `.venv/bin/python scripts/transcribe.py <p>` (turbo; `--language` if not English).
3. **Rough cut** — `.venv/bin/python scripts/rough_cut.py <p> [--order …]`. Read `edit_report.md` fully:
   verify every struck sentence really is a retake/filler and that no meaning was lost. Restore wrongly
   dropped words by widening that segment's srcIn/srcOut and adding the words back.
4. **Creative pass (you are the editor)** — edit `projects/<p>/timeline.json`:
   - Hook: strongest line within the first 1–2 s. Either reorder segments or add a cold-open segment
     duplicating the best line (unique id). Set the hookTitle text (≤7 words, a promise or tension,
     not a transcript copy) and `highlight` 1–2 words.
   - Story order: hook → context → payoff → CTA; cut tangents.
   - Emphasis: mark key nouns/numbers `emphasis: true` (≤1 per caption page).
   - Keyword overlays (`type: keyword`, 0.6–1.0 s, anchored with `seg`) on 2–4 key moments, with `pop` SFX.
   - B-roll/graphics: user assets in `public/assets/broll/`, self-made HyperFrames inserts
     (`motion/<name>`, render `--format webm`, overlay `type: clip`), or licensed stock only.
   - Accent transitions (whip/zoom + whoosh) only at section changes.
   - Music only from `public/assets/music/` (user-licensed). If none, say so — do not fetch random music.
5. **Preview** — `scripts/render.py <p> --still <frames>` at hook, each overlay, and 2–3 caption moments;
   look at them. Fix framing/caption collisions before the full render.
6. **Render + QA** — `scripts/render.py <p>` then follow the `video-qa` skill. Fix → re-render until PASS
   and the contact sheet looks right.
7. **Deliver** — list: exports/<p>/<p>-vN.mp4, .srt/.vtt, .timeline.json, project folder; duration,
   what was cut (seconds, fillers, retakes), hook choice and why, anything you could not do (e.g. no music).
   Offer `cd engine && npx remotion studio --public-dir ../projects/<p>/public --props ../projects/<p>/renders/props.json`.
