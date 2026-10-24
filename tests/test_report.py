from datetime import date

from readiness.models import Reading
from readiness.report import build_weekly_report, render_report_html

END = date(2026, 7, 7)


def _demo_readings():
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))
    from generate_data import generate
    return [Reading(**r) for r in generate()]


def test_story_over_a_week(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    report = build_weekly_report(_demo_readings(), END)
    by = {w.name: w for w in report.athletes}
    assert report.total == 9
    assert by["D. Silva"].week_status.value == "review"
    assert by["A. Rivera"].week_status.value == "monitor"
    assert by["R. Bennett"].week_status.value == "monitor"


def test_render_contains_names_labels_disclaimer_svg(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    report = build_weekly_report(_demo_readings(), END)
    html = render_report_html(report, generated=END)
    assert "D. Silva" in html            # real names re-attached on the way out
    assert "REVIEW" in html and "neuromuscular" in html
    assert "synthetic" in html.lower()
    assert "The AI never writes a number" in html
    assert html.count("<svg") >= len(report.flagged)  # a sparkline per flagged card


def test_flagged_notes_are_filled(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    report = build_weekly_report(_demo_readings(), END)
    assert all(w.note for w in report.flagged)
    for w in report.flagged:            # names re-attached, aliases gone
        assert "Athlete " not in w.note
