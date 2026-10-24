"""Readiness: a multi-domain morning readiness brief.

Deterministic multi-domain engine (perceptual/autonomic/neuromuscular),
convergence flagging, load/ACWR context-only, anonymized number-guarded
narration. The AI never writes a number. It surfaces availability, never
predicts injury.
"""

from .adapters import CSVAdapter, SyntheticCSVAdapter
from .brief import build_brief, post_to_slack, render_text
from .engine import assess_athlete, assess_squad
from .merge import resolve_roster
from .models import (AthleteAssessment, Brief, Domain, ReadinessDriver, Reading,
                     Status, WeeklyReport)
from .report import build_weekly_report, render_report_html
from .weekly import rollup_squad

__all__ = [
    "AthleteAssessment", "Brief", "Domain", "ReadinessDriver", "Reading",
    "Status", "WeeklyReport", "CSVAdapter", "SyntheticCSVAdapter", "assess_athlete",
    "assess_squad", "build_brief", "post_to_slack", "render_text",
    "resolve_roster", "build_weekly_report", "render_report_html", "rollup_squad",
]
