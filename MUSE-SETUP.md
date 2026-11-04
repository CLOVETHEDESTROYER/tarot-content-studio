# Meta Muse and the Tarot content studio

**Studio v3:** choose Separate reading series for independent Western astrology, Chinese astrology and numerology videos on each day. The default is 21 videos per week (morning); both editions produce 42. Requests use `readingTypes: ["western", "chinese", "numerology"]` with `editions: ["morning"]` or both editions. Existing morningType/eveningType requests still work. Prepare the exchange again to refresh its catalog and agent instructions. See [UNIFIED-STUDIO.md](UNIFIED-STUDIO.md).

Open http://127.0.0.1:5057 and choose **History & Agent Jobs**. This implements the same local-file handoff used by ZenWave's History & Agent Jobs section, with a separate Tarot exchange and date-based production history.

## Responsibilities

| Component | Responsibility |
|---|---|
| Tarot studio | Calculate each day's sky/calendar/numerology, draw and save cards, write scripts, render videos, preserve generation history, and return checksummed media |
| Exchange folder | Carry JSON requests, status, completed media, and external posting reports through authorized local access or a verified synced storage folder |
| Meta Muse | Request the week, retrieve completed assets, schedule/post through its authorized target Page, and report the actual returned platform IDs/times |

Muse can keep its own daily records. The studio also reserves each production **date + morning/evening + timezone** in SQLite, so a forgotten conversation or repeated request cannot silently redraw that slot. This differs from ZenWave's creative-combination identity: the same tarot card appearing on another date is valid.

## Set up the handoff

1. Use **Prepare exchange** with a dedicated Tarot folder. The default is `data/exchange` on this computer. If Muse uses your existing Google Drive connection, choose a **separate Tarot Exchange folder alongside ZenWave's exchange**, with the necessary write/read/video retrieval access. Keep the SQLite database on one authoritative rendering computer; do not sync a live database.
2. Keep ZenWave's selected folder and schedules unchanged. The Tarot app rejects exchange metadata belonging to another studio before overwriting it.
3. Enable **Watch inbox** while the studio and rendering computer stay awake. It resumes on app startup if left enabled. Pause inbox watching before changing folders. Pausing stops new inbox ingestion; already accepted batches finish.
4. Use **Copy Muse connection prompt** and paste it into the intended Muse conversation. The prompt includes the selected local path but tells Muse to use its authorized local/storage route. A Windows/Mac path is not a cloud filesystem path.
5. Have Muse read the instructions/catalog and perform the provided connection test: submit `Examples/first-test.json` atomically into `Requests/first-test.json`, wait for complete, retrieve the video, verify checksums, and replay it unchanged. **Run connection test** in the studio verifies local production; only Muse actually retrieving the file verifies the external connection.

The connection test is one 30-second silent video. It never claims a production day and cannot accept publication reports. Preparing the folder does not submit it automatically.

```text
Tarot Exchange/
  AGENT-INSTRUCTIONS.md
  catalog.json
  studio-info.json
  Examples/first-test.json
  Requests/                 complete input JSON files
  Status/                   atomic status replies; complete is the ready signal
  Ready/request-id/          media, request.json, ready.json
  Ready/request-id.zip       complete batch package
  Reports/                  actual external scheduling/publication acknowledgements
```

## Voice and writing direction (3.1)

For new production requests, use `"writer": "openai"`, `"voice": "openai-marin"`, `"voice_style": "engaging"`, and `"voice_energy": "expressive"`. For livelier delivery try `"uplifting"` and `"high"`; for evenings try `"reflective"`. Cedar and Coral are useful alternatives. All thirteen available voices are listed in the refreshed catalog. Preview voices in the studio before requesting a week. OpenAI writing and narration use the studio computer's configured key and API credits.

Daily scripts use the selected posting date, not the day Muse happens to request them. Saved facts and cards stay attached to the edition. New AI scripts enforce section word limits and check the opening date; an invalid script gets one editorial revision and otherwise fails for review. Existing drafts need Rewrite and a new preview/export to adopt the new content and voice direction. Replays reuse accepted output; never modify the payload under an accepted request ID.

## Generate the week

The weekly form defaults to seven days and both editions: **14 readings**, at **06:00 and 18:00 America/Denver**. Choose an explicit first day, morning/evening reading type, visual style, tarot artwork, voice, and writer. The request ID defaults to `tarot-week-YYYY-MM-DD`. Use a stable ID for one exact request; change it for a genuinely different brief/window. Existing production slots are reused when settings match; conflicting settings fail rather than overwrite an edition.

For Muse automation, the documented `reading-week` schema is in [resources/AgentInstructions.md](resources/AgentInstructions.md), copied into the exchange as `AGENT-INSTRUCTIONS.md`. Supported types are tarot, western, chinese, numerology, and combined. Combined can select any two or more systems through its request `components`. The range is one to seven days, with morning, evening, or both. The worker renders sequentially, so a 14-video batch does not overload the normal render queue.

Each edition stores its actual calendar date, target time and UTC offset, calculated context, draw, script, and immutable export revision. Daylight saving changes are handled per date. Weekly generation omits news by default: future headlines cannot be known in advance. Use a one-day request near publication for news-based content; multi-day requests with news are rejected.

## Scheduling and daily history

`ready.json` includes asset IDs, media paths relative to the exchange, SHA-256 checksums, date/edition, and `proposedPublishAt`. Those times are proposals, not confirmed social schedules. Muse needs separate access to the intended Facebook Page and a working upload/schedule flow. This app does not log into Muse/Facebook, publish videos, create a Muse recurring task, or independently verify platform publication.

After an authorized platform action returns a real post ID, Muse writes a report into `Reports`. See the exact schema in the agent instructions. The studio accepts only known production assets from completed batches, rejects changed report IDs, and records later transitions under new event IDs. History labels these results **externally reported**. A local acceptance receipt confirms recording, not independent verification by Facebook.

Use the same asset/post IDs to reconcile uncertain uploads in Muse and on the platform before retrying. Studio generation idempotency cannot itself prevent a separate third-party upload from being repeated.

The weekly recurring task's generation day/time and target Page still need to be selected in Muse through its actual available controls. Do not change an existing ZenWave task as part of Tarot setup.

## Replays and recovery

- The same request ID and normalized payload returns its saved result, even after media is moved. Different parameters with that ID are an error.
- A different request ID for already generated production slots reuses the original videos. Different settings for a claimed slot are rejected.
- Deleting a video does not erase generation history and does not cause automatic regeneration. Restore the saved export/handoff rather than rerendering it as new content.
- Failed/interrupted requests retain completed editions. Use **Resume** after reviewing the error; completed exports are reused. Replaying an input file alone does not retry a failed job.
- Restarting marks unfinished batches interrupted. No partial batch is advertised as ready. Muse must require whole-request status complete before retrieving/posting assets.
- Original manual reading variants remain in **Library**. Agent production slots and test assets are tracked separately; the first connection test does not appear as a production day.

## Local verification

Run `python -m unittest discover -s tests -v` using the installed virtual environment. Tests cover calendar/DST slots, folder isolation, request/report idempotency, changed payloads, canonical slot reuse/conflicts, checksums, restart recovery, missing media, and rejection of posting test assets. Browser QA also exercises a real 14-video week in an isolated workspace. That proves the local handoff, not Muse's account access or Facebook publishing.
