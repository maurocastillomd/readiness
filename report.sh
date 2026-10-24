#!/usr/bin/env bash
# Build the weekly Readiness report (HTML, print-to-PDF ready).
#
#   ./report.sh              write reports/readiness-week-<date>.html
#
# Secrets are read from a local, git-ignored .env (ANTHROPIC_API_KEY optional).
# Same loading as run.sh.

set -euo pipefail
cd "$(dirname "$0")"

if [ ! -x .venv/bin/python ]; then
  python3 -m venv .venv
  .venv/bin/pip -q install pydantic pytest anthropic
fi

[ -f .env ] && export $(grep -vE '^\s*#' .env | xargs)

.venv/bin/python scripts/run_report.py "$@"
