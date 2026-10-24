import pytest
from datetime import date

from readiness import narrate
from readiness.anonymize import Roster
from readiness.models import (AthleteAssessment, AthleteWeek, LoadContext,
                              ReadinessDriver, Status)
from readiness.narrate import (allowed_numbers, narrate_weekly_summary,
                               template_weekly_summary, weekly_facts)

WS, WE = date(2026, 7, 1), date(2026, 7, 7)
BANNED = ["injur", "predict", "risk of", "diagnos", "tear", "strain"]


def _assess(aid, name, status):
    return AthleteAssessment(athlete_id=aid, name=name, pos="RHP", status=status,
                             domains=[], drivers=[], load=LoadContext(), reasons=[])


def _week(aid, name, status, watch=False, dz=-0.1, drivers=None, days_flagged=1):
    return AthleteWeek(
        athlete_id=aid, name=name, pos="RHP", week_status=status, watch=watch,
        days_tested=6, days_flagged=days_flagged, week_mean_z=-1.4,
        prior_mean_z=-0.3, delta_z=dz, drivers=drivers or [], acwr_end=1.5,
        load_spike=False, daily_z=[], worst_day=_assess(aid, name, status))


@pytest.fixture
def rows():
    return [
        _week("A1", "D. Silva", Status.REVIEW,
              drivers=[ReadinessDriver.NEUROMUSCULAR, ReadinessDriver.PERCEPTUAL]),
        _week("A2", "A. Rivera", Status.MONITOR, drivers=[ReadinessDriver.AUTONOMIC]),
        _week("A3", "T. Nakamura", Status.CLEARED, watch=True, dz=-0.6),
        _week("A4", "J. Okafor", Status.CLEARED, dz=-0.1),
    ]


@pytest.fixture
def roster(rows):
    return Roster([w.worst_day for w in rows])


def test_facts_pass_the_wall(rows, roster):
    roster.assert_clean(str(weekly_facts(rows, roster, WS, WE)))


def test_no_key_uses_template(rows, roster, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    assert (narrate_weekly_summary(rows, roster, WS, WE)
            == template_weekly_summary(rows, roster, WS, WE))


def test_invented_number_discarded(rows, roster, monkeypatch):
    monkeypatch.setattr(narrate, "_llm_note",
                        lambda f, m, system=None: "The week had 999 flagged.")
    assert (narrate_weekly_summary(rows, roster, WS, WE)
            == template_weekly_summary(rows, roster, WS, WE))


def test_real_name_discarded(rows, roster, monkeypatch):
    monkeypatch.setattr(narrate, "_llm_note",
                        lambda f, m, system=None: "D. Silva led the flags.")
    assert (narrate_weekly_summary(rows, roster, WS, WE)
            == template_weekly_summary(rows, roster, WS, WE))


def test_clean_output_accepted(rows, roster, monkeypatch):
    text = "Athlete 1 and Athlete 2 need eyes; Athlete 3 is trending down."
    monkeypatch.setattr(narrate, "_llm_note", lambda f, m, system=None: text)
    assert narrate_weekly_summary(rows, roster, WS, WE) == text


def test_template_is_alias_only_and_clean(rows, roster):
    s = template_weekly_summary(rows, roster, WS, WE)
    assert "Athlete 1" in s
    assert not any(b in s.lower() for b in BANNED)
    roster.assert_clean(s)


def test_weekly_prompt_has_no_injury_language():
    assert not any(b in narrate.WEEKLY_SYSTEM_PROMPT.lower() for b in BANNED)
