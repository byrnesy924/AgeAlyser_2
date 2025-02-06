import pandas as pd
import logging

logger = logging.getLogger(__name__)

from abc import ABC, abstractmethod

from agealyser.agealyser_enums import (  # Getting a bit too cute here with constants but it will do for now
    UnitCreationTime,
    ArcheryRangeUnits,
    BarracksUnits,
    StableUnits,
    SiegeWorkshopUnits,
    TownCentreUnitsAndTechs,
)


class MGZParserException(Exception):
    """Exception for when the MGZ Parser cannot parse a game - this package is dependant on MGZ. If it errors,
    then need to fail and return the reason with this error
    """

    def __init__(self, file_name, *args):
        self.message = f"MGZ Parser error for the file {file_name}. This may be caused by a game update or using an invalid file."
        super().__init__(self.message, *args)


class ProductionBuilding(ABC):
    """This abstract base class models the function of a production building, including:
    - creating units, - storing upgrades, - measuring idle time"""

    @abstractmethod
    def produce_units(self, data: pd.DataFrame, units_production_enum) -> pd.DataFrame:
        """Take the time stamps of units, as well as the upgrades, and work out when they wouldve been produced,
        taking into account 1 at a time creation (i.e., queuing)

        :return pd.DataFrame: a dataframe of units and when they were created

        """
        # TODO - add in upgrades before this
        # self.apply_unit_upgrades()  # call this method first, so that below works, and that produce_units() is only main call

        if not all(col in data.columns.to_list() for col in ["timestamp", "param"]):
            # TODO log
            raise ValueError(
                f"Missing a column from data in Production Building.\nCols: {data.columns}"
            )

        # coerce timestamp to time delta
        data["timestamp"] = pd.to_timedelta(data["timestamp"])

        # identify start times of all relevant units
        data["CreationTime"] = data["param"].apply(
            lambda x: pd.Timedelta(
                seconds=units_production_enum.get(name=x, civilisation="")
            )
        )  # TODO add civ to this object
        data["UnitCreatedTimestamp"] = data["timestamp"] + data["CreationTime"]
        data.reset_index(inplace=True)

        # Iterate through units. If queued during creation of previous unit, then push out times
        for index, row in data.iterrows():
            if index == 0:  # skip first unit
                continue
            if (
                pd.Timedelta(row["timestamp"])
                < data.loc[index - 1, "UnitCreatedTimestamp"]
            ):
                data.loc[index, "UnitCreatedTimestamp"] += (
                    data.loc[index - 1, "UnitCreatedTimestamp"] - row["timestamp"]
                )
                data.loc[index, "timestamp"] += (
                    data.loc[index - 1, "UnitCreatedTimestamp"] - row["timestamp"]
                )

        # sort table
        # maybe iterate through is simplest - if start_above + creation_time_above > start_time
        # then start_time = start_above + creation_time_above
        # problem - distribution of units across buildings?? way to differentiate?

        return data[["param", "UnitCreatedTimestamp"]]

    @abstractmethod
    def apply_unit_upgrades(self) -> pd.DataFrame:
        """Method for finding when units have been upgraded. Requires coupling with player technologies"""
        pass

    @abstractmethod
    def count_building_idle_time(self) -> int:
        pass

    @property
    @abstractmethod
    def building_type(self):
        return self._building_type  # string type

    @property
    @abstractmethod
    def units(self):
        return self._units  # CONST list of units

    @property
    @abstractmethod
    def id(self):
        return self._id  # Buildings ID

    @property
    @abstractmethod
    def x(self):
        return self._x

    @property
    @abstractmethod
    def y(self):
        return self._y

    @property
    @abstractmethod
    def data(self):
        return self._data

    @property
    @abstractmethod
    def player(self):
        return self._player


