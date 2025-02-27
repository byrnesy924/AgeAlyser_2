"""Enums for build times, research times, creation times.
Data for this including some notes and exceptions can be found in the Data folder
"""

import logging
import warnings
from enum import Enum
from typing import Final, List

logger = logging.getLogger(__name__)


MilitaryBuildings: Final[List[str]] = [
    "Stable",
    "Archery Range",
    "Barracks",
    "Siege Workshop",
    "Castle",
    "Donjon",
    "Monastery",
    "Krepost",
]

FeudalAgeMilitaryUnits: Final[List[str]] = [
    "Scout Cavalry",
    "Skirmisher",
    "Archer",
    "Spearman",
]

BarracksUnits: Final[List[str]] = ["Militia", "Spearman"]

ArcheryRangeUnits: Final[List[str]] = [
    "Skirmisher",
    "Archer",
    "Cavalry Archer",
    "Elephant Archer",
    "Slinger",
    "Hand Canoneer",
    "Genitour",
]

StableUnits: Final[List[str]] = [
    "Scout Cavalry",
    "Knight",
    "Camel Rider",
    "Battle Elephant",
    "Steppe Lancer",
    "Tarkan",
    "Shrivamsha Rider",
]

# TODO include technologies in these units so that they can be modelled
BarracksUnits: Final[List[str]] = [
    "Militia",
    "Spearman",
    "Eagle Scout",
    "Condottiero",
    "Huskarl",
    "Flemish Militia",
]

SiegeWorkshopUnits: Final[List[str]] = [
    "Battering Ram",
    "Armoured Elephant",
    "Mangonel",
    "Scorpion",
    "Siege Tower",
    "Bombard Cannon",
]

ProductionBuildings: Final[List[str]] = [
    "Archery Range",
    "Barracks",
    "Castle",
    "Donjon",
    "Krepost",
    "Stable",
    "Siege Workshop",
    "Dock",
]

TownCentreUnitsAndTechs: Final[List[str]] = [
    "Villager",
    "Loom",
    "Wheelbarrow",
    "Hand Cart",
    "Town Watch",
    "Town Patrol",
    "Feudal Age",
    "Castle Age",
    "Imperial Age",
]


class BuildTimesEnum(Enum):
    """Enum of building times with override"""

    Archery_Range = 50
    Barracks = 50
    Blacksmith = 40
    Bombard_Tower = 80
    Castle = 200
    Dock = 35
    Donjon = 83
    Farm = 15
    Fish_Trap = 53
    Fortified_Wall = 8
    Gate = 70
    Guard_Tower = 80
    House = 25
    Keep = 80
    Krepost = 150
    Lumber_Camp = 35
    Market = 60
    Mill = 35
    Mining_Camp = 35
    Monastery = 40
    Mule_Cart = 25
    Outpost = 15
    Palisade_Wall = 5
    Palisade_Gate = 30
    Siege_Workshop = 40
    Stable = 50
    Stone_Wall = 8
    Town_Center = 150
    University = 60
    Watch_Tower = 80
    Wonder = 3503
    OVERRIDES = {
        "Sicilians": {"Town_Centre": 75, "Castle": 133.33, "Donjon": 83},
        "Cumans": {
            "Town_Centre": 270
        },  # Note this only applies in Feudal Age - handled in getter
        "Spanish": {"Wonder": 2694.615385},  # Note Spanish 30% handled in get function
    }
    RATEOVERRIDES = {"Spanish": 1.30, "Romans": 1.05}

    @classmethod
    def has_value(cls, name: str):
        """Helper function to check if the unit (name) exists in the enum and raise an error with the main program
        This passes a true false flag to the main program to be handled - I am open to better ways of doing this.
        """
        try:
            cls[name]
        except KeyError:
            if name == "" or name is None:
                # In this case error as MGZ has incorrectly read in a technology or there is a bug in AgeAlyser
                raise ValueError(f"A Building has been incorrectly parsed by MGZ or there is a bug in AgeAlyser. Please Raise an issue with details on the game (building: {name})")
            else:
                # In this case I have not updated the AgeAlyser Enums - raise a warning for the user to raise an issue but do not fail
                warnings.warn(f"A building could not be found in the game data. Please raise an issue on github (building: {name})")
            return False
        else:
            return True

    @classmethod
    def get(cls, name: str, civilisation: str, age: str = None) -> int:
        """Getter function to include civilisation overrides, e.g. Spanish 30% faster builders"""
        match (name, civilisation, age):
            case ("Town_Centre", "Cumans", "Feudal Age"):
                # Cuman second feudal TC scenario
                return cls["OVERRIDES"].value[civilisation][name]
            case (_, "Sicilians", _):
                if name in ["Town_Centre", "Castle", "Donjon"]:
                    return cls["OVERRIDES"].value[civilisation][name]
                return cls[name].value
            case ("Wonder", "Spanish", _):
                return cls["OVERRIDES"].value[civilisation][name]
            case (_, "Spanish", _):
                return cls[name].value / cls["RATEOVERRIDES"].value[civilisation]
            case (_, "Romans", _):
                return cls[name].value / cls["RATEOVERRIDES"].value[civilisation]
            case (_, _, _):
                return cls[name].value


