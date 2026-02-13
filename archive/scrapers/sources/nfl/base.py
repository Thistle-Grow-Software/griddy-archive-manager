import json
import logging
import time
from datetime import date
from random import uniform
from typing import Dict, Optional

from griddy.nfl import GriddyNFL
from griddy.nfl.models import SeasonTypeEnum

logger = logging.getLogger(__name__)

from archive.models import (
    Franchise,
    Game,
    League,
    OrgUnit,
    Season,
    Team,
    TeamAffiliation,
    TeamVenueOccupancy,
    Venue,
)
from archive.scrapers import BaseScraper
from archive.utils import get_content_file_from_url

PRO_API_MIN_SEASON = 2020


class NFLScraper(BaseScraper):
    logo_format_instructions = "h_144,w_144,q_auto,f_auto,dpr_2.0"

    def __init__(
        self,
        login_email: str = None,
        login_password: str = None,
        creds: Optional[Dict | str] = None,
        headless_login: bool = True,
        year: int = None,
    ):
        self._validate_init_params(
            login_email=login_email,
            login_password=login_password,
            creds=creds,
            headless_login=headless_login,
        )
        if login_email:
            self.client = GriddyNFL(
                login_email=login_email,
                login_password=login_password,
                headless_login=headless_login,
            )
        else:
            if isinstance(creds, str):
                with open(creds, "r") as infile:
                    creds = json.load(infile)

            self.client = GriddyNFL(nfl_auth=creds, headless_login=headless_login)

        self.league = League.objects.get(short_name="NFL")
        self.season = Season.objects.get(league=self.league, year=year)

    def _validate_init_params(
        self,
        login_email: str = None,
        login_password: str = None,
        creds: dict = None,
        headless_login: bool = True,
    ):
        if login_email and creds:
            raise ValueError("You must provide either login_email OR creds, not both.")
        elif not (login_email or creds):
            raise ValueError(
                "You must provide either login_email or creds, you've provided neither."
            )
        elif login_email and not login_password:
            raise ValueError(
                "You're attempting email + password login, but have not provided login_password."
            )

    def transform_team_data(self, nfl_data: dict) -> dict:
        griddy_data = {
            "name": nfl_data["name"],
            "alternate_name": nfl_data["fullName"],
            "short_name": nfl_data["abbr"],
            "city": nfl_data["city"],
            # TODO: For some reason th NFL just stores the city value in cityState
            "state": nfl_data["cityState"],
            "country": "US",
            "mascot": nfl_data["nickname"],
            "external_ids": {
                "nfl.com": {
                    "slug": nfl_data["slug"],
                    "smartId": nfl_data["smartId"],
                    "teamId": nfl_data["teamId"],
                }
            },
            "primary_color": nfl_data["primaryColor"].replace("#", ""),
            "secondary_color": nfl_data["secondaryColor"].replace("#", ""),
            "tertiary_color": nfl_data["tertiaryColor"].replace("#", ""),
            "additional_colors": {
                "altColor": nfl_data["altColor"],
                "darkColor": nfl_data["darkColor"],
            },
            "logo": nfl_data["logo"].format(
                formatInstructions=self.logo_format_instructions
            ),
        }

        addl_data = {
            key: nfl_data[key]
            for key in [
                "conference",
                "division",
                "domain",
                "isProBowl",
                "nick",
                "season",
                "stadiumName",
                "teamSiteTicketUrl",
                "teamSitUrl",
                "teamType",
                "ticketPhoneNumber",
                "yearFound",
            ]
            if key in nfl_data
        }
        griddy_data["bonus_data"] = addl_data

        return griddy_data

    def _create_division_affiliation(self, team: Team, div_str: str):
        division = OrgUnit.objects.get(long_name=div_str)
        ta = TeamAffiliation(
            team=team, org_unit=division, start_date=date(year=2002, month=9, day=5)
        )
        ta.save()

    def create_db_object(self, raw_data):
        logger.info(f"Creating team for {raw_data['name']}")
        team_data = self.transform_team_data(nfl_data=raw_data)
        logger.info("Transformed data")
        logo_url = team_data.pop("logo")

        franchise, _ = Franchise.objects.get_or_create(
            league=League.objects.get(short_name="NFL"),
            name=raw_data["nickname"],
        )
        team_data["franchise"] = franchise

        team = Team(**team_data)
        team.save()
        logger.info(f"Saved team to disk. ID={team.id}")
        team.logo.save(
            f"{raw_data['slug']}.png", get_content_file_from_url(logo_url), save=True
        )
        logger.info("Saved logo to disk")

        self._create_division_affiliation(
            team=team,
            div_str=raw_data["division"]["full_name"].replace(" Division", ""),
        )
        logger.info("Created division affiliation")
        self.create_team_venue_occupancy(team=team, venue_name=raw_data["stadiumName"])
        logger.info("Created team occupancy record")

    def process_venue(self, venue_data: dict):
        venue = Venue.objects.filter(name=venue_data["name"]).first()
        if venue is None:
            venue = Venue(
                name=venue_data.pop("name"),
                city=venue_data.pop("city"),
                state=venue_data.pop("territory", ""),
                country=venue_data.pop("country"),
                external_ids={"nfl": {"id": venue_data.pop("id")}},
                bonus_data=venue_data,
            )
            venue.save()
        return venue

    def create_team_venue_occupancy(self, team: Team, venue_name: str):
        venue = Venue.objects.filter(name=venue_name).first()
        if venue is None:
            return
        tvo = TeamVenueOccupancy(team=team, venue=venue)
        tvo.save()

    def _cast_to_json(self, data: Dict) -> Dict:
        dictified_info = {}
        for info_type, sub_data in data.items():
            if isinstance(sub_data, dict):
                dictified_info[info_type] = self._cast_to_json(sub_data)
                continue

            if isinstance(sub_data, list):
                dictified_info[info_type] = [item.model_dump() for item in sub_data]
                continue

            dictified_info[info_type] = sub_data.model_dump()

        return dictified_info

    def gather_all_data_for_week(
        self,
        season: int,
        week: int,
        season_type: SeasonTypeEnum = "REG",
        as_json: bool = False,
    ) -> Dict:
        if (not self.season) or (self.season.year != season):
            self.season = Season.objects.get(year=season)

        existing_game_nfl_ids = Game.objects.filter(
            league=self.league, season=self.season
        ).values_list("external_ids__nfl_game_id", flat=True)

        use_pro_api = season >= PRO_API_MIN_SEASON

        # Fetch weekly game details (available for all seasons).
        # Explicit server_url required: the SDK shares a mutable SDKConfiguration, and
        # accessing any ProSDK endpoint (e.g. schedules) sets server_type to "pro",
        # causing subsequent regular-API calls to hit the wrong server.
        weekly_details = self.client.games.get_weekly_game_details(
            season=season,
            type_=season_type,
            week=week,
            include_drive_chart=True,
            include_replays=True,
            include_standings=True,
            include_tagged_videos=True,
            server_url="https://api.nfl.com",
        )
        logger.info(f"Fetched weekly game details for {len(weekly_details)} games")
        weekly_details_by_game = {detail.id: detail for detail in weekly_details}

        # ----- Game discovery: build all_game_data keyed by game ID -----
        if use_pro_api:
            games = self.client.schedules.get_scheduled_games(
                season=season, season_type=season_type, week=week
            ).games
            games = [g for g in games if g.id not in existing_game_nfl_ids]
            all_game_data = {g.id: {"scheduled_games": g} for g in games}
        else:
            # Pre-2020: discover games from WeeklyGameDetail objects
            all_game_data = {}
            for game_id, detail in weekly_details_by_game.items():
                if game_id in existing_game_nfl_ids:
                    continue
                all_game_data[game_id] = {"wgd_detail": detail}

        # ----- Enrich with WGD supplemental data -----
        for game_id, detail in weekly_details_by_game.items():
            if game_id not in all_game_data:
                continue
            unique_data = {}
            if detail.summary is not None:
                unique_data["summary"] = detail.summary
            if detail.drive_chart is not None:
                unique_data["drive_chart"] = detail.drive_chart
            if detail.replays is not None:
                unique_data["replays"] = detail.replays
            if detail.away_team_standings is not None:
                unique_data["away_team_standings"] = detail.away_team_standings
            if detail.home_team_standings is not None:
                unique_data["home_team_standings"] = detail.home_team_standings
            if detail.tagged_videos is not None:
                unique_data["tagged_videos"] = detail.tagged_videos
            all_game_data[game_id]["weekly_game_details"] = unique_data

        # ----- Per-game detail fetching -----
        game_ids = list(all_game_data.keys())
        game_count = len(game_ids)

        for cur_game, game_id in enumerate(game_ids, start=1):
            logger.info(
                f"Working on game {game_id} - No {cur_game} of {game_count} "
                f"for week {week} of {season}"
            )

            if use_pro_api:
                sked_game_dtls = self.client.schedules.get_scheduled_game(
                    game_id=game_id
                )
                logger.info("Fetched scheduled_game details")
                pro_game_id = str(sked_game_dtls.game_id)
                logger.info(f"Pro Game ID: {pro_game_id}")

                box_score = self.client.pro_games.get_stats_boxscore(
                    game_id=pro_game_id
                )
                logger.info("Fetched box score")
                game_center = self.client.pro_games.get_gamecenter(game_id=pro_game_id)
                logger.info("Fetched game center")

                play_list = self.client.pro_games.get_playlist(
                    game_id=pro_game_id
                ).plays
                logger.info("Fetched play list")

                all_game_data[game_id].update(
                    {
                        "sked_game_dtls": sked_game_dtls,
                        "box_score": box_score,
                        "game_center": game_center,
                        "play_list": play_list,
                    }
                )
            else:
                # Pre-2020: use regular API endpoints only
                regular_box_score = self.client.games.get_box_score(
                    game_id=game_id,
                    server_url="https://api.nfl.com",
                )
                logger.info("Fetched regular box score")

                regular_play_by_play = self.client.games.get_play_by_play(
                    game_id=game_id,
                    server_url="https://api.nfl.com",
                )
                logger.info("Fetched regular play-by-play")

                all_game_data[game_id].update(
                    {
                        "regular_box_score": regular_box_score,
                        "regular_play_by_play": regular_play_by_play,
                    }
                )

            if as_json:
                all_game_data[game_id] = self._cast_to_json(data=all_game_data[game_id])

        return all_game_data
