import logging
from datetime import datetime
from typing import Dict, List, Optional

from django.db import transaction

from archive.models import (
    Drive,
    ExtraPointsBoxscore,
    FieldGoalsBoxscore,
    FumblesBoxscore,
    Game,
    GameReplay,
    KickingBoxscore,
    League,
    PassingBoxscore,
    Play,
    PlayStat,
    PuntingBoxscore,
    QuarterScore,
    ReceivingBoxscore,
    ReturnBoxscore,
    RushingBoxscore,
    Season,
    TacklesBoxscore,
    Team,
    TeamStandingsSnapshot,
    Venue,
)

logger = logging.getLogger(__name__)

# -------------------------
# Boxscore field mappings
# API camelCase key → Django model field name
# -------------------------

_PASSING_FIELDS = {
    "attempts": "attempts",
    "completions": "completions",
    "completionPct": "completion_pct",
    "yards": "yards",
    "yardsPerAttempt": "yards_per_attempt",
    "touchdowns": "touchdowns",
    "interceptions": "interceptions",
    "sacks": "sacks",
    "lostSackedYards": "sack_yards",
    "qbRating": "qb_rating",
    "longestPassCompletion": "longest_pass",
    "longestTdPass": "longest_td_pass",
}

_RUSHING_FIELDS = {
    "attempts": "attempts",
    "yards": "yards",
    "avgYards": "avg_yards",
    "touchdowns": "touchdowns",
    "longestRush": "longest_rush",
    "longestTdRush": "longest_td_rush",
}

_RECEIVING_FIELDS = {
    "receptions": "receptions",
    "yards": "yards",
    "avgYards": "avg_yards",
    "touchdowns": "touchdowns",
    "passTarget": "targets",
    "longestPassReception": "longest_reception",
    "longestTdReception": "longest_td_reception",
    "yardsAfterCatch": "yards_after_catch",
}

_TACKLES_FIELDS = {
    "count": "tackles",
    "assists": "assists",
    "sacks": "sacks",
    "sackYards": "sack_yards",
    "qbHits": "qb_hits",
    "tacklesForLoss": "tackles_for_loss",
    "tacklesforLossYards": "tackles_for_loss_yards",
    "safeties": "safeties",
    "specialTeamsTackles": "special_teams_tackles",
    "specialTeamsAssists": "special_teams_assists",
    "specialTeamsBlocks": "special_teams_blocks",
}

_FUMBLES_FIELDS = {
    "fumbles": "fumbles",
    "ownFumbleRecoveries": "own_recoveries",
    "ownFumbleRecoveryYards": "own_recovery_yards",
    "ownFumbleRecoveryTds": "own_recovery_tds",
    "opponentFumbleRecoveries": "opp_recoveries",
    "opponentFumbleRecoveryYards": "opp_recovery_yards",
    "opponentFumbleRecoveryTds": "opp_recovery_tds",
    "forcedFumbles": "forced_fumbles",
    "fumbleOutOfBounds": "out_of_bounds",
}

_FIELD_GOALS_FIELDS = {
    "attempts": "attempts",
    "successCnt": "made",
    "blockedCnt": "blocked",
    "yards": "yards",
    "avgYard": "avg_yards",
    "longestMadeFieldGoal": "longest",
}

_EXTRA_POINTS_FIELDS = {
    "attemptCnt": "attempts",
    "successCnt": "made",
    "blockedCnt": "blocked",
}

_KICKING_FIELDS = {
    "count": "kickoffs",
    "yards": "yards",
    "touchbackCnt": "touchbacks",
    "inside20Cnt": "inside_20",
    "outOfBoundsCnt": "out_of_bounds",
    "toEndzoneCnt": "to_endzone",
    "returnYards": "return_yards",
}

_PUNTING_FIELDS = {
    "attempts": "attempts",
    "yards": "yards",
    "grossAvgPuntLength": "gross_avg",
    "netPuntingAvg": "net_avg",
    "blockedCnt": "blocked",
    "longestPunt": "longest",
    "touchbackCnts": "touchbacks",
    "inside20Cnt": "inside_20",
    "returnYards": "return_yards",
}

_RETURN_FIELDS = {
    "count": "returns",
    "yards": "yards",
    "avgYards": "avg_yards",
    "touchdowns": "touchdowns",
    "longestReturn": "longest",
    "longestTdReturn": "longest_td",
    "fairCatches": "fair_catches",
}

