# The Age-2-Alyser
This python package mines out key strategic choices and statistics from a recorded Age of Empires 2 game. The intention is to enable for further data analysis, including at scale. The package takes in a .AOE2RECORD file as input and produces a Pandas Series with statistical data about the match. This data includes:
- The military strategy choices of both players throughout the game, including unit and strategy choices, production numbers, timings of openings, and so on.
- The economic choices of each player through the game.
- An analysis of the players' maps.
- And some other miscellaneous data, such as elo difference and civilisations.
The package is built on top of the [mgz parser](https://github.com/happyleavesaoc/aoc-mgz/tree/master/mgz) to parse in recorded games - see also [this fork](https://github.com/aoeinsights/aoc-mgz) maintained by aoe insights. 

The goal is to create an open source project that enables large scale analytics of the game. Capture Age provides incredible analysis tools for watching replays, however there is a gap in terms of being able to extract statistical data from games en masse for analytics purposes. The task is difficult, given the structure of an mgz file (see appendices below for a more detailed technical explanation).

Aside from this package, some other great projects I have come across which perform something similar are: 
- [Rec Opening Analysis by dj0wns](https://github.com/dj0wns/AoE_Rec_Opening_Analysis/tree/main)
- [AOE insights](https://www.aoe2insights.com/)
- [AOE Pulse made by dj0wns](https://www.aoepulse.com/home)

The goal of this package is to flesh out the statistical data we can mine from replays, and deliver it en masse to anyone who can bash up a python script. Feel free to contribute in any way (including a code review or building out tests or documentation).

## Installation and Version
```
pip install age-alyser
```
The current version is *0.0.5*. The most recent updates contains fixes for:
- (0.0.4) Now missing technologies/units/buildings that are missing will raise a warning rather than crashing the program. The warning asks the user to raise an issue on the GitHub to be fixed.
- Updated a number of technology/unit/buildings Enums for some of the missing values, mostly recent updates to civs unique techs.
- Instances where the mgz parser cannot find a players ELO in the record file - this no longer crashes the program but will return 0 as the difference in ELO.
- Fixed a bug where if a player never built palisade walls a malformed data frame would throw a key error. Now exits and returns correct values.
- Handled an issue where the MGZ parser couldn't find player locations. In this case, the analysis of the map cannot be performed. There are also consequences for modelling of the starting Town Centre. Please raise an issue if you find any errors in age up times as it may be related to this.


## Usage and Documentation
Currently only the advanced parser is implemented - in the future I intend to flesh out the API with some other options.
```
import pandas as pd
from agealyser import AgeGame

g = AgeGame("file/path/to/game.aoe2record")
stats: pd.Series = g.advanced_parser()  # optional - include_map_analysis = False
```
#### Limitations
Given that:
1. This package is dependant on the [mgz package](https://github.com/happyleavesaoc/aoc-mgz) (and I'm not planning on maintaining a fork or anything)
2. Updates to the game can often break mgz's parsing of a .aoe2record file
3. This package is an WIP/unfinished alpha release

There may be a number of inaccuracies, errors, and bugs.

I would recommend wrapping the the above code in a try-except block. In the future I also intend to improve the error handling so the whole package fails more gracefully.

#### Modeling Structure and package API
**AgeMap** 
- Models the map itself and the resources/objects within
- Identifies hills, resources, treelines, etc.
- Attempts to extract relevant features from this, e.g. resources on front/hills, distance to opponent and so on.

**GamePlayer**
- Models the decisions/strategies/tactics made by individuals
- Identifies strategies, choices, etc.
- Two key lines of analysis - Military and Economic

**AgeGame**
- Central object, contains key data for the game (for example the GamePlayer and AgeMap objects), also houses mgz parsing behaviour.


## Appendices
#### AOE Devleopment Utilities
- [Siege Engineers GitHub](https://github.com/SiegeEngineers)
- [Relic/MS Documentation](https://wiki.librematch.org/librematch/data_sources/start)
- [Download Recs Manually @ aoe2recs.com](https://aoe2recs.com/)
- [AOE 2 rules for content](https://www.xbox.com/en-GB/developers/rules)
- https://api-dev.ageofempires.com/
- https://wiki.librematch.org/librematch/design/backend/authentication/start

#### MGZ file/recorded game structure
The .AOE2RECORD file type only contains the starting state of the game and the series of actions made by both players. This is extremely limiting when it comes to mining out statistics for a game. 

For example, my original idea was to map growth in total resources as a proxy for player development and analyse the decisions that contributed to that. However, resources collected are not stored in the game files, and any modelling of villagers collecting resources would be difficult and woefully inaccurate (Modelling villager gather rates is extremely hard, what with their pathing, bumping, getting stuck, and the changing efficiency as the shape of a resource changes, etc. causing fluctuations in gather rates). 
In general, what can be mined out of the .aoe2record file is limited.

As such, things like up times might be imprecise, as the game only records when a player clicks the research button, and I have had to completely model the production of each Town Centre to identify when research would be complete, based on queued villagers/techs etc. Currently, the mgz package does not seem to handle unqueing units particularly well, which trickles down into further inaccuracies in this package.

This package has turned into an exploration into what the mgz package can produce, and trying to gleam from that as much as possible.

#### MGZ Parser version to use
If the original aoc-mgz is behind the current game update and therefore not functional, check aoeinsights version and use that fork:
```
git clone https://github.com/aoeinsights/aoc-mgz
```
then 
```
python setup.py install
```