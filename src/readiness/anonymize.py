"""The privacy wall. Names come off before the model sees anything.

The engine works on real identities. Before any text reaches a language
model, every athlete becomes "Athlete N". Code re-attaches the real name
after. The model cannot leak what it never sees.
"""

from __future__ import annotations

from .models import AthleteAssessment


class Roster:
    """A per-run mapping between real athletes and anonymous aliases."""

    def __init__(self, assessments: list[AthleteAssessment]):
        self._alias: dict[str, str] = {}
        self._real: dict[str, tuple[str, str]] = {}  # alias -> (name, pos)
        for i, a in enumerate(assessments, start=1):
            alias = f"Athlete {i}"
            self._alias[a.athlete_id] = alias
            self._real[alias] = (a.name, a.pos)

    def alias(self, athlete_id: str) -> str:
        return self._alias[athlete_id]

    def names(self) -> list[str]:
        return [name for name, _ in self._real.values()]

    def deanonymize(self, text: str) -> str:
        """Swap aliases back to real names. Longest alias first so
        'Athlete 12' is never half-replaced by 'Athlete 1'."""
        for alias in sorted(self._real, key=len, reverse=True):
            name, _pos = self._real[alias]
            text = text.replace(alias, name)
        return text

    def assert_clean(self, text: str) -> None:
        """Raise if a real name slipped into text bound for the model."""
        for name in self.names():
            if name in text:
                raise ValueError(
                    f"Real name {name!r} in model-bound text. Refusing to send."
                )
