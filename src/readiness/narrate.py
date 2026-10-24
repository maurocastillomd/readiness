"""Narration: the only file that talks to a language model.

The rule that makes this system trustworthy:

    The AI does not write numbers.

Code computed every fact on the assessment. The model only restates them in
plain English. Every number in the output is checked against the engine's
numbers; one invented number and the output is discarded for a deterministic
template. No key? Templates run the whole pipeline. The model is a phrasing
layer, never a dependency. The model surfaces availability — never injury,
never prediction.
"""

from __future__ import annotations

import os
import re

from .anonymize import Roster
from .engine import MONITOR_DECLINE_SESSIONS
from .models import METRICS, AthleteAssessment, AthleteWeek, Domain, Status

DEFAULT_MODEL = "claude-sonnet-5"
_NUM_RE = re.compile(r"-?\d+(?:\.\d+)?")

_LABELS = {d: METRICS[d].label for d in METRICS}


def facts_for(a: AthleteAssessment, roster: Roster) -> dict:
    return {
        "athlete": roster.alias(a.athlete_id),
        "position": a.pos,
        "status": a.status.value,
        "drivers": [d.value for d in a.drivers],
        "flagged_domains": {
            d.domain.value: {
                "metric": _LABELS[d.domain],
                "today": d.today,
                "change_pct_vs_28day_baseline": d.pct,
                "decline_z": d.decline_z,
                "consecutive_declines": d.consecutive_declines,
            }
            for d in a.flagged_domains()
        },
        "load_context": {
            "srpe_z": a.load.srpe_z,
            "load_spike": a.load.spike,
            "workload_acwr": a.load.acwr,
        },
        "baseline_window_days": 28,
    }


def _collect_numbers(value, out: set[float]) -> None:
    if isinstance(value, bool):
        return
    if isinstance(value, (int, float)):
        for v in (value, abs(value), round(value), abs(round(value))):
            out.add(float(v))
    elif isinstance(value, str):
        for tok in _NUM_RE.findall(value):
            _collect_numbers(float(tok), out)
    elif isinstance(value, dict):
        for v in value.values():
            _collect_numbers(v, out)
    elif isinstance(value, (list, tuple)):
        for v in value:
            _collect_numbers(v, out)


def allowed_numbers(facts: dict) -> set[float]:
    out: set[float] = set()
    _collect_numbers(facts, out)
    return out


def verify_numbers(text: str, allowed: set[float]) -> list[str]:
    normalized = text.replace("−", "-")
    return [tok for tok in _NUM_RE.findall(normalized) if float(tok) not in allowed]


def template_note(a: AthleteAssessment, roster: Roster) -> str:
    alias = roster.alias(a.athlete_id)
    bits = ", ".join(
        (f"{_LABELS[d.domain]} {d.pct:+.1f}% vs 28-day baseline (z {d.decline_z:+.1f})"
         if d.pct is not None
         else f"{_LABELS[d.domain]} z {d.decline_z:+.1f} vs 28-day baseline")
        for d in a.flagged_domains())
    parts = [f"{alias}: {bits}."]
    for d in a.flagged_domains():
        if d.consecutive_declines >= MONITOR_DECLINE_SESSIONS:
            parts.append(f"{d.consecutive_declines} consecutive declining "
                         f"{_LABELS[d.domain]} readings.")
    if a.drivers:
        names = ", ".join(d.value for d in a.drivers)
        label = "Drivers" if len(a.drivers) > 1 else "Driver"
        parts.append(f"{label}: {names}.")
    if a.load.spike:
        parts.append("Context: acute training-load spike this week.")
    if a.load.acwr is not None:
        parts.append(f"Workload context: ACWR {a.load.acwr:.2f}.")
    if a.status is Status.REVIEW:
        parts.append("Worth a conversation before today's session.")
    elif a.status is Status.MONITOR:
        parts.append("Not past the review line. Eyes on him this week.")
    return " ".join(parts)


def template_summary(flagged: int, cleared: int, total: int) -> str:
    if flagged == 0:
        return f"All {total} athletes tested within their normal range this morning."
    return (f"{total} athletes tested this morning. {flagged} flagged for a look, "
            f"{cleared} within normal range.")


SYSTEM_PROMPT = """You write one short note for a pro team's performance staff.

You are given computed facts about one anonymized athlete's readiness. Your
ONLY job is to restate those facts in plain English a coach reads in five
seconds.

Hard rules:
- Use ONLY the numbers given. Never compute, estimate, or invent a number.
- Refer to the athlete ONLY by the alias given (e.g. "Athlete 3").
- Surface readiness only. Describe what changed and in which domain. No
  medical or clinical labels, no forecasting, no training prescriptions.
  You may suggest a conversation or keeping an eye on the athlete.
- The drivers are the computed domains that dropped. Load and ACWR are
  workload context only — never a cause, never a concern on their own.
- 1-3 short sentences. No preamble, no markdown, no bullet points.
"""


