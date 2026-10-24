from readiness.models import (METRICS, Domain, ReadinessDriver, Reading,
                              Status, goodness_specs)


def test_response_domains_have_specs():
    assert set(METRICS) == {Domain.PERCEPTUAL, Domain.AUTONOMIC,
                            Domain.NEUROMUSCULAR}


def test_hrv_uses_seven_day_rolling():
    assert METRICS[Domain.AUTONOMIC].rolling_days == 7
    assert METRICS[Domain.PERCEPTUAL].rolling_days == 1
    assert METRICS[Domain.NEUROMUSCULAR].rolling_days == 1


def test_response_metrics_are_higher_is_better():
    assert all(not s.higher_is_worse for s in METRICS.values())


def test_driver_names_match_domains():
    assert {d.value for d in ReadinessDriver} == {d.value for d in Domain}


def test_reading_roundtrips():
    r = Reading(athlete_id="A1", name="D. Silva", pos="RHP",
                day="2026-07-07", metric="rsi_mod", value=0.51, source="forceplate")
    assert r.metric == "rsi_mod" and r.value == 0.51


def test_goodness_specs_helper_lists_metric_columns():
    cols = goodness_specs()
    assert cols[Domain.NEUROMUSCULAR] == "rsi_mod"
