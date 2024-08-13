"""Enums for build times, research times, creation times. 
Data for this including some notes and exceptions can be found in the Data folder
"""
from enum import Enum


class BuildTimesEnum(Enum):
    """Enum of building times with override
    """
    Archery_Range = 50
    Barracks = 50
    Blacksmith = 40
    Bombard_Tower = 80
    Castle = 200
    Dock = 35
    Farm = 15
    Fish_Trap = 53
    Fortified_Wall = 8
    Gate = 70
    Guard_Tower = 80
    House = 25
    Keep = 80
    Lumber_Camp = 35
    Market = 60
    Mill = 35
    Mining_Camp = 35
    Monastery = 40
    Outpost = 15
    Palisade_Wall = 5
    Siege_Workshop = 40
    Stable = 50
    Stone_Wall = 8
    Town_Center = 150
    University = 60
    Watch_Tower = 80
    Wonder = 3503
    OVERRIDES = {
        "Sicilians": {"Town_Centre": 75, "Castle": 133.33, "Donjon": 83},
        "Cumans": {"Town_Centre": 270},  # Note this only applies in Feudal Age - handled in getter
        "Spanish": {"Wonder": 2694.615385}  # Note Spanish 30% handled in get function
    }
    RATEOVERRIDES = {"Spanish": 1.30, "Romans": 1.05}

    @classmethod
    def get(cls, name: str, civilisation: str, age: str = None) -> int:
        """Getter function to include civilisation overrides, e.g. Spanish 30% faster builders"""
        match (name, civilisation, age):
            case ("Town_Centre", "Cumans", "Feudal Age"):
                # Cuman second feudal TC scenario
                return cls["OVERRIDES"][civilisation][name]
            case (_, "Sicilians", _):
                if name in ["Town_Centre", "Castle", "Donjon"]:
                    return cls["OVERRIDES"][civilisation][name]
                return cls[name]
            case ("Wonder", "Spanish", _):
                return cls["OVERRIDES"][civilisation][name]
            case (_, "Spanish", _):
                return cls[name]/cls["RATEOVERRIDES"][civilisation]
            case (_, "Romans", _):
                return cls[name]/cls["RATEOVERRIDES"][civilisation]
            case (_, _, _):
                return cls[name]


class TechnologyResearchTimes(Enum):
    """Enum for technology research times with relevant overrides. Excel table for this can be found in Data folder"""
    Anarchy = 60
    Arbalest = 50
    Architecture = 70
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
    Chemistry = 100
    Coinage = 50
    Conscription = 60
    Crenellations = 60
    Crop_Rotation = 70
    Crossbowman = 35
    Double_Bit_Axe = 25
    Drill = 60
    Dry_Dock = 60
    El_Dorado = 50
    Elite_Berserk = 45
    Elite_Cannon_Galleon = 30
    Elite_Cataphract = 50
    Elite_Chu_Ko_Nu = 50
    Elite_Conquistador = 60
    Elite_Eagle_Warrior = 40
    Elite_Huskarl = 40
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
    Fast_Fire_Ship = 50
    Fervor = 50
    Feudal_Age = 130
    Fletching = 30
    Forging = 50
    Fortified_Wall = 50
    Furor_Celtica = 50
    Galleon = 65
    Garland_Wars = 60
    Gold_Mining = 30
    Gold_Shaft_Mining = 75
    Guard_Tower = 30
    Guilds = 50
    Halberdier = 50
    Hand_Cart = 55
    Heated_Shot = 30
    Heavy_Camel = 125
    Heavy_Cavalry_Archer = 50
    Heavy_Demolition_Ship = 50
    Heavy_Plow = 40
    Heavy_Scorpion = 50
    Herbal_Medicine = 35
    Heresy = 60
    Hoardings = 75
    Horse_Collar = 20
    Husbandry = 50
    Hussar = 50
    Illumination = 65
    Imperial_Age = 190
    Iron_Casting = 70
    Kataparuto = 60
    Keep = 75
    Leather_Archer_Armor = 55
    Ligth_Cavalry = 45
    Logistica = 50
    Long_Swordman = 45
    Loom = 25
    Mahouts = 50
    Man_At_Arms = 40
    Masonry = 50
    Murder_Holes = 60
    Onager = 75
    Padded_Archer_Armor = 40
    Paladin = 170
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
    Shinkichon = 60
    Shipwright = 60
    Siege_Engineers = 45
    Siege_Onager = 150
    Siege_Ram = 75
    Spies = 1
    Squires = 40
    Stone_Mining = 30
    Stone_Shaft_Mining = 75
    Supremacy = 60
    Theocracy = 75
    Thumb_Ring = 45
    Town_Patrol = 40
    Town_Watch = 25
    Tracking = 35
    Treadmill_Crane = 40
    Treason = 1
    Two_Handed_Swordsman = 75
    Two_Man_Saw = 100
    War_Galley = 50
    Wheelbarrow = 75
    Yeomen = 60
    Zealotry = 50
    OVERRIDES = {
        "Malay": {"Feudal_Age": 86.66666667, "Castle_Age": 106.6666667, "Imperial_Age": 191.3333333},
        "Goths": {"Loom": 0.01}
        # Note porto is done manually in getter
    }

    @classmethod
    def get(cls, name: str, civilisation: str):
        match (name, civilisation):
            case "Malay", _:
                if name in ["Feudal_Age", "Castle_Age", "Imperial_Age"]:
                    return cls["OVERRIDES"][name][civilisation]
                return cls[name]
            case "Goths", "Goths":
                return cls["OVERRIDES"][name][civilisation]
            case "Portuguese", _:
                if name in ["Feudal_Age", "Castle_Age", "Imperial_Age"]:
                    return cls[name]
                return cls[name]/1.25
            case _, _:
                return cls[name]
            
            




