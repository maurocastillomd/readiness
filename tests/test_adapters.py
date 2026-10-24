from datetime import date

from readiness.adapters import CSVAdapter
from readiness.models import Reading


def _wide(tmp_path, body, header):
    p = tmp_path / "export.csv"
    p.write_text(header + "\n" + body)
    return p


HEADER = "id,athlete,position,date,RSI_modified,ln_rMSSD,wellness"
MAP = {"RSI_modified": "rsi_mod", "ln_rMSSD": "hrv_lnrmssd", "wellness": "wellness_score"}


def _adapter(path):
    return CSVAdapter(path, id_col="id", name_col="athlete", pos_col="position",
                      day_col="date", metric_map=MAP, source="vald")


def test_wide_export_becomes_one_reading_per_metric(tmp_path):
    # a realistic vendor export: one row per athlete-day, many metric columns
    p = _wide(tmp_path,
              "A01,D. Silva,RHP,2026-07-07,0.49,4.21,19.27\n"
              "A02,A. Rivera,OF,2026-07-07,0.57,4.31,21.25\n", HEADER)
    rows = _adapter(p).fetch(date(2026, 6, 1), date(2026, 7, 7))
    assert len(rows) == 6  # 2 athletes x 3 metrics
    assert all(isinstance(r, Reading) for r in rows)
    silva_rsi = [r for r in rows if r.athlete_id == "A01" and r.metric == "rsi_mod"]
    assert len(silva_rsi) == 1
    assert silva_rsi[0].value == 0.49
    assert silva_rsi[0].name == "D. Silva" and silva_rsi[0].source == "vald"


def test_blank_metric_cell_is_skipped_not_zeroed(tmp_path):
    # HRV missing for that athlete-day — must not become value 0.0
    p = _wide(tmp_path, "A01,D. Silva,RHP,2026-07-07,0.49,,19.27\n", HEADER)
    rows = _adapter(p).fetch(date(2026, 6, 1), date(2026, 7, 7))
    metrics = {r.metric for r in rows}
    assert metrics == {"rsi_mod", "wellness_score"}  # no hrv reading emitted


def test_date_window_is_honored(tmp_path):
    p = _wide(tmp_path,
              "A01,D. Silva,RHP,2026-07-07,0.49,4.21,19.27\n"
              "A01,D. Silva,RHP,2026-05-01,0.55,4.30,20.10\n", HEADER)
    rows = _adapter(p).fetch(date(2026, 6, 1), date(2026, 7, 7))
    assert {r.day for r in rows} == {date(2026, 7, 7)}
