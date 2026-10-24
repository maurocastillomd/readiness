"""The privacy wall: the model never sees a real name."""

import pytest

from readiness.anonymize import Roster
from readiness.models import (AthleteAssessment, LoadContext, Status)


def make_assessment(athlete_id, name, pos="OF"):
    return AthleteAssessment(
        athlete_id=athlete_id, name=name, pos=pos, status=Status.CLEARED,
        domains=[], drivers=[], load=LoadContext(), reasons=[])


@pytest.fixture
def roster():
    return Roster([
        make_assessment("A01", "D. Silva", "RHP"),
        make_assessment("A02", "A. Rivera"),
    ])


class TestRoster:
    def test_aliases_are_anonymous(self, roster):
        assert roster.alias("A01") == "Athlete 1"
        assert roster.alias("A02") == "Athlete 2"

    def test_round_trip(self, roster):
        anonymized = "Athlete 1 is down 11%; Athlete 2 is trending down."
        restored = roster.deanonymize(anonymized)
        assert "D. Silva is down 11%" in restored
        assert "A. Rivera is trending down" in restored
        assert "Athlete" not in restored

    def test_double_digit_aliases_replace_correctly(self):
        many = Roster([make_assessment(f"A{i:02d}", f"Player {i}") for i in range(1, 13)])
        text = many.deanonymize("Athlete 12 and Athlete 1 both tested.")
        assert "Player 12 and Player 1 both tested." == text

    def test_refuses_to_send_a_real_name(self, roster):
        with pytest.raises(ValueError, match="Real name"):
            roster.assert_clean("Facts about D. Silva, RHP")

    def test_clean_text_passes(self, roster):
        roster.assert_clean("Facts about Athlete 1, RHP")
