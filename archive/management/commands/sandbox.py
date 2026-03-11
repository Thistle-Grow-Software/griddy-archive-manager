import json
import re
from typing import Any

import djclick as click
from griddy.nfl import GriddyNFL


def camel_to_snake(s):
    return re.sub(r"(?<=[a-z0-9])([A-Z])", r"_\1", s).lower()


def _build_nfl_client(email, password, creds_file):
    kwargs: dict[str, Any] = {"headless_login": True}
    if creds_file:
        with open(creds_file) as infile:
            creds = json.load(infile)
            kwargs["nfl_auth"] = creds
    else:
        kwargs["login_email"] = email
        kwargs["login_password"] = password
    return GriddyNFL(**kwargs)


@click.group()
def sandbox():
    pass


@sandbox.command()
@click.option("--email", type=str)
@click.option("--password", type=str)
@click.option("--creds-file", type=str)
@click.option("--fetch", default=False, is_flag=True, flag_value=True)
def comparison(
    email: str | None = None,
    password: str | None = None,
    creds_file: str | None = None,
    fetch: bool = False,
):

    game_id = "10012015-0910-001f-0988-f51e8eea770e"
    modern_game_id = "10012016-0908-00db-4b7c-51baf4fe674d"
    if fetch:
        nfl = _build_nfl_client(email, password, creds_file)
        all_wgd = nfl.games.get_weekly_game_details(
            season=2015,
            type_="REG",
            week=1,
            include_replays=True,
            include_standings=True,
            include_drive_chart=True,
            include_tagged_videos=True,
        )
        weekly_game_details = None
        for w in all_wgd:
            if w.id == game_id:
                weekly_game_details = w

        all_reg_keys = [*weekly_game_details.model_dump().keys()]
        with open("all_reg_keys.json", "w") as outfile:
            json.dump(all_reg_keys, outfile, indent=4)

        all_pro_wgd = nfl.games.get_weekly_game_details(
            season=2016,
            type_="REG",
            week=1,
            include_replays=True,
            include_standings=True,
            include_drive_chart=True,
            include_tagged_videos=True,
        )
        pro_wgd = None
        for wgd in all_pro_wgd:
            if wgd.id == modern_game_id:
                pro_wgd = wgd

        all_sked_games = nfl.schedules.get_scheduled_games(
            season=2015, season_type="REG", week=1
        ).games

        pro_scheduled_game_hdr = None
        for sg in all_sked_games:
            if sg.id == game_id:
                pro_scheduled_game_hdr = sg

        pro_sked_game_dtls = nfl.schedules.get_scheduled_game(game_id=modern_game_id)

        pro_game_id = pro_sked_game_dtls.game_id

        pro_box_score = nfl.pro_games.get_stats_boxscore(game_id=str(pro_game_id))
        pro_game_center = nfl.pro_games.get_gamecenter(game_id=str(pro_game_id))
        pro_play_list = nfl.pro_games.get_playlist(game_id=str(pro_game_id))

        combined_pro_info = {
            "weekly_game_details": list(pro_wgd.model_dump().keys()),
            "scheduled_games_hdr": list(pro_scheduled_game_hdr.model_dump().keys()),
            "sked_game_dtls": list(pro_sked_game_dtls.model_dump().keys()),
            "box_score": list(pro_box_score.model_dump().keys()),
            "game_center": list(pro_game_center.model_dump().keys()),
            "pro_play_list": list(pro_play_list.plays[0].model_dump().keys()),
        }

        with open("combined_pro_info.json", "w") as outfile:
            json.dump(combined_pro_info, outfile, indent=4)

        missing_keys = {}
        for category, keys in combined_pro_info.items():
            missing_keys[category] = list(set(all_reg_keys) - set(keys))

        with open("missing_keys.json", "w") as outfile:
            json.dump(missing_keys, outfile, indent=4)
    else:
        with open("all_reg_keys.json") as infile:
            all_reg_keys = json.load(infile)

        with open("combined_pro_info.json") as infile:
            combined_pro_info = json.load(infile)

        for category, keys in combined_pro_info.items():
            combined_pro_info[category] = [camel_to_snake(k) for k in keys]

        with open("combined_pro_info.json", "w") as outfile:
            json.dump(combined_pro_info, outfile, indent=4)

        missing_keys = {}
        for category, keys in combined_pro_info.items():
            missing_keys[category] = list(set(keys) - set(all_reg_keys))

        with open("missing_keys.json", "w") as outfile:
            json.dump(missing_keys, outfile, indent=4)


@sandbox.command()
@click.option("--email", type=str)
@click.option("--password", type=str)
@click.option("--creds-file", type=str)
@click.option("--fetch", default=False, is_flag=True, flag_value=True)
def boxscore_comparison(email, password, creds_file, fetch):
    modern_game_id = "10012016-0908-00db-4b7c-51baf4fe674d"

    old_game_id = "10012015-0910-001f-0988-f51e8eea770e"
    if fetch:
        nfl = _build_nfl_client(email, password, creds_file)

        wgd = nfl.experience.get_game_details(
            game_id=old_game_id,
            include_drive_chart=True,
            include_replays=True,
            include_standings=True,
            include_tagged_videos=True,
            include_summary=True,
        )

        live_player_resp = nfl.football_stats.live.get_player_statistics(
            game_id=old_game_id
        )
        live_team_resp = nfl.football_stats.live.get_team_statistics(
            game_id=old_game_id
        )
        home_team_id = "10403200-69ab-9ea6-5af5-e240fbc08bea"
        hist_player_resp = nfl.football_stats.historical.get_player_stats(
            game_id=old_game_id, team_id=home_team_id
        )
        hist_team_resp = nfl.football_stats.historical.get_team_stats(
            game_id=old_game_id, team_id=home_team_id
        )

        historic_game_info = {
            "wgd": wgd.model_dump(),
            "live_player_stats": live_player_resp.model_dump(),
            "live_team_stats": live_team_resp.model_dump(),
            "historic_player_stats": hist_player_resp.model_dump(),
            "historic_team_stats": hist_team_resp.model_dump(),
        }

        # Get scheduled game to resolve IDs
        sked_game_dtls = nfl.schedules.get_scheduled_game(game_id=modern_game_id)
        pro_game_id = str(sked_game_dtls.game_id)

        boxscore = nfl.pro_games.get_stats_boxscore(game_id=pro_game_id)
        game_center = nfl.pro_games.get_gamecenter(game_id=pro_game_id)
        play_list = nfl.pro_games.get_playlist(game_id=pro_game_id).plays
        example_play = play_list[0]

        pro_game_info = {
            "wgd": wgd.model_dump(),
            "sked_game_dtls": sked_game_dtls.model_dump(),
            "boxscore": boxscore.model_dump(),
            "game_center": game_center.model_dump(),
            "play_list": example_play.model_dump(),
        }

        with open("historic_game_info.json", "w") as outfile:
            json.dump(historic_game_info, outfile, indent=4)

        with open("pro_game_info.json", "w") as outfile:
            json.dump(pro_game_info, outfile, indent=4)
