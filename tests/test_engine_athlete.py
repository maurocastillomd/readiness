from datetime import date, timedelta

from readiness.engine import assess_athlete, assess_squad, compute_baseline
from readiness.models import (HSR, METRICS, SRPE, TOTAL, Domain,
                              ReadinessDriver, Reading, Status)

END = date(2026, 7, 7)


def _read(metric, values, aid="A1", name="D. Silva", pos="RHP", source="s"):
    n = len(values)
    return [Reading(athlete_id=aid, name=name, pos=pos,
                    day=END - timedelta(days=n - 1 - i), metric=metric,
                    value=v, source=source) for i, v in enumerate(values)]


def _stable(n, base, wig):
    return [base + (wig if i % 2 else -wig) for i in range(n)]


def _drop(metric, z):
    bases = {"rsi_mod": 0.55, "wellness_score": 20.0, "hrv_lnrmssd": 4.0}
    wigs = {"rsi_mod": 0.02, "wellness_score": 0.6, "hrv_lnrmssd": 0.15}
    hist = _stable(27, bases[metric], wigs[metric])
    base = compute_baseline(hist)
    return _read(metric, hist + [base.mean + z * base.sd])


def _all_stable():
    return (_read("rsi_mod", _stable(28, 0.55, 0.02))
            + _read("wellness_score", _stable(28, 20.0, 0.6))
            + _read("hrv_lnrmssd", _stable(28, 4.0, 0.15)))


def test_two_response_domains_down_converge_to_review():
    rs = _drop("rsi_mod", -1.3) + _drop("wellness_score", -1.3) \
        + _read("hrv_lnrmssd", _stable(28, 4.0, 0.15))
    a = assess_athlete(rs, END)
    assert a.status is Status.REVIEW
    assert set(a.drivers) == {ReadinessDriver.NEUROMUSCULAR, ReadinessDriver.PERCEPTUAL}


def test_single_domain_down_is_monitor():
    # perceptual is a rolling_days=1 domain: a single-day drop translates directly
    rs = _drop("wellness_score", -1.4) + _read("rsi_mod", _stable(28, 0.55, 0.02)) \
        + _read("hrv_lnrmssd", _stable(28, 4.0, 0.15))
    a = assess_athlete(rs, END)
    assert a.status is Status.MONITOR
    assert a.drivers == [ReadinessDriver.PERCEPTUAL]


def test_all_stable_is_cleared():
    a = assess_athlete(_all_stable(), END)
    assert a.status is Status.CLEARED and a.drivers == []


def test_load_spike_and_high_acwr_never_flag():
    # 21 easy days, a hard last week, and a today spike vs the athlete's baseline
    rs = _all_stable() + _read(SRPE, [400.0] * 21 + [900.0] * 6 + [1500.0])
    a = assess_athlete(rs, END)
    assert a.load.acwr > 1.3 and a.load.spike is True
    assert a.status is Status.CLEARED
    joined = " ".join(a.reasons).lower()
    assert "acwr" not in joined and "load" not in joined.replace("workload", "")


def test_no_fresh_response_domain_returns_none():
    old = [r.model_copy(update={"day": r.day - timedelta(days=30)}) for r in _all_stable()]
    assert assess_athlete(old, END) is None


def test_squad_sorted_worst_first():
    silva = _drop("rsi_mod", -1.3) + _drop("wellness_score", -1.3) \
        + _read("hrv_lnrmssd", _stable(28, 4.0, 0.15))
    calm = _read("rsi_mod", _stable(28, 0.55, 0.02), aid="A2", name="J. Okafor") \
        + _read("wellness_score", _stable(28, 20.0, 0.6), aid="A2", name="J. Okafor") \
        + _read("hrv_lnrmssd", _stable(28, 4.0, 0.15), aid="A2", name="J. Okafor")
    squad = assess_squad(silva + calm, END)
    assert squad[0].name == "D. Silva" and squad[0].status is Status.REVIEW
