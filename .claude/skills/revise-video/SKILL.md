---
name: revise-video
description: Apply natural-language feedback to an existing edit ("make the hook bigger", "faster pacing", "change caption style", "captions behind my head", "more cinematic") by changing only the affected parts of timeline.json/style, re-rendering, verifying, and recording accepted preferences. Use for any change request on a rendered draft.
---

# Revise video (Phase 4)

1. Identify the project + latest version (`exports/<p>/`). Read `projects/<p>/timeline.json`.
2. Map the request to the smallest change:
   | Request | Change |
   |---|---|
   | bigger hook | `titles.hookFontSize`↑ / hookScale↑ / riser SFX / tighter first segment / stronger hook text |
   | faster pacing | `pacing.maxPauseMs`↓, `padAfterMs`↓, `targetShotSec`↓ → re-run rough_cut **only if** no manual creative edits; otherwise trim srcIn/srcOut by hand |
   | more/interesting transitions | `transitionIn` on chosen segments (whip/zoom/flash) + whoosh SFX at `seg` |
   | caption style | `captions.*` / `typography.*` / colours in style.override.json (project) |
   | captions behind head | needs a subject matte: generate per-clip alpha mattes (e.g. HyperFrames `remove-background`, or Remotion video-matting guide), add a foreground layer above captions in Shot.tsx; confirm cost/time first |
   | more cinematic | slower drift, fewer punch-ins, `fade`/`zoom` transitions, letterbox/grade via ffmpeg LUT on intermediates, softer music |
3. Project-only change → `projects/<p>/style.override.json`; edit timeline segments by id. Don't rebuild
   unrelated sections; don't re-run prep/transcribe.
4. Preview stills at the changed moments, then full render → `video-qa`. Present vN+1 with a one-line diff
   of what changed.
5. When the user accepts: append to "Learned preferences" in `styles/my-style.md`
   (`- YYYY-MM-DD <project>: <preference> → <setting>`), and promote to `design-system.json` if it's a
   general preference (ask if unclear).