class TechnologyResearchTimes(Enum):
    """Enum for technology research times with relevant overrides. Excel table for this can be found in Data folder"""

    Anarchy = 60
    Arbalest = 50
    Arbalester = 50
    Architecture = 70
    Arrowslits = 25
    Arson = 25
    Artillery = 40
    Atheism = 60
    Atonement = 40
    Ballistics = 60
    Banking = 50
    Bearded_Axe = 60
    Berserkergang = 40
    Blast_Furnace = 100
    Block_Printing = 55
    Bloodlines = 50
    Bodkin_Arrow = 35
    Bombard_Tower = 60
    Bow_Saw = 50
    Bracer = 40
    Burgundian_Vineyards = 45
    Cannon_Galleon = 50
    Capped_Ram = 50
    Caravan = 40
    Careening = 50
    Cartography = 60
    Castle_Age = 160
    Cavalier = 100
    Chain_Barding_Armor = 60
    Chain_Mail_Armor = 55
    Champion = 100
    Chatras = 40
    Chemistry = 100
    Coinage = 50
    Conscription = 60
    Crenellations = 60
    Crop_Rotation = 70
    Crossbowman = 35
    Detinets = 40
    Devotion = 40
    Double_Bit_Axe = 25
    Drill = 60
    Druzhina = 40
    Dry_Dock = 60
    Eagle_Warrior = 50
    El_Dorado = 50
    Elite_Ballista_Elephant = 70
    Elite_Berserk = 45
    Elite_Boyar = 60
    Elite_Cannon_Galleon = 30
    Elite_Cataphract = 50
    Elite_Chu_Ko_Nu = 50
    Elite_Conquistador = 60
    Elite_Eagle_Warrior = 40
    Elite_Elephant_Archer = 80
    Elite_Gbeto = 46
    Elite_Ghulam = 45
    Elite_Huskarl = 40
    Elite_Hussite_Wagon = 45
    Elite_Jaguar_Warrior = 45
    Elite_Janissary = 55
    Elite_Longboat = 60
    Elite_Longbowman = 60
    Elite_Mameluke = 50
    Elite_Mangudai = 50
    Elite_Plumed_Archer = 45
    Elite_Samurai = 60
    Elite_Skirmisher = 50
    Elite_Tarkan = 45
    Elite_Teutonic_Knight = 50
    Elite_Throwing_Axeman = 45
    Elite_Turtle_Ship = 65
    Elite_War_Elephant = 75
    Elite_War_Wagon = 75
    Elite_Woad_Raider = 45
    Faith = 60
    Farimba = 40
    Fast_Fire_Ship = 50
    Fervor = 50
    Feudal_Age = 130
    First_Crusade = 60
    Fletching = 30
    Forging = 50
    Fortified_Wall = 50
    Furor_Celtica = 50
    Galleon = 65
    Gambesons = 25
    Garland_Wars = 60
    Gillnets = 45
    Gold_Mining = 30
    Gold_Shaft_Mining = 75
    Guard_Tower = 30
    Grand_Trunk_Road = 40
    Guilds = 50
    Halberdier = 50
    Hand_Cart = 55
    Heated_Shot = 30
    Heavy_Camel_Rider = 125
    Heavy_Cavalry_Archer = 50
    Heavy_Cav_Archer = 50
    Heavy_Demolition_Ship = 50
    Heavy_Plow = 40
    Heavy_Scorpion = 50
    Herbal_Medicine = 35
    Heresy = 60
    Hill_Forts = 40
    Hoardings = 75
    Houfnice = 140
    Horse_Collar = 20
    Howdah = 40
    Husbandry = 50
    Hussar = 50
    Illumination = 65
    Imperial_Age = 190
    Imperial_Camel_Rider = 0  # TODO-missing
    Iron_Casting = 70
    Kataparuto = 60
    Keep = 75
    Leather_Archer_Armor = 55
    Lechitic_Legacy = 60
    Light_Cavalry = 45
    Logistica = 50
    Long_Swordsman = 45
    Loom = 25
    Mahouts = 50
    Mahayana = 60
    Manipur_Cavalry = 40
    Man_at_Arms = 40
    Masonry = 50
    Murder_Holes = 60
    Onager = 75
    Padded_Archer_Armor = 40
    Paiks = 45
    Paladin = 170
    Paper_Money = 60
    Parthian_Tactics = 65
    Perfusion = 40
    Pikeman = 45
    Plate_Barding_Armor = 75
    Plate_Mail_Armor = 70
    Redemption = 50
    Ring_Archer_Armor = 70
    Rocketry = 60
    Sanctity = 60
    Sappers = 10
    Scale_Barding_Armor = 45
    Scale_Mail_Armor = 40
    Shatagni = 0  # TODO
    Shinkichon = 60
    Shipwright = 60
    Siege_Engineers = 45
    Siege_Onager = 150
    Siege_Ram = 75
    Sipahi = 60
    Spies = 1
    Squires = 40
    Stirrups = 35
    Stone_Mining = 30
    Stone_Shaft_Mining = 75
    Supplies = 20
    Sultans = 40
    Supremacy = 60
    Szlachta_Privileges = 45
    Tigui = 40
    Theocracy = 75
    Thumb_Ring = 45
    Tower_Shields = 40
    Town_Patrol = 40
    Town_Watch = 25
    Tracking = 35
    Treadmill_Crane = 40
    Treason = 1
    Two_Handed_Swordsman = 75
    Two_Man_Saw = 100
    Wagenburg_Tactics = 45
    War_Galley = 50
    Wheelbarrow = 75
    Winged_Hussar = 0  # TODO
    Yasama = 40
    Yeomen = 60
    Zealotry = 50
    OVERRIDES = {
        "Malay": {
            "Feudal_Age": 86.66666667,
            "Castle_Age": 106.6666667,
            "Imperial_Age": 191.3333333,
        },
        "Goths": {"Loom": 0.01},
        # Note porto is done manually in getter
    }

    @classmethod
    def has_value(cls, name: str):
        """Helper function to check if the unit (name) exists in the enum and raise an error with the main program
        This passes a true false flag to the main program to be handled - I am open to better ways of doing this.
        """
        try:
            cls[name]
        except KeyError:
            if name == "" or name is None:
                # In this case error as MGZ has incorrectly read in a technology or there is a bug in AgeAlyser
                raise ValueError(f"A Technology has been incorrectly parsed by MGZ or there is a bug in AgeAlyser. Please Raise an issue with details on the game (tech: {name})")
            else:
                # In this case I have not updated the AgeAlyser Enums - raise a warning for the user to raise an issue but do not fail
                warnings.warn(f"A technology could not be found in the game data. Please raise an issue on github (tech: {name})")
            return False
        else:
            return True

    @classmethod
    def get(cls, name: str, civilisation: str):
        # TODO - check university researches faster, malians i think?
        match (civilisation, name):
            case "Malay", _:
                if name in ["Feudal_Age", "Castle_Age", "Imperial_Age"]:
                    return cls["OVERRIDES"].value[civilisation][name]
                return cls[name].value
            case "Goths", "Loom":
                return cls["OVERRIDES"].value[civilisation][name]
            case "Bulgarians", _:
                # Note that this is actually a team bonus TODO handle correctly
                if name in [
                    "Fletching",
                    "Bodkin_Arrow",
                    "Bracer",
                    "Padded_Archer_Armor",
                    "Leather_Archer_Armor",
                    "Ring_Archer_Armour",
                    "Forging",
                    "Iron_Casting",
                    "Blast_Furnace",
                    "Scale_Barding_Armor",
                    "Chain_Barding_Armor",
                    "Plate_Barding_Armor",
                    "Scale_Mail_Armor",
                    "Chain_Mail_Armor",
                    "Plate_Mail_Armor",
                ]:  # This is all the blacksmith
                    return cls[name].value / 1.80
                return cls[name].value
            case "Vietnamese", _:
                if name in [
                    "Wheelbarrow",
                    "Hand_Cart",
                    "Double_Bit_Axe",
                    "Bow_Saw",
                    "Two_Man_Saw",
                    "Horse_Collar",
                    "Heavy_Plow",
                    "Crop_Rotation",
                    "Gold_Mining",
                    "Gold_Shaft_Mining",
                    "Stone_Mining",
                    "Stone_Shaft_Mining",
                ]:
                    return cls[name].value / 2
                return cls[name].value
            case "Portuguese", _:
                if name in ["Feudal_Age", "Castle_Age", "Imperial_Age"]:
                    return cls[name].value
                return cls[name].value / 1.25
            case _, _:
                return cls[name].value


