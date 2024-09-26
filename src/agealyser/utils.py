import pandas as pd

from abc import ABC, abstractmethod
# import logging

from enums import (  # Getting a bit too cute here with constants but it will do for now
    ArcheryRangeUnits,
    StableUnits,
    SiegeWorkshopUnits

)


class ProductionBuilding(ABC):
    """This abstract base class models the function of a production building, including:
    - creating units, - storing upgrades, - measuring idle time"""

    @abstractmethod
    def produce_units(self, data: pd.DataFrame, production_building_units: list, units_production_enum) -> pd.DataFrame:
        """Take the time stamps of units, as well as the upgrades, and work out when they wouldve been produced,
        taking into account 1 at a time creation (i.e., queuing)

        :return pd.DataFrame: a dataframe of units and when they were created

        """
        if not all(col in data.columns.to_list() for col in ["timestamp", "param", "payload.object_ids"]):
            # TODO log
            raise ValueError("Missing a column from data in Production Building")

        pass

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


class ArcheryRange(ProductionBuilding):
    def __init__(self, building_type: str, units: list, id: int, x: float, y: float, data: pd.DataFrame, player: int) -> None:
        self._building_type = building_type
        self._units = units
        self._id = id
        self._x = x
        self._y = y
        self._data = data
        self._player = player

    def produce_units(self) -> pd.DataFrame:
        return super().produce_units()

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


class Stable(ProductionBuilding):
    def __init__(self, building_type: str, units: list, id: int, x: float, y: float, data: pd.DataFrame, player: int) -> None:
        self._building_type = building_type
        self._units = units
        self._id = id
        self._x = x
        self._y = y
        self._data = data
        self._player = player

    def produce_units(self) -> pd.DataFrame:
        return super().produce_units()

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


class SiegeWorkshop(ProductionBuilding):
    def __init__(self, building_type: str, units: list, id: int, x: float, y: float, data: pd.DataFrame, player: int) -> None:
        self._building_type = building_type
        self._units = units
        self._id = id
        self._x = x
        self._y = y
        self._data = data
        self._player = player

    def produce_units(self) -> pd.DataFrame:
        return super().produce_units()

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
    def create_production_building_and_remove_used_id(self, building_type: str, units: list, inputs_data: pd.DataFrame, player: int):
        """Identify all the Production Buildings and Create them"""
        relevent_buildings_produced = inputs_data.loc[(inputs_data["param"] == building_type) & (inputs_data["type"] == "Build")]
        if relevent_buildings_produced.empty:
            # TODO handle when it should not create the object; log m
            return None

        relevent_buildings_produced = relevent_buildings_produced[["timestamp", "param", "position.x", "position.y"]]

        relevent_units_queued = inputs_data.loc[inputs_data["param"].isin(units)]
        relevent_units_queued["payload.object_ids"] = relevent_units_queued["payload.object_ids"].apply(lambda x: x[0])

        first_appearance_of_each_building = relevent_units_queued.groupby("payload.object_ids", as_index=False).min()
        dataframe_to_marry_up_to_production = first_appearance_of_each_building[["timestamp", "payload.object_ids"]]

        df_to_return = pd.concat(
            [relevent_buildings_produced.reset_index(drop=True),
             dataframe_to_marry_up_to_production["payload.object_ids"].reset_index(drop=True)],
            axis=1,
        )

        return [
            self.factory_method(building_type,
                                id=x["payload.object_ids"],
                                x=x["position.x"],
                                y=x["position.y"],
                                data=relevent_units_queued,
                                player=player
                                )
            for index, x in df_to_return.iterrows()
        ]


class ArcheryRangeProductionBuildingFactory(AbstractProductionBuildingFactory):
    def factory_method(self, building_type: str, id: int, x: float, y: float, data: pd.DataFrame, player: int) -> ProductionBuilding:
        return ArcheryRange(building_type=building_type, units=ArcheryRangeUnits, id=id, x=x, y=y, data=data, player=player)

    def create_production_building_and_remove_used_id(self, inputs_data: pd.DataFrame, player: int):
        return super().create_production_building_and_remove_used_id("Archery Range", ArcheryRangeUnits, inputs_data, player=player)


class StableProductionBuildingFactory(AbstractProductionBuildingFactory):
    def factory_method(self, building_type: str, id: int, x: float, y: float, data: pd.DataFrame, player: int) -> ProductionBuilding:
        return Stable(building_type=building_type, units=StableUnits, id=id, x=x, y=y, data=data, player=player)

    def create_production_building_and_remove_used_id(self, inputs_data: pd.DataFrame, player: int):
        return super().create_production_building_and_remove_used_id("Stable", StableUnits, inputs_data, player)


class SiegeWorkshopProductionBuildingFactory(AbstractProductionBuildingFactory):
    def factory_method(self, building_type: str, id: int, x: float, y: float, data: pd.DataFrame, player: int) -> ProductionBuilding:
        return SiegeWorkshop(building_type=building_type, units=SiegeWorkshopUnits, id=id, x=x, y=y, data=data, player=player)

    def create_production_building_and_remove_used_id(self, inputs_data: pd.DataFrame, player: int):
        return super().create_production_building_and_remove_used_id("Siege Workshop", SiegeWorkshopUnits, inputs_data, player=player)


# TODO - Castle, Dock, Monastery, etc.


if __name__ == "__main__":
    test_inputs = pd.read_csv(r"DataExploration\Player1_inputs.csv")

    archery_ranges = ArcheryRangeProductionBuildingFactory().create_production_building_and_remove_used_id(inputs_data=test_inputs,
                                                                                                           player=1)
    print(archery_ranges)
