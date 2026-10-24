"""Adapters: how raw data gets in.

Every source gets an adapter that returns the same thing — a list of
Reading objects. The engine never knows or cares where the data came from.
Swap the synthetic CSV for a VALD, Catapult, or HRV export and nothing
downstream changes.

Only the synthetic adapter ships here. Real-platform adapters implement
fetch() against each vendor's API/export and are private to a team
engagement — credentials and data agreements live there, not in a public
repo.
"""

from __future__ import annotations

import csv
from datetime import date
from pathlib import Path
from typing import Protocol

from .models import Reading


class Adapter(Protocol):
    def fetch(self, start: date, end: date) -> list[Reading]: ...


class SyntheticCSVAdapter:
    """Long-form readings CSV.

    Columns: athlete_id,name,pos,day,metric,value,source
    """

    def __init__(self, path: str | Path):
        self.path = Path(path)

    def fetch(self, start: date, end: date) -> list[Reading]:
        readings: list[Reading] = []
        with open(self.path, newline="") as f:
            for row in csv.DictReader(f):
                day = date.fromisoformat(row["day"])
                if start <= day <= end:
                    readings.append(Reading(
                        athlete_id=row["athlete_id"], name=row["name"],
                        pos=row["pos"], day=day, metric=row["metric"],
                        value=float(row["value"]),
                        source=row.get("source", "synthetic")))
        return readings


class CSVAdapter:
    """A real, generic adapter for a wide vendor export.

    Most systems (a force-plate report, a GPS export, an AMS pull) put one row
    per athlete-day with many metric columns. This turns that into the engine's
    normalized stream: give it which columns hold identity and a map from each
    source column to the engine's metric name, and it emits one Reading per
    athlete-day-metric. Writing an adapter for a new system is exactly this —
    column plumbing. The engine downstream never changes.

    metric_map: {source_column_name: engine_metric_name}
    e.g. {"RSI_modified": "rsi_mod", "ln_rMSSD": "hrv_lnrmssd"}
    """

    def __init__(self, path: str | Path, *, id_col: str, name_col: str,
                 pos_col: str, day_col: str, metric_map: dict[str, str],
                 source: str = "csv"):
        self.path = Path(path)
        self.id_col = id_col
        self.name_col = name_col
        self.pos_col = pos_col
        self.day_col = day_col
        self.metric_map = dict(metric_map)
        self.source = source

    def fetch(self, start: date, end: date) -> list[Reading]:
        readings: list[Reading] = []
        with open(self.path, newline="") as f:
            for row in csv.DictReader(f):
                day = date.fromisoformat(row[self.day_col].strip())
                if not (start <= day <= end):
                    continue
                for src_col, metric in self.metric_map.items():
                    cell = (row.get(src_col) or "").strip()
                    if cell == "":  # a missing metric that day is absent, not zero
                        continue
                    readings.append(Reading(
                        athlete_id=row[self.id_col].strip(),
                        name=row[self.name_col].strip(),
                        pos=row[self.pos_col].strip(),
                        day=day, metric=metric, value=float(cell),
                        source=self.source))
        return readings