def _llm_note(facts: dict, model: str, system: str = SYSTEM_PROMPT) -> str | None:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        return None
    try:
        import anthropic
    except ImportError:
        return None
    try:
        client = anthropic.Anthropic(api_key=api_key)
        msg = client.messages.create(model=model, max_tokens=300,
                                     system=system,
                                     messages=[{"role": "user",
                                                "content": f"Facts:\n{facts}"}])
        return msg.content[0].text.strip()
    except Exception:
        return None


def narrate_note(a: AthleteAssessment, roster: Roster,
                 model: str = DEFAULT_MODEL) -> str:
    facts = facts_for(a, roster)
    roster.assert_clean(str(facts))
    text = _llm_note(facts, model)
    if text is None:
        return template_note(a, roster)
    if verify_numbers(text, allowed_numbers(facts)):
        return template_note(a, roster)
    if any(name in text for name in roster.names()):
        return template_note(a, roster)
    return text


# --- weekly executive summary ------------------------------------------------


def weekly_facts(rows: list[AthleteWeek], roster: Roster,
                 week_start, week_end) -> dict:
    flagged = [w for w in rows if w.week_status is not Status.CLEARED]
    watch = [w for w in rows if w.watch]
    return {
        "week_start": week_start.isoformat(),
        "week_end": week_end.isoformat(),
        "counts": {"tested": len(rows), "flagged": len(flagged),
                   "watch": len(watch),
                   "cleared": len(rows) - len(flagged) - len(watch)},
        "flagged": [{"athlete": roster.alias(w.athlete_id), "position": w.pos,
                     "status": w.week_status.value, "days_flagged": w.days_flagged,
                     "week_readiness_z": w.week_mean_z,
                     "delta_vs_prior_week": w.delta_z,
                     "drivers": [d.value for d in w.drivers]} for w in flagged],
        "watch": [{"athlete": roster.alias(w.athlete_id),
                   "week_readiness_z": w.week_mean_z,
                   "delta_vs_prior_week": w.delta_z} for w in watch],
        "baseline_window_days": 28,
    }


def template_weekly_summary(rows: list[AthleteWeek], roster: Roster,
                            week_start, week_end) -> str:
    flagged = [w for w in rows if w.week_status is not Status.CLEARED]
    watch = [w for w in rows if w.watch]
    cleared = len(rows) - len(flagged) - len(watch)
    if not flagged and not watch:
        return f"All {len(rows)} athletes held within their normal range this week."
    lead = (f"{len(rows)} athletes this week. {len(flagged)} flagged, "
            f"{len(watch)} to watch, {cleared} within normal range.")
    bits = []
    for w in flagged:
        drivers = ", ".join(d.value for d in w.drivers) or "readiness"
        bits.append(f"{roster.alias(w.athlete_id)} sat {w.week_status.value} on "
                    f"{w.days_flagged} day(s), driven by {drivers}.")
    if watch:
        names = ", ".join(roster.alias(w.athlete_id) for w in watch)
        bits.append(f"Trending down but not flagged: {names}.")
    return " ".join([lead] + bits)


WEEKLY_SYSTEM_PROMPT = """You write the one-paragraph executive summary of a pro
team's weekly readiness report, for the performance staff.

You are given computed facts about an anonymized squad's week. Restate them in
plain English a head coach reads in fifteen seconds.

Hard rules:
- Use ONLY the numbers given. Never compute, estimate, or invent a number.
- Refer to athletes ONLY by the alias given (e.g. "Athlete 3").
- Surface readiness only. Say who was flagged, by which domain, and who is
  trending down. No medical or clinical labels, no forecasting, no prescriptions.
- Load and ACWR are workload context only — never a cause or a concern on their own.
- 3-5 short sentences. No preamble, no markdown, no bullet points.
"""


def narrate_weekly_summary(rows: list[AthleteWeek], roster: Roster,
                           week_start, week_end, model: str = DEFAULT_MODEL) -> str:
    facts = weekly_facts(rows, roster, week_start, week_end)
    roster.assert_clean(str(facts))
    text = _llm_note(facts, model, system=WEEKLY_SYSTEM_PROMPT)
    if text is None:
        return template_weekly_summary(rows, roster, week_start, week_end)
    if verify_numbers(text, allowed_numbers(facts)):
        return template_weekly_summary(rows, roster, week_start, week_end)
    if any(name in text for name in roster.names()):
        return template_weekly_summary(rows, roster, week_start, week_end)
    return text
