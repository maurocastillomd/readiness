#!/usr/bin/env bash
# Run the Readiness morning brief with one command.
#
#   ./run.sh              print the brief (Claude phrasing if a key is found)
#   ./run.sh --post       also post it to Slack
#
# Secrets are read from a local, git-ignored .env in this folder:
#   SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
#   ANTHROPIC_API_KEY=sk-...        (optional)
# Copy .env.example to .env and fill it in. Never commit .env.

set -euo pipefail
cd "$(dirname "$0")"

# 1. Load this repo's .env if present
[ -f .env ] && export $(grep -vE '^\s*#' .env | xargs)

.venv/bin/python scripts/run_brief.py "$@"
