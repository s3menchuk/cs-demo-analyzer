# CS2 Demo Lab

A local CS2 `.dem` analyzer with Rust parsing through demoparser2, a Python/FastAPI API, SQLite storage, and a Russian-language browser interface with no frontend build step.

## Getting started

Windows, Python 3.11–3.14:

```powershell
.\start.ps1
```

If PowerShell restricts script execution, start the application manually:

```powershell
python -m venv .venv
python -m pip --python .venv\Scripts\python.exe install -r requirements.txt
.venv\Scripts\python -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Open http://127.0.0.1:8000. Click "Open sample match" or upload an unpacked `.dem` file. Sample data is explicitly marked as synthetic. API documentation: http://127.0.0.1:8000/docs.

## Features

- CS2 header validation, a 1 GB upload limit, a queue of up to three jobs, and a separate parser process.
- Completed rounds excluding warmup, kills, assists, deaths, and opening duels.
- K/D, ADR, HS%, KAST, player sorting, and a damage comparison chart.
- Position sampling rate selected at upload: 1, 8, 16, 32, or 64 snapshots per second (default: 16). Playback follows demo time, with optional smooth interpolation, navigation to kills, and player/side filters.
- Heatmap of living players for the selected round. Intensity is normalized within the current filter.
- Automatic overhead maps showing passages, walls, and cover: Mirage, Dust2, Inferno, Nuke, Ancient, Anubis, Overpass, Train, and Vertigo. Radar images and calibration are bundled locally; viewing requires no external service. Floor selection is available for Nuke, Train, and Vertigo.
- A "Kills by round" chart in individual analysis: all rounds, including rounds with zero kills, accounting for the player's side. Click to select a round for detailed analysis; click again to return to the entire match. The chart remains complete when a single round is selected and counts kills even when coordinates are missing.
- A "Player analysis" tab: common kill positions, death locations, ranked zones with event counts and shares, weapon statistics, and round/side filters. Also accessible by clicking a player in the scoreboard.
- Two duel visualization modes: frequency in cells of 128/256/512 game units and individual event points. Kills are green; deaths are red. Click a zone to see its events; click an event to open the corresponding round.
- Calibrated custom PNG/JPG radar images remain available for other maps and historical versions. Without a suitable radar image, a clearly labeled X/Y grid is displayed.
- SQLite match library, confirmed deletion from the library or match card, full-model JSON export, and CSV statistics export. Matches being processed cannot be deleted (HTTP 409).

## Architecture

### Importing recent FACEIT matches

In "Recent FACEIT matches", paste a profile URL such as `https://www.faceit.com/ru/players/nickname` (or just the nickname), select the latest 5/10/20 CS2 matches, and click "Find matches". Select demos and click "Download and analyze". Matches without an available demo include an explanation; when a match has multiple demos, each can be selected separately. Downloading, gzip/zstd decompression, and analysis run on the server through the shared queue of up to three jobs. Progress is displayed in the upload panel. Importing the same demo again uses the existing record; failed imports can be retried. The sampling rate comes from the general upload setting.

This requires **two FACEIT credentials**: a server-side Data API key for profile and match history lookup, and a separate token with Downloads API permission for signed demo URLs. Automatic import does not work without them; the application displays its connection status. A Data API key alone does not grant download access.

Set the environment variables in PowerShell before starting the application (the values below are placeholders):

```powershell
$env:FACEIT_API_KEY = 'YOUR_SERVER_SIDE_DATA_API_KEY'
$env:FACEIT_DOWNLOAD_TOKEN = 'YOUR_DOWNLOADS_API_ACCESS_TOKEN'
.\start.ps1
```

Credentials are not sent to the browser or saved in the database; the browser only receives flags indicating whether the connection is configured. The download token is sent only to the FACEIT API, not to the file host. Restart the server after changing the environment. The presence of environment variables confirms configuration; only requests to FACEIT can validate the credentials.

