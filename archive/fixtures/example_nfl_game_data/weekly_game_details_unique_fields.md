# `weekly_game_details.json` — Unique Fields Reference

Data present in the NFL weekly game details endpoint that is **not** available in the
scheduled games / box score / game center / play list endpoints
(`2025_week_1_games.json`).

Based on Week 1, 2025 data (16 games).

---

## 1. `summary`

Game state snapshot at final whistle (or live during game). 16 keys at top level.

- [ ] `gameId` — `str` — Game UUID
- [ ] `phase` — `str` — enum: `FINAL` (likely also `PREGAME`, `INGAME` during live)
- [ ] `quarter` — `str` — enum: `END_OF_GAME` (likely also `1`, `2`, `3`, `4`, `OT` during live)
- [ ] `clock` — `str` — Game clock in `MM:SS` format
- [ ] `down` — `int` — Current/final down (1–4)
- [ ] `distance` — `int` — Yards to first down/goal (7–14 observed)
- [ ] `yardLine` — `str` — Field position, format `TEAM NN` or `50`
- [ ] `isGoalToGo` — `bool`
- [ ] `isRedZone` — `bool`
- [ ] `attendance` — `int` — Stadium attendance (47,627–83,253 observed)
- [ ] `weather` — `str | null` — Free text: `"Rain Temp: 75° F, Humidity: 66%, Wind: S 11 mph"` (null for domed stadiums)
- [ ] `startTime` — `str` — ISO 8601 datetime of actual kickoff
- [ ] `gameBookUrl` — `str` — URL to official game book PDF: `https://static.www.nfl.com/image/upload/v.../gamecenter/{gameId}.pdf`
- [ ] `offset` — `int` — Timezone offset in minutes (438–680 observed)

### `summary.awayTeam` / `summary.homeTeam`

- [ ] `teamId` — `str` — Team UUID
- [ ] `hasPossession` — `bool` — Which team had possession at end of game / currently

#### `summary.*.score`

- [ ] `q1` — `int` — 1st quarter points
- [ ] `q2` — `int` — 2nd quarter points
- [ ] `q3` — `int` — 3rd quarter points
- [ ] `q4` — `int` — 4th quarter points
- [ ] `ot` — `int` — Overtime points
- [ ] `total` — `int` — Total points

#### `summary.*.timeouts`

- [ ] `remaining` — `int` — Timeouts remaining (0–3)
- [ ] `used` — `int` — Timeouts used (0–4, can exceed 3 due to challenges)

---

## 2. `driveChart`

Drive-level game data. Contains drives, individual plays, and scoring summaries.

### Top-level fields

- [ ] `gameId` — `str` — Game UUID
- [ ] `offset` — `int` — Timezone offset in minutes

### `driveChart.drives[]` (25 fields per drive, ~16–28 drives per game)

- [ ] `sequence` — `int` — Drive number within the game (1-based)
- [ ] `teamId` — `str` — Possessing team UUID
- [ ] `startedDescription` — `str` — enum: `Blocked FG`, `Downs`, `Fumble`, `Interception`, `Kickoff`, `Missed FG`, `Muffed Punt`, `Punt`
- [ ] `startedClock` — `str` — Game clock at drive start (`MM:SS`)
- [ ] `startedQuarter` — `int` — Quarter drive started (1–4)
- [ ] `startedYardLine` — `str | null` — Starting field position (`TEAM NN` or `50`)
- [ ] `startedPlayId` — `int` — Play ID of first play in drive
- [ ] `startedPlaySequenceNumber` — `float` — Sequence number of first play
- [ ] `startedTime` — `str` — ISO 8601 real-world timestamp of drive start
- [ ] `endedDescription` — `str` — enum: `Blocked FG`, `Downs`, `End of Game`, `End of Half`, `Field Goal`, `Fumble`, `Interception`, `Missed FG`, `Punt`, `Touchdown`
- [ ] `endedClock` — `str` — Game clock at drive end (`MM:SS`)
- [ ] `endedQuarter` — `int` — Quarter drive ended (1–4)
- [ ] `endedYardLine` — `str | null` — Ending field position
- [ ] `endedPlayId` — `int` — Play ID of last play in drive
- [ ] `endedPlaySequenceNumber` — `float` — Sequence number of last play
- [ ] `endedTime` — `str | null` — ISO 8601 real-world timestamp of drive end (null ~47% of the time)
- [ ] `endedWithScore` — `bool` — Whether this drive ended with points scored
- [ ] `totalEndedWithScore` — `bool` — Whether scoring occurred (including PAT)
- [ ] `plays` — `int` — Number of plays in drive (0–18)
- [ ] `firstDowns` — `int` — First downs gained on drive (0–8)
- [ ] `yardsGained` — `int` — Total yards gained (-25 to 95)
- [ ] `yardsGainedByPenalty` — `int` — Yards from penalties (-32 to 42)
- [ ] `yardsGainedNet` — `int` — Net yards gained (-25 to 95)
- [ ] `timeOfPossession` — `str` — Drive duration (`M:SS` format)
- [ ] `inside20` — `bool` — Whether drive reached opponent's 20-yard line

