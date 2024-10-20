import numpy as np
import pandas as pd
# import json
# import os
import math
from scipy.ndimage import label, generate_binary_structure
from scipy.spatial import distance
from shapely import Point, Polygon
import logging
from pathlib import Path
# from datetime import datetime
# from mgz import header, fast, body
# from mgz.enums import ObjectEnum, ResourceEnum
# from mgz.summary import Summary
from mgz.model import parse_match, serialize
# from utils import GamePlayer, AgeGame  # buildings model
# import utils

from enums import (  # Getting a bit too cute here with constants but it will do for now
    BuildTimesEnum,
    TechnologyResearchTimes,
    # UnitCreationTime,
    MilitaryBuildings,
    FeudalAgeMilitaryUnits,
    # ArcheryRangeUnits,
    # StableUnits,
    # SiegeWorkshopUnits
)

from utils import ArcheryRangeProductionBuildingFactory, StableProductionBuildingFactory, SiegeWorkshopProductionBuildingFactory

logger = logging.getLogger(__name__)
logging.basicConfig(filename='AdvancedParser.log', encoding='utf-8', level=logging.DEBUG)


# step one - identify the things within an AOE game that I can find, publish this as a package;
# e.g. how close the map is; front or back woodlines, civs, winner, units created, timings etc.

# idea for structure - design a player that keeps track of their actions and their location and stuff
# Also have production building modelling
# store this within game; use to mine features for analysis
# construct a timeline? timeseries data?

