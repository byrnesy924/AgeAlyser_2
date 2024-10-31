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

    # load the correct map results
    # correct_results = pd.read_csv("regression_testing_correct_results.csv")

    results.to_csv(r"tests\\Test_Games\\regression_testing_correct_results.csv")

    assert pd.testing.assert_frame_equal(results, correct_results)

if __name__=="__main__":
    regression_testing()
