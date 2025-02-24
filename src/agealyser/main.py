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
from typing import List
# from typeguard import typechecked

# from datetime import datetime
# from mgz import header, fast, body
# from mgz.enums import ObjectEnum, ResourceEnum
# from mgz.summary import Summary
from mgz.model import parse_match, serialize

# from utils import GamePlayer, AgeGame  # buildings model
# import utils

from .agealyser_enums import (
    BuildTimesEnum,
    TechnologyResearchTimes,
    # UnitCreationTime,
    MilitaryBuildings,
    FeudalAgeMilitaryUnits,
    TownCentreUnitsAndTechs,
    # ArcheryRangeUnits,
    # StableUnits,
    # SiegeWorkshopUnits
)

from .utils import (
    ArcheryRangeProductionBuildingFactory,
    BarracksProductionBuildingFactory,
    StableProductionBuildingFactory,
    SiegeWorkshopProductionBuildingFactory,
    TownCentreBuildingFactory,
    MGZParserException
)

logger = logging.getLogger(__name__)
logging.basicConfig(
    filename="AdvancedParser.log", encoding="utf-8", level=logging.DEBUG
)


# step one - identify the things within an AOE game that I can find, publish this as a package;
# e.g. how close the map is; front or back woodlines, civs, winner, units created, timings etc.

# idea for structure - design a player that keeps track of their actions and their location and stuff
# Also have production building modelling
# store this within game; use to mine features for analysis
# construct a timeline? timeseries data?

# TODO-feature handle free techs in economic analysis - Bohemians, Franks, Burmese, Vikings
# TODO-patch Malians university faster research


