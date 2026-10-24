"""The weekly rollup. All math, zero AI.

Rolls the multi-domain daily engine over the last 7 days into one row per
athlete: worst status of the week, how many days flagged, which domains drove
it, the week-over-week trend, and a WATCH for athletes cleared all week but
trending down. Load and ACWR ride along as context — they never flag or watch.
"""

from __future__ import annotations

import statistics
from datetime import date, timedelta

from .engine import SEVERITY, assess_athlete
from .models import (AthleteAssessment, AthleteWeek, DailyPoint, Domain,
                     ReadinessDriver, Reading, Status, WeeklyReport)

WEEK_DAYS = 7
WATCH_DELTA_Z = -0.4  # twice the smallest worthwhile change (0.2 z)


def _day_z(a: AthleteAssessment) -> float | None:
    """Daily readiness index: the worst assessable domain that day."""
    zs = [d.decline_z for d in a.domains if d.assessable]
    return min(zs) if zs else None


def _assessed(readings: list[Reading], start: date,
              end: date) -> list[tuple[date, AthleteAssessment, float]]:
    out: list[tuple[date, AthleteAssessment, float]] = []
    d = start
    while d <= end:
        a = assess_athlete(readings, d)
        if a is not None:
            z = _day_z(a)
            if z is not None:
                out.append((d, a, z))
        d += timedelta(days=1)
    return out


def rollup_athlete(readings: list[Reading], athlete_id: str,
                   end: date) -> AthleteWeek | None:
    rs = [r for r in readings if r.athlete_id == athlete_id]
    week_start = end - timedelta(days=WEEK_DAYS - 1)
    prior_end = week_start - timedelta(days=1)
    prior_start = prior_end - timedelta(days=WEEK_DAYS - 1)

    week = _assessed(rs, week_start, end)
    if not week:
        return None
    prior = _assessed(rs, prior_start, prior_end)

    week_status = min((a.status for _, a, _ in week), key=lambda s: SEVERITY[s])
    days_flagged = sum(1 for _, a, _ in week if a.status is not Status.CLEARED)
    week_mean_z = round(statistics.fmean([z for _, _, z in week]), 2)
    prior_mean_z = round(statistics.fmean([z for _, _, z in prior]), 2) if prior else None
    delta_z = round(week_mean_z - prior_mean_z, 2) if prior_mean_z is not None else None

    dom_min: dict[Domain, float] = {}
    dom_flagged: set[Domain] = set()
    for _, a, _ in week:
        for dd in a.domains:
            if dd.assessable:
                dom_min[dd.domain] = min(dom_min.get(dd.domain, 0.0), dd.decline_z)
            if dd.status is not Status.CLEARED:
                dom_flagged.add(dd.domain)
    drivers = [ReadinessDriver(dom.value)
               for dom in sorted(dom_flagged, key=lambda dom: dom_min.get(dom, 0.0))]

    worst_day = min(week, key=lambda t: (SEVERITY[t[1].status], t[2]))[1]
    ident = week[0][1]
    daily_z = [DailyPoint(day=d, z=round(z, 2)) for d, _, z in week]
    watch = (week_status is Status.CLEARED and delta_z is not None
             and delta_z <= WATCH_DELTA_Z)

    return AthleteWeek(
        athlete_id=ident.athlete_id, name=ident.name, pos=ident.pos,
        week_status=week_status, watch=watch, days_tested=len(week),
        days_flagged=days_flagged, week_mean_z=week_mean_z,
        prior_mean_z=prior_mean_z, delta_z=delta_z, drivers=drivers,
        acwr_end=worst_day.load.acwr, load_spike=worst_day.load.spike,
        daily_z=daily_z, worst_day=worst_day)


def rollup_squad(readings: list[Reading], end: date) -> list[AthleteWeek]:
    ids: list[str] = []
    seen: set[str] = set()
    for r in readings:
        if r.athlete_id not in seen:
            seen.add(r.athlete_id)
            ids.append(r.athlete_id)
    weeks = [w for aid in ids if (w := rollup_athlete(readings, aid, end)) is not None]
    return sorted(weeks, key=lambda w: (SEVERITY[w.week_status], not w.watch,
                                        w.week_mean_z))
