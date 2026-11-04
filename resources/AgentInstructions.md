# StarPower Tarot local content exchange — schema 1

## Separate reading series (studio v3)

For one Western, one Chinese and one numerology reading each day, include `readingTypes: ["western", "chinese", "numerology"]` and `editions: ["morning"]` in a normal reading-week request. Seven days return 21 videos; both editions return 42. The list applies to each selected edition. Omit readingTypes to retain morningType/eveningType behavior. Each date/edition/timezone/type is reserved independently. Use the returned file paths and checksums; multi-series folders include the type and assets include readingType. Never submit separate changed-settings requests to overwrite a reserved type. Refresh catalog.json and verify its checksum before relying on this capability.

Use this dedicated Tarot exchange separately from ZenWave. Do not change ZenWave's folder, requests, schedules, permissions, or database. A storage connector must actually be able to write request JSON and retrieve finished videos. Browser access alone does not establish access to local files.

The operator uses Content Studio → History & Agent Jobs → Prepare exchange. Watch inbox enables local processing while the studio and computer stay awake. It resumes when the studio restarts if left enabled. You may use separately authorized local-folder access or a verified Drive-synced folder; the studio does not create a Drive connection, public endpoint, Muse login, or Facebook connection.

## First connection test

1. Read studio-info.json, catalog.json, and these instructions. Verify catalogSHA256 before using catalog choices.
2. Check Status/first-test.json. If complete, retrieve and verify its existing result. Do not create a replacement test or post it.
3. For a first test, atomically copy Examples/first-test.json into Requests/first-test.json (write a .tmp then rename). This creates one 30-second silent test video. Examples are not submitted automatically.
4. Wait for Status/first-test.json status complete. Retrieve Ready/first-test/ready.json and the files it lists, or Ready/first-test.zip. Verify each file's SHA-256.
5. Re-submit exactly the same request. It returns the same assets without rendering again. A changed payload with the same ID is rejected; a separate .error.json receipt preserves the valid completed status.
6. Connection-test assets have publicationAllowed false. Never post or schedule them.

## Weekly production

Write Requests/requestId.json with schemaVersion 1, kind reading-week, a stable requestId, the original brief, and an explicit startDate. IDs use 1–80 ASCII letters/numbers/underscores/hyphens, starting with a letter or number; Windows device names are reserved. Filename and requestId must match.

```json
{
  "schemaVersion": 1,
  "kind": "reading-week",
  "requestId": "tarot-week-2026-11-09",
  "brief": "Create a week of collective morning intentions and evening reflections.",
  "startDate": "2026-11-09",
  "days": 7,
  "editions": ["morning", "evening"],
  "timezone": "America/Denver",
  "morningType": "combined",
  "eveningType": "tarot",
  "style": "esoteric-minimal",
  "deck": "esoteric-minimal",
  "voice": "macos",
  "writer": "local",
  "components": ["tarot", "western", "chinese", "numerology"],
  "includeNews": false,
  "campaign": "daily-perspective",
  "requestedBy": "Meta Muse"
}
```

Use catalog.defaultVoice for the rendering computer: macos on a Mac, windows on Windows. Captions-only uses silent. For richer scripts and directed narration, use writer "openai", voice "openai-marin" (or any catalog OpenAI voice), voice_style "engaging", and voice_energy "expressive". "uplifting" with "high" gives a more enthusiastic delivery; "reflective" suits evening editions. These require the operator's existing local OpenAI configuration and use API credits. Never put API keys into requests. Voice styles/energies are optional; omitted values default to engaging/expressive. Do not add new fields to an already accepted request ID.

Supported types: tarot, western, chinese, numerology, combined. Combined uses any two or more of the catalog components. Choose one to seven days, morning/evening/both, and the planner's timezone (America/Denver by default). Maximum 14 assets. The proposed morning slot is 06:00, evening is 18:00, with the correct offset for each calendar day. Duration may be a catalog preset; omitted durations are 90 seconds for combined, 45 for numerology, and 60 otherwise. style, deck, writer, voice, campaign, requestedBy are optional; defaults are recorded when the request is accepted. Keep the same explicit parameters when replaying an ID.

Advance batches cannot know future headlines. includeNews must be false for a multi-day batch. A one-day request may enable news near its posting day. Do not infer or fabricate future events.

## Replays, recovery, and ready output

One request ID identifies one immutable normalized brief/settings payload. Identical replays reuse the saved request even after files are moved; changed parameters need a new ID. A completed request does not silently regenerate missing media. Ask the operator to restore missing outputs if necessary.

Production editions share the daily planner's atomic date/edition/timezone reservation. A new request for the same saved slot/settings reuses the video. A request trying different settings for an already claimed slot fails rather than replacing it. Manual editor variants can exist separately; these are not new agent slots. The same tarot card may naturally recur on different dates.

Failed/interrupted requests retain their completed editions and need explicit Resume in the studio. A replay alone does not retry them. Resuming reuses completed exports and retries only unfinished slots. Failed requests may contain partial files; do not post those files or treat them as a complete batch.

Only consume a batch after Status/requestId.json says complete. Ready/requestId/ready.json lists immutable asset IDs, reading/revision, date/edition/timezone, proposedPublishAt, and each media file's relative path, checksum, and byte size. Resolve paths relative to THIS exchange root, including in cloud storage. Require publicationAllowed true for production. Ready/requestId.zip packages the complete handoff. A proposed time is not a confirmed social schedule.

The private SQLite database stays on one authoritative rendering computer, outside the exchange and Git. Do not edit it, sync a live copy between machines, or move a batch's exchange folder while it is active. Files and history remain distinct: removing a file does not remove its generated-day reservation.

## Scheduling and publication reports

Muse performs platform actions through its own separately authorized account/Page access. This studio never posts or schedules a social video. Confirm the intended Facebook Page and its actual upload/scheduling capability before relying on recurring production. Do not use tokens, passwords, shell commands, URLs to fetch media, or SQL in requests.

After the platform returns a REAL post ID, atomically write Reports/report-id.json:

```json
{
  "id": "facebook-real-post-scheduled",
  "assetId": "export ID from ready.json",
  "platform": "facebook",
  "accountId": "actual Facebook Page ID",
  "postId": "actual returned platform post ID",
  "status": "scheduled",
  "scheduledAt": "2026-11-09T06:00:00-07:00",
  "url": "https://www.facebook.com/actual-post"
}
```

Supported platforms are facebook/instagram; report scheduled, published, or failed. scheduled requires scheduledAt with an explicit offset; publishedAt may record the actual publication time. Each later transition uses a new report ID. Identical reports are idempotent; changing an existing report ID is rejected. The asset must be a production asset from a completed batch. Reports/report-id.result.json confirms LOCAL acceptance or rejection. These are external acknowledgements, not independent platform verification. The studio does not fetch analytics, verify Page permissions, create Muse recurring tasks, or independently confirm publication.

Before retrying any uncertain upload, inspect the platform and Muse's own records using the same stable asset/post IDs. Local generation idempotency does not prove that a separate platform upload cannot be duplicated.