### `driveChart.scoringSummaries[]` (10 fields, ~8 per game)

- [ ] `sequence` — `int` — Scoring play number within the game (1-based)
- [ ] `scoreType` — `str` — enum: `FIELD_GOAL`, `TOUCHDOWN`
- [ ] `scoringPlayId` — `int` — Play ID of the scoring play
- [ ] `patPlayId` — `int` — Play ID of the PAT attempt (0 for field goals)
- [ ] `quarter` — `int` — Quarter (1–4)
- [ ] `clockTime` — `str` — Game clock at time of score (`MM:SS`)
- [ ] `scoringTeamId` — `str` — Scoring team UUID
- [ ] `awayScore` — `int` — Running away team score after this play
- [ ] `homeScore` — `int` — Running home team score after this play
- [ ] `playDescription` — `str` — Full scoring description, e.g. `"J.Williams 1 yd. run (B.Aubrey kick) (6-53, 3:11)"`

### `driveChart.plays[]` — unique fields not in `play_list`

The plays array has 28 fields total. These are the fields that have **no equivalent**
in `2025_week_1_games.json`'s `play_list`:

- [ ] `playStartTime` — `str | null` — ISO 8601 real-world wall-clock time play started
- [ ] `playEndTime` — `str | null` — ISO 8601 real-world wall-clock time play ended
- [ ] `playDescriptionWithJerseyNumbers` — `str | null` — Play description with jersey numbers prepended to player names, e.g. `"(Shotgun) 23-C.McCaffrey left guard to SF 23 for 4 yards (20-J.Love)."`
- [ ] `prePlayByPlay` — `str | null` — Compact pre-snap context string, e.g. `"ARI 1-10 ARI 17"`
- [ ] `driveSequence` — `int` — Which drive this play belongs to (0 = non-drive plays)
- [ ] `drivePlayCount` — `int` — Number of plays in the parent drive
- [ ] `driveNetYards` — `int` — Net yards of the parent drive
- [ ] `driveTimeOfPossession` — `str | null` — Parent drive time of possession (`M:SS`)
- [ ] `nextPlayType` — `str` — enum: `FREE_KICK`, `PLAY_FROM_SCRIMMAGE`, `UNSPECIFIED`, `XP_KICK`
- [ ] `nextPlayIsGoalToGo` — `bool`
- [ ] `playIsEndOfQuarter` — `bool`
- [ ] `playScored` — `bool`
- [ ] `playDeleted` — `bool` — Whether the play was nullified
- [ ] `scoringPlayType` — `str` — enum: `FIELD_GOAL`, `PAT`, `PAT2`, `TOUCHDOWN`, `UNSPECIFIED`
- [ ] `scoringTeamId` — `str | null` — UUID of scoring team (null on non-scoring plays)
- [ ] `specialTeamsPlayType` — `str` — enum: `PENALTY`, `UNSPECIFIED`

#### `driveChart.plays[].stats[]` — unique fields not in `play_list.play_stats`

Both endpoints have per-player stat arrays, but these fields are unique to driveChart:

- [ ] `playStatId` — `str` — Unique UUID for this stat entry
- [ ] `personId` — `str | null` — Player UUID (NFL smart ID)
- [ ] `gsisPlayerJerseyNumber` — `str | null` — Jersey number as zero-padded string (`"04"`, `"99"`)

### `driveChart.plays[]` — shared play-level fields (for reference only)

These fields overlap with `play_list` (different names, same data). **Not** unique:

