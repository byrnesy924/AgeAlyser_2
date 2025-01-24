import os
import pandas as pd
# import pytest

from agealyser.main import AgeGame


def regression_testing():
    results = []
    # get the suite of test games
    test_files = [game for game in os.listdir(r"tests\\Test_Games") if ".aoe2record" in game]  # TODO fix pathing when automating
    test_games = [AgeGame(r"tests\\Test_Games\\" + file) for file in test_files]

    # run the package on these
    results = pd.concat([game.advanced_parser(include_map_analyses=True) for game in test_games], axis=1)

    for player in test_games[0].players:
        player.inputs_df.to_csv(fr"tests\\Test_Games\\Game_Data_Structures\\Player{player.number}_inputs.csv")
        player.actions_df.to_csv(fr"tests\\Test_Games\\Game_Data_Structures\\Player{player.number}_actions.csv")
        temp = pd.Series(player.technologies)
        temp.to_csv(fr"tests\\Test_Games\\Game_Data_Structures\\Player{player.number}_technologies.csv")
        player.buildings.to_csv(fr"tests\\Test_Games\\Game_Data_Structures\\Player{player.number}_buildings.csv")
        player.queue_units.to_csv(fr"tests\\Test_Games\\Game_Data_Structures\\Player{player.number}_queue.csv")
        player.unqueue_units.to_csv(fr"tests\\Test_Games\\Game_Data_Structures\\Player{player.number}_unqueue.csv")
        player.military_units.to_csv(fr"tests\\Test_Games\\Game_Data_Structures\\Player{player.number}_units.csv")

    # load the correct map results
    correct_results = pd.read_csv(r"tests\\Test_Games\\regression_testing_correct_results.csv")

    results.to_csv(r"tests\\Test_Games\\regression_testing_test_results.csv")

    assert pd.testing.assert_frame_equal(results, correct_results)


if __name__ == "__main__":
    regression_testing()
