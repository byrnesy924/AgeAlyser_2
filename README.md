# AgeAlyser_2
Experiments in Analyzing AOE2 Recorded Games

### Utilities
- [AOE Pulse - very cool Opening strategy analytics work that is similar to what I'm doing](https://www.aoepulse.com/home)
- [The Original Repository for AOE Opening Analysis](https://github.com/dj0wns/AoE_Rec_Opening_Analysis/tree/main)
- [Relic/MS Documentation](https://wiki.librematch.org/librematch/data_sources/start)
- [Download Recs Manually @ aoe2recs.com](https://aoe2recs.com/)
- [AOE 2 rules for content](https://www.xbox.com/en-GB/developers/rules)
- https://api-dev.ageofempires.com/
- https://wiki.librematch.org/librematch/design/backend/authentication/start


### Idea
- Need a way to download top rec games
- Use parser to extract features of top games
    - resource collection
    - Starting question: 1TC vs 2 TC vs 3 TC play
    - Development of each civ in terms of resources
- perform an interesting analysis of strategies, maybe using ML

Iterate back and forth on points 2 and 3

### Initially analysis
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


### Bulk downloading of games
AOE insights has links for a particular game - it hits the aoe ms website api to download it
I will need to work out how to authenticate against that
https://www.aoe2insights.com/match/301103008/#savegames

e.g. this is a Hera and Yo game
https://aoe.ms/replay/?gameId=301103008&profileId=197964


### Version of Parser to use - AOE Insights's own fork of MGZ
```
git clone https://github.com/aoeinsights/aoc-mgz
```
then 
```
python  setup.py install
```
Note this might have to be done outside of VS code, as VS code wont release the lock on the .egg file, stopping installation


### mgz game structure
Items in the mgz game json once serialised

Key items: actions; inputs --> that is the list of things that the game runs on

dict_keys(['players', 'teams', 'gaia', 'map', 'file', 'restored', 'restored_at', 'speed', 'speed_id', 'cheats', 'lock_teams', 'population', 'chat', 'guid', 'lobby', 'rated', 'dataset', 'type', 'type_id', 'map_reveal', 'map_reveal_id', 'difficulty_id', 'starting_age', 'starting_age_id', 'team_together', 'lock_speed', 'all_technologies', 'multiqueue', 'duration', 'diplomacy_type', 'completed', 'dataset_id', 'version', 'game_version', 'save_version', 'log_version', 'build_version', 'timestamp', 'spec_delay', 'allow_specs', 'hidden_civs', 'private', 'hash', 'actions', 'inputs'])


### AOE 2 objects
Town Centre - class id = 80, object id = 109