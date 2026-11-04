# One StarPower studio

Version 3 combines Live Studio, the original card library and longer spreads, daily readings, video exports, Muse jobs and desktop updates in one app. The public website can still run independently.

## Live readings

The original approval queue, cooldown, cadence, pause/resume, saved starter, presenter, three decks, narration retries, animated card reveals, captions and broadcast-link reset are included. Choose Tarot, Western astrology, Chinese astrology, Numerology or Combined. Leave Reading date blank for today in America/Denver, or select a date. Date-based readings use the same calculations and illustrated cards as Daily readings. They are collective readings focused on a viewer's question, not personal natal or BaZi charts.

Save settings before adding requests. Each accepted request keeps its selected type and date; changing the session selection does not rewrite waiting requests. A manual request can override the type. Chat commands: `!tarot`, `!western` / `!astrology`, `!chinese`, `!numerology`, `!combined`, and `!reading` (the session type). Approval and cooldown apply across all types.

Completed live readings appear in Library for editing and video export. Card library & spreads includes the deck browser, explanations/narrated snippets, one/three cards, cross, relationship and Celtic cross. Starting a session does not start TikTok; actual chat delivery requires the selected account to be LIVE.

## Host and broadcast

Local desktop use requires no second login and retains session CSRF protection. To require the original password login, configure `LIVE_REQUIRE_LOGIN=1`, `LIVE_USERNAME`, `LIVE_PASSWORD_HASH` and `LIVE_SESSION_SECRET` in the shared local environment. Never commit credentials.

Open broadcast view shows the 1080 x 1920 scene for OBS capture. A separate read-only service runs on the studio port plus 100 (normally 5157). An HTTPS tunnel for TikTok Link sources must target this service, never the editor server. Only the broadcast scene, approved public state, narration and allowed artwork are served. Host controls and Muse endpoints are excluded. No tunnel is published automatically.

For an existing HTTPS tunnel, change its target to the new read-only address, set `LIVE_BROADCAST_URL` to its HTTPS origin in the local environment, and restart. Copy a fresh broadcast link; previous tickets are not migrated. Reset broadcast link revokes existing tickets. The local service address appears under Broadcast setup.

On this Windows workspace, first launch imports the previous sibling project's live database if no unified live database exists. A consistent copy preserves the original, returns interrupted work to the queue and leaves the session stopped for review. New Mac installations do not import another computer's data. History, live state and broadcast credentials remain outside the installed app.

## Separate daily series for Muse

History & Agent Jobs defaults to Separate reading series: Western, Chinese and numerology, once each morning. Seven days produce 21 videos; both daily times produce 42. The original one-morning/one-evening layout remains available.

Requests can include `readingTypes: ["western", "chinese", "numerology"]` with `editions: ["morning"]` or both editions. Existing schemaVersion 1 requests remain supported. Each date, edition, timezone and reading type has its own reservation. Replays reuse exports; different settings for an occupied type are rejected. Multi-series files use distinct date-edition-type folders, and assets include `readingType`. The catalog advertises this capability and a maximum of 70 assets.

Prepare the Tarot exchange again so Muse receives the updated instructions and catalog. Keep Zenwave's exchange unchanged. Muse handles separately authorized social scheduling/posting; the studio does not publish.

## Updates

End Live before updating or closing. Installation waits for running live sessions, batches and exports, retains the previous app and preserves current history. See DESKTOP-UPDATES.md for installation, private GitHub access and Mac first launch.