class Barracks(ProductionBuilding):
    def __init__(
        self,
        building_type: str,
        units: list,
        id: int,
        x: float,
        y: float,
        data: pd.DataFrame,
        player: int,
    ) -> None:
        self._building_type = building_type
        self._units = units
        self._id = id
        self._x = x
        self._y = y
        self._data = data
        self._player = player

    def produce_units(self) -> pd.DataFrame:
        return super().produce_units(self._data, UnitCreationTime)

    def apply_unit_upgrades(self) -> pd.DataFrame:
        return super().apply_unit_upgrades()

    def count_building_idle_time(self) -> int:
        return super().count_building_idle_time()

    @property
    def building_type(self):
        return self._building_type  # string type

    @property
    def units(self):
        return self._units  # CONST list of units

    @property
    def id(self):
        return self._id  # Building's ID

    @property
    def x(self):
        return self._x

    @property
    def y(self):
        return self._y

    @property
    def data(self):
        return self._data

    @property
    def player(self):
        return self._player


class ArcheryRange(ProductionBuilding):
    def __init__(
        self,
        building_type: str,
        units: list,
        id: int,
        x: float,
        y: float,
        data: pd.DataFrame,
        player: int,
    ) -> None:
        self._building_type = building_type
        self._units = units
        self._id = id
        self._x = x
        self._y = y
        self._data = data
        self._player = player

    def produce_units(self) -> pd.DataFrame:
        return super().produce_units(self._data, UnitCreationTime)

    def apply_unit_upgrades(self) -> pd.DataFrame:
        return super().apply_unit_upgrades()

    def count_building_idle_time(self) -> int:
        return super().count_building_idle_time()

    @property
    def building_type(self):
        return self._building_type  # string type

    @property
    def units(self):
        return self._units  # CONST list of units

    @property
    def id(self):
        return self._id  # Building's ID

    @property
    def x(self):
        return self._x

    @property
    def y(self):
        return self._y

    @property
    def data(self):
        return self._data

    @property
    def player(self):
        return self._player


class Stable(ProductionBuilding):
    def __init__(
        self,
        building_type: str,
        units: list,
        id: int,
        x: float,
        y: float,
        data: pd.DataFrame,
        player: int,
    ) -> None:
        self._building_type = building_type
        self._units = units
        self._id = id
        self._x = x
        self._y = y
        self._data = data
        self._player = player

    def produce_units(self) -> pd.DataFrame:
        return super().produce_units(self._data, UnitCreationTime)

    def apply_unit_upgrades(self) -> pd.DataFrame:
        return super().apply_unit_upgrades()

    def count_building_idle_time(self) -> int:
        return super().count_building_idle_time()

    @property
    def building_type(self):
        return self._building_type  # string type

    @property
    def units(self):
        return self._units  # CONST list of units

    @property
    def id(self):
        return self._id  # Building's ID

    @property
    def x(self):
        return self._x

    @property
    def y(self):
        return self._y

    @property
    def data(self):
        return self._data

    @property
    def player(self):
        return self._player


class SiegeWorkshop(ProductionBuilding):
    def __init__(
        self,
        building_type: str,
        units: list,
        id: int,
        x: float,
        y: float,
        data: pd.DataFrame,
        player: int,
    ) -> None:
        self._building_type = building_type
        self._units = units
        self._id = id
        self._x = x
        self._y = y
        self._data = data
        self._player = player

    def produce_units(self) -> pd.DataFrame:
        return super().produce_units(self._data, UnitCreationTime)

    def apply_unit_upgrades(self) -> pd.DataFrame:
        return super().apply_unit_upgrades()

    def count_building_idle_time(self) -> int:
        return super().count_building_idle_time()

    @property
    def building_type(self):
        return self._building_type  # string type

    @property
    def units(self):
        return self._units  # CONST list of units

    @property
    def id(self):
        return self._id  # Building's ID

    @property
    def x(self):
        return self._x

    @property
    def y(self):
        return self._y

    @property
    def data(self):
        return self._data

    @property
    def player(self):
        return self._player


class TownCentre(ProductionBuilding):
    def __init__(
        self,
        building_type: str,
        units: list,
        id: int,
        x: float,
        y: float,
        data: pd.DataFrame,
        player: int,
    ) -> None:
        self._building_type = building_type
        self._units = units  # Include techs like Loom, Wheelbarrow, etc.
        self._id = id
        self._x = x
        self._y = y
        self._data = data
        self._player = player

    def produce_units(self) -> pd.DataFrame:
        return super().produce_units(self._data, UnitCreationTime)

    def apply_unit_upgrades(self) -> pd.DataFrame:
        """Boiler plate should never be called"""
        return super().apply_unit_upgrades()

    def count_building_idle_time(self) -> int:
        return super().count_building_idle_time()

    @property
    def building_type(self):
        return self._building_type  # string type

    @property
    def units(self):
        return self._units  # CONST list of units

    @property
    def id(self):
        return self._id  # Building's ID

    @property
    def x(self):
        return self._x

    @property
    def y(self):
        return self._y

    @property
    def data(self):
        return self._data

    @property
    def player(self):
        return self._player


