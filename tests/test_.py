import os
import pandas as pd
import pytest

from agealyser.main import AgeGame, GamePlayer, AgeMap


def test_regression_testing():
    results = []
    # get the suite of test games
    test_files = [game for game in os.listdir(r"tests\\Test_Games") if ".aoe2record" in game]  # TODO fix pathing when automating
    test_games = [AgeGame(r"tests\\Test_Games\\" + file) for file in test_files]

    # run the package on these
    results = pd.concat([game.advanced_parser(include_map_analyses=True) for game in test_games], axis=1).T
    correct_results = pd.read_parquet(r"tests\\Test_Games\\regression_testing_test_results.parquet")
    results = results.astype(correct_results.dtypes.to_dict())

    assert pd.testing.assert_frame_equal(results, correct_results) is None

    # save data
    # results.to_parquet(r"tests\\Test_Games\\regression_testing_test_results.parquet")