class GamePlayer:
    def __init__(
        self,
        number: int,
        name: str,
        civilisation: str,
        starting_position: dict,
        actions: pd.DataFrame,
        inputs: pd.DataFrame,
        winner: bool,
        elo: int,
    ) -> None:

        self.number: int = number
        self.name: str = name
        self.civilisation: str = civilisation

        # Comes as dict with x and y - store as tuple for arithmetic
        self.starting_position: tuple = (starting_position["x"], starting_position["y"])
        self.player_won: bool = winner
        self.elo: int = elo

        self.inputs_df: pd.DataFrame = inputs.copy()
        self.actions_df: pd.DataFrame = actions.copy()

        self.opening = pd.Series()

        # Data formatting - parse str to timestamp
        self.inputs_df.loc[:, "timestamp"] = pd.to_timedelta(
            self.inputs_df.loc[:, "timestamp"].copy()
        )
        self.actions_df.loc[:, "timestamp"] = pd.to_timedelta(
            self.actions_df.loc[:, "timestamp"].copy()
        )

        self.inputs_df["timestamp"] = self.inputs_df["timestamp"].astype(
            "timedelta64[ns]"
        )
        self.actions_df["timestamp"] = self.inputs_df["timestamp"].astype(
            "timedelta64[ns]"
        )

        # discovered an issue where records would be duplicated with around 0.2s apart
        # iterate through df. Identify duplicate records, then drop one if necessary
        to_drop_inputs = self.inputs_df[
            (self.inputs_df["timestamp"].diff() < pd.Timedelta(seconds=0.25))
            & (self.inputs_df["timestamp"] > pd.Timedelta(seconds=20))
            & (
                self.inputs_df.loc[:, ["type", "param", "payload.object_ids"]]
                .eq(
                    self.inputs_df.loc[
                        :, ["type", "param", "payload.object_ids"]
                    ].shift(1)
                )
                .all(axis=1)
            )
        ]
        to_drop_inputs = to_drop_inputs.loc[
            to_drop_inputs["type"] == "Queue", :
        ]  # remove anything that is not Queue after

        self.inputs_df = self.inputs_df.drop(to_drop_inputs.index)

        # self.actions_df.to_csv(Path(f"DataExploration/Player{self.number}_actions.csv"))
        # self.inputs_df.to_csv(Path(f"DataExploration/Player{self.number}_inputs.csv"))

        # all techs researched and their completion time
        research_techs = self.inputs_df.loc[
            self.inputs_df["type"] == "Research", :
        ].dropna(subset="param")
        # if a tech is added that is not captured by the AOE parser, it will throw an error for us because "" cannot be found in Enums
        research_techs = research_techs[research_techs["param"] != ""]
        # can just keep this as a dictionary given its just a hashmap with 1 item
        self.technologies = {
            tech: self.identify_technology_research_and_time(
                tech, research_data=research_techs, civilisation=civilisation
            )
            for tech in pd.unique(research_techs["param"])
        }

        # Create model form town centre productions, including technologies.
        # The reason to do here is to overwrite research times for age up and Loom/Wheel
        self.town_centres = (
            TownCentreBuildingFactory().create_production_building_and_remove_used_id(
                inputs_data=self.inputs_df,
                player=self.number,
                position_x=self.starting_position[0],
                position_y=self.starting_position[1],
            )
        )
        if not self.town_centres:
            raise ValueError(
                "Found no town centres for this player. Without this, cannot accurately parse game"
            )
        else:
            self.tc_units_and_techs = pd.concat(
                [tc_.produce_units() for tc_ in self.town_centres]
            )

        # update research times and age up times after proper unit production
        for research in TownCentreUnitsAndTechs:
            if research == "Villager":  # Ignore units of course
                continue
            # TODO-patch check this is accurate
            if not self.tc_units_and_techs.loc[
                self.tc_units_and_techs["param"] == research, "UnitCreatedTimestamp"
            ].empty:
                self.technologies[research] = self.tc_units_and_techs.loc[
                    self.tc_units_and_techs["param"] == research, "UnitCreatedTimestamp"
                ].to_list()[
                    0
                ]  # need to extract data rather than a series object

        # dict for quickly accessing age up times (not click up times)
        self.age_up_times = {
            index
            + 2: self.identify_technology_research_and_time(
                age, research_techs, civilisation=self.civilisation
            )
            for index, age in enumerate(["Feudal Age", "Castle Age", "Imperial Age"])
        }

        # Buildings created
        all_buildings_created = self.inputs_df.loc[
            (self.inputs_df["type"] == "Build") | (self.inputs_df["type"] == "Reseed"),
            :,
        ]
        self.buildings = pd.concat(
            [
                self.identify_building_and_timing(
                    building_name=building,
                    buildings_data=all_buildings_created,
                    feudal_time=self.age_up_times[2],
                    castle_time=self.age_up_times[3],
                    imperial_time=self.age_up_times[4],
                    civilisation=self.civilisation,
                )
                for building in pd.unique(all_buildings_created["param"])
            ]
        ).sort_values("timestamp")

        # Split into military production buildings and everything else
        # TODO-patch check if this is used anywhere
        self.military_buildings_created = all_buildings_created[
            all_buildings_created.loc[:, "param"].isin(MilitaryBuildings)
        ].copy()

        self.economic_buildings_created = all_buildings_created[
            ~all_buildings_created.loc[:, "param"].isin(
                MilitaryBuildings
            )  # Note not (~)
        ].copy()

        # Player walls - Palisade Wall(s) and Stone Wall(s)
        self.player_walls = self.inputs_df.loc[self.inputs_df["type"] == "Wall", :]

        # Units and unqueing. Note that unqueuing is not possible to handle...
        self.queue_units = self.inputs_df.loc[self.inputs_df["type"] == "Queue", :]
        self.unqueue_units = self.inputs_df.loc[self.inputs_df["type"] == "Unqueue", :]

        # Create models for archery ranges, stables etc.
        # These production buildings allow us to see when a unit is CREATED rather than queued. Otherwise, we only see the time
        # the player clicks the unit/technology etc, not when it is completed.
        self.archery_ranges = ArcheryRangeProductionBuildingFactory().create_production_building_and_remove_used_id(
            inputs_data=self.inputs_df, player=self.number
        )
        if self.archery_ranges is not None and len(self.archery_ranges) > 0:
            self.archery_units = pd.concat(
                [range_.produce_units() for range_ in self.archery_ranges]
            )
        else:
            self.archery_units = pd.DataFrame()

        # Barracks
        self.barracks = BarracksProductionBuildingFactory().create_production_building_and_remove_used_id(
            inputs_data=self.inputs_df, player=self.number
        )
        if self.barracks is not None and len(self.barracks) > 0:
            self.barracks = pd.concat(
                [range_.produce_units() for range_ in self.barracks]
            )
        else:
            self.barracks = pd.DataFrame()

        self.stables = StableProductionBuildingFactory().create_production_building_and_remove_used_id(
            inputs_data=self.inputs_df, player=self.number
        )
        if self.stables is not None and len(self.stables) > 0:
            self.stable_units = pd.concat(
                [stable.produce_units() for stable in self.stables]
            )
        else:
            self.stable_units = pd.DataFrame()

        self.siege_shops = SiegeWorkshopProductionBuildingFactory().create_production_building_and_remove_used_id(
            inputs_data=self.inputs_df, player=self.number
        )
        if self.siege_shops is not None and len(self.siege_shops) > 0:
            self.siege_units = pd.concat(
                [seige_shop.produce_units() for seige_shop in self.siege_shops]
            )
        else:
            self.siege_units = pd.DataFrame()

        # data structure to hold all military units
        self.military_units = pd.concat(
            [self.archery_units, self.barracks, self.stable_units, self.siege_units]
        )
        # TODO-feature - castle, donjon, dock. Lots of boiler plate

    def full_player_choices_and_strategy(
        self,
        feudal_time: pd.Timedelta,
        castle_time: pd.Timedelta | None,
        loom_time: pd.Timedelta,
        end_of_game: pd.Timedelta,
        civilisation: str,
    ) -> pd.Series:
        """Main API - call to analyse the player's choices"""

        # Extract the key statistics / data points
        # research age timings and loom to mine out

        # Handle if the game ends in feudal for this player
        if castle_time is None:
            castle_time = end_of_game  # end of the game

        self.dark_age_stats = self.extract_feudal_uptime_info(
            feudal_time=feudal_time, loom_time=loom_time, civilisation=civilisation
        )

        # Identify Feudal and Dark Age military Strategy
        self.opening_strategy = self.extract_opening_strategy(
            feudal_time=feudal_time,
            castle_time=castle_time,
            mills_building_data=self.buildings.loc[
                self.buildings["Building"] == "Mill", :
            ],
            technologies_researched=self.technologies,
            military_buildings_spawned=self.military_buildings_created,
            units_queued=self.military_units,
        )

        # Identify Feudal and Dark Age economic choices
        self.feudal_economic_choices_and_castle_time = (
            self.extract_early_game_economic_strat(
                castle_time=castle_time,
                feudal_time=feudal_time,
                player_eco_buildings=self.economic_buildings_created,
                player_walls=self.player_walls.loc[
                    self.player_walls["payload.building"] == "Palisade Wall", :
                ],
                technologies=self.technologies,
            )
        )

        self.opening = pd.concat(
            [
                self.opening,
                self.dark_age_stats,
                self.opening_strategy,
                self.feudal_economic_choices_and_castle_time,
            ]
        )

        return self.opening

    def identify_location(self) -> pd.Series:
        """Wrapper to return a pandas friendly starting position object"""
        return pd.Series({"StartingLocation": self.starting_position})

    def identify_civilisation(self) -> pd.Series:
        """Wrapper to return civilisation pandas friendly"""
        return pd.Series({"Civilisation": self.civilisation})

    def identify_technology_research_and_time(
        self, technology: str, research_data: pd.DataFrame, civilisation: str = None
    ) -> pd.Timedelta | None:
        """A helper method that can identify when players research certain things and the timing of that

        :param technology: technology being researches
        :type technology: str
        :param civilisations: civilisations to handle faster research times, defaults to None
        :type civilisations: dict, optional
        :raises ValueError: incorrect technology passed
        :return: data frame with the time each player researched and completed the technology
        :rtype: pd.DataFrame
        """
        enum_technology = technology.replace(" ", "_").replace(
            "-", "_"
        )  # TODO-patch for cleanliness, think about handling this in Enum methods

        if not TechnologyResearchTimes.has_value(enum_technology):
            logger.error(
                f"Technology could not be found in Enums. Tech was: {technology}"
            )
            # consider warning and gracefully returning None rather than failing
            # in the case of an invalid string, the Enum will raise an error. In other cases, just warn the user.
            # raise ValueError(f"Couldn't find technology: {technology} (Enum: {enum_technology}). Please raise this issue on GitHub.")
            return None  # return empty data a time for this tech
        time_to_research = TechnologyResearchTimes.get(
            enum_technology, civilisation=civilisation
        )

        # Unsure why there is two clicks - maybe one for queue and one for actually clicking up? Bug in mgz?
        # Handle two clicks
        relevent_research = research_data.loc[
            research_data["param"] == technology, "timestamp"
        ]  # handle unqueue

        if relevent_research.empty:
            # Log if no data can be found for a technology.
            logger.warning(f"Could not find any parsed game data for a researched tech ({technology}). Check why this is searched for.")
            return None

        # using len here handles multiple like a cancel and re-research
        return relevent_research.iloc[len(relevent_research) - 1] + pd.Timedelta(
            seconds=time_to_research
        )

    def identify_building_and_timing(
        self,
        building_name: str,
        buildings_data: pd.DataFrame,
        feudal_time: pd.Timedelta | None,
        castle_time: pd.Timedelta | None,
        imperial_time: pd.Timedelta | None,
        civilisation: str = None,
    ) -> pd.DataFrame:
        """Helper to find all the creations of an economic building type.

        :param building: the string name of the building. See enums for validation. Errors if incorrect
        :param civilisations: player's civilisation, defaults to None
        :raises ValueError: _description_
        :return: df with all the instances of building creation and time of completion
        :rtype: pd.DataFrame
        """

        enum_building_name = building_name.replace(" ", "_").replace(
            "-", "_"
        )  # TODO for cleanliness, think about handling this in Enum methods

        if not BuildTimesEnum.has_value(enum_building_name):
            logger.error(
                f"Building given to find building method incorrect. Building was: {building_name}"
            )
            # No longer error if building cant be found - let Enum handle erroring on a bad MGZ Parse
            # raise ValueError(f"Couldn't find building: {building_name}")
            return pd.DataFrame(columns=buildings_data)  # return an empty dataframe

        time_to_build = BuildTimesEnum.get(
            enum_building_name, civilisation=civilisation
        )

        relevent_building = buildings_data.loc[
            buildings_data["param"] == building_name,
            ["timestamp", "player", "payload.object_ids"],
        ]
        if relevent_building.empty:
            # log this and return empty data frame but with correct columns - handle accordingly
            logger.warning(f"Building was never built according to parsed game data ({building_name})")
            return relevent_building

        # Handle case where MGZ cannot find the payload.object_ids - in other words the vils building the building
        if relevent_building["payload.object_ids"].isna().any():
            # In this case, just assume 1 vil and circumvent failure below
            relevent_building.loc[relevent_building["payload.object_ids"].isna(), "payload.object_ids"] = [0]

        relevent_building["Building"] = building_name
        relevent_building["NumberVillsBuilding"] = relevent_building[
            "payload.object_ids"
        ].apply(lambda x: len(x))
        relevent_building["TimeToBuild"] = (3 * time_to_build) / (
            relevent_building["NumberVillsBuilding"] + 2
        )
        relevent_building["TimeToBuild"] = pd.to_timedelta(
            relevent_building["TimeToBuild"], unit="s"
        )
        relevent_building["timestamp"] = (
            relevent_building["timestamp"] + relevent_building["TimeToBuild"]
        )

        # Age of building creation
        relevent_building["Age"] = 1  # default is dark age
        for index, time in enumerate([feudal_time, castle_time, imperial_time]):
            if time is not None:
                relevent_building.loc[relevent_building["timestamp"] > time, "Age"] = (
                    index + 2
                )  # +2 as need to map from 0= Feudal to Feudal = 2 and so on

        return relevent_building

    def extract_feudal_uptime_info(
        self,
        feudal_time: pd.Timedelta,
        loom_time: pd.Timedelta,
        civilisation: str = None,
    ) -> pd.Series:
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
        # Need to remove the age up time which is built into the feudal time passed to this function
        feudal_click_up_time = feudal_time - pd.Timedelta(
            seconds=TechnologyResearchTimes.get("Feudal_Age", civilisation=civilisation)
        )
        loom_in_dark_age = (
            loom_time < feudal_time
        )  # Returns a series where the only entry is true
        if isinstance(loom_in_dark_age, pd.Series):
            loom_in_dark_age = loom_in_dark_age.to_list()[0]  # retrieve the Bool

        if loom_in_dark_age:
            # Need to also remove loom if it was before feudal
            feudal_click_up_time - pd.Timedelta(
                seconds=TechnologyResearchTimes.get("Loom", civilisation=civilisation)
            )
        villager_creation_time = (
            25 if civilisation != "Persians" else 25 * 0.95
        )  # Persians in dark age produce 5% faster

        # This basically gives us a float where seconds = int of villagers and ms = % of vil idle time
        villager_analysis = feudal_click_up_time / villager_creation_time

        # Get final integer number of villagers - handle Chinese and Mayans
        number_villagers = villager_analysis.seconds + 3  # 3 for starting villagers
        if civilisation == "Mayans":
            number_villagers += 1
        if civilisation == "Chinese":
            # assume approx two - a skilled player can get this to near 2.5, which may lead to innaccurate results
            number_villagers += 2

        # Get idle time from ms in timedelta
        # TODO-Feature this is no longer correct because of innaccuracies in Feudal Time calculation from mgz package
        # dark_age_idle_time = (villager_analysis._ms * villager_creation_time) / 1000  # convert ms to s, this is % of villager time

        feudal_stats_to_return = {
            "FeudalTime": feudal_time,
            "Villagers": number_villagers,
            # "DarkAgeIdleTime": dark_age_idle_time,
            "DarkAgeLoom": loom_in_dark_age,
        }

        return pd.Series(feudal_stats_to_return)

    def extract_opening_strategy(
        self,
        feudal_time: pd.Timedelta,
        castle_time: pd.Timedelta,
        military_buildings_spawned: pd.DataFrame,
        mills_building_data: pd.DataFrame,
        technologies_researched: dict,
        units_queued: pd.DataFrame,
    ) -> pd.Series:
        """Function that identifies military stratgy. Uses Militia and Feudal military methods"""
        # time of maa tech for maa function
        maa_time: pd.Timedelta | None = technologies_researched.get("Man-At-Arms", None)
        # time of first mill for maa function
        first_mill_time = mills_building_data["timestamp"].min() if not mills_building_data["timestamp"].empty else None

        # identify drush and categorise into MAA/Pre-mill/Drush
        dark_age_approach = self.militia_based_strategy(
            feudal_time=feudal_time,
            castle_time=castle_time,
            military_buildings_spawned=military_buildings_spawned,
            mill_created_time=first_mill_time,
            units_created=units_queued,
            maa_upgrade=maa_time,
        )  # TODO - identify towers or a fast castle

        feudal_approach = self.feudal_military_choices(
            feudal_time=feudal_time, castle_time=castle_time, units_queued=units_queued
        )

        # Extract number of steals
        match (
            dark_age_approach["MilitiaStrategyIdentified"],
            feudal_approach["OpeningMilitaryBuilding"],
            feudal_approach["Archer"] > 0,
            feudal_approach["Skirmisher"] > 0,
            feudal_approach["Scout Cavalry"] > 0,
            feudal_time > pd.Timedelta(seconds=25 * 26),
        ):  # arbitrarily pick 25 vils + loom for fastle castle feudal time
            case ("Drush", "Archery Range", _, _, _, True):
                strategy = "Drush FC"
            case ("Drush", "Archery Range", _, _, _, False):
                strategy = "Drush Flush"
            case ("Pre-Mill Drush", "Archery Range", _, _, _, True):
                strategy = "Pre-Mill Drush FC"
            case ("Pre-Mill Drush", "Archery Range", _, _, _, False):
                strategy = "Pre-Mill Drush Flush"
            case ("MAA", "Archery Range", _, _, _, _):
                strategy = "MAA Archers"
            case ("MAA", _, _, _, _, _):
                strategy = "MAA"
            case (_, "Archery Range", True, True, True, _):
                strategy = "Archery Range into Full Feudal"
            case (_, "Stable", True, True, True, _):
                strategy = "Scouts into Full Feudal"
            case (_, "Stable", False, False, True, _):
                strategy = "Full Scouts"
            case (_, "Archery Range", True, True, _, _):
                strategy = "Archers and Skirms"
            case (_, "Archery Range", True, _, True, _):
                strategy = "Archers into scouts"
            case (_, "Archery Range", True, _, True, _):
                strategy = "Skirms into scouts"
            case (_, "Stable", True, _, _, _):
                strategy = "Scouts into archers"
            case (_, "Stable", _, True, _, _):
                strategy = "Scouts into skirms"
            case (_, "Archery Range", True, False, False, _):
                strategy = "Straight Archers"
            case (_, "Archery Range", False, True, False, _):
                strategy = "Straight Skirms or Trash Rush"
            case (_, _, _, _, _, True):
                strategy = "Fastle Castle"
            case (_, _, _, _, _, _):
                strategy = "Could not Identify!"
                v1, v2, v3, v4, v5 = (
                    dark_age_approach["MilitiaStrategyIdentified"],
                    feudal_approach["OpeningMilitaryBuilding"],
                    feudal_approach["Archer"] > 0,
                    feudal_approach["Skirmisher"] > 0,
                    feudal_approach["Scout Cavalry"] > 0,
                )
                logger.warning(
                    f"Couldn't identify strategy. Dark Age: {v1}, Building: {v2}, Archers, Skirms, Scouts:{v3, v4, v5}"
                )
        return pd.concat(
            [
                pd.Series({"OpeningStrategy": strategy}),
                dark_age_approach,
                feudal_approach,
            ]
        )

    def militia_based_strategy(
        self,
        feudal_time: pd.Timedelta,
        castle_time: pd.Timedelta | None,  # None in case of game ending in Feudal
        military_buildings_spawned: pd.DataFrame,
        mill_created_time: pd.Timedelta | None,  # None in case of no mills
        units_created: pd.DataFrame,
        maa_upgrade: pd.Timedelta | None = None,  # None in case of not researched
    ) -> pd.Series:
        """Logic to identify groups of MAA or Militia based strategy: MAA, pre-mill drush, drush"""
        # Identify key timings and choices associated with these strategies
        dark_age_feudal_barracks: pd.DataFrame = military_buildings_spawned.loc[
            (military_buildings_spawned["param"] == "Barracks")
            & (military_buildings_spawned["timestamp"] < castle_time),
            :,
        ]
        dark_age_feudal_barracks: pd.DataFrame = self.identify_building_and_timing(
            "Barracks",
            dark_age_feudal_barracks,
            feudal_time=feudal_time,
            castle_time=castle_time,
            imperial_time=None,
            civilisation=self.civilisation,
        )
        first_barracks_time: pd.Timedelta | None = dark_age_feudal_barracks["timestamp"].min() if not dark_age_feudal_barracks["timestamp"].empty else None
        
        pre_mill_barracks: bool = first_barracks_time < mill_created_time if first_barracks_time is not None else False
        if units_created.empty:
            number_of_militia_or_maa_dark: int = 0
        else:
            militia_created_dark_age: pd.DataFrame = units_created.loc[
                (units_created["param"] == "Militia")
                & (units_created["UnitCreatedTimestamp"] < feudal_time),
                :,
            ]
            militia_created: pd.DataFrame = units_created.loc[
                (units_created["param"] == "Militia")
                & (units_created["UnitCreatedTimestamp"] < castle_time),
                :,
            ]
            # convert raw information into strategy - number of units
            number_of_militia_or_maa_dark = len(militia_created_dark_age)
            number_of_militia_or_maa_total = len(militia_created)

        # convert raw information into strategy - strategy
        if maa_upgrade is not None:
            militia_opening_strategy = "MAA"
        elif pre_mill_barracks and number_of_militia_or_maa_dark > 0:
            militia_opening_strategy = "Pre-Mill Drush"
        elif number_of_militia_or_maa_dark > 0 or number_of_militia_or_maa_total > 0:
            militia_opening_strategy = "Drush"
        else:
            militia_opening_strategy = None

        # TODO-FeatureIdea identify the time the militia rock up to the opponents base - click within certain distance
        # Return key featues
        dark_age_choices_to_return = {
            "FirstBarracksTime": first_barracks_time,
            "MilitiaStrategyIdentified": militia_opening_strategy,
            "NumberOfMilitiaUnits": number_of_militia_or_maa_dark,
            "PreMillBarracks": pre_mill_barracks,
        }

        return pd.Series(dark_age_choices_to_return)

    def feudal_military_choices(
        self,
        feudal_time: pd.Timedelta,
        castle_time: pd.Timedelta,
        units_queued: pd.DataFrame,
        # TODO add military buildings
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
        # TODO pass buildings as argument
        feudal_military_buildings = self.buildings.loc[
            (
                (self.buildings["Building"] == "Archery Range")
                | (self.buildings["Building"] == "Stable")
            )
            & (self.buildings["timestamp"] > feudal_time)
            & (self.buildings["timestamp"] < castle_time),
            :,
        ]

        # time of first building
        opening_timing = feudal_military_buildings["timestamp"]
        if opening_timing.empty:
            # went for a drush FC, or maa strat - just take feudal time
            # TODO in future change this depending on MAA, Drush, FC, towers etc.
            opening_timing = feudal_time
        else:
            opening_timing = opening_timing.iloc[0]

        # Get the first military building made in feudal
        opening_military_building = feudal_military_buildings.loc[
            feudal_military_buildings["timestamp"] == opening_timing, "Building"
        ]
        if opening_military_building.empty:
            opening_military_building = (
                "Towers/Barracks/FC"  # TODO as above differentiate between them
            )
        else:
            opening_military_building = opening_military_building.iloc[0]

        # extract the units created and how many of those created
        if units_queued.empty:
            number_of_each_unit = pd.Series(
                [0] * len(FeudalAgeMilitaryUnits), index=FeudalAgeMilitaryUnits
            )
        else:
            feudal_military_units = units_queued.loc[
                (units_queued["param"].isin(FeudalAgeMilitaryUnits))
                & (units_queued["UnitCreatedTimestamp"] < castle_time),
                :,
            ]
            # Count of each military unit
            number_of_each_unit = feudal_military_units.groupby("param").count()[
                "UnitCreatedTimestamp"
            ]

            # Handle instance where they do not produce this unit
            for unit in FeudalAgeMilitaryUnits:
                if unit not in number_of_each_unit.index:
                    number_of_each_unit[unit] = 0

        # Non spear units - to identify strategy
        # non_spear_military_units = feudal_military_units.loc[feudal_military_units["param"] != "Spearman", :]  # TODO

        # Extract time to 3 of first units

        military_stats_to_return = {
            "OpeningMilitaryBuildingTime": opening_timing,
            "OpeningMilitaryBuilding": opening_military_building,
        }

        return pd.concat([pd.Series(military_stats_to_return), number_of_each_unit])

    def extract_early_game_economic_strat(
        self,
        feudal_time: pd.Timedelta,
        castle_time: pd.Timedelta,
        player_eco_buildings: pd.DataFrame,
        player_walls: pd.DataFrame,
        technologies: dict,
    ) -> pd.Series:

        # TODO - extract information from the dark age: sheep, deer, boars, berries
        # dark_age_economic_development = self.extract_dark_age_economic_tactics()

        # Feudal age wood and farm upgrade;
        double_bit_axe_time = technologies.get("Double-Bit Axe", None)
        horse_collar_time = technologies.get("Horse Collar", None)
        wheelbarrow_time = technologies.get("Wheelbarrow", None)

        feudal_technology_times = pd.Series(
            {
                "DoubleBitAxe": double_bit_axe_time,
                "HorseCollar": horse_collar_time,
                "Wheelbarrow": wheelbarrow_time,
            }
        )

        # Extract how quickly they develop their farming economy
        farm_development = self.farm_economic_development(
            feudal_time, castle_time, player_eco_buildings
        )
        # Extract when/if they choose to wall their map
        walling_tactics = self.walling_tactics(
            feudal_time, castle_time, player_eco_buildings, player_walls
        )

        # Concat to pandas series and return
        stats_to_return = pd.concat(
            [feudal_technology_times, farm_development, walling_tactics]
        )
        return stats_to_return

    def dark_age_economic_tactics(self) -> pd.Series:
        # dark age number of deer taken
        # dark age number of boars/rhinos taken
        # dark age number of sheep taken
        # dark age time of mill on berries + number of vils on berries
        pass

    def farm_economic_development(
        self,
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
        farms_in_feudal: pd.DataFrame = player_eco_buildings.loc[
            (player_eco_buildings["payload.building"] == "Farm")
            & (player_eco_buildings["timestamp"] > feudal_time)
            & (player_eco_buildings["timestamp"] < castle_time),
            :,
        ]
        farms_in_feudal: pd.DataFrame = self.identify_building_and_timing(
            "Farm", farms_in_feudal, feudal_time, castle_time, None, self.civilisation
        )
        number_farms_made: int = len(farms_in_feudal)
        # time of 3, 6, 10, 15, 20 farms
        farms_results = pd.Series(
            {
                "TimeThreeFarms": None,
                "TimeSixFarms": None,
                "TimeTenFarms": None,
                "TimeFifteenFarms": None,
                "TimeTwentyFarms": None,
            }
        )
        # Iterate through the number of farms, with the series key and the index number
        for key, farms_number in zip(farms_results.index.to_list(), [3, 6, 10, 15, 20]):
            if number_farms_made >= farms_number:
                # Need guard statement incase dataframe is not long enough
                farms_results.loc[key] = farms_in_feudal.iloc[farms_number - 1, :][
                    "timestamp"
                ]
        farms_results = pd.concat(
            [pd.Series({"NumberFeudalFarms": number_farms_made}), farms_results]
        )

        return farms_results

    def walling_tactics(
        self,
        feudal_time: pd.Timedelta,
        castle_time: pd.Timedelta,
        player_eco_buildings: pd.DataFrame,
        player_walls: pd.DataFrame,
    ) -> pd.Series:
        """Helper function to extract walls built in the early game
        :param feudal_time: _description_
        :param castle_time: _description_
        :param player_eco_buildings: _description_
        :return: _description_
        :rtype: pd.Series
        """
        # Note on houses - include as a proxy for fortifying your map/walls in the mid game (feudal - castle)

        
        # Houses - for the moment limit to feudal. Number of Houses is probably a poor proxy for identifying walling tactics,
        # as they aren't always used to reinforce walls
        # Some sort of really complicated location analysis would be required to amend this - I will not go down this path.
        houses_built = player_eco_buildings.loc[
            player_eco_buildings["payload.building"] == "House", "timestamp"
        ]
        feudal_houses: int = len(
            houses_built.loc[
                (houses_built > feudal_time) & (houses_built < castle_time)
            ]
        )

        # Walls - # calculate chebyshev distance of each wall segment - sum in each age
        palisade_walls = player_walls.loc[
            player_walls["payload.building"] == "Palisade Wall", :
        ]
        # Assertion on empty dataframe
        if palisade_walls.empty:
            # player never built palisade walls - guard statement blocks code below, as malformed dataframe can throw key errors
            return pd.Series({
                "DarkAgeWallsNumber": 0,
                "FeudalWallsNumber": 0,
                "PostCastleWalls": 0,
                "FeudalHousesBuilt": feudal_houses,
            })

        # Calculate chebyshev distance between the wall start and end to get # of tiles
        palisade_walls["NumberTilesPlaced"] = palisade_walls.apply(
            lambda x: distance.chebyshev(
                x[["position.x", "position.y"]], x[["payload.x_end", "payload.y_end"]]  # payload.x_end and .y_end throw key errors on empty DF
            ),
            axis=1,
        )
        dark_age_walls = palisade_walls.loc[
            palisade_walls["timestamp"] < feudal_time, "NumberTilesPlaced"
        ].sum()
        feudal_age_walls = palisade_walls.loc[
            (palisade_walls["timestamp"] >= feudal_time)
            & (palisade_walls["timestamp"] <= castle_time),
            "NumberTilesPlaced",
        ].sum()
        post_castle_walls = palisade_walls.loc[
            palisade_walls["timestamp"] > castle_time, "NumberTilesPlaced"
        ].sum()

        walling_results = pd.Series(
            {
                "DarkAgeWallsNumber": dark_age_walls,
                "FeudalWallsNumber": feudal_age_walls,
                "PostCastleWalls": post_castle_walls,
                "FeudalHousesBuilt": feudal_houses,
            }
        )

        return walling_results


class AgeMap:
    """Data structure representing the AOE2 map. Goal of identifying and extracting map features for analysis"""

    def __init__(self, map: dict, gaia: List[dict], player_starting_locations: list) -> None:
        """Reconstruct the key features of the map - terrain, relics, resources (trees, gold, stone, berries).
        Store this information in a dataframe"""

        # Map object
        self.map: dict = map  # Store map object
        self.map_size_int: int = map[
            "dimension"
        ]  # The size of the map (note map is always square)
        self.map_name: str = self.map["name"]

        # Distribution of starting objects
        self.tiles_raw: List[dict] = gaia
        self.tiles = pd.DataFrame(gaia)
        self.tiles = self.tiles.join(
            self.tiles["position"].apply(pd.Series), validate="one_to_one"
        )  # Explode out dict into cols for x + y

        self.tiles["x"] = self.tiles["x"].astype(int)
        self.tiles["y"] = self.tiles["y"].astype(int)

        self.elevation_map: pd.DataFrame = pd.DataFrame(
            self.map["tiles"]
        )  # Elevation of each tile
        # Explode out dict into cols for x + y
        self.elevation_map = self.elevation_map.join(
            self.elevation_map["position"].apply(pd.Series), validate="one_to_one"
        )
        self.elevation_map = self.elevation_map.drop(
            columns=["position", "terrain"]
        )  # clean up columns

        # Join elevation on - note have to use x and y as ofc no object ID for terrain
        self.tiles = self.tiles.merge(self.elevation_map, on=["x", "y"], how="left")

        self.player_locations = player_starting_locations

        # Assertion - if any of the player locations are empty, then we cannot perform the AgeMap analysis
        # For now, set the key attribute that we access to None and return without performing analysis
        for player_loc in player_starting_locations:
            if not player_loc or len(player_loc) == 0:
                # Case where a tuple is empty - set key attribute to None
                self.map_analysis = None
                return

        # Judge a hill for each player res by elevation greater than starting location; could think of a more elegant solution
        self.height_of_player_locations = [
            self.tiles.loc[
                (self.tiles["x"] == int(player[0])) & (self.tiles["y"] == int(player[1])),  # TODO type checking of this - ints and floats
                "elevation",
            ].mean()
            for player in self.player_locations
        ]
        # Need to change to 0 for instances where the x and y cannot be found
        self.height_of_player_locations: List[int] = [int(item) if not math.isnan(item) else 0 for item in self.height_of_player_locations]

        # Data parsing - coerce some varied names to regular ones.
        # Remove anything in brackets - treat together (trees)
        self.tiles["name"] = self.tiles["name"].str.replace(r"\s\(.*\)", "", regex=True)
        # Coerce different types of starting food into one type for processing
        self.tiles["name"] = self.tiles["name"].str.replace(
            pat="(Forage Bush)|(Berry Bush)", repl="Fruit Bush", regex=True
        )
        self.tiles["name"] = self.tiles["name"].str.replace(
            pat="(Llama)|(Goat)|(Goose)|(Turkey)|(Pig)|(Turkey)",
            repl="Sheep",
            regex=True,
        )
        self.tiles["name"] = self.tiles["name"].str.replace(
            pat="(Zebra)|(Ostrich)|(Ibex)|(Gazelle)", repl="Deer", regex=True
        )
        self.tiles["name"] = self.tiles["name"].str.replace(
            pat="(Elephant)|(Rhinoceros)", repl="Wild Boar", regex=True
        )
        # TODO mark if elephant or rhino as more food
        # TODO maybe treat water buffalo and cows seperately... if needed

        # Identify islands (groups) of resources for minin information from later
        resources_to_check_between_players = [
            "Fruit Bush",
            "Gold Mine",
            "Stone Mine",
            "Tree",
        ]  # Check these resources

        # Wrapper function that gets the following for the object and stores it in the object:
        # - Identifies islands of resources
        # - Identifies the polygon corridor between players
        # - Falgs the resources between the players
        self.process_resource_locations(
            resources_to_identify=resources_to_check_between_players
        )

        p_1_resource_analysis = self.analyse_map_features_for_player(
            player=1,
            player_resources=self.tiles.loc[self.tiles["ClosestPlayer"] == 1, :],
            min_height_for_hill=self.height_of_player_locations[0],
        )

        p_2_resources_analysis = self.analyse_map_features_for_player(
            player=2,
            player_resources=self.tiles.loc[self.tiles["ClosestPlayer"] == 2, :],
            min_height_for_hill=self.height_of_player_locations[1],
        )

        self.map_analysis = pd.concat([p_1_resource_analysis, p_2_resources_analysis])

        # TODO test results against actual

        return

    def analyse_map_features_for_player(
        self, player: int, player_resources: pd.DataFrame, min_height_for_hill: int
    ) -> pd.Series:
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
        sizes_of_golds = golds.groupby(
            "Gold Mine"
        ).count()  # TODO there is a much better way of doing this - col for each type is not good
        main_gold_index = sizes_of_golds["instance_id"].idxmax()
        main_gold = player_resources.loc[
            player_resources["Gold Mine"] == main_gold_index
        ]
        list_of_ids_for_secondary_golds = (
            sizes_of_golds["instance_id"].drop(index=main_gold_index).index.to_list()
        )
        secondary_gold_one = player_resources.loc[
            player_resources["Gold Mine"] == list_of_ids_for_secondary_golds[0]
        ]
        secondary_gold_two = player_resources.loc[
            player_resources["Gold Mine"] == list_of_ids_for_secondary_golds[1]
        ]

        # Apply rules to main gold - Back, Front or Front Hill
        main_gold_analysis = self.analyse_resource(
            main_gold["BetweenPlayers"].max(),
            bool(main_gold["elevation"].mean() > min_height_for_hill),
        )

        resource_analysis = pd.Series({f"Player{player}.MainGold": main_gold_analysis})

        # Apply logic to both secondary golds
        for index, gold in enumerate([secondary_gold_one, secondary_gold_two]):
            # Get name of gold for storing in dict
            gold_name = "SecondGold" if index == 1 else "ThirdGold"
            # Get bools for front/back and hill
            front_or_back = gold["BetweenPlayers"].max() if not gold["BetweenPlayers"].empty else False
            hill = gold["elevation"].mean() > min_height_for_hill

            analysis_of_current_gold = self.analyse_resource(
                between_players=front_or_back, average_height_above_tc=hill
            )

            resource_analysis = pd.concat(
                [
                    resource_analysis,
                    pd.Series(
                        {f"Player{player}.{gold_name}": analysis_of_current_gold}
                    ),
                ]
            )

        # Identify berries
        berries = player_resources.loc[player_resources["name"] == "Fruit Bush", :]
        berries_between_players = berries["BetweenPlayers"].max() if not berries["BetweenPlayers"].empty else False

        # Apply to analysis method (Hill/Front/Back) to berries
        berry_analysis = self.analyse_resource(
            between_players=berries_between_players,
            average_height_above_tc=berries["elevation"].mean() > min_height_for_hill,
        )
        resource_analysis = pd.concat(
            [resource_analysis, pd.Series({f"Player{player}.Berries": berry_analysis})]
        )

        # identify main stone
        stones = player_resources.loc[player_resources["name"] == "Stone Mine", :]
        sizes_of_stones = stones.groupby(
            "Stone Mine"
        ).count()  # TODO there are better ways of doing this - col for each type is not good
        main_stone_index = sizes_of_stones["instance_id"].max()
        main_stone = player_resources.loc[
            player_resources["Stone Mine"] == main_stone_index
        ]
        stone_between_players = main_stone["BetweenPlayers"].max() if not main_stone["BetweenPlayers"].empty else False

        # Apply to analysis method (Hill/Front/Back) to stone
        stone_analysis = self.analyse_resource(
            between_players=stone_between_players,
            average_height_above_tc=main_stone["elevation"].mean() > min_height_for_hill,
        )

        resource_analysis = pd.concat(
            [resource_analysis, pd.Series({f"Player{player}.Stone": stone_analysis})]
        )

        # Identify and analyse structure of woodlines
        woodlines = player_resources.loc[
            player_resources["name"] == "Tree", :
        ].drop_duplicates(subset=["name", "x", "y"])

        # Apply woodlines analysis
        woodlines_analysis = self.analyse_player_woodlines(
            woodlines=woodlines, player_number=player
        )

        resource_analysis = pd.concat([resource_analysis, woodlines_analysis])

        # TODO add validation of format of resource analysis

        return resource_analysis

    def analyse_resource(
        self, between_players: bool, average_height_above_tc: bool | np.bool
    ) -> str:
        """Categorise a resource into Front Hill / Front / Back depending on forwardness and hilliness"""
        match (between_players, average_height_above_tc):
            case (True, True):
                analysis = "Front Hill"
            case (True, False):
                analysis = "Front"
            case (False, _):
                analysis = "Back"
            case _:
                analysis = "Unknown"
                logger.info(f"Could not analyse resource correctly. {between_players}, {average_height_above_tc}")  # log unknown
        return analysis

    def analyse_player_woodlines(
        self, woodlines: pd.DataFrame, player_number
    ) -> pd.Series:
        """Categorise front/side/back woodlines and get count by #

        :param woodlines: DataFrame of tiles with woodlines, their player, and associated flags
        :param player_number:
        :return: series with summary information
        """
        woodlines_dict = {"Front": 0, "Side": 0, "Back": 0}
        for woodline_index in pd.unique(woodlines["Tree"]):
            wood = woodlines.loc[woodlines["Tree"] == woodline_index, :]
            number_trees_forward: int = len(
                wood.loc[wood["BetweenPlayers"], :]
            )  # Relies on no duplicates see exception below
            total_trees: int = len(wood)

            if wood.groupby(["x", "y"]).ngroups != total_trees:
                # Crazy that this can actually happen - TODO in test game 7 check if these are actually duplicates
                # This is an MGZ parser error - changed to that
                raise MGZParserException(
                    f"Woodline number {woodline_index} has duplicate tiles and has been parsed incorrectly"
                )  # proper logging

            if total_trees < 3:
                # Picked up stragglers around TC, disregard these
                continue

            if number_trees_forward / total_trees >= 0.6:
                woodlines_dict["Front"] += 1
            elif number_trees_forward / total_trees >= 0.2:
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
        self.resource_labels = [
            self.identify_islands_of_resources(self.tiles, resource=res)
            for res in resources_to_identify
        ]

        # Take all the resource labels and merge onto main tiles dataframe
        for res in self.resource_labels:
            self.tiles = self.tiles.merge(
                res.drop(columns=["x", "y"]), on="instance_id", how="left"
            )

        # Flag resources that are in between the players
        # Identify the corners of the corridor between players
        self.corridor_between_players = (
            self.identify_pathway_between_players()
        )  # List of tuples

        # Apply for each resource - check if it is in polygon
        list_dfs_of_resources_between_players = [
            self.identify_resources_or_feature_between_players(
                map_feature_locations=self.tiles.loc[self.tiles[res] > 0, :],
                polygon_to_check_within=self.corridor_between_players,
            )
            for res in resources_to_identify
        ]

        df_resources_between_players = pd.concat(list_dfs_of_resources_between_players)

        # Merge DF of all resources that are between
        self.tiles = self.tiles.merge(
            df_resources_between_players, on="instance_id", how="left"
        )

        # Max distance for resources to be considered close to players, as 0.4*distance between players
        distance_between_players = np.linalg.norm(
            (
                self.player_locations[0][0] - self.player_locations[1][0],
                self.player_locations[0][1] - self.player_locations[1][1],
            )
        )
        max_distance_to_players = 0.4 * distance_between_players
        # In general max distance of actual golds to players is around 32.
        # IF the formula above returns something less then it is possible to miss a player's gold
        # Extra 4 tile golds are around the 45-60 tiles away mark
        df_distances_to_players = self.assign_resource_island_to_player(
            map_feature_locations=self.tiles.copy(),
            maximum_distance_to_player=max(
                max_distance_to_players, 35
            ),  # 31 October caused some golds to be missed
            player_locations=self.player_locations,
        )

        self.tiles = self.tiles.merge(
            df_distances_to_players, on="instance_id", how="left"
        )
        return

    def identify_pathway_between_players(self) -> list:
        """Idenitfy a corridor between players.
        Use this to find key features in main battlefields, like trees, resources, large hills etc.
        """
        # TODO think about making this like a cone @ each players base, and identify a different polygon for their sides
        # Identify the vector between players
        # dx = x2 - x1, dy = y2 - y1
        dx, dy = (
            self.player_locations[0][0] - self.player_locations[1][0],
            self.player_locations[0][1] - self.player_locations[1][1],
        )

        # Normalise the vector
        magnitude = math.sqrt(dx**2 + dy**2)  # Cartesian length
        dx, dy = dx / magnitude, dy / magnitude

        # Identify the tangential direction to this vector
        # for a vector (dx, dy), the tangents from the same starting points are (-dy, dx) and (dy, -dx)
        # Identify the 4 corners of the plane by taking the starting locations and going 25 tiles in either of the normal directions
        # example: c1 = (x_1, y_1) + (dy, -dx)
        c1 = (
            self.player_locations[0][0] + dy * 25,
            self.player_locations[0][1] - dx * 25,
        )
        c2 = (
            self.player_locations[0][0] - dy * 25,
            self.player_locations[0][1] + dx * 25,
        )
        c3 = (
            self.player_locations[1][0] + dy * 25,
            self.player_locations[1][1] - dx * 25,
        )
        c4 = (
            self.player_locations[1][0] - dy * 25,
            self.player_locations[1][1] + dx * 25,
        )

        return [c1, c2, c3, c4]

    def identify_resources_or_feature_between_players(
        self, map_feature_locations: pd.DataFrame, polygon_to_check_within: list
    ) -> pd.DataFrame:
        """Identify the # of a map feature between players. Models scenarios such as large forests that units must move around,
        or can identify forward golds"""
        # TODO generalise this to just polygons, so that the sides can be checked for resources
        poly = Polygon(polygon_to_check_within)
        locations = map_feature_locations.copy()
        locations.loc[:, "BetweenPlayers"] = locations.apply(
            lambda x: Point(
                x["x"],
                x["y"],
            ).within(poly),
            axis=1,
        )
        return locations.loc[:, ["instance_id", "BetweenPlayers"]]

    def identify_islands_of_resources(
        self, dataframe_of_map: pd.DataFrame, resource: str
    ) -> pd.DataFrame:
        """Search for islands of resrouces in the 2D image of the map. Label the dataframe of resources with groups found"""
        # See some resources: https://stackoverflow.com/questions/46737409/finding-connected-components-in-a-pixel-array
        # https://docs.scipy.org/doc/scipy-0.16.0/reference/generated/scipy.ndimage.measurements.label.html
        # https://docs.scipy.org/doc/scipy/reference/generated/scipy.ndimage.label.html#scipy.ndimage.label

        df = dataframe_of_map[["y", "x", "instance_id", "name"]]  # Reduce columns
        # The AOE Game engine starts these objects in the centre of the tile. Remove the decimal if it exists.
        df.loc[:, ["x", "y"]] = np.floor(df[["x", "y"]].round()).astype(
            np.int32
        )  # remove decimal of floats
        df = df.loc[df["name"] == resource, ["x", "y", "instance_id"]]

        map_of_resources = np.zeros((self.map_size_int, self.map_size_int))
        for index, row in df.iterrows():
            # Not the fastest or most pythonic but quickest to write the code
            map_of_resources[int(row["x"]), int(row["y"])] = 1

        s = generate_binary_structure(
            2, 2
        )  # Creates a 3x3 matrix of 1's. Pass as structure to label to allow diagnoal check
        labeled_array, num_features = label(map_of_resources, structure=s)

        for label_index in range(1, num_features + 1):
            coords = np.where(labeled_array == label_index)
            for x, y in zip(coords[0], coords[1]):
                df.loc[(df["x"] == int(x)) & (df["y"] == int(y)), resource] = (
                    label_index
                )

        return df

    def assign_resource_island_to_player(
        self,
        map_feature_locations: pd.DataFrame,
        maximum_distance_to_player: float,
        player_locations: list,
    ) -> pd.DataFrame:
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
                (row["x"] - player_locations[0][0], row["y"] - player_locations[0][1])
            ),
            axis=1,
        )
        # Same for location to second player
        map_feature_locations["DistancePlayer2"] = map_feature_locations.apply(
            lambda row: np.linalg.norm(
                (row["x"] - player_locations[1][0], row["y"] - player_locations[1][1])
            ),
            axis=1,
        )

        map_feature_locations["ClosestPlayer"] = map_feature_locations.apply(
            lambda row: (
                row[["DistancePlayer1", "DistancePlayer2"]].idxmin()
                if row[["DistancePlayer1", "DistancePlayer2"]].min()
                < maximum_distance_to_player
                else None
            ),
            axis=1,
        )

        map_feature_locations["ClosestPlayer"] = map_feature_locations[
            "ClosestPlayer"
        ].map({"DistancePlayer1": 1, "DistancePlayer2": 2})

        return map_feature_locations[
            ["instance_id", "ClosestPlayer", "DistancePlayer1", "DistancePlayer2"]
        ]


