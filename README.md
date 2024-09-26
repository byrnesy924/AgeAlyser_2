# AgeAlyser_2
This package is an attempt to mine out key strategic choices and statistics from an age of empires 2 game for analysis. Built ontop of the [mgz parser](https://github.com/happyleavesaoc/aoc-mgz/tree/master/mgz), the package takes in a .AOE2RECORD and produces a pandas Series that documents:
- The military strategy choices of both players throughout the game, including unit choice, mass, and timings
- The economic choices of each player through the game
- the players' maps
and so on.

The goal is to create an open source project that enables large scale analytics of the game. Capture Age provides incredible analysis tools for watching replays, however there is a gap in terms of being able to extract statistical data from games en masse for analytics purposes. The task is difficult, given the structure of an mgz file, see below.

Aside from this package, to my knowledge, the best progress so far has been made by: 
- [dj0wns](https://github.com/dj0wns/AoE_Rec_Opening_Analysis/tree/main)
- [aoe insights](https://www.aoe2insights.com/)
- [AOE Pulse made by dj0wns](https://www.aoepulse.com/home)

I know there is a large section of the community that would love to run large scale analytics beyond civ matchups. The goal of this package is to bridge this gap.

## Installation
TODO - yet to publish

## Usage
### Modeling Structure and package API
**AgeMap** 
- Models the map itself and the natural objects within
- key are hills, resources, especially trees
- attempts to extract relevant features from this, e.g. resources on front/hills, distance to opponent

**GamePlayer**
- Models the decisions/strategies/tactics made by individuals
- How strategies and choices are mined
- Two key lines of analysis - Military and Economic strategy/tactics

**AgeGame**
- Central object, contains key data for the game, also houses behaviour


## Appendices
### MGZ Parser version to use
If the original aoc-mgz is behind the current game update and therefore not functional, use aoeinsights fork:
```
git clone https://github.com/aoeinsights/aoc-mgz
```
then 
```
python  setup.py install
```

### AOE Devleopment Utilities
- [Siege Engineers GitHub](https://github.com/SiegeEngineers)
- [Relic/MS Documentation](https://wiki.librematch.org/librematch/data_sources/start)
- [Download Recs Manually @ aoe2recs.com](https://aoe2recs.com/)
- [AOE 2 rules for content](https://www.xbox.com/en-GB/developers/rules)
- https://api-dev.ageofempires.com/
- https://wiki.librematch.org/librematch/design/backend/authentication/start

### mgz game structure
The .AOE2RECORD file type (in essence) only contains the starting state of the game and the series of actions made by both players. This is extremely limiting when it comes to mining out statistics for a game. 

For example, my original idea was to map growth in total resources as a proxy for development and analyse the decisions that contributed to that. However, resource amounts are not stored in the game files. In order to know how many resources have been collected at a point in time, you would need to basically simulate the whole game until that point in time, or create a mathematical model for villager gathering. Modelling villager gather rates is extremely hard, what with their pathing, bumping, getting stuck, and the changing efficiency as the shape of a resource changes, etc. causing fluctuations in gather rates. In summary, modelling resource collected is very difficult.

This package has turned into an exploration into what the mgz package can produce, and trying to gleam from that as much as possible.

### Initial planned pieces of analysis
Comparison of detailed opening strategy
Features:
- civilisations
- distance from opponent
- if possible, tree coverage between players
    - location of all trees, number of trees in hallway between players
    - front trees on either side
- feudal times
- winner
- castle age time
- walls
    - timing? amount?
- Opening strategy
    - scouts FC
    - scouts archers
    - scouts skirms
    - all in scouts
    - all in feudal
    - pre mill drush FC
    - pre mill drush flush
    - drush FC
    - drush flush
    - maa archers
    - maa towers
    - straight towers
    - archers into FC
    - archers into skirms
    - skirms and spears
    - all in feudal
    - FC archers
    - FC knights
    - FC UU
    - boom
    - timing of 1st TC
    - timing of second TC
    - TC idle time