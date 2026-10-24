"""Run the whole pipeline end to end and print the morning brief.

    python3 scripts/run_brief.py                 # templates only, no key needed
    ANTHROPIC_API_KEY=... python3 scripts/run_brief.py   # Claude phrases the notes
    SLACK_WEBHOOK_URL=... python3 scripts/run_brief.py --post   # deliver to Slack

adapter -> merge -> engine -> anonymize -> narrate -> verify -> brief
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from readiness import (SyntheticCSVAdapter, assess_squad, build_brief,
                       post_to_slack, render_text, resolve_roster)
from readiness.narrate import DEFAULT_MODEL


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(Path(__file__).parent.parent / "data" / "synthetic.csv"))
    ap.add_argument("--date", default="2026-07-07")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--post", action="store_true")
    args = ap.parse_args()

    today = date.fromisoformat(args.date)
    readings = SyntheticCSVAdapter(args.data).fetch(today - timedelta(days=45), today)
    readings = resolve_roster(readings, {})  # synthetic ids are already canonical
    assessments = assess_squad(readings, today)
    brief = build_brief(assessments, today, model=args.model)

    print(render_text(brief))
    print()
    if os.environ.get("ANTHROPIC_API_KEY"):
        print(f"[narration: {args.model}, anonymized in, every number verified "
              f"against the engine]")
    else:
        print("[narration: deterministic templates — set ANTHROPIC_API_KEY for "
              "model phrasing]")

    if args.post:
        webhook = os.environ.get("SLACK_WEBHOOK_URL")
        if not webhook:
            sys.exit("SLACK_WEBHOOK_URL is not set")
        print(f"[posted to Slack: HTTP {post_to_slack(brief, webhook)}]")


if __name__ == "__main__":
    main()
