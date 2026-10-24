"""The deterministic core. All math lives here. No AI anywhere in this file.

Rules (plain English, because a coach has to trust them):

  Baseline     Each response metric is measured against the athlete's OWN
               28-day rolling baseline (min 10 readings). HRV is baselined
               on its 7-day rolling mean (Williams 2017). Direction is
               sign-normalized to a "goodness" scale so a decline is always
               a negative z and one threshold set serves every domain.

  Per domain   REVIEW z <= -2.0; MONITOR z <= -1.2 or 3+ consecutive
               declines past the smallest worthwhile change (0.2 x SD);
               else CLEARED.

  Convergence  Athlete status escalates on agreement: REVIEW if any domain
               is REVIEW, or if >= 2 assessable domains sit at/under -1.2.
               Else MONITOR if any domain is MONITOR. Else CLEARED. This is
               the multivariate upgrade: flag on convergence, not one metric.

  Context      Internal load (sRPE), external load (GPS) and ACWR are
               computed as CONTEXT and attached to every athlete. They
               explain the "why". They never set availability status.
               ACWR is a flawed ratio (Impellizzeri 2020) and is context
               only, by design.

  Freshness    Streams arrive on different clocks. A domain is assessed
               from its most recent reading within FRESHNESS_DAYS; with no
               fresh reading it is "no current data" and never flags.

Nothing here predicts injury. It surfaces individual change in readiness.
"""

from __future__ import annotations

import statistics
from collections import defaultdict
from datetime import date, timedelta

from .models import (METRICS, SRPE, HSR, TOTAL, AthleteAssessment, Baseline,
                     Domain, DomainAssessment, LoadContext, MetricSpec,
                     ReadinessDriver, Reading, Status)

BASELINE_DAYS = 28
MIN_BASELINE_SESSIONS = 10
FRESHNESS_DAYS = 4
ACUTE_DAYS = 7
REVIEW_Z = -2.0
MONITOR_Z = -1.2
CONVERGENCE_Z = -1.2
MONITOR_DECLINE_SESSIONS = 3
TREND_SESSIONS = 14
SWC_FACTOR = 0.2
LOAD_SPIKE_Z = 2.0

SEVERITY = {Status.REVIEW: 0, Status.MONITOR: 1, Status.CLEARED: 2}


def goodness(value: float, higher_is_worse: bool) -> float:
    return -value if higher_is_worse else value


def compute_baseline(values: list[float]) -> Baseline | None:
    if len(values) < MIN_BASELINE_SESSIONS:
        return None
    mean = statistics.fmean(values)
    sd = statistics.stdev(values)
    if sd == 0:
        return None
    return Baseline(mean=mean, sd=sd, n=len(values), swc=SWC_FACTOR * sd)


def z_score(today: float, base: Baseline) -> float:
    return (today - base.mean) / base.sd


def rolling(points: list[tuple[date, float]], days: int) -> list[tuple[date, float]]:
    """Trailing calendar-window mean. days=1 is identity. points sorted by day."""
    if days <= 1:
        return list(points)
    out: list[tuple[date, float]] = []
    for i, (d, _) in enumerate(points):
        window = [v for (dd, v) in points[: i + 1] if d - timedelta(days=days - 1) <= dd <= d]
        out.append((d, statistics.fmean(window)))
    return out


def count_consecutive_declines(values: list[float]) -> int:
    run = 0
    for prev, cur in zip(reversed(values[:-1]), reversed(values[1:])):
        if cur < prev:
            run += 1
        else:
            break
    return run


def assess_domain(spec: MetricSpec, points: list[tuple[date, float]],
                  today: date) -> DomainAssessment:
    """Assess one response domain from its raw (day, value) series."""
    pts = sorted(points)
    rolled = rolling(pts, spec.rolling_days)
    fresh_pts = [p for p in rolled
                 if today - timedelta(days=FRESHNESS_DAYS) <= p[0] <= today]
    if not fresh_pts:
        return DomainAssessment(domain=spec.domain, status=Status.CLEARED,
                                fresh=False, today=None, base=None, pct=None,
                                decline_z=None)
    today_day, today_val = fresh_pts[-1]
    window_start = today_day - timedelta(days=BASELINE_DAYS)
    prior = [v for (d, v) in rolled if window_start <= d < today_day]
    g_prior = [goodness(v, spec.higher_is_worse) for v in prior]
    base = compute_baseline(g_prior)
    if base is None:
        return DomainAssessment(domain=spec.domain, status=Status.CLEARED,
                                fresh=True, today=round(today_val, 2), base=None,
                                pct=None, decline_z=None,
                                reasons=["baseline-building"])
    g_today = goodness(today_val, spec.higher_is_worse)
    decline_z = z_score(g_today, base)
    recent = (g_prior + [g_today])[-TREND_SESSIONS:]
    declines = count_consecutive_declines(recent)
    cumulative_drop = (recent[-1 - declines] - recent[-1]) if declines else 0.0

    reasons: list[str] = []
    if decline_z <= REVIEW_Z:
        status = Status.REVIEW
        reasons.append(f"{spec.label} z {decline_z:.1f} at or below review "
                       f"line ({REVIEW_Z:.1f})")
    elif decline_z <= MONITOR_Z:
        status = Status.MONITOR
        reasons.append(f"{spec.label} z {decline_z:.1f} at or below monitor "
                       f"line ({MONITOR_Z:.1f})")
    elif declines >= MONITOR_DECLINE_SESSIONS and cumulative_drop > base.swc:
        status = Status.MONITOR
        reasons.append(f"{spec.label}: {declines} consecutive declining "
                       f"readings past the smallest worthwhile change")
    else:
        status = Status.CLEARED

    raw_mean = -base.mean if spec.higher_is_worse else base.mean
    pct = (None if raw_mean == 0
           else round((today_val - raw_mean) / raw_mean * 100.0, 1))
    return DomainAssessment(domain=spec.domain, status=status, fresh=True,
                            today=round(today_val, 2), base=base,
                            pct=pct, decline_z=round(decline_z, 1),
                            consecutive_declines=declines, reasons=reasons)


