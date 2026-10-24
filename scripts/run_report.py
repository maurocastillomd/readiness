"""Build the weekly readiness report as a self-contained HTML file.

    python3 scripts/run_report.py                 # templates, no key needed
    ANTHROPIC_API_KEY=... python3 scripts/run_report.py   # Claude phrases the summary

adapter -> merge -> rollup -> anonymize -> narrate -> verify -> HTML
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from readiness import (SyntheticCSVAdapter, build_weekly_report,
                       render_report_html, resolve_roster)
from readiness.narrate import DEFAULT_MODEL


def main() -> None:
    ap = argparse.ArgumentParser()
    root = Path(__file__).parent.parent
    ap.add_argument("--data", default=str(root / "data" / "synthetic.csv"))
    ap.add_argument("--date", default="2026-07-07", help="week end date")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--out", default=str(root / "reports"))
    args = ap.parse_args()

    end = date.fromisoformat(args.date)
    readings = SyntheticCSVAdapter(args.data).fetch(end - timedelta(days=45), end)
    readings = resolve_roster(readings, {})
    report = build_weekly_report(readings, end, model=args.model)

    html = render_report_html(report, generated=date.today())
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"readiness-week-{end.isoformat()}.html"
    out.write_text(html)

    print(f"{out}")
    print(f"{report.total} athletes · {len(report.flagged)} flagged · "
          f"{len(report.watch)} to watch · {report.cleared_count} within range")
    if os.environ.get("ANTHROPIC_API_KEY"):
        print(f"[summary: {args.model}, anonymized in, every number verified "
              f"against the engine]")
    else:
        print("[summary: deterministic template — set ANTHROPIC_API_KEY for "
              "model phrasing]")


if __name__ == "__main__":
    main()
