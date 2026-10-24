from datetime import date

from readiness.adapters import SyntheticCSVAdapter
from readiness.merge import resolve_roster
from readiness.models import Reading


def test_resolve_roster_maps_source_names_to_ids():
    raw = [
        Reading(athlete_id="Silva, D.", name="Silva, D.", pos="RHP",
                day="2026-07-07", metric="rsi_mod", value=0.5, source="vald"),
        Reading(athlete_id="D Silva", name="D Silva", pos="RHP",
                day="2026-07-07", metric="hrv_lnrmssd", value=4.0, source="oura"),
    ]
    roster_map = {"Silva, D.": ("A01", "D. Silva"), "D Silva": ("A01", "D. Silva")}
    merged = resolve_roster(raw, roster_map)
    assert {r.athlete_id for r in merged} == {"A01"}
    assert {r.name for r in merged} == {"D. Silva"}


def test_unmapped_reading_keeps_its_own_id():
    raw = [Reading(athlete_id="A09", name="E. Cruz", pos="RP",
                   day="2026-07-07", metric="rsi_mod", value=0.4, source="s")]
    merged = resolve_roster(raw, {})
    assert merged[0].athlete_id == "A09"


def test_csv_adapter_reads_long_form(tmp_path):
    p = tmp_path / "r.csv"
    p.write_text("athlete_id,name,pos,day,metric,value,source\n"
                 "A01,D. Silva,RHP,2026-07-07,rsi_mod,0.51,forceplate\n")
    rows = SyntheticCSVAdapter(p).fetch(date(2026, 6, 1), date(2026, 7, 7))
    assert len(rows) == 1 and isinstance(rows[0], Reading)
    assert rows[0].metric == "rsi_mod" and rows[0].source == "forceplate"
