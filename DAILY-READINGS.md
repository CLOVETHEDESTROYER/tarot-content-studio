# Daily editions: implementation plan

Build five independent flows: Tarot, Western astrology, Chinese astrology, Numerology, and Combined. All are collective readings without viewer questions. Combined editions let the producer select any two or more systems.

Each edition records its date, America/Denver publication timezone, morning (06:00) or evening (18:00) slot, calculation instant, source snapshot, selected artwork, exact draw, script, narration, and export. Morning copy supports intentions and choices for the day; evening copy supports reflection and the next step. Date and timezone boundaries, including daylight saving time, are calculated rather than guessed.

Western context uses calculated tropical, geocentric Sun/Moon/planet longitudes, lunar phase, and relevant major aspects. Chinese context uses the lunisolar calendar for the annual zodiac (Chinese New Year boundary) and the local calendar date's stem–branch day cycle. It is a collective calendar reading, not a personal BaZi chart. Numerology explicitly sums the Gregorian date's digits, reducing while preserving 11/22/33. All interpretation remains symbolic.

Optional world context uses timestamped public RSS headlines. Save publisher, URL, publication time, fetch time, and cutoff with each reading. Skip missing/stale sources and do not manufacture historical or future headlines. Interpretations must not claim celestial movements caused reported events.

Create complete visual collections in the existing Esoteric Minimal and Storybook Cartoon styles: twelve Western signs, twelve Chinese zodiac animals, and twelve numerology cards (1–9, 11, 22, 33) in each style. Use generated illustration atlases, extract individual portrait cards, and typeset accurate names/numbers in code. Preserve prompts and source atlases. Tarot continues to use its existing complete decks.

Add a local daily planner with configurable reading type for each slot, a date-based queue, idempotent preparation, background video rendering, restart recovery, and clear statuses. Targets are 06:00 and 18:00 America/Denver. Facebook does not exist yet; this phase prepares local content and posting bundles, without social publishing or external account setup. Automatic local preparation is opt-in and requires the studio to remain running.

Verify all flows, both art styles, lunar new year, midnight/DST boundaries, numerology reduction, stable daily draws, stale/news cutoff handling, planner idempotency/recovery, editor interaction, and real portrait video exports.