class AbstractProductionBuildingFactory(ABC):
    """This Factory solves the complex problem of identifying production buildings in the input data and creating the correct
    Production Building Object, with its type, location, and, critically, its ID!
    In brief, because of the structure of the input data, we need to get the ID from the first unit created there,
    but IDs cannot be re-used.
    """

    @abstractmethod
    def factory_method(self):
        pass

    @abstractmethod
    def create_production_building_and_remove_used_id(
        self, building_type: str, units: list, inputs_data: pd.DataFrame, player: int
    ):
        """Identify all the Production Buildings and Create them"""
        relevent_buildings_produced = inputs_data.loc[
            (inputs_data["param"] == building_type) & (inputs_data["type"] == "Build")
        ]
        if relevent_buildings_produced.empty:
            # TODO handle when it should not create the object; log m
            return None

        relevent_buildings_produced = relevent_buildings_produced[
            ["timestamp", "payload.object_ids", "param", "position.x", "position.y"]
        ]

        relevent_units_queued = inputs_data.loc[
            inputs_data["param"].isin(units)
        ]  # 24 Jan note units now includes TECHNOLOGIES

        # Discovery - the payload object IDs are the buildings queued in. This is a list of buildings
        # so - split them up by building and assign accordingly.
        all_units_all_buildings = pd.get_dummies(
            relevent_units_queued["payload.object_ids"].explode()
        )
        building_ids = all_units_all_buildings.columns
        relevent_units_queued = relevent_units_queued.join(all_units_all_buildings)

        first_appearance_of_each_building = relevent_buildings_produced.groupby(
            ["position.x", "position.y"], as_index=False
        ).min()
        dataframe_to_marry_up_to_production = first_appearance_of_each_building[
            ["timestamp", "payload.object_ids"]
        ]

        # get x and y coords of buildings
        df_to_return = pd.concat(
            [
                relevent_buildings_produced.reset_index(drop=True),
                dataframe_to_marry_up_to_production["timestamp"].reset_index(drop=True),
            ],
            axis=1,
        )
        buildings_used = len(building_ids)
        df_to_return = df_to_return.loc[
            0 : buildings_used - 1, :
        ]  # remove unused buildigns
        if len(df_to_return.index) < buildings_used:
            logger.warning(
                "Producing from more buildings than have created! TODO log what game this is"
            )  # TODO log what game is this
            df_to_return.index = building_ids.sort_values()[0 : len(df_to_return)]
        else:
            df_to_return.index = building_ids.sort_values()

        # if - else handles buildings that never make units
        return [
            (
                self.factory_method(
                    building_type,
                    id=index,
                    x=x["position.x"],
                    y=x["position.y"],
                    data=relevent_units_queued.loc[
                        relevent_units_queued[index], ["timestamp", "type", "param"]
                    ],
                    player=player,
                )
                if index in relevent_units_queued.columns
                else None
            )
            for index, x in df_to_return.iterrows()
        ]


class BarracksProductionBuildingFactory(AbstractProductionBuildingFactory):
    def factory_method(
        self,
        building_type: str,
        id: int,
        x: float,
        y: float,
        data: pd.DataFrame,
        player: int,
    ) -> ProductionBuilding:
        return Barracks(
            building_type=building_type,
            units=BarracksUnits,
            id=id,
            x=x,
            y=y,
            data=data,
            player=player,
        )

    def create_production_building_and_remove_used_id(
        self, inputs_data: pd.DataFrame, player: int
    ):
        return super().create_production_building_and_remove_used_id(
            "Barracks", BarracksUnits, inputs_data, player=player
        )


