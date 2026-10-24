from datetime import date, timedelta

from readiness.models import Reading, ReadinessDriver, Status
from readiness.weekly import WATCH_DELTA_Z, rollup_athlete, rollup_squad

END = date(2026, 7, 7)


def _read(metric, values, aid="A1", name="D. Silva", pos="RHP", end=END):
    n = len(values)
    return [Reading(athlete_id=aid, name=name, pos=pos,
                    day=end - timedelta(days=n - 1 - i), metric=metric, value=v)
            for i, v in enumerate(values)]


def _stable(n, b, w):
    return [b + (w if i % 2 else -w) for i in range(n)]


def _drop_today(metric, b, w, z, aid="A1", name="D. Silva"):
    from readiness.engine import compute_baseline
    hist = _stable(41, b, w)
    base = compute_baseline(hist[-28:])
    return _read(metric, hist + [base.mean + z * base.sd], aid=aid, name=name)


def _stable_athlete(aid, name):
    return (_read("rsi_mod", _stable(42, 0.55, 0.02), aid=aid, name=name)
            + _read("wellness_score", _stable(42, 20.0, 0.6), aid=aid, name=name)
            + _read("hrv_lnrmssd", _stable(42, 4.0, 0.15), aid=aid, name=name))


def test_stable_athlete_is_cleared_week():
    w = rollup_athlete(_stable_athlete("A1", "D. Silva"), "A1", END)
    assert w is not None
    assert w.week_status is Status.CLEARED
    assert w.days_tested >= 5


def test_converging_drop_is_review_week_with_drivers():
    rs = (_drop_today("rsi_mod", 0.55, 0.02, -1.5)
          + _drop_today("wellness_score", 20.0, 0.6, -1.5)
          + _read("hrv_lnrmssd", _stable(42, 4.0, 0.15)))
    w = rollup_athlete(rs, "A1", END)
    assert w.week_status is Status.REVIEW
    assert set(w.drivers) == {ReadinessDriver.NEUROMUSCULAR, ReadinessDriver.PERCEPTUAL}
    assert w.days_flagged >= 1
    assert w.daily_z and all(-4 <= p.z <= 2 for p in w.daily_z)


def test_no_data_returns_none():
    assert rollup_athlete([], "A1", END) is None


def test_watch_threshold_boundary():
    assert WATCH_DELTA_Z == -0.4


def test_squad_sorted_review_first():
    rs = (_drop_today("rsi_mod", 0.55, 0.02, -1.5)
          + _drop_today("wellness_score", 20.0, 0.6, -1.5)
          + _read("hrv_lnrmssd", _stable(42, 4.0, 0.15))
          + _stable_athlete("A2", "J. Okafor"))
    squad = rollup_squad(rs, END)
    assert squad[0].name == "D. Silva" and squad[0].week_status is Status.REVIEW
    assert squad[-1].week_status is Status.CLEARED
