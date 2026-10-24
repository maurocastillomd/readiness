"""Assemble and deliver the morning brief.

Pipeline: adapter -> merge -> engine -> anonymize -> narrate -> verify -> deliver.
Real names re-attach here, after narration, on the way out.
"""

from __future__ import annotations

import json
import urllib.request
from datetime import date

from .anonymize import Roster
from .models import AthleteAssessment, Brief, Flag, Status
from .narrate import DEFAULT_MODEL, narrate_note, template_summary

STATUS_LABEL = {Status.REVIEW: "REVIEW", Status.MONITOR: "MONITOR",
                Status.CLEARED: "CLEARED"}


def build_brief(assessments: list[AthleteAssessment], today: date,
                model: str = DEFAULT_MODEL) -> Brief:
    roster = Roster(sorted(assessments, key=lambda a: a.athlete_id))
    flagged = [a for a in assessments if a.status is not Status.CLEARED]
    cleared = [a for a in assessments if a.status is Status.CLEARED]
    flags = []
    for a in flagged:
        note = narrate_note(a, roster, model=model)
        flags.append(Flag(assessment=a, note=roster.deanonymize(note)))
    summary = template_summary(len(flagged), len(cleared), len(assessments))
    return Brief(day=today, summary=summary, flags=flags, cleared=cleared,
                 total=len(assessments))


def render_text(brief: Brief) -> str:
    lines = [f"*Readiness — {brief.day.strftime('%A, %B %-d')}*", brief.summary, ""]
    for f in brief.flags:
        a = f.assessment
        drivers = ", ".join(d.value for d in a.drivers)
        lines.append(f"[{STATUS_LABEL[a.status]}] {a.name} ({a.pos}) "
                     f"| readiness drivers: {drivers}")
        lines.append(f"  {f.note}")
        lines.append("")
    if brief.cleared:
        names = ", ".join(a.name for a in brief.cleared)
        lines.append(f"Cleared ({brief.cleared_count}/{brief.total}): {names}")
    return "\n".join(lines).strip()


def post_to_slack(brief: Brief, webhook_url: str) -> int:
    payload = json.dumps({"text": render_text(brief)}).encode()
    req = urllib.request.Request(webhook_url, data=payload,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req) as resp:
        return resp.status
