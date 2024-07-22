import pandas as pd
import json
import os
import math
import logging
from pathlib import Path
from datetime import datetime
from mgz import header, fast
from mgz.model import parse_match, serialize

logger = logging.getLogger(__name__)
logging.basicConfig(filename='AdvancedParser.log', encoding='utf-8', level=logging.DEBUG)


# TODO step one - identify the things within an AOE game that I can find, publish this as a package; 
# e.g. how close the map is; front or back woodlines, civs, winner, units created, timings etc.

# TODO idea for structure - design a player that keeps track of their actions and their location and stuff
# store this within game; use to mine features for analysis
# construct a timeline? timeseries data?


class AgeGame:
    """A small wrapper for understanding an AOE game. Should just be a container for the mgz game which I can start to unpack
    TODO later, plan the functionality for a wrapper for this
    """
    def __init__(self, path: Path) -> None:
        self.path_to_game: Path = path

        with open(self.path_to_game, "rb") as g:
            self.match = parse_match(g)
            self.match_json = serialize(self.match)

        self.players = self.match_json["players"]  # List of dictionaries, including civilisations; location;

        # Raw data from the game
        self.teams: list = self.match_json["teams"]  # Just a list lists with teams and player IDs per team 
        self.rated_game: bool = self.match_json["rated"]  # bool
        self.game_speed: str = self.match_json["speed"]  # String
        self.game_data_set: str = self.match_json["dataset"]  # Just DE, not necessary
        self.starting_age: str = self.match_json["starting_age"]  # String, Dark/Fuedal/Castle
        self.game_duration: str = self.match_json["duration"]  # time HH:MM:SS.XXXXXX
        self.timestamp: str = self.match_json["timestamp"]  # Datetime, ISO format
        self.actions = self.match_json["actions"]  # JSON format! this is it
        self.inputs = self.match_json["inputs"]

        # Transform raw data into usable chunks
        self.inputs_df = pd.json_normalize(self.inputs)
        self.actions_df = pd.json_normalize(self.actions)

        # Data formatting
        self.inputs_df["timestamp"] = pd.to_timedelta(self.inputs_df["timestamp"])
        self.actions_df["timestamp"] = pd.to_timedelta(self.actions_df["timestamp"])

        # self.actions_df.to_csv(Path("DataExploration/actions.csv"))  # TODO log or save
        # self.inputs_df.to_csv(Path("DataExploration/inputs.csv"))

        self.queue_units = self.inputs_df.loc[self.inputs_df["type"] == "Queue", :]
        self.unqueue_units = self.inputs_df.loc[self.inputs_df["type"] == "Unqueue", :]

        self.research_techs = self.inputs_df.loc[self.inputs_df["type"] == "Research", :]
        self.economic_buildings_created = self.inputs_df.loc[self.inputs_df["type"] == "Build", :]

        military_buildings = ["Stable", "Archery Range", "Barracks", "Siege Workshop"]

        self.military_buildings_created = self.economic_buildings_created[
            self.economic_buildings_created.loc[:, "param"].isin(military_buildings)
            ]  # TODO factor in build times!

        # Information mined # TODO think of best way to store this - probably want one row of a table for the whole game, but maybe multiple?
        # One for each stage in the game? and flatten out what they do for each of these stages? interesting
        self.opening = pd.Series()
        return

    def explore_games(self) -> None:
        # Current knowledge - check out the objects added to the game

        print("use this as a breakpoint")

        return

    def identify_technology_research_and_time(self, technology, civilisations: dict = None) -> pd.DataFrame:
        """A helper function that can identify when players research certain things and the timing of that

        :param technology: technology that can be research TODO enumerate this
        :type technology: str
        :param civilisations: civilisations to handle faster research times, defaults to None
        :type civilisations: dict, optional
        :raises ValueError: incorrect technology passed
        :return: data frame with the time each player researched and completed the technology
        :rtype: pd.DataFrame
        """

        if technology not in ["Feudal Age", "Loom", "Double-Bit Axe", "Horse Collar", "Fletching", "Castle Age", "Man-At-Arms"]:
            logger.error(f"Technology given to find tech function incorrect. Tech was: {technology}")
            raise ValueError(f"Couldn't find technology: {technology}")

        # TODO check why there is two clicks - maybe one for queue and one for actually clicking up?
        # Handle two clicks
        relevent_research = self.research_techs.loc[self.research_techs["param"] == technology, ["timestamp", "player"]]
        max_idx = relevent_research.groupby(["player"])["timestamp"].transform(max) == relevent_research["timestamp"]
        relevent_research = relevent_research[max_idx]

        # TODO - map the research times and then apply them, find a good way to house this data (tiny data with civ?)
        # TODO work out how to handle shorter time with civilisation parameter

        return relevent_research

    def identify_building_and_timing(self, building, civilisations: dict = None) -> pd.DataFrame:
        """Helper to find all the creations of an economic building type. TODO refactor for each player.

        :param building: _description_ TODO
        :type building: _type_
        :param civilisations: _description_, defaults to None
        :type civilisations: dict, optional
        :raises ValueError: _description_
        :return: _description_
        :rtype: pd.DataFrame
        """

        if building not in ["Mill", "Farm", "House", "Lumber Camp", "Mining Camp", "Blacksmith"]:
            logger.error(f"Technology given to find tech function incorrect. Tech was: {building}")
            raise ValueError(f"Couldn't find technology: {building}")
    
        # TODO - map the building times, find a good way to house this data (tiny data with civ?)
        time_to_build_dictionary = {"Mill": 100, "Farm": 15}
        time_to_build = time_to_build_dictionary[building]

        relevent_building = self.economic_buildings_created.loc[self.economic_buildings_created["param"] == building, ["timestamp", "player"]]
        relevent_building["timestamp"] = relevent_building["timestamp"] + pd.Timedelta(seconds=time_to_build)
        
        return relevent_building

    def extract_feudal_time_information(self, feudal_time: pd.Timedelta, loom_time: pd.Timedelta, civilisation: str = None) -> pd.Series:
        """_summary_ TODO

        :param feudal_time: _description_
        :type feudal_time: datetime
        :param loom_time: _description_
        :type loom_time: datetime
        :param civilisation: _description_, defaults to None
        :type civilisation: str, optional
        :return: _description_
        :rtype: pd.Series
        """

        # TODO - check if loom was in feudal or not
        loom_in_dark_age = loom_time < feudal_time

        villager_creation_time = 25  # TODO handle other civs that have special shit like chinese, Mayans, Hindustanis

        villager_analysis = feudal_time / villager_creation_time  # TODO working with times
        number_villagers = villager_analysis.seconds
        dark_age_idle_time = (villager_analysis._ms * villager_creation_time) / 1000  # convert ms to s, this is % of villager time

        feudal_stats_to_return = {"FeudalTime": feudal_time,
                                  "Villagers": number_villagers,
                                  "DarkAgeIdleTime": dark_age_idle_time,
                                  "DarkAgeLoom": loom_in_dark_age}

        return pd.Series(feudal_stats_to_return)

    def identify_militia_based_strategy(self,
                                        castle_time: pd.Timedelta,
                                        military_buildings_spawned: pd.DataFrame,
                                        mill_created_time: pd.Timedelta,
                                        units_queued: pd.DataFrame,
                                        maa_upgrade: pd.Timedelta = None
                                        ) -> pd.Series:
        """Logic to identify groups of MAA or Militia based strategy: MAA, pre-mill drush, drush"""
        # Identify key timings and choices associated with these strategies
        dark_age_feudal_barracks = military_buildings_spawned.loc[(military_buildings_spawned["param"] == "Barracks") &
                                                                  (military_buildings_spawned["timestamp"] < castle_time), :]
        first_barracks_time = dark_age_feudal_barracks["timestamp"].min()
        pre_mill_barracks = first_barracks_time < mill_created_time
        militia_created = units_queued.loc[(units_queued["param"] == "Militia") &
                                           (units_queued["timestamp"] < castle_time), :]

        # convert raw information into strategy - number of units
        number_of_militia_or_maa = len(militia_created)

        # convert raw information into strategy - strategy
        if maa_upgrade is not None:
            militia_opening_strategy = "MAA"
        elif pre_mill_barracks and len(militia_created) > 0:
            militia_opening_strategy = "Pre-Mill Drush"
        elif len(militia_created) > 0:
            militia_opening_strategy = "Drush"
        else:
            militia_opening_strategy = None

        # TODO identify the time the militia rock up to the opponents base
        # Return key featues
        dark_age_choices_to_return = {
            "FirstBarracksTime": first_barracks_time,
            "MilitiaStrategyIdentified": militia_opening_strategy,
            "NumberOfMilitiaUnits": number_of_militia_or_maa,
            "PreMillBarracks": pre_mill_barracks,
        }

        return pd.Series(dark_age_choices_to_return)

    def identify_feudal_military_choices(self,
            feudal_time: pd.Timedelta,
            castle_time: pd.Timedelta,
            military_buildings_spawned: pd.DataFrame,
            units_queued: pd.DataFrame
    ) -> pd.Series:
        """Draws out the base military decisions in feudal age, e.g. buildings created, number of units, etc. TODO finish detail

        :param feudal_time: _description_
        :type feudal_time: pd.Timedelta
        :param castle_time: _description_
        :type castle_time: pd.Timedelta
        :param military_buildings_spawned: _description_
        :type military_buildings_spawned: pd.DataFrame
        :param units_queued: _description_
        :type units_queued: pd.DataFrame
        :return: _description_
        :rtype: pd.Series
        """
        # get ranges and stables made in feudal
        feudal_military_buildings = military_buildings_spawned.loc[
            ((military_buildings_spawned["param"] == "Archery Range") |
             (military_buildings_spawned["param"] == "Stable")) &
            (military_buildings_spawned["timestamp"] > feudal_time) &
            (military_buildings_spawned["timestamp"] < castle_time),
            :
            ]

        # time of first building
        opening_timing = feudal_military_buildings["timestamp"]

        # Get the first military building made in feudal
        opening_military_building = feudal_military_buildings.loc[feudal_military_buildings["timestamp"] == opening_timing, "param"]

        # extract the units created and how many of those created
        feudal_units = ["Scout Cavalry", "Skirmisher", "Archer", "Spearman"]  # TODO store this information somewhere
        feudal_military_units = units_queued.loc[(units_queued["param"].isin(feudal_units)) &
                                                 (units_queued["timestamp"] < castle_time),
                                                 :
                                                 ]

        # Count of each military unit
        number_of_each_unit = feudal_military_units.groupby("param").count()["type"]

        # Handle instance where they do not produce this unit
        for unit in ["Archer", "Skirmisher", "Scout Cavalry", "Spearman"]:
            if unit not in number_of_each_unit.index:
                number_of_each_unit[unit] = 0

        # Non spear units - to identify strategy
        non_spear_military_units = feudal_military_units.loc[feudal_military_units["param"] != "Spearman", :]

        # Extract time to 3 of first units
        # TODO - need to build out a method for working out when an object could produce a unit
        # TODO Extract idle time of first military building

        # TODO extract second military building
        # TODO Extract second military unit

        military_stats_to_return = {
            "OpeningMilitaryBuildingTime": opening_timing.iloc[0],
            "OpeningMilitaryBuilding": opening_military_building.iloc[0],
        }

        return pd.concat([pd.Series(military_stats_to_return), number_of_each_unit])

    def extract_opening_strategy(self,
                                 feudal_time: pd.Timedelta,
                                 castle_time: pd.Timedelta,
                                 military_buildings_spawned: pd.DataFrame,
                                 mill_created_time: pd.Timedelta,
                                 units_queued: pd.DataFrame,
                                 maa_upgrade: pd.Timedelta = None
                                 ) -> pd.Series:

        # identify drush and categorise into MAA/Pre-mill/Drush
        dark_age_approach = self.identify_militia_based_strategy(
            castle_time=castle_time,
            military_buildings_spawned=military_buildings_spawned,
            mill_created_time=mill_created_time,
            units_queued=units_queued,
            maa_upgrade=maa_upgrade
        )  # TODO - identify towers or a fast castle

        feudal_approach = self.identify_feudal_military_choices(
            feudal_time=feudal_time,
            castle_time=castle_time,
            military_buildings_spawned=military_buildings_spawned,
            units_queued=units_queued
        )

        # Extract number of steals
        match (dark_age_approach["MilitiaStrategyIdentified"],
               feudal_approach["OpeningMilitaryBuilding"],
               feudal_approach["Archer"] > 0,
               feudal_approach["Skirmisher"] > 0,
               feudal_approach["Scout Cavalry"] > 0):
            case ("Drush", "Archery Range", _, _, _):
                strategy = "Drush Flush"
            case ("Pre-Mill Drush", "Archery Range", _, _, _):
                strategy = "Pre-Mill Drush Flush"
            case ("MAA", "Archery Range", _, _, _):
                strategy = "MAA Archers"
            case (_, "Archery Range", True, True, True):
                strategy = "Archery Range into Full Feudal"
            case (_, "Stable", True, True, True):
                strategy = "Scouts into Full Feudal"
            case (_, "Archery Range", True, True, _):
                strategy = "Archers and Skirms"
            case (_, "Archery Range", True, _, True):
                strategy = "Archers into scouts"
            case (_, "Archery Range", True, _, True):
                strategy = "Skirms into scouts"
            case (_, "Stable", True, _, _):
                strategy = "Scouts into archers"
            case (_, "Stable", _, True, _):
                strategy = "Scouts into skirms"
            case (_, "Archery Range", True, False, False):
                strategy = "Straight Archers"
            case (_, "Archery Range", False, True, False):
                strategy = "Straight Skirms or Trash Rush"
            case (_, "Archery Range", False, False, True):
                strategy = "Full scouts or Scouts into Castle"
            case (_, _, _, _, _):
                strategy = "Could not Identify!"
                logger.warning("Couldn't identify this strategy")

        # Map approximately to known strategies
        return pd.concat([pd.Series({"OpeningStrategy": strategy}), dark_age_approach, feudal_approach])

    def extract_feudal_and_dark_age_economics(self, ) -> pd.Series:
        # TODO
        # feudal age wood upgrade (early, late, castle)
        # feudal age farm upgrade (early, late, castle)
        # dark age number of deer taken
        # dark age number of boars/rhinos taken
        # dark age number of sheep taken
        # dark age time of mill on berries + number of vils on berries
        # feudal age number of farms
        # time of three farms
        # time of 6 farms
        # time of 10 farms
        # time of 15 farms
        # time of 20 farms if in
        # number of walls in dark age
        # number of walls in feudal age
        # number of houses in dark age + feudal (assume part of walls)
        return

    def extract_map_features(self) -> pd.Series:
        # TODO
        # distance between players
        # hills between players?
        # number of trees directly between players / in corridor
        # Idea for lumber camps - % of front covered by trees - maybe divide into quarters?
        return

    def advanced_parser(self) -> None:
        # TODO mine location of players and their distance from players
        # TODO mine civilisations and player rating from players
        # TODO get the winner from players
        # TODO mine if boar or elephant
        # TODO mine if scout lost
        # TODO identify what it looks like if a player un-queus a unit
        # TODO create an object for each player that houses this information

        # Extract the key statistics / data points
        # research times to mine out
        feudal_times = self.identify_technology_research_and_time("Feudal Age")  # Get feudal times of the players
        castle_times = self.identify_technology_research_and_time("Castle Age")
        loom_times = self.identify_technology_research_and_time("Loom")  # Get loom time

        # Military timings to mine out
        maa_time = self.identify_technology_research_and_time("Man-At-Arms") # TODO check name
        player_one_maa = None  # TODO when made player object remove this
        if not maa_time.loc[maa_time["player"] == 1, "timestamp"].empty:
            player_one_maa = not maa_time.loc[maa_time["player"] == 1, "timestamp"].iloc[0]

        player_two_maa = None  # TODO when made player object remove this
        if not maa_time.loc[maa_time["player"] == 2, "timestamp"].empty:
            player_two_maa = not maa_time.loc[maa_time["player"] == 2, "timestamp"].iloc[0]

        # economic times to mine out
        all_mill_times = self.identify_building_and_timing("Mill")
        min_mill_idx = all_mill_times.groupby(["player"])["timestamp"].transform(min) == all_mill_times["timestamp"]
        first_mill_times = all_mill_times[min_mill_idx]

        # TODO create a factory for each players choices or an object
        player_one_dark_age_stats = self.extract_feudal_time_information(
            feudal_time=feudal_times.loc[feudal_times["player"] == 1, "timestamp"].iloc[0],
            loom_time=loom_times.loc[loom_times["player"] == 1, "timestamp"].iloc[0])

        player_two_dark_age_stats = self.extract_feudal_time_information(
            feudal_time=feudal_times.loc[feudal_times["player"] == 2, "timestamp"].iloc[0],
            loom_time=loom_times.loc[loom_times["player"] == 2, "timestamp"].iloc[0])

        player_one_dark_age_stats = player_one_dark_age_stats.add_prefix("PlayerOne.")  # Naming convention; TODO sub for winner and loser
        player_two_dark_age_stats = player_two_dark_age_stats.add_prefix("PlayerTwo.")

        self.opening = pd.concat([self.opening, player_one_dark_age_stats, player_two_dark_age_stats])  # include self as is it empty series

        # Identify Feudal Age Strategy
        player_one_opening_strategy = self.extract_opening_strategy(
            feudal_time=feudal_times.loc[feudal_times["player"] == 1, "timestamp"].iloc[0],
            castle_time=castle_times.loc[castle_times["player"] == 1, "timestamp"].iloc[0],
            military_buildings_spawned=self.military_buildings_created.loc[self.military_buildings_created["player"] == 1, :],
            mill_created_time=first_mill_times.loc[first_mill_times["player"] == 1, "timestamp"].iloc[0],
            units_queued=self.queue_units.loc[self.queue_units["player"] == 1, :],
            maa_upgrade=player_one_maa,
        )
        player_one_opening_strategy = player_one_opening_strategy.add_prefix("PlayerOne.")

        player_two_opening_strategy = self.extract_opening_strategy(
            feudal_time=feudal_times.loc[feudal_times["player"] == 2, "timestamp"].iloc[0],
            castle_time=castle_times.loc[castle_times["player"] == 2, "timestamp"].iloc[0],
            military_buildings_spawned=self.military_buildings_created.loc[self.military_buildings_created["player"] == 2, :],
            mill_created_time=first_mill_times.loc[first_mill_times["player"] == 2, "timestamp"].iloc[0],
            units_queued=self.queue_units.loc[self.queue_units["player"] == 2, :],
            maa_upgrade=player_one_maa,
        )
        player_two_opening_strategy = player_two_opening_strategy.add_prefix("PlayerTwo.")

        self.opening = pd.concat([self.opening, player_one_opening_strategy, player_two_opening_strategy])

        return


if __name__ == "__main__":

    test_file = Path("Test_Games/SD-AgeIIDE_Replay_324565276.aoe2record")

    test_match = AgeGame(path=test_file)
    test_match.advanced_parser()
    print("\n")
    print(test_match.opening)