# TODO handle free techs in economic analysis - Bohemians, Franks, Burmese, Vikings
# TODO Malians university faster research

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

        self.number: int = number
        self.name: str = name
        self.civilisation: str = civilisation  # Comes as dict with x and y - store as tuple for arithmetic
        self.starting_position: tuple = (starting_position["x"], starting_position["y"])
        self.player_won: bool = winner
        self.elo: int = elo

        self.inputs_df: pd.DataFrame = inputs
        self.actions_df: pd.DataFrame = actions

        self.opening = pd.Series()

        # Data formatting - parse str to timestamp
        self.inputs_df["timestamp"] = pd.to_timedelta(self.inputs_df["timestamp"])
        self.actions_df["timestamp"] = pd.to_timedelta(self.actions_df["timestamp"])

        # self.actions_df.to_csv(Path(f"DataExploration/Player{self.number}_actions.csv"))
        # self.inputs_df.to_csv(Path(f"DataExploration/Player{self.number}_inputs.csv"))

        # all techs researched
        self.research_techs = self.inputs_df.loc[self.inputs_df["type"] == "Research", :]

        # Buildings created
        all_buildings_created = self.inputs_df.loc[(self.inputs_df["type"] == "Build") | (self.inputs_df["type"] == "Reseed"), :]
        # Split into military production buildings and everything else
        self.military_buildings_created = all_buildings_created[
            all_buildings_created.loc[:, "param"].isin(MilitaryBuildings)
            ].copy()

        self.economic_buildings_created = all_buildings_created[
            ~all_buildings_created.loc[:, "param"].isin(MilitaryBuildings)
            ].copy()

        # Player walls - Palisade Wall(s) and Stone Wall(s)
        self.player_walls = self.inputs_df.loc[self.inputs_df["type"] == "Wall", :]

        # Units and unqueing. Note that unqueuing is not possible to handle...
        self.queue_units = self.inputs_df.loc[self.inputs_df["type"] == "Queue", :]
        self.unqueue_units = self.inputs_df.loc[self.inputs_df["type"] == "Unqueue", :]

        self.archery_ranges = ArcheryRangeProductionBuildingFactory().create_production_building_and_remove_used_id(
            inputs_data=self.inputs_df,
            player=self.number
        )
        if len(self.archery_ranges) > 0:
            self.archery_units = pd.concat([range_.produce_units() for range_ in self.archery_ranges])
        else:
            self.archery_units = pd.DataFrame()

        self.stables = StableProductionBuildingFactory().create_production_building_and_remove_used_id(
            inputs_data=self.inputs_df,
            player=self.number
        )
        if len(self.stables) > 0:
            self.stable_units = pd.concat([stable.produce_units() for stable in self.stables])
        else:
            self.stable_units = pd.DataFrame()

        self.siege_shops = SiegeWorkshopProductionBuildingFactory().create_production_building_and_remove_used_id(
            inputs_data=self.inputs_df,
            player=self.number
        )
        if len(self.siege_shops) > 0:
            self.siege_units = pd.concat([seige_shop.produce_units() for seige_shop in self.siege_shops])
        else:
            self.siege_units = pd.DataFrame()

        self.military_units = pd.concat([self.archery_units, self.stable_units, self.siege_units])
        # TODO - barracks, castle, donjon, dock. Lots of boiler plate

    def full_player_choices_and_strategy(self) -> pd.Series:
        """Main API - call to analyse the player's choices"""

        # Extract the key statistics / data points
        # research age timings and loom to mine out
        self.feudal_time = self.identify_technology_research_and_time("Feudal Age", civilisation=self.civilisation)
        self.castle_time = self.identify_technology_research_and_time("Castle Age", civilisation=self.civilisation)
        self.loom_times = self.identify_technology_research_and_time("Loom", civilisation=self.civilisation)  # Get loom time

        self.dark_age_stats = self.extract_feudal_time_information(
            feudal_time=self.feudal_time,
            loom_time=self.loom_times
        )

        # Identify Feudal and Dark Age military Strategy
        self.opening_strategy = self.extract_opening_strategy(
            feudal_time=self.feudal_time,
            castle_time=self.castle_time,
            military_buildings_spawned=self.military_buildings_created,
            units_queued=self.military_units,
        )

        # Identify Feudal and Dark Age economic choices
        self.feudal_economic_choices_and_castle_time = self.extract_early_game_economic_strat(
            castle_time=self.castle_time,
            feudal_time=self.feudal_time,
            player_eco_buildings=self.economic_buildings_created,
            player_walls=self.player_walls.loc[self.player_walls["payload.building"] == "Palisade Wall", :]
        )

        self.opening = pd.concat([self.opening, self.dark_age_stats, self.opening_strategy, self.feudal_economic_choices_and_castle_time])

        return self.opening

    def identify_location(self) -> pd.Series:
        """Wrapper to return a pandas friendly starting position object"""
        return pd.Series({"StartingLocation": self.starting_position})

    def identify_civilisation(self) -> pd.Series:
        """Wrapper to return civilisation"""
        return pd.Series({"Civilisation": self.civilisation})

    def identify_technology_research_and_time(self, technology: str, civilisation: str = None) -> pd.Timedelta:
        """A helper method that can identify when players research certain things and the timing of that

        :param technology: technology being researches
        :type technology: str
        :param civilisations: civilisations to handle faster research times, defaults to None
        :type civilisations: dict, optional
        :raises ValueError: incorrect technology passed
        :return: data frame with the time each player researched and completed the technology
        :rtype: pd.DataFrame
        """
        enum_technology = technology.replace(" ", "_").replace("-", "_")  # TODO for cleanliness, think about handling this in Enum methods

        if not TechnologyResearchTimes.has_value(enum_technology):
            logger.error(f"Technology given to find technology research function incorrect. Tech was: {technology}")
            raise ValueError(f"Couldn't find technology: {technology}")

        time_to_research = TechnologyResearchTimes.get(enum_technology, civilisation=civilisation)

        # TODO check why there is two clicks - maybe one for queue and one for actually clicking up?
        # Handle two clicks
        relevent_research = self.research_techs.loc[self.research_techs["param"] == technology, "timestamp"]  # handle unqueue

        if relevent_research.empty:
            # TODO log if cannot find
            return None

        # using len here handles multiple like a cancel and re-research
        return relevent_research.iloc[len(relevent_research) - 1] + pd.Timedelta(seconds=time_to_research) 

    def identify_building_and_timing(self, building, civilisation: str = None) -> pd.DataFrame:
        """Helper to find all the creations of an economic building type.

        :param building: the string name of the building. See enums for validation. Errors if incorrect
        :param civilisations: player's civilisation, defaults to None
        :raises ValueError: _description_
        :return: df with all the instances of building creation and time of completion
        :rtype: pd.DataFrame
        """

        enum_building_name = building.replace(" ", "_").replace("-", "_")  # TODO for cleanliness, think about handling this in Enum methods

        if not BuildTimesEnum.has_value(enum_building_name):
            logger.error(f"Building given to find building method incorrect. Building was: {building}")
            raise ValueError(f"Couldn't find building: {building}")

        time_to_build = BuildTimesEnum.get(enum_building_name, civilisation=civilisation)

        relevent_building = self.economic_buildings_created.loc[
            self.economic_buildings_created["param"] == building,
            ["timestamp", "player", "payload.object_ids"]
            ]
        if relevent_building.empty:
            # TODO log this and return empty data frame but with correct columns - handle accordingly
            return relevent_building

        relevent_building["NumberVillsBuilding"] = relevent_building["payload.object_ids"].apply(lambda x: len(x))
        relevent_building["TimeToBuild"] = (3*time_to_build)/(relevent_building["NumberVillsBuilding"] + 2)
        relevent_building["TimeToBuild"] = pd.to_timedelta(relevent_building["TimeToBuild"])
        relevent_building["timestamp"] = relevent_building["timestamp"] + relevent_building["TimeToBuild"]

        return relevent_building

    def extract_feudal_time_information(self, feudal_time: pd.Timedelta, loom_time: pd.Timedelta, civilisation: str = None) -> pd.Series:
        """_summary_

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

    def extract_opening_strategy(self,
                                 feudal_time: pd.Timedelta,
                                 castle_time: pd.Timedelta,
                                 military_buildings_spawned: pd.DataFrame,
                                 units_queued: pd.DataFrame,
                                 ) -> pd.Series:
        """Function that identifies military stratgy. Uses Militia and Feudal military methods"""
        # time of maa tech for maa function
        maa_time = self.identify_technology_research_and_time("Man-At-Arms", civilisation=self.civilisation)
        # time of first mill for maa function
        self.all_mill_times = self.identify_building_and_timing("Mill")
        first_mill_time = self.all_mill_times["timestamp"].min()

        # identify drush and categorise into MAA/Pre-mill/Drush
        dark_age_approach = self.militia_based_strategy(
            castle_time=castle_time,
            military_buildings_spawned=military_buildings_spawned,
            mill_created_time=first_mill_time,
            units_created=units_queued,
            maa_upgrade=maa_time
        )  # TODO - identify towers or a fast castle

        feudal_approach = self.feudal_military_choices(
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

    def militia_based_strategy(self,
                               castle_time: pd.Timedelta,
                               military_buildings_spawned: pd.DataFrame,
                               mill_created_time: pd.Timedelta,
                               units_created: pd.DataFrame,
                               maa_upgrade: pd.Timedelta = None
                               ) -> pd.Series:
        """Logic to identify groups of MAA or Militia based strategy: MAA, pre-mill drush, drush"""
        # Identify key timings and choices associated with these strategies
        dark_age_feudal_barracks = military_buildings_spawned.loc[(military_buildings_spawned["param"] == "Barracks") &
                                                                  (military_buildings_spawned["timestamp"] < castle_time), :]
        first_barracks_time = dark_age_feudal_barracks["timestamp"].min()
        pre_mill_barracks = first_barracks_time < mill_created_time
        militia_created = units_created.loc[(units_created["param"] == "Militia") &
                                           (units_created["UnitCreatedTimestamp"] < castle_time), :]

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

    def feudal_military_choices(self,
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
        feudal_military_units = units_queued.loc[(units_queued["param"].isin(FeudalAgeMilitaryUnits)) &
                                                 (units_queued["UnitCreatedTimestamp"] < castle_time),
                                                 :
                                                 ]

        # Count of each military unit
        number_of_each_unit = feudal_military_units.groupby("param").count()["UnitCreatedTimestamp"]

        # Handle instance where they do not produce this unit
        for unit in FeudalAgeMilitaryUnits:
            if unit not in number_of_each_unit.index:
                number_of_each_unit[unit] = 0

        # Non spear units - to identify strategy
        # non_spear_military_units = feudal_military_units.loc[feudal_military_units["param"] != "Spearman", :]  # TODO

        # Extract time to 3 of first units

        military_stats_to_return = {
            "OpeningMilitaryBuildingTime": opening_timing.iloc[0],
            "OpeningMilitaryBuilding": opening_military_building.iloc[0],
        }

        return pd.concat([pd.Series(military_stats_to_return), number_of_each_unit])

    def extract_early_game_economic_strat(self,
                                          feudal_time: pd.Timedelta,
                                          castle_time: pd.Timedelta,
                                          player_eco_buildings: pd.DataFrame,
                                          player_walls: pd.DataFrame,
                                          ) -> pd.Series:

        # TODO - extract information from the dark age: sheep, deer, boars, berries
        # dark_age_economic_development = self.extract_dark_age_economic_tactics()

        # Feudal age wood and farm upgrade;
        double_bit_axe_time = self.identify_technology_research_and_time("Double-Bit Axe", civilisation=self.civilisation)
        horse_collar_time = self.identify_technology_research_and_time("Horse Collar", civilisation=self.civilisation)
        wheelbarrow_time = self.identify_technology_research_and_time("Wheelbarrow", civilisation=self.civilisation)

        feudal_technology_times = pd.Series({"DoubleBitAxe": double_bit_axe_time,
                                             "HorseCollar": horse_collar_time,
                                             "Wheelbarrow": wheelbarrow_time
                                             })

        # Extract how quickly they develop their farming economy
        farm_development = self.farm_economic_development(feudal_time, castle_time, player_eco_buildings)
        # Extract when/if they choose to wall their map
        walling_tactics = self.walling_tactics(feudal_time, castle_time, player_eco_buildings, player_walls)

        # Concat to pandas series and return
        stats_to_return = pd.concat([feudal_technology_times, farm_development, walling_tactics])
        return stats_to_return

    def dark_age_economic_tactics(self) -> pd.Series:
        # dark age number of deer taken
        # dark age number of boars/rhinos taken
        # dark age number of sheep taken
        # dark age time of mill on berries + number of vils on berries
        pass

    def farm_economic_development(self,
                                  feudal_time: pd.Timedelta,
                                  castle_time: pd.Timedelta,
                                  player_eco_buildings: pd.DataFrame,
                                  ) -> pd.Series:
        """Parse the economic buildings created for farms built and reseeded; note timing

        :param feudal_time: _description_
        :param castle_time: _description_
        :param player_eco_buildings: _description_
        :return: _description_
        :rtype: pd.Series
        """
        # feudal age number of farms
        # find all "Reseed" inputs and "Build - Farm actions"
        # TODO - understand if a built farm is deleted
        farms_in_feudal = player_eco_buildings.loc[
            (player_eco_buildings["payload.building"] == "Farm") &
            (player_eco_buildings["timestamp"] > feudal_time) &
            (player_eco_buildings["timestamp"] < castle_time),
            :
        ]
        number_farms_made = len(farms_in_feudal)
        # time of 3, 6, 10, 15, 20 farms
        farms_results = pd.Series({"TimeThreeFarms": None,
                                   "TimeSixFarms": None,
                                   "TimeTenFarms": None,
                                   "TimeFifteenFarms": None,
                                   "TimeTentyFarms": None
                                   })
        # Iterate through the number of farms, with the series key and the index number
        for key, farms_number in zip(farms_results.index.to_list(), [2, 5, 9, 14, 19]):
            if number_farms_made >= farms_number:
                # Need guard statement incase dataframe is not long enough
                farms_results.loc[key] = farms_in_feudal.iloc[farms_number-1, :]["timestamp"]
        farms_results = pd.concat([pd.Series({"NumberFeudalFarms": number_farms_made}), farms_results])

        return farms_results

    def walling_tactics(self,
                        feudal_time: pd.Timedelta,
                        castle_time: pd.Timedelta,
                        player_eco_buildings: pd.DataFrame,
                        player_walls: pd.DataFrame
                        ) -> pd.Series:
        """Helper function to extract walls built in the early game
        :param feudal_time: _description_
        :param castle_time: _description_
        :param player_eco_buildings: _description_
        :return: _description_
        :rtype: pd.Series
        """
        # Note on houses - include as a proxy for fortifying your map/walls in the mid game (feudal - castle)
        # Walls - # calculate chebyshev distance of each wall segment - sum in each age
        palisade_walls = player_walls.loc[player_walls["payload.building"] == "Palisade Wall", :]
        # Calculate chebyshev distance between the wall start and end to get # of tiles
        palisade_walls["NumberTilesPlaced"] = palisade_walls.apply(lambda x: distance.chebyshev(
            x[["position.x", "position.y"]], x[["payload.x_end", "payload.y_end"]]
            ), axis=1)
        dark_age_walls = palisade_walls.loc[palisade_walls["timestamp"] < feudal_time, "NumberTilesPlaced"].sum()
        feudal_age_walls = palisade_walls.loc[
            (palisade_walls["timestamp"] >= feudal_time) &
            (palisade_walls["timestamp"] <= castle_time),
            "NumberTilesPlaced"
        ].sum()
        post_castle_walls = palisade_walls.loc[palisade_walls["timestamp"] > castle_time, "NumberTilesPlaced"].sum()

        # Houses - for the moment limit to feudal. Number of Houses is probably a poor proxy for identifying walling tactics,
        # as they aren't always used to reinforce walls
        # Some sort of really complicated location analysis would be required to amend this - I will not go down this path.
        houses_built = player_eco_buildings.loc[player_eco_buildings["payload.building"] == "House", "timestamp"]
        feudal_houses = len(houses_built.loc[(houses_built > feudal_time) & (houses_built < castle_time)])

        walling_results = pd.Series({
            "DarkAgeWallsNumber": dark_age_walls,
            "FeudalWallsNumber": feudal_age_walls,
            "PostCastleWalls": post_castle_walls,
            "FeudalHousesBuilt": feudal_houses
        })

        return walling_results


class AgeMap:
    """Data structure representing the AOE2 map. Goal of identifying and extracting map features for analysis
    """
    def __init__(self, map: dict, gaia: dict, player_starting_locations: list) -> None:
        """Reconstruct the key features of the map - terrain, relics, resources (trees, gold, stone, berries).
        Store this information in a dataframe"""

        # Map object
        self.map: dict = map  # Store map object
        self.map_size_int: int = map["dimension"]  # The size of the map (note map is always square)
        self.map_name: str = self.map["name"]

        # Distribution of starting objects
        self.tiles_raw: dict = gaia
        self.tiles = pd.DataFrame(gaia)
        self.tiles = self.tiles.join(self.tiles["position"].apply(pd.Series), validate="one_to_one")  # Explode out dict into cols for x + y

        self.tiles["x"] = self.tiles["x"].astype(int) 
        self.tiles["y"] = self.tiles["y"].astype(int)

        self.elevation_map: pd.DataFrame = pd.DataFrame(self.map["tiles"])  # Elevation of each tile
        # Explode out dict into cols for x + y
        self.elevation_map = self.elevation_map.join(self.elevation_map["position"].apply(pd.Series), validate="one_to_one")
        self.elevation_map = self.elevation_map.drop(columns=["position", "terrain"])  # clean up columns

        # Join elevation on - note have to use x and y as ofc no object ID for terrain
        self.tiles = self.tiles.merge(self.elevation_map, on=["x", "y"], how="left")

        self.player_locations = player_starting_locations
        # Judge a hill for each player res by elevation greater than starting location; could think of a more elegant solution
        self.height_of_player_locations = [
            self.tiles.loc[(self.tiles["x"] == player[0]) & (self.tiles["y"] == player[1]), "elevation"].mean()
            for player in self.player_locations
            ]

        # Data parsing - coerce some varied names to regular ones.
        # Remove anything in brackets - treat together (trees)
        self.tiles["name"] = self.tiles["name"].str.replace(r"\s\(.*\)", "", regex=True)
        # Coerce different types of starting food into one type for processing
        self.tiles["name"] = self.tiles["name"].str.replace(pat="(Forage Bush)|(Berry Bush)", repl="Fruit Bush", regex=True)
        self.tiles["name"] = self.tiles["name"].str.replace(pat="(Llama)|(Goat)|(Goose)|(Turkey)|(Pig)|(Turkey)", repl="Sheep", regex=True)
        self.tiles["name"] = self.tiles["name"].str.replace(pat="(Zebra)|(Ostrich)|(Ibex)|(Gazelle)", repl="Deer", regex=True)
        self.tiles["name"] = self.tiles["name"].str.replace(pat="(Elephant)|(Rhinoceros)", repl="Wild Boar", regex=True)
        # TODO mark if elephant or rhino as more food
        # TODO maybe treat water buffalo and cows seperately... if needed

        # Identify islands (groups) of resources for minin information from later
        resources_to_check_between_players = ["Fruit Bush", "Gold Mine", "Stone Mine", "Tree"]  # Check these resources

        # Wrapper function that gets the following for the object and stores it in the object:
        # - Identifies islands of resources
        # - Identifies the polygon corridor between players
        # - Falgs the resources between the players
        self.process_resource_locations(resources_to_identify=resources_to_check_between_players)

        p_1_resource_analysis = self.analyse_map_features_for_player(player=1,
                                                                     player_resources=self.tiles.loc[self.tiles["ClosestPlayer"] == 1, :],
                                                                     min_height_for_hill=self.height_of_player_locations[0])

        p_2_resources_analysis = self.analyse_map_features_for_player(player=2,
                                                                      player_resources=self.tiles.loc[self.tiles["ClosestPlayer"] == 2, :],
                                                                      min_height_for_hill=self.height_of_player_locations[1])

        self.map_analysis = pd.concat([p_1_resource_analysis, p_2_resources_analysis])

        # TODO test results against actual

        return

    def analyse_map_features_for_player(self,
                                        player: int,
                                        player_resources: pd.DataFrame,
                                        min_height_for_hill: int) -> pd.Series:
        """analyse the main features of the players map, mining out key information like the state of their gold
        :param player: int for player number - to be used in return pd.Series name (i.e. "Player1")
        :param player_resources: dataframe of tiles with islands of resources
        :param min_height_for_hill: the height of the player TC. Above this, consider the spot a hill.
        :return: Series with analysis of maps for the players
        :rtype: pd.Series
        """
        # Rules:
        # - if its in the corrider, then it is "Front", else "Back". Maybe "exposed" is a better descriptor
        # - if the elevation is above the TC and "Front", then set to "Front Hill". For now, ignore back hills
        # Apply Y/N/Hill for front main gold, berries, secondary gold #1 and #2

        # For woodline (use fact they are much bigger):
        # - >= 60% in corridor = front woodline
        # - 20% - 60% = side woodline
        # - <= 20% = back woodline
        # number of front, back and side woodlines
        # back woodlines

        # Golds - identify main and secondary golds and get their dataframe
        golds = player_resources.loc[player_resources["name"] == "Gold Mine", :]
        sizes_of_golds = golds.groupby("Gold Mine").count()  # TODO there is a much better way of doing this - col for each type is not good
        main_gold_index = sizes_of_golds["instance_id"].idxmax()
        main_gold = player_resources.loc[player_resources["Gold Mine"] == main_gold_index]
        list_of_ids_for_secondary_golds = sizes_of_golds["instance_id"].drop(index=main_gold_index).index.to_list()
        secondary_gold_one = player_resources.loc[player_resources["Gold Mine"] == list_of_ids_for_secondary_golds[0]]
        secondary_gold_two = player_resources.loc[player_resources["Gold Mine"] == list_of_ids_for_secondary_golds[1]]

        # Apply rules to main gold - Back, Front or Front Hill
        main_gold_analysis = self.analyse_resource(
            main_gold["BetweenPlayers"].max(),
            bool(main_gold["elevation"].mean() > min_height_for_hill)
        )

        resource_analysis = pd.Series({f"Player{player}.MainGold": main_gold_analysis})

        # Apply logic to both secondary golds
        for index, gold in enumerate([secondary_gold_one, secondary_gold_two]):
            # Get name of gold for storing in dict
            gold_name = "SecondGold" if index == 1 else "ThirdGold"
            # Get bools for front/back and hill
            front_or_back = gold["BetweenPlayers"].max()
            hill = gold["elevation"].mean() > min_height_for_hill

            analysis_of_current_gold = self.analyse_resource(
                between_players=front_or_back,
                average_heigh_above_tc=hill
            )

            resource_analysis = pd.concat([resource_analysis, pd.Series({f"Player{player}.{gold_name}": analysis_of_current_gold})])

        # Identify berries
        berries = player_resources.loc[player_resources["name"] == "Fruit Bush", :]

        # Apply to analysis method (Hill/Front/Back) to berries
        berry_analysis = self.analyse_resource(
            between_players=berries["BetweenPlayers"].max(),
            average_heigh_above_tc=berries["elevation"].mean() > min_height_for_hill
        )
        resource_analysis = pd.concat(
            [resource_analysis, pd.Series({f"Player{player}.Berries": berry_analysis})]
        )

        # identify main stone
        stones = player_resources.loc[player_resources["name"] == "Stone Mine", :]
        sizes_of_stones = stones.groupby("Stone Mine").count()  # TODO there are better ways of doing this - col for each type is not good
        main_stone_index = sizes_of_stones["instance_id"].max()
        main_stone = player_resources.loc[player_resources["Stone Mine"] == main_stone_index]

        # Apply to analysis method (Hill/Front/Back) to stone
        stone_analysis = self.analyse_resource(
            between_players=main_stone["BetweenPlayers"].max(),
            average_heigh_above_tc=main_stone["elevation"].mean() > min_height_for_hill
        )

        resource_analysis = pd.concat(
            [resource_analysis, pd.Series({f"Player{player}.Stone": stone_analysis})]
        )

        # Identify and analyse structure of woodlines
        woodlines = player_resources.loc[player_resources["name"] == "Tree", :]

        # Apply woodlines analysis
        woodlines_analysis = self.analyse_player_woodlines(woodlines=woodlines, player_number=player)

        resource_analysis = pd.concat(
            [resource_analysis, woodlines_analysis]
        )

        # TODO add validation of format of resource analysis

        return resource_analysis

    def analyse_resource(self, between_players: bool, average_heigh_above_tc: bool) -> str:
        """ Categorise a resource into Front Hill / Front / Back depending on forwardness and hilliness"""
        match(between_players, average_heigh_above_tc):
            case (True, True):
                analysis = "Front Hill"
            case (True, False):
                analysis = "Front"
            case (False, _):
                analysis = "Back"
            case _:
                analysis = "Unknown"  # TODO log unknown
        return analysis

    def analyse_player_woodlines(self, woodlines: pd.DataFrame, player_number) -> pd.Series:
        """Categorise front/side/back woodlines and get count by #

        :param woodlines: DataFrame of tiles with woodlines, their player, and associated flags
        :param player_number:
        :return: series with summary information
        """
        woodlines_dict = {"Front": 0, "Side": 0, "Back": 0}
        for woodline_index in pd.unique(woodlines["Tree"]):
            wood = woodlines.loc[woodlines["Tree"] == woodline_index, :]
            number_trees_forward = len(wood.loc[wood["BetweenPlayers"], :])  # Relies on no duplicates see exception below
            total_trees = len(wood)

            if wood.groupby(["x", "y"]).ngroups != total_trees:
                raise Exception(f"Woodline number {woodline_index} has duplicate tiles")  # TODO proper logging

            if total_trees < 3:
                # Picked up stragglers around TC, disregard these
                continue

            if number_trees_forward/total_trees >= 0.6:
                woodlines_dict["Front"] += 1
            elif number_trees_forward/total_trees >= 0.2:
                woodlines_dict["Side"] += 1
            else:
                woodlines_dict["Back"] += 1
        woodlines_to_return = pd.Series(woodlines_dict)
        woodlines_to_return = woodlines_to_return.add_prefix(f"Player{player_number}.")
        return woodlines_to_return

    def process_resource_locations(self, resources_to_identify: list) -> None:
        """Helper function that wraps the primary set up of the resources on the Map for later analysis. The following tasks are completed:
            - Identifies islands of resources
            - Identifies the polygon corridor between players
            - Falgs the resources between the players
        Note this updates the self.tiles variable directly, as well as saving other pieces to the object

        :param resources_to_identify: List of strings, each of the strings being the name of a tile to process
        """
        # Identify islands (groups) of resources for minin information from later
        self.resource_labels = [self.identify_islands_of_resources(self.tiles, resource=res) for res in resources_to_identify]

        # Take all the resource labels and merge onto main tiles dataframe
        for res in self.resource_labels:
            self.tiles = self.tiles.merge(res.drop(columns=["x", "y"]), on="instance_id", how="left")

        # Flag resources that are in between the players
        # Identify the corners of the corridor between players
        self.corridor_between_players = self.identify_pathway_between_players()  # List of tuples

        # Apply for each resource - check if it is in polygon
        list_dfs_of_resources_between_players = [
            self.identify_resources_or_feature_between_players(
                map_feature_locations=self.tiles.loc[self.tiles[res] > 0, :],
                polygon_to_check_within=self.corridor_between_players
            ) for res in resources_to_identify
            ]

        df_resources_between_players = pd.concat(list_dfs_of_resources_between_players)

        # Merge DF of all resources that are between
        self.tiles = self.tiles.merge(df_resources_between_players, on="instance_id", how="left")

        # Max distance for resources to be considered close to players, as 0.4*distance between players
        distance_between_players = np.linalg.norm(
            (self.player_locations[0][0] - self.player_locations[1][0],
             self.player_locations[0][1] - self.player_locations[1][1]
             )
        )
        max_distance_to_players = 0.4*distance_between_players
        df_distances_to_players = self.assign_resource_island_to_player(
            map_feature_locations=self.tiles.copy(),
            maximum_distance_to_player=max_distance_to_players,
            player_locations=self.player_locations
        )

        self.tiles = self.tiles.merge(df_distances_to_players, on="instance_id", how="left")
        return

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

    def identify_resources_or_feature_between_players(self,
                                                      map_feature_locations: pd.DataFrame, 
                                                      polygon_to_check_within: list
                                                      ) -> pd.Series:
        """Identify the # of a map feature between players. Models scenarios such as large forests that units must move around, 
        or can identify forward golds"""
        # TODO generalise this to just polygons, so that the sides can be checked for resources
        poly = Polygon(polygon_to_check_within)
        map_feature_locations.loc[:, "BetweenPlayers"] = map_feature_locations.apply(lambda x: Point(x["x"], x["y"],).within(poly), axis=1)
        return map_feature_locations.loc[:, ["instance_id", "BetweenPlayers"]]

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

    def assign_resource_island_to_player(self,
                                         map_feature_locations: pd.DataFrame,
                                         maximum_distance_to_player: float,
                                         player_locations: list) -> pd.DataFrame:
        """Simply checks the distance from each resource to the players. Takes min distance as the appropriate player.
        Max distance is to prevent far away resources from being assigned. Should be approx 50% of the distance between players

        :param map_feature_locations: DataFrame with the tiles of interest to assign to each player
        :param maximum_distance_to_player: upper limit to assign a resource to person
        :param player_locations: tuple of ((x_1, y_1), (x_2,y_2))
        :return: Collumns of object ID, closest player, and distance to both players
        :rtype: pd.DataFrame
        """
        # Identify the main resources around a player and assign to that player for further analysis
        # Distance to player 1 = norm of vecotr: x_resource - x_player, y_resource - y_player
        map_feature_locations["DistancePlayer1"] = map_feature_locations.apply(
            lambda row: np.linalg.norm(
                (row["x"] - player_locations[0][0],
                 row["y"] - player_locations[0][1]
                 )),
            axis=1
        )
        # Same for location to second player
        map_feature_locations["DistancePlayer2"] = map_feature_locations.apply(
            lambda row: np.linalg.norm(
                (row["x"] - player_locations[1][0],
                 row["y"] - player_locations[1][1]
                 )),
            axis=1
        )

        map_feature_locations["ClosestPlayer"] = map_feature_locations.apply(
            lambda row: row[["DistancePlayer1", "DistancePlayer2"]].idxmin()
            if row[["DistancePlayer1", "DistancePlayer2"]].min() < maximum_distance_to_player else None,
            axis=1
        )

        map_feature_locations["ClosestPlayer"] = map_feature_locations["ClosestPlayer"].map({"DistancePlayer1": 1, "DistancePlayer2": 2})

        return map_feature_locations[["instance_id", "ClosestPlayer", "DistancePlayer1", "DistancePlayer2"]]


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
        self.player_map_analysis = self.game_map.map_analysis

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

    def calculate_distance_between_players(self, location_one: tuple, location_two: tuple) -> pd.Series:
        return math.dist(location_one, location_two)

    def calculate_difference_in_elo(self, player_one: GamePlayer, player_two: GamePlayer):
        if player_one.player_won:
            return player_one.elo - player_two.elo
        return player_two.elo - player_one.elo

    def advanced_parser(self) -> None:
        # TODO get the winner from players
        # TODO mine if boar or elephant

        # Extract the key statistics / data points
        # research times to mine out
        self.game_results = pd.Series()

        # Identify the opening strategy and choices of each player
        for player in self.players:
            player_opening_strategies = player.full_player_choices_and_strategy()
            player_opening_strategies = player_opening_strategies.add_prefix(f"Player{player.number}.")

            location_and_civilisation = pd.concat([player.identify_civilisation(), player.identify_location()])
            location_and_civilisation = location_and_civilisation.add_prefix(f"Player{player.number}.")

            self.game_results = pd.concat([self.game_results, player_opening_strategies, location_and_civilisation])

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
    # TODO think about the best structure of the module in order to create a good API and workflow
    # - what information is must-have, what is optional
    # - some sort of fast vs full API, or breaking up by sections of analysis
    # - Maybe an option is like Opening - Feudal - Castle - Map analyses

    # TODO change so that functions and methods have LESS SIDE EFFECTS - THEN CAN BE TESTED EFFECTIVELY
    # TODO errors and logging

    def main():

        # test_file = Path("../../Data/RawAoe2RecordBytes/SD-AgeIIDE_Replay_324565276.aoe2record")
        test_file = Path("Data/RawAoe2RecordBytes/AOE2ReplayBinary_2.aoe2record")  # ../../ Using a downloaded game from the scraper worked

        test_match = AgeGame(path=test_file)
        test_match.advanced_parser()
        print("\n")
        print(test_match.game_results)
        # print(test_match.player_map_analysis)
        test_results = pd.concat([test_match.game_results, test_match.player_map_analysis]).sort_index()
        test_results.to_csv("tests/Test_Games/Test_results.csv")

        return test_match.players[0].inputs_df

    test_inputs = main()

    # TODO Next castle age economic choices
    # And Next TODO is check order of players is correct and maybe validate map analysis