| driveChart field | play_list equivalent |
|---|---|
| `playId` | `play_id` |
| `playSequenceNumber` | `sequence` |
| `playType` | `play_type` |
| `quarter` | `quarter` |
| `clockTime` | `start_game_clock` |
| `down` | `down` |
| `yardsRemaining` | `yards_to_go` |
| `yardsGained` | `yards_gained` |
| `yardLine` | `yard_line_side` + `yard_line_number` |
| `playIsGoalToGo` | `is_goal_to_go` (inferred) |
| `playDescription` | `play_description_with_jersey_numbers` |

---

## 3. `replays[]`

Video replay asset metadata. Typically 3–5 replays per game.

### Meaningful fields

- [ ] `type` — `str` — enum: `video`
- [ ] `subType` — `str` — enum: `All-22`, `Condensed Game`, `Full Game`, `Full Game - Alternative Broadcasts`, `Full Game - Spanish`
- [ ] `cameraSource` — `str | null` — enum: `Combined` (only for `All-22` subType, null otherwise)
- [ ] `title` — `str` — Display title, e.g. `"Dallas Cowboys at Philadelphia Eagles"`
- [ ] `description` — `str` — Matchup description with venue and date
- [ ] `duration` — `str` — Duration in seconds as string, e.g. `"6810"`
- [ ] `externalId` — `str` — Base64-like content ID, e.g. `"r2Ya55c6WjCy0rwqnSAn9w"`
- [ ] `mcpPlaybackId` — `str` — MCP playback ID as numeric string, e.g. `"2272906"`
- [ ] `publishDate` — `str` — ISO 8601 datetime when replay was published
- [ ] `originalAirDate` — `str | null` — ISO 8601 datetime of original broadcast
- [ ] `expirationDate` — `str | null` — ISO 8601 datetime, typically ~10 years out
- [ ] `preRollDisabled` — `bool` — Always `false` in sample
- [ ] `thumbnail.thumbnailUrl` — `str` — CDN URL (Akamai-hosted JPEG)

#### `replays[].authorizations`

- [ ] `nfl_plus_premium` — `list[dict]` — Authorization requirements, structure: `[{"NFL_PLUS - REPLAYS": {"requirements": {"countryCode": ["US"]}}}]`
- [ ] `nfl_plus_plus` — `list[dict]` — Same structure as above

#### `replays[].ids`

- [ ] `awayTeamId` — `str` — Away team UUID
- [ ] `gameId` — `str` — Game UUID
- [ ] `homeTeamId` — `str` — Home team UUID
- [ ] `playId` — `null` — Always null

#### `replays[].tags[]`

Tags are polymorphic — some reference players, some reference teams, some reference the game:

**Player tags:**
- [ ] `title` — `str` — Player display name
- [ ] `slug` — `str` — URL slug, e.g. `"saquon-barkley"`
- [ ] `personId` — `str` — Player UUID

**Team tags:**
- [ ] `title` — `str` — Team nickname, e.g. `"Eagles"`
- [ ] `slug` — `str` — URL slug, e.g. `"eagles"`
- [ ] `teamId` — `str` — Team UUID

**Game tags:**
- [ ] `gameId` — `str` — Game UUID
- [ ] `season` — `str` — e.g. `"2025"`
- [ ] `seasonType` — `str` — enum: `""` (empty), `REG`
- [ ] `week` — `str` — e.g. `"1"` or `""` (empty)

### Always-null fields (included for completeness)

These are present in the response but always `null` or empty across all 16 games:

`id`, `advertiserId`, `author`, `clipType`, `ctaLink`, `ctaTarget`, `ctaText`,
`displayTitle`, `endDate`, `entitlement`, `episodeNumber`, `fantasyLink`,
`hostNetwork`, `intendedAudience`, `introEnd`, `language`, `lastUpdated`,
`mobileLink`, `mobileTitle`, `outroStart`, `promoLink`, `promoText`,
`radioStation`, `series`, `seriesSeason`, `seriesTitle`, `slug`, `startDate`,
`summary`, `webLink`

Always-empty lists: `ctas`, `images`, `playIds`, `promoAssets`, `videos`

Always-empty dict: `background`

---

## 4. `awayTeamStandings` / `homeTeamStandings`

Full team standings at the time of the game. Identical structure for both.

### Top-level

- [ ] `team.id` — `str` — Team UUID
- [ ] `team.currentLogo` — `str` — Logo URL template: `https://static.www.nfl.com/{formatInstructions}/league/api/clubs/logos/{ABBR}`
- [ ] `team.fullName` — `str` — e.g. `"Dallas Cowboys"`