Official instructions: [API keys](https://docs.faceit.com/getting-started/authentication/api-keys/), [Data API](https://docs.faceit.com/api/data/), and [obtaining Downloads API access](https://docs.faceit.com/getting-started/Guides/download-api/). Downloads API access must be requested separately from FACEIT. Demo availability is determined by FACEIT; a match appearing in history does not guarantee that its recording can be downloaded. Import does not use browser cookies or a FACEIT password.

Application API: `GET /api/faceit/config`, `GET /api/faceit/matches?profile=...&limit=5`, and `POST /api/faceit/import` with `match_id`, `demo_index` (zero-based), and `sample_rate`. Compressed archives are supported for FACEIT imports; regular uploads currently accept only unpacked `.dem` files.

`app/parser.py` extracts headers, round boundaries, events, and position snapshots. `app/analytics.py` calculates metrics independently of the parser. `app/main.py` receives upload streams, submits parsing to ProcessPoolExecutor, and serves the API. `app/storage.py` saves summaries and compressed JSON in SQLite. `static/` contains the interface and Canvas visualization.

`app/player_analysis.py` aggregates individual player events and spatial zones. `static/map-view.js` applies the same game-coordinate transformation to playback and analysis. `GET /api/maps` returns the map catalog; `GET /api/matches/{id}/players/{player_id}/analysis` accepts `round_number`, `side=CT|T`, and `cell_size` (64–1024).

The uploaded `.dem` is deleted after processing; results remain in `data/matches.sqlite3`. Set the data directory using the `CS2_DATA_DIR` environment variable. Jobs interrupted by a restart are marked as failed; upload the file again to retry.

Matches in the old format (before `schema_version=2`) lack event identifiers and coordinates. Re-upload them to use individual player maps; the interface explicitly indicates this requirement. Existing results are preserved. The sample match is updated when "Open sample match" is clicked.

## Grenades, view direction, and deletion

"Positions" mode includes "Player view direction", "Grenades", and "Flight trail" toggles. The arrow shows the horizontal view angle (`yaw`), not movement direction or a verified line of sight through walls. Exports also retain `pitch`. When smoothing is enabled, yaw is interpolated along the shortest angle across the ±180° boundary.

Grenades come from `parse_grenades(grenades=False)`: only airborne projectiles, excluding inventory grenades and other items. Flight is sampled at the selected position interval; the start and end are also retained. Reuse of an entity number does not merge separate throws. The trail shows only the path already traveled during the last 1.5 seconds. The "Grenades and effects" list allows navigation to the activation time.

Smoke and fire use the centers and time intervals from `smokegrenade_detonate/expired` and `inferno_startburn/expire`; decoys use `decoy_started/detonate`. If the ending event is missing, the interval is limited to the round and marked `end_confirmed=false`. HE and flash grenades display a brief activation marker (0.8 seconds), not the duration of damage or blindness. Smoke and fire areas are **approximate circles**, not the exact shape of volumetric smoke, fire spread, or damage. Layers respect the selected floor, player (the thrower), and that player's side in the round.

The newer `schema_version=3` format stores angles in snapshots, trajectories in `grenades`, and effects in `utility_effects`. Older matches remain available; re-upload the original `.dem` to use the new layers. The sample match is updated by clicking its button.

Rename a demo using the ✎ button in the library or "Rename" on the match card. The name (1–240 characters) is saved in SQLite and displayed in the library and card without reparsing or interrupting playback. Leading and trailing whitespace is removed; empty names and control characters are rejected. API: `PATCH /api/matches/{id}` with JSON `{"name":"New name"}`. Renaming is also available during processing; statistics and positions are preserved.

Delete a match using the × button in the library or "Delete" on the card. After confirmation, `DELETE /api/matches/{id}` atomically removes statistics, positions, grenades, and analysis from the local database. It returns 409 for queued/parsing matches and 404 for unknown IDs. Other matches and the original file in the user's folder are unaffected. Restore a deleted match by uploading its demo again.

## Timers, C4, and gunfire

The remaining freeze/round time, C4 countdown, and plant/defuse progress are displayed above the map. The round timer uses `m_iRoundTime`, `round_start_time`, `game_time`, and pause flags from the game rules. It is not the time until the recorded `round_end`: it represents the in-game time limit. After `decision_tick`, the round is considered finished; once C4 is planted, bomb status replaces the old time limit. Pausing stops countdown interpolation. If clock fields are missing, the value remains unknown (—).

Bombsites A/B are marked using coordinates from the map overview. The site name for an event is determined by the nearest landmark on the appropriate floor; the original numeric `site` is retained in `raw_site`. This matters because `site` in events may be an entity ID rather than 0/1. The C4 position is the planting player's coordinates from `bomb_planted`, not extracted geometry of the bomb object. Plant/defuse starts and cancellations, defuse kit availability, defusal, and explosion are handled as separate events; the "Bomb" list allows navigation to them.

For the C4 countdown, a recorded explosion in the same round takes priority, followed by the server's `mp_c4timer`. If the value was not recorded, a consistent measurement from explosions in other rounds is used and marked **≈**. If no such measurement is available, the user can enter an assumed duration (initially 40 seconds), also marked **≈**. When clock fields are available, time is calculated using the game clock. The C4 countdown stops after defusal or the end of the round. Defuse progress uses 5 seconds with a kit and 10 seconds without one.

Gunfire is stored as individual `weapon_fire` events with the exact tick, shooter position, yaw/pitch, and weapon, independently of the snapshot rate. Grenade throws, knives, and C4 are excluded. A marker and short ray are visible for 0.16 game seconds; they indicate shot direction, **not a simulation of the bullet**, spread, penetration, or hits. The layer respects player, side, and floor filters. Expand the "Shots" list to navigate to each event. Exports include `shots`, `bomb_events`, and `bombs`; frames include `clock`. The newer format has `schema_version=4`. Previously saved demos must be re-uploaded to obtain these data.

## Position sampling and playback

Before uploading a file, select "Position sampling rate at upload". Available rates are 1, 8, 16, 32, and 64 snapshots per second; the default is 16 (a 62.5 ms interval). A rate of 64 saves every CS2 tick. Higher rates increase processing time, memory use, and result size. The API accepts `POST /api/upload?name=match.dem&sample_rate=16`; other values are rejected with HTTP 422. The selected rate is stored in `sample_rate`, the interval in `sample_seconds`, and the rate is displayed below the round map.

The setting applies to new uploads. To increase the rate of an existing match, upload its `.dem` again: source files are deleted after processing, and missing positions cannot be reconstructed exactly. Older results and the sample match with a one-second interval retain a rate of 1 Hz.

Playback uses demo ticks and real elapsed time (`requestAnimationFrame`), so 1× corresponds to one game second at any snapshot rate. The timeline moves in one-tick increments; the time display includes milliseconds. Smoothing linearly interpolates coordinates between snapshots and can be disabled using "Smooth movement". This estimates intermediate movement rather than adding recorded data. Changes in life state or side, large position/height jumps, and recording gaps are not interpolated. Seeking with the timeline, navigating to kill/grenade/C4/shot events, or selecting another round preserves playback state: a playing replay continues from the new position, while a paused replay stays paused. Rendering temporarily stops while a round loads without changing the selected state; pausing during loading is respected. Playback speed is preserved. Playback pauses when the tab is hidden.

## Kill and death maps

Coordinates come from `player_death`: kill maps use `attacker_X/Y/Z`, while death maps use `user_X/Y/Z`. Movement snapshots are **not used** for this purpose, regardless of the selected sampling rate. Team kills and suicides are excluded from the kill map; the death map includes all deaths of the selected player. If coordinates are missing, the event contributes to the count but not to the spatial map; coordinate coverage is shown below the map.

Frequency is calculated using cells on a fixed world-coordinate grid with a separate floor key. Negative coordinates are rounded down. The count is the number of events in a cell; the share is the percentage of events of the corresponding type with available coordinates across the entire selected period and side (all floors combined). Intensity is normalized to the maximum of the current layers. A cell describes an area, and its boundary may cross a wall; it does not determine traversability.

Bundled radars are a snapshot of CS2 assets from [cs2-map-icons](https://github.com/MurkyYT/cs2-map-icons); sources and licensing are listed in [ATTRIBUTION.md](static/maps/ATTRIBUTION.md). Older demos may have different geometry from the current radar. `scripts/fetch_maps.py` downloads a pinned revision of the images and parameters; to update them, change `REVISION` and run the script. Calibration uses a 1024 px base; images scale together with player positions. When vertical sections are available, the floor is selected by Z; an unknown Z is treated as the main floor.

## Methodology and limitations

**ADR**: total damage dealt to opponents / rounds participated in; damage is capped at the victim's remaining health (100 HP at the start of a round). Self-damage and team damage are excluded from the numerator. Modes with health regeneration are not supported.

**KAST**: the percentage of rounds with a kill, assist, survival, or a teammate trading the player's death within 5 seconds. Participation is determined from snapshots and events. Mid-round connections, disconnections, and bots may affect survival estimates. Bots without SteamIDs are distinguished by name.

**HS%**: headshot kills / opponent kills. **K/D**: kills / max(deaths, 1). **Entry**: the first opponent kill in a round.

Wins are displayed by **CT/T side**, not by team. Side switches do not distort individual metrics: side membership is checked for each event. Kills during the delay after the winner is announced belong to the previous round, until `round_officially_ended` or the next `round_start`. Round duration includes freeze time and this delay. Snapshots are stored at the selected 1/8/16/32/64 Hz rate with 64 ticks per second; subtick precision, economy, bullet trajectories, and full 3D playback are outside the scope of this version. Incomplete rounds are excluded. Parsing expects a GOTV demo of a standard CS2 match; old CS:GO demos, archives, and some POV recordings are unsupported.

The parser processes one file at a time. In newer results, snapshots are compressed and stored separately for each round: requesting a round does not decompress positions for the rest of the match. Older records with a single payload remain supported without rebuilding; reading them decompresses the original full payload. Full JSON export combines all rounds and can be large at high sampling rates. This is a local application for individual use, without authentication or a multi-user mode. By default, the server listens only on localhost.

## Checks

```powershell
python -m pip --python .venv\Scripts\python.exe install -r requirements-dev.txt
.venv\Scripts\python -m pytest -q
node --check static/app.js
node --check static/player-analysis.js
node tests/test_map_view.cjs
node tests/test_replay.cjs
node tests/test_overlays.cjs
node tests/test_round_state.cjs
node tests/test_playback.cjs
```

Integration test with a real file:

```powershell
$env:CS2_TEST_DEMO = 'C:\path\match.dem'
.venv\Scripts\python -m pytest tests/test_parser.py -q
```

The application uses the [demoparser2](https://github.com/LaihoE/demoparser) API and its [Python documentation](https://github.com/LaihoE/demoparser/tree/main/documentation/python). For testing, use the public `src/parser/test_demo.dem` file from that repository; binary demo files are not included in the application's source tree.


The first round is classified as a knife round solely by its weapon inventory: only knives must remain in living players' inventories and among all weapon entities on the map. Passive equipment (armor, helmet, defuse kit) is not considered a weapon; firearms, grenades, and C4 rule out a knife round. Every frame of the active round phase is checked, from the end of freeze time until the winner is announced. Kills, falls, and the number of dead players are not used. Weapons after the winner is announced do not affect the result. Incomplete data produces an "unknown" result, and the round remains visible with an explanation. Older records without this check must be re-uploaded: the kill-based heuristic is no longer used.

Weapon entities are checked using a local scanner based on [demoinfocs-golang v5.2.0](https://github.com/markus-wa/demoinfocs-golang/tree/v5.2.0), with source code in `tools/weapon-scan`. Go 1.26+ is required: `start.ps1` builds `bin/weapon-scan.exe` if it is missing. To build manually from `tools/weapon-scan`, run `go build -o ../../bin/weapon-scan.exe .`; to test, run `go test ./...`. The initial build requires internet access and Go; the compiled scanner works locally. Without the scanner, the main analysis remains available, but automatic knife-round hiding is disabled.

The "Show knife round" checkbox restores a hidden round. Knife rounds are always labeled "Knife" without a number; regular rounds are always numbered from 1 regardless of whether the knife round is visible. Original identifiers and stored data remain unchanged. `include_knife=true` is supported by the match, individual analysis, and export APIs. New uploads save overall statistics both with and without the knife round.

In round history, select a player in "Player sides": CT/T strips show that player's actual side, and a dashed line marks a switch. The kills chart uses the analyzed player's side. Switches are determined from snapshots, including overtime; each individual history cell still uses the winning side's color.

Round history and the kills chart distinguish regulation halves (1–12 and 13–24) and MR3 overtime sets: OT 1 — 25–27 / 28–30, OT 2 — 31–33 / 34–36, and so on. Half and overtime-set boundaries are shown even if the player's side stays the same. In the API and JSON, the knife round has `display_number: null` and `is_knife: true`; the original `number` remains the navigation identifier.


### Multiple matches and map summaries

Select multiple `.dem` files in the file dialog or drag them in together. Files are submitted sequentially; when the three-job queue is full, the application waits for a slot. Progress and errors are displayed for each file. "Do not upload remaining files" cancels files that have not yet been submitted; files already sent continue to be analyzed.

Each file has a progress bar: during upload, it shows the percentage of bytes transferred; during analysis, it shows the current stage and progress based on completed stages. The value may remain unchanged during a long stage; it is not an estimate of remaining time. Progress updates every 1.5 seconds, and current jobs reappear after refreshing the page. Progress reaches 100% after results have been saved.

The library automatically groups demos by the map in each record's metadata. Click a map name in the library or open "Map summaries": statistics are calculated immediately across all completed demos for each map, without selecting individual files. Newly completed demos automatically join their group and update the open summary. Expand "Demos" within a group to open an individual match; a SteamID player filter is available for the entire group. Each map has its own statistics, player table, match list, and K−D heatmap. The knife-round toggle applies to the selected matches in the same way as in individual analysis. Repeating an ID cannot count the same record twice; separate uploaded records are treated as separate matches. Groups are created automatically from the local library each time the summary is opened; filters apply within the current tab.

In individual analysis, select "K−D balance". Each cell contains the number of kills from that position minus the number of deaths there: positive values are green, negative values red, and observed zeros gray. The grid uses common world coordinates with separate floors. Events lacking exact coordinates are not replaced with snapshots; coverage is shown below the map. Cell size controls the level of aggregation. Color intensity is symmetric around zero and normalized within the selected floor.

Aggregate K/D = total kills / max(total deaths, 1); ADR = total damage / total rounds participated in; HS% = total headshot kills / total kills. For all players, ADR uses the sum of their participated rounds; for a selected player, it uses only that player's rounds. Individual match percentages and ratios are not averaged. Warnings accompany statistics from older records and limitations on excluding knife rounds. API: `POST /api/analysis/maps` with `match_ids`, optional `player_id`, `cell_size`, and `include_knife`.

Automatic summary: `GET /api/analysis/maps`, with optional `map_name`, `player_id`, `cell_size`, and `include_knife`. Synthetic records are excluded from the overall summary by default; their group remains available in the library. `POST /api/analysis/maps` remains available for an arbitrary selection of records.
