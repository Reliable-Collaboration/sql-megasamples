"""The native suite's selection check compares databases, as the registry keys them (Sol round 12, P2-1;
Opus round 12, 1). An `append: true` dataset shares its base's database and registry row, so a correct
configuration naming `dvdstore` and `dvdstore_reviews` meets a registry naming `dvdstore` once."""

import pytest

from tests.test_strict_read_native import selection_matches

CASES = [
    # (registry names, configured datasets, matches)
    (["dvdstore"], ["dvdstore", "dvdstore_reviews"], True),          # a base with its append dataset
    (["nyc_taxi"], ["nyc_taxi", "nyc_taxi_yellow"], True),
    (["dvdstore"], ["dvdstore"], True),                              # a base without it
    (["chinook", "dvdstore"], ["dvdstore", "dvdstore_reviews", "chinook"], True),
    (["dvdstore"], ["dvdstore", "chinook"], False),                  # a base the image lacks
    (["chinook", "dvdstore"], ["chinook"], False),                   # a base the configuration lacks
]


@pytest.mark.parametrize("names, datasets, matches", CASES)
def test_selection_is_compared_by_database(names, datasets, matches):
    assert selection_matches(names, datasets) is matches