### `clinched`

- [ ] `bye` — `bool`
- [ ] `division` — `bool`
- [ ] `eliminated` — `bool`
- [ ] `homeField` — `bool`
- [ ] `playoff` — `bool`
- [ ] `wildCard` — `bool`

### Record objects

All record types share the base fields `wins`, `losses`, `ties` (all `int`), `winPct` (`float`),
and `points` (`{for: int, against: int}`).

**`closeGames`** — base fields only:
- [ ] `closeGames` (wins, losses, ties, winPct, points)

**`conference`** — base + rank:
- [ ] `conference` (wins, losses, ties, winPct, points)
- [ ] `conference.rank` — `int` — 1–16

**`division`** — base + rank:
- [ ] `division` (wins, losses, ties, winPct, points)
- [ ] `division.rank` — `int` — 1–4

**`home`** — base fields only:
- [ ] `home` (wins, losses, ties, winPct, points)

**`road`** — base fields only:
- [ ] `road` (wins, losses, ties, winPct, points)

**`last5`** — base fields only:
- [ ] `last5` (wins, losses, ties, winPct, points)

**`overall`** — base + streak:
- [ ] `overall` (games, wins, losses, ties, winPct, points)
- [ ] `overall.streak.type` — `str` — enum: `STREAK_TYPE_LOSING`, `STREAK_TYPE_WINNING`
- [ ] `overall.streak.length` — `int`

---

## 5. `currentLogo` on team objects

Present in three locations (same data):

- [ ] `game[].homeTeam.currentLogo` — `str`
- [ ] `game[].awayTeam.currentLogo` — `str`
- [ ] `awayTeamStandings.team.currentLogo` / `homeTeamStandings.team.currentLogo` — `str`

URL template: `https://static.www.nfl.com/{formatInstructions}/league/api/clubs/logos/{ABBR}`

All 32 team abbreviations: ARI, ATL, BAL, BUF, CAR, CHI, CIN, CLE, DAL, DEN, DET, GB,
HOU, IND, JAX, KC, LA, LAC, LV, MIA, MIN, NE, NO, NYG, NYJ, PHI, PIT, SEA, SF, TB, TEN, WAS

---

## 6. `taggedVideos`

- [ ] `taggedVideos` — Always `null` across all 16 games in this dataset. May be populated in other weeks/contexts.

---

## `statType` Code Reference

The `driveChart.plays[].stats[].statType` field uses numeric codes. 77 distinct codes
observed, listed by frequency:

| Code | Frequency | Code | Frequency | Code | Frequency |
|------|-----------|------|-----------|------|-----------|
| 79 | 1178 | 115 | 995 | 82 | 878 |
| 10 | 807 | 113 | 680 | 111 | 679 |
| 15 | 641 | 21 | 641 | 112 | 356 |
| 14 | 341 | 4 | 340 | 22 | 283 |
| 19 | 274 | 110 | 262 | 20 | 241 |
| 25 | 168 | 23 | 133 | 42 | 98 |
| 44 | 97 | 43 | 90 | 45 | 85 |
| 83 | 83 | 26 | 79 | 3 | 74 |
| 5 | 62 | 71 | 59 | 29 | 59 |
| 84 | 54 | 39 | 52 | 7 | 50 |
| 40 | 48 | 30 | 47 | 70 | 45 |
| 120 | 45 | 104 | 44 | 9 | 38 |
| 6 | 37 | 78 | 35 | 85 | 33 |
| 41 | 33 | 8 | 33 | 77 | 32 |
| 76 | 32 | 37 | 30 | 105 | 30 |
| 38 | 29 | 72 | 23 | 106 | 22 |
| 11 | 22 | 16 | 21 | 80 | 19 |
| 33 | 18 | 49 | 17 | 73 | 16 |
| 32 | 16 | 68 | 15 | 69 | 15 |
| 55 | 14 | 93 | 13 | 88 | 12 |
| 52 | 12 | 57 | 11 | 54 | 10 |
| 51 | 10 | 53 | 9 | 91 | 8 |
| 63 | 6 | 95 | 5 | 59 | 5 |
| 402 | 4 | 427 | 3 | 426 | 3 |
| 424 | 3 | 422 | 2 | 421 | 2 |
| 410 | 2 | 403 | 2 |
