---
name: learn-style
description: Analyse 3–5 reference videos (local files or authorised URLs) and turn measured editing characteristics into styles/my-style.md and styles/design-system.json — inspired by, never copying, the references. Use when the user provides reference videos or asks to learn/update their editing style.
---

# Learn style (Phase 2)

1. **Get references.** Local files → `references/`. URLs → only after the user confirms they may
   download them and the platform permits it: `scripts/analyze_reference.py --download "<url>"`.
   If a download fails or is refused, report it — never invent an analysis.
2. **Measure** — `.venv/bin/python scripts/analyze_reference.py references/<file>…`
   (`--threshold 6–8` if punch-ins aren't detected; compare cut count with what you see).
3. **Look** — open every `references/_analysis/<slug>/hook.jpg` and `cuts.jpg`. Note: caption font class
   (geometric sans / condensed / serif), case, words per page, colour of active word, stroke/box, vertical
   position, animation hints, title cards, B-roll frequency and type, zoom/punch-in use, transitions,
   colour grade. Cite the timestamp for each observation. Mark anything you can't confirm as "unverified".
4. **Synthesise** — a table per reference + cross-reference consensus (median of measured numbers).
   Separate *transferable principles* (pacing, hook density, caption legibility, zoom cadence) from
   *signature identity* (exact fonts-as-brand, colour schemes, logos, music, recurring graphic devices) —
   the latter is never copied. Choose an original identity that satisfies the principles.
5. **Write** — rewrite `styles/my-style.md` (keep "Learned preferences" section intact; set Status to
   LEARNED with date and reference list; every value has an Evidence column) and update the numbers in
   `styles/design-system.json` (`pacing`, `captions`, `zoom`, `titles`, `transitions`, `audio`). Bump `name`.
6. **Prove it** — re-render the latest project (or `scripts/selftest.sh`) and show the user a contact sheet
   with the new style. Ask which differences they like; record answers as learned preferences.
