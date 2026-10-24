import pytest
from datetime import date, timedelta

from readiness import narrate
from readiness.anonymize import Roster
from readiness.engine import assess_athlete, compute_baseline
from readiness.models import Reading
from readiness.narrate import (allowed_numbers, facts_for, narrate_note,
                               template_note, template_summary, verify_numbers)

END = date(2026, 7, 7)
BANNED = ["injur", "predict", "risk of", "diagnos", "tear", "strain"]


def _read(metric, values, aid="A1", name="D. Silva"):
    n = len(values)
    return [Reading(athlete_id=aid, name=name, pos="RHP",
                    day=END - timedelta(days=n - 1 - i), metric=metric, value=v)
            for i, v in enumerate(values)]


def _stable(n, b, w):
    return [b + (w if i % 2 else -w) for i in range(n)]


def _drop(metric, b, w, z):
    hist = _stable(27, b, w)
    base = compute_baseline(hist)
    return _read(metric, hist + [base.mean + z * base.sd])


@pytest.fixture
def flagged():
    rs = (_drop("rsi_mod", 0.55, 0.02, -1.3) + _drop("wellness_score", 20.0, 0.6, -1.3)
          + _read("hrv_lnrmssd", _stable(28, 4.0, 0.15)))
    a = assess_athlete(rs, END)
    return a, Roster([a])


def test_facts_pass_the_wall(flagged):
    a, roster = flagged
    roster.assert_clean(str(facts_for(a, roster)))


def test_no_key_uses_template(flagged, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    a, roster = flagged
    assert narrate_note(a, roster) == template_note(a, roster)


def test_invented_number_discarded(flagged, monkeypatch):
    a, roster = flagged
    monkeypatch.setattr(narrate, "_llm_note", lambda f, m: "Athlete 1 fell 88.8%.")
    assert narrate_note(a, roster) == template_note(a, roster)


def test_real_name_discarded(flagged, monkeypatch):
    a, roster = flagged
    monkeypatch.setattr(narrate, "_llm_note", lambda f, m: "D. Silva looks flat.")
    assert narrate_note(a, roster) == template_note(a, roster)


def test_template_names_drivers_and_no_injury_language(flagged):
    a, roster = flagged
    note = template_note(a, roster).lower()
    assert "neuromuscular" in note and "wellness" in note
    assert not any(b in note for b in BANNED)


def test_prompt_has_no_injury_language():
    assert not any(b in narrate.SYSTEM_PROMPT.lower() for b in BANNED)


def test_verify_numbers_and_allowed_variants():
    assert verify_numbers("z -9.9", {1.0}) == ["-9.9"]
    assert {-1.3, 1.3, -1.0, 1.0} <= allowed_numbers({"z": -1.3})


def test_template_summary():
    assert template_summary(0, 9, 9) == (
        "All 9 athletes tested within their normal range this morning.")
    assert template_summary(3, 6, 9) == (
        "9 athletes tested this morning. 3 flagged for a look, "
        "6 within normal range.")