# Maps boxscore attribute name → (Django model class, field mapping dict)
# Note: kick_return and punt_return both map to ReturnBoxscore
BOXSCORE_CATEGORY_MAP = {
    "passing": (PassingBoxscore, _PASSING_FIELDS),
    "rushing": (RushingBoxscore, _RUSHING_FIELDS),
    "receiving": (ReceivingBoxscore, _RECEIVING_FIELDS),
    "tackles": (TacklesBoxscore, _TACKLES_FIELDS),
    "fumbles": (FumblesBoxscore, _FUMBLES_FIELDS),
    "field_goals": (FieldGoalsBoxscore, _FIELD_GOALS_FIELDS),
    "extra_points": (ExtraPointsBoxscore, _EXTRA_POINTS_FIELDS),
    "kicking": (KickingBoxscore, _KICKING_FIELDS),
    "punting": (PuntingBoxscore, _PUNTING_FIELDS),
    "kick_return": (ReturnBoxscore, _RETURN_FIELDS),
    "punt_return": (ReturnBoxscore, _RETURN_FIELDS),
}

_STREAK_TYPE_MAP = {
    "STREAK_TYPE_WINNING": "W",
    "STREAK_TYPE_LOSING": "L",
    "STREAK_TYPE_TYING": "T",
    "W": "W",
    "L": "L",
    "T": "T",
}


