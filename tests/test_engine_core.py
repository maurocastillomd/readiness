from datetime import date

from readiness.engine import (MIN_BASELINE_SESSIONS, compute_baseline,
                              count_consecutive_declines, goodness, rolling,
                              z_score)


def test_goodness_inverts_only_higher_is_worse():
    assert goodness(0.51, higher_is_worse=False) == 0.51
    assert goodness(250.0, higher_is_worse=True) == -250.0


def test_baseline_needs_min_sessions_and_nonzero_sd():
    assert compute_baseline([1.0] * (MIN_BASELINE_SESSIONS - 1)) is None
    assert compute_baseline([1.0] * 12) is None  # zero SD
    base = compute_baseline([1.0 + (0.1 if i % 2 else -0.1) for i in range(12)])
    assert base is not None and base.swc == 0.2 * base.sd


def test_z_score():
    base = compute_baseline([5.0 + (1.0 if i % 2 else -1.0) for i in range(12)])
    assert abs(z_score(base.mean, base)) < 1e-9


def test_rolling_seven_day_mean_smooths():
    pts = [(date(2026, 7, 1 + i), float(i)) for i in range(7)]  # 0..6
    rolled = rolling(pts, 7)
    assert rolled[-1][1] == sum(range(7)) / 7  # last = mean of all 7
    assert rolling(pts, 1) == pts  # identity for 1-day


def test_count_consecutive_declines():
    assert count_consecutive_declines([5, 6, 5, 4, 3]) == 3
    assert count_consecutive_declines([5, 4, 5, 6]) == 0
    assert count_consecutive_declines([5]) == 0