class ArcheryRangeProductionBuildingFactory(AbstractProductionBuildingFactory):
    def factory_method(
        self,
        building_type: str,
        id: int,
        x: float,
        y: float,
        data: pd.DataFrame,
        player: int,
    ) -> ProductionBuilding:
        return ArcheryRange(
            building_type=building_type,
            units=ArcheryRangeUnits,
            id=id,
            x=x,
            y=y,
            data=data,
            player=player,
        )

    def create_production_building_and_remove_used_id(
        self, inputs_data: pd.DataFrame, player: int
    ):
        return super().create_production_building_and_remove_used_id(
            "Archery Range", ArcheryRangeUnits, inputs_data, player=player
        )


class StableProductionBuildingFactory(AbstractProductionBuildingFactory):
    def factory_method(
        self,
        building_type: str,
        id: int,
        x: float,
        y: float,
        data: pd.DataFrame,
        player: int,
    ) -> ProductionBuilding:
        return Stable(
            building_type=building_type,
            units=StableUnits,
            id=id,
            x=x,
            y=y,
            data=data,
            player=player,
        )

    def create_production_building_and_remove_used_id(
        self, inputs_data: pd.DataFrame, player: int
    ):
        return super().create_production_building_and_remove_used_id(
            "Stable", StableUnits, inputs_data, player
        )


class SiegeWorkshopProductionBuildingFactory(AbstractProductionBuildingFactory):
    def factory_method(
        self,
        building_type: str,
        id: int,
        x: float,
        y: float,
        data: pd.DataFrame,
        player: int,
    ) -> ProductionBuilding:
        return SiegeWorkshop(
            building_type=building_type,
            units=SiegeWorkshopUnits,
            id=id,
            x=x,
            y=y,
            data=data,
            player=player,
        )

    def create_production_building_and_remove_used_id(
        self, inputs_data: pd.DataFrame, player: int
    ):
        return super().create_production_building_and_remove_used_id(
            "Siege Workshop", SiegeWorkshopUnits, inputs_data, player=player
        )


class TownCentreBuildingFactory(AbstractProductionBuildingFactory):
    def factory_method(
        self,
        building_type: str,
        id: int,
        x: float,
        y: float,
        data: pd.DataFrame,
        player: int,
    ) -> ProductionBuilding:
        return TownCentre(
            building_type=building_type,
            units=TownCentreUnitsAndTechs,
            id=id,
            x=x,
            y=y,
            data=data,
            player=player,
        )

    def create_production_building_and_remove_used_id(
        self,
        inputs_data: pd.DataFrame,
        player: int,
        position_x: float = None,
        position_y: float = None,
    ):
        # Hack for town centres - in non-Nomad games, we need to add a line for the first town centre because it is not built
        check_for_build_town_centre = inputs_data.loc[
            (inputs_data["type"] == "Build")
            & (inputs_data["param"] == "Town Center")
            & (inputs_data["timestamp"] < pd.Timedelta(seconds=100)),
            :,
        ]  # give 100 seconds incase of Nomad start

        if check_for_build_town_centre.empty:
            # Create the data for this
            id_of_first_tc = inputs_data.loc[
                inputs_data["param"] == "Villager", "payload.object_ids"
            ].min()  # Hack - get this from the villagers created
            initial_tc_cols = [
                "timestamp",
                "type",
                "param",
                "player",
                "payload.object_ids",
                "position.x",
                "position.y",
            ]
            initial_tc_vals = [
                [
                    pd.Timedelta(-150),
                    "Build",
                    "Town Center",
                    player,
                    id_of_first_tc,
                    position_x,
                    position_y,
                ]
            ]  # note -150 as takes 150 seconds to build

            tc_df = pd.DataFrame(initial_tc_vals, columns=initial_tc_cols)
            # concat it onto the inputs data and then the rest of the logic should handle correctly
            inputs_data = pd.concat([tc_df, inputs_data], ignore_index=True)

        return super().create_production_building_and_remove_used_id(
            "Town Center", TownCentreUnitsAndTechs, inputs_data, player=player
        )


# TODO - Castle, Dock, Monastery, etc.


if __name__ == "__main__":
    test_inputs = pd.read_csv(
        r"Data\TestGameDataExploration\Player1_inputs.csv"
    )  # ..\..\

    archery_ranges = ArcheryRangeProductionBuildingFactory().create_production_building_and_remove_used_id(
        inputs_data=test_inputs, player=1
    )
    print(archery_ranges[0].produce_units())
