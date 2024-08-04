import numpy as np
import pandas as pd
# import json
# import os
import math
from scipy.ndimage import label, generate_binary_structure
from shapely import Point, Polygon
import logging
from pathlib import Path
from datetime import datetime
from mgz import header, fast, body
from mgz.summary import Summary
from mgz.model import parse_match, serialize
# from utils import GamePlayer, AgeGame  # buildings model

logger = logging.getLogger(__name__)
logging.basicConfig(filename='AdvancedParser.log', encoding='utf-8', level=logging.DEBUG)


# TODO step one - identify the things within an AOE game that I can find, publish this as a package; 
# e.g. how close the map is; front or back woodlines, civs, winner, units created, timings etc.

# TODO put objects to utils script and import them

# TODO idea for structure - design a player that keeps track of their actions and their location and stuff
# store this within game; use to mine features for analysis
# construct a timeline? timeseries data?

class GamePlayer:
    def __init__(
            self,
            number: int,
            name: str,
            civilisation: str,
            starting_position: list,
            actions: pd.DataFrame,
            inputs: pd.DataFrame,
            winner: bool,
            elo: int,
            ) -> None:

        self.number = number
        self.name = name
        self.civilisation = civilisation  # Comes as dict with x and y - store as tuple for arithmetic
        self.starting_position = (starting_position["x"], starting_position["y"])
        self.player_won = winner
        self.elo = elo

        self.inputs_df = inputs
        self.actions_df = actions

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

        self.opening = pd.Series()

    def return_location(self) -> pd.Series:
        """Wrapper to return a pandas friendly starting position object"""
        return pd.Series({"StartingLocation": self.starting_position})

    def return_civilisation(self) -> pd.Series:
        """Wrapper to return civilisation"""
        return pd.Series({"Civilisation": self.civilisation})

    def identify_technology_research_and_time(self, technology, civilisations: dict = None) -> pd.Timedelta:
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
        relevent_research = self.research_techs.loc[self.research_techs["param"] == technology, "timestamp"]  # handle unqueue

        # TODO - map the research times and then apply them, find a good way to house this data (tiny data with civ?)
        # TODO work out how to handle shorter time with civilisation parameter

        if relevent_research.empty:
            # Should return empty series instead? for type safety? hmm TODO
            # TODO log if cannot find
            return None

        return relevent_research.iloc[len(relevent_research) - 1]  # using len here handles multiple like a cancel and re-research

    def identify_building_and_timing(self, building, civilisations: dict = None) -> pd.DataFrame:
        """Helper to find all the creations of an economic building type. TODO Build times.

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

        relevent_building = self.economic_buildings_created.loc[
            self.economic_buildings_created["param"] == building,
            ["timestamp", "player"]
            ]

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

        loom_in_dark_age = loom_time < feudal_time

        villager_creation_time = 25  # TODO handle other civs that have special things like chinese, Mayans, Hindustanis

        villager_analysis = feudal_time / villager_creation_time
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

        # TODO identify the time the militia rock up to the opponents base - click within certain distance
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
                                         units_queued: pd.DataFrame
                                         ) -> pd.Series:
        """Draws out the base military decisions in feudal age, e.g. buildings created, number of units, etc.

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
        feudal_military_buildings = self.military_buildings_created.loc[
            ((self.military_buildings_created["param"] == "Archery Range") |
             (self.military_buildings_created["param"] == "Stable")) &
            (self.military_buildings_created["timestamp"] > feudal_time) &
            (self.military_buildings_created["timestamp"] < castle_time),
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
        # non_spear_military_units = feudal_military_units.loc[feudal_military_units["param"] != "Spearman", :]  # TODO

        # Extract time to 3 of first units
        # TODO - need to build out a method for working out when an object could produce a unit
        # TODO Extract idle time of first military building - best method is with object that handles queue length times

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

    def extract_feudal_and_dark_age_economics(self,
                                              feudal_time: pd.Timedelta,
                                              castle_time: pd.Timedelta,
                                              ) -> pd.Series:
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

        # Return castle age time! the most important
        stats_to_return = {
            "CastleTime": castle_time,
        }

        return pd.Series(stats_to_return)

    def extract_player_choices_and_strategy(self) -> pd.Series:
        # TODO mine civilisations
        # TODO mine if boar or elephant
        # TODO mine if scout lost
        # TODO identify what it looks like if a player un-queus a unit

        # Extract the key statistics / data points
        # research times to mine out
        self.feudal_time = self.identify_technology_research_and_time("Feudal Age")  # Get feudal times of the players
        self.castle_time = self.identify_technology_research_and_time("Castle Age")
        self.loom_times = self.identify_technology_research_and_time("Loom")  # Get loom time

        # Military timings to mine out
        self.maa_time = self.identify_technology_research_and_time("Man-At-Arms")  # TODO check name

        # economic times to mine out
        self.all_mill_times = self.identify_building_and_timing("Mill")
        first_mill_time = self.all_mill_times["timestamp"].min()

        self.dark_age_stats = self.extract_feudal_time_information(
            feudal_time=self.feudal_time,
            loom_time=self.loom_times
        )

        self.opening = pd.concat([self.opening, self.dark_age_stats])  # include self as is it empty series

        # Identify Feudal Age Strategy
        self.opening_strategy = self.extract_opening_strategy(
            feudal_time=self.feudal_time,
            castle_time=self.castle_time,
            military_buildings_spawned=self.military_buildings_created,
            mill_created_time=first_mill_time,
            units_queued=self.queue_units,
            maa_upgrade=self.maa_time,
        )

        self.feudal_economic_choices_and_castle_time = self.extract_feudal_and_dark_age_economics(
            castle_time=self.castle_time,
            feudal_time=self.feudal_time
        )

        self.opening = pd.concat([self.opening, self.opening_strategy, self.feudal_economic_choices_and_castle_time])

        return self.opening


class AgeMap:
    """Data structure representing the AOE2 map. Goal of identifying and extracting map features for analysis
    """
    def __init__(self, map: dict, gaia: dict, player_starting_locations: list) -> None:
        """Reconstruct the key features of the map - terrain, relics, resources (trees, gold, stone, berries).
        Store this information in a dataframe"""
        # TODO do something with deer/ostrich/zebra

        # Map object
        self.map: dict = map  # Store map object
        self.map_size_int: int = map["dimension"]  # The size of the map (note map is always square)
        self.map_name: str = self.map["name"]
        self.elevation_map: pd.DataFrame = pd.DataFrame(self.map["tiles"])  # Elevation of each tile
        # Explode out dict into cols for x + y
        self.elevation_map = self.elevation_map.join(self.elevation_map["position"].apply(pd.Series), validate="one_to_one")

        # Dsitribution of starting objects
        self.tiles_raw: dict = gaia
        self.tiles = pd.DataFrame(gaia)
        self.tiles = self.tiles.join(self.tiles["position"].apply(pd.Series), validate="one_to_one")  # Explode out dict into cols for x + y
        # TODO clean up dataframes

        self.player_locations = player_starting_locations

        self.tiles["name"] = self.tiles["name"].str.replace(r"\s\(.*\)", "", regex=True)  # Remove anything in brackets - treat together

        # TODO wrap this is some extraction and analysis functions for more readable code

        # Identify islands (groups) of resources for minin information from later
        # TODO handle that Fruit Bush == Berries in this case
        resources_to_identify = ["Fruit Bush", "Gold Mine", "Stone Mine", "Tree"]
        self.resource_labels = [self.identify_islands_of_resources(self.tiles, resource=res) for res in resources_to_identify]

        # Take all the resource labels and merge onto main tiles dataframe
        for res in self.resource_labels:
            self.tiles = self.tiles.merge(res.drop(columns=["x", "y"]), on="instance_id", how="left")

        # Flag resources that are in between the players
        # Identify the corners of the corridor between players
        self.corridor_between_players = self.identify_pathway_between_players()  # List of tuples

        resources_to_check_between_players = ["Fruit Bush", "Gold Mine", "Stone Mine", "Tree"]  # Check these resources

        # Apply for each resource - check if it is in polygon
        list_dfs_of_resources_between_players = [
            self.identify_resources_or_feature_between_players(
                map_feature_locations=self.tiles.loc[self.tiles[res] > 0, :],
                polygon_to_check_within=self.corridor_between_players
            ) for res in resources_to_check_between_players
            ]

        df_resources_between_players = pd.concat(list_dfs_of_resources_between_players)

        # Merge DF of all resources that are between
        self.tiles = self.tiles.merge(df_resources_between_players, on="instance_id", how="left")
        print("check merge")

        # TODO now actually analyse this model of the map
        print("Break - test accurately got flag")

    def assign_resource_island_to_player(self)-> pd.DataFrame:
        # Identify the main resources around a player and assign to that player for further analysis
        pass

    def identify_pathway_between_players(self) -> list:
        """Idenitfy a corridor between players. 
        Use this to find key features in main battlefields, like trees, resources, large hills etc."""
        # TODO think about making this like a cone @ each players base, and identify a different polygon for their sides
        # Identify the vector between players
        # dx = x2 - x1, dy = y2 - y1
        dx, dy = (self.player_locations[0][0] - self.player_locations[1][0],
                  self.player_locations[0][1] - self.player_locations[1][1])

        # Normalise the vector
        magnitude = math.sqrt(dx**2 + dy**2)  # Cartesian length
        dx, dy = dx/magnitude, dy/magnitude

        # Identify the tangential direction to this vector
        # for a vector (dx, dy), the tangents from the same starting points are (-dy, dx) and (dy, -dx)
        # Identify the 4 corners of the plane by taking the starting locations and going 25 tiles in either of the normal directions
        # example: c1 = (x_1, y_1) + (dy, -dx)
        c1 = (self.player_locations[0][0] + dy*25, self.player_locations[0][1] - dx*25)
        c2 = (self.player_locations[0][0] - dy*25, self.player_locations[0][1] + dx*25)
        c3 = (self.player_locations[1][0] + dy*25, self.player_locations[1][1] - dx*25)
        c4 = (self.player_locations[1][0] - dy*25, self.player_locations[1][1] + dx*25)

        return [c1, c2, c3, c4]

    def identify_key_hills_between_players(self):
        # TODO
        pass

    def identify_resources_or_feature_between_players(self, 
                                                      map_feature_locations: pd.DataFrame, 
                                                      polygon_to_check_within: list
                                                      ) -> pd.Series:
        """Identify the # of a map feature between players. Models scenarios such as large forests that units must move around, 
        or can identify forward golds"""
        # TODO generalise this to just polygons, so that the sides can be checked for resources
        poly = Polygon(polygon_to_check_within)
        map_feature_locations["BetweenPlayers"] = map_feature_locations.apply(lambda x: Point(x["x"], x["y"],).within(poly), axis=1)
        return map_feature_locations.loc[:, ["instance_id", "BetweenPlayers"]]

    def identify_player_front_gold(self):
        """ Analysis Function"""
        # TODO or how forward a gold is with some sort of modelling
        # TODO gold is on a hill, main gold
        # TODO identify clusters of gold
        pass

    def identify_player_wood_setup(self):
        """Analysis Function"""
        # TODO
        pass

    def identify_islands_of_resources(self, dataframe_of_map: pd.DataFrame, resource: str) -> pd.DataFrame:
        """Search for islands of resrouces in the 2D image of the map. Label the dataframe of resources with groups found"""
        # See some resources: https://stackoverflow.com/questions/46737409/finding-connected-components-in-a-pixel-array
        # https://docs.scipy.org/doc/scipy-0.16.0/reference/generated/scipy.ndimage.measurements.label.html
        # https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.label.html#scipy.ndimage.label

        df = dataframe_of_map[["y", "x", "instance_id", "name"]]  # Reduce columns
        # The AOE Game engine starts these objects in the centre of the tile. Remove the decimal if it exists.
        df.loc[:, ["x", "y"]] = np.floor(df[["x", "y"]]).astype(np.int32)  # remove decimal of floats
        df = df.loc[df["name"] == resource, ["x", "y", "instance_id"]]

        map_of_resources = np.zeros((self.map_size_int, self.map_size_int))
        for index, row in df.iterrows():
            # Not the fastest or most pythonic but quickest to write the code
            map_of_resources[int(row["x"]), int(row["y"])] = 1

        s = generate_binary_structure(2, 2)  # Creates a 3x3 matrix of 1's. Pass as structure to label to allow diagnoal check
        labeled_array, num_features = label(map_of_resources, structure=s)

        for label_index in range(1, num_features + 1):
            coords = np.where(labeled_array == label_index)
            for x, y in zip(coords[0], coords[1]):
                df.loc[(df["x"] == int(x)) & (df["y"] == int(y)), resource] = label_index

        return df


class AgeGame:
    """A small wrapper for understanding an AOE game. Should just be a container for the mgz game which I can start to unpack
    """
    def __init__(self, path: Path) -> None:
        self.path_to_game: Path = path

        with open(self.path_to_game, "rb") as g:
            self.match = parse_match(g)
            self.match_json = serialize(self.match)

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

        # Get features of the map in the AgeMap object
        self.game_map = AgeMap(
            map=self.match_json["map"],
            gaia=self.match_json["gaia"],
            player_starting_locations=[tuple(self.match_json["players"][0]["position"].values()),
                                       tuple(self.match_json["players"][1]["position"].values())]
        )
        self.game_map.tiles.to_csv("Map.csv")

        # Transform raw data into usable chunks
        self.all_inputs_df = pd.json_normalize(self.inputs)
        self.all_actions_df = pd.json_normalize(self.actions)

        # Store list of players as GamePlayer objects; this stores indivdual data and data mining methods
        self.players_raw_info = self.match_json["players"]  # List of dictionaries, including civilisations; location;
        self.players = [GamePlayer(
            number=player["number"],
            name=player["name"],
            civilisation=player["civilization"],
            starting_position=player["position"],
            elo=player["rate_snapshot"],
            winner=player["winner"],
            actions=self.all_actions_df.loc[self.all_actions_df["player"] == player["number"], :],
            inputs=self.all_inputs_df.loc[self.all_inputs_df["player"] == player["number"], :]
            ) for player in self.players_raw_info]

        return

    def explore_games(self) -> None:
        # Current knowledge - check out the objects added to the game

        print("use this as a breakpoint")

        return

    def extract_map_features(self) -> pd.Series:
        # TODO
        # hills between players?
        # number of trees directly between players / in corridor
        # Idea for lumber camps - % of front covered by trees - maybe divide into quarters?
        return

    def calculate_distance_between_players(self, location_one: tuple, location_two: tuple) -> pd.Series:  # TODO or list
        return math.dist(location_one, location_two)

    def calculate_difference_in_elo(self, player_one: GamePlayer, player_two: GamePlayer):
        if player_one.player_won:
            return player_one.elo - player_two.elo
        return player_two.elo - player_one.elo

    def advanced_parser(self) -> None:
        # TODO get the winner from players
        # TODO mine if boar or elephant
        # TODO mine if scout lost --> probably cant
        # TODO identify what it looks like if a player un-queus a unit

        # Extract the key statistics / data points
        # research times to mine out
        self.opening = pd.Series()
        self.game_results = pd.Series()

        # Identify the opening strategy and choices of each player
        for player in self.players:
            player_opening_strategies = player.extract_player_choices_and_strategy()
            player_opening_strategies = player_opening_strategies.add_prefix(f"Player{player.number}.")
            self.opening = pd.concat([self.opening, player_opening_strategies])

            location_and_civilisation = pd.concat([player.return_civilisation(), player.return_location()])
            location_and_civilisation = location_and_civilisation.add_prefix(f"Player{player.number}.")

            self.game_results = pd.concat([self.game_results, location_and_civilisation, self.opening])

        # Distance between players
        self.game_results["DistanceBetweenPlayers"] = self.calculate_distance_between_players(
            location_one=self.game_results["Player1.StartingLocation"],
            location_two=self.game_results["Player2.StartingLocation"]
        )

        # Elo difference between players - negative is winner is lower elo
        self.game_results["DifferenceInELO"] = self.calculate_difference_in_elo(
            player_one=self.players[0],
            player_two=self.players[1]
        )

        return


if __name__ == "__main__":

    test_file = Path("Test_Games/SD-AgeIIDE_Replay_324565276.aoe2record")

    test_match = AgeGame(path=test_file)
    test_match.advanced_parser()
    print("\n")
    print(test_match.game_results)
    test_match.game_results.to_csv("Test_Games/Test_results.csv")
