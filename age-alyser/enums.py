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

    @classmethod
    def get(cls, name: str, civilisation: str, age: str = None) -> int:
        """Getter function to include civilisation overrides, e.g. Spanish 30% faster builders"""
        match (name, civilisation, age):
            case ("Town_Centre", "Cumans", "Feudal Age"):
                # Cuman second feudal TC scenario
                return cls["OVERRIDES"][civilisation][name]
            case ("Town_Centre", "Sicilians", "Feudal Age"):
                return cls["OVERRIDES"][civilisation][name]
            case ("Castle", "Sicilians", "Feudal Age"):
                return cls["OVERRIDES"][civilisation][name]
            case ("Donjon", "Sicilians", "Feudal Age"):
                return cls["OVERRIDES"][civilisation][name]
            case ("Wonder", "Spanish", _):
                return
            case (_, "Spanish", _):
                return cls[name]/1.20
            case (_, "Romans", _):
                return cls[name]/1.05
            case (_, _, _):
                return cls[name]


