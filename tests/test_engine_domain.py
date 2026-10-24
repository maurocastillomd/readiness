from datetime import date, timedelta

from readiness.engine import FRESHNESS_DAYS, assess_domain, compute_baseline
from readiness.models import METRICS, Domain, Status

END = date(2026, 7, 7)


def series(values, end=END, step=1):
    """Daily (day, value) points ending `end`, oldest first."""
    n = len(values)
    return [(end - timedelta(days=(n - 1 - i) * step), v) for i, v in enumerate(values)]


def stable(n, base, wig):
    return [base + (wig if i % 2 else -wig) for i in range(n)]


def test_stale_domain_is_not_fresh_and_never_flags():
    spec = METRICS[Domain.NEUROMUSCULAR]
    pts = series(stable(20, 0.55, 0.02))
    pts = [(d - timedelta(days=10), v) for d, v in pts]  # newest is 10d old
    d = assess_domain(spec, pts, END)
    assert d.fresh is False and d.status is Status.CLEARED and d.decline_z is None


def test_fresh_but_no_baseline_is_baseline_building():
    spec = METRICS[Domain.NEUROMUSCULAR]
    d = assess_domain(spec, series(stable(6, 0.55, 0.02)), END)
    assert d.fresh is True and d.base is None and d.status is Status.CLEARED


def test_drop_flags_review():
    spec = METRICS[Domain.NEUROMUSCULAR]
    hist = stable(27, 0.55, 0.02)
    base = compute_baseline(hist)
    today = base.mean + (-2.4) * base.sd
    d = assess_domain(spec, series(hist + [today]), END)
    assert d.status is Status.REVIEW and d.decline_z <= -2.0


def test_moderate_drop_flags_monitor():
    spec = METRICS[Domain.NEUROMUSCULAR]
    hist = stable(27, 0.55, 0.02)
    base = compute_baseline(hist)
    today = base.mean + (-1.5) * base.sd
    d = assess_domain(spec, series(hist + [today]), END)
    assert d.status is Status.MONITOR


def test_hrv_assesses_the_rolling_mean_not_the_raw_day():
    spec = METRICS[Domain.AUTONOMIC]  # rolling_days=7
    hist = stable(30, 4.0, 0.15)
    raw_spike = hist[-1] - 1.2  # one very low single night (~2.65)
    d = assess_domain(spec, series(hist[:-1] + [raw_spike]), END)
    # the domain reads the 7-day rolling mean (~3.8), not the raw 2.65 night
    assert d.today > 3.0
    assert abs(d.today - 4.0) < 0.5


def test_three_declines_past_swc_flag_monitor():
    spec = METRICS[Domain.PERCEPTUAL]
    hist = stable(24, 20.0, 0.6) + [20.2, 20.05, 19.9, 19.75]
    d = assess_domain(spec, series(hist), END)
    assert d.consecutive_declines >= 3 and d.status is Status.MONITOR


def test_sustained_hrv_decline_flags_through_rolling_mean():
    spec = METRICS[Domain.AUTONOMIC]  # rolling_days=7
    hist = stable(21, 4.0, 0.15) + [3.9, 3.8, 3.7, 3.6, 3.5, 3.4, 3.3]
    d = assess_domain(spec, series(hist), END)
    assert d.status is not Status.CLEARED  # a real week-long drop does flag


def test_zero_baseline_mean_gives_no_pct_instead_of_crashing():
    # a baseline whose mean is exactly 0 would divide-by-zero on the pct.
    # Real response metrics are strictly positive so this can't happen, but the
    # math layer must degrade to pct=None, never raise.
    spec = METRICS[Domain.PERCEPTUAL]  # higher_is_worse False -> goodness = value
    hist = [1.0, -1.0] * 14  # 28 prior values, mean 0, sd > 0
    d = assess_domain(spec, series(hist + [0.0]), END)
    assert d.pct is None
    assert d.decline_z == 0.0