class UnitCreationTime(Enum):
    # Technologies that are researched at a production building are put in here just so the code is shorter, see the production buildings
    # Town Centre
    Castle_Age = TechnologyResearchTimes.get("Castle_Age", "")
    Feudal_Age = TechnologyResearchTimes.get("Feudal_Age", "")
    Imperial_Age = TechnologyResearchTimes.get("Imperial_Age", "")
    Loom = TechnologyResearchTimes.get("Loom", "")
    Town_Watch = TechnologyResearchTimes.get("Town_Watch", "")
    Town_Patrol = TechnologyResearchTimes.get("Town_Patrol", "")
    Wheelbarrow = TechnologyResearchTimes.get("Wheelbarrow", "")
    Hand_Cart = TechnologyResearchTimes.get("Hand_Cart", "")

    # actual units below
    Arbalest = 27
    Arbalester = 27
    Archer = 35
    Armored_Elephant = 36
    Battering_Ram = 36
    Berserk = 16
    Bombard_Cannon = 56
    Battle_Elephant = 24
    Camel = 22
    Cannon_Galleon = 46
    Capped_Ram = 36
    Cataphract = 20
    Cavalier = 30
    Cavalry_Archer = 34
    Champion = 21
    Chu_Ko_Nu = 19
    Conquistador = 24
    Crossbowman = 27
    Deer = 0
    Demolition_Ship = 31
    Eagle_Scout = 60  # in castle age goes down to 30... TODO
    Eagle_Warrior = 35
    Elephant_Archer = 32
    Elite_Battle_Elephant = 24
    Elite_Berserk = 16
    Elite_Cannon_Galleon = 46
    Elite_Cataphract = 20
    Elite_Chu_Ko_Nu = 13
    Elite_Conquistador = 24
    Elite_Eagle_Warrior = 20
    Elite_Elephant_Archer = 32
    Elite_Ghulam = 12
    Elite_Huskarl = 16
    Elite_Jaguar_Warrior = 17
    Elite_Janissary = 17
    Elite_Longboat = 25
    Elite_Longbowman = 19
    Elite_Mameluke = 23
    Elite_Mangudai = 26
    Elite_Plumed_Archer = 16
    Elite_Samurai = 9
    Elite_Skirmisher = 22
    Elite_Tarkan = 14
    Elite_Teutonic_Knight = 12
    Elite_Throwing_Axeman = 17
    Elite_Turtle_Ship = 50
    Elite_War_Elephant = 31
    Elite_War_Wagon = 25
    Elite_Woad_Raider = 10
    Fast_Fire_Ship = 36
    Fire_Ship = 36
    Fishing_Ship = 40
    Galleon = 36
    Galley = 60
    Ghulam = 12
    Halberdier = 22
    Hand_Cannoneer = 34
    Heavy_Camel = 22
    Heavy_Cavalry_Archer = 27
    Heavy_Demolition_Ship = 31
    Heavy_Scorpion = 30
    Horse = 0
    Huskarl = 16
    Hussar = 30
    Jaguar = 0
    Jaguar_Warrior = 17
    Janissary = 17
    King = 30
    Knight = 30
    Light_Cavalry = 30
    Long_Swordsman = 21
    Longboat = 25
    Longbowman = 19
    Mameluke = 23
    Man_at_Arms = 21
    Mangonel = 46
    Mangudai = 26
    Militia = 21
    Missionary = 51
    Monk = 51
    Onager = 46
    Paladin = 30
    Petard = 25
    Pikeman = 22
    Plumed_Archer = 16
    Samurai = 9
    Seige_Tower = 36
    Scorpion = 30
    Scout_Cavalry = 30
    Sheep = 0
    Siege_Elephant = 36
    Siege_Onager = 46
    Siege_Ram = 36
    Skirmisher = 22
    Slinger = 25
    Spearman = 22
    Steppe_Lancer = 24
    Tarkan = 14
    Teutonic_Knight = 12
    Throwing_Axeman = 17
    Trade_Cart = 50
    Trade_Cog = 36
    Transport_Ship = 45
    Trebuchet = 50
    Trebuchet_packed = 50
    Turkey = 0
    Turtle_Ship = 50
    Two_Handed_Swordsman = 21
    Villager = 25
    War_Elephant = 31
    War_Galley = 36
    War_Wagon = 25
    Wild_Boar = 0
    Woad_Raider = 10
    Wolf = 0
    OVERRIDES = {}

    @classmethod
    def has_value(cls, name: str):
        """Helper function to check if the unit (name) exists in the enum and raise an error with the main program
        This passes a true false flag to the main program to be handled - I am open to better ways of doing this.
        """
        try:
            cls[name]
        except KeyError:
            if name == "" or name is None:
                # In this case error as MGZ has incorrectly read in a technology or there is a bug in AgeAlyser
                raise ValueError(f"A unit has been incorrectly parsed by MGZ or there is a bug in AgeAlyser. Please Raise an issue with details on the game (unit: {name})")
            else:
                # In this case I have not updated the AgeAlyser Enums - raise a warning for the user to raise an issue but do not fail
                warnings.warn(f"A unit could not be found in the game data. Please raise an issue on github (unit: {name})")
            return False
        else:
            return True

    @classmethod
    def get(cls, name: str, civilisation: str):
        # TODO - include Berbers Kasbah technology flag in most appropriate way
        # TODO - include Cumans Steppe husbandry tech
        # TODO - Franks stables
        # TODO think about passing the building as a parameter here to reduce the if statements - more readable and faster code
        # TODO - Romans centurion and knight; need to be included
        if " " in name:
            name = name.replace(" ", "_")

        match (name, civilisation):
            case "Monk", "Lithuanians":
                return cls[name].value / 1.20
            case "Trade_Cart", "Bohemians":
                return cls[name].value / 1.80
            case _, "Magyars":
                if name in [
                    "Cavalry_Archer",
                    "Heavy_Cavalry_Archer",
                ]:  # Note this is a team bonus
                    return cls[name].value / 1.25
                return cls[name].value
            case _, "Britons":
                if name in [
                    "Archer",
                    "Crossbow",
                    "Arbalest",
                    "Skirmisher",
                    "Elite_Skirmisher",
                ]:
                    cls[name].value / 1.1
                return cls[name].value
            case _, "Celts":
                if name in [
                    "Mangonel",
                    "Scorpion",
                    "Ram",
                    "Onager",
                    "Siege_Onager",
                    "Capped_Ram",
                    "Siege_Ram",
                    "Heavy_Scorpion",
                ]:
                    cls[name].value / 1.2  # Note this is a team bonus as well
                return cls[name].value
            case _, "Goths":
                if name in [
                    "Militia",
                    "Man_At_Arms",
                    "Long_Swordman",
                    "Two_Handed_Swordsman",
                    "Champion",
                    "Spearman",
                    "Pikeman",
                    "Halberdier",
                ]:
                    return cls[name].value / 1.20
                return cls[name].value
            case _, "Gurjaras":
                if name in [
                    "Camel",
                    "Heavy_Camel",
                    "Battle_Elephant",
                    "Elite_Battle_Elephant",
                    "Elephant_Archer",
                    "Elite_Elephant_Archer",
                    "Armored_Elephant",
                    "Siege_Elephant",
                ]:
                    return cls[name].value / 1.25
                return cls[name].value
            case _, "Huns":
                # Note the stables is also a team bonus
                if name in [
                    "Scout_Cavalry",
                    "Light_Cavalry",
                    "Hussar",
                    "Knight",
                    "Cavalier",
                    "Paladin",
                ]:
                    return cls[name].value / 1.20
                return cls[name].value
            case _, "Turks":
                if name in ["Hand_Canoneer", "Janissary", "Elite_Janissary"]:
                    return cls[name].value / 1.25
                return cls[name].value
            case _, "Aztecs":
                return cls[name].value / 1.11
            case _, _:
                return cls[name].value


class Civilisations(Enum):
    """TODO assign and ID to validate strings and create automated testing + exceptions"""

    pass


if __name__ == "__main__":
    print(TechnologyResearchTimes.get("Loom", "Franks"))
    print(UnitCreationTime.get("Archer", "Britons"))
    print(BuildTimesEnum.get("House", "Spanish"))

    print(TechnologyResearchTimes.has_value("TEST"))  # TODO automate
