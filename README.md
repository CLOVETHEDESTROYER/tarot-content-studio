# StarPower Content Studio

**Unified studio (v3):** Live Studio, the original card library and longer spreads, daily readings, video exports, Muse jobs and updates now run in one desktop app. Live supports tarot, Western/Chinese astrology, numerology and combined readings. See [UNIFIED-STUDIO.md](UNIFIED-STUDIO.md).

**Windows desktop:** use **StarPower Content Studio.lnk** or **Start Desktop Studio.cmd** to open a native app window. See [WINDOWS-DESKTOP.md](WINDOWS-DESKTOP.md) for packaging and storage details.

A standalone Windows and macOS studio for making tarot, Western astrology, Chinese astrology, numerology, and combined daily reading videos. It has its own server, editor, database, bundled artwork, and exports. The live website does not need to be running.

**Intel Mac / macOS Sequoia:** download the Mac-Intel ZIP from the private repository's [desktop releases](https://github.com/CLOVETHEDESTROYER/tarot-content-studio/releases/latest), extract it, and move the app to your user Applications folder. No Python or Node setup is required. See [DESKTOP-UPDATES.md](DESKTOP-UPDATES.md) for first launch and in-app updates; [MAC-SETUP.md](MAC-SETUP.md) remains available for developers running from source.

**Meta Muse / weekly automation:** open **History & Agent Jobs** and follow [MUSE-SETUP.md](MUSE-SETUP.md). A dedicated ZenWave-style file exchange accepts weekly jobs, preserves dated production slots, returns finished media and checksums, and records external publication acknowledgements. Muse handles the separately authorized platform scheduling/posting.

## Open the studio

Double-click **Start Content Studio.cmd**, then use **http://127.0.0.1:5057**. Keep the launcher window open while working. Close it or press Ctrl+C to stop the server.

This computer is already set up. On a fresh Windows computer, install Python 3.11+ and Node.js 20.19+ or 22.12+, copy this entire folder including `assets`, and double-click **Setup Content Studio.cmd** once. Then use the start launcher. The setup script installs the bundled FFmpeg package; a separate FFmpeg installation is unnecessary.

## Make a video

1. Choose a topic, deck, one or three cards, target length, voice, and writing mode.
2. Click **Shuffle & write**. Every shuffle creates a new saved reading.
3. Edit the video title, hook, each card's interpretation, and closing. Use the orientation selectors or individual redraw buttons to change a card. A redraw replaces only that card's script and preserves edits elsewhere.
4. Click **Prepare preview**, then **Play**. Scrub through the reading, listen to narration, and optionally show safe guides. Preview frames and exported frames use the same composition function and saved timeline. The browser preview updates at approximately six frames per second; the exported MP4 is 30 fps.
5. Click **Export video**. The studio saves the draft before starting. Download the MP4 or the complete posting bundle when the export finishes.
6. Upload the MP4 in TikTok or Facebook. Use the included cover and posting text if desired. Posting is manual; the studio does not publish to social accounts.

Use **Library** to search, reopen, edit, and download earlier readings. Refreshing or restarting the app preserves saved work and completed exports. Unsaved script edits are marked, and the browser warns before closing a dirty draft.

## Daily readings

1. Open **Daily readings** and choose Tarot, Western astrology, Chinese astrology, Numerology, or Combined. Combined lets you select any two, three, or all four systems.
2. Choose the date and **Morning · 6 AM** or **Evening · 6 PM**. America/Denver is the default, including daylight saving changes. Morning scripts suggest intentions and actions; evening scripts invite reflection and release. These are collective readings, so no question or birth details are required.
3. Choose Esoteric Minimal or Storybook Cartoon, a voice, writing mode, and length. Tarot artwork can be selected independently. The collection below the form previews all 12 Western signs, 12 Chinese zodiac animals, and numerology cards 1–9, 11, 22, and 33 in each style: **72 new cards** total.
4. Optionally select **Include current events**, then **Review date & sources**. Review calculated facts and choose up to three timestamped headlines. BBC World and UN News are public RSS sources; when unavailable, no news claims are added. A future edition cannot know future news. Historical RSS archives are not provided.
5. Click **Generate morning/evening reading**. Edit the script, prepare the spoken preview, and export as usual. Rewriting keeps the same cards and saved context. Calculated astrology and numerology cards follow the date; only tarot cards can be redrawn. Create a new edition to change the date or systems.

Western sky facts use Astronomy Engine's tropical, geocentric Sun/Moon/planet positions at the edition time, lunar illumination, phase, and major aspects within a 3° orb. Chinese calendar facts use lunar-python: the annual zodiac changes at Chinese New Year, and the daily stem–branch uses the local calendar date with midnight rollover. This is collective calendar symbolism rather than a personal BaZi chart. Numerology adds every Gregorian date digit and repeatedly reduces the result while preserving 11, 22, and 33. These calculations supply consistent facts; the interpretations are for entertainment and reflection.

Each date/edition/type has a reproducible initial tarot draw. Saved edits remain authoritative. Context snapshots preserve the original date calculations and source timestamps, so a later rewrite or export does not silently fetch different facts.

## Daily planner

