---
name: video-qa
description: Verify a rendered video before presenting it — automated checks (codec, resolution, fps, duration, black/frozen frames, loudness, peaks, safe zone) plus a mandatory visual inspection of frames. Use after every render.
---

# Video QA

1. `.venv/bin/python scripts/qa.py exports/<p>/<p>-vN.mp4 --project <p>` (render.py runs it automatically).
   Any ERROR → fix and re-render. WARNs: judge each (e.g. silence ≥1s intentional?).
2. Read `<p>-vN.contact.jpg` (frame after every cut + caption samples). Check:
   captions fully visible, not over the face/mouth, not in the right-rail/bottom UI zones; no word collision;
   hook title readable in <1 s; correct reframing (head not cut off); no black/blank/flash frames except
   intended; overlays not covering captions.
3. Spot-check sync: `scripts/render.py <p> --still <frame>` at a word onset; caption word should match
   the speech at that frame (compare with transcript times in timeline.json).
4. Watch-equivalent: `ffprobe` duration = timeline; scrub start/middle/end stills.
5. Report results truthfully — numbers from qa.json, and what you looked at.