def _metric_series(readings: list[Reading], metric: str,
                   today: date) -> list[tuple[date, float]]:
    by_day: dict[date, float] = {}
    for r in readings:
        if r.metric == metric and r.day <= today:
            by_day[r.day] = r.value  # last write per day wins
    return sorted(by_day.items())


def _latest(series: list[tuple[date, float]], today: date) -> float | None:
    fresh = [v for (d, v) in series
             if today - timedelta(days=FRESHNESS_DAYS) <= d <= today]
    return fresh[-1] if fresh else None


def load_context(readings: list[Reading], today: date) -> LoadContext:
    """Internal/external load + ACWR. CONTEXT only — never sets a status."""
    srpe = _metric_series(readings, SRPE, today)
    srpe_today = _latest(srpe, today)
    srpe_z = None
    spike = False
    if srpe_today is not None and len(srpe) > MIN_BASELINE_SESSIONS:
        prior = [v for (d, v) in srpe if d < today][-BASELINE_DAYS:]
        base = compute_baseline(prior)
        if base is not None:
            srpe_z = round(z_score(srpe_today, base), 1)
            spike = srpe_z >= LOAD_SPIKE_Z

    acwr = None
    if srpe:
        vals = dict(srpe)
        acute = [v for d, v in vals.items()
                 if today - timedelta(days=ACUTE_DAYS) < d <= today]
        chronic = [v for d, v in vals.items()
                   if today - timedelta(days=BASELINE_DAYS) < d <= today]
        if acute and chronic:
            cm = statistics.fmean(chronic)
            if cm:
                acwr = round(statistics.fmean(acute) / cm, 2)

    return LoadContext(
        srpe_today=srpe_today, srpe_z=srpe_z, spike=spike,
        hsr_today=_latest(_metric_series(readings, HSR, today), today),
        total_today=_latest(_metric_series(readings, TOTAL, today), today),
        acwr=acwr)


def assess_athlete(readings: list[Reading],
                   today: date) -> AthleteAssessment | None:
    """Assess one athlete across response domains; status by convergence.
    None if no response domain has a fresh, baselined reading."""
    ident: tuple[str, str, str] | None = None
    for r in readings:
        if r.day <= today:
            ident = (r.athlete_id, r.name, r.pos)
            break
    if ident is None:
        return None

    domains: list[DomainAssessment] = []
    for spec in METRICS.values():
        series = _metric_series(readings, spec.column, today)
        domains.append(assess_domain(spec, series, today))

    assessable = [d for d in domains if d.assessable]
    if not assessable:
        return None

    any_review = any(d.status is Status.REVIEW for d in domains)
    converging = [d for d in assessable if d.decline_z <= CONVERGENCE_Z]
    if any_review or len(converging) >= 2:
        status = Status.REVIEW
    elif any(d.status is Status.MONITOR for d in domains):
        status = Status.MONITOR
    else:
        status = Status.CLEARED

    flagged = sorted((d for d in domains if d.status is not Status.CLEARED),
                     key=lambda d: (SEVERITY[d.status], d.decline_z))
    drivers = [ReadinessDriver(d.domain.value) for d in flagged]
    reasons = [r for d in flagged for r in d.reasons]

    load = load_context(readings, today)
    if load.spike and status is not Status.CLEARED:
        reasons.append("during an acute training-load spike (context)")

    aid, name, pos = ident
    return AthleteAssessment(athlete_id=aid, name=name, pos=pos, status=status,
                             domains=domains, drivers=drivers, load=load,
                             reasons=reasons)


def _worst_z(a: AthleteAssessment) -> float:
    zs = [d.decline_z for d in a.domains if d.decline_z is not None]
    return min(zs) if zs else 0.0


def assess_squad(readings: list[Reading],
                 today: date) -> list[AthleteAssessment]:
    """Assess every athlete with data. Sorted worst-first."""
    by_athlete: dict[str, list[Reading]] = defaultdict(list)
    for r in readings:
        by_athlete[r.athlete_id].append(r)
    out = [a for group in by_athlete.values()
           if (a := assess_athlete(group, today)) is not None]
    return sorted(out, key=lambda a: (SEVERITY[a.status], _worst_z(a)))