Open **Daily planner** to choose a morning and evening reading type and production settings. The next seven days show separate 6 AM and 6 PM targets in America/Denver. **Prepare** creates the reading and its full video/posting bundle in the background. Repeated clicks on a slot reuse that edition; failures require **Retry**. Completed slots open their saved readings.

**Automatically prepare editions** is off initially. Enable it and save to prepare each local edition 30 minutes before its target. Keep the studio running and the computer awake. Past missed targets are not automatically backfilled. Preparing future dates manually uses the facts available at preparation time; review news again near publication if needed. Claimed slots keep their own settings snapshot even when the planner defaults change.

This phase prepares local content. It does **not** connect to or publish on Facebook; a Page does not exist yet. Posting at 6 AM and 6 PM on Facebook will need a later publishing integration and Page authorization. No access tokens or Facebook login are needed to use this studio.

Changing the deck or spread requires a new shuffle. Changing voice, target length, writing mode, or topic can be saved on the current draw. Choose **Rewrite with these same cards** to generate a fresh script for that saved topic and writing mode. Saving alone preserves the approved script.

## Voices and writing

- **Built-in writing** uses individually authored card meanings and varied openings/closings. It is free and works offline. Use OpenAI writing for a reading tailored to a specific topic, or edit the built-in script yourself.
- **Windows voice** uses an installed English Windows voice and real word timing events. No API calls or credits are needed.
- **macOS voice** uses the Mac's built-in `say` command. Card transitions follow measured section audio durations; word timing inside each section is estimated and labeled in the preview. No API calls or credits are needed. Fresh Mac installations default to this voice in both the editor and planner.
- **OpenAI writing / Coral / Nova** use `OPENAI_API_KEY` from the environment or a local `.env`. This computer's existing environment connection is detected automatically. Optional model overrides are shown in `.env.example`. Do not commit keys.
- OpenAI narration creates one speech recording, then uses transcription word timestamps for caption alignment. These operations incur API usage. Audio is reused when exporting the same content again.
- **Captions only** creates a silent video with a timed script.

The duration presets are 30, 45, 60, and 90 seconds. The renderer adjusts speech within a comfortable range. If a long edited script cannot fit clearly, it extends the video and shows the actual duration and an explanation instead of cutting off words. Short scripts can finish before the preset ends; the final card remains on screen. All narration is disclosed in the video footer as synthetic narration.

## Files and persistence

`data/studio.sqlite3` stores readings and export jobs. `data/prepared/` stores cached audio and caption timelines. Each export gets its own folder under `exports/<export-id>/`:

- `reading.mp4`: 1080 × 1920 portrait, H.264, yuv420p, 30 fps, AAC audio, fast-start MP4, burned-in captions.
- `cover.jpg`: portrait cover image.
- `subtitles.srt`: timed captions, also available separately for editing.
- `caption.txt`: suggested posting text.
- `reading.json`: exact approved cards, orientations, settings, script, and revision.
- `timeline.json`: section and caption timing.
- `context.json` and `sources.txt`: daily editions also include the saved date/sky/calendar/news snapshot and references used in the reading.
- `posting-bundle.zip`: all the export files together.

The original random seed records the initial draw. The saved card list and script are authoritative after manual edits or redraws. An export takes an immutable snapshot, so later draft edits cannot alter a completed video. Re-exporting unchanged content reuses the same narration and timing.

If a server restart interrupts a render, it is marked failed and can be started again. Saved readings and completed exports remain available. The studio is bound to this computer's loopback interface and rejects remote requests and untrusted mutation requests.

## Development and checks

```powershell
./.venv/Scripts/python.exe -m unittest discover -s tests -v
cd frontend
npm run build
```

Run the production app with `./.venv/Scripts/python.exe app.py`. For frontend development, run the Python server and `npm run dev` inside `frontend`; Vite proxies local API and asset requests to port 5057.

On macOS, use `.venv/bin/python` in place of the Windows Python path. Run `python scripts/doctor.py` to verify all bundled assets and native FFmpeg, and `python scripts/smoke-test.py` for a real video export/decode test without OpenAI calls. GitHub Actions verifies both Windows and Intel macOS 15.

This folder has its own Git repository, separate from the original live website and parent Playground folder. Source, dependency lockfiles, launchers, tests, and all artwork belong in Git. Local databases, exports, credentials, virtual environments, and installed dependencies stay ignored. A clone starts a new local library; see the Mac guide to transfer existing saved work separately.

The app uses React/Vite for the editor, Flask/Waitress for its local API, SQLite for persistence, Pillow for a shared preview/video composition, and FFmpeg for encoding. All 234 tarot card images are bundled under `assets/cards`, with 72 daily visual cards under `assets/daily`. The catalog and tarot rules were copied from the original project, with card-specific Minor Arcana meanings added here. No runtime imports depend on the live website or its folders.

Daily artwork source atlases, prompts, and extraction coordinates are preserved under `assets/daily`. Rebuild the individual card files and collection sheets with `./.venv/Scripts/python.exe scripts/build-daily-cards.py`.

The safe guides are a composition aid rather than a guarantee for every social interface. Check the final video in the destination app before posting.
