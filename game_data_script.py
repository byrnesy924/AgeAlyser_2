"""Script for getting game data
"""
# Start link for Libre match API: https://wiki.librematch.org/rlink/start
# https://github.com/librematch
# https://github.com/librematch/librematch-rlink_client/tree/main/rlink_client_python

# dj0wns has charted this territory - see their github project 
# https://github.com/dj0wns/AoE_Rec_Opening_Analysis/blob/main/aoe_opening_data/find_replays_from_ms_api.py


endpoint = "https://aoe.ms/replay/?gameId=<game_id>&profileId=<profile_id>"

# Another method of getting match IDs and so on - https://aoestats.io/api-info/
# Get them from the parquet dumps for aoestats, and then use the id and profile id to git the aoe.ms API


import requests
import io
import zipfile
from pprint import pprint


# Taken from https://github.com/dj0wns/AoE_Rec_Opening_Analysis/blob/main/aoe_opening_data/find_replays_from_ms_api.py
LEADERBOARD_IDS = {
    # from https://aoe-api.worldsedgelink.com/community/leaderboard/getAvailableLeaderboards?title=age2
    "RM_SOLO": (3, 6),  # RM 1v1 - ID = 3; matchtype_ID = 6
    # (4, [7,8,9]), # RM Team - 
    # EMPIRE WARS
    "EW_SOLO": (13, 26),  # EW 1v1
    # (14, [27,28,29]), #EW Team
    # THESE ARENT SUPPORTED BY THE PARSER YET

}


def get_leaderboard(leaderboard_id: int):
    """See https://github.com/dj0wns/AoE_Rec_Opening_Analysis/blob/main/aoe_opening_data/find_replays_from_ms_api.py
    Returns top 200 of the leaderboard - not sorted but all we need is their ID
    """
    try:
        leaderboard = requests.get(
            f"https://aoe-api.worldsedgelink.com/community/leaderboard/getLeaderBoard2?leaderboard_id={leaderboard_id}&title=age2")
        # print(leaderboard.status_code)  # turn into log
        if leaderboard.status_code != 200:
            return None
    except Exception as e:
        print(e)
        return None
    return leaderboard.json()


def get_match_history_for_player_ids(player_ids: list[int], match_type: int):
    """See https://github.com/dj0wns/AoE_Rec_Opening_Analysis/blob/main/aoe_opening_data/find_replays_from_ms_api.py
    Returns a list of player matches
    """
    try:
        matches = requests.get(
            f"https://aoe-api.worldsedgelink.com/community/leaderboard/getRecentMatchHistory?title=age2&matchtype_id={match_type}&profile_ids={player_ids}"
            )
        if matches.status_code != 200:
            return None
    except Exception as e:
        print(e)
        return None
    return matches.json()


def download_match(match_id: int, player_id: int):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_5) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/50.0.2661.102 Safari/537.36'}
        r = requests.get(
            f"https://aoe.ms/replay/?gameId={match_id}&profileId={player_id}",
            headers=headers
        )
    except Exception as e:
        print(e)
        return False
    if r.status_code == 404:
        # cant download match, add dummy to list of undownloadable matches
        return False
    elif r.status_code != 200:
        print(f"Received {r.status_code} from {r.url}")
        return False

    print("Success!")

    # replay_zip = zipfile.ZipFile(io.BytesIO(r.content))
    # replay = replay_zip.read(replay_zip.namelist()[0])
    return


if __name__ == "__main__":
    solo_leader_board = get_leaderboard(leaderboard_id=LEADERBOARD_IDS["RM_SOLO"][0])["statGroups"]
    player_ids = {player_json["members"][0]["alias"]: player_json["members"][0]["profile_id"] for player_json in solo_leader_board}

    valid_matches = []

    for player_id in player_ids.items():
        player_matches_reponse = get_match_history_for_player_ids([player_id], LEADERBOARD_IDS["RM_SOLO"][1])  # Can get more players from the profiles section of this
        if player_matches_reponse is None:
            print(f"No match history for {player_id}")
            continue

        player_matches = player_matches_reponse["matchHistoryStats"]

        match_metadata = [{
            "id": rec_match_json["id"],
            "maxplayers": rec_match_json["maxplayers"],
            "map": rec_match_json["mapname"],
            "ranked": rec_match_json["description"] == "AUTOMATCH",
            "playerOne": rec_match_json["creator_profile_id"],
            "playerTwo": rec_match_json["matchhistoryreportresults"][0]["profile_id"],
            } for rec_match_json in player_matches]

        valid_matches.extend(match_metadata)

    for match in valid_matches:
        download_match(match["id"], match["playerOne"])
    