class NFLDataIngestor:
    """Stores NFL game data from the GriddyNFL SDK into Django models."""

    def __init__(self, league: League, season: Season):
        self.league = league
        self.season = season
        self._build_team_lookups()

    def _build_team_lookups(self):
        nfl_teams = (
            Team.objects.filter(affiliations__org_unit__league=self.league)
            .distinct()
            .iterator()
        )
        self._team_by_abbr: Dict[str, Team] = {}
        self._team_by_smart_id: Dict[str, Team] = {}
        self._team_by_nfl_id: Dict[str, Team] = {}

        for t in nfl_teams:
            if t.short_name:
                self._team_by_abbr[t.short_name] = t
            nfl_ids = (t.external_ids or {}).get("nfl.com", {})
            if "smartId" in nfl_ids:
                self._team_by_smart_id[nfl_ids["smartId"]] = t
            if "teamId" in nfl_ids:
                self._team_by_nfl_id[str(nfl_ids["teamId"])] = t

    def _resolve_team(
        self,
        abbr: Optional[str] = None,
        smart_id: Optional[str] = None,
        nfl_id: Optional[str] = None,
    ) -> Optional[Team]:
        if smart_id and smart_id in self._team_by_smart_id:
            return self._team_by_smart_id[smart_id]
        if abbr and abbr in self._team_by_abbr:
            return self._team_by_abbr[abbr]
        if nfl_id and str(nfl_id) in self._team_by_nfl_id:
            return self._team_by_nfl_id[str(nfl_id)]
        if abbr or smart_id or nfl_id:
            logger.warning(
                "Could not resolve team: abbr=%s, smart_id=%s, nfl_id=%s",
                abbr,
                smart_id,
                nfl_id,
            )
        return None

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def ingest_week(self, week_data: Dict, week: int) -> List[Game]:
        """Store all games from gather_all_data_for_week(as_json=False) output."""
        games = []
        for game_id, game_data in week_data.items():
            try:
                with transaction.atomic():
                    game = self._ingest_game(game_id, game_data, week)
                    games.append(game)
                logger.info("Ingested game %s successfully", game_id)
            except Exception:
                logger.exception("Failed to ingest game %s", game_id)
        logger.info(
            "Ingested %d / %d games for week %d", len(games), len(week_data), week
        )
        return games

    # ------------------------------------------------------------------
    # Per-game orchestrator
    # ------------------------------------------------------------------

    def _ingest_game(self, game_id: str, data: Dict, week: int) -> Game:
        scheduled_game = data.get("scheduled_games")
        sked_details = data.get("sked_game_dtls")
        wgd = data.get("weekly_game_details", {})
        box_score = data.get("box_score")
        play_list = data.get("play_list")
        game_center = data.get("game_center")

        game = self._store_game_record(
            game_id, scheduled_game, sked_details, game_center
        )

        if sked_details and hasattr(sked_details, "score") and sked_details.score:
            self._store_quarter_scores(game, sked_details)

        if wgd:
            for side_key in ("home_team_standings", "away_team_standings"):
                standings = wgd.get(side_key)
                if standings:
                    self._store_standings(standings, week)

            drive_chart = wgd.get("drive_chart")
            if drive_chart and hasattr(drive_chart, "drives") and drive_chart.drives:
                self._store_drives(game, drive_chart.drives)

            replays = wgd.get("replays")
            if replays:
                self._store_replays(game, replays)

        if play_list:
            self._store_plays(game, play_list)

        if box_score:
            self._store_boxscore(game, box_score)

        return game

    # ------------------------------------------------------------------
    # Game record
    # ------------------------------------------------------------------

    def _store_game_record(self, game_id, scheduled_game, sked_details, game_center):
        # Resolve teams
        home_team = None
        away_team = None

        if scheduled_game:
            if hasattr(scheduled_game, "home_team") and scheduled_game.home_team:
                home_team = self._resolve_team(
                    smart_id=getattr(scheduled_game.home_team, "team_id", None)
                )
            if hasattr(scheduled_game, "away_team") and scheduled_game.away_team:
                away_team = self._resolve_team(
                    smart_id=getattr(scheduled_game.away_team, "team_id", None)
                )

        # Fallback to sked_details abbreviations
        if not home_team and sked_details:
            home_team = self._resolve_team(
                abbr=getattr(sked_details, "home_team_abbr", None)
            )
        if not away_team and sked_details:
            away_team = self._resolve_team(
                abbr=getattr(sked_details, "visitor_team_abbr", None)
            )

        if not home_team or not away_team:
            raise ValueError(
                f"Cannot resolve teams for game {game_id}: "
                f"home={home_team}, away={away_team}"
            )

        # Determine date
        date_local = None
        if scheduled_game and hasattr(scheduled_game, "date_"):
            date_local = scheduled_game.date_

        if not date_local:
            raise ValueError(f"Cannot determine date for game {game_id}")

        # Build defaults for update_or_create
        defaults = {
            "game_type": "REG",
        }

        if scheduled_game:
            defaults["week"] = getattr(scheduled_game, "week", None)
            defaults["kickoff_utc"] = getattr(scheduled_game, "time", None)
            defaults["status"] = getattr(scheduled_game, "status", "") or ""
            defaults["neutral_site"] = getattr(scheduled_game, "neutral_site", False)

            # Venue
            venue_data = getattr(scheduled_game, "venue", None)
            if venue_data:
                venue_name = getattr(venue_data, "name", None)
                if venue_name:
                    venue = Venue.objects.filter(name=venue_name).first()
                    if venue:
                        defaults["venue"] = venue

            # Season type → game_type mapping
            season_type = getattr(scheduled_game, "season_type", None)
            if season_type == "POST":
                defaults["game_type"] = "POST"

            # External IDs from scheduled_games
            ext_ids = {}
            ext_id_list = getattr(scheduled_game, "external_ids", None)
            if ext_id_list:
                for eid in ext_id_list:
                    source = getattr(eid, "source", None)
                    id_val = getattr(eid, "id", None)
                    if source and id_val:
                        ext_ids[source] = id_val
            ext_ids["nfl_game_id"] = game_id
            defaults["external_ids"] = ext_ids

        if sked_details:
            defaults["broadcast_channel"] = (
                getattr(sked_details, "network_channel", "") or ""
            )

            # External IDs from sked_details
            ext_ids = defaults.get("external_ids", {})
            smart_id = getattr(sked_details, "smart_id", None)
            if smart_id:
                ext_ids["smart_id"] = smart_id
            game_key = getattr(sked_details, "game_key", None)
            if game_key:
                ext_ids["game_key"] = game_key
            pro_game_id = getattr(sked_details, "game_id", None)
            if pro_game_id:
                ext_ids["pro_game_id"] = str(pro_game_id)
            defaults["external_ids"] = ext_ids

            # Scores
            score = getattr(sked_details, "score", None)
            if score:
                home_ts = getattr(score, "home_team_score", None)
                away_ts = getattr(score, "visitor_team_score", None)
                if home_ts and hasattr(home_ts, "point_total"):
                    defaults["final_home_score"] = home_ts.point_total
                if away_ts and hasattr(away_ts, "point_total"):
                    defaults["final_away_score"] = away_ts.point_total
                # Overtime
                if home_ts and getattr(home_ts, "point_ot", 0):
                    defaults["overtime_periods"] = 1
                elif away_ts and getattr(away_ts, "point_ot", 0):
                    defaults["overtime_periods"] = 1

                # Override status from score phase
                phase = getattr(score, "phase", None)
                if phase:
                    defaults["status"] = phase

            # NFL-specific bonus data
            bonus = {}
            ngs_game = getattr(sked_details, "ngs_game", None)
            if ngs_game is not None:
                bonus["ngs_game"] = ngs_game
            released = getattr(sked_details, "released_to_clubs", None)
            if released is not None:
                bonus["released_to_clubs"] = released

            if game_center:
                try:
                    bonus["game_center"] = game_center.model_dump()
                except Exception:
                    pass

            if bonus:
                defaults["bonus_data"] = bonus

        game, created = Game.objects.update_or_create(
            league=self.league,
            season=self.season,
            date_local=date_local,
            home_team=home_team,
            away_team=away_team,
            defaults=defaults,
        )
        action = "Created" if created else "Updated"
        logger.debug("%s game %s (pk=%d)", action, game_id, game.pk)
        return game

    # ------------------------------------------------------------------
    # Quarter scores
    # ------------------------------------------------------------------

    def _store_quarter_scores(self, game: Game, sked_details):
        score = sked_details.score
        QuarterScore.objects.filter(game=game).delete()

        rows = []
        for team, team_score in [
            (game.home_team, getattr(score, "home_team_score", None)),
            (game.away_team, getattr(score, "visitor_team_score", None)),
        ]:
            if not team_score:
                continue
            for period, attr in [
                (1, "point_q1"),
                (2, "point_q2"),
                (3, "point_q3"),
                (4, "point_q4"),
            ]:
                pts = getattr(team_score, attr, None)
                if pts is not None:
                    rows.append(
                        QuarterScore(game=game, team=team, period=period, points=pts)
                    )
            # OT — only create if points > 0
            ot_pts = getattr(team_score, "point_ot", 0) or 0
            if ot_pts > 0:
                rows.append(QuarterScore(game=game, team=team, period=5, points=ot_pts))

        if rows:
            QuarterScore.objects.bulk_create(rows)
            logger.debug(
                "Created %d quarter score rows for game %d", len(rows), game.pk
            )

    # ------------------------------------------------------------------
    # Standings
    # ------------------------------------------------------------------

    def _store_standings(self, standings, week: int):
        team_obj = getattr(standings, "team", None)
        if not team_obj:
            return
        team_id = getattr(team_obj, "id", None)
        team = self._resolve_team(smart_id=team_id)
        if not team:
            logger.warning("Cannot resolve team for standings: %s", team_id)
            return

        overall = getattr(standings, "overall", None)
        conference = getattr(standings, "conference", None)
        division = getattr(standings, "division", None)
        home = getattr(standings, "home", None)
        road = getattr(standings, "road", None)
        clinched = getattr(standings, "clinched", None)

        defaults = {}

        if overall:
            defaults["overall_wins"] = getattr(overall, "wins", 0) or 0
            defaults["overall_losses"] = getattr(overall, "losses", 0) or 0
            defaults["overall_ties"] = getattr(overall, "ties", 0) or 0
            defaults["overall_win_pct"] = getattr(overall, "win_pct", 0.0) or 0.0
            overall_pts = getattr(overall, "points", None)
            if overall_pts:
                defaults["points_for"] = getattr(overall_pts, "for_", 0) or 0
                defaults["points_against"] = getattr(overall_pts, "against", 0) or 0
            streak = getattr(overall, "streak", None)
            if streak:
                defaults["streak_length"] = getattr(streak, "length", 0) or 0
                raw_type = getattr(streak, "type", "") or ""
                defaults["streak_type"] = _STREAK_TYPE_MAP.get(raw_type, raw_type[:1])

        if conference:
            defaults["conference_wins"] = getattr(conference, "wins", 0) or 0
            defaults["conference_losses"] = getattr(conference, "losses", 0) or 0
            defaults["conference_rank"] = getattr(conference, "rank", None)

        if division:
            defaults["division_wins"] = getattr(division, "wins", 0) or 0
            defaults["division_losses"] = getattr(division, "losses", 0) or 0
            defaults["division_rank"] = getattr(division, "rank", None)

        if home:
            defaults["home_wins"] = getattr(home, "wins", 0) or 0
            defaults["home_losses"] = getattr(home, "losses", 0) or 0

        if road:
            defaults["road_wins"] = getattr(road, "wins", 0) or 0
            defaults["road_losses"] = getattr(road, "losses", 0) or 0

        if clinched:
            defaults["clinched_playoff"] = getattr(clinched, "playoff", False)
            defaults["clinched_division"] = getattr(clinched, "division", False)
            defaults["clinched_bye"] = getattr(clinched, "bye", False)
            defaults["eliminated"] = getattr(clinched, "eliminated", False)

        TeamStandingsSnapshot.objects.update_or_create(
            team=team,
            season=self.season,
            week=week,
            defaults=defaults,
        )
        logger.debug("Stored standings for %s week %d", team.short_name, week)

    # ------------------------------------------------------------------
    # Drives
    # ------------------------------------------------------------------

    def _store_drives(self, game: Game, drives):
        Drive.objects.filter(game=game).delete()

        rows = []
        for d in drives:
            team = self._resolve_team(smart_id=getattr(d, "team_id", None))
            rows.append(
                Drive(
                    game=game,
                    sequence=d.sequence,
                    team=team,
                    started_quarter=getattr(d, "started_quarter", None),
                    started_clock=getattr(d, "started_clock", "") or "",
                    started_description=getattr(d, "started_description", "") or "",
                    started_yard_line=getattr(d, "started_yard_line", "") or "",
                    ended_quarter=getattr(d, "ended_quarter", None),
                    ended_clock=getattr(d, "ended_clock", "") or "",
                    ended_description=getattr(d, "ended_description", "") or "",
                    ended_yard_line=getattr(d, "ended_yard_line", "") or "",
                    ended_with_score=getattr(d, "ended_with_score", False),
                    plays_count=getattr(d, "plays", 0) or 0,
                    first_downs=getattr(d, "first_downs", 0) or 0,
                    yards_gained=getattr(d, "yards_gained", 0) or 0,
                    yards_gained_net=getattr(d, "yards_gained_net", 0) or 0,
                    yards_gained_by_penalty=getattr(d, "yards_gained_by_penalty", 0)
                    or 0,
                    time_of_possession=getattr(d, "time_of_possession", "") or "",
                    inside_20=getattr(d, "inside_20", False),
                )
            )

        if rows:
            Drive.objects.bulk_create(rows)
            logger.debug("Created %d drives for game %d", len(rows), game.pk)

    # ------------------------------------------------------------------
    # Plays + PlayStats
    # ------------------------------------------------------------------

    def _store_plays(self, game: Game, play_list):
        # Delete existing (cascades to PlayStat via FK)
        Play.objects.filter(game=game).delete()

        play_rows = []
        play_stat_rows = []  # will be bulk_created after plays

        for p in play_list:
            # Resolve possession team by abbreviation
            poss_abbr = getattr(p, "possession_team", None)
            if poss_abbr == "LA":
                # For some reason, some of the playlists use "LA" as the
                # abbreviation for the LA Rams, _only_ for possession abbr.
                poss_abbr = "LAR"
            poss_team = self._resolve_team(abbr=poss_abbr) if poss_abbr else None

            # Collect NGS data
            ngs_data = {}
            for ngs_attr in ("offense", "defense", "pass_info", "rec_info"):
                val = getattr(p, ngs_attr, None)
                if val is not None:
                    try:
                        ngs_data[ngs_attr] = val.model_dump()
                    except Exception:
                        ngs_data[ngs_attr] = val

            play = Play(
                game=game,
                play_id=getattr(p, "play_id", 0) or 0,
                sequence=getattr(p, "sequence", 0.0) or 0.0,
                quarter=getattr(p, "quarter", None),
                down=getattr(p, "down", None),
                yards_to_go=getattr(p, "yards_to_go", None),
                play_type=getattr(p, "play_type", "") or "",
                play_description=getattr(p, "play_description", "") or "",
                play_state=getattr(p, "play_state", "") or "",
                possession_team=poss_team,
                home_score=getattr(p, "home_score", 0) or 0,
                visitor_score=getattr(p, "visitor_score", 0) or 0,
                yard_line_number=getattr(p, "yard_line_number", None),
                yard_line_side=getattr(p, "yard_line_side", "") or "",
                is_scoring=getattr(p, "is_scoring", False) or False,
                is_big_play=getattr(p, "is_big_play", False) or False,
                is_stp_play=getattr(p, "is_stp_play", False) or False,
                is_marker_play=getattr(p, "is_marker_play", False) or False,
                is_red_zone_play=getattr(p, "is_red_zone_play", None),
                start_game_clock=getattr(p, "start_game_clock", "") or "",
                end_game_clock=getattr(p, "end_game_clock", "") or "",
                ngs_data=ngs_data if ngs_data else None,
            )
            play_rows.append(play)

        # Bulk create plays first to get PKs
        created_plays = Play.objects.bulk_create(play_rows)

        # Now create PlayStat rows
        # Map play_id → Play object for FK assignment
        play_by_play_id = {p.play_id: p for p in created_plays}

        for p in play_list:
            play_stats = getattr(p, "play_stats", None)
            if not play_stats:
                continue

            play_obj = play_by_play_id.get(getattr(p, "play_id", None))
            if not play_obj:
                continue

            for ps in play_stats:
                play_stat_rows.append(
                    PlayStat(
                        play=play_obj,
                        team_abbr=getattr(ps, "club_code", "") or "",
                        player_name=getattr(ps, "player_name", "") or "",
                        gsis_id=getattr(ps, "gsis_id", "") or "",
                        stat_id=getattr(ps, "stat_id", 0) or 0,
                        yards=getattr(ps, "yards", 0) or 0,
                    )
                )

        if play_stat_rows:
            PlayStat.objects.bulk_create(play_stat_rows)

        logger.debug(
            "Created %d plays and %d play stats for game %d",
            len(created_plays),
            len(play_stat_rows),
            game.pk,
        )

    # ------------------------------------------------------------------
    # Boxscore stats
    # ------------------------------------------------------------------

    def _store_boxscore(self, game: Game, box_score):
        # Delete all existing boxscore rows for this game
        for model_cls, _ in BOXSCORE_CATEGORY_MAP.values():
            model_cls.objects.filter(game=game).delete()

        for side, side_label in [("home", "home"), ("away", "away")]:
            team_box = getattr(box_score, side, None)
            if not team_box:
                continue

            team = game.home_team if side == "home" else game.away_team

            for category, (model_cls, field_map) in BOXSCORE_CATEGORY_MAP.items():
                player_stats = getattr(team_box, category, None)
                if not player_stats:
                    continue

                rows = []
                for stat_dict in player_stats:
                    kwargs = {
                        "game": game,
                        "team": team,
                        "side": side_label,
                        "player_name": stat_dict.get("playerName", ""),
                        "jersey_number": stat_dict.get("jerseyNumber"),
                        "position": stat_dict.get("position", ""),
                        "external_ids": {},
                    }
                    nfl_id = stat_dict.get("nflId")
                    if nfl_id:
                        kwargs["external_ids"] = {"nfl.com": {"nflId": nfl_id}}

                    # Map stat-specific fields
                    for api_key, model_field in field_map.items():
                        val = stat_dict.get(api_key)
                        if val is not None:
                            kwargs[model_field] = val

                    # Special handling for return type
                    if category in ("kick_return", "punt_return"):
                        kwargs["return_type"] = (
                            "kick" if category == "kick_return" else "punt"
                        )

                    rows.append(model_cls(**kwargs))

                if rows:
                    model_cls.objects.bulk_create(rows)

        logger.debug("Stored boxscore stats for game %d", game.pk)

    # ------------------------------------------------------------------
    # Replays
    # ------------------------------------------------------------------

    def _store_replays(self, game: Game, replays):
        GameReplay.objects.filter(game=game).delete()

        rows = []
        for r in replays:
            # Parse publish_date
            publish_date = None
            raw_date = getattr(r, "publish_date", None)
            if raw_date:
                if isinstance(raw_date, str):
                    try:
                        publish_date = datetime.fromisoformat(
                            raw_date.replace("Z", "+00:00")
                        )
                    except ValueError, TypeError:
                        pass
                elif isinstance(raw_date, datetime):
                    publish_date = raw_date

            # Thumbnail URL
            thumbnail = getattr(r, "thumbnail", None)
            thumbnail_url = ""
            if isinstance(thumbnail, dict):
                thumbnail_url = thumbnail.get("thumbnailUrl", "") or ""
            elif thumbnail:
                thumbnail_url = getattr(thumbnail, "thumbnail_url", "") or ""

            rows.append(
                GameReplay(
                    game=game,
                    replay_type=getattr(r, "type_", "") or "",
                    sub_type=getattr(r, "sub_type", "") or "",
                    title=getattr(r, "title", "")[:200] or "",
                    description=getattr(r, "description", "") or "",
                    duration=getattr(r, "duration", None),
                    external_id=getattr(r, "external_id", "") or "",
                    mcp_playback_id=getattr(r, "mcp_playback_id", "") or "",
                    publish_date=publish_date,
                    thumbnail_url=thumbnail_url,
                )
            )

        if rows:
            GameReplay.objects.bulk_create(rows)
            logger.debug("Created %d replays for game %d", len(rows), game.pk)
