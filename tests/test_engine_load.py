from datetime import date, timedelta

from readiness.engine import LOAD_SPIKE_Z, load_context
from readiness.models import HSR, SRPE, TOTAL, Reading

END = date(2026, 7, 7)


def readings(metric, values, source="gps"):
    n = len(values)
    return [Reading(athlete_id="A1", name="X", pos="OF",
                    day=END - timedelta(days=n - 1 - i), metric=metric,
                    value=v, source=source) for i, v in enumerate(values)]


def test_acwr_computed_as_context():
    rs = readings(SRPE, [400.0] * 21 + [900.0] * 7)  # heavy last week
    lc = load_context(rs, END)
    assert lc.acwr is not None and lc.acwr > 1.3


def test_srpe_spike_flagged():
    base = [400.0 + (20 if i % 2 else -20) for i in range(27)]
    rs = readings(SRPE, base + [900.0])
    lc = load_context(rs, END)
    assert lc.spike is True and lc.srpe_z >= LOAD_SPIKE_Z


def test_hsr_and_total_surfaced():
    rs = readings(HSR, [600.0] * 10) + readings(TOTAL, [5000.0] * 10)
    lc = load_context(rs, END)
    assert lc.hsr_today == 600.0 and lc.total_today == 5000.0


def test_no_load_data_is_all_none():
    lc = load_context([], END)
    assert lc.acwr is None and lc.spike is False and lc.srpe_today is None