class AgeGame:
    """A small wrapper for understanding an AOE game. Should just be a container for the mgz game which I can start to unpack"""

    def __init__(self, path: Path | str) -> None:
        self.path_to_game: Path | str = path

        try:
            with open(self.path_to_game, "rb") as g:
                self.match = parse_match(g)
                self.match_json = serialize(self.match)
        except FileNotFoundError as e:
            # Tell the user the file was not found
            raise e
        except Exception:
            # From the perspective of this package, fail if the MGZ parser cannot parse the game.
            # The below error message lets the user know it is an MGZ error, and beyond the scope of this package
            # In other words, catch any base exceptions raised by MGZ, which are from the perspective of this package,
            # unknown failure states. Fatally exit in this case
            raise MGZParserException(path)

        # Raw data from the game
        self.teams: list = self.match_json[
            "teams"
        ]  # Just a list lists with teams and player IDs per team
        self.rated_game: bool = self.match_json["rated"]  # bool
        self.game_speed: str = self.match_json["speed"]  # String
        self.game_data_set: str = self.match_json["dataset"]  # Just DE, not necessary
        self.starting_age: str = self.match_json[
            "starting_age"
        ]  # String, Dark/Fuedal/Castle
        self.game_duration: str = self.match_json["duration"]  # time HH:MM:SS.XXXXXX
        self.timestamp: str = self.match_json["timestamp"]  # Datetime, ISO format
        self.actions = self.match_json["actions"]  # JSON format! this is it
        self.inputs = self.match_json["inputs"]

        # Get features of the map in the AgeMap object
        # In some instances parser cannot find player positions - they are empty dictionaries
        # TODO alter API so that this analysis can be turned on or off, and is returned rather found from an attribute
        self.game_map = AgeMap(
            map=self.match_json["map"],
            gaia=self.match_json["gaia"],
            player_starting_locations=[
                tuple(self.match_json["players"][0]["position"].values()),
                tuple(self.match_json["players"][1]["position"].values()),
            ],
        )
        self.player_map_analysis = self.game_map.map_analysis

        # Transform raw data into usable chunks
        self.all_inputs_df = pd.json_normalize(self.inputs)
        self.all_actions_df = pd.json_normalize(self.actions)

        # Store list of players as GamePlayer objects; this stores indivdual data and data mining methods
        self.players_raw_info = self.match_json[
            "players"
        ]  # List of dictionaries, including civilisations; location;
        self.players = [
            GamePlayer(
                number=player["number"],
                name=player["name"],
                civilisation=player["civilization"],
                starting_position=player["position"],
                elo=player.get("rate_snapshot", None),  # sometimes not contained - do not fail, just need to flow on as NoneType
                winner=player["winner"],
                actions=self.all_actions_df.loc[
                    self.all_actions_df["player"] == player["number"], :
                ],
                inputs=self.all_inputs_df.loc[
                    self.all_inputs_df["player"] == player["number"], :
                ],
            )
            for player in self.players_raw_info
            if isinstance(player, dict)
        ]  # Note some TGs can have extra players but ints

        return

    def calculate_distance_between_players(
        self, location_one: tuple, location_two: tuple
    ) -> float:
        return math.dist(location_one, location_two)

    def calculate_difference_in_elo(
        self, player_one: GamePlayer, player_two: GamePlayer
    ):
        if player_one.elo is None or player_two.elo is None:
            logger.warning("One or both of these players did not have an Elo - no value")
            return 0  # Consider returning NoneType
        if player_one.player_won:
            return player_one.elo - player_two.elo
        return player_two.elo - player_one.elo

    def advanced_parser(self, include_map_analyses: bool = True) -> pd.Series:
        # TODO get the winner from players
        # TODO mine if boar or elephant

        # Extract the key statistics / data points
        # research times to mine out
        self.game_results = pd.Series()

        # Identify the opening strategy and choices of each player
        for player in self.players:
            player_opening_strategies = player.full_player_choices_and_strategy(
                feudal_time=player.age_up_times[2],
                castle_time=player.age_up_times[3],
                loom_time=player.technologies["Loom"],
                end_of_game=player.actions_df["timestamp"].max(),
                civilisation=player.civilisation
            )
            player_opening_strategies = player_opening_strategies.add_prefix(
                f"Player{player.number}.OpeningStrategy."
            )

            location_and_civilisation = pd.concat(
                [player.identify_civilisation(), player.identify_location()]
            )
            location_and_civilisation = location_and_civilisation.add_prefix(
                f"Player{player.number}.MapAndCiv."
            )

            self.game_results = pd.concat(
                [
                    self.game_results,
                    player_opening_strategies,
                    location_and_civilisation,
                ]
            )

        # Distance between players
        self.game_results["DistanceBetweenPlayers"] = (
            self.calculate_distance_between_players(
                location_one=self.game_results["Player1.MapAndCiv.StartingLocation"],
                location_two=self.game_results["Player2.MapAndCiv.StartingLocation"],
            )
        )

        # Elo difference between players - negative is winner is lower elo
        self.game_results["DifferenceInELO"] = self.calculate_difference_in_elo(
            player_one=self.players[0], player_two=self.players[1]
        )  # Currently, if either do not have an elo the difference value returned will be 0

        if include_map_analyses:
            return pd.concat([self.game_results, self.player_map_analysis])
        return self.game_results


if __name__ == "__main__":
    # TODO think about the best structure of the module in order to create a good API and workflow
    # - what information is must-have, what is optional
    # - some sort of fast vs full API, or breaking up by sections of analysis
    # - Maybe an option is like Opening - Feudal - Castle - Map analyses

    # TODO change so that functions and methods have LESS SIDE EFFECTS - THEN CAN BE TESTED EFFECTIVELY
    # TODO errors and logging

    def main():

        # test_file = Path("../../Data/RawAoe2RecordBytes/SD-AgeIIDE_Replay_324565276.aoe2record")
        test_file = Path(
            "Data/RawAoe2RecordBytes/AOE2ReplayBinary_2.aoe2record"
        )  # ../../ Using a downloaded game from the scrapper worked

        test_match = AgeGame(path=test_file)
        test_match.advanced_parser()
        print("\n")
        print(test_match.game_results)
        # print(test_match.player_map_analysis)
        test_results = pd.concat(
            [test_match.game_results, test_match.player_map_analysis]
        ).sort_index()
        test_results.to_csv("tests/Test_Games/Test_results.csv")

        return test_match.players[0].inputs_df

    test_inputs = main()

    # TODO-Feature Next castle age economic choices
