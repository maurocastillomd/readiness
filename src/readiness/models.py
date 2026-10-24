"""Data models for the multi-domain Readiness pipeline.

A Reading is one athlete-day-metric value (what an adapter delivers).
DomainAssessment is what the engine computes for one response domain;
AthleteAssessment aggregates the response domains into an availability
status by convergence, with load/ACWR carried as context. A Brief is the
assembled morning message.

Every number a coach reads exists on an assessment before any language
model is involved. The model phrases; it never computes. Nothing here
predicts injury — it surfaces individual change in readiness.
"""

from __future__ import annotations

from datetime import date
from enum import Enum

from pydantic import BaseModel, Field


class Status(str, Enum):
    REVIEW = "review"
    MONITOR = "monitor"
    CLEARED = "cleared"


class Domain(str, Enum):
    PERCEPTUAL = "perceptual"      # subjective wellness
    AUTONOMIC = "autonomic"        # HRV
    NEUROMUSCULAR = "neuromuscular"  # CMJ strategy


class ReadinessDriver(str, Enum):
    PERCEPTUAL = "perceptual"
    AUTONOMIC = "autonomic"
    NEUROMUSCULAR = "neuromuscular"


class MetricSpec(BaseModel):
    domain: Domain
    column: str          # matches Reading.metric
    label: str
    unit: str
    higher_is_worse: bool
    rolling_days: int    # 7 for HRV (rolling mean), 1 otherwise


METRICS: dict[Domain, MetricSpec] = {
    Domain.PERCEPTUAL: MetricSpec(
        domain=Domain.PERCEPTUAL, column="wellness_score",
        label="Wellness", unit="pts", higher_is_worse=False, rolling_days=1),
    Domain.AUTONOMIC: MetricSpec(
        domain=Domain.AUTONOMIC, column="hrv_lnrmssd",
        label="HRV (ln rMSSD)", unit="", higher_is_worse=False, rolling_days=7),
    Domain.NEUROMUSCULAR: MetricSpec(
        domain=Domain.NEUROMUSCULAR, column="rsi_mod",
        label="RSI-mod", unit="", higher_is_worse=False, rolling_days=1),
}

# context metric column names (never flag)
SRPE = "srpe_au"
HSR = "hsr_m"
TOTAL = "total_m"


def goodness_specs() -> dict[Domain, str]:
    """Map each response domain to its metric column (helper for callers)."""
    return {d: s.column for d, s in METRICS.items()}


class Reading(BaseModel):
    """One athlete-day-metric value, as delivered by an adapter."""

    athlete_id: str
    name: str
    pos: str
    day: date
    metric: str
    value: float
    source: str = "synthetic"


class Baseline(BaseModel):
    mean: float
    sd: float
    n: int
    swc: float  # 0.2 x SD, on the goodness scale


class DomainAssessment(BaseModel):
    domain: Domain
    status: Status
    fresh: bool                    # a recent-enough reading exists
    today: float | None            # raw scale, human units
    base: Baseline | None
    pct: float | None
    decline_z: float | None        # goodness scale: a decline is negative
    consecutive_declines: int = 0
    reasons: list[str] = Field(default_factory=list)

    @property
    def assessable(self) -> bool:
        return self.fresh and self.decline_z is not None


class LoadContext(BaseModel):
    """Load/workload CONTEXT. Never sets availability status."""

    srpe_today: float | None = None
    srpe_z: float | None = None
    spike: bool = False
    hsr_today: float | None = None
    total_today: float | None = None
    acwr: float | None = None


class AthleteAssessment(BaseModel):
    athlete_id: str
    name: str
    pos: str
    status: Status                       # convergence across response domains
    domains: list[DomainAssessment]
    drivers: list[ReadinessDriver]       # non-cleared domains, worst first
    load: LoadContext
    reasons: list[str] = Field(default_factory=list)

    def flagged_domains(self) -> list[DomainAssessment]:
        return [d for d in self.domains if d.status is not Status.CLEARED]


class Flag(BaseModel):
    assessment: AthleteAssessment
    note: str


class Brief(BaseModel):
    day: date
    summary: str
    flags: list[Flag]
    cleared: list[AthleteAssessment]
    total: int

    @property
    def cleared_count(self) -> int:
        return len(self.cleared)


class DailyPoint(BaseModel):
    day: date
    z: float


class AthleteWeek(BaseModel):
    athlete_id: str
    name: str
    pos: str
    week_status: Status
    watch: bool
    days_tested: int
    days_flagged: int
    week_mean_z: float
    prior_mean_z: float | None
    delta_z: float | None
    drivers: list[ReadinessDriver]
    acwr_end: float | None
    load_spike: bool
    daily_z: list[DailyPoint]
    worst_day: AthleteAssessment
    note: str = ""


class WeeklyReport(BaseModel):
    week_start: date
    week_end: date
    summary: str
    athletes: list[AthleteWeek]
    total: int

    @property
    def flagged(self) -> list[AthleteWeek]:
        return [w for w in self.athletes if w.week_status is not Status.CLEARED]

    @property
    def watch(self) -> list[AthleteWeek]:
        return [w for w in self.athletes if w.watch]

    @property
    def cleared_count(self) -> int:
        return self.total - len(self.flagged) - len(self.watch)
